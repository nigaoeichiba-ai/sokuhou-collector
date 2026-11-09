"""kuma-sokuho.com (2026-11-09): a prefecture page with almost no sightings (under 10 in the last full year and under 10 so far this year) is noindex and out of the sitemap, the page stays
(like Chiba's).  It returns to the index by itself when the counts reach 10.  Negative cases: a prefecture with 10 is not thin; one without the ministry's table is not decided by it."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, indexing
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data


def row(done_total, ytd, has=True):
    return {"has": has, "total": {"R07": done_total}, "ytd": {"R08": ytd}}


D = {"done": "R07", "cur": "R08"}


class PrefThinTest(unittest.TestCase):
    def test_both_the_last_year_and_this_year_under_ten_is_thin(self):
        self.assertTrue(indexing.pref_is_thin(D, row(0, 0)))
        self.assertTrue(indexing.pref_is_thin(D, row(7, 3)))
        self.assertTrue(indexing.pref_is_thin(D, row(9, 9)))

    def test_ten_in_either_period_is_not_thin(self):
        self.assertFalse(indexing.pref_is_thin(D, row(10, 0)))
        self.assertFalse(indexing.pref_is_thin(D, row(3, 10)))
        self.assertFalse(indexing.pref_is_thin(D, row(25, 12)))

    def test_a_prefecture_without_the_ministrys_table_is_not_decided_by_the_rule(self):
        self.assertFalse(indexing.pref_is_thin(D, {"has": False, "total": {"R07": None}, "ytd": {"R08": None}}))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class ThinPrefPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True)
        cls.d = build.prepare(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_noindex_prefecture_pages_are_exactly_the_thin_ones_and_they_stay_on_the_site(self):
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        thin = [r for r in self.d["rows"] if not build.has_no_bears(self.d, r) and indexing.pref_is_thin(self.d, r)]
        self.assertTrue(thin)
        for r in self.d["rows"]:
            if build.has_no_bears(self.d, r):
                continue
            html = (self.out / r["slug"] / "index.html").read_text(encoding="utf-8")
            is_thin = indexing.pref_is_thin(self.d, r)
            self.assertEqual('<meta name="robots" content="noindex,follow">' in html, is_thin, r["name"])
            self.assertEqual(f"<loc>https://kuma-sokuho.com/{r['slug']}/</loc>" in sitemap, not is_thin, r["name"])
            self.assertIn("<table", html if r["has"] else "<table")                    # the page is the full page, not a short one

    def test_a_thin_prefecture_page_is_still_linked_from_the_other_pages(self):
        home = (self.out / "ranking" / "sightings" / "index.html").read_text(encoding="utf-8")
        nav = (self.out / "tottori" / "index.html").read_text(encoding="utf-8")
        for r in self.d["rows"]:
            if indexing.pref_is_thin(self.d, r) and r["slug"] != "tottori":
                self.assertIn(f'href="/{r["slug"]}/"', nav, r["name"])                    # the list of the other prefectures on every prefecture page
        self.assertTrue(re.search(r'href="/[a-z]+/"', home))


if __name__ == "__main__":
    unittest.main()
