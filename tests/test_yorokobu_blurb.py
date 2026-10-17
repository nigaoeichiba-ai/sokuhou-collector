"""商品カードの一言 (sites/yorokobu/blurb.py): 店の商品名の代わりに、当サイトの語で、ブランド・種類・数値だけ。商品名のラベルは付けない。リンクにしない。"""
import json
import re
import unittest
from pathlib import Path

from sites.yorokobu import blurb, build

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {g["slug"]: g for g in json.loads((ROOT / "sites" / "yorokobu" / "content" / "compare.json").read_text(encoding="utf-8"))["groups"]}


def line(title, slug=None, **kw):
    g = GROUPS.get(slug) if slug else None
    return blurb.blurb(build.strip_occasions(title), kind=g["label"] if g else None, must=g["words"] if g else None, **kw)


class LineTest(unittest.TestCase):
    def test_a_brand_of_the_dictionary_a_kind_and_one_number(self):
        self.assertEqual(line("ロクシタン ハンドクリーム ギフト 女性 誕生日プレゼント 人気 プチギフト パリスガールボックス ミニ 10ml 北欧風"), "ロクシタンのハンドクリーム(10ml)")
        self.assertEqual(line("お茶 爽健美茶 緑茶 飲み物 ドリンク 600ml"), "爽健美茶の緑茶(600ml)")
        self.assertEqual(line("ヨックモック プティ サンク デリス 5種25個入 ハロウィン 焼き菓子 詰め合わせ プレゼント", "baked-sweets"), "ヨックモックの焼き菓子(5種)")

    def test_the_kind_of_the_page_wins_over_the_search_words_of_the_title(self):
        t = "スイーツ お菓子 ギフト 内祝い 個包装 井桁堂 アーモンドのガトーセレクション（24個） 焼き菓子"
        self.assertEqual(line(t, "baked-sweets"), "焼き菓子(24個)")

    def test_no_kind_and_no_brand_gives_no_line(self):
        self.assertEqual(line("さんご（花水引）1セット：20筋"), "")
        self.assertEqual(line(""), "")

    def test_the_dictionary_of_one_product_overrides(self):
        blurb._OVERRIDE = {"shop:1": "凛菓のティラミス"}
        try:
            self.assertEqual(blurb.blurb("なんでも 販促 語", code="shop:1"), "凛菓のティラミス")
        finally:
            blurb._OVERRIDE = None

    def test_the_kind_words_of_an_idea_stay_in_the_line(self):
        self.assertEqual(blurb.blurb("テスト商品a2 贈り物にぴったりのギフトセット 語0", must=["語0"]), "語0")

    def test_pairing_of_earphones_is_not_a_pair(self):
        self.assertNotIn("ペア", line("Bluetooth 6.0 イヤホン ノイズキャンセリング 自動ペアリング", "earphones"))


@unittest.skipUnless((ROOT / "data" / "yorokobu_compare.json").exists(), "the Rakuten data is in the private store (privatedata.py), not in the repository: this run did not pull it")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads((ROOT / "data" / "yorokobu_compare.json").read_text(encoding="utf-8"))["groups"]
        cls.rows = [(slug, i["name"], line(i["name"], slug)) for slug, g in data.items() if slug in GROUPS for i in g]

    def test_most_products_get_a_line_and_few_only_a_brand(self):
        self.assertGreater(len(self.rows), 500)
        have = [r for r in self.rows if r[2]]
        self.assertGreater(len(have) / len(self.rows), 0.9)
        self.assertLess(sum("の品" in r[2] for r in have) / len(self.rows), 0.05)

    def test_the_line_is_short_and_has_no_search_words_and_no_copy_of_the_title(self):
        words = set(blurb.vocab()) | set(blurb.vocab2()) | {n for _, n in blurb.brands()}
        for slug, title, b in self.rows:
            if not b:
                continue
            self.assertLessEqual(len(b), 40, (title, b))
            body = re.sub(r"\(.*?\)", "", b)
            for w in sorted(words | set(GROUPS[slug]["words"]) | {GROUPS[slug]["label"]}, key=len, reverse=True):
                body = body.replace(w, "")
            for w in ("ギフト", "プレゼント", "送料無料", "おしゃれ", "人気", "商品名"):
                self.assertNotIn(w, body, (title, b))
            self.assertLess(len(body), 8, (title, b))                                      # what is left of the line, apart from the site's own words, is nothing like a run of the title


class CardTest(unittest.TestCase):
    def cfg(self):
        return {"site_url": "https://yorokobu-present.com", "site_name": "x", "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "t", "amazon_tracking_id": "az-22"}

    def item(self):
        return {"code": "s:1", "name": "ロクシタン ハンドクリーム ギフト 女性 10ml", "price": 2000, "url": "https://item.rakuten.co.jp/s/1/",
                "image": "https://thumbnail.image.rakuten.co.jp/x.jpg?_ex=300x300", "shop": "s", "shop_code": "s", "reviews": 10, "rating": 4.5,
                "available": True, "free_shipping": True, "gift": False, "appoint": False}

    def test_a_card_has_the_picture_as_a_link_the_site_words_as_plain_text_and_rakutens_link_only(self):
        html = build.item_card(self.cfg(), self.item())
        self.assertIn('class="item-blurb">ロクシタンのハンドクリーム(10ml)</p>', html)
        self.assertNotRegex(html, r"<h3><a ")                                              # no link on the words
        self.assertNotIn("ハンドクリーム ギフト", html)                                       # the shop's title is not on the card
        self.assertNotIn("title=", html)
        self.assertIn("_ex=128x128", html)                                                  # the picture as the API gives it
        self.assertIn('width="128" height="128"', html)
        self.assertNotIn("amazon.co.jp", html)                                              # a Rakuten part has no link to another mall (terms Article 8)
        self.assertEqual(len(re.findall(r'<a class="item-img" href="https://hb\.afl\.rakuten', html)), 1)
        self.assertIn('alt="ロクシタンのハンドクリーム(10ml)"', html)

    def test_the_rank_and_the_heart_are_a_row_above_the_picture_never_inside_its_link(self):
        html = build.item_card(self.cfg(), self.item(), rank=1)
        top = re.search(r'<div class="item-top">(.*?)</div><a class="item-img"', html, re.S)
        self.assertIsNotNone(top)
        self.assertIn('class="rank r1"', top.group(1))
        self.assertIn('class="fav"', top.group(1))
        link = re.search(r'<a class="item-img".*?</a>', html, re.S).group(0)
        self.assertNotIn("rank", link)
        self.assertNotIn("fav", link)
        self.assertNotIn("<button", link)

    def test_the_stylesheet_puts_nothing_over_a_product_picture_and_never_crops_it(self):
        css = (ROOT / "sites" / "yorokobu" / "assets" / "style.css").read_text(encoding="utf-8")
        for sel in (".item .rank", ".item .fav, .imgbox .fav", ".imgbox", ".cmp-img .fav"):
            rule = re.search(re.escape(sel) + r" \{([^}]*)\}", css)
            self.assertIsNotNone(rule, sel)
            self.assertNotIn("position: absolute", rule.group(1), sel)
        for sel in (".item-img img", ".cmp-img img", ".pick-img img", ".feat-photo img", ".pick-hl img"):
            rule = re.search(re.escape(sel) + r" \{([^}]*)\}", css)
            self.assertIsNotNone(rule, sel)
            self.assertIn("object-fit: contain", rule.group(1), sel)
        self.assertNotRegex(css, r"\.yh-row \.cmp-no \{[^}]*position: absolute")           # nor the Yahoo! row's number

    def test_a_product_the_site_cannot_describe_shows_the_picture_and_the_buttons_only(self):
        it = {**self.item(), "name": "さんご（花水引）1セット：20筋"}
        html = build.item_card(self.cfg(), it)
        self.assertNotIn("item-blurb", html)
        self.assertIn('alt="楽天市場の商品ページ"', html)
        self.assertIn("楽天市場で見る", html)


if __name__ == "__main__":
    unittest.main()
