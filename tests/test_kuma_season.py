"""/season/ of the bear site: the share of the year in each month, per prefecture, from the four complete fiscal years of the ministry's table.

The numbers on the page are checked against values written into the test (a hand calculation on a small, made-up table) and against the real fixture
counted another way.
"""
import copy
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.kuma import build, season
from sokuhou import sitecheck
from tests.test_kuma_build import CFG, HAVE_PYPDF
from tests.test_kuma_cite import make_raw

OCT = date(2026, 10, 7)


def text_of(html: str) -> str:
    body = html.split("<main", 1)[1].split("</main>", 1)[0]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def month_list(sep, oct_, nov):
    """April..March: only September, October and November have sightings."""
    v = [0] * 12
    v[5], v[6], v[7] = sep, oct_, nov
    return v


def raw_with(pattern):
    raw = make_raw()
    rows = {p["name"]: p for p in raw["sightings"]["prefectures"]}
    for name, per_year in pattern.items():
        for y, vals in per_year.items():
            rows[name]["monthly"][y] = vals
    return raw


# Miyagi: every year 10 / 80 / 10 percent in Sep / Oct / Nov, but the year R05 is twice as large (totals 100, 200, 100, 100)
MIYAGI = {"R04": month_list(10, 80, 10), "R05": month_list(20, 160, 20), "R06": month_list(10, 80, 10), "R07": month_list(10, 80, 10)}
# Akita: a year with 49 sightings (below the threshold of 50): no pattern
AKITA = {"R04": month_list(10, 80, 10), "R05": month_list(5, 39, 5), "R06": month_list(10, 80, 10), "R07": month_list(10, 80, 10)}
# Fukushima: a month that is not published in a complete year (None): no pattern
FUKUSHIMA = {"R04": month_list(10, 80, 10), "R05": month_list(10, 80, 10), "R06": [None] * 12, "R07": month_list(10, 80, 10)}


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class SeasonPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = raw_with({"宮城": MIYAGI, "秋田": AKITA, "福島": FUKUSHIMA})
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, today=OCT)
        cls.html = (cls.out / "season/index.html").read_text(encoding="utf-8")
        cls.text = text_of(cls.html)
        cls.d = build.prepare(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_page_exists_and_passes_the_site_checker(self):
        self.assertIn("season/index.html", self.files)
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])
        self.assertIn("<title>クマの出没は何月に多い?都道府県別の月別の割合(令和4年度〜令和7年度)", self.html)
        self.assertIn('href="/season/"', (self.out / "index.html").read_text(encoding="utf-8"))

    def test_the_hand_calculated_prefecture(self):
        r = next(x for x in self.d["rows"] if x["short"] == "宮城")
        p = season.pref_pattern(self.d, r)
        self.assertEqual(p["peak"], 10)
        self.assertAlmostEqual(p["share"][6], 0.8)                 # October is the 7th month of the fiscal year
        self.assertAlmostEqual(p["autumn_share"], 1.0)
        self.assertEqual((p["autumn_min"], p["autumn_max"]), (100, 200))
        self.assertEqual(p["yearly"], {"R04": 100, "R05": 200, "R06": 100, "R07": 100})
        self.assertEqual(p["quiet"], [m for m in (4, 5, 6, 7, 8, 12, 1, 2, 3)])
        row = re.search(r"宮城県 10月 80% 100% 100〜200件 125", self.text)
        self.assertTrue(row, self.text[self.text.find("宮城県"):][:120])      # peak, this month's share, autumn share, range, average a year

    def test_a_year_below_the_threshold_or_with_an_unpublished_month_gives_no_pattern(self):
        akita = next(x for x in self.d["rows"] if x["short"] == "秋田")
        fukushima = next(x for x in self.d["rows"] if x["short"] == "福島")
        self.assertIsNone(season.pref_pattern(self.d, akita))
        self.assertIsNone(season.pref_pattern(self.d, fukushima))
        table = self.text.split("都道府県 最も多い月", 1)[1].split("この表の読み方", 1)[0]
        self.assertNotIn("秋田県", table)
        self.assertNotIn("福島県", table)
        self.assertIn("傾向を出していない都道府県", self.text)
        self.assertRegex(self.text, r"傾向を出していない都道府県: [^。]*秋田県")

    def test_the_national_row_is_the_average_of_the_yearly_shares_counted_another_way(self):
        years = ["R04", "R05", "R06", "R07"]
        nat = self.raw["sightings"]["national"]["monthly"]
        want = []
        for k in range(12):
            want.append(sum(nat[y][k] / sum(nat[y]) for y in years) / 4)
        got = season.national_pattern(self.d)
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(sum(got), 1.0)
        peak = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3][max(range(12), key=lambda k: want[k])]
        self.assertIn(f"全国では、 {peak}月 が、いちばん多い月です", self.text)

    def test_this_month_is_the_month_of_the_build_date(self):
        self.assertIn("いまは10月で", self.text)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m"
            build.render_site(self.raw, CFG, out, release=True, today=date(2026, 6, 20))
            t = text_of((out / "season/index.html").read_text(encoding="utf-8"))
            self.assertIn("いまは6月で", t)
            self.assertIn("6月の割合", t)
            self.assertRegex(t, r"宮城県 10月 0% 100%")                 # in June this prefecture's share is 0

    def test_it_says_these_are_past_patterns_and_not_a_forecast(self):
        self.assertIn("今年が、同じになるとは、限りません", self.text)
        for bad in ("予測", "今年は多い", "安全", "危険です", "日本一"):
            self.assertNotIn(bad, self.text)
        self.assertIn("環境省が作成したものではありません", self.text)

    def test_only_complete_fiscal_years_are_used(self):
        self.assertEqual(season.complete_years(self.d), ["R04", "R05", "R06", "R07"])
        self.assertNotIn("R08", season.complete_years(self.d))


class HelpersTest(unittest.TestCase):
    def test_pct(self):
        self.assertEqual(season.pct(0.804), "80%")
        self.assertEqual(season.pct(0.0), "0%")


if __name__ == "__main__":
    unittest.main()
