"""Yahoo!ショッピング itemSearch: 取り込み(正規化)、ID を漏らさないこと、リクエストの間隔。"""
import unittest
import urllib.error
from io import BytesIO
from unittest import mock

from sites.yorokobu import yahoo_fetch as Y

VC = {"sid": "3784606", "pid": "892726918"}
HIT = {"name": "ギフト 商品", "url": "https://shopping.yahoo.co.jp/products/x", "price": 2000, "code": "shop_item1", "inStock": True,
       "image": {"medium": "https://item-shopping.c.yimg.jp/i/j/x"}, "review": {"count": 12, "rate": 4.5},
       "shipping": {"code": 2}, "point": {"amount": 40}, "seller": {"name": "店", "sellerId": "shop"}}


class NormalizeTest(unittest.TestCase):
    def test_fields(self):
        it = Y.normalize(HIT)
        self.assertEqual((it["price"], it["reviews"], it["rating"], it["free_shipping"], it["point_rate"], it["shop"]), (2000, 12, 4.5, True, 2.0, "店"))

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

    def test_requests_are_spaced(self):
        c = Y.Client("id", VC)
        self.assertGreaterEqual(c.min_interval, 1.0)


if __name__ == "__main__":
    unittest.main()
