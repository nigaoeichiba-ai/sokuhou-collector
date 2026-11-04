"""文章工房 (sokuhou/kobo): the writer's Markdown, the machine checks (a negative case for each), the material rules, and the write -> check ->
reader-gate loop with a fake model backend (no model is called in a test).  The texts here are made up (no news, no mall data)."""
import json
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
        self.assertIn("K01", codes(GOOD.replace("出しておけば大丈夫です", "出しておくのが一つの手です")))

    def test_same_opening_three_times(self):
        md = GOOD.replace("市は11月4日、夜に停電の点検があると発表しました。点検は2時間です。",
                          "市の発表では、夜に停電の点検があります。市の発表では、点検は2時間です。市の発表では、11月4日の発表です。")
        self.assertIn("K01", codes(md))

    def test_same_ending_three_times(self):
        md = GOOD.replace("ライトをひとつ出して、一度点けてみてください。", "ライトを出しておきましょう。点けておきましょう。電池も入れておきましょう。")
        self.assertIn("K01", codes(md))

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

    def test_same_thing_twice(self):
        md = GOOD.replace("> 出したついでにスイッチを入れて、点くか見ておきます。", "> 市は11月4日、夜に停電の点検があると発表しました。")
        self.assertIn("K02", codes(md))

    def test_table_repeating_a_paragraph(self):
        md = GOOD.replace("## 何を出せばいい?", "| 市は11月4日 | 夜に停電の点検があると発表しました |\n\n## 何を出せばいい?")
        self.assertIn("K02", codes(md))

    def test_lead_of_three_sentences(self):
        self.assertIn("K10", codes(GOOD.replace("暗い中で探さずにすみます。", "暗い中で探さずにすみます。電池も見ます。")))

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
        if "ふつうの会社員" in prompt:
            self.reader_marks -= 1
            if self.reader_marks >= 0:
                return json.dumps({"marks": [{"text": "大丈夫です", "level": 2, "why": "硬い", "fix": "x"}], "impression": ""})
            return json.dumps({"marks": [{"text": "x", "level": 1, "why": "好み", "fix": ""}], "impression": "自然"})
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


class Loop(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_rewrite_until_the_reader_passes(self):
        bad = GOOD.replace("出しておけば大丈夫です", "出しておくのが一つの手です")
        fake = FakeModels([bad, GOOD], reader_marks=1)
        runner.set_backend(fake)
        r = engine.run("article", MAT, CARD, writer="sonnet", record=False)
        self.assertTrue(r["passed"])
        self.assertEqual(r["rewrites"], 1)
        self.assertEqual(r["reader"], "codex")          # the reader is of the other family
        self.assertEqual(r["output"], GOOD)
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
        self.assertEqual(c, {"P01", "P02", "P03"})
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
