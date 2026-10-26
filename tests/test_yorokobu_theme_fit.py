"""Weekly review 2026-10-26: a page of shoe CARE showed shoes (the idea's word 「靴」 / 「シューズ」 lets the shoes in), a page titled 'tools' for making matcha showed a sweet
(the idea is a matcha sweet; the title now says 道具と茶菓子)."""
import unittest

from sites.yorokobu import content, relevance


class ThemeFitTest(unittest.TestCase):
    themes = {t["slug"]: t for t in content.load()["themes"]}

    def test_the_shoe_care_page_lets_in_care_goods_and_not_shoes(self):
        must = [w for i in self.themes["shoe-first-week"]["ideas"] for w in i["must"]]
        self.assertNotIn("靴", must)
        self.assertNotIn("シューズ", must)
        brush = next(i for i in self.themes["shoe-first-week"]["ideas"] if i["label"] == "靴ブラシ")
        self.assertFalse(relevance.fits_idea("レディース スニーカー 靴 2色 通勤 シューズ", brush["must"]))
        self.assertTrue(relevance.fits_idea("馬毛 靴ブラシ 3点セット シューケア", brush["must"]))
        dry = next(i for i in self.themes["shoe-first-week"]["ideas"] if i["label"] == "乾燥材")
        self.assertFalse(relevance.fits_idea("ランニング シューズ 軽量", dry["must"]))
        self.assertTrue(relevance.fits_idea("靴用 乾燥剤 脱臭 繰り返し使える", dry["must"]))

    def test_the_matcha_page_names_the_sweet_in_its_title(self):
        t = self.themes["matcha-at-home-tools"]
        self.assertIn("茶菓子", t["title"])
        self.assertTrue(any("琥珀糖" in i["label"] or "琥珀糖" in i["must"] for i in t["ideas"]))


if __name__ == "__main__":
    unittest.main()
