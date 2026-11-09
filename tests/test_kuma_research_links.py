"""kuma-sokuho.com (2026-11-09): links from the pages to the research notes of the same subject, and the site's own 404 page.

The notes were linked from their own list only; now a page links the notes that count what it shows (research_links.json), and a prefecture page links the notes that have a row
for the prefecture.  Negative cases: an unknown slug is skipped (a typo in the links file fails the file test), a note a page already links is not repeated, a prefecture with no row gets no block."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build
from sites.kuma import research as research_mod
from sokuhou.sources import env_kuma
from tests.test_kuma_adsense_fix import TODAY, _yamaguchi
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data

DOCS = [{"slug": "a", "h1": "Aの見出し", "sections": [{"table": {"rows": [["宮城県", "1"], ["令和7年度", "2"]]}}]},
        {"slug": "b", "h1": "Bの見出し", "sections": [{"table": {"rows": [["秋田県", "1"]]}}]},
        {"slug": "c", "h1": "Cの見出し", "sections": [{"paragraphs": ["表なし"]}]}]


class HelperTest(unittest.TestCase):
    def test_a_block_lists_the_notes_by_their_titles(self):
        html = research_mod.related_html(DOCS, ["a", "b"])
        self.assertIn('<a href="/research/a/">Aの見出し</a>', html)
        self.assertIn('<a href="/research/b/">Bの見出し</a>', html)
        self.assertTrue(html.startswith("<h2>関連する研究ノート</h2>"))

    def test_a_note_the_page_already_links_is_not_repeated_and_nothing_is_written_when_all_are_linked(self):
        page = '<a href="/research/a/">x</a>'
        html = research_mod.related_html(DOCS, ["a", "b"], page)
        self.assertNotIn("/research/a/", html)
        self.assertIn("/research/b/", html)
        self.assertEqual(research_mod.related_html(DOCS, ["a"], page), "")

    def test_a_slug_that_is_not_among_the_notes_is_skipped_and_the_links_file_test_below_guards_typos(self):
        html = research_mod.related_html(DOCS, ["a", "zzz"])
        self.assertIn("/research/a/", html)
        self.assertNotIn("zzz", html)
        self.assertEqual(research_mod.related_html(DOCS, ["zzz"]), "")

    def test_notes_with_a_row_for_the_prefecture_in_the_given_order(self):
        self.assertEqual(research_mod.notes_with_row(DOCS, {"宮城県"}, ["b", "a", "c"]), ["a"])
        self.assertEqual(research_mod.notes_with_row(DOCS, {"宮城県", "秋田県"}, ["b", "a", "c"]), ["b", "a"])
        self.assertEqual(research_mod.notes_with_row(DOCS, {"宮城県", "秋田県"}, ["b", "a", "c"], limit=1), ["b"])

    def test_a_prefecture_with_no_row_gets_nothing(self):
        self.assertEqual(research_mod.notes_with_row(DOCS, {"高知県"}, ["a", "b", "c"]), [])
        self.assertEqual(research_mod.notes_with_row(DOCS, {"令和7年度"} - {"令和7年度"}, ["a"]), [])

    def test_the_links_file_names_only_notes_that_exist_and_pages_with_a_path(self):
        slugs = {x["slug"] for x in research_mod.load()}
        for path, names in research_mod.LINKS.items():
            self.assertRegex(path, r"^/[a-z/]*/$")
            self.assertTrue(names)
            self.assertFalse(set(names) - slugs, path)
            self.assertEqual(len(names), len(set(names)), path)
        for s in research_mod.PREF_NOTES + research_mod.LIVE_NOTES:
            self.assertIn(s, slugs)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class SitePagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.docs = research_mod.load()
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs={"yamaguchi": _yamaguchi({"岩国市": 120, "周南市": 30})}, today=TODAY, research=cls.docs)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_pages_link_the_notes_of_their_subject(self):
        self.assertIn('href="/research/injury-rate/"', self.read("ranking/injuries/index.html"))
        self.assertIn('href="/research/deaths-by-year/"', self.read("ranking/deaths/index.html"))
        self.assertIn('href="/research/peak-month-type/"', self.read("season/index.html"))
        self.assertIn('href="/research/emergency-by-month/"', self.read("emergency/index.html"))
        self.assertIn('href="/research/hour-of-day/"', self.read("live/index.html"))
        self.assertIn('href="/research/latitude-by-month/"', self.read("map/index.html"))
        self.assertIn('href="/research/trace-ratio/"', self.read("guide/data/index.html"))

    def test_every_note_of_the_links_file_is_linked_from_at_least_one_page_besides_its_list(self):
        linked = set()
        for f in self.files:
            if f.endswith(".html") and not f.startswith("research/"):
                linked |= set(re.findall(r'href="/research/([a-z0-9-]+)/"', self.read(f)))
        wanted = {s for names in research_mod.LINKS.values() for s in names} - {"hokkaido-monthly"}       # the Hokkaido page is not in this fixture
        self.assertFalse(wanted - linked, wanted - linked)

    def test_a_prefecture_page_links_only_notes_that_have_a_row_for_it(self):
        by = {x["slug"]: x for x in self.docs}
        for r in build.prepare(self.raw)["rows"]:
            if build.has_no_bears(build.prepare(self.raw), r):
                continue
            html = self.read(f"{r['slug']}/index.html")
            for s in re.findall(r'href="/research/([a-z0-9-]+)/"', html):
                cells = {str(row[0]).strip() for sec in by[s].get("sections", []) if sec.get("table") for row in sec["table"]["rows"] if row}
                self.assertIn(r["name"], cells, (r["name"], s))                       # a note is on the page only because its table has this prefecture
            self.assertLessEqual(len(set(re.findall(r'href="/research/([a-z0-9-]+)/"', html))), 4, r["name"])

    def test_the_link_block_is_inside_the_main_text_and_after_the_content(self):
        html = self.read("ranking/injuries/index.html")
        body = html.split("<main", 1)[1].split("</main>", 1)[0]
        self.assertGreater(body.index("関連する研究ノート"), body.index("<table"))

    def test_an_unknown_url_answers_with_the_sites_own_404_page_and_the_redirects_survive(self):
        ht = self.read(".htaccess")
        self.assertEqual(ht.count("ErrorDocument 404 /404.html"), 1)
        self.assertIn("RewriteEngine on", ht)
        self.assertIn("404.html", self.files)
        page = self.read("404.html")
        self.assertIn('content="noindex,follow"', page)                            # opened directly it answers 200, so it asks not to be indexed
        self.assertIn("ページが見つかりません", page)
        sitemap = self.read("sitemap.xml")
        self.assertNotIn("404", sitemap)
        self.assertIn("<loc>https://kuma-sokuho.com/</loc>", sitemap)              # the home page is still in the sitemap (the 404 page must not take it out)

    def test_the_404_page_has_no_ad_script(self):
        self.assertNotIn("adsbygoogle", self.read("404.html"))      # (the loader of the content pages is checked on the live site: the test configuration has no publisher id)


if __name__ == "__main__":
    unittest.main()
