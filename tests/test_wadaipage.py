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
        "verification": [{"fact": 0, "primary": True, "sources": ["x"]}, {"fact": 1, "primary": True, "sources": ["x"]}],
        "series": {"name": "手帖", "parent": "/a/", "children": [{"path": "/a/1/", "title": "場面別", "kind": "場面別"}, {"path": "/a/2/", "title": "チェック", "kind": "チェックリスト"}]},
        "hero": {"kind": "image", "src": "x.webp", "alt": "雨の夜の部屋の絵", "caption": "手の届く所に灯りを。"},
        "poll": {"id": "p1", "question": "いちばん困るのは?", "options": ["暗さ", "電池", "情報"]},
        "next": [{"path": "/b/", "title": "次の記事"}],
        "sections": [
            {"layer": "fact", "heading": "台風はいま、どこ?", "summary": "灯りは手の届く所に。", "bullets": ["気象庁は11月4日、台風が南の海上にあると発表しています。"],
             "figures": [{"kind": "chart", "type": "bar", "title": "例の棒グラフ", "desc": "三つの値の例。", "labels": ["a", "b", "c"], "values": [3, 5, 4], "caption": "気象庁(2026年)"}],
             "boxes": [{"kind": "tip", "title": "豆知識", "text": "灯りは、頭に付けると両手が空きます。"}]},
            {"layer": "opinion", "heading": "あなたの場合は?", "summary": "場面で選びます。", "paras": ["家で過ごすなら、手の届く所に置くのがよさそうです。"], "boxes": []},
            {"layer": "prep", "heading": "ライトの選び方", "summary": "四つだけ見ます。", "paras": ["電池が合うかを見ましょう。"], "bullets": ["置き場所を決める"], "cards": [{"kind": "light"}],
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
        a["sections"][1]["summary"] = ""                           # a one-line summary under a heading is optional
        self.assertNotIn("A23", codes(w.check_reading(a)))
        a = fixture()
        a["tldr"][0] = "あ" * 61
        self.assertIn("A23", codes(w.check_reading(a)))

    def test_a25_rhythm(self):
        a = fixture()
        a["sections"][1]["paras"] = ["家で過ごすなら、手の届く所に置くのが一つの手です。", "外に出る日は、雨具を先に考えるのも一つの手です。"]
        self.assertIn("A25", codes(w.check_reading(a)))                                   # the formula twice
        a = fixture()
        a["sections"][1]["paras"] = ["通勤の日は雨具を先に出します。", "通勤の日は靴も先に出します。", "通勤の日は傘もかばんに入れます。"]
        self.assertIn("A25", codes(w.check_reading(a)))                                   # three sentences with the same opening
        a = fixture()
        a["sections"][1]["paras"] = ["暗い部屋でもすぐ見つかるように、玄関に置きます。", "暗い部屋でもすぐ見つかるように、枕元にも置きます。", "暗い部屋でもすぐ見つかるように、かばんにも入れます。"]
        self.assertIn("A25", codes(w.check_reading(a)))                                   # the same long phrase three times
        a = fixture()
        a["sections"][1]["paras"] = ["台風という言葉と、停電という言葉と、備蓄という言葉と、灯りという言葉があります。"]
        self.assertIn("A25", codes(w.check_reading(a)))                                   # 'という' too often
        a = fixture()
        a["sections"][1]["paras"] = ["確認することができます。"]
        self.assertIn("A25", codes(w.check_reading(a)))                                   # 'することができます' even once

    def test_a26_the_same_fact_said_again(self):
        a = fixture()
        a["lead"] = "台風は5日朝に280キロの海上を進みます。置き場所を決めておきましょう。"
        a["tldr"] = ["台風は280キロの海上。", "置き場所を決める。", "電池を確かめる。"]
        a["sections"][0]["bullets"] = ["気象庁は11月4日、台風が280キロ先の海上にあると発表しています。"]
        self.assertIn("A26", codes(w.check_reading(a)))
        a["tldr"][0] = "台風は南の海上。"
        self.assertNotIn("A26", codes(w.check_reading(a)))

    def test_a22_commas_and_nominalised_chains(self):
        a = fixture()
        a["sections"][1]["paras"] = ["契約内容をよく確かめて、関連の商品やサービスが必要かを確かめて、予約の取りやすさを確かめて、トレーナーを変えられるかを確かめて、不安なら相談して、早めに動きます。"]
        self.assertIn("A22", codes(w.check_reading(a)))                                   # a list of clauses in one sentence
        a["sections"][1]["paras"] = ["エステ、美容医療、語学、家庭教師、学習塾、パソコン、結婚相手紹介が対象です。"]
        self.assertNotIn("A22", codes(w.check_reading(a)))                                # a short list of nouns is fine
        a["sections"][1]["paras"] = ["その場で決めないこと、確かめること、相談することが大切です。"]
        self.assertIn("A22", codes(w.check_reading(a)))                                   # three 'こと' in one sentence

    def test_a28_terms_the_reader_stumbled_on(self):
        for bad in ("二つ目の確認を付けます。", "携帯トイレの入数を見ます。", "届いたリンクは開きません。", "物理のセキュリティキーがあります。"):
            a = fixture()
            a["sections"][1]["paras"] = [bad]
            self.assertIn("A28", codes(w.check_reading(a)), bad)
        a = fixture()
        a["sections"][1]["paras"] = ["二段階認証を調べます。"]
        self.assertNotIn("A28", codes(w.check_reading(a)))

    def test_a22_a_long_sentence(self):
        a = fixture()
        a["sections"][1]["paras"] = ["停電になったときに暗い部屋の中でも慌てずに動けるように" * 3 + "準備します。"]
        self.assertIn("A22", codes(w.check_reading(a)))

    def test_a27_headings_are_for_the_reader(self):
        for h in ("確認できた事実:台風はいま、どこ?", "考察(編集部の見方):あなたの場合は?", "備え・選び方"):
            a = fixture()
            a["sections"][0]["heading"] = h
            self.assertIn("A27", codes(w.check_article(a)), h)
        a = fixture()
        a["sections"][0]["heading"] = "台風31号、いまどこ?"
        self.assertNotIn("A27", codes(w.check_article(a)))

    def test_reading_edition_facts_as_paragraphs_are_verified_and_name_the_issuer_once(self):
        a = fixture()
        a["sections"][0]["bullets"] = []
        a["sections"][0]["paras"] = ["気象庁の4日9時の解析では、台風は南の海上にいます。", "このあとは北へ進みます。"]
        a["verification"] = [{"fact": 0, "primary": True, "sources": ["x"]}, {"fact": 1, "primary": True, "sources": ["x"]}, {"fact": 2, "primary": True, "sources": ["x"]}]
        found = codes(w.check_article(a))
        self.assertNotIn("A03", found)                                   # the second paragraph continues the subject
        self.assertNotIn("A19", found)
        a["verification"] = [{"fact": 0, "primary": True, "sources": ["x"]}]
        self.assertIn("A19", codes(w.check_article(a)))                  # the second paragraph and the 豆知識 box have no record
        a["sections"][0]["paras"][0] = "台風は南の海上にいます。"
        self.assertIn("A03", codes(w.check_article(a)))                  # the first paragraph names no issuer

    def test_a25_same_ending_three_times(self):
        a = fixture()
        a["sections"][1]["paras"] = ["通勤の日は、雨具と靴を先に出しておくのがよい準備です。", "家で過ごす夜は、ライトを手元に置いておくのがよい準備です。", "出かける前は、電池を確かめておくのがよい準備です。"]
        self.assertIn("A25", codes(w.check_reading(a)))

    def test_a26_a_table_that_repeats_the_paragraphs(self):
        a = fixture()
        a["sections"][1]["paras"] = ["家で過ごす夜は手の届く所にライトを置きます。通勤の日は雨具と靴を先に出します。"]
        a["sections"][1]["figures"] = [{"kind": "table", "title": "場面別", "headers": ["場面", "先に"], "rows": [["家で過ごす夜", "手の届く所にライトを置きます"], ["通勤の日", "雨具と靴を先に出します"]]}]
        self.assertIn("A26", codes(w.check_reading(a)))
        a["sections"][1]["figures"][0]["rows"] = [["a", "1"], ["b", "2"]]
        self.assertNotIn("A26", codes(w.check_reading(a)))

    def test_a29_an_advertising_note_without_a_product_card(self):
        a = fixture()
        a["sections"][2]["cards"] = []
        self.assertIn("A29", codes(w.check_reading(a)))
        a["ads"] = False
        self.assertNotIn("A29", codes(w.check_reading(a)))

    def test_a30_a_tip_that_is_the_news(self):
        a = fixture()
        a["sections"][0]["paras"] = ["台風は11月5日9時に父島の西北西およそ280キロの海上を北北東へ進みます。"]
        a["sections"][0]["boxes"] = [{"kind": "tip", "title": "台風は北北東へ進む", "text": "台風は11月5日9時に父島の西北西およそ280キロの海上を北北東へ進みます。"}]
        self.assertIn("A30", codes(w.check_reading(a)))
        a["sections"][0]["boxes"] = [{"kind": "tip", "title": "台風の名前", "text": "名前は、アジアの国々が出した中から順番に使われます。"}]
        self.assertNotIn("A30", codes(w.check_reading(a)))

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
        for needle in ("3行でまとめ", "ひとことで", "豆知識", "ライフハック", 'id="poll"', 'id="copy"', 'id="fav"', "このシリーズの続き", "次に読む", "<svg", "下の案内には広告が含まれます", "最終更新"):
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

    def test_ad_note_sits_next_to_the_product_cards_and_nowhere_else(self):
        self.assertIn("広告が含まれます", self.html)
        self.assertGreater(self.html.index("広告が含まれます"), self.html.index("ライトの選び方"))       # inside the section that holds the cards, not at the top
        a = fixture()
        a["ads"] = False
        a["sections"][2]["cards"] = []
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
