"""sale-calendar.com /yahoo/: 「いま割引が多いYahoo!ショッピングの店」の欄(sites/kaidoki/shops.py)。

守ること(オーナー厳命 2026-10-17 と 2026-11-12):
  - 店名・件数・店のURL・商品名・価格・画像は、ログにも、ビルドの成果物にも、リポジトリにも入らない(非公開フォルダ → PHP → JS)。
  - 欄の文に、価格・順位・おすすめの語が無い。リンクは MyLink・PR・rel="nofollow sponsored noopener"・target=_blank。クレジットがある。
  - データが無い・古い・店が少ないときは、欄が出ない(PHP も JS も隠す)。鮮度点検が、古い・無い・測れなかったを拾う。
負例: 古いデータ・禁止の店・評価の低い店・終わった店は出ない。ログに店名が出たら落ちる検査が、実際に落とせる。"""
from __future__ import annotations

import io
import json
import os
import re
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")

from sites.kaidoki import shops as S  # noqa: E402
from sites.kaidoki.redesign import affiliate as AFF  # noqa: E402
from sites.kaidoki.redesign.tools import freshness as F  # noqa: E402
from sites.kaidoki.tools import yahoo_shops as Y  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000                       # 2027-01-15 JST の朝
TODAY = "2027-01-15"
SECRET_SHOP, SECRET_ID, SECRET_NAME, SECRET_URL, SECRET_IMG = "ひみつの店QQ", "secretshopqq", "ひみつの商品名XYZ", "https://store.example/ITEMURL", "https://img.example/IMGURL"


def hit(i, shop=0, default=10000, disc=8000, end=NOW + 86400, rev=(500, 4.6), name=None):
    return {"code": f"c{i}", "name": SECRET_NAME, "url": SECRET_URL, "price": disc, "image": {"medium": SECRET_IMG},
            "priceLabel": {"defaultPrice": default, "discountedPrice": disc, "periodStart": NOW - 100, "periodEnd": end},
            "seller": {"sellerId": f"{SECRET_ID}{shop}", "name": name or f"{SECRET_SHOP}{shop}", "review": {"count": rev[0], "rate": rev[1]}}}


def genre_hits(shops=4):
    """4店。店0は3件(割引率 20%・50%)、ほかは1件。"""
    h = [hit(1, 0), hit(2, 0, disc=5000, end=NOW + 3 * 86400), hit(3, 0)]
    h += [hit(10 + s, s) for s in range(1, shops)]
    return h


class FakeYahoo:
    calls = 0

    def search(self, **p):
        self.calls += 1
        hs = genre_hits() if p.get("start", 1) == 1 else []
        return {"hits": hs, "totalResultsAvailable": len(hs)}


class AggregateTest(unittest.TestCase):
    def db(self, hits):
        return S.aggregate({"phone": hits}, NOW, TODAY)

    def test_counts_range_end_and_name_order(self):
        d = self.db(genre_hits())
        rows = d["genres"]["phone"]
        self.assertEqual([r["n"] for r in rows], sorted(r["n"] for r in rows))
        r0 = [r for r in rows if r["id"] == f"{SECRET_ID}0"][0]
        self.assertEqual((r0["c"], r0["lo"], r0["hi"], r0["e"]), (3, 20, 50, "2027-01-18"))
        self.assertEqual(d["updated"], TODAY)

    def test_the_same_item_is_counted_once(self):
        d = self.db(genre_hits() + genre_hits())
        self.assertEqual([r["c"] for r in d["genres"]["phone"] if r["id"] == f"{SECRET_ID}0"], [3])

    def test_a_genre_with_few_shops_is_left_out(self):
        self.assertEqual(self.db(genre_hits(shops=2))["genres"], {})

    def test_negative_shops_that_must_not_appear(self):
        base = genre_hits()
        d = self.db(base + [hit(50, 8, rev=(99, 4.9)), hit(51, 9, rev=(5000, 3.9)), hit(52, 7, name="ディノス 公式"), hit(53, 6, end=NOW - 10), hit(54, 5, default=100, disc=100)])
        ids = {r["id"] for r in d["genres"]["phone"]}
        self.assertEqual(ids, {f"{SECRET_ID}{i}" for i in range(4)})          # 評価の件数が足りない・評価が低い・禁止の店・終わった割引・割引でない商品は入らない

    def test_no_product_data_in_the_rows(self):
        text = json.dumps(self.db(genre_hits()), ensure_ascii=False)
        for s in (SECRET_NAME, SECRET_URL, SECRET_IMG, "ITEMURL", "IMGURL"):
            self.assertNotIn(s, text)

    def test_cap_per_genre(self):
        d = self.db([hit(100 + i, i) for i in range(40)])
        self.assertEqual(len(d["genres"]["phone"]), S.MAX_SHOPS_PER_GENRE)


class NoLeakTest(unittest.TestCase):
    def run_log(self, client):
        buf = io.StringIO()
        with redirect_stdout(buf):
            db = Y.run("SECRETKEY", pages=1, client=client, now=NOW)
        return buf.getvalue(), db

    def test_the_log_has_no_shop_or_product_data(self):
        out, db = self.run_log(FakeYahoo())
        for s in (SECRET_SHOP, SECRET_ID, SECRET_NAME, SECRET_URL, SECRET_IMG, "SECRETKEY", "ITEMURL", "IMGURL", "store.shopping"):
            self.assertNotIn(s, out)
        self.assertIn("スマホ", out)
        self.assertIn("4店", out)
        self.assertTrue(db["genres"])                                   # 集計は戻り値(→ 非公開の置き場所)にだけある

    def test_negative_a_log_that_prints_a_shop_would_be_caught(self):
        class Leaky(FakeYahoo):
            def search(self, **p):
                print("shop", SECRET_SHOP)
                return super().search(**p)
        out, _ = self.run_log(Leaky())
        self.assertIn(SECRET_SHOP, out)                                  # この検査(上のテスト)は、こう出たら落とせる

    def test_the_tool_never_writes_the_data_to_a_file(self):
        src = (ROOT / "sites" / "kaidoki" / "tools" / "yahoo_shops.py").read_text(encoding="utf-8")
        for bad in ("open(", "write_text", "json.dump(", "to_csv"):
            self.assertNotIn(bad, src)

    def test_no_shop_data_is_tracked(self):
        import subprocess
        files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8", "replace").split("\0")
        self.assertEqual([f for f in files if "yahoo_shops" in f and f.endswith((".json", ".csv", ".txt", ".jsonl"))], [])


class AnswerTest(unittest.TestCase):
    db = S.aggregate({"phone": genre_hits(), "tv": genre_hits()}, NOW, TODAY)
    D = date(2027, 1, 15)

    def test_fresh_data_is_given_with_the_mylink(self):
        a = S.answer(self.db, self.D)
        self.assertEqual(a["u"], TODAY)
        self.assertEqual([g["s"] for g in a["genres"]], ["phone", "tv"])
        h = a["genres"][0]["shops"][0]["h"]
        self.assertEqual(h, AFF.vc_href(AFF.VC_PID["yahoo"], f"https://store.shopping.yahoo.co.jp/{self.db['genres']['phone'][0]['id']}/"))
        self.assertTrue(h.startswith("//ck.jp.ap.valuecommerce.com/servlet/referral?sid=3787704&pid=892746565&vc_url="))

    def test_old_missing_or_unreadable_data_shows_nothing(self):
        for d in (date(2027, 1, 18), date(2027, 2, 1), date(2027, 1, 14)):             # 古い(3日後・2週間後)・取得日が未来
            self.assertEqual(S.answer(self.db, d)["genres"], [], d)
        for bad in (None, {}, {"updated": "x", "genres": {}}, {"updated": TODAY, "genres": {}}, "abc"):
            self.assertEqual(S.answer(bad, self.D)["genres"], [], bad)
        self.assertEqual(len(S.answer(self.db, date(2027, 1, 16))["genres"]), 2)       # 1日前までは出す

    def test_a_shop_whose_sale_ended_is_dropped(self):
        self.assertEqual(len(S.answer(self.db, date(2027, 1, 16))["genres"]), 2)       # 終わりが1月16日の店は、16日までは出る
        self.assertEqual(S.answer(self.db, date(2027, 1, 17))["genres"], [])           # 17日には、終わった店を除くと3店に満たないので、欄ごと出ない

    def test_bad_shop_ids_are_dropped(self):
        d = json.loads(json.dumps(self.db))
        for r in d["genres"]["phone"]:
            r["id"] = "a b/../x"
        self.assertEqual([g["s"] for g in S.answer(d, self.D)["genres"]], ["tv"])


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_kaidoki_redesign import build
        cls.pages = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "0", "KAIDOKI_NOW": "2026-11-12T10:00"}, products=[])
        h = cls.pages["yahoo/index.html"]
        m = re.search(r'<section class="content-block shops-box" id="shops" hidden>.*?</section>', h, re.S)
        cls.section = m.group(0) if m else ""
        cls.text = re.sub(r"<style>.*?</style>|<!--.*?-->", "", cls.section, flags=re.S)

    def test_the_box_is_in_the_page_hidden_and_fixed(self):
        self.assertTrue(self.section)
        self.assertEqual(self.pages["yahoo/index.html"].count('id="shops"'), 1)
        self.assertIn(S.HEADING, self.section)
        self.assertIn('<div id="shops-body"></div>', self.section)          # 店のデータは入っていない(JS が後から入れる)
        self.assertNotIn("<li", self.section)
        self.assertIn("/assets/yahoo-shops.js?v=", self.pages["yahoo/index.html"])

    def test_no_price_rank_or_recommendation_words_in_the_box(self):
        visible = re.sub(r"<[^>]+>", "", self.text).replace("おすすめの店を選んだ並びではありません", "")
        for w in ("価格", "円", "順位", "ランキング", "人気", "安い", "最安", "おすすめ", "No.1", "TOP"):
            self.assertNotIn(w, visible, w)
        js = self.pages["assets/yahoo-shops.js"].split("*/", 1)[1]
        for w in ("price", "rank", "価格", "順位"):
            self.assertNotIn(w, js.lower(), w)
        self.assertNotIn("<img", self.text)                                   # 商品画像なし

    def test_pr_credit_and_credit_text(self):
        self.assertIn('<span class="pr-chip">PR</span>', self.section)
        self.assertIn("Web Services by Yahoo! JAPAN", self.section)
        self.assertIn('href="https://developer.yahoo.co.jp/sitemap/"', self.section)

    def test_the_link_the_script_makes_is_sponsored_blank_and_a_mylink(self):
        js = self.pages["assets/yahoo-shops.js"]
        self.assertIn('a.target = "_blank"', js)
        self.assertIn('a.rel = "nofollow sponsored noopener"', js)
        self.assertIn('SID = "3787704"', js)
        self.assertIn('PID = "892746565"', js)
        self.assertIn("gifbanner", js)                                        # 提携先の1x1のカウンター(既存のリンクと同じ)
        self.assertNotIn("innerHTML", js)                                     # 店名は textContent(HTMLとして入れない)
        self.assertNotRegex(js, r"__[A-Z_]+__")        # 差し込み忘れなし

    def test_the_php_hides_old_data_reads_the_private_folder_and_holds_no_shop(self):
        php = self.pages["api/yahoo-shops.php"]
        self.assertIn("/kaidoki-private", php)
        self.assertIn("yahoo_shops.json", php)
        self.assertIn("$age > 2", php)
        self.assertIn("pid=892746565", php)
        self.assertIn("rawurlencode('https://store.shopping.yahoo.co.jp/'", php)
        self.assertIn("Sec-Fetch-Site".upper().replace("-", "_"), php)
        self.assertNotRegex(php.replace("__DIR__", ""), r"__[A-Z_]+__")
        self.assertIn('"phone"', php)

    def test_the_built_pages_hold_no_shop_data(self):
        for rel, html in self.pages.items():
            if isinstance(html, str) and rel.endswith((".html", ".js", ".php", ".xml")):
                self.assertNotIn(SECRET_SHOP, html, rel)

    def test_the_old_build_without_the_redesign_also_gets_the_box(self):
        from tests.test_kaidoki_redesign import build
        old = build({"KAIDOKI_REDESIGN": "0"}, products=[])
        self.assertIn('id="shops"', old["yahoo/index.html"])
        self.assertIn("api/yahoo-shops.php", old)


class WorkflowTest(unittest.TestCase):
    wf = (ROOT / ".github" / "workflows" / "kaidoki-sale-daily.yml").read_text(encoding="utf-8")

    def test_daily_and_by_hand_numbers_only_and_nothing_kept(self):
        self.assertIn('cron: "0 21 * * *"', self.wf)                          # 06:00 JST
        self.assertIn("workflow_dispatch", self.wf)
        self.assertIn("contents: read", self.wf)
        for bad in ("upload-artifact", "actions/cache", "git add", "git commit", "git push", "gh issue", "GITHUB_STEP_SUMMARY", "tee "):
            self.assertNotIn(bad, self.wf)
        self.assertIn("python -m sites.kaidoki.tools.yahoo_shops --store", self.wf)

    def test_secrets_are_only_read_from_secrets(self):
        for k in ("YAHOO_CLIENT_ID", "XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER"):
            self.assertIn("${{ secrets.%s }}" % k, self.wf)


class FreshnessShopsTest(unittest.TestCase):
    T = date(2026, 11, 12)

    def test_fresh_today_or_yesterday_early_is_fine(self):
        self.assertEqual(F.check_shops({"u": "2026-11-12", "genres": 8, "shops": 100}, self.T), [])
        self.assertEqual(F.check_shops({"u": "2026-11-11", "genres": 8, "shops": 100}, self.T, hour=7), [])

    def test_yesterday_after_nine_is_reported(self):
        r = F.check_shops({"u": "2026-11-11", "genres": 8, "shops": 100}, self.T, hour=10)
        self.assertEqual(len(r), 1)
        self.assertIn("今日の取得ではない", r[0])

    def test_old_empty_and_unreadable_are_reported(self):
        self.assertIn("日のずれ", F.check_shops({"u": "2026-11-05", "genres": 8, "shops": 100}, self.T)[0])
        self.assertIn("出ていない", F.check_shops({"u": "", "genres": 0, "shops": 0}, self.T)[0])
        self.assertIn("測れていない", F.check_shops({"error": "URLError"}, self.T)[0])        # 測れなかったを、問題なしにしない
        self.assertEqual(F.check_shops(None, self.T), [])                                      # --no-network

    def test_fetch_meta_reads_the_date_and_counts_only(self):
        class R:
            def __init__(s, b): s.b = b
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return s.b
        body = json.dumps({"u": "2026-11-12", "genres": [{"s": "tv", "shops": [{"n": SECRET_SHOP}] * 3}]}).encode()
        m = F.fetch_shops_meta(opener=lambda req, timeout=0: R(body))
        self.assertEqual(m, {"u": "2026-11-12", "genres": 1, "shops": 3})
        self.assertNotIn(SECRET_SHOP, json.dumps(m, ensure_ascii=False))
        bad = F.fetch_shops_meta(opener=lambda req, timeout=0: (_ for _ in ()).throw(OSError("boom")))
        self.assertEqual(bad, {"error": "OSError"})

    def test_the_report_names_the_item(self):
        txt = F.render(self.T, {k: [] for k in ("ending", "starting", "ended_confirmed", "expected_due", "notice_due", "stale")}, [], 1, 1, ["x"], {"u": "2026-11-12", "genres": 2, "shops": 9})
        self.assertIn("## 8. ショップ欄", txt)
        self.assertIn("2ジャンル・9店", txt)
        self.assertIn("合計: 1 件", txt)


if __name__ == "__main__":
    unittest.main()
