"""Weekly review 2026-10-19 found on /theme/fridge-door-notes/ a wristwatch (its title lists 「カレンダー」) leading the page, two cards called 「リップ」 (a lip balm sold with a
hair clip, and a money clip: 「マネークリップ」 holds 「リップ」), a magnet board called 「マグ」 (「マグネット」 holds 「マグ」), and on three pages a first-four card whose favourite
button read 「気になる品」 (the card had no words at all).  The titles below are made up for the same shapes; no shop's data is in this file."""
import unittest

from sites.yorokobu import blurb, build, relevance

FRIDGE = [
    {"label": "白板メモ", "type": "実用品", "must": ["ホワイトボード", "マグネットボード", "メモボード"], "items": []},
    {"label": "月間予定表", "type": "実用品", "must": ["カレンダー", "予定表", "マグネットカレンダー"], "items": []},
    {"label": "メモクリップ", "type": "おもしろ・サプライズ", "must": ["マグネットクリップ", "メモクリップ", "クリップ"], "items": []},
]


def item(code, name, price=2000, reviews=100):
    return {"code": code, "name": name, "price": price, "url": "https://item.rakuten.co.jp/s/x/", "image": "https://thumbnail.image.rakuten.co.jp/x.jpg", "shop": "s",
            "shop_code": code, "reviews": reviews, "rating": 4.5, "available": True, "free_shipping": True, "gift": False, "appoint": False}


def DATA(ideas):
    return {"pairs": {"k": {"ideas": ideas, "tiers": {}}}, "site_name": "よろこぶプレゼント", "fetched_label": "2026年10月19日 7:00"}


class KindWordIsAWordTest(unittest.TestCase):
    def kind(self, title, **kw):
        return blurb.find_kind(title, **kw)

    def test_a_katakana_kind_word_inside_a_longer_word_is_not_that_kind(self):
        self.assertNotEqual(self.kind("マグネットボード 45cm 冷蔵庫"), "マグ")
        self.assertNotEqual(self.kind("マネークリップ メンズ 薄型"), "リップ")
        self.assertNotEqual(self.kind("ガーデン スコップ 小型"), "コップ")
        self.assertNotEqual(self.kind("サングラス UV カット"), "グラス")
        self.assertNotEqual(self.kind("スタイル抜群 おしゃれ"), "スタイ")

    def test_the_same_words_still_count_when_they_stand_alone_or_end_a_compound_kind(self):
        self.assertEqual(self.kind("ステンレス マグ 350ml"), "マグ")
        self.assertEqual(self.kind("保温 ステンレスマグ"), "マグ")
        self.assertEqual(self.kind("リップ 保湿 無香料"), "リップ")
        self.assertEqual(self.kind("グラス ペア 2個"), "グラス")
        self.assertEqual(self.kind("ハンドクリームセット ミニ"), "ハンドクリーム")        # 「セット」「ギフト」「ペア」 after a kind do not make another word

    def test_the_card_line_of_a_money_clip_does_not_say_lip(self):
        self.assertNotIn("リップ", blurb.blurb("ジーンズ マネークリップ メンズ 薄型"))
        self.assertNotIn("マグ", blurb.blurb("マグネットボード 45cm 冷蔵庫 白"))


class IdeaWordWithSpacesTest(unittest.TestCase):
    def test_the_idea_word_is_found_in_a_title_that_spaces_it_the_way_the_gate_does(self):
        # relevance.fits_idea ignores spaces and case; a card that passed it by 「ホワイト ボード」 said 「二つ折り」 (a word of another idea) or, with no word known, 「気になる品」
        t = "二つ折り ホワイト ボード 冷蔵庫 マグネット 45cm"
        self.assertTrue(relevance.fits_idea(t, ["ホワイトボード"]))
        self.assertEqual(blurb.find_kind(t, must=["ホワイトボード"]), "ホワイトボード")
        self.assertEqual(blurb.find_kind(t, kind="白板", must=["ホワイトボード"]), "白板")


class ForeignKindTest(unittest.TestCase):
    CAL = ["カレンダー", "予定表", "マグネットカレンダー"]
    CLIP = ["マグネットクリップ", "メモクリップ", "クリップ"]

    def test_a_watch_whose_title_lists_the_word_of_another_idea_is_not_of_that_idea(self):
        self.assertEqual(relevance.foreign_kind("腕時計 レディース 日付 カレンダー 防水 ブランド", self.CAL), "腕時計")
        self.assertFalse(relevance.fits_lead("腕時計 レディース 日付 カレンダー 防水 ブランド", self.CAL))

    def test_a_lip_balm_sold_with_a_hair_clip_is_a_lip_balm(self):
        self.assertEqual(relevance.foreign_kind("リップ 保湿 ヘアクリップ セット", self.CLIP), "リップ")

    def test_the_idea_s_own_kind_and_its_family_are_not_foreign(self):
        self.assertIsNone(relevance.foreign_kind("マグネット カレンダー 冷蔵庫 2027", self.CAL))
        self.assertIsNone(relevance.foreign_kind("マネークリップ メンズ", self.CLIP))                       # kept out by the idea's `not`, not by this rule
        self.assertIsNone(relevance.foreign_kind("お菓子 クッキー 詰め合わせ", ["クッキー"]))               # a whole family in front of the word
        self.assertIsNone(relevance.foreign_kind("マグ 保温 タンブラー 350ml", ["タンブラー"]))              # same family (drinkware)
        self.assertIsNone(relevance.foreign_kind("ボトル 保温 タンブラー", ["保温タンブラー", "水筒"]))
        self.assertIsNone(relevance.foreign_kind("ハンドタオル ギフト ブランケット", ["ブランケット"]))
        self.assertIsNone(relevance.foreign_kind("名前のない商品", self.CAL))
        self.assertIsNone(relevance.foreign_kind("腕時計 カレンダー", None))

    def test_the_theme_keeps_money_clips_and_hair_clips_out_of_the_memo_clip_idea(self):
        from sites.yorokobu import content
        c = content.load()
        idea = next(i for t in c["themes"] if t["slug"] == "fridge-door-notes" for i in t["ideas"] if i["label"] == "メモクリップ")
        for title in ("ジーンズ マネークリップ メンズ", "ヘアクリップ バンスクリップ 大"):
            self.assertFalse(relevance.fits_idea(title, idea["must"], idea.get("not")), title)
        self.assertTrue(relevance.fits_idea("マグネット メモクリップ 10個", idea["must"], idea.get("not")))


class FirstFourTest(unittest.TestCase):
    def page(self):
        ideas = [dict(i) for i in FRIDGE]
        ideas[0]["items"] = [item("b1", "マグネットボード 45cm 冷蔵庫 白", reviews=50), item("b2", "ホワイトボード マグネット 小さめ", reviews=40)]
        ideas[1]["items"] = [item("w1", "腕時計 レディース 日付 カレンダー 防水", reviews=900), item("c1", "マグネット カレンダー 冷蔵庫 月間", reviews=60)]
        ideas[2]["items"] = [item("l1", "リップ 保湿 ヘアクリップ セット", reviews=300), item("m1", "マグネット メモクリップ 10個", reviews=70)]
        return DATA(ideas)

    def test_the_watch_and_the_lip_balm_do_not_lead_the_page(self):
        shown = [i["code"] for i in build.top_shown(self.page(), "k")]
        self.assertNotIn("w1", shown)
        self.assertNotIn("l1", shown)
        self.assertEqual(set(shown), {"b1", "b2", "c1", "m1"})

    def test_every_first_four_card_says_what_its_idea_is_about(self):
        cfg = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None}
        html = build.top_picks(cfg, self.page(), "k")
        self.assertIn("top-picks", html)
        self.assertNotIn("気になる品", html)                                   # the favourite button's name when a card had no words at all
        self.assertNotIn('class="item-blurb"></p>', html)
        self.assertNotIn(">マグ<", html)
        self.assertNotIn("腕時計", html)
        self.assertIn("ホワイトボード", html)

    def test_a_product_the_vocabulary_does_not_know_gets_the_word_of_its_idea(self):
        ideas = [{"label": "x", "type": "実用品", "must": ["ミニ黒板"], "items": [item("a", "ミニ黒板 木製 小さい"), item("b", "ミニ黒板 白"), item("c", "ミニ黒板 壁掛け")]}]
        cfg = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None}
        html = build.top_picks(cfg, DATA(ideas), "k")
        self.assertEqual(html.count('class="item-blurb">ミニ黒板'), 3)
        self.assertNotIn("気になる品", html)


if __name__ == "__main__":
    unittest.main()
