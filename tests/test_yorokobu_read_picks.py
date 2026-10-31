"""Owner's approval of 2026-11-01 (B1): the 101 reading articles had no product link; each now ends with 「この話題の人気の3点」, three image cards of the first theme it names that has
enough products.  The cards are the theme pages' own (the picture carries the link, the words are the site's); nothing of the shop is stored in the repository."""
import re
import unittest

from sites.yorokobu import build
from tests.test_yorokobu_card_kinds import DATA, FRIDGE, item

CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None}


def world(products_per_idea=3):
    ideas = [dict(i) for i in FRIDGE]
    ideas[0]["items"] = [item(f"a{k}", f"マグネットボード {k} 冷蔵庫 白", reviews=50 + k) for k in range(products_per_idea)]
    ideas[1]["items"] = [item(f"b{k}", f"マグネット カレンダー {k} 冷蔵庫 月間", reviews=40 + k) for k in range(products_per_idea)]
    ideas[2]["items"] = [item(f"c{k}", f"マグネット メモクリップ {k} 10個", reviews=30 + k) for k in range(products_per_idea)]
    d = DATA(ideas)
    d["pairs"] = {"k1": {"ideas": ideas, "tiers": {}}, "k2": {"ideas": [], "tiers": {}}}
    d["c"] = {"theme": {"fridge": {"key": "k1", "name": "冷蔵庫伝言", "title": "t"}, "empty": {"key": "k2", "name": "空", "title": "t2"}}}
    d["live_themes"] = [{"slug": "fridge"}, {"slug": "empty"}]
    return d


class ArticlePicksTest(unittest.TestCase):
    def test_an_article_gets_three_cards_of_its_theme_with_the_picture_linked_and_no_name_link(self):
        html = build.article_picks(CFG, world(), {"themes": ["fridge"]})
        self.assertIn("この話題の人気の3点", html)
        self.assertEqual(html.count('<li class="item"'), 3)
        self.assertEqual(html.count('class="item-img"><a href="https://hb.afl.rakuten.co.jp/'), 3)
        self.assertNotRegex(html, r'<p class="item-blurb"><a ')                      # the words are not a link
        self.assertIn('href="/theme/fridge/"', html)
        self.assertNotIn("title=", html)

    def test_the_first_theme_without_enough_products_is_skipped_for_the_next(self):
        html = build.article_picks(CFG, world(), {"themes": ["empty", "fridge"]})
        self.assertEqual(html.count('<li class="item"'), 3)

    def test_no_block_when_no_theme_has_enough_products_or_the_article_names_none(self):
        self.assertEqual(build.article_picks(CFG, world(0), {"themes": ["fridge"]}), "")
        self.assertEqual(build.article_picks(CFG, world(), {"themes": ["empty"]}), "")
        self.assertEqual(build.article_picks(CFG, world(), {"themes": []}), "")
        self.assertEqual(build.article_picks(CFG, world(), {}), "")

    def test_a_theme_that_is_not_live_is_not_used(self):
        d = world()
        d["live_themes"] = []
        self.assertEqual(build.article_picks(CFG, d, {"themes": ["fridge"]}), "")

    def test_the_block_names_the_time_of_the_prices(self):
        self.assertIn("時点", build.article_picks(CFG, world(), {"themes": ["fridge"]}))

    def test_no_shop_data_in_the_content_of_the_articles(self):
        import json
        from pathlib import Path
        text = (Path(build.HERE) / "content" / "articles.json").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"rakuten\.co\.jp|thumbnail\.image")


if __name__ == "__main__":
    unittest.main()
