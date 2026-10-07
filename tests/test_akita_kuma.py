import csv
import io
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou.sources import akita_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
CSV = FIX / "akita_kumadas_sample.csv"
API = FIX / "akita_kumadas_api.json"


def _parse_sample():
    with mock.patch.object(kuma, "MIN_ROWS", 1):
        return kuma.parse_csv(CSV.read_bytes())


def _csv_rows():
    reader = csv.reader(io.StringIO(CSV.read_bytes().decode("utf-8-sig")))
    header = next(reader)
    return header, list(reader)


def _csv_bytes(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _bare(rows):
    """The rows without their coordinates (the coordinates are checked in the coordinate tests)."""
    return [{k: v for k, v in r.items() if k not in ("lat", "lon")} for r in rows]


class AkitaKumaSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = _parse_sample()

    def test_coordinates_are_kept_rounded_and_inside_the_prefecture(self):
        with_coords = [r for r in self.d["sightings"] if "lat" in r]
        self.assertGreater(len(with_coords), len(self.d["sightings"]) * 0.9)
        for r in with_coords:
            self.assertTrue(38.8 <= r["lat"] <= 40.6 and 139.6 <= r["lon"] <= 141.1, r)
            self.assertEqual(r["lat"], round(r["lat"], 4))
            self.assertEqual(r["lon"], round(r["lon"], 4))

    def test_two_date_formats_parse(self):
        dt, has_time = kuma._parse_observed("2026/8/31 14:53")
        self.assertTrue(has_time)
        self.assertEqual(dt.isoformat(), "2026-08-31T14:53:00+09:00")
        # Verified independently with date(1899, 12, 30) + timedelta(days=44661.58333).
        serial, has_time = kuma._parse_observed("44661.58333")
        self.assertTrue(has_time)
        self.assertEqual(serial.isoformat(), "2022-04-10T14:00:00+09:00")

    def test_multiline_fields_and_address_cleaning(self):
        self.assertEqual(self.d["duplicate_rows_removed"], 26)
        self.assertIn({
            "observed_at": "2026-08-31T07:30:00+09:00",
            "city": "鹿角市",
            "place": "秋田県鹿角市十和田瀬田石瀬田石",
            "count": 1,
            "kind": "痕跡(食害)",
            "species": "ツキノワグマ",
        }, _bare(self.d["sightings"]))
        self.assertEqual(self.d["sightings"][0]["place"], "秋田県秋田市寺内児桜２丁目１５")

    def test_non_bear_rows_are_excluded_from_sightings(self):
        self.assertEqual({s["species"] for s in self.d["sightings"]}, {"ツキノワグマ"})
        self.assertEqual(len(self.d["sightings"]), 192)

    def test_fiscal_window_and_monthly_counts(self):
        self.assertEqual(self.d["as_of"], "2026-08-31")
        self.assertEqual(self.d["newest_observed_at"], "2026-08-31T14:53:00+09:00")
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertNotIn("R06", self.d["monthly"])
        self.assertEqual(self.d["monthly_kind"], "目撃")
        self.assertEqual(self.d["monthly"]["R08"], {"8": 100, "6": 2, "4": 3, "7": 9, "5": 1})
        self.assertEqual(self.d["monthly"]["R07"], {"10": 25, "12": 1, "6": 10, "8": 5, "7": 5, "11": 11, "9": 4, "5": 1, "2": 1})

    def test_collect_without_network(self):
        with mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=CSV.read_bytes())),                 mock.patch.object(kuma, "polite_fetch", lambda url: API.read_bytes()):
            out = kuma.collect()
        self.assertEqual(out["source"], "akita")
        self.assertEqual(out["source_page"], kuma.DATASET_PAGE)
        self.assertEqual(out["source_file"], kuma.SOURCE_FILE)
        self.assertRegex(out["fetched_at"], r"\+09:00$")


class AkitaApiTest(unittest.TestCase):
    """The prefecture's public API adds the newest records of the same system (same record numbers) that the monthly open data does not have yet."""

    @classmethod
    def setUpClass(cls):
        with mock.patch.object(kuma, "MIN_ROWS", 1):
            cls.parsed = kuma.parse_csv(CSV.read_bytes())
        cls.ids = cls.parsed["_ids"]

    def api_rows(self, **kw):
        args = dict(known_ids=self.ids, after=date(2026, 8, 31), today=date(2026, 10, 7))
        args.update(kw)
        return kuma.parse_api(API.read_bytes(), **args)

    def test_only_new_confirmed_bear_records_after_the_open_data_are_taken(self):
        rows = self.api_rows()
        self.assertEqual(len(rows), 6)  # 9 in the file: 2 already in the open data, 1 not confirmed by the prefecture
        self.assertTrue(all(r["observed_at"] >= "2026-09-01" for r in rows))
        self.assertNotIn("99999999", str(rows))
        self.assertEqual(rows[0]["observed_at"], "2026-10-06T21:30:00+09:00")
        self.assertEqual(rows[0]["city"], "秋田市")
        self.assertEqual(rows[0]["place"], "秋田県秋田市千秋矢留町４−２３")  # the postal code is cleaned like the CSV's addresses
        self.assertEqual(rows[0]["kind"], "目撃")
        self.assertTrue(38.8 <= rows[0]["lat"] <= 40.6)
        self.assertEqual(len(self.api_rows(known_ids=set())), 8)  # without the record numbers the two rows already in the open data would be doubled
        self.assertEqual([r["observed_at"][:10] for r in self.api_rows(today=date(2026, 10, 3))], ["2026-10-04", "2026-10-01", "2026-10-01"])  # nothing after today + 2 days: a date typed in the future is dropped

    def test_merge_updates_as_of_monthly_credit_and_note(self):
        out = {k: v for k, v in self.parsed.items() if k != "_ids"}
        before = dict(out["monthly"]["R08"])
        kuma.add_api_records(out, self.api_rows())
        self.assertEqual(out["as_of"], "2026-10-06")
        self.assertEqual(out["newest_observed_at"], "2026-10-06T21:30:00+09:00")
        self.assertEqual(out["monthly"]["R08"], {**before, "10": 6})
        self.assertTrue(out["credit"].startswith(kuma.CREDIT) and "公開API" in out["credit"])
        self.assertIn("確認済み", out["update_note"])
        self.assertEqual(out["api_records_added"], 6)
        self.assertEqual(out["sightings"][0]["observed_at"], "2026-10-06T21:30:00+09:00")

    def test_a_failing_api_leaves_the_open_data_alone(self):
        def boom(url):
            raise OSError("down")
        with mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=CSV.read_bytes())),                 mock.patch.object(kuma, "polite_fetch", boom):
            out = kuma.collect()
        self.assertEqual(out["as_of"], "2026-08-31")
        self.assertIn("OSError", out["api_error"])
        self.assertNotIn("_ids", out)

    def test_collect_with_the_api_and_no_known_ids_stored(self):
        with mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=CSV.read_bytes())),                 mock.patch.object(kuma, "polite_fetch", lambda url: API.read_bytes()):
            out = kuma.collect()
        self.assertEqual(out["as_of"], "2026-10-06")
        self.assertNotIn("_ids", out)
        self.assertNotIn("api_error", out)


class AkitaKumaFailureTest(unittest.TestCase):
    def test_changed_header_is_refused(self):
        header, rows = _csv_rows()
        header[0] = "ID"
        with mock.patch.object(kuma, "MIN_ROWS", 1), self.assertRaisesRegex(kuma.AkitaKumaParseError, "header changed"):
            kuma.parse_csv(_csv_bytes(header, rows[:3]))

    def test_coordinate_outside_box_is_refused_when_over_limit(self):
        header, rows = _csv_rows()
        rows = rows[:2]
        rows[0][10] = "35.0"
        with mock.patch.object(kuma, "MIN_ROWS", 1), self.assertRaisesRegex(kuma.AkitaKumaParseError, "coordinates outside"):
            kuma.parse_csv(_csv_bytes(header, rows))


if __name__ == "__main__":
    unittest.main()
