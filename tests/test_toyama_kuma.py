"""富山県のクマ出没(記録を一覧にする。県の書面の許可あり)アダプタのテスト。ネットワークなし。

期待値は、固定ファイル(tests/fixtures/toyama_kuma.json: 実データの抜粋180行。座標・概要・通報者の列は含まない)を、アダプタとは別の方法
(time.gmtime + 素朴なループ)で数えたものと、数えて書き写した値の両方。
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

from sokuhou import run
from sokuhou.sources import arcgis_counts, kumalib
from sokuhou.sources import toyama_kuma as kuma

FX = json.loads((Path(__file__).parent / "fixtures" / "toyama_kuma.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)
HOST = urlparse(FX["webmap"]["operationalLayers"][0]["url"]).hostname
D, C, T, A = kuma.DATE_FIELD, kuma.CITY_FIELD, kuma.TYPE_FIELD, kuma.AREA_FIELD
NOT_WANTED = {"lat", "lon", "latitude", "longitude", "geometry", "x", "y", "tsuhoinfo", "tsuhoname_2", "mail", "email", "address", "addr"}


def make_fetch(fx, log=None, pages=1):
    """A fake network: the web map, the layer description and the query pages (split into `pages` pages)."""
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
    """Counted another way: the JST date from gmtime, the fiscal year by hand."""
    monthly, latest = Counter(), ""
    for r in fx["rows"]:
        t = time.gmtime(r["attributes"][D] / 1000 + 9 * 3600)
        fy = t.tm_year if t.tm_mon >= 4 else t.tm_year - 1
        monthly[(f"R{fy - 2018:02d}", t.tm_mon)] += 1
        latest = max(latest, f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d}")
    return monthly, latest


class ToyamaKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_the_fixture_holds_only_the_wanted_columns(self):
        self.assertEqual(len(FX["rows"]), 180)
        for r in FX["rows"]:
            self.assertEqual(set(r), {"attributes"})
            self.assertEqual(set(r["attributes"]), set(kuma.FIELDS))
        self.assertEqual({f["name"] for f in FX["layer"]["fields"]} - set(kuma.FIELDS), {"objectid"})

    def test_monthly_counts_equal_an_independent_count_of_the_fixture(self):
        monthly, latest = naive(FX)
        got = {(fy, int(m)): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(monthly))
        self.assertEqual(self.out["as_of"], latest)
        self.assertEqual(self.out["sightings"][0]["observed_at"][:10], latest)

    def test_the_numbers_copied_from_a_hand_count(self):
        out = self.out
        self.assertNotIn("mode", out)                       # a record source, not a counts-only one
        self.assertEqual(out["source"], "toyama")
        self.assertEqual(out["fy_current"], "R08")
        self.assertEqual(out["as_of"], "2026-10-07")
        self.assertEqual(out["monthly"]["R08"], {"7": 70, "8": 35, "9": 16, "10": 9})
        self.assertEqual(out["monthly"]["R07"], {"1": 3, "2": 2, "3": 7, "12": 38})
        self.assertEqual(out["unparsed"], 0)
        self.assertEqual(out["sightings_in_window"], 180)
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertIn("許可", out["credit"])
        self.assertIn("富山県", out["credit"])
        # the store keeps the current fiscal year and the January-March before it (not December)
        self.assertEqual(len(out["sightings"]), 142)      # 70+35+16+9 of R08, and 3+2+7 of the previous January-March
        self.assertTrue(all(s["observed_at"] >= "2026-01-01" for s in out["sightings"]))

    def test_the_newest_row_is_a_full_record(self):
        s = self.out["sightings"][0]
        self.assertEqual(s, {"observed_at": "2026-10-07", "city": "小矢部市", "place": "嘉例谷", "count": 1, "kind": "目撃", "species": "ツキノワグマ"})

    def test_kinds_counts_and_places(self):
        by_kind = Counter(s["kind"] for s in self.out["sightings"])
        self.assertIn("人身被害", by_kind)
        self.assertEqual(set(by_kind) - {"目撃", "痕跡", "人身被害", "目撃（クマAIカメラ等）"}, set())
        injury = [s for s in self.out["sightings"] if s["kind"] == "人身被害"]
        self.assertEqual([(s["city"], s["place"], s["count"]) for s in injury], [("南砺市", "ブナオ峠", 1)])
        self.assertEqual(kuma._bears({"BearAdult": 1, "BearYoung": 1, "BearUnknown": 2}), 4)
        self.assertEqual(kuma._bears({"BearAdult": 0, "BearYoung": 0, "BearUnknown": 0}), None)
        self.assertEqual(kuma._bears({"BearAdult": None, "BearYoung": None, "BearUnknown": None}), None)
        self.assertEqual(kuma._bears({"BearAdult": 2.0}), 2)

    def test_municipality_names_are_plain_names(self):
        for s in self.out["sightings"]:
            self.assertRegex(s["city"], r"^.+[市町村区]$")
            self.assertNotRegex(s["city"], r"[0-9]|.+郡.+|富山県")

    def test_the_stored_data_has_no_coordinates_free_text_or_reporter(self):
        keys = set()

        def walk(x):
            if isinstance(x, dict):
                keys.update(x)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(self.out)
        self.assertEqual({k.lower() for k in keys} & NOT_WANTED, set())
        for s in self.out["sightings"]:
            self.assertEqual(set(s), {"observed_at", "city", "place", "count", "kind", "species"})
        self.assertNotIn("@", json.dumps(self.out, ensure_ascii=False))
        run.check_pref_bear(None, self.out)
        half = {**self.out, "sightings": self.out["sightings"][: len(self.out["sightings"]) // 3]}
        with self.assertRaises(run.SanityError):
            run.check_pref_bear(self.out, half)

    def test_only_the_wanted_columns_are_requested_and_no_geometry(self):
        log = []
        collect(log=log)
        queries = [u for u in log if "/query?" in u]
        self.assertEqual(len(queries), 1)
        q = parse_qs(urlparse(queries[0]).query)
        self.assertEqual(q["outFields"], [",".join(kuma.FIELDS)])
        self.assertEqual(q["returnGeometry"], ["false"])
        self.assertNotIn("*", queries[0])
        self.assertNotIn("Tsuho", queries[0])
        self.assertEqual(len(log), 3)                          # the web map, the layer description, one page
        self.assertTrue(all(u.startswith("https://") for u in log))

    def test_a_second_page_is_read_after_a_pause_and_gives_the_same_result(self):
        sleeps, log = [], []
        out = collect(pages=3, log=log, sleep=sleeps.append)
        self.assertEqual(len([u for u in log if "/query?" in u]), 3)
        self.assertGreaterEqual(len(sleeps), 4)
        self.assertTrue(all(s >= 1.0 for s in sleeps))
        self.assertEqual(out["monthly"], self.out["monthly"])
        self.assertEqual(out["sightings"], self.out["sightings"])

    def test_the_default_fetch_is_the_polite_one(self):
        seen = []

        def fake(url):
            seen.append(url)
            return make_fetch(FX)(url)
        with mock.patch.object(kumalib, "polite_fetch", fake), mock.patch.object(kuma, "MIN_ROWS", 1):
            out = kuma.collect(sleep=lambda s: None, now=NOW)
        self.assertEqual(len(seen), 3)
        self.assertEqual(out["sightings"], self.out["sightings"])

    def test_a_renamed_or_retyped_column_is_refused(self):
        for field in (D, C, A, T, "BearAdult"):
            fx = copy.deepcopy(FX)
            for f in fx["layer"]["fields"]:
                if f["name"] == field:
                    f["name"] = field + "_2"
            with self.assertRaises(kuma.ToyamaKumaSourceError):
                collect(fx)
        fx = copy.deepcopy(FX)
        for f in fx["layer"]["fields"]:
            if f["name"] == D:
                f["type"] = "esriFieldTypeString"
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)

    def test_a_web_map_that_no_longer_points_at_exactly_one_layer_is_refused(self):
        fx = copy.deepcopy(FX)
        fx["webmap"]["operationalLayers"] = []
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)
        fx["webmap"]["operationalLayers"] = [FX["webmap"]["operationalLayers"][0], {"title": "x", "url": FX["webmap"]["operationalLayers"][0]["url"].replace("/rest/services/", "/rest/services/z")}]
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)

    def test_too_few_rows_are_refused(self):
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(min_rows=500)
        fx = copy.deepcopy(FX)
        fx["rows"] = []
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)

    def test_unreadable_dates_are_counted_and_too_many_of_them_refuse_the_data(self):
        fx = copy.deepcopy(FX)
        for r in fx["rows"][:3]:
            r["attributes"][D] = None                            # 3 of 180 = 1.7 %: counted, not stored
        out = collect(fx)
        self.assertEqual(out["unparsed"], 3)
        self.assertEqual(out["sightings_in_window"], 177)
        for r in fx["rows"][:4]:
            r["attributes"][D] = "not a date"                    # 4 of 180 = 2.2 %
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)

    def test_a_date_more_than_two_days_ahead_is_not_stored(self):
        fx = copy.deepcopy(FX)
        fx["rows"][0]["attributes"][D] = int(datetime(2026, 10, 20, tzinfo=kumalib.JST).timestamp() * 1000)
        out = collect(fx)
        self.assertEqual(out["unparsed"], 1)
        self.assertEqual(out["as_of"], "2026-10-06")           # the newest row was the typo; the next one is the latest real day
        fx["rows"][0]["attributes"][D] = int(datetime(2026, 10, 9, 0, 0, tzinfo=kumalib.JST).timestamp() * 1000)   # today + 2 days is allowed
        self.assertEqual(collect(fx)["unparsed"], 0)

    def test_blank_or_unknown_municipalities_are_counted_and_too_many_refuse_the_data(self):
        fx = copy.deepcopy(FX)
        for r in fx["rows"][:3]:
            r["attributes"][C] = "ZZZ"
        out = collect(fx)
        self.assertEqual(out["unparsed"], 3)
        self.assertEqual(out["sightings_in_window"], 177)
        fx["rows"][3]["attributes"][C] = None
        fx["rows"][4]["attributes"][C] = None
        with self.assertRaises(kuma.ToyamaKumaSourceError):
            collect(fx)

    def test_rows_before_fiscal_year_R01_are_left_out_and_not_counted_as_unusable(self):
        fx = copy.deepcopy(FX)
        for r in fx["rows"][:5]:
            r["attributes"][D] = int(datetime(2017, 6, 1, tzinfo=kumalib.JST).timestamp() * 1000)
        out = collect(fx)
        self.assertEqual(out["unparsed"], 0)
        self.assertEqual(out["sightings_in_window"], 175)
        self.assertEqual(sorted(out["monthly"]), ["R07", "R08"])
        self.assertTrue(all(len(k) == 3 and k[1:].isdigit() for k in out["monthly"]))

    def test_a_blank_kind_is_a_sighting_and_a_blank_place_stays_blank(self):
        fx = copy.deepcopy(FX)
        fx["rows"][0]["attributes"][T] = None
        fx["rows"][0]["attributes"][A] = None
        s = collect(fx)["sightings"][0]
        self.assertEqual((s["kind"], s["place"]), ("目撃", ""))

    def test_an_error_answer_or_a_page_that_is_not_json_is_refused(self):
        good = make_fetch(FX)

        def err(url):
            return b'{"error":{"code":400,"message":"Invalid URL"}}' if "/query?" in url else good(url)

        def junk(url):
            return b"<html>maintenance</html>" if "/query?" in url else good(url)
        for f in (err, junk):
            with self.assertRaises(kuma.ToyamaKumaSourceError):
                kuma.collect(fetch=f, sleep=lambda s: None, now=NOW)

    def test_the_error_is_a_value_error(self):
        self.assertTrue(issubclass(kuma.ToyamaKumaSourceError, ValueError))

    def test_toyama_is_collected_as_a_record_source_with_the_record_check(self):
        src = next(s for s in run.GROUPS["kuma"] if s.name == "toyama_kuma")
        self.assertIs(src.check, run.check_pref_bear)
        self.assertIs(src.collect, kuma.collect)


if __name__ == "__main__":
    unittest.main()
