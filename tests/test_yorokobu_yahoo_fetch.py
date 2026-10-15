"""Yahoo!ショッピング itemSearch: 取り込み(正規化)、ID を漏らさないこと、リクエストの間隔。"""
import unittest
import urllib.error
from io import BytesIO
from unittest import mock

from sites.yorokobu import yahoo_fetch as Y

VC = {"sid": "3784606", "pid": "892726918"}
HIT = {"name": "ギフト 商品", "url": "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784606&pid=892726918&vc_url=x", "price": 2000, "code": "shop_item1", "inStock": True,
       "image": {"medium": "https://item-shopping.c.yimg.jp/i/g/x"}, "review": {"count": 12, "rate": 4.5},
       "shipping": {"code": 2, "name": "送料無料"},
       "point": {"amount": 20, "times": 1, "bonusAmount": 10, "lyLimitedBonusAmount": 30, "premiumAmount": 99, "premiumBonusAmount": 99},
       "seller": {"name": "店", "sellerId": "shop"}}


class NormalizeTest(unittest.TestCase):
    def test_fields(self):
        it = Y.normalize(HIT)
        self.assertEqual((it["price"], it["reviews"], it["rating"], it["free_shipping"], it["ship"], it["shop"], it["shop_code"]), (2000, 12, 4.5, True, 2, "店", "shop"))
        self.assertEqual(it["points"], 60)                                    # the member's own: base + store bonus + limited; the premium-member fields are not counted
        self.assertTrue(it["url"].startswith("https://ck.jp.ap.valuecommerce.com/"))

    def test_only_the_free_shipping_code_counts_as_free(self):
        for code, free in ((1, False), (2, True), (3, False)):
            self.assertEqual(Y.normalize({**HIT, "shipping": {"code": code}})["free_shipping"], free)

    def test_items_that_cannot_be_shown_are_dropped(self):
        for bad in ({**HIT, "price": 0}, {**HIT, "url": "http://x"}, {**HIT, "name": ""}):
            self.assertIsNone(Y.normalize(bad))


class ClientTest(unittest.TestCase):
    def test_the_affiliate_id_is_the_referral_link_up_to_vc_url(self):
        self.assertEqual(Y.vc_affiliate_id(VC), "http://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784606&pid=892726918&vc_url=")

    def test_an_error_never_carries_the_client_id(self):
        c = Y.Client("SECRETID123", VC, min_interval=0)
        err = urllib.error.HTTPError("https://x/?appid=SECRETID123", 403, "no", {}, BytesIO(b'{"error":"bad appid SECRETID123"}'))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(Y.YahooError) as cm:
                c.search("お歳暮")
        self.assertNotIn("SECRETID123", str(cm.exception))

    def test_requests_stay_under_30_a_minute(self):
        c = Y.Client("id", VC)
        self.assertGreaterEqual(c.min_interval, 2.0)                          # 60 / 30

    def test_a_429_is_waited_out_once_then_the_request_is_repeated(self):
        c = Y.Client("SECRETID123", VC, min_interval=0, retry_wait=0)
        limit = urllib.error.HTTPError("https://x/", 429, "slow", {}, BytesIO(b'{"Status":429}'))
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"hits":[]}'
        with mock.patch("urllib.request.urlopen", side_effect=[limit, ok]):
            self.assertEqual(c.search("x"), {"hits": []})
        self.assertEqual(c.calls, 2)

    def test_a_second_429_is_an_error(self):
        c = Y.Client("SECRETID123", VC, min_interval=0, retry_wait=0)
        errs = [urllib.error.HTTPError("https://x/", 429, "slow", {}, BytesIO(b"{}")) for _ in range(2)]
        with mock.patch("urllib.request.urlopen", side_effect=errs):
            with self.assertRaises(Y.YahooError):
                c.search("x")


if __name__ == "__main__":
    unittest.main()
