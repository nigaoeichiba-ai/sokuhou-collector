"""The desk's residual points (2026-11-04 evening): titles, repeated heading verbs, 全角？, dictionary entries."""
import unittest

from sokuhou.kobo import doc, engine, lexicon, style_rules


class Residual(unittest.TestCase):
    def test_a_title_with_kudasai_or_mashou_is_marked_and_dropped_from_the_vote(self):
        for t in ("パーソナルジムの契約は、持ち帰って決めてください", "停電に備えて電池を確認しましょう"):
            d = doc.parse("# " + t + "\n\n冒頭です。二文目です。\n\n## 見出し\n本文です。\n")
            self.assertIn("S20", [x["code"] for x in style_rules.check(d)], t)
            self.assertTrue(engine.BAD_TITLE.search(t), t)

    def test_the_same_verb_in_three_headings(self):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 水を確かめる\nあ。\n\n## 食料を確かめる\nい。\n\n## ライトを確かめる\nう。\n"
        self.assertIn("S37", [x["code"] for x in style_rules.check(doc.parse(md))])
        ok = "# 題\n\n冒頭です。二文目です。\n\n## 水を確かめる\nあ。\n\n## 食料を見る\nい。\n\n## ライトを選ぶ\nう。\n"
        self.assertNotIn("S37", [x["code"] for x in style_rules.check(doc.parse(ok))])

    def test_question_marks_and_the_new_entries(self):
        self.assertEqual(lexicon.autofix("## 足りない？ いくつ?\n\n本当ですか?")[0], "## 足りない？ いくつ？\n\n本当ですか？")
        self.assertEqual(lexicon.autofix("https://example.com/?a=1")[0], "https://example.com/?a=1")      # a URL is left alone
        self.assertTrue(lexicon.scan(["家族が代わりに相談するとき", "介護や見守りをしている人からの相談"])[0:1])
        self.assertIn("手に取れる場所", lexicon.autofix("すぐ手に取れる所にありますか")[0])
        self.assertTrue(lexicon.scan(["停電への備えは、いま見直す時期です。"]))
        self.assertTrue(lexicon.scan(["事前防災の徹底を求める緊急要請を出しました。"]))
        self.assertFalse(lexicon.scan(["「事前防災の徹底を求める緊急要請」と呼ばれます。"]))


class Summary(unittest.TestCase):
    def test_a_lead_sentence_repeated_in_the_summary_is_marked(self):
        md = ("# 題\n\n防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。全部を一度に始めなくて大丈夫です。\n\n"
              "## 3行まとめ\n- 防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。\n- 水は一人一日3リットルです。\n- どれから始めるかを選びます。\n\n## 見出し\n本文です。\n")
        self.assertIn("S53", [x["code"] for x in style_rules.check(doc.parse(md))])
        ok = md.replace("- 防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。", "- 5つは、耐震診断と家具の固定、備蓄、ハザードマップの確認、持ち出し品の準備、防災訓練への参加です。")
        self.assertNotIn("S53", [x["code"] for x in style_rules.check(doc.parse(ok))])


class Wording(unittest.TestCase):
    def test_the_calculator_label_and_the_sonae_noun(self):
        from sokuhou.kobo import parts
        h = parts.calculator_html([{"name": "水", "rate": 3, "unit": "リットル"}])
        self.assertIn("いっしょに暮らす人数", h)
        self.assertNotIn("家の人数", h)
        self.assertIn("水と食料、必要な量", lexicon.autofix("水と食料の数え方")[0])
        self.assertIn("携帯トイレ、必要な数", lexicon.autofix("携帯トイレの数え方")[0])
        self.assertEqual(lexicon.autofix("足りない備えを増やす")[0], "足りない防災グッズを増やす")
        self.assertEqual(lexicon.autofix("水や食料などの備えは足りていますか")[0], "水や食料などの備蓄は足りていますか")
        self.assertFalse(lexicon.scan(["災害への備えが大事です。"]))             # the general use stays
        self.assertTrue(lexicon.scan(["家にある備えに□をつけます。"]))


class SeparateStories(unittest.TestCase):
    def test_typhoon_and_the_agency_call_in_one_lead_or_paragraph_are_marked(self):
        md = ("# 題\n\n台風31号は直撃しない予報です。防災庁は11月2日、備えを呼びかけました。\n\n## 見出し\n本文です。\n\n## 別の節\n台風と同じころ、防災庁は呼びかけました。\n")
        marks = [x for x in style_rules.check(doc.parse(md)) if x["code"] == "S45"]
        self.assertEqual(len(marks), 2)                                       # the lead and the paragraph
        ok = ("# 題\n\n台風31号は直撃しない予報です。備えは足りていますか。\n\n## 見出し\n本文です。\n\n## 別の節\n国の防災庁は11月2日、備えを呼びかけました。\n")
        self.assertFalse([x for x in style_rules.check(doc.parse(ok)) if x["code"] == "S45"])
        self.assertTrue(lexicon.scan(["台風と同じころ、防災庁は呼びかけました。"]))
        self.assertFalse(lexicon.scan(["国の防災庁は11月2日、水と食料を備えるよう呼びかけました。"]))


class Residual2(unittest.TestCase):
    def test_square_in_the_lead_and_mixed_summary_endings(self):
        md = ("# 題\n\n冒頭に□をつけます。二文目です。\n\n## 3行まとめ\n- 一つ目です。\n- 二つ目は、そろえる。\n- 三つ目です。\n\n## 見出し\n本文です。\n")
        codes = [x["code"] for x in style_rules.check(doc.parse(md))]
        self.assertIn("S43", codes)
        self.assertIn("S44", codes)
        ok = md.replace("□をつけ", "確かめ").replace("そろえる。", "そろえます。")
        self.assertNotIn("S44", [x["code"] for x in style_rules.check(doc.parse(ok))])


if __name__ == "__main__":
    unittest.main()


class DeAndOku(unittest.TestCase):
    def test_deru_and_oku_words(self):
        hit = ["回数が出たら、次へ進みます。", "表で出した回数に届くものを選びます。", "買い足す数を出す", "手の届く場所に置きます。", "手元に置いて読みます。"]
        ok = ["ライトを出して、一度点けます。", "外に出る前に確認します。", "熱が出たら休みます。", "水道水の汲み置きは3日ほどです。", "古い電池の買い置きを確かめます。", "置き場所を決めます。", "位置を確かめます。"]
        for t in hit:
            self.assertTrue(lexicon.scan([t]), t)
        for t in ok:
            self.assertFalse(lexicon.scan([t]), t)
