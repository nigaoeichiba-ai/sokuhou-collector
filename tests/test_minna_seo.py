"""みんなのイラスト: SEO fixes of the 2026-10-20 audit.  The live site had 540 illustration pages sharing 231 titles ('ロケット 無料・商用OKのイラスト' on 4 pages),
and the empty list of a visitor's favourites and the search form were offered to search engines."""
import re
import unittest
from collections import Counter

from sites.minna import build
from tests.test_minna_sitecache import shared_site


def item(i, title, series, **kw):
    return {"id": i, "title": title, "series": series, "genre": "g", "touch": "flat", "tags": [], "desc": "d", "w": 10, "h": 10, **kw}


class TitleRule(unittest.TestCase):
    ITEMS = [item("a1", "ロケット", "s-space"), item("b1", "ロケット", "s-transport"), item("c1", "ねこ", "s-cat"),
             item("d1", "手を振る", "s-pair"), item("d2", "手を振る", "s-pair")]
    SERIES = {"s-space": {"title": "宇宙と太陽系の星", "ids": ["a1"]}, "s-transport": {"title": "乗り物", "ids": ["b1"]}, "s-cat": {"title": "ねこ", "ids": ["c1"]},
              "s-pair": {"title": "二人", "ids": ["d1", "d2"]}}

    def t(self, i):
        it = next(x for x in self.ITEMS if x["id"] == i)
        return build.illust_page_title(it, self.ITEMS, self.SERIES[it["series"]])

    def test_a_unique_subject_keeps_its_name(self):
        self.assertEqual(self.t("c1"), "ねこ")

    def test_a_subject_drawn_in_several_sets_gets_the_set_name(self):
        self.assertEqual(self.t("a1"), "ロケット(宇宙と太陽系の星)")
        self.assertEqual(self.t("b1"), "ロケット(乗り物)")
        self.assertNotEqual(self.t("a1"), self.t("b1"))

    def test_the_same_subject_twice_in_one_set_gets_its_place_in_the_set(self):
        self.assertEqual(self.t("d1"), "手を振る(二人・1点目)")
        self.assertEqual(self.t("d2"), "手を振る(二人・2点目)")


class InTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_no_two_indexable_picture_pages_share_a_title(self):
        titles = Counter()
        for rel in self.files:
            if rel.startswith("illust/") and rel.endswith("/index.html") and "/page/" not in rel:
                html = self.read(rel)
                if 'content="noindex' not in html:
                    titles[re.search(r"<title>(.*?)</title>", html, re.S).group(1)] += 1
        self.assertEqual([t for t, n in titles.items() if n > 1][:5], [])

    def test_the_favourites_page_and_the_search_form_are_noindex_and_not_in_the_sitemap(self):
        sitemap = self.read("sitemap.xml")
        for rel in ("favorites/index.html", "search/index.html"):
            self.assertIn('<meta name="robots" content="noindex,follow">', self.read(rel), rel)
            self.assertNotIn(f"https://minna-no-illust.com/{rel[:-len('index.html')]}<", sitemap, rel)

    def test_the_picture_pages_have_breadcrumb_data(self):
        rel = next(f for f in self.files if f.startswith("illust/") and f.endswith("/index.html") and "/page/" not in f and f != "illust/index.html")
        self.assertIn('"@type": "BreadcrumbList"', self.read(rel))


if __name__ == "__main__":
    unittest.main()
