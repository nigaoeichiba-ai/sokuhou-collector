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


if __name__ == "__main__":
    unittest.main()
