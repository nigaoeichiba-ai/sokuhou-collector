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

class MakingThemesTest(unittest.TestCase):
    """2026-11-02 (weekly review): a page about the TOOLS for making candles showed finished candles - the idea's words held the bare 「キャンドル」.  The same shape in the pizza,
    dumpling, cheese and soap-carving pages (frozen pizza, frozen dumplings, cheese itself, liquid soap, rhinestones as 「ストーン」)."""
    themes = {t["slug"]: t for t in content.load()["themes"]}

    def ideas(self, slug):
        return {i["label"]: i for i in self.themes[slug]["ideas"]}

    def fits(self, slug, label, title):
        i = self.ideas(slug)[label]
        return relevance.fits_idea(title, i["must"], i.get("not"))

    def test_no_candle_idea_takes_a_finished_candle(self):
        for label in self.ideas("candle-making-workspace"):
            self.assertNotIn("キャンドル", self.ideas("candle-making-workspace")[label]["must"], label)
            self.assertFalse(self.fits("candle-making-workspace", label, "ウッドウィック キャンドル アロマ 3個 ギフト 完成品"), label)
        self.assertTrue(self.fits("candle-making-workspace", "芯固定ホルダー", "キャンドル用 芯ホルダー 5.6mm"))
        self.assertTrue(self.fits("candle-making-workspace", "植物性ワックス", "ソイワックス 500g キャンドル作り"))
        self.assertFalse(self.fits("candle-making-workspace", "植物性ワックス", "ヘアワックス 80g スタイリング"))
        self.assertTrue(self.fits("candle-making-workspace", "シリコンモールド", "キャンドルモールド シリコン 6連"))

    def test_the_making_pages_take_the_tools_and_not_the_finished_food_or_goods(self):
        self.assertFalse(self.fits("home-pizza-table", "ピザ用粉", "冷凍ピザ 5枚 マルゲリータ 宅配"))
        self.assertTrue(self.fits("home-pizza-table", "ピザ用粉", "ピザ用粉 強力粉 1kg"))
        self.assertFalse(self.fits("home-pizza-table", "ピザストーン", "スワロフスキー ストーン 10mm ラインストーン"))
        self.assertTrue(self.fits("home-pizza-table", "ピザストーン", "ピザストーン 33cm 石窯プレート"))
        self.assertFalse(self.fits("dumpling-making-table", "皮の型抜き", "冷凍 餃子 20個 ギョーザ お取り寄せ"))
        self.assertTrue(self.fits("dumpling-making-table", "皮の型抜き", "餃子の皮 型抜き 9cm ステンレス"))
        self.assertFalse(self.fits("cheese-board-at-home", "チーズナイフ", "チーズ 詰め合わせ ギフトセット 5種"))
        self.assertTrue(self.fits("cheese-board-at-home", "チーズナイフ", "チーズナイフ 3本セット チーズカッター"))
        self.assertFalse(self.fits("soap-carving-table", "彫刻用石けん", "ハンドソープ 詰め替え 1600ml"))
        self.assertTrue(self.fits("soap-carving-table", "彫刻用石けん", "彫刻用石けん ソープカービング 6個"))


if __name__ == "__main__":
    unittest.main()
