"""新潟県のクマ出没(記録を一覧にする。県環境対策課の書面の許可あり)アダプタのテスト。ネットワークなし。

固定ファイル tests/fixtures/niigata_kuma.json は、実データの抜粋180行(日付・市町村・地区・種別・頭数の列と、位置だけ。通報者のアドレスと自由記述は含まない)。
"""
import copy
import json
import time
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sites.kuma import live as live_mod
from sokuhou import run
from sokuhou.sources import arcgis_counts, kumalib
from sokuhou.sources import niigata_kuma as kuma

FX = json.loads((Path(__file__).parent / "fixtures" / "niigata_kuma.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)
HOST = urlparse(FX["webmap"]["operationalLayers"][0]["url"]).hostname
D = kuma.DATE_FIELD
NOT_WANTED = {"field_9", "field_22", "field_19", "field_21", "mail", "email", "address", "tsuhoinfo"}       # 状況の自由記述・報告書の送信先・出没原因・時間


def make_fetch(fx, log=None, pages=1):
    rows = fx["rows"]
    size = -(-len(rows) // pages)

    def fetch(url):
        if log is not None:
            log.append(url)
        assert urlparse(url).hostname in ("www.arcgis.com", HOST), url
        if "/data?f=json" in url:
            return json.dumps(fx["webmap"], ensure_ascii=False).encode()
        if "/query?" in url:
            off = int(parse_qs(urlparse(url).query)["resultOffset"][0])
            chunk = rows[off:off + size]
            return json.dumps({"features": chunk, "exceededTransferLimit": off + size < len(rows)}, ensure_ascii=False).encode()
        return json.dumps(fx["layer"], ensure_ascii=False).encode()
    return fetch


def collect(fx=None, **kw):
    kw.setdefault("sleep", lambda s: None)
    with mock.patch.object(kuma, "MIN_ROWS", kw.pop("min_rows", 1)):
        return kuma.collect(fetch=make_fetch(fx or FX, kw.pop("log", None), kw.pop("pages", 1)), now=NOW, **kw)


def naive(fx):
    monthly, latest = Counter(), ""
    for r in fx["rows"]:
        t = time.gmtime(r["attributes"][D] / 1000 + 9 * 3600)
        if t.tm_year < 2019 or (t.tm_year == 2019 and t.tm_mon < 4):
            continue
        fy = t.tm_year if t.tm_mon >= 4 else t.tm_year - 1
        monthly[(f"R{fy - 2018:02d}", t.tm_mon)] += 1
        latest = max(latest, f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d}")
    return monthly, latest


class NiigataKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_the_fixture_holds_only_the_wanted_columns(self):
        self.assertEqual(len(FX["rows"]), 180)
        for r in FX["rows"]:
            self.assertEqual(set(r["attributes"]), set(kuma.FIELDS))
        self.assertFalse({f["name"] for f in FX["layer"]["fields"]} & NOT_WANTED)

    def test_monthly_counts_equal_an_independent_count_of_the_fixture(self):
        monthly, latest = naive(FX)
        got = {(fy, int(m)): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(monthly))
        self.assertEqual(self.out["as_of"], latest)
        self.assertEqual(self.out["sightings"][0]["observed_at"][:10], latest)

    def test_it_is_a_record_source_with_the_credit_the_prefecture_asked_for(self):
        out = self.out
        self.assertNotIn("mode", out)
        self.assertEqual((out["source"], out["fy_current"]), ("niigata", "R08"))
        self.assertIn("新潟県鳥獣被害対策支援センター「にいがたクマ出没マップ」", out["credit"])
        self.assertIn("許可", out["credit"])
        self.assertIn("新潟県が作成したものではありません", out["credit"])
        self.assertEqual(out["source_page"], kuma.PAGE)
        meta = live_mod.LIVE_SOURCES["niigata"]
        self.assertTrue(meta["license"])                       # so the CSV may carry it, with the credit as the condition
        self.assertNotIn("scope", meta)

    def test_a_sighting_has_date_city_place_kind_count_and_a_rounded_point(self):
        s = self.out["sightings"][0]
        self.assertEqual(set(s) - {"lat", "lon"}, {"observed_at", "city", "place", "count", "kind", "species"})
        self.assertEqual(s["species"], "ツキノワグマ")
        for s in self.out["sightings"]:
            self.assertTrue(s["city"].endswith(("市", "町", "村")), s)
            self.assertIn(s["kind"], {"目撃", "痕跡", "人身"})
            self.assertTrue(s["count"] is None or s["count"] >= 1)
            if "lat" in s:
                self.assertTrue(36.7 <= s["lat"] <= 38.6 and 137.3 <= s["lon"] <= 140.1)
                self.assertEqual(s["lat"], round(s["lat"], 4))
        self.assertTrue(any("lat" in s for s in self.out["sightings"]))

    def test_only_the_wanted_columns_are_requested_with_the_point_in_wgs84(self):
        log = []
        collect(log=log, pages=2)
        queries = [parse_qs(urlparse(u).query) for u in log if "/query?" in u]
        self.assertEqual(len(queries), 2)
        for q in queries:
            self.assertEqual(q["outFields"], [",".join(kuma.FIELDS)])
            self.assertEqual((q["returnGeometry"], q["outSR"], q["f"]), (["true"], ["4326"], ["json"]))
            self.assertFalse(set(q["outFields"][0].split(",")) & NOT_WANTED)

    def test_the_number_of_bears_is_read_from_the_prefectures_text(self):
        self.assertEqual([kuma._bears(x) for x in ("１頭", "2頭", "３頭", "不明", "", None, "0頭")], [1, 2, 3, None, None, None, None])

    def test_a_point_outside_the_prefecture_is_dropped_but_the_record_stays(self):
        fx = copy.deepcopy(FX)
        fx["rows"][0]["geometry"] = {"x": 0.0, "y": 0.0}
        fx["rows"][1]["geometry"] = {}
        out = collect(fx)
        by_date = {}
        for s in out["sightings"]:
            by_date.setdefault(s["observed_at"], []).append(s)
        first = fx["rows"][0]["attributes"]
        self.assertTrue(any("lat" not in s and s["place"] == (first[kuma.AREA_FIELD] or "").strip() for s in out["sightings"]))

    def test_rows_without_a_readable_date_or_city_are_counted_as_unparsed_and_too_many_stop_the_run(self):
        fx = copy.deepcopy(FX)
        fx["rows"][5]["attributes"][D] = None
        fx["rows"][6]["attributes"][kuma.CITY_FIELD] = "不明"
        out = collect(fx)
        self.assertEqual(out["unparsed"], 2)
        self.assertEqual(out["sightings_in_window"], 178)
        for r in fx["rows"][:30]:
            r["attributes"][D] = None
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_too_few_rows_a_lost_column_and_an_ambiguous_web_map_store_nothing(self):
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(min_rows=500)
        fx = copy.deepcopy(FX)
        fx["layer"]["fields"] = [f for f in fx["layer"]["fields"] if f["name"] != kuma.COUNT_FIELD]
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)
        fx = copy.deepcopy(FX)
        fx["webmap"]["operationalLayers"].append({"url": FX["webmap"]["operationalLayers"][0]["url"].replace("survey123_", "survey123_00")})
        with self.assertRaises(arcgis_counts.ArcgisCountsError):
            collect(fx)

    def test_the_run_checks_and_registration(self):
        run.check_pref_bear(None, self.out)
        with self.assertRaises(run.SanityError):
            run.check_pref_bear(self.out, {**self.out, "sightings": self.out["sightings"][:20]})
        src = {s.name: s for s in run.GROUPS["kuma"]}["niigata_kuma"]
        self.assertIs(src.check, run.check_pref_bear)
        self.assertIsNone(src.merge)


if __name__ == "__main__":
    unittest.main()
