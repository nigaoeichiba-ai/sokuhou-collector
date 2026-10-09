"""The Japanese style gate: each rule must catch the writing the owner found off (2026-10-09), and must let calm, concrete writing through."""
import unittest
from pathlib import Path

from sites.yorokobu import factory, quality

GOOD = ("通勤バッグに入る薄型のポーチなら、職場で渡しても持ち帰れます。小物の整理にも使えるので、毎日の出番があります。"
        "個包装の焼き菓子は、家族で分けられて、余っても翌日に回せます。")


class LanguageGateTest(unittest.TestCase):
    def probs(self, text, casual=False):
        return quality.language_problems(text, "x", casual=casual)

    def test_calm_concrete_writing_passes(self):
        self.assertEqual(self.probs(GOOD), [])

    def test_a_comma_after_every_short_phrase_is_caught(self):
        for bad in ("誕生日や記念日を登録すると、3週間前に、カレンダーで、お知らせします。",
                    "商品は、楽天市場の情報を、毎日、自動で、表示しています。",
                    "母に、父に、兄にと、広げます。"):
            self.assertTrue(any("comma after every" in p for p in self.probs(bad)), bad)
        self.assertEqual(self.probs("3週間前にカレンダーでお知らせします。"), [])
        self.assertEqual(self.probs("花器、時計、クッション、収納小物など、家に置く贈り物は長く目に入ります。"), [])      # a list of nouns is fine

    def test_editors_jargon_is_caught(self):
        for w in ("切り口", "ソムリエ", "ナビゲーター", "見立て", "ギフトマップ", "コンシェルジュ", "ガチャ"):
            self.assertTrue(any("internal word" in p for p in self.probs(f"{w}から選びます。")), w)

    def test_childish_tone_is_caught_except_in_the_senders_own_voice(self):
        for w in ("贈るきっかけを選んでね", "候補を見つけたよ", "ぜんぶ見る", "プレゼント選びをわくわくに"):
            self.assertTrue(any("childish" in p for p in self.probs(w + "。")), w)
        self.assertEqual(self.probs("体に気をつけてね。", casual=True), [])

    def test_the_easy_ending_is_limited(self):
        self.assertTrue(any("やすい" in p for p in self.probs("選びやすいです。渡しやすいです。使いやすいです。")))
        self.assertTrue(any("やすい" in p for p in self.probs("選びやすい。" * 5)))
        self.assertEqual(self.probs("選びやすいです。渡しやすいです。"), [])

    def test_a_very_long_sentence_and_claims_without_basis_are_caught(self):
        self.assertTrue(any("split it" in p for p in self.probs("あ" * 101 + "。")))
        self.assertTrue(any("without basis" in p for p in self.probs("よく読まれているページです。")))

    def test_the_gate_runs_on_new_themes_articles_and_messages_and_the_factory_brief_names_the_rules(self):
        self.assertIn("never write for teenagers", factory.RULES)
        self.assertIn("切り口", factory.RULES)
        src = Path(quality.__file__).read_text(encoding="utf-8")
        for fn, nxt in (("theme_problems", "article_problems"), ("article_problems", "MESSAGE_FORBIDDEN"), ("message_problems", "repeated_sentences")):
            body = src.split(f"def {fn}" if fn != "MESSAGE_FORBIDDEN" else fn)[1].split(nxt)[0]
            self.assertIn("language_problems", body, fn)


if __name__ == "__main__":
    unittest.main()
