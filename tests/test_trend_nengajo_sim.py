"""trend: 年賀状印刷の総額シミュレーター(sites/trend/nengajo_sim/)。計算(JS)を node か deno で動かし、公式表から手で検算した値と突き合わせる。
node も deno も無ければ失敗させる(スキップは何も確かめない)。数字を1つ壊すと落ちること(負例)も確かめる。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sites" / "trend" / "nengajo_sim"
JS = SIM / "nengajo-sim.js"

SALE = "2026-11-13T15:00:00+09:00"      # 確認日の午後(早割は5社とも適用中)
AFTER = "2026-11-17T10:00:00+09:00"     # おたより本舗・年賀状スクエア・挨拶状・Rakpo の締切後(しまうまは11/30まで)


def runtime() -> list[str]:
    for c in (shutil.which("node"), "C:/Program Files/nodejs/node.exe"):
        if c and Path(c).exists():
            return [c]
    deno = shutil.which("deno")
    return [deno, "run", "-A", "--ext=cjs"] if deno else []


def compute(cases: list[dict], js: Path = JS) -> list[dict]:
    rt = runtime()
    assert rt, "neither node nor deno is installed: the simulator cannot be checked"
    probe = ("const {compute}=require(process.argv[2]);const cs=JSON.parse(process.argv[3]);"
             "console.log(JSON.stringify(cs.map(c=>{c.now=Date.parse(c.now);return compute(c)})));")
    with tempfile.TemporaryDirectory() as d:
        pf = Path(d) / "probe.cjs"
        pf.write_text(probe, encoding="utf-8")
        r = subprocess.run(rt + [str(pf), str(js), json.dumps(cases)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def by_id(res: dict) -> dict:
    return {r["id"]: r for r in res["rows"]}


def mk(qty, address=True, now=SALE, login=False):
    return {"qty": qty, "address": address, "now": now, "aisatsuLogin": login}


class TestNengajoSimCalc(unittest.TestCase):
    def test_30_sheets_with_address_during_sale(self):
        r = by_id(compute([mk(30)])[0])
        self.assertEqual((r["square"]["print"], r["square"]["min"]), (3628, 6178))          # 3,628 + 85x30
        self.assertEqual((r["otayori"]["min"], r["otayori"]["max"]), (5174, 8835))          # star 1 .. star 6
        self.assertEqual((r["otayori"]["print"], r["otayori"]["printMax"]), (2624, 6285))
        self.assertEqual(r["shimauma"]["min"], 6570)                                         # 123x30 + 2,550 + 330 (yu-packet)
        self.assertEqual((r["rakpo"]["print"], r["rakpo"]["address"], r["rakpo"]["min"]), (2790, 825, 6015))   # 2,790 + 80x30 + 825
        self.assertEqual((r["aisatsu"]["print"], r["aisatsu"]["address"], r["aisatsu"]["shipping"], r["aisatsu"]["min"]), (4422, 759, 330, 8061))
        self.assertEqual(compute([mk(30)])[0]["cheapest"], "otayori")

    def test_aisatsu_login_free_shipping_and_no_address(self):
        r = by_id(compute([mk(30, login=True), mk(30, address=False)])[0])
        self.assertEqual(r["aisatsu"]["min"], 7731)
        r2 = by_id(compute([mk(30, address=False)])[0])
        self.assertEqual((r2["aisatsu"]["address"], r2["aisatsu"]["min"]), (0, 4422 + 2550 + 330))
        self.assertEqual((r2["rakpo"]["address"], r2["rakpo"]["min"]), (0, 2790 + 2400))

    def test_after_the_deadlines_normal_prices(self):
        r = by_id(compute([mk(30, now=AFTER)])[0])
        self.assertEqual(r["square"]["min"], 7113 + 2550)
        self.assertEqual((r["otayori"]["min"], r["otayori"]["max"]), (4037 + 2550, 9669 + 2550))
        self.assertEqual(r["aisatsu"]["min"], 7370 + 2550 + 759 + 330)
        self.assertEqual(r["rakpo"]["min"], 6200 + 2400 + 825)
        self.assertEqual(r["shimauma"]["min"], 6570)                                         # 12% OFF until 11/30
        self.assertFalse(r["square"]["onSale"])
        self.assertTrue(r["shimauma"]["onSale"])
        late = by_id(compute([mk(30, now="2026-12-01T00:00:00+09:00")])[0])["shimauma"]
        self.assertEqual((late["onSale"], late["min"]), (False, 140 * 30 + 2550 + 330))      # unit 165 -> 15% off = 140

    def test_deadline_edges_in_jst(self):
        c = [mk(30, now=t) for t in ("2026-11-15T23:59:30+09:00", "2026-11-16T00:00:00+09:00", "2026-11-16T12:59:00+09:00", "2026-11-16T13:00:00+09:00",
                                      "2026-11-17T01:59:00+09:00", "2026-11-17T02:00:00+09:00", "2026-11-30T12:59:00+09:00", "2026-11-30T13:00:00+09:00")]
        g = [by_id(x) for x in compute(c)]
        self.assertEqual([x["square"]["onSale"] for x in g], [True, False, False, False, False, False, False, False])
        self.assertEqual([x["otayori"]["onSale"] for x in g], [True, True, True, False, False, False, False, False])
        self.assertEqual([x["rakpo"]["onSale"] for x in g], [True, True, True, True, True, False, False, False])
        self.assertEqual([x["shimauma"]["onSale"] for x in g], [True] * 7 + [False])

    def test_quantities_between_published_steps(self):
        r = by_id(compute([mk(35)])[0])
        self.assertEqual(r["square"]["min"], 3928 + 85 * 35 )          # band 31-40
        self.assertFalse(r["aisatsu"]["estimate"])                     # 35 is in the official 5-step table
        self.assertEqual(r["aisatsu"]["print"], 4801)
        self.assertTrue(r["rakpo"]["estimate"])                        # rounded up to the 40-sheet price
        self.assertEqual((r["rakpo"]["print"], r["rakpo"]["printQty"], r["rakpo"]["postcard"]), (3015, 40, 80 * 35))
        self.assertTrue(r["otayori"]["estimate"])
        self.assertEqual(r["otayori"]["printQty"], 40)

    def test_large_quantities(self):
        r = by_id(compute([mk(150)])[0])
        self.assertTrue(r["aisatsu"]["unavailable"] and r["rakpo"]["unavailable"])
        self.assertNotIn("min", r["aisatsu"])
        self.assertEqual((r["otayori"]["printQty"], r["otayori"]["estimate"]), (200, True))
        res = compute([mk(150)])[0]
        self.assertEqual([x["id"] for x in res["rows"][-2:]], ["aisatsu", "rakpo"])          # the two that cannot be computed come last
        r = by_id(compute([mk(200)])[0])
        self.assertEqual(r["square"]["print"], 8368)
        self.assertEqual((r["shimauma"]["print"], r["shimauma"]["shipping"]), (79 * 200, 880))   # 165 x 55% = 90, early 12% = 79
        self.assertEqual(r["otayori"]["min"], (8230 - 8230 * 35 // 100) * 11 // 10 + 85 * 200)
        self.assertEqual(by_id(compute([mk(108)])[0])["shimauma"]["shipping"], 330)
        self.assertEqual(by_id(compute([mk(109)])[0])["shimauma"]["shipping"], 880)

    def test_invalid_input(self):
        for q in (9, 201, "abc", "", None, -5):
            self.assertFalse(compute([mk(q)])[0]["ok"], q)
        self.assertTrue(compute([mk(10)])[0]["ok"] and compute([mk(200)])[0]["ok"])

    def test_rows_sorted_cheapest_first(self):
        for q in (10, 30, 77, 100):
            res = compute([mk(q)])[0]
            mins = [x["min"] for x in res["rows"] if "min" in x]
            self.assertEqual(mins, sorted(mins))
            self.assertEqual(res["rows"][0]["id"], res["cheapest"])

    def test_negative_a_broken_number_is_caught(self):
        """数字を1つ壊した複製で、同じ検算が落ちること(検算が何も見ていない、を防ぐ)。"""
        src = JS.read_text(encoding="utf-8")
        for old, new in (("3628", "3629"), ("[30, 7370, 4422]", "[30, 7370, 4423]"), ("5174", "5175"), ("[30, 6200, 2790]", "[30, 6200, 2791]")):
            if old not in src:
                continue    # the number is not literally in the file (5174 is computed); the next one covers it
            with tempfile.TemporaryDirectory() as d:
                bad = Path(d) / "bad.js"
                bad.write_text(src.replace(old, new, 1), encoding="utf-8")
                r = by_id(compute([mk(30)], js=bad)[0])
                got = (r["square"]["min"], r["aisatsu"]["min"], r["rakpo"]["min"])
                self.assertNotEqual(got, (6178, 8061, 6015), old)
        with tempfile.TemporaryDirectory() as d:     # a wrong star-1 price for 30 sheets (3670 -> 3680) changes the otayori total
            bad = Path(d) / "bad.js"
            bad.write_text(src.replace("[3670, 5050", "[3680, 5050", 1), encoding="utf-8")
            self.assertNotEqual(by_id(compute([mk(30)], js=bad)[0])["otayori"]["min"], 5174)


class TestNengajoSimPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp())
        cls.page = {}
        for name, flag in (("on", "1"), ("off", "0")):
            o = cls.out / name
            r = subprocess.run([sys.executable, str(ROOT / "sites" / "trend" / "build.py"), "--release", "--out", str(o)], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", env={**os.environ, "TREND_NENGAJO_SIM": flag, "PYTHONIOENCODING": "utf-8"})
            assert r.returncode == 0, r.stderr[-800:] + r.stdout[-800:]
            cls.page[name] = (o / "trend-nengajo-hayawari" / "index.html").read_text(encoding="utf-8")
            cls.assets = getattr(cls, "assets", {})
            cls.assets[name] = sorted(p.name for p in (o / "assets").glob("nengajo-sim.*"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_off_by_default_nothing_ships(self):
        self.assertNotIn("nsim-form", self.page["off"])
        self.assertEqual(self.assets["off"], [])
        self.assertIn("30枚前後なら、この記事の表がそのまま使えます", self.page["off"])

    def test_on_form_labels_and_position(self):
        t = self.page["on"]
        self.assertEqual(self.assets["on"], ["nengajo-sim.css", "nengajo-sim.js"])
        self.assertIn('<label for="nsim-qty">', t)
        self.assertIn('id="nsim-qty"', t)
        self.assertIn('<legend>宛名印刷</legend>', t)
        self.assertIn('<label class="opt" for="nsim-login">', t)
        # after the total-price table, before the next heading
        self.assertLess(t.index("5,174円"), t.index("nsim-form"))
        self.assertLess(t.index("nsim-form"), t.index("割引率だけ見ると損するワケ"))
        self.assertNotIn("この記事の表がそのまま使えます", t)
        self.assertIn("シミュレーターに入れて", t)

    def test_on_links_affiliate_rules_and_no_url_text(self):
        t = self.page["on"]
        block = t[t.index('<div class="nsim">'):t.index("割引率だけ見ると損するワケ")]
        a8 = re.findall(r'<a [^>]*px\.a8\.net[^>]*>', block)
        self.assertEqual(len(a8), 1)
        for attr in ('rel="nofollow sponsored noopener"', 'target="_blank"', "a8mat=4BGH3G+CRMT6Y+33J0+15OK2A"):
            self.assertIn(attr, a8[0])
        self.assertIn("【PR】", block)
        self.assertIn("www11.a8.net/0.gif?a8mat=4BGH3G+CRMT6Y+33J0+15OK2A", block)
        for text in re.findall(r"<a [^>]*>([^<]*)</a>", block):
            self.assertFalse(re.match(r"\s*(https?:|www\.)", text), f"link text is a URL: {text}")
        for name in ("年賀状スクエア", "おたより本舗", "しまうまプリント", "挨拶状ドットコム", "Rakpo", "ラクスル", "郵便局"):
            self.assertIn(name, block)
        self.assertIn("2026年11月13日", block)
        self.assertNotRegex(block, r"<ol[^>]*>\s*</ol>")     # sitecheck refuses an empty list


if __name__ == "__main__":
    unittest.main()
