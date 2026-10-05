"""Bear data from the Ministry of the Environment's PDFs. Expected values come from outside the parser:
the national R07 injury row and the five biggest R07 sighting counts are the figures reported by nippon.com."""
import unittest
from pathlib import Path
from unittest import mock

try:
    import pypdf  # noqa: F401
    HAVE_PYPDF = True
except ImportError:  # the parser needs it; the rest of the suite does not
    HAVE_PYPDF = False

from sokuhou.prefectures import SHORT
from sokuhou.sources import env_kuma as bear

FIX = Path(__file__).parent / "fixtures"
SIGHT = (FIX / "env_kuma_syutubotu.pdf").read_bytes()
INJ = (FIX / "env_kuma_injury.pdf").read_bytes()


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class SightingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = bear.parse_sightings(SIGHT)
        cls.by = {p["name"]: p for p in cls.d["prefectures"]}

    def test_layout(self):
        self.assertEqual(self.d["updated"], "2026-09-09")
        self.assertEqual(self.d["years"], ["R04", "R05", "R06", "R07", "R08"])
        self.assertEqual([p["name"] for p in self.d["prefectures"]], SHORT[:39])  # Hokkaido to Kochi; Fukuoka..Okinawa are not in the table
        self.assertEqual(self.d["latest_month"], 7)

    def test_the_five_biggest_r07_counts_match_the_press(self):
        top = sorted(self.d["prefectures"], key=lambda p: -(p["total"]["R07"] or 0))[:5]
        self.assertEqual([(p["name"], p["total"]["R07"]) for p in top],
                         [("秋田", 13592), ("岩手", 9739), ("宮城", 3559), ("新潟", 3528), ("青森", 3334)])

    def test_months_add_up_to_totals_and_prefectures_to_the_national_row(self):
        for p in self.d["prefectures"]:
            for y in self.d["years"]:
                self.assertEqual(sum(v for v in p["monthly"][y] if v is not None), p["total"][y] or 0)
        for y in self.d["years"]:
            self.assertEqual(sum(p["total"][y] or 0 for p in self.d["prefectures"]), self.d["national"]["total"][y])

    def test_a_dash_is_no_data_and_future_months_are_empty(self):
        self.assertTrue(all(v is None for v in self.by["北海道"]["total"].values()))
        self.assertEqual(self.by["青森"]["monthly"]["R08"][4:], [None] * 8)  # August R08 onwards not yet reported
        self.assertEqual(self.by["青森"]["monthly"]["R07"][0], 46)  # April R07, read straight from the table


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class InjuriesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = bear.parse_injuries(INJ)

    def test_layout(self):
        self.assertEqual(self.d["updated"], "2026-10-02")
        self.assertEqual(self.d["as_of"], "R08年8月末")
        self.assertEqual(self.d["years"][0], "H20")
        self.assertEqual(self.d["years"][-1], "R08")
        self.assertEqual(len(self.d["years"]), 19)

    def test_national_r07_matches_the_press(self):
        self.assertEqual(self.d["national"]["R07"], [216, 238, 13])  # cases, people injured, deaths (nippon.com)

    def test_prefectures_add_up(self):
        for y in self.d["years"]:
            for k in range(3):
                self.assertEqual(sum(p["by_year"][y][k] for p in self.d["prefectures"]), self.d["national"][y][k])


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class RefusalTest(unittest.TestCase):
    """A layout change or a wrong number must stop the run, never be stored."""

    def with_tokens(self, change):
        real = bear._tokens

        def patched(pdf, page_no):
            return change(real(pdf, page_no))
        return mock.patch.object(bear, "_tokens", patched)

    def test_a_changed_cell_breaks_the_sums(self):
        def change(tokens):
            for t in tokens:
                if t["text"] == "3,334":
                    t["text"] = "3,335"
                    break
            return tokens
        with self.with_tokens(change), self.assertRaises(bear.EnvKumaError):
            bear.parse_sightings(SIGHT)

    def test_a_missing_prefecture_row_is_refused(self):
        def change(tokens):
            ys = {t["y"] for t in tokens if t["text"] == "岩手"}
            return [t for t in tokens if all(abs(t["y"] - y) > 3 for y in ys)]
        with self.with_tokens(change), self.assertRaises(bear.EnvKumaError):
            bear.parse_sightings(SIGHT)

    def test_a_missing_year_header_is_refused(self):
        def change(tokens):
            for i, t in enumerate(tokens):
                if t["text"] == "R08":
                    del tokens[i]
                    break
            return tokens
        with self.with_tokens(change), self.assertRaises(bear.EnvKumaError):
            bear.parse_sightings(SIGHT)

    def test_an_unreadable_cell_is_refused(self):
        def change(tokens):
            for t in tokens:
                if t["text"] == "3,334":
                    t["text"] = "n/a"
            return tokens
        with self.with_tokens(change), self.assertRaises(bear.EnvKumaError):
            bear.parse_sightings(SIGHT)

    def test_injury_rows_that_do_not_add_up_are_refused(self):
        def change(tokens):
            for t in tokens:
                if t["text"] == "216":
                    t["text"] = "217"
            return tokens
        with self.with_tokens(change), self.assertRaises(bear.EnvKumaError):
            bear.parse_injuries(INJ)


def fx(name):
    return (FIX / name).read_bytes()


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class FatalAndEmergencyTest(unittest.TestCase):
    def test_r08_fatal_accidents(self):
        d = bear.parse_fatal(fx("env_kuma_r08_fatal.pdf"), 2026)
        self.assertEqual(d["as_of"], "2026-07-10")
        self.assertEqual(d["deaths"], 6)
        self.assertEqual((d["incidents"][0]["date"], d["incidents"][0]["prefecture"], d["incidents"][0]["place"]),
                         ("2026-04-21", "岩手県", "紫波町"))
        self.assertTrue(d["incidents"][0]["found_date"])  # "被害者発見日": the date the victim was found

    def test_r07_fatal_accidents_match_the_injury_table(self):
        d = bear.parse_fatal(fx("env_kuma_r07_fatal.pdf"), 2025)
        self.assertEqual(d["deaths"], 13)
        self.assertEqual(d["deaths"], bear.parse_injuries(INJ)["national"]["R07"][2])  # deaths in the other table
        self.assertEqual(d["incidents"][-1]["date"], "2025-11-03")

    def test_emergency_shootings(self):
        d = bear.parse_emergency(fx("env_kuma_r08_emergency.pdf"), 2026)
        self.assertEqual((d["updated"], len(d["cases"])), ("2026-10-01", 31))  # "事例は31件" on the page
        self.assertEqual(d["cases"][5]["species"], "イノシシ")  # not every case is a bear
        self.assertEqual(d["cases"][-1]["date"], "2026-09-30")
        last = bear.parse_emergency(fx("env_kuma_r07_emergency.pdf"), 2025)
        self.assertEqual(len(last["cases"]), 60)
        self.assertEqual(last["cases"][-1]["date"], "2026-03-25")  # January to March fall in the next calendar year

    def test_a_list_with_a_missing_row_is_refused(self):
        real = bear._page_text

        def drop(pdf):
            return real(pdf).replace("\n15 6月10日 岩手県遠野市 ツキノワグマ", "")
        with mock.patch.object(bear, "_page_text", drop), self.assertRaises(bear.EnvKumaError):
            bear.parse_emergency(fx("env_kuma_r08_emergency.pdf"), 2026)

    def test_fiscal_files_are_found_from_the_page(self):
        html = '<a href="r08jiko-gaiyo.pdf">x</a><a href="r08kinkyu-jishi.pdf">y</a><a href="r07jiko-gaiyo.pdf">z</a>'
        files = bear._fiscal_files(html)
        self.assertEqual(sorted(files), [2025, 2026])
        self.assertEqual(files[2026]["emergency"], bear.BASE + "r08kinkyu-jishi.pdf")
        self.assertNotIn("emergency", files[2025])


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class CollectTest(unittest.TestCase):
    def test_collect_without_network(self):
        from types import SimpleNamespace

        page = ('<a href="r08jiko-gaiyo.pdf">a</a><a href="r08kinkyu-jishi.pdf">b</a>'
                '<a href="r07jiko-gaiyo.pdf">c</a><a href="r07kinkyu-jishi.pdf">d</a>').encode()
        files = {"syutubotu.pdf": SIGHT, "injury-qe.pdf": INJ, "effort12.html": page,
                 "r08jiko-gaiyo.pdf": fx("env_kuma_r08_fatal.pdf"), "r08kinkyu-jishi.pdf": fx("env_kuma_r08_emergency.pdf"),
                 "r07jiko-gaiyo.pdf": fx("env_kuma_r07_fatal.pdf"), "r07kinkyu-jishi.pdf": fx("env_kuma_r07_emergency.pdf")}

        def fake(url):
            return SimpleNamespace(body=files[url.rsplit("/", 1)[1]])
        with mock.patch.object(bear, "fetch", fake):
            out = bear.collect()
        self.assertEqual(out["source_page"], bear.PAGE)
        self.assertRegex(out["fetched_at"], r"\+09:00$")
        self.assertEqual(out["sightings"]["national"]["total"]["R07"], 50801)
        self.assertEqual(out["injuries"]["national"]["R07"], [216, 238, 13])
        self.assertEqual(sorted(out["fatal"]), ["R07", "R08"])
        self.assertEqual(len(out["emergency"]["R08"]["cases"]), 31)


if __name__ == "__main__":
    unittest.main()
