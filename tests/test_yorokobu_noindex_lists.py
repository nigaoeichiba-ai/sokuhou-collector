"""Owner's approval of 2026-10-20 (first wave): the individual pages of the sales ranking (/ranking/<list>/) and of the number lists (/numbers/<list>/) are mostly a list of
products that changes every day, with little text of their own.  They get <meta name="robots" content="noindex,follow"> and leave the sitemap; the hubs, every other page and
every link stay as they were.  (No robots.txt ban: the search engine has to be able to read the tag.)  To undo: empty NOINDEX_LISTS in build.py."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, ranking
from sokuhou import sitecheck
from tests.test_yorokobu_numbers import prod
from tests.test_yorokobu_ranking import CFG, day, codes

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
NOINDEX = '<meta name="robots" content="noindex,follow">'


class NoindexListsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = content.load(FIX)
        items = copy.deepcopy(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        items["pairs"]["birthday-boyfriend"]["ideas"][0]["items"] += [prod(f"big{i}", 10000 + i, 4.6) for i in range(7)]
        s = ranking.update(None, {"f20": day(codes(16)), "m40": day(codes(16, "q"))}, date(2026, 10, 6))
        store = ranking.update(s, {"f20": day(codes(16)), "m40": day(codes(16, "q"))}, date(2026, 10, 7))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(c, items, CFG, cls.out, release=True, today=date(2026, 10, 7), ranking=store)
        cls.sitemap = (cls.out / "sitemap.xml").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def listed(self):
        return re.findall(r"<loc>https://yorokobu-present\.com(/[^<]*)</loc>", self.sitemap)

    def test_the_individual_lists_have_noindex_follow_once_and_are_not_in_the_sitemap(self):
        pages = sorted(p.relative_to(self.out).as_posix() for sub in ("ranking", "numbers") for p in (self.out / sub).glob("*/index.html"))
        self.assertGreaterEqual(len(pages), 3, pages)
        self.assertTrue(any(p.startswith("ranking/") for p in pages) and any(p.startswith("numbers/") for p in pages))
        for rel in pages:
            t = self.read(rel)
            self.assertEqual(t.count('name="robots"'), 1, rel)
            self.assertIn(NOINDEX, t, rel)
            self.assertNotIn("/" + rel[: -len("index.html")], self.listed(), rel)

    def test_the_hubs_and_every_other_page_stay_indexable_and_in_the_sitemap(self):
        for rel, url in (("ranking/index.html", "/ranking/"), ("numbers/index.html", "/numbers/"), ("index.html", "/"), ("about/index.html", "/about/"), ("policy/index.html", "/policy/")):
            self.assertNotIn("noindex", self.read(rel), rel)
            self.assertIn(url, self.listed(), url)
        others = [p for p in self.out.rglob("index.html") if p.relative_to(self.out).parts[0] not in ("ranking", "numbers", "favorites", "list", "ask", "p") and not p.relative_to(self.out).as_posix().startswith(("ask/", "ask_"))]
        self.assertGreater(len(others), 20)
        bad = [p.relative_to(self.out).as_posix() for p in others if NOINDEX in p.read_text(encoding="utf-8") and p.relative_to(self.out).as_posix() not in ("favorites/index.html", "list/index.html")]
        self.assertEqual(bad, [], "pages that should be indexable carry noindex")

    def test_links_stay_and_robots_txt_does_not_ban_them(self):
        self.assertIn('href="/ranking/f20/"', self.read("ranking/index.html"))                 # internal links are kept (follow)
        self.assertIn('href="/numbers/reviews-10000/"', self.read("numbers/index.html"))
        robots = self.read("robots.txt")
        self.assertNotIn("ranking", robots)
        self.assertNotIn("numbers", robots)

    def test_the_site_checker_accepts_the_result(self):
        problems = sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",))
        self.assertEqual([p for p in problems if "ranking" in p or "numbers" in p], [], problems[:10])


class RuleTest(unittest.TestCase):
    def test_only_the_individual_pages_of_the_two_lists_match(self):
        for key in ("ranking/g-bag/index.html", "ranking/f20/index.html", "numbers/hidden-gems/index.html"):
            self.assertTrue(build.NOINDEX_LISTS.match(key), key)
        for key in ("ranking/index.html", "numbers/index.html", "budget/under3000/index.html", "month/1/index.html", "theme/x/index.html", "gift/x/index.html",
                    "data/ranking-turnover/index.html", "ranking/f20/extra/index.html", "rankings/x/index.html"):
            self.assertFalse(build.NOINDEX_LISTS.match(key), key)

    def test_noindex_thin_marks_the_matching_pages_once_and_returns_their_keys(self):
        pages = {"ranking/a/index.html": "<head><title>x</title></head>", "ranking/index.html": "<head></head>", "numbers/b/index.html": f"<head>\n{NOINDEX}</head>",
                 "theme/t/index.html": "<head></head>"}
        keys = build.noindex_thin(pages)
        self.assertEqual(sorted(keys), ["numbers/b/index.html", "ranking/a/index.html"])
        self.assertEqual(pages["ranking/a/index.html"].count("noindex"), 1)
        self.assertEqual(pages["numbers/b/index.html"].count("noindex"), 1)                  # not added twice
        self.assertNotIn("noindex", pages["ranking/index.html"])
        self.assertNotIn("noindex", pages["theme/t/index.html"])


if __name__ == "__main__":
    unittest.main()
