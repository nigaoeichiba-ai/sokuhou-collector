"""kaidoki のセール取得の試行: ログに商品データ(名前・URL・画像・店名・価格)と鍵が出ないこと、セール判定の読み方。"""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from sites.kaidoki.tools import sale_probe as P

NOW = 1_800_000_000
SECRET_NAME, SECRET_URL, SECRET_SHOP, SECRET_IMG = "ひみつの商品名XYZ", "https://store.example/ITEMURL", "秘密ストアQQ", "https://img.example/IMGURL"


def hit(i, default=10000, disc=8000, start=NOW - 100, end=NOW + 86400):
    return {"code": f"c{i}", "name": SECRET_NAME, "url": SECRET_URL, "price": disc, "image": {"medium": SECRET_IMG},
            "priceLabel": {"defaultPrice": default, "discountedPrice": disc, "periodStart": start, "periodEnd": end},
            "review": {"count": 50, "rate": 4.5},
            "seller": {"sellerId": "s1", "name": SECRET_SHOP, "isBestSeller": True, "review": {"count": 500, "rate": 4.6}}}


class FakeYahoo:
    calls = 0

    def search(self, **p):
        self.calls += 1
        if p.get("results") == 1:
            return {"totalResultsAvailable": 7}
        if "is_discounted" not in p and p.get("genre_category_id") is None:
            return {"hits": [hit(1), {**hit(2), "priceLabel": {}}], "totalResultsAvailable": 99}
        return {"hits": [hit(1), hit(2, start=0, end=0)], "totalResultsAvailable": 1234}


class JudgeTest(unittest.TestCase):
    def test_ms_and_seconds_are_both_read(self):
        self.assertEqual(P.to_seconds(NOW * 1000), NOW)
        self.assertEqual(P.to_seconds(NOW), NOW)

    def test_stats(self):
        st = P.yahoo_stats([hit(1), hit(2, start=0, end=0), {**hit(3), "priceLabel": {}}], NOW)
        self.assertEqual((st["got"], st["label"], st["period"], st["active_now"], st["ends_3d"], st["good_shops"]), (3, 2, 1, 1, 1, 1))
        self.assertEqual(st["pct"], {"10-29": 2})

    def test_rakuten_point_up_needs_a_rate_of_2_or_more(self):
        v = P.rakuten_view({"pointRate": 5, "pointRateEndTime": "2099-01-01 09:59"}, NOW)
        self.assertTrue(v["up_with_end"])
        self.assertFalse(P.rakuten_view({"pointRate": 1, "pointRateEndTime": "2099-01-01 09:59"}, NOW)["up"])


class NoLeakTest(unittest.TestCase):
    def test_the_log_has_no_product_data_and_the_store_has(self):
        buf, store = io.StringIO(), {}
        with redirect_stdout(buf):
            P.run_yahoo("SECRETKEY", store, pages=1, client=FakeYahoo(), now=NOW)
        out = buf.getvalue()
        for s in (SECRET_NAME, SECRET_URL, SECRET_SHOP, SECRET_IMG, "SECRETKEY", "ITEMURL", "IMGURL"):
            self.assertNotIn(s, out)
        self.assertIn("スマホ", out)
        items = store["genres"]["phone"]["items"]
        self.assertTrue(items and items[0]["name"] == SECRET_NAME)         # 商品データは store(非公開の置き場所へ行く)にだけある

    def test_the_yahoo_error_has_no_url_or_key(self):
        import urllib.error
        from io import BytesIO
        err = urllib.error.HTTPError("https://x/?appid=SECRETKEY", 403, "no", {}, BytesIO(b"bad appid SECRETKEY"))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(P.YahooError) as cm:
                P.Yahoo("SECRETKEY", gap=0).search(query="x")
        self.assertNotIn("SECRETKEY", str(cm.exception))

    def test_rakuten_log_has_no_product_data(self):
        from sokuhou import rakuten as R
        item = {"itemCode": "a:1", "itemName": SECRET_NAME, "itemUrl": SECRET_URL, "itemPrice": 1000, "shopName": SECRET_SHOP, "shopCode": "s",
                "pointRate": 5, "pointRateStartTime": "2026-11-12 00:00", "pointRateEndTime": "2099-01-01 09:59", "mediumImageUrls": [SECRET_IMG]}
        body = json.dumps({"count": 321, "Items": [item]}).encode()
        mk = lambda ref: R.Client("APPID", "KEY", ref, min_interval=0, transport=lambda u, h: body, sleep=lambda s: None)
        buf, store = io.StringIO(), {}
        with redirect_stdout(buf):
            P.run_rakuten("APPID", "KEY", store, None, now=NOW, make_client=mk)
        out = buf.getvalue()
        for s in (SECRET_NAME, SECRET_URL, SECRET_SHOP, SECRET_IMG, "APPID", "KEY"):
            self.assertNotIn(s, out)
        self.assertEqual(store["genres"]["phone"]["items"][0]["itemName"], SECRET_NAME)


if __name__ == "__main__":
    unittest.main()
