"""みんなのイラスト: a later page of a list has its own title and meta description (週次レビュー 2026-10-19: page 2 and page 10 shared the description of page 1)."""
import re
import unittest

from tests.test_minna_sitecache import shared_site


def meta(html: str) -> tuple[str, str]:
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    return title, desc


class PagedMetaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()

    def read(self, f):
        return (self.out / f).read_text(encoding="utf-8")

    def test_every_page_of_a_list_has_its_own_description_and_title(self):
        pages = [f for f in self.files if re.search(r"/page/\d+/index\.html$", f)]
        self.assertGreater(len(pages), 5)
        seen = {}
        for f in pages:
            n = re.search(r"/page/(\d+)/", f).group(1)
            title, desc = meta(self.read(f))
            self.assertIn(f"ページ{n}", title, f)
            self.assertTrue(title.endswith(" | みんなのイラスト"), (f, title))
            self.assertRegex(desc, r"^\d+〜\d+点目", f)
            seen.setdefault((title, desc), []).append(f)
        self.assertEqual([v for v in seen.values() if len(v) > 1], [])

    def test_the_first_page_keeps_its_description(self):
        _, d1 = meta(self.read("illust/index.html"))
        _, d2 = meta(self.read("illust/page/2/index.html"))
        self.assertTrue(d2.endswith(d1))
        self.assertNotRegex(d1, r"点目")


if __name__ == "__main__":
    unittest.main()
