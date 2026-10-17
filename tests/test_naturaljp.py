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

    def test_a_run_of_links_or_names_is_not_a_long_sentence(self):
        toc = "自治体の目撃情報の一覧 / 地図で見る(現在地の近く) / 週ごとのまとめ / データ(CSV) / 市町村名から探す / 都道府県の公式の出没情報(リンク集) / データの出典・引用のしかた"
        self.assertGreater(nj.prose_length(toc), nj.profile("kuma")["long"])                      # long enough to be caught if it were a sentence
        self.assertNotIn("long_sentence", ids(toc, "kuma"))
        self.assertNotIn("long_sentence", ids_html(f"<div>{toc}</div>", "kuma"))
        links = "".join(f'<a href="/{i}/">{t}</a> / ' for i, t in enumerate(toc.split(" / ")))[:-3]
        self.assertNotIn("long_sentence", ids_html(f"<div>{links}</div>", "kuma"))                 # the same as real links
        for sep in (" | ", " ／ ".replace("／", "/"), "・"):
            self.assertNotIn("long_sentence", ids(sep.join(["自治体の目撃情報の一覧", "地図で見る(現在地の近く)", "週ごとのまとめ", "データ(CSV)", "市町村名から探す", "都道府県の公式の出没情報", "データの出典と引用のしかた"]), "kuma"))
        log = "2026年10月15日: 令和8年度の47都道府県の最低賃金・前年度の額・引上げ額・発効日を、厚生労働省「令和8年度地域別最低賃金全国一覧」(PDF)と照合。"
        self.assertNotIn("long_sentence", ids(log, "saichin"))                                    # a log entry: the date prefix and a quoted title are not text
        events = "1月3日にある日付: 第79回ライスボウル(アメフト日本選手権)、筥崎宮 玉取祭(玉せせり) 2026、ハリウッド・フェスティバル・オーケストラ ニューイヤーコンサート2027 大阪など4件。"
        self.assertNotIn("long_sentence", ids(events, "atomou"))                                  # a list after a label

    def test_a_real_long_sentence_is_still_found_next_to_the_exemptions(self):
        real = "最低賃金制度は、最低賃金法にもとづき、国が賃金の最低額を定め、使用者は、その最低賃金額以上の賃金を労働者に支払わなければならないとする制度であり、違反した使用者には罰則が定められています。"
        self.assertIn("long_sentence", ids(real, "saichin"))
        self.assertIn("long_sentence", ids("自治体の一覧 / 地図 / まとめ。" + real, "saichin"))        # a link run elsewhere in the block does not hide it
        quoted = "厚生労働省の「令和8年度地域別最低賃金全国一覧」を見ると、前年度より多くの県で引上げ額が大きくなっていて、全国の加重平均も初めて千円を超えたことが分かるうえ、発効日も県ごとに違います。"
        self.assertIn("long_sentence", ids(quoted, "saichin"))

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
            if r.scope in ("heading", "headlike"):
                blocks = [nj.Block("heading", r.bad.split(": ", 1)[-1], i + 1, "txt") for i in range(max(r.min_per_page, 1))]
            elif r.scope in ("page", "site"):
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

    def test_a_title_and_its_body_in_one_item_are_two_texts(self):
        html = "<ul><li><b>入力は端末の中だけ</b><span>名前も文面もブラウザの中だけで処理します。</span></li><li><b>A4で印刷</b><span>カレンダー、名札、賞状はA4で印刷できる大きさで作れます。</span></li></ul>"
        texts = [b.text for b in nj.blocks_from_html(html)]
        self.assertEqual(texts, ["入力は端末の中だけ", "名前も文面もブラウザの中だけで処理します。", "A4で印刷", "カレンダー、名札、賞状はA4で印刷できる大きさで作れます。"])
        self.assertEqual(ids_html(html, "minna"), set())                                         # no phantom comma or repeated word across the join
        self.assertEqual([b.text for b in nj.blocks_from_html("<p>これは<b>大事な</b>話です。</p>")], ["これは大事な話です。"])      # an emphasis inside a sentence stays in it

    def test_a_long_quoted_example_is_not_judged_as_the_writers_own_prose(self):
        text = "親しい人には「楽しいクリスマスになりますように」「寒い日が続きますので、あたたかくお過ごしください」「またゆっくり会える日を楽しみにしています」などが使いやすいです。"
        self.assertEqual(ids(text, "minna", level="mid"), set())
        letter = "「生活の形が少し変わりましたため、来年より年賀状でのご挨拶を失礼させていただくことにいたしました。」"
        self.assertNotIn("sasete_itadaku", ids(letter + chr(10) + letter, "minna"))
        self.assertEqual(ids_html("<blockquote><p>おかげさまで、今年もたのしくすごせました。ありがとうございます。させていただきます。させていただきます。</p></blockquote>", "minna"), set())
        # the writer's own sentence next to a quote is still judged
        self.assertIn("hedge_deshou", ids("「楽しいクリスマスになりますように」と書くのがよいと言えるでしょう。", "minna"))
        self.assertIn("md_leftover", ids_html("<blockquote>**重要**です。</blockquote>"))                  # a leftover mark is a leftover anywhere

    def test_an_official_name_leading_a_dated_sentence_is_not_style(self):
        names = ["STPR Family Festival!! 2026 東京ドーム公演", "一番くじ すみっコぐらし 発売", "岩手県東日本大震災津波追悼式", "ゲーム『シナモロール ～わくわくカフェライフだもん！』サービス終了",
                 "第7回 かがよふあかり 竹灯籠", "Hey! Say! JUMP アルバム『Juliet』発売", "第40回臨床工学技士国家試験 合格発表"]
        for site in ("atomou", "kuma"):
            for name in names:
                for tail in ("は2026年11月3日(火)、東京都。", "は、2026年11月3日(火)です。2026年10月17日の時点で、あと17日です。"):
                    self.assertEqual(ids(name + tail, site), set(), (site, name, tail))
                    self.assertEqual(ids_html(f"<p>{name}{tail}</p>", site), set(), (site, name, tail))

    def test_the_same_shapes_in_the_writers_own_prose_are_still_found(self):
        self.assertIn("noun_chain", ids("岩手県東日本大震災津波追悼式実施要項改定状況確認作業を毎年ここにまとめています。", "atomou"))
        self.assertIn("spaced_writing", ids("あと 何日 で 来るかを 数えて 予定に 入れる 日です。", "atomou"))
        self.assertIn("exclaim", ids("予定を入れられます。便利です！今すぐ使えます！", "atomou"))
        self.assertIn("flowery", ids("わくわくする毎日を、そっと支えます。", "atomou"))
        self.assertEqual(ids("正式名称は全日本大学女子駅伝対校選手権大会です。", "atomou"), set())             # stating an official name
        # the name is masked, the rest of the sentence is still judged

        self.assertIn("hedge_deshou", ids("ハイキュー!!展 挑戦者たちは2026年10月30日に開幕し、混み合うと言えるでしょう。", "atomou"))
        self.assertIn("pet_verb", ids(chr(10).join(["時期と量を整えます。", "迷う相手には早めに手配すると整います。", "在宅できる日を聞くと整います。"]), "atomou"))

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
