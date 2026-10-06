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


class OkayamaKumaSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = _parse_fixture()

    def test_first_placemark(self):
        self.assertIn({
            "observed_at": "2025-04-24",
            "city": "新見市",
            "place": "高尾",
            "count": None,
            "kind": "目撃",
            "species": "ツキノワグマ",
        }, self.d["sightings"])

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
