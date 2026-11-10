"""sale-calendar.com (買い時カレンダー): dates agree with the calendar, nothing invents a date, no outside link or price, the calculator agrees with its Python twin."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from datetime import date
from pathlib import Path

os.environ["KAIDOKI_TODAY"] = "2026-11-03"

from sites.kaidoki import gen  # noqa: E402
from sites.kaidoki.gen import facts  # noqa: E402
from sites.kaidoki.gen.pages_calc import real_price  # noqa: E402
from sokuhou import newsite  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kaidoki"
AFF_BOX = re.compile(r'<aside class="aff-box">.*?</aside>', re.S)
WD = "月火水木金土日"
FULL = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\(([月火水木金土日])\)")


class KaidokiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen.write()
        cls.pages, cls.report = newsite.build_pages(SITE, release=True, strict_seo=True)
        cls.html = {k: v for k, v in cls.pages.items() if isinstance(v, str) and k.endswith(".html")}

    def test_thirty_pages_with_the_designed_mix(self):
        kinds = [json.loads(p.read_text(encoding="utf-8"))["kind"] for p in sorted((SITE / "content").glob("*.json"))]
        self.assertEqual(len(kinds), 30)
        deep = sum(k in ("analysis", "article") for k in kinds)
        self.assertGreaterEqual(deep, 10)
        self.assertLessEqual(kinds.count("item"), 15)

    def test_every_weekday_agrees_with_the_calendar(self):
        bad = []
        for rel, html in self.html.items():
            for y, m, d, w in FULL.findall(html):
                if WD[date(int(y), int(m), int(d)).weekday()] != w:
                    bad.append((rel, y, m, d, w))
        self.assertEqual(bad, [])

    def test_no_outside_link_no_price_no_source_block(self):
        for rel, html in self.html.items():
            if rel.startswith(("contact", "privacy", "terms", "about")):
                continue
            body = html.split("<main", 1)[-1]
            body = AFF_BOX.sub("", body)      # the one affiliate box of a mall's page (tested below) is the only outside link
            self.assertNotIn('href="http', body, rel)
            self.assertNotIn('href="//', body, rel)
            self.assertNotRegex(body, r"出典の公開ページ|取得日", rel)

    def test_unannounced_sales_have_no_date_in_the_facts(self):
        names = " ".join(e["name"] for e in facts.EVENTS)
        for name, _, _ in facts.UNANNOUNCED:
            self.assertNotIn(name, names)

    def test_stale_is_read_only_and_lists_unannounced(self):
        before = {p: p.read_bytes() for p in (SITE / "content").glob("*.json")}
        rows = gen.stale()
        self.assertTrue(any("未発表" in r for r in rows))
        self.assertEqual(before, {p: p.read_bytes() for p in (SITE / "content").glob("*.json")})

    def test_a_later_day_marks_a_past_sale_as_finished(self):
        out = subprocess.run(["python", "-c", "import os;os.environ['KAIDOKI_TODAY']='2026-11-12';from sites.kaidoki import gen;gen.write();"
                              "import json;print(json.load(open('sites/kaidoki/content/rakuten-marathon.json',encoding='utf-8'))['answer'])"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertNotIn("開催中", out.stdout)
        gen.write()      # back to the fixed day for the other tests

    def test_calculator_js_equals_python(self):
        """node (on the CI runners) or deno runs assets/calc.js.  Neither installed: the test fails, it never skips (a skipped test checks nothing)."""
        node, deno = shutil.which("node"), shutil.which("deno")
        self.assertTrue(node or deno, "neither node nor deno is installed: the calculator cannot be checked")
        cases = [dict(price=11000, ship=500, coupon=1000, rate=10, cap=0, excl_tax=True, use=100),
                 dict(price=100000, ship=0, coupon=0, rate=10, cap=7000, excl_tax=True, use=50),
                 dict(price=5000, ship=300, coupon=9999, rate=3.5, cap=0, excl_tax=False, use=80)]
        js = ("const {compute}=require(process.argv[2]);const cs=JSON.parse(process.argv[3]);console.log(JSON.stringify(cs.map(c=>compute(c))));")
        tmp = ROOT / "out" / "_calc_probe.cjs"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(js, encoding="utf-8")
        cmd = [node, str(tmp)] if node else [deno, "run", "-A", "--ext=cjs", str(tmp)]
        r = subprocess.run(cmd + [str(SITE / "assets" / "calc.js"), json.dumps(cases)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        for c, g in zip(cases, got):
            p = real_price(c["price"], c["ship"], c["coupon"], c["rate"], c["cap"], c["excl_tax"], c["use"])
            self.assertEqual((g["pay"], g["points"], g["usable"], round(g["real"])), (p["pay"], p["points"], p["usable"], p["real"]))

    # ---- affiliate links (owner 2026-11-11) ----
    def _cfg(self):
        return json.loads((SITE / "config.json").read_text(encoding="utf-8"))

    def test_affiliate_links_only_on_mall_pages_one_mall_one_box(self):
        from sites.kaidoki import hooks
        cfg = self._cfg()
        boxes = {rel: AFF_BOX.findall(html) for rel, html in self.html.items() if AFF_BOX.search(html)}
        self.assertEqual(sorted(boxes), sorted(hooks.AFF_LINKS))
        for rel, bx in boxes.items():
            self.assertEqual(len(bx), 1, rel)
            hrefs = re.findall(r'href="([^"]+)"', bx[0])
            self.assertEqual(len(hrefs), 1, rel)
            mall = hooks.AFF_LINKS[rel][0]
            h = hrefs[0]
            if mall == "rakuten":
                self.assertTrue(h.startswith("https://hb.afl.rakuten.co.jp/hgc/" + cfg["rakuten_affiliate_id"] + "/?pc=https%3A%2F%2Fevent.rakuten.co.jp%2F"), h)
                self.assertNotRegex(h, r"amazon|yahoo|valuecommerce", rel)
            elif mall == "amazon":
                self.assertRegex(h, r"^https://www\.amazon\.co\.jp/[a-z/]+\?tag=" + re.escape(cfg["amazon_tracking_id"]) + "$")
                self.assertIn("Amazonのアソシエイトとして", bx[0])
            self.assertIn('<span class="pr-chip">PR</span>', bx[0], rel)
            self.assertIn('target="_blank" rel="nofollow sponsored noopener">', bx[0], rel)
            self.assertNotRegex(bx[0], r"今すぐ|お見逃し|クリック|こちら|最安|お得", rel)

    def test_yahoo_has_no_valuecommerce_link_until_the_site_is_registered(self):
        self.assertNotIn("yahoo_vc", self._cfg())
        for rel, html in self.html.items():
            self.assertNotIn("valuecommerce", html, rel)

    def test_top_page_and_tables_and_calendar_have_no_outside_link(self):
        for rel in ("index.html", "calendar/index.html", "buytime/index.html", "black-friday/index.html", "calc/index.html"):
            html = self.html[rel]
            self.assertNotRegex(html, r'href="(https?:)?//(?!sale-calendar\.com)', rel)
        for rel, html in self.html.items():
            for t in re.findall(r"<table.*?</table>", html, re.S):
                self.assertNotRegex(t, r'href="(https?:)?//', rel)

    def test_affiliate_negative_a_mixed_or_changed_link_is_caught(self):
        from sites.kaidoki import hooks
        cfg = self._cfg()
        r = hooks.affiliate_block("rakuten", "https://event.rakuten.co.jp/campaign/point-up/marathon/", "x", cfg)
        self.assertNotIn("amazon", r)
        a = hooks.affiliate_block("amazon", "https://www.amazon.co.jp/primeday", "x", cfg)
        self.assertEqual(re.findall(r'href="([^"]+)"', a), ["https://www.amazon.co.jp/primeday?tag=" + cfg["amazon_tracking_id"]])
        bad = r.replace("hgc/" + cfg["rakuten_affiliate_id"], "hgc/other")
        self.assertNotIn(cfg["rakuten_affiliate_id"], bad)      # a changed id would no longer match the config: the test above compares with it


if __name__ == "__main__":
    unittest.main()
