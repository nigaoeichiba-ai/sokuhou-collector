"""文章工房 (sokuhou/kobo): the writer's Markdown, the machine checks (a negative case for each), the material rules, and the write -> check ->
reader-gate loop with a fake model backend (no model is called in a test).  The texts here are made up (no news, no mall data)."""
import json
import re
import unittest

from sokuhou.kobo import calibrate, checks, doc, engine, material, runner

MAT = {
    "id": "t-light", "site": "wadai", "weight": "mid", "topic": "停電の夜のライト", "date": "2026-11-04",
    "reader_memo": {"reader": "停電が気になる人", "trouble": "何を出せばいいか分からない", "feel": "ひとつでいいと感じる", "action": "ライトを出す"},
    "facts": [{"text": "市は11月4日、夜に停電の点検があると発表しました。点検は2時間です。", "status": "primary"}],
    "advice": ["ライトを手の届く所に出す", "出したら点けてみる", "電池はライトのそばに入れておく"],
    "tips": [{"title": "電池の向き", "text": "乾電池の出っ張っている側がプラスです。", "status": "primary"}],
    "names": [], "direction": [], "slot": "", "history": "",
}
CARD = engine.load_card("wadai")

GOOD = """# 停電の夜に、ライトをひとつ出しておこう

停電が気になるなら、ライトをひとつ、手の届く所に出しておけば大丈夫です。暗い中で探さずにすみます。

## 3行まとめ
- ライトをひとつ、手の届く所に
- 点検は2時間
- 電池はライトのそばへ

## 点検は、いつ?
市は11月4日、夜に停電の点検があると発表しました。点検は2時間です。

## 何を出せばいい?
ライトをひとつ出して、一度点けてみてください。電池は、ライトのそばに入れておくと探さずにすみます。

> ライフハック: 出したら点ける
> 出したついでにスイッチを入れて、点くか見ておきます。

> 豆知識: 電池の向き
> 乾電池の出っ張っている側がプラスです。
"""


def codes(md, m=MAT, card=CARD):
    return [f.code for f in checks.blocking(checks.check(doc.parse(md), m, card))]


class Parse(unittest.TestCase):
    def test_parts(self):
        d = doc.parse(GOOD)
        self.assertEqual(d["title"], "停電の夜に、ライトをひとつ出しておこう")
        self.assertEqual(len(doc.sentences(d["lead"])), 2)
        self.assertEqual(len(d["tldr"]), 3)
        self.assertEqual([s["heading"] for s in d["sections"]], ["点検は、いつ?", "何を出せばいい?"])
        boxes = d["sections"][1]["boxes"]
        self.assertEqual([b["kind"] for b in boxes], ["hack", "tip"])
        self.assertIn("プラス", boxes[1]["text"])
        self.assertNotIn("3行まとめ", doc.plain(d).split("【3行まとめ】")[0])

    def test_the_reader_sees_the_fixed_parts_in_place(self):
        md = GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "下の表で、家の人数の行を見てください。\n\n[表: 人数別]\n\nそのあとライトを出します。\n\n[商品カード]")
        txt = doc.plain(doc.parse(md), [{"mark": "[表: 人数別]", "content": "| 1人 | 3L |"}])
        self.assertLess(txt.index("下の表で"), txt.index("[表: 人数別]"))
        self.assertLess(txt.index("| 1人 | 3L |"), txt.index("そのあとライトを出します"))
        self.assertIn("(ここに商品の一覧が入ります)", txt)

    def test_edits_change_only_the_named_sentences(self):
        from sokuhou.kobo import engine
        out, n = engine.apply_edits(GOOD, [{"old": "点検は2時間です。", "new": "点検には2時間かかります。"},
                                           {"old": "本文にない文。", "new": "x"}, "junk"])
        self.assertEqual(n, 1)
        self.assertEqual(out, GOOD.replace("点検は2時間です。", "点検には2時間かかります。"))
        self.assertEqual(engine.apply_edits(GOOD, None), (GOOD, 0))

    def test_a_rewrite_that_drops_the_summary_gets_it_back(self):
        from sokuhou.kobo import engine
        lost = re.sub(r"## 3行まとめ\n(?:- .*\n)+\n?", "", GOOD)
        self.assertFalse(doc.parse(lost)["tldr"])
        back = engine._keep_shape(lost, GOOD, "article")
        self.assertEqual(doc.parse(back)["tldr"], doc.parse(GOOD)["tldr"])
        self.assertEqual(engine._keep_shape(GOOD, GOOD, "article"), GOOD)

    def test_a_part_without_content_is_shown_by_what_it_is(self):
        md = GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "続きは次のページで。\n\n[子ページの案内]\n\n")
        txt = doc.plain(doc.parse(md), [{"mark": "[子ページの案内]", "what": "体験の前 / 質問と答え", "content": ""}])
        self.assertNotIn("[子ページの案内]", txt)
        self.assertIn("【くわしく読む】\n・体験の前\n・質問と答え", txt)
        self.assertNotIn("ここに入る", txt)
        judge = doc.plain(doc.parse(md), [{"mark": "[子ページの案内]", "what": "体験の前 / 質問と答え", "content": ""}], describe_empty=False)
        self.assertIn("[子ページの案内]", judge)

    def test_round_trip(self):
        d = doc.parse(GOOD)
        self.assertEqual(doc.parse(doc.to_markdown(d))["sections"], d["sections"])

    def test_wadai_shape(self):
        a = doc.to_wadai(doc.parse(GOOD), MAT)
        self.assertEqual(a["format"], "reading")
        self.assertEqual(a["sections"][0]["layer"], "fact")
        self.assertEqual(a["sections"][-1]["layer"], "prep")


class Checks(unittest.TestCase):
    def test_good_text_has_no_blocking_finding(self):
        self.assertEqual(codes(GOOD), [])

    def test_hedge_formula(self):
        once = GOOD.replace("出しておけば大丈夫です", "出しておくのが一つの手です")
        self.assertNotIn("K01", codes(once))           # once: a note
        self.assertIn("K01", codes(once.replace("一度点けてみてください", "一度点けてみるのも手です")))

    def test_summary_then_detail_is_not_a_repeat(self):
        md = GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "見る点は、両手があくか、電池が合うか、置き場所を家族が知っているかです。ふたつめは、電池が合うか。")
        self.assertNotIn("K02", codes(md))

    def test_same_opening_three_times(self):
        md = GOOD.replace("市は11月4日、夜に停電の点検があると発表しました。点検は2時間です。",
                          "市の発表では、夜に停電の点検があります。市の発表では、点検は2時間です。市の発表では、11月4日の発表です。")
        self.assertIn("K01", codes(md))

    def test_same_ending_three_times(self):
        md = GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "ライトを出しておきましょう。点けておきましょう。電池も入れておきましょう。")
        self.assertIn("K01", codes(md))

    def test_three_alike_spread_over_a_long_text_are_a_note(self):
        self.assertFalse(checks._close([(0, "a"), (12, "b"), (30, "c")]))
        self.assertTrue(checks._close([(0, "a"), (2, "b"), (4, "c")]))
        self.assertTrue(checks._close([(0, "a"), (12, "b"), (30, "c"), (45, "d")]))

    def test_number_not_in_material(self):
        self.assertIn("K03", codes(GOOD.replace("点検は2時間です。", "点検は3時間です。")))

    def test_name_not_in_material(self):
        self.assertIn("K04", codes(GOOD.replace("市は11月4日", "東都電力株式会社は11月4日")))

    def test_label_heading(self):
        self.assertIn("K06", codes(GOOD.replace("## 点検は、いつ?", "## 確認できた事実:点検は、いつ?")))
        self.assertIn("K06", codes(GOOD.replace("## 何を出せばいい?", "## まとめ")))

    def test_advertising_note_in_text(self):
        self.assertIn("K07", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます(このページは広告を含みます)。")))

    def test_tip_without_a_confirmed_story(self):
        self.assertIn("K08", codes(GOOD, dict(MAT, tips=[])))

    def test_tip_that_is_the_news(self):
        md = GOOD.replace("> 豆知識: 電池の向き\n> 乾電池の出っ張っている側がプラスです。", "> 豆知識: 点検の時間\n> 市は11月4日、夜に停電の点検があると発表しました。")
        self.assertIn("K08", codes(md))

    def test_source_talk_and_not_known(self):
        self.assertIn("K09", codes(GOOD.replace("点検は2時間です。", "点検は2時間と報じられています。")))
        self.assertIn("K09", codes(GOOD.replace("点検は2時間です。", "点検の場所は分かっていません。")))

    def test_telling_someone_is_not_source_talk(self):
        self.assertNotIn("K09", codes(GOOD.replace("一度点けてみてください。", "家族にも、置き場所を伝えてください。")))
        self.assertIn("K09", codes(GOOD.replace("点検は2時間です。", "点検は2時間だと伝えています。")))

    def test_same_thing_twice(self):
        md = GOOD.replace("> 出したついでにスイッチを入れて、点くか見ておきます。", "> 市は11月4日、夜に停電の点検があると発表しました。")
        self.assertIn("K02", codes(md))

    def test_table_repeating_a_paragraph(self):
        md = GOOD.replace("## 何を出せばいい?", "| 市は11月4日 | 夜に停電の点検があると発表しました |\n\n## 何を出せばいい?")
        self.assertIn("K02", codes(md))

    def test_situation_from_another_story(self):
        md = GOOD.replace("> 出したついでにスイッチを入れて、点くか見ておきます。", "> 台風で停電したときのために、点くか見ておきます。")
        self.assertIn("K12", codes(md))
        self.assertNotIn("K12", codes(GOOD))      # 停電 is in this material's facts
        # a situation in the material's own confirmed 豆知識 is not a mix-in
        tip = dict(MAT["tips"][0], text=MAT["tips"][0]["text"] + "台風のときも同じです。")
        self.assertNotIn("K12", codes(md, dict(MAT, tips=[tip])))

    def test_the_word_advert_in_a_sentence_is_not_an_ad_note(self):
        self.assertNotIn("K07", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。広告やチラシも取っておきます。")))
        self.assertIn("K07", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。【PR】")))

    def test_lead_of_three_sentences(self):
        self.assertNotIn("K10", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。電池も見ます。")))   # 3 sentences: fine
        self.assertIn("K10", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。電池も見ます。点けます。消します。")))

    def test_long_sentence(self):
        self.assertIn("K10", codes(GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "ライトをひとつ出して" + "、手の届く所に置いて" * 12 + "、一度点けてみてください。")))


class Material(unittest.TestCase):
    def test_unconfirmed_fact_and_tip(self):
        m = dict(MAT, facts=[{"text": "x", "status": "single"}], tips=[{"title": "a", "text": "b", "status": "single"}])
        p = material.validate(m)
        self.assertTrue(any("fact 0" in x for x in p) and any("tip 0" in x for x in p))
        self.assertEqual(material.validate(MAT), [])

    def test_memo_is_required(self):
        self.assertTrue(material.validate(dict(MAT, reader_memo={"reader": "a"})))

    def test_from_wadai_drops_a_tip_with_one_source(self):
        a = {"id": "x", "reader_memo": MAT["reader_memo"], "sections": [
            {"layer": "fact", "paras": ["市は発表しました。"]}, {"layer": "prep", "boxes": [{"kind": "tip", "title": "t", "text": "u"}]}],
            "verification": [{"fact": 0, "primary": True, "sources": ["s"]}, {"fact": 1, "sources": ["one"]}]}
        m = material.from_wadai(a, "mid", "x")
        self.assertEqual(m["tips"], [])
        self.assertEqual(len(m["dropped_tips"]), 1)
        self.assertEqual(m["facts"][0]["status"], "primary")

    def test_prompt_hides_the_confirmation_notes(self):
        m = dict(MAT, facts=[{"text": "市は発表しました。", "status": "primary", "note": "PRIVATE-NOTE"}])
        self.assertNotIn("PRIVATE-NOTE", material.for_prompt(m))
        self.assertIn("なし。豆知識の囲みは作らない", material.for_prompt(dict(MAT, tips=[])))


class FakeModels:
    """writer answers from a list; the reader marks the first `reader_marks` reads; the judge finds nothing."""

    def __init__(self, drafts, reader_marks=1):
        self.drafts, self.reader_marks, self.calls = list(drafts), reader_marks, []

    def __call__(self, model, prompt, system=None):
        self.calls.append((model, prompt[:30]))
        if "事実確認係" in prompt:
            return json.dumps({"unsupported": []})
        if "読み終えたところ" in prompt:            # the remaining-questions pass: nothing left
            return json.dumps({"left": []})
        if "意地悪で細かい" in prompt:              # the 突っ込み役 passes the text through unchanged (no point)
            body = prompt.split("----- 原稿 -----\n", 1)[1].rsplit("\n----- ここまで -----", 1)[0]
            return "===突っ込み===\n" + json.dumps({"points": []}) + "\n===直した全文===\n" + body
        if "ふつうの会社員" in prompt:
            self.reader_marks -= 1
            if self.reader_marks >= 0:
                return json.dumps({"marks": [{"text": "大丈夫です", "level": 3, "why": "意味が取れない", "fix": "x"}], "impression": ""})
            return json.dumps({"marks": [{"text": "x", "level": 1, "why": "好み", "fix": ""}], "impression": "自然"})
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


class Light(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_one_writer_call_one_tsukkomi_call_no_judges(self):
        fake = FakeModels([GOOD.replace("点検は2時間です。", "点検は3時間です。")])
        runner.set_backend(fake)
        r = engine.light("article", MAT, CARD, writer="opus", tsukkomi_model="haiku", record=False)
        names = [m for m, _ in fake.calls]
        self.assertEqual(names[0], "opus")
        self.assertIn("haiku", names)                                     # the 突っ込み役 ran; no reader gate, no judge, no rounds
        self.assertNotIn("fable", [m for m, _ in fake.calls])
        self.assertIn("3時間", r["output"])                                         # nothing passes or stops: the text is output
        self.assertIn("K03", [x["code"] for x in r["marks"]])                      # the number not in the material is marked for a person
        self.assertIn("total", r["seconds"])

    def test_personas_read_in_parallel_and_shared_points_come_first(self):
        calls = []

        def fake(model, prompt, system=None):
            calls.append(model)
            if "何人かの読者が読んで" in prompt:          # the one fix: sentence replacements
                return json.dumps({"edits": [{"old": "点検は2時間です。", "new": "停電の点検は2時間です。"}]})
            if "次の人になって" in prompt:
                pts = [{"text": "点検は2時間です。", "ask": "何の点検?", "fix": "停電の点検"}]
                if "疑い深い" in prompt:
                    pts.append({"text": "市は11月4日", "ask": "出典を書いて", "fix": "URLを書く"})     # dropped: the owner's rule
                if "斜め読み" in prompt:
                    pts.append({"text": "ライトをひとつ", "ask": "どの?", "fix": "x"})
                return json.dumps({"gist": "停電の点検の話", "points": pts})
            return GOOD
        runner.set_backend(fake)
        r = engine.light("article", dict(MAT, deep_readers=True), CARD, writer="opus", record=False)
        self.assertEqual(calls.count("haiku"), 7)                      # 4 readers + the haiku proofreader + the fix + the named-word check
        self.assertEqual(calls.count("codex"), 2)                      # the Codex proofreader + the named-word check
        self.assertIn("停電の点検は2時間です", r["output"])
        top = r["tsukkomi_points"][0]
        self.assertEqual(len(top["by"]), 7)                             # the point every reader made comes first
        self.assertFalse(any("出典" in a for p in r["tsukkomi_points"] for a in p["asks"]))
        self.assertEqual(len(r["readers"]), 7)      # 4 readers + 3 proofreaders (haiku, sonnet, Codex)

    def test_an_explanation_added_by_the_tsukkomi_is_marked(self):
        final = GOOD.replace("点検は2時間です。", "点検(電気を止めて設備を調べる作業)は2時間です。")
        ms = engine.added_explanations(GOOD, final, MAT)
        self.assertEqual([x["code"] for x in ms], ["TK"])
        self.assertEqual(engine.added_explanations(GOOD, GOOD, MAT), [])

    def test_wording_and_heading_rules(self):
        from sokuhou.kobo import style_rules as SR
        md = GOOD.replace("# ", "# 防災グッズを数えてみよう ", 1).replace("## 点検は、いつ?", "## 備えは足りている? 人数に合わせて数える").replace(
            "暗い中で探さずにすみます。", "暗い中で探さずにすみます。表に数字を並べると分かります。この記事は水を扱います。答えてみてください。")
        codes_ = [x["code"] for x in SR.check(doc.parse(md))]
        for c in ("S05", "S06", "S01", "S03", "S04"):
            self.assertIn(c, codes_, c)
        self.assertEqual([x for x in SR.check(doc.parse(GOOD)) if x["code"] in ("S01", "S03", "S05", "S06", "S07")], [])
        # a range that does not match the count, an unclear table intro, a list of nouns standing as a sentence
        md2 = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。いま、そろっている数(0〜7)を答えてください。8つの種類があります。一人暮らしの人は1人の行を見てください。エステ、語学教室、学習塾、家庭教師。")
        c2 = [x["code"] for x in SR.check(doc.parse(md2))]
        for c in ("S10", "S11", "S08"):
            self.assertIn(c, c2, c)

    def test_parts_are_computed_from_confirmed_rates(self):
        from sokuhou.kobo import parts
        t = parts.quick_table([{"head": "水 3日分", "rate": 3, "days": 3, "unit": "リットル"}, {"head": "水 7日分", "rate": 3, "days": 7, "unit": "リットル"}])
        self.assertIn("| 1人 | 9リットル | 21リットル |", t)
        self.assertIn("| 4人 | 36リットル | 84リットル |", t)            # the numbers the desk's table has
        self.assertEqual(parts.table_intro(1, 5, ["水", "食料", "携帯トイレ"]),
                         "早見表は、1人から5人までの人数別です。自分の家の人数の行を見ると、水、食料、携帯トイレの目安が分かります。")
        from sokuhou.kobo import style_rules
        intro = parts.table_intro(1, 5, ["水"])
        d = doc.parse("# t\n\n" + intro + "\n\n## a\n" + intro)
        self.assertEqual([x for x in style_rules.check(d) if x['code'] in ('S11', 'S12')], [])    # the template trips none of the table-intro rules
        h = parts.calculator_html([{"name": "水", "rate": 3, "unit": "リットル"}])
        self.assertIn('data-rate="3"', h)
        self.assertNotIn("src=", h)                                      # no external script

    def test_place_words_and_counting_things(self):
        from sokuhou.kobo import style_rules
        md = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。足りない所を見つけてみませんか。足りなかったら、どこから買いますか。8つの種類を数えます。")
        c = [x["code"] for x in style_rules.check(doc.parse(md))]
        for code in ("S15", "S16", "S17", "S18"):
            self.assertIn(code, c, code)
        ok = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。ライトはどこにありますか。水を3リットル数えます。")
        self.assertFalse([x for x in style_rules.check(doc.parse(ok)) if x["code"] in ("S15", "S16", "S17", "S18")])

    def test_the_word_dictionary_marks_replaces_and_learns(self):
        import tempfile
        from pathlib import Path as P
        from sokuhou.kobo import lexicon
        self.assertEqual(lexicon.scan(["足りない所を見つけてみませんか。"])[0]["code"], "S15")
        txt = ("## 足りなかったら、どこから?\n\n足りない所を見つけてみませんか。この記事は水を扱います。\n\n| 扱 | 足りない所 |\n\n"
               "> ライフハック: 足りない所\n\nどこにありますか。取り扱いは別です。")
        new, n = lexicon.autofix(txt)
        self.assertIn("## 足りなかったら、何から?", new)
        self.assertIn("足りないものを確認しませんか。この記事は水を取り上げます。", new)
        self.assertIn("| 扱 | 足りない所 |", new)                  # a table row is left alone
        self.assertIn("どこにありますか。", new)                   # a place: not replaced
        self.assertIn("取り扱いは別です", new)                     # 取り扱い is not 扱う
        self.assertEqual(n, 4)
        # a new point becomes an entry at once
        old = lexicon.PATH
        with tempfile.TemporaryDirectory() as td:
            lexicon.PATH = P(td) / "w.json"
            lexicon.PATH.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
            try:
                e = lexicon.add_entry("試しの語", "試しの語は使わない。", ["別の語"], code="S99", auto=[["試しの語", "別の語"]])
                self.assertEqual(lexicon.autofix("これは試しの語です。")[0], "これは別の語です。")
                self.assertEqual(lexicon.scan(["試しの語"])[0]["id"], e["id"])
            finally:
                lexicon.PATH = old

    def test_style_marks_never_block(self):
        md = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。表に数字を並べると分かります。")
        fs = [f for f in checks.check(doc.parse(md), MAT, CARD) if f.code.startswith("S")]
        self.assertTrue(fs)
        self.assertFalse(any(f.block for f in fs))

    def test_definite_claims_are_marked_not_blocked(self):
        md = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。これで必ず安心です。")
        fs = checks.check(doc.parse(md), MAT, CARD)
        k14 = [f for f in fs if f.code == "K14"]
        self.assertTrue(k14)
        self.assertFalse(any(f.block for f in k14))


class Loop(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_rewrite_until_the_reader_passes(self):
        bad = GOOD.replace("出しておけば大丈夫です", "出しておくのが一つの手です").replace("一度点けてみてください", "一度点けてみるのも手です")
        fake = FakeModels([bad, GOOD], reader_marks=1)
        runner.set_backend(fake)
        r = engine.run("article", MAT, CARD, writer="sonnet", record=False)
        self.assertTrue(r["passed"])
        self.assertEqual(r["rewrites"], 1)
        self.assertEqual(r["reader"], "codex")          # the reader is of the other family
        self.assertEqual(r["output"].strip(), GOOD.strip())
        # the reader never sees the rule findings
        reader_prompts = [p for m, p in fake.calls if m == "codex"]
        self.assertTrue(reader_prompts)

    def test_nothing_is_output_when_the_reader_never_passes(self):
        runner.set_backend(FakeModels([GOOD], reader_marks=99))
        r = engine.run("article", MAT, CARD, writer="haiku", record=False)
        self.assertFalse(r["passed"])
        self.assertEqual(r["output"], "")
        self.assertEqual(r["rewrites"], engine.MAX_REWRITES)
        self.assertEqual(len(r["rounds"]), engine.MAX_REWRITES + 1)

    def test_machine_finding_blocks_even_if_the_reader_passes(self):
        bad = GOOD.replace("点検は2時間です。", "点検は3時間です。")
        runner.set_backend(FakeModels([bad], reader_marks=0))
        r = engine.run("article", MAT, CARD, writer="opus", record=False, rewrites=1)
        self.assertFalse(r["passed"])

    def test_the_best_round_is_kept_not_the_last(self):
        worse = GOOD.replace("点検は2時間です。", "点検は3時間です。")          # a rewrite that adds a number not in the material
        runner.set_backend(FakeModels([GOOD, worse], reader_marks=99))   # the reader never passes: nothing passes, the best is still recorded
        r = engine.run("article", MAT, CARD, writer="opus", record=False, rewrites=1)
        self.assertFalse(r["passed"])
        self.assertEqual(r["best_round"], 0)
        self.assertEqual(r["best"].strip(), GOOD.strip())

    def test_mark_allowance(self):
        l2 = [{"level": 2}]
        self.assertTrue(engine.marks_ok([{"level": 1}], "x"))
        self.assertFalse(engine.marks_ok([{"level": 3}], "x" * 5000))
        old = engine.PASS_L2_CHARS
        try:
            engine.PASS_L2_CHARS = 0
            self.assertFalse(engine.marks_ok(l2, "x" * 5000))
            engine.PASS_L2_CHARS = 500
            self.assertTrue(engine.marks_ok(l2, "x" * 600))
            self.assertFalse(engine.marks_ok(l2 * 2, "x" * 600))
            self.assertFalse(engine.marks_ok(l2, "x" * 600, "title"))      # short pieces: no level-2 mark at all
        finally:
            engine.PASS_L2_CHARS = old

    def test_reader_of_the_same_family_is_refused(self):
        runner.set_backend(FakeModels([GOOD]))
        with self.assertRaises(ValueError):
            engine.run("article", MAT, CARD, writer="sonnet", reader="opus", record=False)

    def test_title_candidates_passed_one_by_one(self):
        fake = FakeModels(["停電の夜に、ライトをひとつ出しておこう\n点検の夜、ライトはどこに置く?\n停電の前に、電池の向きを見ておこう"], reader_marks=0)
        runner.set_backend(fake)
        r = engine.run("title", MAT, CARD, record=False)
        self.assertTrue(r["passed"])
        self.assertEqual(r["writer"], "haiku")           # short pieces go to the light model
        self.assertEqual(len(r["output"]), 3)

    def test_writer_by_weight(self):
        self.assertEqual(engine.pick_writer("article", dict(MAT, weight="heavy"), None), "opus")
        self.assertEqual(engine.pick_writer("article", dict(MAT, weight="mid"), None), "sonnet")
        self.assertEqual(engine.pick_writer("threads", dict(MAT, weight="heavy"), None), "haiku")
        self.assertEqual(runner.other_family("codex"), "opus")


PLAN_ONE = """# 案1: ライトをひとつ
## 入口のニュース
市の停電の点検。
## 読者と、感じる不安(根拠の事実)
点検は2時間。
## 置く商品の種類と、置く文脈
- ライト — 暗い夜
## 親ページと子ページ
親1、子1。
## 読者に動いてもらう仕掛け
- ライトを出す
## 危機感の作り方(事実から)
今すぐ買わないと手遅れです。
## 誠実さの線(書かないこと)
直撃と書かない。
"""
PLAN_WIDE = """# 案2: 停電の夜の総点検
## 入口のニュース
市の停電の点検。
## 読者と、感じる不安(根拠の事実)
点検は2時間。
## 置く商品の種類と、置く文脈
- ライト — 暗い夜
- 電池 — ライトと連絡
- ラジオ — 情報
## 親ページと子ページ
親1、子3。
## 読者に動いてもらう仕掛け
- チェックリストで数える
- アンケート
## 危機感の作り方(事実から)
台風は直撃はしない。点検の2時間を、家で数える時間にする。
## 商品の置き場所
- 親: なし / 子1: ライトの選び方のあと、ライトの種類
## 誠実さの線(書かないこと)
直撃と書かない。
"""
BRIEF = {"id": "t", "site": "wadai", "facts": [{"text": "市は11月4日、夜に停電の点検があると発表しました。点検は2時間です。", "status": "primary"}],
         "products": [{"kind": "ライト"}, {"kind": "電池"}, {"kind": "ラジオ"}]}


class Plan(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_checks_catch_a_narrow_alarming_plan(self):
        from sokuhou.kobo import plan
        c = {x["code"] for x in plan.plan_checks(PLAN_ONE, BRIEF) if x["block"]}
        self.assertEqual(c, {"P01", "P02", "P03", "P06"})
        self.assertEqual([x for x in plan.plan_checks(PLAN_WIDE, BRIEF) if x["block"]], [])     # '直撃はしない' is the fact, not an alarm

    def test_three_plans_reviewed_and_the_pick_reworked(self):
        from sokuhou.kobo import plan
        state = {"reviews": 0}

        def fake(model, prompt, system=None):
            if "読みたい" in prompt:          # the reviewer
                state["reviews"] += 1
                if state["reviews"] == 1:
                    return json.dumps({"plans": [{"no": 1, "issues": [{"kind": "商品が少ない", "text": "ライトだけ", "level": 3}]},
                                                 {"no": 2, "issues": [{"kind": "その他", "text": "子ページが薄い", "level": 2}]}], "choice": 2, "why": "広い", "improve": ["子ページに表"]})
                return json.dumps({"plans": [{"no": 1, "issues": []}], "choice": 1, "why": "よい"})
            if "書き直して" in prompt:
                return PLAN_WIDE.replace("親1、子3。", "親1、子3(それぞれに数える表)。")
            return PLAN_ONE + "\n" + PLAN_WIDE
        runner.set_backend(fake)
        r = plan.run(BRIEF, CARD, writer="opus", record=False)
        self.assertEqual(len(r["plans"]), 2)
        self.assertEqual(r["choice"], 2)
        self.assertTrue(r["passed"])
        self.assertIn("数える表", r["chosen"])
        self.assertEqual(r["reader"], "codex")


class Tsukkomi(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_points_and_the_revised_text_become_the_next_version(self):
        fixed = GOOD.replace("## 点検は、いつ?", "## 停電の点検は、いつ?")
        answer = "===突っ込み===\n" + json.dumps({"points": [{"text": "点検は、いつ?", "kind": "見出し", "ask": "何の点検?", "fix": "停電の点検は、いつ?"}]}) + "\n===直した全文===\n" + fixed
        runner.set_backend(lambda model, prompt, system=None: answer)
        t = engine.tsukkomi(GOOD, "haiku")
        self.assertTrue(t["ok"])
        self.assertEqual(len(t["points"]), 1)
        self.assertEqual(t["revised"].strip(), fixed.strip())

    def test_an_unreadable_answer_keeps_the_text(self):
        runner.set_backend(lambda model, prompt, system=None: "形の違う答え")
        t = engine.tsukkomi(GOOD, "haiku")
        self.assertFalse(t["ok"])
        self.assertEqual(t["revised"], GOOD)


class Questions(unittest.TestCase):
    PAGE = "<html><body><p>消費者ホットラインは、身近な消費生活センターや消費生活相談窓口をご案内します。</p></body></html>"

    def tearDown(self):
        runner.set_backend(None)

    def test_quote_check(self):
        from sokuhou.kobo import questions as Q
        fetch = lambda url: self.PAGE
        self.assertTrue(Q.quote_found("https://www.caa.go.jp/x", "身近な消費生活センターや消費生活相談窓口をご案内します", fetch)[0])
        self.assertFalse(Q.quote_found("https://www.caa.go.jp/x", "消費者庁が直接相談に乗ります。電話は無料です", fetch)[0])      # not on the page
        self.assertFalse(Q.quote_found("https://example.com/x", "身近な消費生活センターや消費生活相談窓口をご案内します", fetch)[0])  # not a public page

    def test_ask_research_and_material(self):
        from sokuhou.kobo import questions as Q

        def fake(model, prompt, system=None):
            if "演じます" in prompt:
                return json.dumps({"personas": [{"who": "迷っている人", "questions": [
                    {"q": "188に電話するとどこにつながる?", "action": "電話する", "answer_type": 1, "place": "質問と答え", "search": "消費者庁"},
                    {"q": "私の地域の相談先は?", "action": "調べる", "answer_type": 3, "place": "別ページ"}]}]})
            return json.dumps({"answers": [
                {"q": "188に電話するとどこにつながる?", "found": True, "answer": "188は、身近な消費生活センターや相談窓口を案内する。",
                 "url": "https://www.caa.go.jp/x", "quote": "身近な消費生活センターや消費生活相談窓口をご案内します"},
                {"q": "作り話", "found": True, "answer": "x", "url": "https://www.caa.go.jp/x", "quote": "このページにない文をそれらしく書いたもの"}]})
        runner.set_backend(fake)
        q = Q.ask(MAT)
        self.assertEqual([x["answer_type"] for x in q["questions"]], [1, 3])
        r = Q.research(q["questions"], fetch=lambda url: self.PAGE)
        self.assertEqual(len(r["accepted"]), 1)
        self.assertEqual(r["dropped"][0]["check"], "the quote is not in the page")
        m2 = Q.add_to_material(MAT, r["accepted"])
        self.assertEqual(m2["facts"][-1]["status"], "primary")
        self.assertIn("quote checked", m2["facts"][-1]["note"])
        self.assertNotIn("caa.go.jp", material.for_prompt(m2))          # the record stays private


class Output(unittest.TestCase):
    def test_toc_for_a_long_article(self):
        long = GOOD.replace("## 何を出せばいい?", "## 何を出せばいい?\nライトを出します。\n\n## どこに置く?\n手の届く所です。\n\n## 電池は?\nそばに入れます。\n\n## 何を見る?")
        out = doc.with_toc(long)
        self.assertIn("## 目次\n- 点検は、いつ?", out)
        self.assertLess(out.index("## 3行まとめ"), out.index("## 目次"))
        self.assertEqual([s["heading"] for s in doc.parse(out)["sections"]], [s["heading"] for s in doc.parse(long)["sections"]])
        self.assertEqual(doc.with_toc(GOOD), GOOD)          # short: no table of contents
        named = doc.with_toc(long.replace("## 3行まとめ", "## 備えの3行まとめ"))
        self.assertLess(named.index("## 備えの3行まとめ"), named.index("## 目次"))

    def test_ledger(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            old = engine.home
            engine.home = lambda: Path(tmp)
            try:
                f = Path(tmp) / "a.md"
                f.write_text(GOOD, encoding="utf-8")
                engine.ledger_add(MAT, {"tool": "article", "site": "wadai", "writer": "opus", "reader": "codex"}, f)
                row = engine.ledger_set("t-light/article", "note_views", 12)
                self.assertEqual(row["reading"]["note_views"], 12)
                self.assertIsNone(row["reading"]["site_clicks"])
                with self.assertRaises(KeyError):
                    engine.ledger_set("t-light/article", "price", 1)
            finally:
                engine.home = old

    def test_note_needs_the_ai_line(self):
        fs = [f.code for f in checks.blocking(checks.check(doc.parse(GOOD), MAT, dict(CARD, _tool="note"), "article"))]
        self.assertIn("K13", fs)
        ok = GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。\n\n(この記事は、公開データをもとに、AIの支援を受けて作成しています。)", 1)
        self.assertNotIn("K13", [f.code for f in checks.blocking(checks.check(doc.parse(ok), MAT, dict(CARD, _tool="note"), "article"))])


class Calibration(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_rates(self):
        def fake(model, prompt, system=None):
            lvl = 3 if "一つの手" in prompt else 1
            return json.dumps({"marks": [{"text": "a", "level": lvl, "why": "", "fix": ""}]})
        runner.set_backend(fake)
        items = [{"id": "b1", "label": "bad", "head": "", "text": "出すのが一つの手です。"}, {"id": "b2", "label": "bad", "head": "", "text": "ふつうの文です。"},
                 {"id": "g1", "label": "good", "head": "", "text": "ライトを出しておこう。"}]
        s = calibrate.run(items, "codex", workers=1)["summary"]
        self.assertEqual((s["bad_marked"], s["bad_rate"], s["good_passed"], s["good_rate"]), (1, 0.5, 1, 1.0))

    def test_unreadable_answer_counts_as_marked(self):
        runner.set_backend(lambda model, prompt, system=None: "読めない答え")
        s = calibrate.run([{"id": "g", "label": "good", "head": "", "text": "x"}], "codex", workers=1)["summary"]
        self.assertEqual(s["good_passed"], 0)
        self.assertEqual(s["errors"], ["g"])


if __name__ == "__main__":
    unittest.main()
