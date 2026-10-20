"""Rakuten Web Service terms, checked for the pages of yorokobu (audit of 2026-10-17, items 2 / 4 / 7; asked by the owner on 2026-10-20):
- Article 8: a part made with the Web Service (the product cards and their section) carries Rakuten's links only; another mall's links are a part of their own;
- Article 10 (1) (7): the shop's title is not altered and kept in a title attribute: the links of the cards have no title attribute;
- Article 10 (1) (6): no page compares prices across malls or calls a product the cheapest or the better deal."""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, dataroom
from tests.test_yorokobu_boards import board_content
from tests.test_yorokobu_dataroom import CFG, inflated

AMAZON = re.compile(r'href="https?://(?:www\.)?amazon\.co\.jp/')
VC = re.compile(r'href="(?:https?:)?//ck\.jp\.ap\.valuecommerce\.com/')
BLOCK = re.compile(r"<(section|div)\b[^>]*>(?:(?!</\1>).)*?</\1>", re.S)


def sections_with_cards_and_other_malls(html: str) -> list[str]:
    """Every section / div that holds a product card and a link to Amazon or Yahoo! (the cards' own part)."""
    bad = []
    for m in re.finditer(r"<section\b[^>]*>.*?</section>|<div class=\"shop-range\">.*?</div>(?=<div class=\"shop-range\">|</section>|<section|$)", html, re.S):
        s = m.group(0)
        if '<li class="item"' in s and (AMAZON.search(s) or VC.search(s)):
            bad.append(s[:80])
    return bad


class MallPartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rows = (dataroom.MIN_ROWS, dataroom.MIN_PER_ROW)
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = 2, 8
        cdir = Path(cls.tmp.name) / "c"
        cdir.mkdir()
        cls.c = board_content(cdir)
        cls.out = Path(cls.tmp.name) / "site"
        cfg = {**CFG, "amazon_tracking_id": "amazonmacs-22"}
        build.render_site(cls.c, inflated(), cfg, cls.out, release=True, today=date(2026, 10, 7))
        cls.pages = {p.relative_to(cls.out).as_posix(): p.read_text(encoding="utf-8") for p in cls.out.rglob("*.html")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = cls.rows
        build.RANKING_ON = False
        build.DATA_ON = False

    def test_no_part_with_product_cards_links_to_amazon_or_yahoo(self):
        for rel, t in self.pages.items():
            self.assertEqual(sections_with_cards_and_other_malls(t), [], rel)

    def test_the_budget_ranges_of_the_data_room_keep_the_amazon_buttons_in_a_part_of_their_own(self):
        shop = [t for rel, t in self.pages.items() if rel.startswith("data/") and 'id="shop"' in t]
        self.assertTrue(shop, "the fixture builds no data page with the budget ranges")
        for t in shop:
            part = t[t.index('id="shop"'):]
            rakuten_part = part[: part.index("</section>")]
            self.assertNotIn("amazon.co.jp", rakuten_part)
            self.assertIn('id="shop-amazon"', t)
            self.assertIn("Amazonで探す", t[t.index('id="shop-amazon"'):])

    def test_the_check_would_catch_a_card_part_with_an_amazon_button(self):
        bad = '<section class="block"><ul><li class="item">x</li></ul><a href="https://www.amazon.co.jp/s?k=a&amp;tag=b">Amazonで探す</a></section>'
        self.assertEqual(len(sections_with_cards_and_other_malls(bad)), 1)
        ok = '<section><ul><li class="item">x</li></ul></section><section><a href="https://www.amazon.co.jp/s?k=a">Amazonで探す</a></section>'
        self.assertEqual(sections_with_cards_and_other_malls(ok), [])

    def test_no_link_to_a_shop_page_carries_a_title_attribute(self):
        for rel, t in self.pages.items():
            self.assertEqual(re.findall(r'<a [^>]*href="[^"]*(?:rakuten|valuecommerce)[^"]*"[^>]*\btitle=', t), [], rel)

    def test_no_page_calls_a_product_the_cheapest_or_compares_malls(self):
        for rel, t in self.pages.items():
            text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", t, flags=re.S))
            for w in ("どちらがお得", "どっちがお得", "お得な方", "最安値", "価格比較"):
                self.assertNotIn(w, text, f"{rel}: {w}")
            for m in re.finditer(r"最安", text):
                self.assertIn("「最安」とは言えません", text[m.start() - 1: m.start() + 12], f"{rel}: 最安 outside the disclaimer")

    def test_amazon_parts_show_no_price(self):
        for rel, t in self.pages.items():
            for m in re.finditer(r'<section class="block cmp-other".*?</section>|<section class="block" id="shop-amazon".*?</section>', t, re.S):
                self.assertNotIn("¥", m.group(0), rel)


if __name__ == "__main__":
    unittest.main()
