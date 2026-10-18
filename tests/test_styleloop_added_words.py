"""check_rewrite refuses a rewording that adds a noun the original does not have (2026-10-18 owner/desk order: adding or dropping words changes the information)."""
import unittest

from sokuhou import styleloop as sl

CASES = [  # real rewordings that had been accepted on 2026-10-18 and were taken out again
    ("あたたかい夜を。", "あたたかなクリスマスを。", "クリスマス"),
    ("日々の助言に多くを学ばせていただいております。ささやかですが、お礼としてお受け取りください。", "日々のご助言から多くを学んでおります。ささやかですが、お礼の品としてお受け取りください。", "品"),
    ("今年も一緒に季節を迎えられることをうれしく思います。あたたかい時間を過ごしましょう。", "今年も一緒にクリスマスを迎えられてうれしいです。家族であたたかい時間を過ごしましょう。", "家族"),
]


class AddedWords(unittest.TestCase):
    def test_added_noun_is_found(self):
        for old, new, word in CASES:
            self.assertIn(word, sl.added_words(old, new))

    def test_rejected_by_check_rewrite(self):
        for old, new, word in CASES:
            reasons = sl.check_rewrite(old, new, "yorokobu", kind="note", small_edit=False)
            self.assertTrue(any("words added" in r for r in reasons), (old, reasons))

    def test_plain_rewording_is_not_flagged(self):
        self.assertEqual(sl.added_words("お誕生日おめでとうございます。", "お誕生日おめでとう。"), [])
        self.assertEqual(sl.added_words("感謝や一年のねぎらいを中心にすると使いやすくなります。", "感謝や一年のねぎらいを中心に伝えます。"), [])


if __name__ == "__main__":
    unittest.main()
