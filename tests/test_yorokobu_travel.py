"""旅行・宿泊を贈る /travel/: the only affiliate link is Rakuten Travel (the spec's formula, nothing added), and every internal link has a page."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import quote

from sites.yorokobu import build, content
from tests.test_yorokobu_build import CFG, FIX

TODAY = date(2026, 5, 3)


class TravelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = content.load(FIX)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.files = build.render_site(c, items, CFG, cls.out, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_page_exists_in_sitemap_and_is_linked_from_the_tools_hub_and_the_top(self):
        self.assertIn("travel/index.html", self.files)
        self.assertIn("/travel/</loc>", self.read("sitemap.xml"))
        self.assertIn('href="/travel/"', self.read("tool/index.html"))
        self.assertIn('href="/travel/"', self.read("index.html"))

    def test_the_rakuten_travel_links_are_the_spec_formula_with_pr_and_a_word_as_text(self):
        t = self.read("travel/index.html")
        want = f"https://hb.afl.rakuten.co.jp/hgc/{CFG['rakuten_affiliate_id']}/?pc={quote('https://travel.rakuten.co.jp/', safe='')}"
        hrefs = re.findall(r'<a href="([^"]+)" target="_blank" rel="([^"]+)">([^<]+)</a>', t)
        aff = [h for h in hrefs if "hb.afl.rakuten" in h[0]]
        self.assertGreaterEqual(len(aff), 2)
        for href, rel, text in aff:
            self.assertEqual(href, want)
            self.assertEqual(rel, "nofollow sponsored noopener")
            self.assertEqual(text, "楽天トラベル")           # a word, never the URL
        self.assertIn("pr-note", t)
        self.assertEqual(t.count('<aside class="pr-foot"'), 1)    # one notice only (2026-11-28: there were two)
        self.assertNotIn("amazon.co.jp", t)                 # no other mall's link next to a Rakuten link
        self.assertNotIn("Amazonアソシエイト", t)            # and then the notice does not name it (2026-11-28: it did, with no Amazon link on the page)

    def test_internal_links_all_point_at_built_pages(self):
        t = self.read("travel/index.html")
        for href in re.findall(r'href="(/[^"#?]*)"', t):
            if href.endswith("/") or href.endswith(".html"):
                rel = href.lstrip("/") + ("index.html" if href.endswith("/") else "")
                self.assertIn(rel or "index.html", self.files, href)

    def test_title_description_and_h1_are_specific(self):
        t = self.read("travel/index.html")
        self.assertIn("<h1>旅行・宿泊を贈る</h1>", t)
        self.assertRegex(t, r"<title>旅行・宿泊のプレゼント")
        self.assertEqual(len(re.findall(r"<h1>", t)), 1)


if __name__ == "__main__":
    unittest.main()
