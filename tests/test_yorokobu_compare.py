"""商品比較 (sites/yorokobu/compare.py): the score, the tables, the pages and what they must say."""
import json
import re
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sites.yorokobu import build, compare, compare_fetch, content
from tests.yorokobu_data import with_musts

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}
FILTERS = {"min_review_count": 5, "min_review_average": 3.8, "min_price": 500, "ng_words": ["ジャンク"], "relaxed": {"min_review_count": 0, "min_review_average": 0},
           "max_per_list": 12}
FUTURE = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d 09:59")
PAST = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d 09:59")


def item(i, price=2000, rating=4.5, reviews=100, ship=True, gift=False, shop=None, name=None, **kw):
    return {"code": f"s{i % 5}:{i}", "name": name or f"タンブラー ステンレス 保温 ギフト {i}", "price": price, "url": f"https://item.rakuten.co.jp/s{i % 5}/{i}/", "image": "https://thumbnail.image.rakuten.co.jp/x.jpg?_ex=300x300",
            "shop": shop or f"店{i % 5}", "shop_code": f"s{i % 5}", "reviews": reviews, "rating": rating, "available": True, "free_shipping": ship, "gift": gift, "appoint": False, **kw}


GROUP = {"slug": "tumbler", "label": "タンブラー", "query": "タンブラー ギフト", "words": ["タンブラー"]}


def raw_with(items, slug="tumbler"):
    return {"version": 1, "fetched_at": "2026-10-14T05:40:00+09:00", "groups": {slug: items}}


class ScoreTest(unittest.TestCase):
    def test_the_weights_add_up_to_a_hundred_and_a_table_is_scored_among_its_own_products(self):
        self.assertEqual(compare.W_PRICE + compare.W_REVIEW + compare.W_SHIP + compare.W_GIFT, 100)
        rows = compare.score_table([item(1, price=1000, ship=True, gift=True), item(2, price=3000, ship=False, gift=False)])
        by = {r["code"]: r for r in rows}
        cheap, dear = by["s1:1"], by["s2:2"]
        self.assertEqual(cheap["parts"][0], compare.W_PRICE)                    # the cheapest gets all of the price part
        self.assertEqual(dear["parts"][0], 0)                                   # the dearest none
        self.assertEqual((cheap["parts"][2], cheap["parts"][3], dear["parts"][2], dear["parts"][3]), (10, 10, 0, 0))
        self.assertTrue(all(0 <= r["total"] <= 100 for r in rows))
        self.assertEqual(rows[0]["code"], "s1:1")                               # sorted by the total

    def test_few_reviews_do_not_beat_many(self):
        rows = compare.score_table([item(1, rating=5.0, reviews=2), item(2, rating=4.6, reviews=1500), item(3, rating=4.5, reviews=300), item(4, rating=4.4, reviews=200)])
        by = {r["code"]: r for r in rows}
        self.assertLess(by["s1:1"]["bayes"], by["s2:2"]["bayes"])               # 5.0 from two reviews is below 4.6 from 1500

    def test_a_running_point_multiplier_lowers_the_effective_price_and_an_ended_one_does_not(self):
        build.SALE_NOW = None
        run = item(1, price=3000, point_rate=10, point_end=FUTURE)
        old = item(2, price=3000, point_rate=10, point_end=PAST)
        self.assertEqual(compare.points_of(run), 300)
        self.assertEqual(compare.effective(run), 2700)
        self.assertEqual(compare.points_of(old), 0)
        self.assertEqual(compare.effective(old), 3000)
        self.assertEqual(compare.points_of(item(3)), 0)

    def test_a_table_of_one_price_does_not_divide_by_zero(self):
        rows = compare.score_table([item(i, price=2000) for i in range(1, 9)])
        self.assertEqual(len(rows), 8)


class ViewTest(unittest.TestCase):
    def view(self, items, group=GROUP):
        return compare.view(raw_with(items, group["slug"]), FILTERS, [group])

    def test_nothing_without_data_and_a_kind_with_too_few_products_or_shops_is_left_out(self):
        self.assertIsNone(compare.view(None, FILTERS, [GROUP]))
        self.assertIsNone(self.view([item(i) for i in range(1, 6)]))                          # 5 products
        self.assertIsNone(self.view([{**item(i), "shop_code": "one"} for i in range(1, 12)]))                       # one shop only
        ok = self.view([item(i) for i in range(1, 15)])
        self.assertTrue(ok and ok["groups"][0]["n"] >= compare.MIN_ITEMS)

    def test_products_of_another_kind_ads_and_one_shops_flood_are_not_in_the_table(self):
        items = [item(i) for i in range(1, 10)] + [item(20, name="マグカップ ギフト 陶器"), item(21, name="ジャンク タンブラー", price=900)]
        items += [{**item(30 + k), "shop_code": "flood", "shop": "あふれる店", "code": f"flood:{k}"} for k in range(8)]
        v = self.view(items)["groups"][0]
        names = [r["name"] for r in v["rows"]]
        self.assertFalse(any("マグカップ" in n or "ジャンク" in n for n in names))
        self.assertLessEqual(sum(1 for r in v["rows"] if r["shop_code"] == "flood"), compare.PER_SHOP)

    def test_the_table_shows_at_most_twenty_and_is_scored_again_among_those(self):
        items = [{**item(i, price=1000 + i * 100), "shop_code": f"x{i}"} for i in range(1, 60)]
        v = self.view(items)["groups"][0]
        self.assertEqual(v["n"], compare.MAX_ROWS)
        self.assertEqual(max(r["parts"][0] for r in v["rows"]), compare.W_PRICE)         # the cheapest of the table has the full price part
        self.assertEqual(min(r["parts"][0] for r in v["rows"]), 0)


class FetchTest(unittest.TestCase):
    def test_every_kind_has_a_query_words_and_a_unique_slug(self):
        gs = compare_fetch.groups()
        self.assertGreaterEqual(len(gs), 20)
        self.assertEqual(len({g["slug"] for g in gs}), len(gs))
        for g in gs:
            self.assertTrue(g["query"] and g["words"] and g["label"], g)

    def test_the_fetch_asks_three_times_per_kind_and_keeps_each_product_once(self):
        calls = []

        class Fake:
            def search(self, **p):
                calls.append(p)
                return [{"itemName": "タンブラー ギフト", "itemCode": "a:1", "itemUrl": "https://item.rakuten.co.jp/a/1/", "itemPrice": 1500, "mediumImageUrls": [{"imageUrl": "https://thumbnail.image.rakuten.co.jp/x.jpg"}],
                         "shopName": "店", "shopCode": "a", "reviewCount": 10, "reviewAverage": 4.5, "availability": 1, "postageFlag": 0, "giftFlag": 0, "pointRate": 5, "pointRateEndTime": "2026-10-20 09:59"}]

        out = compare_fetch.fetch(Fake(), [GROUP], now=datetime(2026, 10, 14, 5, 40), log=lambda *a, **k: None)
        self.assertEqual(len(calls), len(compare_fetch.PASSES))
        self.assertEqual({c["sort"] for c in calls}, {"standard", "-reviewCount"})
        self.assertEqual(len(out["groups"]["tumbler"]), 1)
        self.assertEqual(out["groups"]["tumbler"][0]["point_rate"], 5)
        self.assertTrue(out["fetched_at"].startswith("2026-10-14T05:40"))


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        gs = compare_fetch.groups()
        raw = {"version": 1, "fetched_at": "2026-10-14T05:40:00+09:00", "groups": {gs[0]["slug"]: [item(i, price=1000 + 150 * i, reviews=20 + i, name=f"{gs[0]['words'][0]} ステンレス ギフト {i}", point_rate=5 if i % 4 == 0 else 1, point_end=FUTURE if i % 4 == 0 else "") for i in range(1, 16)]}}
        cls.slug = gs[0]["slug"]
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 14), compare_data=raw)
        cls.none = tempfile.TemporaryDirectory()
        build.render_site(cls.c, items, CFG, Path(cls.none.name), release=True, today=date(2026, 10, 14))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.none.cleanup()

    def read(self, rel, root=None):
        return ((root or self.root) / rel).read_text(encoding="utf-8")

    def test_without_data_there_are_no_pages_and_no_tile(self):
        self.assertFalse((Path(self.none.name) / "compare").exists())
        self.assertNotIn("/compare/", self.read("index.html", Path(self.none.name)))
        self.assertNotIn("/compare/", self.read("tool/index.html", Path(self.none.name)))

    def test_the_hub_the_tile_the_tool_page_and_the_sitemap_lead_to_the_comparison(self):
        self.assertIn(f'href="/compare/{self.slug}/"', self.read("compare/index.html"))
        self.assertIn('href="/compare/"', self.read("index.html"))
        self.assertIn('href="/compare/"', self.read("tool/index.html"))
        self.assertIn("/compare/", self.read("sitemap.xml"))

    def test_a_table_page_shows_every_number_with_its_date_and_prints_its_formula(self):
        html = self.read(f"compare/{self.slug}/index.html")
        self.assertEqual(html.count('class="cmp-row"'), 15)
        for needle in ("総合点のつけ方", "実質価格", "2026年10月14日 5:40", "「最安」とは言えません", "価格・在庫は2026年10月14日 5:40時点の情報です", 'data-score=', 'data-points=', "/assets/compare.js"):
            self.assertIn(needle, html, needle)
        self.assertIn("ポイント約", html)                                         # the rows with a running multiplier say the points
        self.assertEqual(len(re.findall(r'<li class="cmp-row"', html)), len(re.findall(r'class="btn" href="https://hb\.afl\.rakuten\.co\.jp/hgc/AFF\.ID/trk', html)))   # every row's button is the affiliate link

    def test_the_page_says_why_amazon_is_not_in_the_table_and_does_not_show_an_amazon_price(self):
        html = self.read(f"compare/{self.slug}/index.html")
        self.assertIn("Amazonの価格はこの表には入っていません", html)
        self.assertIn("Amazonのアソシエイトとして", html)                           # a page with an Amazon link carries the Associates sentence
        self.assertNotRegex(html, r"amazon[^\"<]{0,80}[0-9]{3,}円")
        hub = self.read("compare/index.html")
        self.assertIn("いまは楽天市場の商品だけを比べています", hub)

    def test_the_rows_keep_the_formula_the_page_prints(self):
        html = self.read(f"compare/{self.slug}/index.html")
        scores = [int(x) for x in re.findall(r'data-score="(\d+)"', html)]
        self.assertEqual(scores, sorted(scores, reverse=True))                      # in the page the rows are in the order of the score
        self.assertTrue(all(0 <= s <= 100 for s in scores))


@unittest.skipUnless(compare.DATA.exists(), "data/yorokobu_compare.json has not been fetched yet")
class RealDataTest(unittest.TestCase):
    """The snapshot the daily workflow committed, through the same view and the site-wide checker the deploy runs."""

    def test_the_real_snapshot_makes_sound_tables_and_pages(self):
        from sokuhou import sitecheck
        c = content.load()
        raw = compare.load()
        v = compare.view(raw, c["filters"])
        self.assertTrue(v and len(v["groups"]) >= 10, "the real data gives tables for at least ten kinds")
        for g in v["groups"]:
            self.assertGreaterEqual(g["shops"], compare.MIN_SHOPS, g["slug"])
            totals = [r["total"] for r in g["rows"]]
            self.assertEqual(totals, sorted(totals, reverse=True), g["slug"])
            self.assertTrue(all(r["price"] > 0 and r["url"].startswith("https://") for r in g["rows"]), g["slug"])
        cfg = json.loads((Path(build.__file__).parent / "config.json").read_text(encoding="utf-8"))
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), c)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build.render_site(c, items, cfg, out, release=True, today=date(2026, 10, 14), compare_data=raw)
            self.assertEqual(sitecheck.check_dir(out, cfg["site_url"]), [])
            self.assertEqual(len(list((out / "compare").glob("*/index.html"))), len(v["groups"]))


if __name__ == "__main__":
    unittest.main()
