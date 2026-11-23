"""Rakuten motion widget on sale-calendar.com (owner 2026-11-22): 1-3 blocks on every page but the 404, each alone with a 'PR' above it, no mall link inside, no product data stored."""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")
os.environ.setdefault("KAIDOKI_REDESIGN", "1")

from sites.kaidoki import gen  # noqa: E402
from sites.kaidoki.redesign import rakuten_widget as rw  # noqa: E402
from sokuhou import newsite  # noqa: E402

SITE = Path(__file__).resolve().parents[1] / "sites" / "kaidoki"
BLOCK = re.compile(r'<aside class="rk-widget".*?</aside>', re.S)


class RakutenWidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen.write()
        cls.pages = {k: v for k, v in newsite.build_pages(SITE, release=True)[0].items() if isinstance(v, str) and k.endswith(".html") and v.startswith("<!doctype")}

    def test_every_page_has_one_to_three_blocks(self):
        for rel, html in self.pages.items():
            n = html.count('class="rk-widget"')
            if rel == "404.html":
                self.assertEqual(n, 0)
            elif rel.startswith("google") or '<main id="main">' not in html:
                continue
            else:
                self.assertTrue(1 <= n <= 3, f"{rel}: {n} widgets")

    def test_block_is_alone_with_pr_and_only_the_widget_script(self):
        for rel, html in self.pages.items():
            for b in BLOCK.findall(html):
                self.assertIn('<span class="pr-chip">PR</span>', b, rel)
                self.assertNotIn("<a ", b, rel)
                self.assertNotIn("amazon", b.lower().replace("rakuten_widget", ""), rel)
                self.assertEqual(re.findall(r"https?://[^\"\s']+", b), [rw.SCRIPT_URL], rel)       # document.write form, only the widget script
                self.assertEqual(b.count("<script>"), 1, rel)
                self.assertIn("rakuten_items=\"'+m+'\"", b, rel)
                self.assertIn('w>=760?"728x200":(w>=480?"468x160":', b, rel)

    def test_not_inside_a_table_or_before_the_lead(self):
        for rel, html in self.pages.items():
            for m in re.finditer('<aside class="rk-widget"', html):
                before = html[:m.start()]
                self.assertEqual(before.count("<table"), before.count("</table>"), f"{rel}: widget inside a table")

    def test_types_and_sizes(self):
        body = '<section class="content-block">a</section>' * 8 + '<h2>関連</h2><div class="article-links"></div><p class="credit">x</p>'
        out = rw.inject(body)
        blocks = BLOCK.findall(out)
        self.assertEqual(len(blocks), 3)
        self.assertIn('m="ctsmatch"', blocks[0]); self.assertIn('"300x250")', blocks[0])
        self.assertIn('m="ctsmatch"', blocks[1]); self.assertIn('"200x600")', blocks[1])
        self.assertIn('m="ranking"', blocks[2]); self.assertIn('"200x600")', blocks[2])
        self.assertEqual(out.count("rakuten_size"), 3)
        self.assertNotIn("__M__", out); self.assertNotIn("__MOBILE__", out)

    def test_inject_negative(self):
        body = '<section class="content-block">a</section>' * 3 + '<h2>関連</h2><div class="article-links"></div><p class="credit">x</p>'
        out = rw.inject(body)
        self.assertEqual(out.count("rk-widget\""), 2)
        self.assertLess(out.index("rk-widget"), out.index("<h2>関連"))


if __name__ == "__main__":
    unittest.main()
