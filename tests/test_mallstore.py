"""The shared product shelves (sokuhou/mallstore.py, mallshelf.php.tpl, mallshelf.js, .github/workflows/mall-refresh.yml).

The rule that every test here guards: the repository, the logs, the artifacts and the cache never hold a shop's product name, price, picture or link; only the definition of a shelf is public.
Past failure reproduced on purpose: product data written into a public file (yorokobu 2026-10-17/18: daily/features held shop data and had to be taken out).
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from sokuhou import mallstore, newsite

ROOT = Path(__file__).resolve().parents[1]
TREND = ROOT / "sites" / "trend"


def raw(n, name="防災用 LED 懐中電灯 単3 3本付き", price=1980, reviews=120, rating=4.5, avail=1, shop="shopA"):
    return {"itemName": name, "itemCode": f"{shop}:{n}", "itemUrl": f"https://item.rakuten.co.jp/{shop}/item{n}/", "itemPrice": price,
            "mediumImageUrls": [{"imageUrl": f"https://thumbnail.image.rakuten.co.jp/@0_mall/{shop}/cabinet/{n}.jpg?_ex=128x128"}],
            "shopName": f"店{shop}", "shopCode": shop, "reviewCount": reviews, "reviewAverage": rating, "availability": avail}


class FakeClient:
    def __init__(self, items):
        self.items, self.calls = items, []

    def search(self, **params):
        self.calls.append(params)
        return list(self.items)


SHELF = {"id": "light", "label": "防災用の懐中電灯", "keyword": "防災 懐中電灯", "count": 2, "min_price": 800, "max_price": 8000, "min_reviews": 30, "min_rating": 4.0, "exclude": ["福袋"]}


class Select(unittest.TestCase):
    def test_choice_follows_the_bars_and_one_product_per_shop(self):
        items = [raw(1, avail=0), raw(2, reviews=3), raw(3, rating=3.1), raw(4, name="福袋 懐中電灯"), raw(5, shop="shopB"), raw(6, shop="shopB"), raw(7, shop="shopC"), raw(8, shop="shopD")]
        from sokuhou import rakuten
        got = mallstore.select([rakuten.normalize(x) for x in items], SHELF)
        self.assertEqual([g["code"] for g in got], ["shopB:5", "shopC:7"])        # sold out, few reviews, low rating, excluded word, a second product of one shop: all left out

    def test_the_row_keeps_the_picture_and_the_page_exactly_as_given(self):
        from sokuhou import rakuten
        it = rakuten.normalize(raw(9))
        r = mallstore.row(it)
        self.assertEqual(r["i"], raw(9)["mediumImageUrls"][0]["imageUrl"])             # never rewritten (no _ex change)
        self.assertEqual(r["u"], raw(9)["itemUrl"])
        self.assertNotIn("name", r)                                                    # the shop's title is not kept at all

    def test_build_db_asks_once_per_shelf_with_the_bars_and_drops_an_empty_shelf(self):
        c = FakeClient([raw(1), raw(2, shop="shopB")])
        db = mallstore.build_db([SHELF, dict(SHELF, id="none", min_reviews=10 ** 6)], c, "2026-11-08", log=lambda *_: None)
        self.assertEqual(len(c.calls), 2)
        p = c.calls[0]
        self.assertEqual((p["minPrice"], p["maxPrice"], p["availability"], p["imageFlag"], p["NGKeyword"]), (800, 8000, 1, 1, "福袋"))
        self.assertEqual(list(db["shelves"]), ["light"])
        self.assertEqual(db["updated"], "2026-11-08")

    def test_one_shelf_failing_does_not_stop_the_others_and_the_log_has_no_shop_data(self):
        class Boom(FakeClient):
            def search(self, **params):
                if params["keyword"] == "bad":
                    raise RuntimeError("HTTP 500: {'itemName': '秘密の商品名'}")
                return super().search(**params)
        logs: list[str] = []
        db = mallstore.build_db([dict(SHELF, id="bad", keyword="bad"), SHELF], Boom([raw(1)]), "2026-11-08", log=logs.append)
        self.assertEqual(list(db["shelves"]), ["light"])
        self.assertTrue(logs and all("秘密の商品名" not in l and "RuntimeError" in l or "shelf light" in l for l in logs))


class ApiError(unittest.TestCase):
    def test_an_api_error_shows_its_reason_and_nothing_else_shows_more_than_its_type(self):
        from sokuhou import rakuten

        class Bad(FakeClient):
            def search(self, **params):
                if params["keyword"] == "api":
                    raise rakuten.RakutenError("HTTP 403: {\"error\":\"REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING\"}")
                raise RuntimeError("{'itemName': '秘密の商品名'}")
        logs: list[str] = []
        mallstore.build_db([dict(SHELF, id="a", keyword="api"), dict(SHELF, id="b", keyword="other")], Bad([]), "2026-11-08", log=logs.append)
        self.assertIn("HTTP 403", logs[0])
        self.assertNotIn("秘密の商品名", " ".join(logs))


class Definition(unittest.TestCase):
    def test_a_definition_that_holds_a_product_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "shelves.json").write_text(json.dumps({"shelves": [dict(SHELF, itemName="x")]}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(mallstore.ShelfError):
                mallstore.load_shelves(Path(td))
            (Path(td) / "shelves.json").write_text(json.dumps({"shelves": [SHELF, SHELF]}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(mallstore.ShelfError):
                mallstore.load_shelves(Path(td))
            (Path(td) / "shelves.json").write_text(json.dumps({"shelves": [dict(SHELF, id="../x")]}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(mallstore.ShelfError):
                mallstore.load_shelves(Path(td))

    def test_the_sites_shelves_are_definitions_only(self):
        for r in mallstore.sites_with_shelves():
            for s in mallstore.load_shelves(ROOT / "sites" / r["name"]):
                self.assertTrue(set(s) <= set(mallstore.KEYS))
            text = (ROOT / "sites" / r["name"] / "shelves.json").read_text(encoding="utf-8")
            for bad in ("https://", "item.rakuten", "thumbnail.image", "hb.afl", "円"):
                self.assertNotIn(bad, text)


class Answer(unittest.TestCase):
    DB = {"updated": "2026-11-08", "shelves": {"light": [{"i": "https://thumbnail.image.rakuten.co.jp/a.jpg", "u": "https://item.rakuten.co.jp/s/a/?x=1&y=2", "p": 1980, "r": 4.5, "n": 12}]}}
    AFF = "583f273a.77c989b6.583f273b.0a6a5fff"

    def test_answer_gives_the_picture_the_affiliate_link_and_the_price_only(self):
        st, d = mallstore.answer({"s": "light"}, self.DB, self.AFF)
        self.assertEqual(st, 200)
        it = d["items"][0]
        self.assertEqual(set(it), {"i", "h", "p"})
        self.assertEqual(it["h"], "https://hb.afl.rakuten.co.jp/hgc/" + self.AFF + "/?pc=" + urllib.parse.quote("https://item.rakuten.co.jp/s/a/?x=1&y=2", safe=""))
        self.assertNotIn("m=", it["h"])                                               # nothing added behind the ID: the specification's form (2026-10-18)
        self.assertEqual(d["u"], "2026-11-08")

    def test_bad_or_unknown_shelf(self):
        self.assertEqual(mallstore.answer({"s": "../etc"}, self.DB, self.AFF)[0], 400)
        self.assertEqual(mallstore.answer({}, self.DB, self.AFF)[0], 400)
        self.assertEqual(mallstore.answer({"s": "none"}, self.DB, self.AFF), (200, {"u": "2026-11-08", "items": []}))

    def test_the_php_does_what_the_python_twin_does(self):
        php = mallstore.shelf_php({"site_url": "https://trend-sokuho.com/", "rakuten_affiliate_id": self.AFF, "_site_name_key": "trend"})
        self.assertIn("'https://hb.afl.rakuten.co.jp/hgc/" + self.AFF + "/?pc=' . rawurlencode($r['u'])", php)
        self.assertIn("$home . '/trend-private'", php)                                # a folder beside public_html, never inside it
        self.assertIn("strpos($ref, 'https://trend-sokuho.com/') !== 0", php)          # the pages of this site only
        self.assertIn("preg_match('/^[a-z0-9_-]{1,40}$/', $s)", php)
        self.assertIn("array_slice($rows, 0, 6)", php)
        self.assertNotIn("__", php.replace("__DIR__", ""))                            # every placeholder was filled
        for ch in ("'", " ", "(", ")", "!", "*", "~", "/", "?", "&", "=", ":", "#", "@"):                      # rawurlencode and quote(safe="") agree
            self.assertEqual(urllib.parse.quote("a" + ch + "b", safe=""), "a" + {"'": "%27", " ": "%20", "(": "%28", ")": "%29", "!": "%21", "*": "%2A", "~": "~", "/": "%2F", "?": "%3F", "&": "%26", "=": "%3D", ":": "%3A", "#": "%23", "@": "%40"}[ch] + "b")

    def test_a_site_without_an_affiliate_id_cannot_make_the_php(self):
        with self.assertRaises(mallstore.ShelfError):
            mallstore.shelf_php({"site_url": "https://x.example", "_site_name_key": "x"})


class Card(unittest.TestCase):
    JS = (ROOT / "sokuhou" / "mallshelf.js").read_text(encoding="utf-8")

    def test_the_card_follows_the_owner_rules(self):
        js = self.JS
        self.assertIn('rel = "nofollow sponsored noopener"', js)
        self.assertIn('a.target = "_blank"', js)
        self.assertNotIn("innerHTML", js)                                             # nothing from the API is ever parsed as HTML
        self.assertIn("時点", js)                                                      # the price carries the day
        self.assertIn("PR ", js)                                                       # the PR note is next to the cards
        self.assertIn("box.hidden = false", js)
        self.assertIn("楽天市場で見る", js)
        self.assertNotIn("itemName", js)
        self.assertNotIn("最安", js)                                                   # no "cheapest" claim (Article 10 (1) (6))
        self.assertIn('indexOf("https://hb.afl.rakuten.co.jp/") !== 0', js)           # only Rakuten's own redirect is ever linked
        self.assertNotIn("amazon", js.lower())
        self.assertNotIn("yahoo", js.lower())                                          # no other mall inside a Rakuten part (Article 8 (3))

    def test_the_card_has_no_link_on_the_word_and_the_picture_is_the_link(self):
        js = self.JS
        self.assertIn('li.appendChild(el("span", "shelf-word", label))', js)           # the site's own word as plain text
        self.assertIn("pic.appendChild(img)", js)


class NothingPublic(unittest.TestCase):
    def test_the_built_site_holds_no_product_data(self):
        pages, _ = newsite.build_pages(TREND, release=True)
        blob = "".join(v for v in pages.values() if isinstance(v, str))
        self.assertEqual(mallstore.shop_data_in(blob), [])
        self.assertIn('data-shelf="light"', pages["trend-typhoon32/index.html"])
        self.assertIn("api/shelf.php", pages)                                          # shipped by newsite for any site with shelves.json
        self.assertIn("assets/shelf.js", pages)

    def test_a_site_without_shelves_ships_nothing_extra(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(mallstore.build_files(Path(td), {"site_url": "https://x.example"}), {})

    def test_the_scan_catches_the_past_failure_and_the_repository_has_none(self):
        self.assertTrue(mallstore.shop_data_in('{"image": "https://thumbnail.image.rakuten.co.jp/@0_mall/x/1.jpg"}'))          # product data in a public file (yorokobu 2026-10-18)
        self.assertTrue(mallstore.shop_data_in('"itemName": "x"'))
        self.assertEqual(mallstore.shop_data_in("防災用の懐中電灯"), [])
        for p in (TREND / "content").glob("*.json"):
            self.assertEqual(mallstore.shop_data_in(p.read_text(encoding="utf-8")), [], p.name)
        self.assertEqual(mallstore.shop_data_in((TREND / "shelves.json").read_text(encoding="utf-8")), [])

    def test_every_shelf_in_a_page_is_defined(self):
        defined = {s["id"] for s in mallstore.load_shelves(TREND)}
        for p in (TREND / "content").glob("*.json"):
            for sid in re.findall(r'data-shelf=\\"([a-z0-9_-]+)\\"', p.read_text(encoding="utf-8")):
                self.assertIn(sid, defined, p.name)

    def test_the_workflow_never_commits_caches_or_uploads_the_data(self):
        wf = (ROOT / ".github" / "workflows" / "mall-refresh.yml").read_text(encoding="utf-8")
        code = "\n".join(l for l in wf.splitlines() if not l.lstrip().startswith("#"))
        for bad in ("actions/cache", "upload-artifact", "git add", "git commit", "git push", "contents: write", "--artifact"):
            self.assertNotIn(bad, code)
        self.assertIn("python -m sokuhou.mallstore refresh", code)
        self.assertIn("secrets.RAKUTEN_APP_ID", code)


class Refresh(unittest.TestCase):
    def test_every_site_in_turn_and_an_empty_site_pushes_nothing(self):
        pushed = {}
        rows = [{"name": "trend", "domain": "trend-sokuho.com"}]
        # the real trend shelves, a fake client: every shelf finds the same two products
        failed = mallstore.refresh(rows, lambda r: FakeClient([raw(1), raw(2, shop="shopB")]), "2026-11-08", push_fn=lambda s, db: pushed.setdefault(s, db) and True, root=ROOT, log=lambda *_: None)
        self.assertEqual(failed, 0)
        self.assertEqual(set(pushed), {"trend"})
        self.assertEqual(set(pushed["trend"]["shelves"]), {s["id"] for s in mallstore.load_shelves(TREND)})
        pushed.clear()
        failed = mallstore.refresh(rows, lambda r: FakeClient([]), "2026-11-08", push_fn=lambda s, db: pushed.setdefault(s, db) and True, root=ROOT, log=lambda *_: None)
        self.assertEqual((failed, pushed), (1, {}))                                    # nothing found: the old data on the server stays

    def test_push_without_the_server_secrets_does_nothing(self):
        import os
        keep = {k: os.environ.pop(k, None) for k in ("XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER")}
        try:
            self.assertFalse(mallstore.push("trend", {"updated": "x", "shelves": {}}))
        finally:
            for k, v in keep.items():
                if v is not None:
                    os.environ[k] = v

    def test_push_sends_one_tar_stream_into_the_private_folder(self):
        import os
        calls = []

        class P:
            returncode = 0

        def run(cmd, input=None, capture_output=None):
            calls.append((cmd, input))
            return P()
        os.environ.update({"XSERVER_SSH_KEY": "k", "XSERVER_HOST": "h", "XSERVER_USER": "u"})
        try:
            ok = mallstore.push("trend", {"updated": "2026-11-08", "shelves": {"light": []}}, run=run, sleep=lambda *_: None)
        finally:
            for k in ("XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER"):
                os.environ.pop(k, None)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)
        remote = calls[0][0][-1]
        self.assertIn("~/trend-private", remote)
        self.assertIn("chmod 700", remote)
        self.assertIn("chmod 600", remote)
        self.assertNotIn("public_html", remote)


if __name__ == "__main__":
    unittest.main()
