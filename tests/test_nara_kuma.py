import json
import time
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sokuhou import run
from sokuhou.sources import kumacounts, kumalib
from sokuhou.sources import nara_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)
FORBIDDEN_KEYS = {"lat", "lon", "latitude", "longitude", "place", "places", "sightings", "address", "mail", "email", "remarks", "note"}
JST = timezone(timedelta(hours=9))


def _features():
    return json.loads((FIX / "nara_kuma.json").read_text(encoding="utf-8"))["features"]


def _naive_expected(features):
    """Counted another way: epoch milliseconds -> a JST calendar day by hand (UTC seconds + 9 hours), then plain string splitting."""
    monthly, by_city, latest = Counter(), {}, {}
    for f in features:
        secs = f["attributes"]["field_9"] // 1000 + 9 * 3600
        day = time.strftime("%Y-%m-%d", time.gmtime(secs))
        y, m = int(day[:4]), int(day[5:7])
        if y < 2026:
            continue
        city = f["attributes"]["field_6"]
        fy = "R%02d" % ((y if m >= 4 else y - 1) - 2018)
        monthly[(fy, str(m))] += 1
        by_city.setdefault(city, Counter())[(fy, str(m))] += 1
        latest[city] = max(latest.get(city, ""), day)
    return monthly, by_city, latest


def _server(features, asked=None, extra=None):
    """A FeatureServer stand-in that pages like the real one (resultOffset / resultRecordCount / exceededTransferLimit)."""
    def fake(url):
        if asked is not None:
            asked.append(url)
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert q["returnGeometry"] == "false" and q["outFields"] == "field_9,field_6,field_7,field_4,field_10,field_14" and q["f"] == "json", q
        off, n = int(q["resultOffset"]), int(q["resultRecordCount"])
        page = [{"attributes": dict(f["attributes"], **(extra or {}))} for f in features[off:off + n]]
        return json.dumps({"features": page, **({"exceededTransferLimit": True} if off + n < len(features) else {})}).encode()
    return fake


def _collect(features=None, page_size=None, **patch):
    asked = patch.pop("asked", None)
    with mock.patch.object(kuma, "fetch", _server(features if features is not None else _features(), asked, patch.pop("extra", None))), \
            mock.patch.object(kuma, "MIN_ROWS", patch.pop("min_rows", 1)), mock.patch.object(kumacounts, "PAUSE", 0), \
            mock.patch.object(kuma, "PAGE_SIZE", page_size or 1000):
        return kuma.collect(NOW)


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    return found


class NaraKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _collect()

    def test_counts_equal_a_naive_recount_of_the_fixture(self):
        monthly, by_city, latest = _naive_expected(_features())
        self.assertLessEqual(len(_features()), 200)
        got = {(fy, m): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(monthly))
        self.assertEqual(self.out["total_fy"], sum(n for (fy, _), n in monthly.items() if fy == "R08"))
        self.assertEqual(set(self.out["municipalities"]), set(by_city))
        for city, m in self.out["municipalities"].items():
            self.assertEqual({(fy, mo): n for fy, ms in m["monthly"].items() for mo, n in ms.items()}, dict(by_city[city]), city)
            self.assertEqual(m["latest"], latest[city], city)
        self.assertEqual(self.out["as_of"], max(latest.values()))
        self.assertEqual(self.out["unparsed"], 0)

    def test_2025_rows_of_the_fixture_are_outside_the_window(self):
        self.assertTrue(any(datetime.fromtimestamp(f["attributes"]["field_9"] / 1000, JST).year == 2025 for f in _features()))
        self.assertNotIn("R07", {fy for fy in self.out["monthly"] if any(int(m) >= 4 for m in self.out["monthly"][fy])})
        self.assertEqual(set(self.out["monthly"]["R07"]), {"1", "2", "3"})

    def test_a_place_name_in_the_municipality_column_is_counted_as_its_own_area(self):
        self.assertIn("大台ヶ原", self.out["municipalities"])
        self.assertEqual(self.out["municipalities"]["大台ヶ原"]["latest"], max(
            datetime.fromtimestamp(f["attributes"]["field_9"] / 1000, JST).strftime("%Y-%m-%d") for f in _features()
            if f["attributes"]["field_6"] == "大台ヶ原"))

    def test_a_time_just_before_midnight_in_japan_is_counted_on_that_day(self):
        ms = int(datetime(2026, 9, 30, 23, 45, tzinfo=JST).timestamp() * 1000)    # 14:45 UTC on the same day
        ms2 = int(datetime(2026, 10, 1, 0, 5, tzinfo=JST).timestamp() * 1000)     # 15:05 UTC on September 30
        out = _collect(_features() + [{"attributes": {"field_9": ms, "field_6": "テスト村"}}, {"attributes": {"field_9": ms2, "field_6": "テスト村"}}])
        self.assertEqual(out["municipalities"]["テスト村"]["monthly"]["R08"], {"9": 1, "10": 1})

    def test_paging_goes_on_while_the_server_says_the_limit_was_exceeded_and_waits_between_pages(self):
        asked = []
        with mock.patch.object(kumacounts, "pause") as pause:
            with mock.patch.object(kuma, "fetch", _server(_features(), asked)), mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kuma, "PAGE_SIZE", 60):
                out = kuma.collect(NOW)
        self.assertEqual(len(asked), 4)                    # 200 rows, 60 per page
        self.assertEqual(pause.call_count, 3)
        self.assertEqual(out["municipalities"], self.out["municipalities"])
        self.assertTrue(all("orderByFields=objectid" in u for u in asked))

    def test_the_stored_data_has_the_place_of_each_row_but_no_position_or_free_text(self):
        """Other publications carry this same list (owner's rule 2026-10-13): the 大字, the kind and the number are stored; the free text, the position and the mail are not."""
        extra = {"field_7": "OAZA名", "field_4": "目撃", "field_10": 2, "field_11": "SECRET_TEXT 090-1234-5678", "field_13": 34.5, "mail": "a@example.com"}
        out = _collect(extra=extra)
        self.assertEqual(out["municipalities"], self.out["municipalities"])
        text = json.dumps(out, ensure_ascii=False)
        for secret in ("SECRET", "34.5", "example.com", "090-"):
            self.assertNotIn(secret, text)
        self.assertFalse(_keys(out) & (FORBIDDEN_KEYS - {"place"}))
        self.assertEqual({k for m in out["municipalities"].values() for k in m}, {"monthly", "latest"})
        recs = out["corroborated"]
        self.assertTrue(recs)
        self.assertEqual({k for r in recs for k in r}, {"observed_at", "city", "place", "kind", "count"})
        self.assertTrue(all(r["place"] == "OAZA名" and r["count"] == 2 and r["kind"] == "目撃" for r in recs))
        self.assertEqual([r["observed_at"] for r in recs], sorted((r["observed_at"] for r in recs), reverse=True))
        self.assertLessEqual(len(recs), out["total_fy"])
        run.check_counts_bear(None, out)

    def test_a_row_without_a_place_is_not_listed_and_a_bear_like_animal_is_marked(self):
        feats = [{"attributes": {"field_9": int(datetime(2026, 10, 7, 9, 0, tzinfo=JST).timestamp() * 1000), "field_6": "十津川村", "field_7": "", "field_14": "クマ"}},
                 {"attributes": {"field_9": int(datetime(2026, 10, 6, 9, 0, tzinfo=JST).timestamp() * 1000), "field_6": "十津川村", "field_7": "高滝", "field_14": "クマらしき", "field_10": 1}}]
        out = _collect(feats)
        self.assertEqual([(r["observed_at"], r["place"]) for r in out["corroborated"]], [("2026-10-06", "高滝(クマらしき動物)")])
        self.assertEqual(out["total_fy"], 2)                 # both are still counted

    def test_the_fixture_without_places_stores_no_records(self):
        self.assertNotIn("corroborated", self.out)

    def test_bad_dates_and_future_dates_are_counted_as_unparsed(self):
        future = int(datetime(2026, 10, 20, 9, 0, tzinfo=JST).timestamp() * 1000)
        out = _collect(_features() + [{"attributes": {"field_9": None, "field_6": "奈良市"}}, {"attributes": {"field_9": future, "field_6": "奈良市"}}])
        self.assertEqual(out["unparsed"], 2)
        self.assertEqual(out["total_fy"], self.out["total_fy"])
        many = [{"attributes": {"field_9": None, "field_6": "奈良市"}}] * 10
        with self.assertRaises(kuma.NaraKumaSourceError):
            _collect(_features() + many)                    # 10 of 210 is above 2%

    def test_blank_municipalities_are_limited(self):
        blank = [{"attributes": {"field_9": int(datetime(2026, 9, 1, 9, tzinfo=JST).timestamp() * 1000), "field_6": None}}] * 10
        with self.assertRaises(kuma.NaraKumaSourceError):
            _collect(_features() + blank)

    def test_a_changed_format_or_too_few_rows_is_refused(self):
        renamed = [{"attributes": {"date": f["attributes"]["field_9"], "field_6": f["attributes"]["field_6"]}} for f in _features()]
        with self.assertRaises(kuma.NaraKumaSourceError):
            _collect(renamed)
        with self.assertRaises(kuma.NaraKumaSourceError):
            _collect(min_rows=500)
        for body in (b"<html>", json.dumps({"error": {"code": 400}}).encode(), json.dumps({"layers": []}).encode(), b"[]"):
            with mock.patch.object(kuma, "fetch", lambda url, body=body: body):
                with self.assertRaises(kuma.NaraKumaSourceError):
                    kuma.collect(NOW)

    def test_credit_and_note(self):
        self.assertIn("奈良県", self.out["credit"])
        self.assertIn("大台ヶ原", self.out["update_note"])
        self.assertIn("クマらしき", self.out["update_note"])


if __name__ == "__main__":
    unittest.main()
