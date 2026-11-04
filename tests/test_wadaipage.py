"""wadai reading edition: the checks A20-A24 (casual tone, figures, lumps of text, summaries, parts) with a negative case for each, and the HTML page (sokuhou/wadaipage.py).
The article here is a made-up fixture (no news, no mall data)."""
import copy
import re
import unittest

from sokuhou import wadaipage as pg
from sokuhou import wadaipost as w


def fixture():
    return {
        "format": "reading", "id": "t-1", "updated": "2026-11-04", "title": "停電の夜に、ひとつだけ出しておく物", "lead": "停電に備えて、灯りをひとつ出しておきましょう。置き場所を決めておくと、夜に探さずに済みます。",
        "tldr": ["灯りをひとつ出す。", "置き場所を決める。", "電池を確かめる。"],
        "reader_memo": {"reader": "a", "trouble": "b", "feel": "c", "action": "d"}, "ledger": [], "parties": [], "ads": True,
        "series": {"name": "手帖", "parent": "/a/", "children": [{"path": "/a/1/", "title": "場面別", "kind": "場面別"}, {"path": "/a/2/", "title": "チェック", "kind": "チェックリスト"}]},
        "hero": {"kind": "image", "src": "x.webp", "alt": "雨の夜の部屋の絵", "caption": "手の届く所に灯りを。"},
        "poll": {"id": "p1", "question": "いちばん困るのは?", "options": ["暗さ", "電池", "情報"]},
        "next": [{"path": "/b/", "title": "次の記事"}],
        "sections": [
            {"layer": "fact", "heading": "確認できた事実", "summary": "灯りは手の届く所に。", "bullets": ["気象庁は11月4日、台風が南の海上にあると発表しています。"],
             "figures": [{"kind": "chart", "type": "bar", "title": "例の棒グラフ", "desc": "三つの値の例。", "labels": ["a", "b", "c"], "values": [3, 5, 4], "caption": "気象庁(2026年)"}],
             "boxes": [{"kind": "tip", "title": "豆知識", "text": "灯りは、頭に付けると両手が空きます。"}]},
            {"layer": "opinion", "heading": "考察", "summary": "場面で選びます。", "paras": ["家で過ごすなら、手の届く所に置くのがよさそうです。"], "boxes": []},
            {"layer": "prep", "heading": "備え・選び方", "summary": "四つだけ見ます。", "paras": ["電池が合うかを見ましょう。"], "bullets": ["置き場所を決める"],
             "boxes": [{"kind": "hack", "title": "予備の電池", "text": "予備は、灯りと同じ袋に入れましょう。"}]},
            {"layer": "history", "heading": "更新履歴", "bullets": ["11月4日 追記: 作りました。"]}],
    }


def codes(findings):
    return {f.code for f in findings}


class TestReadingChecks(unittest.TestCase):
    def test_fixture_passes(self):
        self.assertEqual([f.line() for f in w.check_reading(fixture())], [])

    def test_a20_stiff_phrases_and_tone(self):
        for stiff in ("この対策が望ましい。", "と考えられます。", "が実施されるべきである。", "において確認する。", "することが可能です。", "留意が必要である。"):
            a = fixture()
            a["sections"][1]["paras"] = ["家で過ごすなら、手の届く所に置くのがよさそうです。" + stiff]
            self.assertIn("A20", codes(w.check_reading(a)), stiff)
        a = fixture()                                               # a plain-form (だ・である) text: the です・ます tone is the base
        a["lead"] = "灯りをひとつ出しておく。置き場所を決めておくと、夜に探さずに済む。"
        a["sections"][1]["paras"] = ["家で過ごすなら、手の届く所に置くのがいい。", "通勤なら小型で足りる。"]
        self.assertIn("A20", codes(w.check_reading(a)))

    def test_a21_figures(self):
        a = fixture()
        a["sections"][0]["figures"] = []
        self.assertIn("A21", codes(w.check_reading(a)))             # no chart / table
        a = fixture()
        a["hero"] = None
        self.assertIn("A21", codes(w.check_reading(a)))             # no illustration
        a = fixture()
        a["hero"]["alt"] = ""
        self.assertIn("A21", codes(w.check_reading(a)))             # no alt text
        a = fixture()
        del a["sections"][0]["figures"][0]["desc"]
        self.assertIn("A21", codes(w.check_reading(a)))             # a chart without a description

    def test_a22_lumps_of_text(self):
        a = fixture()
        a["sections"][1]["paras"] = ["あ" * 140 + "です。"]
        self.assertIn("A22", codes(w.check_reading(a)))
        a = fixture()
        a["sections"][1]["paras"] = ["一つ目です。", "二つ目です。", "三つ目です。", "四つ目です。"]       # four plain paragraphs in a row
        self.assertIn("A22", codes(w.check_reading(a)))
        a["sections"][1]["boxes"] = [{"kind": "tip", "title": "豆知識", "text": "間に箱を入れると読みやすい。"}]
        self.assertNotIn("A22", codes(w.check_reading(a)))

    def test_a23_summaries(self):
        a = fixture()
        a["tldr"] = ["一つ", "二つ"]
        self.assertIn("A23", codes(w.check_reading(a)))
        a = fixture()
        a["sections"][1]["summary"] = ""
        self.assertIn("A23", codes(w.check_reading(a)))
        a = fixture()
        a["tldr"][0] = "あ" * 61
        self.assertIn("A23", codes(w.check_reading(a)))

    def test_a24_parts(self):
        for mutate, why in ((lambda a: a["sections"][0].__setitem__("boxes", []), "no tip"), (lambda a: a["sections"][2].__setitem__("boxes", []), "no hack"),
                            (lambda a: a["series"].__setitem__("children", []), "no children"), (lambda a: a.__setitem__("next", []), "no next"),
                            (lambda a: a.__setitem__("poll", None), "no poll"), (lambda a: a["poll"].__setitem__("options", ["a", "b"]), "two choices"),
                            (lambda a: a["poll"].__setitem__("question", "お名前を教えてください"), "personal information")):
            a = fixture()
            mutate(a)
            self.assertIn("A24", codes(w.check_reading(a)), why)

    def test_check_article_runs_reading_checks_only_for_the_reading_format(self):
        a = fixture()
        a["tldr"] = []
        self.assertIn("A23", codes(w.check_article(a)))
        a["format"] = "classic"
        self.assertNotIn("A23", codes(w.check_article(a)))


class TestPage(unittest.TestCase):
    def setUp(self):
        self.html = pg.render_article(fixture(), path="/a/", base="https://example.invalid")

    def test_parts_are_on_the_page(self):
        for needle in ("3行でまとめ", "ひとことで", "豆知識", "ライフハック", 'id="poll"', 'id="copy"', 'id="fav"', "このシリーズの続き", "次に読む", "<svg", "このページの案内には広告が含まれます", "最終更新"):
            self.assertIn(needle, self.html, needle)
        self.assertIn('alt="雨の夜の部屋の絵"', self.html)
        self.assertRegex(self.html, r"<title[^>]*>例の棒グラフ</title>")

    def test_no_tracker_no_cookie_no_external_file_no_source_link(self):
        self.assertNotIn("document.cookie", self.html)
        self.assertNotRegex(self.html, r"<script[^>]+src=")
        self.assertNotRegex(self.html, r"<link[^>]+href=\"https?://")
        hrefs = re.findall(r'href="(https?://[^"]+)"', self.html)
        self.assertTrue(all(h.startswith(("https://twitter.com/intent/tweet", "https://line.me/R/msg/text/")) for h in hrefs), hrefs)   # only the two share buttons leave the site
        self.assertNotIn("localStorage.setItem(\"wadai:poll", self.html.replace(" ", "")[:0])

    def test_text_is_escaped(self):
        a = fixture()
        a["title"] = "<script>alert(1)</script>"
        a["sections"][1]["paras"] = ["a < b & c > d です。"]
        html = pg.render_article(a, path="/a/")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("a &lt; b &amp; c &gt; d", html)

    def test_ad_note_is_on_the_first_screen_and_only_when_there_are_ads(self):
        self.assertLess(self.html.index("広告が含まれます"), self.html.index("3行でまとめ"))
        a = fixture()
        a["ads"] = False
        self.assertNotIn("広告が含まれます", pg.render_article(a, path="/a/"))

    def test_dark_mode_and_mobile_basics(self):
        self.assertIn("prefers-color-scheme:dark", self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertIn("overflow-x:auto", self.html)                 # tables scroll inside their own box on a narrow screen

    def test_bar_axis_top_is_a_round_number(self):
        self.assertEqual(pg._nice_hi(1457), 1600)
        self.assertEqual(pg._nice_hi(36), 40)
        self.assertEqual(pg._nice_hi(5), 8)
        for v in (3, 36, 495, 1457, 99999):
            hi = pg._nice_hi(v)
            self.assertGreaterEqual(hi, v * 1.05)

    def test_a_partial_period_bar_is_drawn_hollow(self):
        svg = pg.chart_svg({"type": "bar", "title": "x", "desc": "d", "labels": ["a", "b", "c"], "values": [3, 5, 2], "partial": [2]})
        self.assertEqual(svg.count('class="bar partial"'), 1)
        self.assertEqual(svg.count('class="bar"'), 2)
        self.assertIn("stroke-dasharray", pg.CSS)

    def test_charts_have_title_and_description(self):
        self.assertIn('role="img"', self.html)
        self.assertRegex(self.html, r"<desc[^>]*>三つの値の例。</desc>")

    def test_the_position_chart_and_the_line_chart_draw(self):
        for fig in ({"type": "xy", "title": "位置", "desc": "d", "points": [{"x": 138.5, "y": 24.2, "label": "a"}, {"x": 150, "y": 37, "label": ""}], "marks": [{"x": 139.7, "y": 35.7, "label": "東京"}]},
                    {"type": "line", "title": "気圧", "desc": "d", "labels": ["a", "b", "c"], "values": [970, 975, 968], "unit": "hPa"}):
            svg = pg.chart_svg(fig)
            self.assertIn("<svg", svg)
            self.assertIn("<title", svg)
            self.assertNotIn("nan", svg.lower())
        with self.assertRaises(ValueError):
            pg.chart_svg({"type": "pie", "title": "x"})

    def test_child_page(self):
        page = {"title": "チェックリスト", "kind": "チェックリスト", "lead": "これだけ済ませましょう。", "blocks": [{"type": "check", "items": ["灯りを出した"]}, {"type": "qa", "items": [{"q": "Q1", "a": "A1"}]}], "next": []}
        html = pg.render_child(page, fixture()["series"], parent_title="親", path="/a/1/")
        self.assertIn("灯りを出した", html)
        self.assertIn("<details>", html)
        self.assertIn("親ページ", html)


if __name__ == "__main__":
    unittest.main()
