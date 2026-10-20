"""みんなのイラスト: thin pages are noindex,follow and out of the sitemap (owner decision 2026-10-20), decided by measuring the build, never by a list."""
import re
import unittest

from sites.minna import build
from tests.test_minna_sitecache import shared_site


def pad(n: int) -> str:
    return "<html><head></head><body><main>" + "あ" * n + "</main></body></html>"


class Rule(unittest.TestCase):
    def test_kinds_of_page(self):
        self.assertEqual(build.page_kind("illust/page/2/index.html"), "paged")
        self.assertEqual(build.page_kind("genre/food/page/3/index.html"), "paged")
        self.assertEqual(build.page_kind("tag/abc1234567/page/2/index.html"), "paged")
        self.assertEqual(build.page_kind("genre/food/pixel/index.html"), "cross")
        self.assertEqual(build.page_kind("genre/food/index.html"), "")             # the first page of a genre is a hub, not thin by kind
        self.assertEqual(build.page_kind("category/expressions/index.html"), "category")
        self.assertEqual(build.page_kind("tag/abc1234567/index.html"), "tag")
        for other in ("illust/season-christmas/index.html", "series/dog-pose/index.html", "guide/x/index.html", "special/x/index.html", "index.html", "touch/flat/index.html"):
            self.assertEqual(build.page_kind(other), "", other)

    def test_a_page_with_more_text_than_the_bar_leaves_the_rule_by_itself(self):
        bar = build.THIN_CHARS
        pages = {"genre/a/b/index.html": pad(bar["cross"] - 1), "genre/a/c/index.html": pad(bar["cross"]),
                 "tag/t1/index.html": pad(bar["tag"] - 1), "tag/t2/index.html": pad(bar["tag"]),
                 "category/x/index.html": pad(bar["category"] - 1), "category/y/index.html": pad(bar["category"]),
                 "illust/page/2/index.html": pad(5000)}                              # a later page of a list is thin however long it is
        self.assertEqual(build.thin_pages(pages), {"genre/a/b/index.html", "tag/t1/index.html", "category/x/index.html", "illust/page/2/index.html"})

    def test_pages_of_other_kinds_are_never_thin_and_bytes_are_ignored(self):
        pages = {"illust/x/index.html": pad(10), "series/y/index.html": pad(10), "genre/z/index.html": pad(10), "files/a.png": b"\x89PNG", "index.html": pad(1)}
        self.assertEqual(build.thin_pages(pages), set())

    def test_noindex_follow_is_added_once(self):
        html = build.noindex("<html><head>\n<meta charset=\"utf-8\"></head></html>")
        self.assertIn('<meta name="robots" content="noindex,follow">', html)
        self.assertEqual(build.noindex(html), html)

    def test_visible_chars_ignores_tags_scripts_and_the_header(self):
        html = "<body><header>ヘッダー</header><main><p>あい う</p><script>var x = 1;</script><b>え</b></main></body>"
        self.assertEqual(build.visible_chars(html), 4)


class InTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()
        cls.sitemap = (cls.out / "sitemap.xml").read_text(encoding="utf-8")

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def in_sitemap(self, rel):
        url = "https://minna-no-illust.com/" + rel[:-len("index.html")]
        return f"<loc>{url}</loc>" in self.sitemap

    def test_thin_pages_have_noindex_follow_and_are_not_in_the_sitemap_and_the_others_are_the_other_way_round(self):
        html_pages = [f for f in self.files if f.endswith("/index.html") or f == "index.html"]
        thin = {f for f in html_pages if build.page_kind(f) == "paged"}
        thin |= set(build.UTILITY_PAGES)        # a visitor's own list and the search form (2026-10-20 SEO audit)
        for f in html_pages:
            kind = build.page_kind(f)
            if kind in build.THIN_CHARS and build.visible_chars(self.read(f).replace('<meta name="robots" content="noindex,follow">', "")) < build.THIN_CHARS[kind]:
                thin.add(f)
        self.assertGreater(len(thin), 150)
        for f in html_pages:
            robots = re.findall(r'<meta name="robots" content="([^"]*)"', self.read(f))
            if f in thin:
                self.assertEqual(robots, ["noindex,follow"], f)
                self.assertFalse(self.in_sitemap(f), f)
            else:
                self.assertEqual(robots, [], f)
                self.assertTrue(self.in_sitemap(f), f)

    def test_the_kinds_the_owner_named_are_covered_and_the_content_pages_are_not(self):
        thin = [f for f in self.files if f.endswith("/index.html") and 'content="noindex,follow"' in self.read(f)]
        kinds = {build.page_kind(f) for f in thin}
        self.assertEqual(kinds - {""}, {"paged", "cross", "category", "tag"})      # "" = the utility pages (build.UTILITY_PAGES)
        for f in thin:
            self.assertFalse(f.startswith(("illust/", "series/", "guide/", "special/")) and not build.page_kind(f), f)
        for f in ("illust/season-christmas/index.html", "series/dog-pose/index.html", "guide/nurie-insatsu/index.html", "special/nenga-2027/index.html", "genre/animals/index.html",
                  "touch/kawaii/index.html", "illust/index.html", "tool/nenga/index.html", "index.html"):
            self.assertNotIn("noindex", self.read(f), f)
            self.assertTrue(self.in_sitemap(f), f)

    def test_the_sitemap_count_is_the_pages_minus_the_thin_ones_and_robots_does_not_block(self):
        pages = [f for f in self.files if f.endswith("/index.html") or f == "index.html"]
        thin = [f for f in pages if 'content="noindex,follow"' in self.read(f)]
        self.assertEqual(self.sitemap.count("<loc>"), len(pages) - len(thin))
        robots = self.read("robots.txt")
        self.assertNotIn("Disallow: /page", robots)
        self.assertNotIn("Disallow: /genre", robots)
        self.assertIn("Allow: /", robots)

    def test_links_to_thin_pages_stay(self):
        home_of_list = self.read("illust/index.html")
        self.assertIn('href="/illust/page/2/"', home_of_list)                   # the pager still leads on (noindex,follow)


if __name__ == "__main__":
    unittest.main()
