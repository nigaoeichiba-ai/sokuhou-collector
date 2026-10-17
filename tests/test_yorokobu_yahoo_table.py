"""商品比較: Yahoo!ショッピングの別の表(楽天の表と混ぜない、画像なし、点数は共通項目、クレジット付き)。"""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, compare, compare_fetch, content
from tests.test_yorokobu_compare import CFG, FIX, item
from tests.yorokobu_data import with_musts

CFG_Y = {**CFG, "yahoo_vc": {"sid": "3784606", "pid": "892728268"}}
CREDIT_LINK = '<a href="https://developer.yahoo.co.jp/sitemap/">Web Services by Yahoo! JAPAN</a>'
RAKUTEN_AT = "2026-10-14T05:40:00+09:00"


def yitem(i, shop=None, price=None, reviews=40, rating=4.5, ship=2, name=None, points=0):
    return {"code": f"shop{i}_item", "name": name or f"タンブラー ギフト {i}", "price": price or 2000 + 300 * i,
            "url": f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784606&pid=892728268&vc_url=https%3A%2F%2Fstore.shopping.yahoo.co.jp%2Fshop{i}%2Fitem{i}.html",
            "image": f"https://item-shopping.c.yimg.jp/i/g/shop{i}_item", "shop": shop or f"ストア{i}", "shop_code": f"shop{i}",
            "reviews": reviews, "rating": rating, "available": True, "ship": ship, "free_shipping": ship == 2, "points": points}


def yraw(items, at="2026-10-14T05:55:00+09:00"):
    return {"version": 1, "fetched_at": at, "groups": {"tumbler": items}}


def group(slug="tumbler"):
    return next(g for g in compare_fetch.groups() if g["slug"] == slug)


class ViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filters = content.load()["filters"]
        cls.rak = {"fetched_at": RAKUTEN_AT}

    def y(self, items, at="2026-10-14T05:55:00+09:00"):
        return compare.y_view(yraw(items, at), self.rak, group(), self.filters)

    def test_a_table_needs_enough_products_and_shops(self):
        self.assertIsNone(self.y([yitem(i) for i in range(1, 5)]))                                        # 4 products
        self.assertIsNone(self.y([{**yitem(i), "shop_code": "one"} for i in range(1, 8)]))               # one shop only
        self.assertIsNotNone(self.y([yitem(i) for i in range(1, 9)]))

    def test_stores_the_programme_bars_are_left_out(self):
        items = [yitem(i) for i in range(1, 8)] + [yitem(8, shop="ディノス PayPayモール店"), yitem(9, shop="喜信堂")]
        y = self.y(items)
        self.assertEqual(y["n"], 7)
        self.assertTrue(all("ディノス" not in r["shop"] and "喜信堂" not in r["shop"] for r in y["rows"]))

    def test_at_most_three_products_of_one_shop(self):
        items = [{**yitem(i), "shop_code": "big", "shop": "大きな店"} for i in range(1, 7)] + [yitem(i) for i in range(7, 12)]
        y = self.y(items)
        self.assertEqual(sum(1 for r in y["rows"] if r["shop_code"] == "big"), 3)

    def test_a_file_from_another_time_than_the_rakuten_one_is_not_shown(self):
        items = [yitem(i) for i in range(1, 9)]
        self.assertIsNotNone(self.y(items, "2026-10-16T05:00:00+09:00"))
        self.assertIsNone(self.y(items, "2026-10-17T05:55:00+09:00"))
        self.assertIsNone(self.y(items, "2026-10-10T05:55:00+09:00"))

    def test_the_score_has_price_review_and_shipping_only_and_sums_to_at_most_100(self):
        rows = self.y([yitem(i, price=2000 + 500 * i, reviews=10 + 20 * i, ship=2 if i % 2 else 1) for i in range(1, 9)])["rows"]
        self.assertEqual(len(rows[0]["parts"]), 3)
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r["total"], r["price"], r["code"])))
        self.assertTrue(all(0 <= r["total"] <= 100 for r in rows))
        cheapest = min(rows, key=lambda r: r["price"])
        self.assertEqual(cheapest["parts"][0], compare.YW_PRICE)
        self.assertEqual(max(rows, key=lambda r: r["price"])["parts"][0], 0)

    def test_conditional_free_shipping_gets_no_shipping_points(self):
        rows = self.y([yitem(i, ship=3 if i == 1 else 2) for i in range(1, 9)])["rows"]
        self.assertEqual(next(r for r in rows if r["code"] == "shop1_item")["parts"][2], 0)


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        gs = {g["slug"]: g for g in compare_fetch.groups()}
        raw = {"version": 1, "fetched_at": RAKUTEN_AT,
               "groups": {slug: [item(i, price=1000 + 150 * i, reviews=20 + 7 * i, name=f"{gs[slug]['words'][0]} ギフト {i}") for i in range(1, 16)] for slug in ("catalog-gift", "tumbler")}}
        yd = yraw([yitem(i, points=40 if i == 2 else 0, ship=3 if i == 3 else 2) for i in range(1, 9)])
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG_Y, cls.root, release=True, today=date(2026, 10, 15), compare_data=raw, yahoo_data=yd)
        cls.none = tempfile.TemporaryDirectory()
        build.render_site(cls.c, items, CFG_Y, Path(cls.none.name), release=True, today=date(2026, 10, 15), compare_data=raw)
        cls.stale = tempfile.TemporaryDirectory()
        build.render_site(cls.c, items, CFG_Y, Path(cls.stale.name), release=True, today=date(2026, 10, 15), compare_data=raw, yahoo_data=yraw(yd["groups"]["tumbler"], "2026-10-20T05:55:00+09:00"))

    @classmethod
    def tearDownClass(cls):
        for t in (cls.tmp, cls.none, cls.stale):
            t.cleanup()

    def read(self, rel, root=None):
        return (Path(root or self.root.as_posix()) / rel).read_text(encoding="utf-8")

    def section(self, html):
        return re.search(r'<section class="block yh" id="yahoo">.*?</section>', html, re.S).group(0)

    def test_the_yahoo_table_is_its_own_section_below_the_rakuten_one(self):
        html = self.read("compare/tumbler/index.html")
        self.assertLess(html.index('id="cmp-list"'), html.index('id="yahoo"'))
        sec = self.section(html)
        self.assertEqual(sec.count('class="yh-row"'), 8)
        self.assertNotIn("cmp-row", sec)                                  # the rows of the Rakuten list (and its sorting script) are not touched
        self.assertIn("楽天市場の表とは混ぜていません", sec)
        self.assertIn("下の別の表", html)

    def test_each_row_links_the_response_url_as_it_is_with_the_counter(self):
        sec = self.section(self.read("compare/tumbler/index.html"))
        for i in range(1, 9):
            self.assertIn(f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784606&amp;pid=892728268&amp;vc_url=https%3A%2F%2Fstore.shopping.yahoo.co.jp%2Fshop{i}%2Fitem{i}.html", sec)
        self.assertEqual(sec.count('rel="nofollow sponsored noopener"'), 16)                  # the photo and the button of each row (the words of a row are not a link)
        self.assertEqual(sec.count("servlet/gifbanner?sid=3784606&amp;pid=892728268"), 8)

    def test_the_pictures_are_the_products_own_photos_from_yahoos_image_host_at_the_size_given_and_nothing_else(self):
        sec = self.section(self.read("compare/tumbler/index.html"))
        imgs = re.findall(r"<img [^>]*>", re.sub(r'<img src="https://ad\.jp\.ap\.valuecommerce\.com[^>]*>', "", sec))      # the programme's 1x1 counters are not pictures
        self.assertEqual(len(imgs), 8)
        for im in imgs:
            self.assertRegex(im, r'src="https://item-shopping\.c\.yimg\.jp/i/g/shop\d_item"')                      # the photo URL as the API gave it (never rewritten)
            self.assertRegex(im, r'^<img src="[^"]+" alt="[^"]*">$')                                               # src and alt only: the 76px is the CSS of its box (.yh-img), the file is the API's
            self.assertNotIn("style=", im)
        self.assertNotIn("s.yimg.jp", sec)                                                                         # no Yahoo! logo, banner or page image
        self.assertNotIn("/images/", sec)

    def test_y_image_takes_only_photos_from_yahoos_image_host(self):
        self.assertEqual(compare.y_image({"image_small": "https://item-shopping.c.yimg.jp/i/c/a_b"}), "https://item-shopping.c.yimg.jp/i/c/a_b")
        self.assertEqual(compare.y_image({"image": "https://item-shopping.c.yimg.jp/i/g/a_b"}), "https://item-shopping.c.yimg.jp/i/g/a_b")           # no small one: the given one, unchanged
        for bad in ({"image": ""}, {"image": "https://s.yimg.jp/images/shp/logo.png"}, {"image": "https://example.test/i/g/x"}, {"image_small": "http://item-shopping.c.yimg.jp/i/c/x"}, {}):
            self.assertEqual(compare.y_image(bad), "", bad)

    def test_no_words_the_programme_or_the_law_makes_risky(self):
        sec = self.section(self.read("compare/tumbler/index.html"))
        for w in ("最安", "実質", "お得"):
            self.assertNotIn(w, sec)

    def test_shipping_is_shown_as_the_stores_category_and_points_apart_from_the_price(self):
        sec = self.section(self.read("compare/tumbler/index.html"))
        self.assertIn("送料無料", sec)
        self.assertIn("条件つきで送料無料", sec)
        self.assertIn("ポイント約40pt", sec)
        self.assertNotRegex(sec, r"実質")

    def test_the_time_and_the_notice_are_written_and_the_credit_is_there_once_and_unchanged(self):
        html = self.read("compare/tumbler/index.html")
        self.assertIn("2026年10月14日 5:55時点の情報", self.section(html))
        self.assertIn("変わることがあります", self.section(html))
        self.assertEqual(html.count("Begin Yahoo! JAPAN Web Services Attribution Snippet"), 1)
        self.assertEqual(html.count("End Yahoo! JAPAN Web Services Attribution Snippet"), 1)
        self.assertEqual(html.count(CREDIT_LINK), 1)
        self.assertIn('<span style="margin:15px 15px 15px 15px">' + CREDIT_LINK + "</span>", html)

    def test_a_page_without_a_yahoo_table_has_no_credit_and_says_the_old_thing(self):
        for root in (self.none.name, self.stale.name):
            html = self.read("compare/tumbler/index.html", root)
            self.assertNotIn("Web Services by Yahoo! JAPAN", html)
            self.assertNotIn('id="yahoo"', html)
            self.assertIn("この表にYahoo!ショッピングの価格は入っていません", html)

    def test_the_hub_says_where_the_yahoo_tables_are_only_when_there_are_some(self):
        self.assertIn("別の表で載せています", self.read("compare/index.html"))
        self.assertNotIn("別の表で載せています", self.read("compare/index.html", self.none.name))
        self.assertNotIn("Web Services by Yahoo! JAPAN", self.read("compare/index.html"))


if __name__ == "__main__":
    unittest.main()
