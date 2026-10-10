import json
import unittest
import urllib.error
from datetime import datetime

from sites.yorokobu import fetch, picking
from sites.yorokobu.content import pair_key
from sokuhou import rakuten

TIERS = [
    {"slug": "under3000", "label": "3,000円以内", "min": 0, "max": 3000},
    {"slug": "3000-5000", "label": "3,000〜5,000円", "min": 3000, "max": 5000},
    {"slug": "over20000", "label": "20,000円以上", "min": 20000, "max": None},
]
FILTERS = {"min_review_count": 10, "min_review_average": 4.0, "ng_words": ["訳あり", "中古"], "max_per_list": 3,
           "tiers": TIERS}
CONTENT = {
    "pairs": [
        {"occasion": "birthday", "recipient": "boyfriend", "queries": ["誕生日 彼氏", "彼氏 ギフト"], "tiers": ["under3000", "3000-5000"],
         "ideas": [{"label": "財布", "type": "実用品", "query": "メンズ 財布 ギフト", "why": "毎日使います。"},
                   {"label": "名入れ", "type": "思い出・名入れ", "query": "名入れ ペン", "why": "世界にひとつです。"}]},
        {"occasion": "mothers-day", "recipient": "mother", "queries": ["母の日 花"], "tiers": ["over20000"],
         "ideas": [{"label": "花", "type": "実用品", "query": "母の日 花", "why": "華やかです。"}]},
    ],
    "tiers": {t["slug"]: t for t in TIERS},
    "filters": FILTERS,
}


def raw_item(code, price, shop="s1", reviews=50, rating=4.5, name=None, **kw):
    return {"itemName": name or f"商品{code}", "itemCode": code, "itemPrice": price, "itemUrl": f"https://item.rakuten.co.jp/{shop}/{code}/",
            "mediumImageUrls": [f"https://thumbnail.image.rakuten.co.jp/@0_mall/{shop}/{code}.jpg?_ex=128x128"],
            "availability": 1, "reviewCount": reviews, "reviewAverage": str(rating), "shopName": f"店{shop}",
            "shopCode": shop, "postageFlag": 0, "giftFlag": 1, **kw}


class FakeTransport:
    def __init__(self, items_for=lambda url: [], fail=None):
        self.urls, self.items_for, self.fail = [], items_for, fail

    def __call__(self, url, headers):
        self.urls.append((url, headers))
        if self.fail:
            exc = self.fail(len(self.urls))
            if exc:
                raise exc
        return json.dumps({"Items": self.items_for(url)}).encode()


def client(transport, **kw):
    return rakuten.Client("APP", "KEY", "https://yorokobu-present.com/", affiliate_id="AFF", min_interval=0,
                          sleep=lambda s: None, transport=transport, **kw)


class NormalizeTest(unittest.TestCase):
    def test_keeps_the_fields_the_site_needs_and_resizes_the_image(self):
        n = rakuten.normalize(raw_item("a1", 3980))
        self.assertEqual((n["code"], n["price"], n["shop"], n["reviews"], n["rating"]), ("a1", 3980, "店s1", 50, 4.5))
        self.assertTrue(n["image"].endswith("a1.jpg?_ex=300x300"))
        self.assertTrue(n["free_shipping"] and n["available"] and n["gift"])

    def test_items_without_price_image_or_https_link_are_dropped(self):
        self.assertIsNone(rakuten.normalize(raw_item("a", 0)))
        self.assertIsNone(rakuten.normalize({**raw_item("a", 100), "mediumImageUrls": []}))
        self.assertIsNone(rakuten.normalize({**raw_item("a", 100), "itemUrl": "http://x"}))

    def test_image_urls_may_be_objects(self):
        x = {**raw_item("a", 100), "mediumImageUrls": [{"imageUrl": "https://t/x.jpg?_ex=128x128"}]}
        self.assertEqual(rakuten.normalize(x)["image"], "https://t/x.jpg?_ex=300x300")

    def test_affiliate_link_with_and_without_a_tracking_id(self):
        self.assertTrue(rakuten.affiliate_link("A.B", "trk", "https://item.rakuten.co.jp/s/x/").startswith("https://hb.afl.rakuten.co.jp/hgc/A.B/trk?pc="))
        self.assertTrue(rakuten.affiliate_link("A.B", None, "https://x").startswith("https://hb.afl.rakuten.co.jp/hgc/A.B/?pc="))


class UrlAndTitleTest(unittest.TestCase):
    WRAPPED = ("https://hb.afl.rakuten.co.jp/hgc/g00qk1uo.hgz7e6c9.g00qk1uo.hgz7f5ea/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fakuse-one%2Fsai109-a%2F"
               "&m=http%3A%2F%2Fm.rakuten.co.jp%2Fakuse-one%2Fi%2F10014842%2F&rafcid=wsc_i_is_APP")

    def test_the_apis_own_affiliate_redirect_is_unwrapped(self):
        self.assertEqual(rakuten.clean_item_url(self.WRAPPED), "https://item.rakuten.co.jp/akuse-one/sai109-a/")
        self.assertEqual(rakuten.clean_item_url("https://item.rakuten.co.jp/s/x/"), "https://item.rakuten.co.jp/s/x/")
        self.assertEqual(rakuten.clean_item_url("https://item.rakuten.co.jp/s/x/?rafcid=wsc_i_ra_0123"), "https://item.rakuten.co.jp/s/x/")   # the API's own tracking is dropped
        n = rakuten.normalize({**raw_item("a1", 2000), "itemUrl": self.WRAPPED})
        self.assertEqual(n["url"], "https://item.rakuten.co.jp/akuse-one/sai109-a/")

    def test_promotions_are_dropped_from_titles(self):
        raw = "クーポン有10/4/20時〜10/9/1:59 名入れ ギフト 財布 ベルト 【送料無料】 ≪540円で世界に一つ≫ 刻印"
        self.assertEqual(rakuten.clean_title(raw), "名入れ ギフト 財布 ベルト 刻印")
        self.assertEqual(rakuten.clean_title("【ポイント10倍】短い"), "【ポイント10倍】短い")  # nothing meaningful left: keep the original

    def test_the_build_links_through_our_id_to_the_plain_item_page(self):
        from sites.yorokobu import build
        cfg = {"rakuten_affiliate_id": "OUR.ID", "rakuten_tracking_id": "trk"}
        card = build.item_card(cfg, {**rakuten.normalize(raw_item("a1", 2000)), "url": self.WRAPPED})
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/OUR.ID/trk?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fakuse-one%2Fsai109-a%2F", card)
        self.assertNotIn("g00qk1uo", card)


class ClientTest(unittest.TestCase):
    def test_sends_credentials_affiliate_id_and_referer(self):
        t = FakeTransport(lambda u: [raw_item("a", 100)])
        items = client(t).search(keyword="花", hits=5)
        url, headers = t.urls[0]
        self.assertEqual(len(items), 1)
        for part in ("applicationId=APP", "accessKey=KEY", "affiliateId=AFF", "formatVersion=2", "hits=5"):
            self.assertIn(part, url)
        self.assertEqual(headers["Referer"], "https://yorokobu-present.com/")

    def test_retries_on_429_then_succeeds(self):
        def fail(n):
            return urllib.error.HTTPError("u", 429, "slow", {}, None) if n == 1 else None
        t = FakeTransport(lambda u: [raw_item("a", 100)], fail=fail)
        self.assertEqual(len(client(t).search(keyword="x")), 1)
        self.assertEqual(len(t.urls), 2)

    def test_gives_up_after_the_retries_and_reports_other_http_errors(self):
        always = FakeTransport(fail=lambda n: urllib.error.HTTPError("u", 503, "down", {}, None))
        with self.assertRaises(rakuten.RakutenError):
            client(always).search(keyword="x")
        self.assertEqual(len(always.urls), 3)
        bad = FakeTransport(fail=lambda n: urllib.error.URLError("boom"))
        with self.assertRaises(rakuten.RakutenError):
            client(bad).search(keyword="x")

    def test_spaces_requests(self):
        slept, now = [], [0.0]
        c = rakuten.Client("A", "K", "https://x/", min_interval=1.1, transport=FakeTransport(), sleep=slept.append,
                           clock=lambda: now[0])
        c.search(keyword="a")
        c.search(keyword="b")
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0], 1.1)


class PickingTest(unittest.TestCase):
    def items(self):
        return [rakuten.normalize(x) for x in [
            raw_item("a", 2000, "s1", reviews=500, rating=4.8),
            raw_item("b", 2500, "s1", reviews=300, rating=4.7),
            raw_item("c", 2800, "s1", reviews=200, rating=4.6),    # third item of shop s1: over the per-shop cap
            raw_item("d", 1500, "s2", reviews=5, rating=5.0),      # too few reviews
            raw_item("e", 1800, "s3", reviews=100, rating=3.5),    # rating too low
            raw_item("f", 1900, "s4", reviews=100, rating=4.6, name="訳あり 商品"),
            raw_item("g", 2900, "s5", reviews=50, rating=4.4),
            raw_item("h", 4000, "s6", reviews=80, rating=4.5),     # other tier
            {**raw_item("i", 1000, "s7"), "availability": 0},      # sold out
        ]]

    def test_filters_buckets_ranks_and_caps_per_shop(self):
        out = picking.pick(self.items(), TIERS[0], FILTERS)
        self.assertEqual([i["code"] for i in out], ["a", "b", "g"])

    def test_option_listings_and_trinkets_are_dropped(self):
        f = {**FILTERS, "min_price": 700, "ng_words": FILTERS["ng_words"] + ["別売"]}
        cheap = rakuten.normalize(raw_item("c1", 540, "s9"))
        option = rakuten.normalize(raw_item("c2", 1500, "s8", name="名入れ専用ページ ※商品は別売りです"))
        good = rakuten.normalize(raw_item("c3", 1500, "s7"))
        self.assertEqual([i["code"] for i in picking.pick([cheap, option, good], TIERS[0], f)], ["c3"])

    def test_tier_boundaries(self):
        self.assertTrue(picking.in_tier(3000, TIERS[0]))
        self.assertFalse(picking.in_tier(3000, TIERS[1]))
        self.assertTrue(picking.in_tier(3001, TIERS[1]) and picking.in_tier(5000, TIERS[1]))
        self.assertTrue(picking.in_tier(1_000_000, TIERS[2]))

    def test_duplicates_are_removed(self):
        it = rakuten.normalize(raw_item("a", 2000))
        self.assertEqual(len(picking.pick([it, dict(it)], TIERS[0], FILTERS)), 1)


class FetchTest(unittest.TestCase):
    def test_plan_is_one_search_per_idea(self):
        reqs = fetch.plan(CONTENT)
        self.assertEqual([(r["pair"], r["idea"]) for r in reqs], [("birthday-boyfriend", 0), ("birthday-boyfriend", 1), ("mothers-day-mother", 0)])
        self.assertEqual(reqs[0]["params"]["keyword"], "メンズ 財布 ギフト")

    def test_collect_builds_ideas_and_budget_lists_per_page(self):
        def items_for(url):
            if "shopCode=2gaoe" in url:
                return [raw_item("p1", 9800, "2gaoe", reviews=0, rating=0)]
            return [raw_item("x1", 2000, "s1"), raw_item("x2", 4000, "s2"), raw_item("x3", 25000, "s3")]
        data = fetch.collect(CONTENT, client(FakeTransport(items_for)), now=datetime(2026, 10, 7, 7, 0))
        self.assertEqual((data["version"], data["fetched_at"]), (2, "2026-10-07T07:00:00"))
        bd = data["pairs"]["birthday-boyfriend"]
        self.assertEqual([i["label"] for i in bd["ideas"]], ["財布", "名入れ"])
        # an item is shown under one idea only
        all_codes = [i["code"] for idea in bd["ideas"] for i in idea["items"]]
        self.assertEqual(len(all_codes), len(set(all_codes)))
        self.assertEqual([i["code"] for i in bd["tiers"]["under3000"]], ["x1"])
        self.assertEqual([i["code"] for i in bd["tiers"]["3000-5000"]], ["x2"])
        self.assertEqual([i["code"] for i in data["pairs"]["mothers-day-mother"]["tiers"]["over20000"]], ["x3"])
        self.assertEqual(len(data["portrait"]), 1)

    def test_a_short_budget_tier_gets_price_bounded_searches(self):
        calls = []

        def items_for(url):
            calls.append(url)
            return [raw_item("x1", 2000, "s1")]
        fetch.collect(CONTENT, client(FakeTransport(items_for)), now=datetime(2026, 10, 7, 7, 0))
        self.assertTrue(any("minPrice=3001" in u and "maxPrice=5000" in u for u in calls))      # tier 3,000-5,000 stayed empty
        self.assertTrue(any("minPrice=20001" in u for u in calls))

    def test_products_for_the_wrong_person_never_reach_the_page(self):
        def items_for(url):
            return [raw_item("m1", 2000, "s1", name="本革 メンズ 長財布"), raw_item("w1", 2100, "s2", name="レディース 長財布"),
                    raw_item("u1", 2200, "s3", name="メンズ レディース 兼用 財布")]
        data = fetch.collect(CONTENT, client(FakeTransport(items_for)), now=datetime(2026, 10, 7, 7, 0))
        mom = [i["code"] for t in data["pairs"]["mothers-day-mother"]["tiers"].values() for i in t] +               [i["code"] for idea in data["pairs"]["mothers-day-mother"]["ideas"] for i in idea["items"]]
        self.assertNotIn("m1", mom)
        self.assertIn("w1", mom)
        bf = [i["code"] for idea in data["pairs"]["birthday-boyfriend"]["ideas"] for i in idea["items"]]
        self.assertIn("m1", bf)
        self.assertNotIn("w1", bf)

    def test_collect_refuses_a_fetch_where_most_pages_are_empty(self):
        with self.assertRaises(rakuten.RakutenError):
            fetch.collect(CONTENT, client(FakeTransport(lambda u: [])))


if __name__ == "__main__":
    unittest.main()
