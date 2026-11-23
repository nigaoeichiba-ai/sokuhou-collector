"""saichin: 提携済み(A8 メディア004)の広告リンクは、PR 表示と rel="nofollow sponsored noopener" target="_blank" を持ち、貼る場所に実際に貼られている(2026-11-15 窓口)。"""
import re
import unittest

from tests.test_saichin_pages import SiteFixture

A8_CODES = {"mamaworks": "4BEL1J+AAX4YY", "workstaff": "4BEL1J+AFOLT6", "coconala": "4BEL1J+AJ97FU",
            "emeao": "4BGR94+A07C2Y", "kyujin": "4BGR94+A3RXPM"}
# 求人・副業の導線を置いたページ(貼らない所の理由は、公開結果の表に書く)
PLACES = {
    "guide/wall/index.html": ("mamaworks", "workstaff", "coconala"),
    "guide/raise/index.html": ("mamaworks", "workstaff", "coconala"),
    "guide/monthly/index.html": ("mamaworks", "workstaff"),
    "guide/city/index.html": ("mamaworks", "workstaff"),
    "guide/calculate/index.html": ("mamaworks", "workstaff"),
    "check/index.html": ("mamaworks", "workstaff"),
    "guide/below/index.html": ("emeao", "kyujin"),   # 雇う人向け(2026-11-23 承認)
    "guide/excluded/index.html": ("emeao",),
}


def a8_anchors(html: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"<a\b([^>]*href=\"https://px\.a8\.net/[^>]*)>", html)]


def bad_a8_anchors(html: str) -> list[str]:
    out = []
    for a in a8_anchors(html):
        rel = (re.search(r'rel="([^"]*)"', a) or [None, ""])[1]
        if not all(w in rel.split() for w in ("nofollow", "sponsored", "noopener")) or 'target="_blank"' not in a:
            out.append(a)
    return out


class AffiliateLinksTest(SiteFixture):
    def test_every_a8_link_has_sponsored_noopener_and_a_new_tab(self):
        bad = {}
        for rel in (r for r in self.files if r.endswith(".html")):
            b = bad_a8_anchors(self.read(rel))
            if b:
                bad[rel] = b
        self.assertEqual(bad, {})

    def test_the_places_have_their_programs_and_a_pr_label(self):
        for rel, programs in PLACES.items():
            html = self.read(rel)
            for p in programs:
                self.assertIn(f"a8mat={A8_CODES[p]}", html, (rel, p))
            self.assertRegex(html, r'<(p|div) class="pr-note"><strong>PR</strong>', rel)

    def test_a_page_with_an_a8_link_says_pr(self):
        for rel in (r for r in self.files if r.endswith(".html")):
            html = self.read(rel)
            if a8_anchors(html):
                self.assertIn("pr-note", html, rel)

    def test_link_words_are_names_not_addresses(self):
        for rel in PLACES:
            for text in re.findall(r"<a\b[^>]*px\.a8\.net[^>]*>(.*?)</a>", self.read(rel), re.S):
                self.assertNotRegex(re.sub(r"<[^>]+>", "", text).strip(), r"^(https?://|www\.)|[a-z0-9-]+\.(jp|com|net)")


class DetectorTest(unittest.TestCase):
    def test_finds_a_link_with_only_nofollow(self):
        self.assertTrue(bad_a8_anchors('<a href="https://px.a8.net/svt/ejp?a8mat=1" rel="nofollow">x</a>'))
        self.assertTrue(bad_a8_anchors('<a href="https://px.a8.net/svt/ejp?a8mat=1" rel="nofollow sponsored noopener">x</a>'))   # no target
        self.assertEqual(bad_a8_anchors('<a href="https://px.a8.net/svt/ejp?a8mat=1" target="_blank" rel="nofollow sponsored noopener">x</a>'), [])


if __name__ == "__main__":
    unittest.main()
