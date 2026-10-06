import csv
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou.sources import yamaguchi_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
CSV = FIX / "yamaguchi_kuma_yp2026.csv"
PACKAGE = FIX / "yamaguchi_package_show.json"


def _parse_fixture():
    with mock.patch.object(kuma, "MIN_ROWS", 1):
        return kuma.parse_csv(CSV.read_bytes())


def _csv_rows():
    reader = csv.reader(io.StringIO(CSV.read_bytes().decode("cp932")))
    header = next(reader)
    return header, list(reader)


def _csv_bytes(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("cp932")


class YamaguchiKumaSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = _parse_fixture()

    def test_first_rows_and_city_split(self):
        self.assertIn({
            "observed_at": "2026-01-04T13:35:00+09:00",
            "city": "周南市",
            "place": "大字須々万奥 国道上",
            "count": 1,
            "kind": "目撃",
            "species": "クマ",
        }, self.d["sightings"])
        self.assertIn({
            "observed_at": "2026-01-04T10:00:00+09:00",
            "city": "山口市",
            "place": "阿東地福上",
            "count": None,
            "kind": "痕跡",
            "species": "クマ",
        }, self.d["sightings"])

    def test_reiwa_dates_multiline_places_and_trace_rule(self):
        self.assertEqual(kuma._parse_reiwa_date("令和8年1月4日").isoformat(), "2026-01-04")
        self.assertEqual(kuma.kind_from_status("熊の足跡を発見したもの"), "痕跡")
        self.assertEqual(kuma.kind_from_status("国道を横断する熊を目撃したもの"), "目撃")
        self.assertEqual(self.d["sightings"][0], {
            "observed_at": "2026-10-03T22:30:00+09:00",
            "city": "岩国市",
            "place": "美和町北中山 敷地内",
            "count": 1,
            "kind": "目撃",
            "species": "クマ",
        })

    def test_fiscal_window_and_monthly_counts(self):
        self.assertEqual(self.d["as_of"], "2026-10-03")
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertEqual(len(self.d["sightings"]), 230)
        self.assertEqual(self.d["monthly"]["R08"], {"4": 21, "5": 55, "6": 51, "7": 35, "8": 20, "9": 36, "10": 4})
        self.assertEqual(self.d["monthly"]["R07"], {"1": 5, "2": 2, "3": 1})

    def test_package_show_and_collect_without_network(self):
        csv_url = kuma.csv_url_from_package_show(PACKAGE.read_bytes())
        self.assertTrue(csv_url.endswith("/r8-01011005.csv"))

        calls = []

        def fake_fetch(url, **kwargs):
            calls.append((url, kwargs))
            if url == kuma.PACKAGE_SHOW:
                return SimpleNamespace(body=PACKAGE.read_bytes())
            return SimpleNamespace(body=CSV.read_bytes())

        with mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kuma, "fetch", fake_fetch):
            out = kuma.collect()
        self.assertEqual(out["source"], "yamaguchi")
        self.assertEqual(out["source_page"], kuma.DATASET_PAGE)
        self.assertEqual(out["source_file"], csv_url)
        self.assertEqual(out["sightings_in_window"], 230)
        self.assertRegex(out["fetched_at"], r"\+09:00$")
        self.assertEqual(calls, [
            (kuma.PACKAGE_SHOW, {"legacy_tls": True}),
            (csv_url, {"legacy_tls": True}),
        ])


class YamaguchiKumaFailureTest(unittest.TestCase):
    def test_changed_header_is_refused(self):
        header, rows = _csv_rows()
        header[0] = "ID"
        with mock.patch.object(kuma, "MIN_ROWS", 1), self.assertRaisesRegex(kuma.YamaguchiKumaSourceError, "header changed"):
            kuma.parse_csv(_csv_bytes(header, rows[:3]))

    def test_coordinate_outside_box_is_refused_when_over_limit(self):
        header, rows = _csv_rows()
        rows = rows[:2]
        rows[0][8] = "35.9"
        with mock.patch.object(kuma, "MIN_ROWS", 1), self.assertRaisesRegex(kuma.YamaguchiKumaSourceError, "coordinates outside"):
            kuma.parse_csv(_csv_bytes(header, rows))

    def test_license_change_is_refused(self):
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        package["result"]["license_id"] = "other"
        with self.assertRaisesRegex(kuma.YamaguchiKumaSourceError, "license_id"):
            kuma.csv_url_from_package_show(json.dumps(package).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
