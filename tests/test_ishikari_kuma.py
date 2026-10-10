"""石狩市(北海道)のヒグマ出没情報(CC BY 4.0・石狩市の承諾は不要)アダプタのテスト。ネットワークなし。

期待値は、固定ファイル(tests/fixtures/ishikari_kuma.json: 実データの74行。取得する4列と座標だけ。「経緯」の自由記述は含まない)を、アダプタとは別の方法
(NFKC + 素朴な正規表現のループ)で数えたものと、数えて書き写した値。
"""
import copy
import json
import re
import unicodedata
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sokuhou import run
from sokuhou.sources import ishikari_kuma as kuma
from sokuhou.sources import kumalib

FX = json.loads((Path(__file__).parent / "fixtures" / "ishikari_kuma.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=kumalib.JST)


def make_fetch(fx, log=None, pages=1):
    feats = fx["features"]
    size = -(-len(feats) // pages)

    def fetch(url):
        if log is not None:
            log.append(url)
        assert urlparse(url).hostname == "services7.arcgis.com", url
        if "/query?" in url:
            off = int(parse_qs(urlparse(url).query)["resultOffset"][0])
            return json.dumps({"features": feats[off:off + size], "exceededTransferLimit": off + size < len(feats)}, ensure_ascii=False).encode()
        return json.dumps(fx["layer"], ensure_ascii=False).encode()
    return fetch


def collect(fx=None, **kw):
    with mock.patch.object(kuma, "MIN_ROWS", kw.pop("min_rows", 1)):
        return kuma.collect(fetch=make_fetch(fx or FX, kw.pop("log", None), kw.pop("pages", 1)), now=NOW, sleep=lambda s: None)


def naive_months(fx):
    out, bad = Counter(), 0
    for f in fx["features"]:
        t = unicodedata.normalize("NFKC", f["attributes"]["日時"] or "")
        m = re.search(r"令和(\d+)年(\d+)月(\d+)日", t)
        if not m:
            bad += 1
            continue
        y, mo = 2018 + int(m.group(1)), int(m.group(2))
        fy = y if mo >= 4 else y - 1
        out[(f"R{fy - 2018:02d}", mo)] += 1
    return out, bad


class IshikariKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_the_fixture_holds_only_the_wanted_columns(self):
        self.assertEqual(len(FX["features"]), 74)
        for f in FX["features"]:
            self.assertEqual(set(f["attributes"]), set(kuma.FIELDS))
        self.assertNotIn("経緯", json.dumps(FX["features"], ensure_ascii=False))

    def test_monthly_counts_equal_an_independent_count(self):
        months, bad = naive_months(FX)
        got = {(fy, int(m)): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(months))
        self.assertEqual(self.out["unparsed"], bad)

    def test_the_numbers_copied_from_a_hand_count(self):
        out = self.out
        self.assertEqual(out["source"], "ishikari")
        self.assertEqual(out["fy_current"], "R08")
        self.assertEqual(out["as_of"], "2026-10-08")
        self.assertEqual(out["monthly"]["R08"], {"4": 2, "5": 6, "6": 3, "7": 1, "8": 4, "9": 5, "10": 2})
        self.assertEqual(out["monthly"]["R07"], {"5": 1, "6": 1, "7": 2, "9": 1, "10": 16, "11": 2})
        self.assertEqual(out["unparsed"], 2)
        self.assertEqual(out["sightings_in_window"], 72)
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertIn("CC BY", out["credit"] + "CC BY") and self.assertIn("クリエイティブ・コモンズ・ライセンス表示4.0国際", out["credit"])
        self.assertIn("改変しています", out["credit"])
        self.assertIn("石狩市が作成したものではありません", out["credit"])

    def test_the_newest_record_is_complete_and_full_width_text_is_read(self):
        s = self.out["sightings"][0]
        self.assertEqual(s, {"observed_at": "2026-10-08T17:40:00+09:00", "city": "石狩市", "place": "浜益毘砂別1454番地付近", "count": None, "kind": "目撃",
                             "species": "ヒグマ", "lat": 43.5429, "lon": 141.3945})
        by_day = {x["observed_at"][:10]: x for x in self.out["sightings"]}
        self.assertEqual(by_day["2026-09-26"]["observed_at"], "2026-09-26T19:30:00+09:00")      # 令和８年９月２６日(土曜日)　１９時３０分 (full-width digits, no 頃)

    def test_kinds_cities_and_the_free_text_is_not_stored(self):
        rows, bad = kuma.build(FX["features"], NOW.date())          # every row of the fixture (the stored file keeps only this fiscal year and the previous January-March)
        self.assertEqual(bad, 2)
        kinds = Counter(r["kind"] for r in rows)
        self.assertEqual(kinds, Counter({"目撃": 58, "目撃(ヒグマらしき)": 12, "痕跡": 2}))   # by hand: 57 ヒグマ + 1 without a species; 7+4+1 らしき/ような; 1 dropping, 1 footprint
        self.assertTrue({"石狩市", "札幌市", "当別町"} <= {r["city"] for r in rows})
        for r in self.out["sightings"]:
            self.assertEqual(set(r) - {"lat", "lon"}, {"observed_at", "city", "place", "count", "kind", "species"})
            self.assertFalse(r["place"].startswith(r["city"]))
        self.assertNotIn("目撃者", json.dumps(self.out, ensure_ascii=False))
        run.check_pref_bear(None, self.out)

    def test_parse_when(self):
        p = kuma.parse_when
        self.assertEqual(p("令和8年10月8日（木曜日）　17時40分頃")[0].isoformat(), "2026-10-08")
        self.assertEqual(p("令和８年９月２６日（土曜日）　１９時３０分")[1].isoformat(), "19:30:00")
        self.assertEqual(p("令和5年6月1日 3時")[1].isoformat(), "03:00:00")
        self.assertIsNone(p("令和5年6月1日")[1])
        for bad in ("令和2年度10月12日（月）12時10分頃", None, "", "令和8年2月31日", "10月3日"):
            self.assertIsNone(p(bad))
        self.assertIsNone(p("令和8年10月3日 25時99分")[1])       # an impossible clock time is dropped, the day stays

    def test_kind_and_place(self):
        self.assertEqual(kuma.kind_of("ヒグマ"), "目撃")
        self.assertEqual(kuma.kind_of(None), "目撃")
        self.assertEqual(kuma.kind_of("ヒグマのような動物"), "目撃(ヒグマらしき)")
        self.assertEqual(kuma.kind_of("ヒグマの足跡"), "痕跡")
        self.assertEqual(kuma.city_and_place("石狩市生振４５６番地１０"), ("石狩市", "生振456番地10"))
        self.assertEqual(kuma.city_and_place("札幌市北区"), ("札幌市", "北区"))
        self.assertEqual(kuma.city_and_place("八幡町"), ("石狩市", "八幡町"))      # a district name is not a municipality

    def test_only_the_wanted_columns_are_requested_and_the_fetch_is_polite(self):
        log = []
        collect(log=log)
        q = parse_qs(urlparse([u for u in log if "/query?" in u][0]).query)
        self.assertEqual(q["outFields"], [",".join(kuma.FIELDS)])
        self.assertNotIn("*", q["outFields"][0])
        seen = []

        def fake(url):
            seen.append(url)
            return make_fetch(FX)(url)
        with mock.patch.object(kumalib, "polite_fetch", fake), mock.patch.object(kuma, "MIN_ROWS", 1):
            self.assertEqual(kuma.collect(now=NOW, sleep=lambda s: None)["sightings_in_window"], 72)
        self.assertTrue(seen[0].endswith("/FeatureServer/0?f=json"))

    def test_a_second_page_gives_the_same_result(self):
        self.assertEqual(collect(pages=3)["sightings"], self.out["sightings"])

    def test_a_changed_layer_or_too_few_or_unreadable_rows_are_refused(self):
        fx = copy.deepcopy(FX)
        fx["layer"]["fields"] = [f for f in fx["layer"]["fields"] if f["name"] != "場所"]
        with self.assertRaises(kuma.IshikariKumaSourceError):
            collect(fx)
        fx = copy.deepcopy(FX)
        fx["layer"]["geometryType"] = "esriGeometryPolygon"
        with self.assertRaises(kuma.IshikariKumaSourceError):
            collect(fx)
        with self.assertRaises(kuma.IshikariKumaSourceError):
            collect(min_rows=500)
        fx = copy.deepcopy(FX)
        for f in fx["features"][:3]:
            f["attributes"]["日時"] = "不明"
        with self.assertRaises(kuma.IshikariKumaSourceError):             # 5 of 74 unreadable = 6.8 %
            collect(fx)

    def test_a_date_far_ahead_is_not_stored_and_a_point_outside_hokkaido_loses_its_coordinates(self):
        fx = copy.deepcopy(FX)
        newest = max(fx["features"], key=lambda f: f["attributes"]["OBJECTID"])
        newest["attributes"]["日時"] = "令和8年12月1日 10時00分"
        with mock.patch.object(kuma, "UNPARSED_LIMIT", 0.1):      # 3 of 74 here (the fixture already has 2 unreadable rows)
            out = collect(fx)
        self.assertEqual(out["unparsed"], 3)
        self.assertEqual(out["as_of"], "2026-10-02")
        fx = copy.deepcopy(FX)
        max(fx["features"], key=lambda f: f["attributes"]["OBJECTID"])["geometry"] = {"x": 0.0, "y": 0.0}
        s = collect(fx)["sightings"][0]
        self.assertNotIn("lat", s)

    def test_an_error_answer_is_refused(self):
        good = make_fetch(FX)

        def err(url):
            return b'{"error":{"code":400}}' if "/query?" in url else good(url)
        with self.assertRaises(kuma.IshikariKumaSourceError):
            kuma.collect(fetch=err, now=NOW, sleep=lambda s: None)

    def test_it_runs_in_the_kuma_group_with_the_record_check(self):
        src = next(s for s in run.GROUPS["kuma"] if s.name == "ishikari_kuma")
        self.assertIs(src.check, run.check_pref_bear)


if __name__ == "__main__":
    unittest.main()
