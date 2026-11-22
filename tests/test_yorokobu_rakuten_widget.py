import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, rakutenwidget as rw
from tests.test_yorokobu_build import CFG

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
BLOCK = re.compile(r'<aside class="rk-widget".*?</aside>', re.S)


class WidgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        c = content.load(FIX)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        build.render_site(c, items, CFG, cls.out, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def pages(self):
        for p in self.out.rglob("*.html"):
            yield "/" + p.relative_to(self.out).as_posix().replace("index.html", ""), p.read_text(encoding="utf-8")

    def test_every_built_page_has_one_to_three_widgets(self):
        n = 0
        for path, t in self.pages():
            k = t.count('class="rk-widget"')
            if rw.eligible(path) and 'class="wrap"' in t and "<h1" in t and path not in ("/about/", "/privacy/"):
                self.assertTrue(1 <= k <= rw.MAX_WIDGETS, f"{path}: {k} widgets")
                n += 1
            elif not rw.eligible(path):
                self.assertEqual(k, 0, path)
        self.assertGreater(n, 20)

    def test_widget_is_its_own_block_with_a_visible_pr_label_and_no_other_link(self):
        for path, t in self.pages():
            for b in BLOCK.findall(t):
                self.assertIn('<span class="pr-chip">PR</span>', b, path)
                self.assertLess(b.index("pr-chip"), b.index("<script"), path)             # the label is above the widget
                self.assertNotIn("<a ", b, path)                                           # no text link of ours inside the block (no product-name links)
                self.assertNotIn("amazon", b.lower(), path)
                self.assertNotIn("valuecommerce", b.lower(), path)
                self.assertEqual(b.count("<script"), 2, path)                              # Rakuten's two scripts only
            if "rk-widget" in t:
                self.assertIn("pr-foot", t, path)                                          # the full advertising notice is at the foot

    def test_no_popup_or_fixed_bar_and_nothing_stored(self):
        css = (build.HERE / "assets" / "style.css").read_text(encoding="utf-8")
        rule = css[css.index("Rakuten motion widget"):]
        self.assertNotIn("position: fixed", rule)
        self.assertNotIn("position:fixed", rule)
        for _, t in self.pages():
            for b in BLOCK.findall(t):
                self.assertNotRegex(b, r"https://(thumbnail|item)\.rakuten|<img")           # the widget draws its own products; none is written into our output

    def test_insert_rules(self):
        body = '<h1>x</h1><p class="lead">a</p>' + "".join(f"<section><h2>s{i}</h2>" + "x" * 3000 + "</section>" for i in range(6))
        out = rw.insert(body, "/gift/a/")
        self.assertEqual(out.count("rk-widget\""), 3)
        self.assertEqual(rw.insert(out, "/gift/a/"), out)                                   # twice = once
        self.assertEqual(rw.insert(body, "/contact/"), body)                                # form pages take none
        self.assertEqual(rw.insert(body, "/ask/abc/"), body)
        short = '<h1>x</h1><p class="lead">a</p><section><h2>s</h2>x</section>'
        self.assertEqual(rw.insert(short, "/x/").count('class="rk-widget"'), 2)             # short page: lead + end, no middle
        related = body + "<section><h2>関連するページ</h2><p>y</p></section>"
        out = rw.insert(related, "/x/")
        self.assertLess(out.index('data-pos="end"'), out.index("関連するページ"))            # the last widget sits before the related links


if __name__ == "__main__":
    unittest.main()
