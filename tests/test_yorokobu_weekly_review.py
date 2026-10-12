"""Findings of the weekly review of 2026-10-12 (a product once on a page, a page's first four really of the page's idea, nothing for summer on a winter page,
nothing made for women at the front of a man's page).  Each test repeats the incident, so a change that brings it back fails here."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, relevance
from tests.yorokobu_data import rich_boyfriend

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None, "adsense_pub_id": None}


def codes_of(html: str) -> list[str]:
    return re.findall(r'<li class="item"[^>]*?data-code="([^"]+)"', html)


class OnePlacePerProductTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel: str) -> str:
        return (self.root / rel / "index.html").read_text(encoding="utf-8")

    def test_no_product_stands_twice_on_a_gift_or_theme_page(self):
        pages = [p for sub in ("gift", "theme", "for") for p in (self.root / sub).glob("*/index.html")]
        self.assertGreater(len(pages), 4)
        for f in pages:
            codes = [c for c in codes_of(f.read_text(encoding="utf-8")) if c != "p1"]
            self.assertEqual(len(codes), len(set(codes)), f"{f.parent.name}: {sorted(c for c in set(codes) if codes.count(c) > 1)}")

    def test_the_page_with_many_products_has_first_four_cards_and_a_list_of_the_rest(self):
        html = self.read("gift/birthday-boyfriend")
        top = re.search(r'<section class="top-picks".*?</section>', html, re.S).group(0)
        self.assertEqual(len(codes_of(top)), 4)
        cards = re.search(r'<section class="proposals".*?</section>', html, re.S).group(0)
        rest = re.search(r'<section class="rest".*?</section>', html, re.S).group(0)
        self.assertTrue(codes_of(cards) and codes_of(rest))
        self.assertFalse(set(codes_of(top)) & set(codes_of(cards)))
        self.assertFalse(set(codes_of(cards)) & set(codes_of(rest)))
        # the filters come before the cards they work on
        self.assertLess(html.index('id="browse"'), html.index('class="proposals"'))

    def test_a_page_whose_products_all_fit_in_the_first_four_still_has_its_filters_but_no_empty_list(self):
        html = self.read("theme/thanks-daily")
        self.assertNotIn('class="items grid-all"', html)
        self.assertNotIn('class="rest"', html)
        self.assertNotIn("data-sort", html)             # nothing to sort

    def test_a_recipient_page_does_not_repeat_the_products_of_its_liked_rows(self):
        for f in (self.root / "for").glob("*/index.html"):
            codes = codes_of(f.read_text(encoding="utf-8"))
            self.assertEqual(len(codes), len(set(codes)), f.parent.name)


class FirstFourTest(unittest.TestCase):
    def item(self, code, name, price=2000):
        return {"code": code, "name": name, "price": price, "url": "https://item.rakuten.co.jp/s/x/", "image": "https://thumbnail.image.rakuten.co.jp/x.jpg",
                "shop": "s", "shop_code": code, "reviews": 100, "rating": 4.5, "available": True, "free_shipping": True, "gift": False, "appoint": False}

    def d(self, ideas):
        return {"pairs": {"k": {"ideas": ideas, "tiers": {}}}}

    def test_a_product_whose_idea_word_stands_far_back_in_its_title_does_not_lead_the_page(self):
        # the plum wine "布袋福梅" (a maker's name) led 発表会帰りに荷物になりにくい一品; an eco bag that lists ランドリー led 風が強い日の洗濯
        must_bag = ["巾着袋", "ラッピング袋", "ギフト袋"]
        must_laundry = ["ランドリーバッグ", "洗濯バッグ", "洗濯袋"]
        ideas = [
            {"label": "布袋", "type": "ファッション小物", "must": must_bag, "items": [self.item("w1", "布袋福梅 720ml 梅酒 ブランデー ギフト"), self.item("b1", "巾着袋 ギフト 小さめ"), self.item("b2", "ラッピング袋 リボン付き")]},
            {"label": "洗濯バッグ", "type": "実用品", "must": must_laundry, "items": [self.item("l1", "LOQI エコバッグ ストラップなし トートバッグ 手提げ袋 コンパクト 軽量 折りたたみ 大容量 ランドリーバッグ"),
                                                                                self.item("l2", "洗濯バッグ ランドリーバッグ 防水")]},
            {"label": "x", "type": "食べもの・飲みもの", "must": ["クッキー"], "items": [self.item("c1", "クッキー 詰め合わせ")]},
        ]
        shown = [i["code"] for i in build.top_shown(self.d(ideas), "k")]
        self.assertNotIn("w1", shown)
        self.assertNotIn("l1", shown)
        self.assertEqual(set(shown), {"b1", "b2", "l2", "c1"})

    def test_a_page_with_fewer_than_three_such_products_has_no_first_four(self):
        ideas = [{"label": "a", "type": "実用品", "must": ["湯呑み"], "items": [self.item("a1", "湯呑み 白"), self.item("a2", "梅酒 湯呑み風")]}]
        self.assertEqual(build.top_shown(self.d(ideas), "k"), [])


class RulesTest(unittest.TestCase):
    CARD_CASE = "名刺入れ 女性用 レディース 本革 カードケース おしゃれ 薄型 大容量 プレゼント ギフト 母の日 誕生日 ユニセックス"

    def test_a_title_that_opens_as_women_s_is_not_shown_to_a_husband_even_when_it_says_unisex_later(self):
        self.assertFalse(relevance.fits(self.CARD_CASE, "husband"))        # /gift/birthday-husband/ led with this
        self.assertTrue(relevance.fits(self.CARD_CASE, "wife"))

    def test_a_title_that_names_both_or_neither_at_the_front_is_kept(self):
        self.assertTrue(relevance.fits("名刺入れ メンズ レディース 兼用 本革", "husband"))
        self.assertTrue(relevance.fits("名刺入れ 本革 薄型 ユニセックス レディース", "husband"))      # the front says it is for both
        self.assertTrue(relevance.fits("名刺入れ 本革 薄型 おしゃれ", "husband"))

    def test_a_men_s_title_is_not_shown_to_a_wife_even_when_it_says_unisex_later(self):
        self.assertFalse(relevance.fits("メンズ 財布 二つ折り 男性用 本革 薄型 コンパクト 大容量 カード ギフト プレゼント 誕生日 ユニセックス", "wife"))


class WinterContentTest(unittest.TestCase):
    def test_no_page_of_a_winter_occasion_mentions_goods_for_summer_anywhere_in_its_content(self):
        c = content.load()
        picks = json.loads((Path(content.__file__).parent / "content" / "picks.json").read_text(encoding="utf-8"))
        seen = 0
        for p in content.pages(c):
            if p.get("occasion") not in relevance.WINTER_OCCASIONS:
                continue
            seen += 1
            text = json.dumps(p, ensure_ascii=False) + json.dumps(picks.get(content.pair_key(p), []), ensure_ascii=False)
            self.assertEqual([w for w in relevance.SUMMER_ONLY if w in text], [], content.pair_key(p))      # the year-end grandfather page had a 甚平 idea, its text and its picks
        self.assertGreater(seen, 10)

    def test_the_year_end_grandfather_page_has_a_winter_idea_where_the_summer_one_was(self):
        c = content.load()
        p = next(x for x in content.pages(c) if content.pair_key(x) == "year-end-gathering-grandfather")
        labels = [i["label"] for i in p["ideas"]]
        self.assertIn("あったかひざ掛け", labels)
        self.assertEqual(len(labels), 4)


class ThemeMustTest(unittest.TestCase):
    def must(self, slug, label):
        c = content.load()
        t = next(x for x in c["themes"] if x["slug"] == slug)
        return next(i for i in t["ideas"] if i["label"] == label)["must"]

    def test_a_plum_wine_of_a_maker_named_hotei_is_not_a_cloth_bag(self):
        self.assertFalse(relevance.fits_idea("布袋福梅 720ml 梅酒 ブランデー にごり12.4度 ギフト 梅果肉", self.must("recital-carry-home", "布袋")))
        self.assertTrue(relevance.fits_idea("巾着袋 ギフト 小さめ 無地", self.must("recital-carry-home", "布袋")))

    def test_a_pinch_hanger_for_hats_is_not_a_laundry_clip_and_a_laundry_idea_is_not_soup(self):
        self.assertFalse(relevance.fits_idea("帽子収納 単品 2個 省スペース 帽子ハンガー キャップハンガー ピンチハンガー", self.must("windy-balcony-laundry", "強力ピンチ")))
        self.assertTrue(relevance.fits_idea("ステンレス 洗濯ピンチ 風で飛ばない 20個", self.must("windy-balcony-laundry", "強力ピンチ")))
        c = content.load()
        t = next(x for x in c["themes"] if x["slug"] == "long-commute-ease")
        self.assertNotIn("粉末スープ", [i["label"] for i in t["ideas"]])


if __name__ == "__main__":
    unittest.main()
