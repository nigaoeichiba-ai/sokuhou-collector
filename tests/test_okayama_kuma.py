import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou.sources import okayama_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
KML = FIX / "okayama_kuma.kml"


def _parse_fixture():
    with mock.patch.object(kuma, "MIN_PLACEMARKS", 1):
        return kuma.parse_kml(KML.read_bytes())


def _bare(rows):
    """The rows without their coordinates (the coordinates are checked in the coordinate tests)."""
    return [{k: v for k, v in r.items() if k not in ("lat", "lon")} for r in rows]


class OkayamaKumaSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = _parse_fixture()

    def test_coordinates_are_kept_rounded_and_inside_the_prefecture(self):
        with_coords = [r for r in self.d["sightings"] if "lat" in r]
        self.assertGreater(len(with_coords), len(self.d["sightings"]) * 0.9)
        for r in with_coords:
            self.assertTrue(34.4 <= r["lat"] <= 35.4 and 133.2 <= r["lon"] <= 134.5, r)
            self.assertEqual(r["lat"], round(r["lat"], 4))
            self.assertEqual(r["lon"], round(r["lon"], 4))

    def test_first_placemark(self):
        self.assertIn({
            "observed_at": "2025-04-24",
            "city": "新見市",
            "place": "高尾",
            "count": None,
            "kind": "目撃",
            "species": "ツキノワグマ",
        }, _bare(self.d["sightings"]))

    def test_fiscal_wareki_and_monthly_counts(self):
        self.assertEqual(self.d["as_of"], "2026-09-06")
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertEqual(len(self.d["sightings"]), 112)
        self.assertEqual(self.d["wareki_mismatches"], 0)
        self.assertEqual(self.d["monthly"]["R08"]["4"], 18)
        self.assertEqual(self.d["monthly"]["R08"], {"4": 18, "5": 12, "6": 12, "7": 14, "8": 11, "9": 3})
        self.assertEqual(self.d["monthly"]["R07"]["1"], 5)

    def test_collect_without_network(self):
        with mock.patch.object(kuma, "MIN_PLACEMARKS", 1), mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=KML.read_bytes())):
            out = kuma.collect()
        self.assertEqual(out["source"], "okayama")
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertEqual(out["source_file"], kuma.SOURCE_FILE)
        self.assertEqual(out["sightings_in_window"], 112)
        self.assertRegex(out["fetched_at"], r"\+09:00$")


class OkayamaKumaFailureTest(unittest.TestCase):
    def test_bad_date_is_reported_and_refused_over_limit(self):
        bad = KML.read_bytes().replace(b"<name>4/24/2025</name>", b"<name>bad</name>", 1)
        with (
            mock.patch.object(kuma, "MIN_PLACEMARKS", 1),
            mock.patch.object(kuma, "UNPARSED_LIMIT", 0),
            self.assertRaisesRegex(kuma.OkayamaKumaSourceError, "unparseable dates"),
        ):
            kuma.parse_kml(bad)

    def test_changed_document_name_is_refused(self):
        bad = KML.read_bytes().replace(kuma.DOCUMENT_NAME.encode("utf-8"), "別の地図".encode("utf-8"), 1)
        with mock.patch.object(kuma, "MIN_PLACEMARKS", 1), self.assertRaisesRegex(kuma.OkayamaKumaSourceError, "Document name changed"):
            kuma.parse_kml(bad)


if __name__ == "__main__":
    unittest.main()
