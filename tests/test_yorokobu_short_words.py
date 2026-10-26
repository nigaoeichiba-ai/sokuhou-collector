"""Weekly review 2026-10-26: 「アンテナ(360ml)」 was a ginger syrup (sold by an antenna shop), 「トレー(250ml)」 a solar lantern.  The idea's word was found INSIDE a longer word
(アンテナショップ, トレーニング ...) and the card took the fragment as its name.  A short katakana word counts only as a word."""
import unittest

from sites.yorokobu import blurb, relevance


class WordPositionsTest(unittest.TestCase):
    def test_a_short_katakana_word_inside_a_longer_one_does_not_count(self):
        self.assertEqual(relevance.word_positions("国産 生姜シロップ 360ml アンテナショップ 限定", "アンテナ"), [])
        self.assertEqual(relevance.word_positions("ソーラーライト トレーニング用 ランタン", "トレー"), [])
        self.assertEqual(relevance.word_positions("ストレート ソーラーランタン", "トレー"), [])
        self.assertEqual(relevance.word_positions("マグネット 付き ボード", "マグ"), [])

    def test_the_same_words_count_when_they_stand_as_words(self):
        self.assertTrue(relevance.word_positions("短波ラジオ 外付け アンテナ 3m", "アンテナ"))
        self.assertTrue(relevance.word_positions("アクセサリー トレー 20cm", "トレー"))
        self.assertTrue(relevance.word_positions("ジュエリートレー 大", "トレー"))                       # a compound that ends in the word
        self.assertTrue(relevance.word_positions("トレー付き 収納", "トレー"))                          # followed by hiragana / kanji
        self.assertTrue(relevance.word_positions("アンテナ セット", "アンテナ"))                       # a space is a border
        self.assertTrue(relevance.word_positions("トレーセット 2個", "トレー"))                          # 「セット」「ギフト」 after a word do not make another word
        self.assertTrue(relevance.word_positions("ステンレスマグ 350ml", "マグ"))

    def test_spaces_inside_the_title_and_the_width_of_letters_are_still_ignored(self):
        self.assertTrue(relevance.word_positions("ホワイト ボード 冷蔵庫", "ホワイトボード"))
        self.assertTrue(relevance.word_positions("ｱﾝﾃﾅ 3m", "アンテナ"))

    def test_longer_words_and_words_with_other_scripts_are_matched_as_before(self):
        self.assertTrue(relevance.word_positions("チョコレートギフト 詰め合わせ", "チョコレート"))      # (5+ letters: the old rule)
        self.assertTrue(relevance.word_positions("洗濯ばさみ 20個", "洗濯ばさみ"))


class GateTest(unittest.TestCase):
    def test_a_product_with_the_word_only_inside_another_word_is_not_of_the_idea(self):
        must = ["アンテナ"]
        self.assertFalse(relevance.fits_idea("国産 生姜シロップ アンテナショップ 限定", must))
        self.assertTrue(relevance.fits_idea("短波 受信用 アンテナ 屋外", must))
        self.assertIsNone(relevance.head_position("生姜シロップ アンテナショップ", must))
        self.assertEqual(relevance.head_position("アンテナ 3m 屋外", must), 0)

    def test_the_card_of_such_a_product_never_takes_the_fragment_as_its_name(self):
        line = blurb.blurb("国産 生姜シロップ 360ml アンテナショップ 限定", must=["アンテナ"])
        self.assertNotIn("アンテナ", line)


if __name__ == "__main__":
    unittest.main()
