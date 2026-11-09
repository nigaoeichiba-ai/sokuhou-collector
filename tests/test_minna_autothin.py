"""Stage 2 of the AdSense work (2026-11-09): thin automatic list pages (keyword, genre, touch, use, new) that nobody has seen in a search are noindex,follow and out of the sitemap;
the pages with a search history (content/keep_indexed.json), the two entrances, thick pages and all other kinds stay.  AUTO_THIN_ENABLED = False undoes it."""
import json
import re
import unittest
from pathlib import Path
from unittest import mock

from sites.minna import build
from tests.test_minna_sitecache import shared_site

THIN = "<main><h1>x</h1><p>" + "あ" * 120 + "</p></main>"
THICK = "<main><h1>x</h1><p>" + "あ" * 400 + "</p></main>"


class Rule(unittest.TestCase):
    def test_a_thin_list_page_without_history_is_thin(self):
        pages = {"tag/aaaa/index.html": THIN, "touch/kawaii/index.html": THIN, "genre/animals/index.html": THIN, "use/flyer/index.html": THIN, "new/index.html": THIN}
        self.assertEqual(build.auto_thin_pages(pages, keep=set()), set(pages))

    def test_a_page_with_a_search_history_stays(self):
        pages = {"tag/aaaa/index.html": THIN, "genre/work/faceless/index.html": THIN}
        self.assertEqual(build.auto_thin_pages(pages, keep={"/tag/aaaa/"}), {"genre/work/faceless/index.html"})

    def test_a_page_with_300_characters_of_sentences_stays(self):
        self.assertEqual(build.auto_thin_pages({"tag/bbbb/index.html": THICK}, keep=set()), set())

    def test_the_two_entrances_stay(self):
        self.assertEqual(build.auto_thin_pages({"tag/index.html": THIN, "use/index.html": THIN}, keep=set()), set())

    def test_other_kinds_are_never_touched_by_this_rule(self):
        pages = {"illust/x/index.html": THIN, "series/x/index.html": THIN, "guide/x/index.html": THIN, "special/x/index.html": THIN, "tool/x/index.html": THIN, "index.html": THIN, "about/index.html": THIN}
        self.assertEqual(build.auto_thin_pages(pages, keep=set()), set())

    def test_a_paged_list_is_left_to_the_older_rule_and_non_html_is_ignored(self):
        self.assertEqual(build.auto_thin_pages({"tag/aaaa/page/2/index.html": THIN, "tag/aaaa/data.json": THIN, "tag/cccc/index.html": b"x"}, keep=set()), set())

    def test_the_switch_undoes_it(self):
        with mock.patch.object(build, "AUTO_THIN_ENABLED", False):
            self.assertEqual(build.auto_thin_pages({"tag/aaaa/index.html": THIN}, keep=set()), set())

    def test_the_list_file_holds_url_paths_of_the_automatic_kinds(self):
        data = json.loads((Path(build.__file__).parent / "content" / "keep_indexed.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["pages"]), 40)
        for u in data["pages"]:
            self.assertRegex(u, r"^/(tag|touch|genre|use)/[^/]+(/[^/]+)?/$", u)


class InTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()
        cls.sitemap = (cls.out / "sitemap.xml").read_text(encoding="utf-8")

    def html(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_pages_are_marked_and_listed_as_the_rule_says(self):
        keep = build.keep_indexed()
        marked = unmarked = 0
        for rel in self.files:
            if not rel.endswith("index.html") or rel.split("/")[0] not in build.AUTO_KINDS or "/" not in rel or build.page_kind(rel) == "paged" or rel in build.AUTO_ALWAYS_INDEXED:
                continue
            t = self.html(rel)
            url = "/" + rel[:-len("index.html")]
            thin_by_rule = url not in keep and build.prose_chars(t) < build.AUTO_MAX_PROSE
            noindex = 'content="noindex,follow"' in t
            in_sitemap = f"<loc>https://minna-no-illust.com{url}</loc>" in self.sitemap
            if thin_by_rule:
                self.assertTrue(noindex and not in_sitemap, rel)
                marked += 1
            elif not noindex:
                self.assertTrue(in_sitemap, rel)
                unmarked += 1
        self.assertGreater(marked, 100)
        self.assertGreater(unmarked, 20)

    def test_the_two_entrances_and_the_pages_with_history_are_indexable(self):
        for rel in ("tag/index.html", "use/index.html", "touch/picturebook/index.html", "use/learning/index.html"):
            t = self.html(rel)
            self.assertNotIn("noindex", t, rel)
            self.assertIn(f"<loc>https://minna-no-illust.com/{rel[:-len('index.html')]}</loc>", self.sitemap, rel)

    def test_noindex_pages_still_lead_on_and_carry_no_ad_tag(self):
        self.assertIn('content="noindex,follow"', self.html("genre/animals/index.html"))
        self.assertNotIn("adsbygoogle", self.html("genre/animals/index.html"))
        self.assertIn('href="/genre/animals/', self.html("index.html"))


if __name__ == "__main__":
    unittest.main()
