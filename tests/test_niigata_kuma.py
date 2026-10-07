"""新潟県のクマ出没(件数だけを保存する)アダプタのテスト。ネットワークなし。

期待値は、固定ファイル(tests/fixtures/niigata_kuma.json: 取得した日付と市町村の列だけ、190行)を、アダプタとは別の方法
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
from sokuhou.sources import niigata_kuma as kuma

FX = json.loads((Path(__file__).parent / "fixtures" / "niigata_kuma.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)
HOST = urlparse(FX["webmap"]["operationalLayers"][0]["url"]).hostname
D, C = kuma.DATE_FIELD, kuma.CITY_FIELD
FORBIDDEN_KEYS = {"lat", "lon", "latitude", "longitude", "place", "sightings", "address", "addr", "mail", "email", "x", "y", "geometry", "detail"}


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


def naive_counts(fx):
    """Counted another way: the domain looked up in a loop, the JST date from gmtime, the fiscal year by hand."""
    names = {}
    for f in fx["layer"]["fields"]:
        if f["name"] == C:
            names = {str(v["code"]): v["name"] for v in (f.get("domain") or {}).get("codedValues", [])}
    monthly, cities, latest = Counter(), Counter(), ""
    for r in fx["rows"]:
        t = time.gmtime(r["attributes"][D] / 1000 + 9 * 3600)
        fy = t.tm_year if t.tm_mon >= 4 else t.tm_year - 1
        monthly[(f"R{fy - 2018:02d}", t.tm_mon)] += 1
        cities[(f"R{fy - 2018:02d}", names.get(str(r["attributes"][C]), r["attributes"][C]))] += 1
        latest = max(latest, f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d}")
    return monthly, cities, latest


class NiigataKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_the_fixture_is_small_and_holds_only_the_date_and_the_municipality(self):
        self.assertEqual(len(FX["rows"]), 190)
        self.assertLessEqual(len(FX["rows"]), 200)
        for r in FX["rows"]:
            self.assertEqual(set(r), {"attributes"})
            self.assertEqual(set(r["attributes"]), {D, C})
        self.assertEqual({f["name"] for f in FX["layer"]["fields"]} - {D, C}, {"objectid"})

    def test_monthly_and_municipal_counts_equal_an_independent_count_of_the_fixture(self):
        monthly, cities, latest = naive_counts(FX)
        got_monthly = {(fy, int(m)): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got_monthly, dict(monthly))
        got_cities = {(fy, c): n for c, m in self.out["municipalities"].items() for fy, ms in m["monthly"].items() for n in [sum(ms.values())]}
        self.assertEqual(got_cities, dict(cities))
        self.assertEqual(self.out["as_of"], latest)
        self.assertEqual(max(m["latest"] for m in self.out["municipalities"].values()), latest)

    def test_the_numbers_copied_from_a_hand_count(self):
        out = self.out
        self.assertEqual(out["mode"], "counts")
        self.assertEqual(out["source"], "niigata")
        self.assertEqual(out["fy_current"], "R08")
        self.assertEqual(out["as_of"], "2026-10-07")
        self.assertEqual(out["monthly"]["R08"], {"4": 5, "5": 11, "6": 16, "7": 71, "8": 47, "9": 28, "10": 7})
        self.assertEqual(out["monthly"]["R07"], {"1": 3, "2": 1, "3": 1})
        self.assertEqual(out["total_fy"], 185)
        self.assertEqual(len(out["municipalities"]), 21)
        for city, n in {"長岡市": 28, "上越市": 27, "糸魚川市": 20}.items():
            self.assertEqual(sum(out["municipalities"][city]["monthly"]["R08"].values()) + sum(out["municipalities"][city]["monthly"].get("R07", {}).values()), n)
        self.assertEqual(out["unparsed"], 0)
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertIn("新潟県", out["credit"])
        self.assertIn("件数だけ", out["credit"])

    def test_municipality_names_are_plain_names(self):
        for city in self.out["municipalities"]:
            self.assertRegex(city, r"^.+[市町村区]$")
            self.assertNotRegex(city, r"[0-9]|.+郡.+|新潟県")

    def test_the_stored_data_has_no_places_coordinates_or_text(self):
        keys = set()

        def walk(x):
            if isinstance(x, dict):
                keys.update(x)
                for v in x.values():
                    walk(v)
        walk(self.out)
        self.assertEqual({k.lower() for k in keys} & FORBIDDEN_KEYS, set())
        for m in self.out["municipalities"].values():
            self.assertEqual(set(m), {"monthly", "latest"})
        text = json.dumps(self.out, ensure_ascii=False)
        self.assertNotIn("@", text)
        run.check_counts_bear(None, self.out)
        with self.assertRaises(run.SanityError):
            run.check_counts_bear(None, {**self.out, "sightings": []})
        with self.assertRaises(run.SanityError):
            run.check_counts_bear(self.out, {**self.out, "total_fy": self.out["total_fy"] // 2})

    def test_only_the_date_and_the_municipality_are_requested_and_no_geometry(self):
        log = []
        collect(log=log)
        queries = [u for u in log if "/query?" in u]
        self.assertEqual(len(queries), 1)
        q = parse_qs(urlparse(queries[0]).query)
        self.assertEqual(q["outFields"], [f"{D},{C}"])
        self.assertEqual(q["returnGeometry"], ["false"])
        self.assertNotIn("*", queries[0])
        self.assertIn("2025-12-31 15:00:00", q["where"][0])      # 1 January 2026, JST midnight, written in UTC
        self.assertEqual(len(log), 3)                          # the web map, the layer description, one page
        self.assertTrue(all(u.startswith("https://") for u in log))

    def test_a_second_page_is_read_after_a_pause_and_gives_the_same_result(self):
        sleeps = []
        log = []
        out = collect(pages=3, log=log, sleep=sleeps.append)
        self.assertEqual(len([u for u in log if "/query?" in u]), 3)
        self.assertGreaterEqual(len(sleeps), 4)
        self.assertTrue(all(s >= 1.0 for s in sleeps))
        self.assertEqual(out["monthly"], self.out["monthly"])
        self.assertEqual(out["municipalities"], self.out["municipalities"])

    def test_the_default_fetch_is_the_polite_one(self):
        seen = []

        def fake(url):
            seen.append(url)
            return make_fetch(FX)(url)
        with mock.patch.object(kumalib, "polite_fetch", fake), mock.patch.object(kuma, "MIN_ROWS", 1):
            out = kuma.collect(sleep=lambda s: None, now=NOW)
        self.assertEqual(len(seen), 3)
        self.assertEqual(out["total_fy"], self.out["total_fy"])

    def test_a_renamed_or_retyped_column_is_refused(self):
        for field in (D, C):
            fx = copy.deepcopy(FX)
            for f in fx["layer"]["fields"]:
                if f["name"] == field:
                    f["name"] = field + "_2"
            with self.assertRaises(kuma.NiigataKumaSourceError):
                collect(fx)
        fx = copy.deepcopy(FX)
        for f in fx["layer"]["fields"]:
            if f["name"] == D:
                f["type"] = "esriFieldTypeString"
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_a_web_map_that_no_longer_points_at_exactly_one_layer_is_refused(self):
        fx = copy.deepcopy(FX)
        fx["webmap"]["operationalLayers"] = []
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)
        fx["webmap"]["operationalLayers"] = [FX["webmap"]["operationalLayers"][0], {"title": "x", "url": FX["webmap"]["operationalLayers"][0]["url"].replace("/rest/services/", "/rest/services/z")}]
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_too_few_rows_are_refused(self):
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(min_rows=500)
        fx = copy.deepcopy(FX)
        fx["rows"] = []
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_unreadable_dates_are_counted_and_too_many_of_them_refuse_the_data(self):
        fx = copy.deepcopy(FX)
        for r in fx["rows"][:3]:
            r["attributes"][D] = None                            # 3 of 190 = 1.6 %: counted, not stored
        out = collect(fx)
        self.assertEqual(out["unparsed"], 3)
        self.assertEqual(sum(sum(m.values()) for m in out["monthly"].values()), 187)
        for r in fx["rows"][:4]:
            r["attributes"][D] = "not a date"                    # 4 of 190 = 2.1 %
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_a_date_more_than_two_days_ahead_is_not_counted(self):
        fx = copy.deepcopy(FX)
        fx["rows"][0]["attributes"][D] = int(datetime(2026, 10, 20, tzinfo=kumalib.JST).timestamp() * 1000)
        out = collect(fx)
        self.assertEqual(out["unparsed"], 1)
        self.assertEqual(out["as_of"], self.out["as_of"])
        self.assertEqual(sum(sum(m.values()) for m in out["monthly"].values()), 189)
        fx["rows"][0]["attributes"][D] = int(datetime(2026, 10, 9, 0, 0, tzinfo=kumalib.JST).timestamp() * 1000)   # today + 2 days is allowed
        self.assertEqual(collect(fx)["unparsed"], 0)

    def test_blank_or_unknown_municipalities_are_counted_and_too_many_refuse_the_data(self):
        fx = copy.deepcopy(FX)
        for r in fx["rows"][:3]:
            r["attributes"][C] = "ZZZ"
        out = collect(fx)
        self.assertEqual(out["unparsed"], 3)
        self.assertEqual(sum(sum(m.values()) for m in out["monthly"].values()), 187)
        fx["rows"][3]["attributes"][C] = None
        with self.assertRaises(kuma.NiigataKumaSourceError):
            collect(fx)

    def test_an_error_answer_or_a_page_that_is_not_json_is_refused(self):
        good = make_fetch(FX)

        def err(url):
            return b'{"error":{"code":400,"message":"Invalid URL"}}' if "/query?" in url else good(url)

        def junk(url):
            return b"<html>maintenance</html>" if "/query?" in url else good(url)
        for f in (err, junk):
            with self.assertRaises(kuma.NiigataKumaSourceError):
                kuma.collect(fetch=f, sleep=lambda s: None, now=NOW)

    def test_the_error_is_a_value_error(self):
        self.assertTrue(issubclass(kuma.NiigataKumaSourceError, ValueError))
        self.assertTrue(issubclass(kuma.NiigataKumaSourceError, arcgis_counts.ArcgisCountsError))

    def test_norm_city(self):
        n = arcgis_counts.norm_city
        self.assertEqual(n("安達郡大玉村", "新潟県"), "大玉村")
        self.assertEqual(n("新潟県十日町市", "新潟県"), "十日町市")
        self.assertEqual(n(" 村上市 ", "新潟県"), "村上市")
        self.assertEqual(n("上市町", "新潟県"), "上市町")
        self.assertEqual(n("郡山市", "新潟県"), "郡山市")
        self.assertEqual(n("新潟市中央区", "新潟県"), "新潟市中央区")
        for junk in ("", None, "不明", "新潟県", "県外"):
            self.assertEqual(n(junk, "新潟県"), "")


if __name__ == "__main__":
    unittest.main()
