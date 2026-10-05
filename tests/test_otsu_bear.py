import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sokuhou.sources import otsu_bear

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 5, 16, 0, tzinfo=JST)
FIXTURE = Path(__file__).parent / "fixtures" / "otsu_bear.kml"


def _kml(folder: str, placemarks: str, description: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>t</name>'
        f"<description><![CDATA[{description}]]></description>"
        f"<Folder><name>{folder}</name>{placemarks}</Folder></Document></kml>"
    )


def _pm(name: str, coords: str = "135.9,35.2,0") -> str:
    return f"<Placemark><name>{name}</name><Point><coordinates>{coords}</coordinates></Point></Placemark>"


class OtsuBearSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.d = otsu_bear.parse(FIXTURE.read_text(encoding="utf-8"), now=NOW)

    def test_every_placemark_is_parsed(self):
        self.assertEqual(len(self.d["sightings"]), 139)
        self.assertEqual(self.d["unparsed"], [])

    def test_latest_sighting(self):
        s = self.d["sightings"][0]
        self.assertEqual(s["observed_at"], "2026-10-03T08:30:00+09:00")
        self.assertEqual(s["place"], "北比良")
        self.assertEqual(s["fiscal_year"], "令和8年度")
        self.assertAlmostEqual(s["lat"], 35.2520291)
        self.assertAlmostEqual(s["lon"], 135.9309192)

    def test_past_years_match_the_city_counts_exactly(self):
        for fy in ("令和5年度", "令和6年度", "令和7年度"):
            self.assertNotIn(fy, self.d["count_mismatch"])
            self.assertEqual(self.d["parsed_counts"][fy], self.d["official_counts"][fy])

    def test_count_mismatch_is_reported_not_hidden(self):
        self.assertEqual(self.d["count_mismatch"]["令和8年度"], {"official": 31, "parsed": 32})


class OtsuBearSyntheticTest(unittest.TestCase):
    def test_january_belongs_to_the_next_calendar_year(self):
        d = otsu_bear.parse(_kml("令和７年度ツキノワグマ目撃情報", _pm("1/15　6：30頃　坂本")), now=NOW)
        self.assertEqual(d["sightings"][0]["observed_at"], "2026-01-15T06:30:00+09:00")

    def test_april_belongs_to_the_fiscal_year_start(self):
        d = otsu_bear.parse(_kml("令和７年度ツキノワグマ目撃情報", _pm("4/2  8:40頃　南小松")), now=NOW)
        self.assertEqual(d["sightings"][0]["observed_at"], "2025-04-02T08:40:00+09:00")
        self.assertEqual(d["sightings"][0]["place"], "南小松")

    def test_time_is_optional(self):
        d = otsu_bear.parse(_kml("令和８年度ツキノワグマ目撃情報", _pm("6/1 若葉台")), now=NOW)
        self.assertEqual(d["sightings"][0]["observed_at"], "2026-06-01")

    def test_unrecognized_name_is_kept_in_unparsed(self):
        d = otsu_bear.parse(_kml("令和８年度ツキノワグマ目撃情報", _pm("クマの痕跡あり")), now=NOW)
        self.assertEqual(d["sightings"], [])
        self.assertEqual(len(d["unparsed"]), 1)


if __name__ == "__main__":
    unittest.main()
