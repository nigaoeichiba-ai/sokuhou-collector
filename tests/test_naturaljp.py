"""sokuhou.naturaljp: the resident checker for Japanese that reads machine-made.

Negative tests: real-looking AI-style passages must be found (a check that cannot fail checks nothing); natural sentences must stay quiet (a checker that cries
wolf is switched off).  Every rule carries a `bad` example that it must catch and a `good` rewrite that it must not.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from sokuhou import naturaljp as nj


def ids(text: str, site=None, level="low", **kw) -> set[str]:
    return {h.rule for h in nj.check_text(text, site, min_level=level, **kw)}


def ids_html(html: str, site=None, path="page/index.html", level="low") -> set[str]:
    return {h.rule for h in nj.check_blocks(nj.blocks_from_html(html), path, site, min_level=level)}


# an AI-style blog passage, written the way the tools write it (stock opening, hedging, 三点列挙, closing)
AI_BLOG = """近年、ギフト市場への注目が高まっています。
本記事では、母の日の贈り物の選び方について詳しく解説します。
母の日の贈り物を選ぶ際には、相手の好みや予算を考慮することが重要です。さまざまな選択肢の中から、最適な一品を見つけることが大切です。
花、スイーツ、雑貨といった定番のギフトは、多くの方に喜ばれると言えるでしょう。
また、メッセージを添えることで、感謝の気持ちがより伝わるのではないでしょうか。
それでは、さっそく見ていきましょう。
いかがでしたでしょうか。この記事がお役に立てれば幸いです。"""

# natural, plain prose of the kind the sites should have (each line is quiet)
NATURAL = [
    "母の日は5月の第2日曜日です。2026年は5月10日になります。",
    "カーネーションは3,000円前後から選べます。花束が重ければ、鉢植えにすると持ち帰りやすくなります。",
    "賞味期限は製造から90日です。常温で保存できるので、遠方の相手にも送れます。",
    "令和8年度の全国加重平均は1,121円で、前年度より56円上がりました。",
    "のしは紅白の蝶結びを使います。表書きは「御中元」とします。",
    "冷蔵品は不在が続くと困るので、受け取れる日を先に聞いておきます。",
    "クマの目撃は、午前5時台と夕方に多く報告されています。",
    "イラストは無料で、商用にも使えます。クレジット表示は要りません。",
]


class AiTextIsFound(unittest.TestCase):
    def test_the_blog_passage_is_caught_by_the_stock_phrase_rules(self):
        got = ids(AI_BLOG)
        for rid in ("closing_ikaga", "closing_kouei", "lets_go", "intro_announce", "hedge_deshou", "opening_kinnen"):
            self.assertIn(rid, got, rid)

    def test_the_high_level_hits_are_the_stock_phrases(self):
        got = ids(AI_BLOG, level="high")
        self.assertTrue({"closing_ikaga", "lets_go", "hedge_deshou"} <= got, got)

    def test_stiff_nominal_style_and_academic_hedges(self):
        text = "この結果は需要が高まっていることを示唆しています。利用前に規約の確認が求められます。\nお客様がご覧になられた商品は、こちらでご確認いただけます。"
        got = ids(text)
        self.assertTrue({"academic_hedge", "expected_required", "double_keigo"} <= got, got)

    def test_markdown_and_emoji_left_in_the_page(self):
        self.assertIn("md_leftover", ids("**重要** なお知らせです。"))
        self.assertIn("emoji", ids("おすすめです✨ ぜひどうぞ。", level="mid"))
        self.assertIn("md_leftover", ids_html("<p>**重要**です。</p>"))

    def test_childish_tone_on_a_site_for_adults(self):
        self.assertIn("child_tone", ids("好きなイラストを見つけてね。", site="minna"))
        self.assertNotIn("child_tone", ids("好きなイラストを見つけてね。", site="atomou"))      # atomou's profile leaves it out
        self.assertNotIn("child_tone", ids("健康だよりや園だよりに使えます。", site="minna"))      # 「だより」 is not 「だよ」

    def test_a_flat_run_of_the_same_ending(self):
        self.assertIn("monotone_ending", ids("画像を保存できます。一覧を印刷できます。設定を変更できます。履歴を確認できます。"))
        self.assertNotIn("monotone_ending", ids("画像は保存でき、一覧は印刷もできます。設定を変えたいときは歯車を押します。履歴は下に出ます。"))

    def test_a_long_sentence_is_mid_and_a_very_long_one_is_high(self):
        mid = "楽天市場のランキングをもとにしながら、ジャンル別・世代別に売れている商品を毎日自動で更新して、贈る相手や予算に合わせて探せるようにしていて、さらに価格の変化もすぐ確かめられるようにしています。"
        long_ = mid[:-1] + "、さらに、各商品の価格や在庫の状況もできるだけ新しい状態に保ち、買う前に迷わないように、条件ごとの絞り込みや並べ替えにも対応して、使いやすさを高めています。"
        self.assertEqual({h.level for h in nj.check_text(mid, "yorokobu") if h.rule == "long_sentence"}, {"mid"})
        self.assertEqual({h.level for h in nj.check_text(long_, "yorokobu") if h.rule == "long_sentence"}, {"high"})

    def test_a_pet_verb_repeated_on_one_page(self):
        text = "\n".join(["時期と量を整えます。", "迷う相手には早めに手配すると整います。", "在宅できる日を聞くと整います。"])
        self.assertIn("pet_verb", ids(text))
        self.assertNotIn("pet_verb", ids("時期と量を整えます。"))                                   # once is fine

    def test_spaced_writing_is_split_into_words_with_spaces(self):
        self.assertIn("spaced_writing", ids("あと 何日 で 来るかを 調べる 日です。", site="atomou"))
        self.assertNotIn("spaced_writing", ids("慶應義塾大学 医学部 一般選抜は、2027年2月9日に実施されます。", site="atomou"))   # a proper name keeps its spaces

    def test_commas_after_short_phrases(self):
        got = nj.check_text("ダウンロードして、すぐに使えます。クレジット表示も、点数の制限も、ありません。", "minna")
        self.assertTrue(any(h.rule == "comma_particle" for h in got))
        self.assertEqual(nj.check_text("ダウンロードしてすぐに使えます。クレジット表示も点数の制限もありません。", "minna"), [])
        self.assertFalse(any(h.rule == "comma_particle" for h in nj.check_text("ダウンロードして、すぐに使えます。", "yorokobu")))   # commas.py is yorokobu's authority


class NaturalTextIsLeftAlone(unittest.TestCase):
    def test_natural_sentences_get_no_mid_or_high_hit(self):
        for line in NATURAL:
            for site in (None, "yorokobu", "minna", "atomou", "kuma", "saichin"):
                self.assertEqual(ids(line, site, level="mid"), set(), (site, line))

    def test_polite_prose_with_a_clause_comma_is_not_a_comma_problem(self):
        for line in ("環境省の公表にあわせて、自動で更新します。", "令和8年度は771件で、最新は10月16日の分です。", "端末の日付がずれていると、数字もずれます。",
                     "卒業、入学、退職、転職、引っ越しなどに使えます。", "のしは付けられますが、包装紙は使えません。"):
            self.assertNotIn("comma_particle", ids(line, "minna"), line)

    def test_a_list_of_prefectures_and_a_quoted_name_are_not_run_ons_or_noun_chains(self):
        pref = "福岡県・佐賀県・長崎県・熊本県・大分県・宮崎県・鹿児島県・沖縄県は、環境省の表に載っていないため、都道府県のページを置いていません。"
        self.assertNotIn("long_sentence", ids(pref, "kuma"))
        self.assertNotIn("noun_chain", ids("雇用保険の新給付「教育訓練休暇給付金」の創設は2025年10月1日(水)です。", "atomou"))

    def test_a_single_hedge_or_one_importance_word_is_not_reported(self):
        self.assertEqual(ids("商品によっては到着が遅れる場合があります。", level="mid"), set())          # a density rule needs several
        self.assertEqual(ids("期限の確認が大切です。", level="mid"), set())

    def test_legal_pages_are_exempt_from_the_style_rules(self):
        text = "お客様の個人情報は、利用目的の範囲内において取り扱うものとし、必要な範囲において第三者へ提供することができます。"
        self.assertIn("ni_oite", {h.rule for h in nj.check_text(text.replace("。", "。\n") * 2, None)})
        self.assertEqual(nj.check_text(text * 2, None, path="privacy/index.html"), [])

    def test_names_and_labels_without_a_full_stop_are_not_prose(self):
        html = "<ul><li>想いを伝える雑貨ギフト irodori ヤフー店</li><li>辻利 煎茶 三角ティーバッグ 2g×50P</li></ul>"
        self.assertEqual(ids_html(html, "yorokobu"), set())

    def test_the_rewritten_examples_are_clean_for_their_own_rule(self):
        for r in nj.R:
            if not r.good or r.good.startswith("(") or r.scope in ("heading", "page"):
                continue
            blocks = [nj.Block("para", r.good, 1, "txt")]
            self.assertNotIn(r.id, {h.rule for h in nj.check_blocks(blocks, "x.html", None)}, f"{r.id}: {r.good}")


class EveryRuleHasItsOwnExample(unittest.TestCase):
    def test_each_rule_explains_itself(self):
        for r in nj.R:
            self.assertTrue(r.why and r.fix and r.bad and r.good, r.id)
            self.assertIn(r.level, nj.LEVEL_RANK, r.id)

    def test_each_rules_bad_example_is_caught(self):
        for r in nj.R:
            if r.scope == "heading":
                blocks = [nj.Block("heading", r.bad.split(": ", 1)[-1], 1, "txt")]
            elif r.scope == "page":
                continue                                                                       # page-level rules have their own tests below
            else:
                reps = max(r.min_per_page, 6)
                if r.min_ratio:
                    reps = max(reps, 5)
                blocks = [nj.Block("para", r.bad, i + 1, "txt") for i in range(reps)]
            site = "minna" if r.id in ("hiragana_heavy",) else ("atomou" if r.id == "spaced_writing" else None)
            if r.id == "hiragana_heavy":
                blocks = [nj.Block("para", r.bad * 4, 1, "txt")]
            if r.id == "spaced_writing":
                blocks = [nj.Block("para", r.bad + "日です。", 1, "txt")]
            if r.id == "long_sentence":
                site = "yorokobu"
            got = {h.rule for h in nj.check_blocks(blocks, "x.html", site)}
            self.assertIn(r.id, got, f"{r.id} did not catch its own bad example: {r.bad}")

    def test_page_level_rules(self):
        heads = [nj.Block("heading", t, i + 1, "txt") for i, t in enumerate(["予算の選び方", "相手の選び方", "包装の選び方", "日付の選び方"])]
        self.assertIn("heading_template", {h.rule for h in nj.check_blocks(heads, "x.html", None)})
        self.assertNotIn("heading_template", {h.rule for h in nj.check_blocks(heads[:3], "x.html", None)})
        abstract = [nj.Block("para", f"負担にならない品を選びます{i}。", i + 1, "txt") for i in range(5)]
        self.assertIn("pet_abstract", {h.rule for h in nj.check_blocks(abstract, "x.html", None)})


class ReadingHtml(unittest.TestCase):
    def test_scripts_styles_and_menu_links_are_not_text_and_lines_are_kept(self):
        html = ("<html><head><title>テスト</title><meta name=\"description\" content=\"いかがでしたでしょうか。\"><style>.a{}</style></head><body>\n"
                "<nav><a href=\"/a\">運営者情報</a><a href=\"/b\">お問い合わせ</a></nav>\n"
                "<script>var x='いかがでしたか';</script>\n<p>本文です。</p>\n<p>最後までお読みいただきありがとうございました。</p></body></html>")
        blocks = nj.blocks_from_html(html)
        texts = [b.text for b in blocks]
        self.assertIn("運営者情報", texts)                                                          # the menu items are separate labels, not one run of nouns
        self.assertNotIn("運営者情報お問い合わせ", texts)
        self.assertFalse(any("var x" in t for t in texts))
        hits = nj.check_blocks(blocks, "p.html", None)
        lines = {h.rule: h.line for h in hits}
        self.assertIn("closing_ikaga", lines)                                                       # from the meta description
        self.assertTrue(any(h.line == 5 and h.rule == "closing_ikaga" for h in hits))                # the <p> on line 5

    def test_a_line_break_inside_japanese_text_is_not_a_space(self):
        blocks = nj.blocks_from_html("<p>あと\n何日\nで来る日です。あと\n何日\nで来る日です。</p>")
        self.assertEqual(blocks[0].text, "あと何日で来る日です。あと何日で来る日です。")

    def test_json_strings_are_read_with_their_line_and_ids_are_skipped(self):
        raw = '{\n "slug": "いかがでしたか",\n "title": "選び方",\n "lead": "いかがでしたでしょうか。"\n}\n'
        hits = nj.check_blocks(nj.blocks_from_json(raw), "a.json", None)
        self.assertEqual([(h.rule, h.line) for h in hits], [("closing_ikaga", 4)])


class ReportOnlyAndGate(unittest.TestCase):
    def test_the_gate_is_empty_so_nothing_can_stop_a_deploy_yet(self):
        for site in nj.SITES:
            self.assertEqual(nj.GATE[site], set(), site)

    def test_a_promoted_rule_makes_check_gate_fail_and_the_others_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "minna" / "page.html"
            f.parent.mkdir()
            f.write_text("<p>いかがでしたでしょうか。</p>", encoding="utf-8")
            old = nj.GATE["minna"]
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    self.assertEqual(nj.main(["check", str(f), "--site", "minna", "--gate"]), 0)           # report only
                    nj.GATE["minna"] = {"closing_ikaga"}
                    self.assertEqual(nj.main(["check", str(f), "--site", "minna", "--gate"]), 1)
                    nj.GATE["minna"] = {"lets_go"}
                    self.assertEqual(nj.main(["check", str(f), "--site", "minna", "--gate"]), 0)
                finally:
                    nj.GATE["minna"] = old

    def test_the_text_and_rules_commands_run(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(nj.main(["text", "いかがでしたでしょうか。", "-v"]), 0)
            self.assertEqual(nj.main(["rules", "--site", "yorokobu"]), 0)
        self.assertIn("closing_ikaga", out.getvalue())

    def test_summary_counts_a_repeated_sentence_once(self):
        hits = [nj.Hit(f"p{i}.html", 3, "closing_ikaga", "high", "いかがでしたか。") for i in range(5)]
        s = nj.summarize(hits)["closing_ikaga"]
        self.assertEqual((s["unique"], s["occurrences"]), (1, 5))


if __name__ == "__main__":
    unittest.main()
