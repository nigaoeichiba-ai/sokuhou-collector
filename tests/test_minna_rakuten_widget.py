"""みんなのイラスト: 楽天モーションウィジェット(2026-11-22)。全ページに共通の位置で入り、絵・ダウンロード・埋め込みの邪魔をしない。"""
import re
import unittest
from pathlib import Path

from sites.minna import rakutenwidget as rw

ILLUST = """<nav class="crumbs">x</nav>
<div class="illust"><div class="pic"><img src="a.webp" alt="a"></div><div class="info"><h1>T</h1><p class="lead">L</p>
<p class="dl"><a class="btn" href="/files/a.png" download>PNG</a></p>
<details class="embed"><textarea>&lt;a&gt;</textarea></details>
<aside class="licence-box">free</aside></div></div>
<nav class="prevnext">p</nav>
<section><h2>1</h2></section><section><h2>2</h2></section><section><h2>3</h2></section><section><h2>4</h2></section>
<section><h2>5</h2></section><section><h2>6</h2></section><section><h2>related</h2></section>
<div class="share">s</div>
<script type="application/ld+json">{"a":1}</script>"""


def page(inner):
    return f'<!doctype html><html><body><main class="wrap">{inner}</main><footer>f</footer></body></html>'


class Widget(unittest.TestCase):
    def test_three_widgets_outside_every_block(self):
        out = rw.add_widgets(page(ILLUST))
        self.assertEqual(out.count('class="rk-ad"'), 3)
        self.assertEqual(out.count("rakuten_widget.js"), 3)
        self.assertIn("document.write", out)
        self.assertEqual(out.count("<b>PR</b>"), 3)
        illust = re.search(r'<div class="illust">.*?</div></div>\n', out, re.S).group(0)
        self.assertNotIn("rk-ad", illust)                                  # not between the picture, the download button and the embed code
        self.assertLess(out.index("rk-ad"), out.index('class="prevnext"'))   # first one right after the answer
        self.assertLess(out.rindex("rk-ad"), out.index("<h2>related</h2>"))  # last one before the related section
        self.assertLess(out.rindex("rk-ad"), out.index('class="share"'))

    def test_short_page_gets_only_what_fits(self):
        out = rw.add_widgets(page('<h1>t</h1><p class="lead">l</p><ul><li>a</li></ul>'))
        self.assertEqual(out.count('class="rk-ad"'), 1)
        self.assertLess(out.index("rk-ad"), out.index("<ul>"))

    def test_idempotent_and_skips_pages_without_main(self):
        once = rw.add_widgets(page(ILLUST))
        self.assertEqual(rw.add_widgets(once), once)
        self.assertEqual(rw.add_widgets("<html><body>x</body></html>"), "<html><body>x</body></html>")

    def test_the_code_is_the_one_given_and_nothing_else_is_stored(self):
        b = rw.widget_block(0)
        self.assertIn("0fbf5187.c5400194.0fbf5188.09a2b95f", b)
        self.assertEqual(re.findall(r"https?://[^\"' ]+", b), [rw.WIDGET_SRC])    # one host: the widget script, no other mall
        self.assertNotIn("<a ", b)                                                  # no text link of ours in the part
        self.assertNotIn('<script type="text/javascript" src=', b)                 # the widget script is only ever written by document.write

    def test_sizes_follow_the_screen_and_link_types_follow_the_position(self):
        first, second, third = (rw.widget_block(n, 3) for n in range(3))
        for b in (first, second, third):
            self.assertIn('s=w>=800?"728x200":(w>=540?"468x160":', b)             # PC: 3 across, tablet: 3 across
        self.assertIn('"300x250");', first)                                         # the first one on a phone stays small
        self.assertIn('"200x600");', second)
        self.assertIn('"200x600");', third)                                         # 3 stacked
        self.assertIn('m="ctsmatch"', first)
        self.assertIn('m="ctsmatch"', second)
        self.assertIn('m="ranking"', third)                                         # the last one before the related section
        self.assertIn('m="ranking"', rw.widget_block(1, 2))
        self.assertIn('m="ctsmatch"', rw.widget_block(0, 1))
        self.assertIn("rk-a", first)
        self.assertIn("rk-b", third)

    def test_reserved_heights_match_the_sizes(self):
        css = (Path(__file__).resolve().parents[1] / "sites/minna/assets/style.css").read_text(encoding="utf-8")
        self.assertIn(".rk-box.rk-b { min-height: 600px; }", css)
        self.assertIn("@media (min-width: 540px) { .rk-box, .rk-box.rk-b { min-height: 160px; } }", css)
        self.assertIn("@media (min-width: 800px) { .rk-box, .rk-box.rk-b { min-height: 200px; } }", css)

    def test_add_to_pages_skips_404_and_non_html(self):
        pages = {"index.html": page(ILLUST), "404.html": page(ILLUST), "a.png": b"x", "sitemap.xml": "<x/>"}
        self.assertEqual(rw.add_to_pages(pages), 1)
        self.assertNotIn("rk-ad", pages["404.html"])

    def test_inline_script_text_does_not_confuse_the_block_finder(self):
        out = rw.add_widgets(page('<h1>t</h1><script>var a="</div><section>";</script><section><h2>x</h2></section><section><h2>y</h2></section>'))
        self.assertGreaterEqual(out.count('class="rk-ad"'), 1)


if __name__ == "__main__":
    unittest.main()
