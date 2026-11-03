"""kaidoki-calendar.com (買い時カレンダー): dates agree with the calendar, nothing invents a date, no outside link or price, the calculator agrees with its Python twin."""
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
            self.assertNotIn('href="http', body, rel)
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
        deno = shutil.which("deno")
        if not deno:
            self.skipTest("deno is not installed")
        cases = [dict(price=11000, ship=500, coupon=1000, rate=10, cap=0, excl_tax=True, use=100),
                 dict(price=100000, ship=0, coupon=0, rate=10, cap=7000, excl_tax=True, use=50),
                 dict(price=5000, ship=300, coupon=9999, rate=3.5, cap=0, excl_tax=False, use=80)]
        js = ("import {createRequire} from 'node:module';const r=createRequire(import.meta.url);const {compute}=r(Deno.args[0]);"
              "const cs=JSON.parse(Deno.args[1]);console.log(JSON.stringify(cs.map(c=>compute(c))));")
        tmp = ROOT / "out" / "_calc_probe.mjs"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(js, encoding="utf-8")
        r = subprocess.run([deno, "run", "-A", str(tmp), str(SITE / "assets" / "calc.js"), json.dumps(cases)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        for c, g in zip(cases, got):
            p = real_price(c["price"], c["ship"], c["coupon"], c["rate"], c["cap"], c["excl_tax"], c["use"])
            self.assertEqual((g["pay"], g["points"], g["usable"], round(g["real"])), (p["pay"], p["points"], p["usable"], p["real"]))


if __name__ == "__main__":
    unittest.main()
