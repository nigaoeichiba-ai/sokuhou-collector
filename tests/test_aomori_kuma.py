import json
import unittest
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

from sokuhou import run
from sokuhou.sources import aomori_kuma as kuma
from sokuhou.sources import kumacounts, kumalib

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)
FORBIDDEN_KEYS = {"lat", "lon", "latitude", "longitude", "place", "places", "sightings", "address", "mail", "email", "remarks", "note"}


def _records():
    return json.loads((FIX / "aomori_kuma.json").read_text(encoding="utf-8"))["result"]


def _naive_expected(records):
    """Counted another way: only verified == 1, only 2026, plain string slicing."""
    monthly, by_city, latest = Counter(), {}, {}
    for r in records:
        if r["verified"] != 1 or r["sighting_datetime"][:4] != "2026":
            continue
        y, m = int(r["sighting_datetime"][0:4]), int(r["sighting_datetime"][5:7])
        fy = "R%02d" % ((y if m >= 4 else y - 1) - 2018)
        monthly[(fy, str(m))] += 1
        by_city.setdefault(r["municipality_name"], Counter())[(fy, str(m))] += 1
        latest[r["municipality_name"]] = max(latest.get(r["municipality_name"], ""), r["sighting_datetime"][:10])
    return monthly, by_city, latest


def _api(records, asked=None, extra=None):
    """A stand-in for the API: honours filter[startdate] / filter[enddate] like the real one and ignores nothing else."""
    def fake(url):
        if asked is not None:
            asked.append(url)
        q = parse_qs(urlparse(unquote(url)).query)
        start, end = q["filter[startdate]"][0], q["filter[enddate]"][0]
        assert q["filter[animal_species_ids][]"] == ["1"]
        rows = [dict(r, **(extra or {})) for r in records if start <= r["sighting_datetime"][:10] <= end]
        return json.dumps({"status": 150, "message": "ok", "count": len(rows), "result": rows}, ensure_ascii=False).encode()
    return fake


def _collect(records=None, **patch):
    with mock.patch.object(kuma, "fetch", _api(records if records is not None else _records(), patch.pop("asked", None), patch.pop("extra", None))), \
            mock.patch.object(kuma, "MIN_ROWS", patch.pop("min_rows", 1)), mock.patch.object(kumacounts, "PAUSE", 0):
        return kuma.collect(NOW)


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    return found


class AomoriKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _collect()

    def test_fixture_has_unconfirmed_posts_and_they_are_not_counted(self):
        recs = _records()
        self.assertLessEqual(len(recs), 200)
        unconfirmed = [r for r in recs if r["verified"] != 1]
        self.assertGreater(len(unconfirmed), 20)
        monthly, by_city, latest = _naive_expected(recs)
        self.assertEqual(self.out["total_fy"], sum(n for (fy, _), n in monthly.items() if fy == "R08"))
        every = sum(1 for r in recs if r["sighting_datetime"] >= "2026-04")
        self.assertEqual(self.out["total_fy"] + sum(1 for r in unconfirmed if r["sighting_datetime"] >= "2026-04"), every)

    def test_counts_equal_a_naive_recount_of_the_fixture(self):
        monthly, by_city, latest = _naive_expected(_records())
        got = {(fy, m): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(monthly))
        self.assertEqual(set(self.out["municipalities"]), set(by_city))
        for city, m in self.out["municipalities"].items():
            self.assertEqual({(fy, mo): n for fy, ms in m["monthly"].items() for mo, n in ms.items()}, dict(by_city[city]), city)
            self.assertEqual(m["latest"], latest[city], city)
        self.assertEqual(self.out["as_of"], max(latest.values()))
        self.assertEqual(self.out["fy_current"], "R08")
        self.assertEqual(self.out["unparsed"], 0)
        self.assertIn("未確認", self.out["update_note"])

    def test_requests_are_split_by_month_from_january_and_use_the_bear_filter(self):
        asked = []
        _collect(asked=asked)
        self.assertEqual(len(asked), 1 + 7)          # January-March, then April ... October
        self.assertIn("2026-01-01", unquote(asked[0]))
        self.assertIn("2026-03-31", unquote(asked[0]))
        self.assertIn("2026-10-31", unquote(asked[-1]))
        self.assertTrue(all("animal_species_ids" in unquote(u) for u in asked))
        self.assertEqual(kuma.periods(date(2026, 4, 2))[-1], (date(2026, 4, 1), date(2026, 4, 30)))
        self.assertEqual(kuma.periods(date(2027, 1, 5))[-1], (date(2027, 1, 1), date(2027, 1, 31)))

    def test_the_stored_data_has_no_place_position_or_free_text(self):
        extra = {"address": "〒030-0111 青森県青森市SECRET_ADDRESS", "latitude": 40.651493931246, "longitude": 140.83916928562,
                 "sighting_condition": "SECRET_TEXT 090-1234-5678", "remarks": "SECRET_REMARK a@example.com"}
        out = _collect(extra=extra)
        self.assertEqual(out["municipalities"], self.out["municipalities"])
        text = json.dumps(out, ensure_ascii=False)
        for secret in ("SECRET", "40.6514", "140.839", "example.com", "090-"):
            self.assertNotIn(secret, text)
        self.assertFalse(_keys(out) & FORBIDDEN_KEYS)
        self.assertEqual({k for m in out["municipalities"].values() for k in m}, {"monthly", "latest"})
        run.check_counts_bear(None, self.out)

    def test_a_record_seen_in_two_requests_is_counted_once(self):
        dup = _records() + [r for r in _records() if r["verified"] == 1][:5]
        self.assertEqual(_collect(dup)["total_fy"], self.out["total_fy"])

    def test_bad_and_future_dates_and_blank_municipalities(self):
        recs = _records()
        base = max(r["id"] for r in recs)
        bad = [{"id": base + 1, "sighting_datetime": "2026-02-30 10:00:00", "municipality_name": "青森市", "verified": 1},
               {"id": base + 2, "sighting_datetime": "2026-10-20 10:00:00", "municipality_name": "青森市", "verified": 1}]
        out = _collect(recs + bad)
        self.assertEqual(out["unparsed"], 2)
        self.assertEqual(out["total_fy"], self.out["total_fy"])
        blanks = [{"id": base + 10 + i, "sighting_datetime": "2026-09-01 10:00:00", "municipality_name": "", "verified": 1} for i in range(10)]
        with self.assertRaises(kuma.AomoriKumaSourceError):
            _collect(recs + blanks)                      # 10 of about 190 is above 3%
        many_bad = [{"id": base + 100 + i, "sighting_datetime": "2026-05-0x", "municipality_name": "青森市", "verified": 1} for i in range(10)]
        with self.assertRaises(kuma.AomoriKumaSourceError):
            _collect(recs + many_bad)                    # above 2%

    def test_a_changed_format_or_too_few_rows_is_refused(self):
        recs = _records()
        no_verified = [{k: v for k, v in r.items() if k != "verified"} for r in recs]
        with self.assertRaises(kuma.AomoriKumaSourceError):
            _collect(no_verified)
        with self.assertRaises(kuma.AomoriKumaSourceError):
            _collect(min_rows=500)
        with mock.patch.object(kuma, "fetch", lambda url: b"<html>maintenance</html>"), mock.patch.object(kumacounts, "PAUSE", 0):
            with self.assertRaises(kuma.AomoriKumaSourceError):
                kuma.collect(NOW)
        with mock.patch.object(kuma, "fetch", lambda url: json.dumps({"count": 5, "result": []}).encode()), mock.patch.object(kumacounts, "PAUSE", 0):
            with self.assertRaises(kuma.AomoriKumaSourceError):
                kuma.collect(NOW)                        # count does not match the list: truncated answer

    def test_the_credit_says_it_is_processed_and_not_the_prefecture_s(self):
        self.assertIn("くまログあおもり", self.out["credit"])
        self.assertIn("青森県が作成したものではありません", self.out["credit"])


if __name__ == "__main__":
    unittest.main()
