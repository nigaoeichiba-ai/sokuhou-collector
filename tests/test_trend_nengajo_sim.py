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

SALE = "2026-11-16T15:00:00+09:00"      # 確認日の午後(早割は4社とも適用中。おたより本舗は表から外した)
LATER = "2026-11-20T15:00:00+09:00"     # Rakpo の締切後・年賀状スクエアの46%OFFの最中
AFTER = "2026-11-24T10:00:00+09:00"     # 挨拶状・Rakpo の締切後。年賀状スクエアは45%OFF(11/27 23:59まで)、しまうまは11/30まで
LATE = "2026-11-28T10:00:00+09:00"      # 年賀状スクエアの45%OFFも終了(しまうまは11/30まで)


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
        self.assertEqual((r["square"]["print"], r["square"]["min"]), (3842, 6392))          # 3,842 + 85x30 (46% OFF)
        self.assertEqual(r["shimauma"]["min"], 6570)                                         # 123x30 + 2,550 + 330 (yu-packet)
        self.assertEqual((r["rakpo"]["print"], r["rakpo"]["address"], r["rakpo"]["min"]), (2790, 825, 6015))   # 2,790 + 80x30 + 825
        self.assertEqual((r["aisatsu"]["print"], r["aisatsu"]["address"], r["aisatsu"]["shipping"], r["aisatsu"]["min"]), (4422, 759, 330, 8061))
        self.assertNotIn("otayori", r)                                                       # an ended sale is not shown
        later = compute([mk(30, now=LATER)])[0]
        self.assertEqual(later["cheapest"], "square")                                        # 46% OFF until 11/23 23:59: 3,842 + 2,550 = 6,392
        self.assertEqual(by_id(later)["square"]["min"], 6392)

    def test_aisatsu_login_free_shipping_and_no_address(self):
        r = by_id(compute([mk(30, login=True), mk(30, address=False)])[0])
        self.assertEqual(r["aisatsu"]["min"], 7731)
        r2 = by_id(compute([mk(30, address=False)])[0])
        self.assertEqual((r2["aisatsu"]["address"], r2["aisatsu"]["min"]), (0, 4422 + 2550 + 330))
        self.assertEqual((r2["rakpo"]["address"], r2["rakpo"]["min"]), (0, 2790 + 2400))

    def test_after_the_deadlines_normal_prices(self):
        r = by_id(compute([mk(30, now=AFTER)])[0])
        self.assertEqual(r["square"]["min"], 3912 + 2550)                                    # 45% OFF (11/24-11/27 23:59): official 21-30 sheets 3,912 yen
        self.assertEqual((r["square"]["saleRate"], r["square"]["saleLabel"]), ("45%OFF", "11月27日(金)23:59"))
        self.assertEqual(r["aisatsu"]["min"], 7370 + 2550 + 759 + 330)                       # 11,009 yen: no discount until the next one is on the official page
        self.assertEqual(r["rakpo"]["min"], 6200 + 2400 + 825)
        self.assertEqual(r["shimauma"]["min"], 6570)                                         # 12% OFF until 11/30
        self.assertTrue(r["square"]["onSale"])
        self.assertFalse(r["aisatsu"]["onSale"])
        self.assertTrue(r["shimauma"]["onSale"])
        self.assertEqual(compute([mk(30, now=AFTER)])[0]["cheapest"], "square")              # 6,462 < shimauma 6,570
        late_r = by_id(compute([mk(30, now=LATE)])[0])
        self.assertEqual((late_r["square"]["onSale"], late_r["square"]["min"]), (False, 7113 + 2550))
        late = by_id(compute([mk(30, now="2026-12-01T00:00:00+09:00")])[0])["shimauma"]
        self.assertEqual((late["onSale"], late["min"]), (False, 140 * 30 + 2550 + 330))      # unit 165 -> 15% off = 140

    def test_deadline_edges_in_jst(self):
        c = [mk(30, now=t) for t in ("2026-11-17T01:59:00+09:00", "2026-11-17T02:00:00+09:00", "2026-11-18T23:59:30+09:00", "2026-11-19T00:00:00+09:00",
                                      "2026-11-19T12:59:00+09:00", "2026-11-19T13:00:00+09:00", "2026-11-23T23:59:00+09:00", "2026-11-24T00:00:00+09:00",
                                      "2026-11-27T23:59:00+09:00", "2026-11-28T00:00:00+09:00", "2026-11-30T12:59:00+09:00", "2026-11-30T13:00:00+09:00")]
        g = [by_id(x) for x in compute(c)]
        T, F = True, False
        self.assertEqual([x["rakpo"]["onSale"] for x in g], [T, F, F, F, F, F, F, F, F, F, F, F])
        self.assertEqual([x["square"]["onSale"] for x in g], [T, T, T, T, T, T, T, T, T, F, F, F])
        self.assertEqual([x["aisatsu"]["onSale"] for x in g], [T, T, T, T, T, T, T, F, F, F, F, F])
        self.assertEqual([x["shimauma"]["onSale"] for x in g], [T] * 11 + [F])
        self.assertEqual([x["square"]["saleRate"] for x in g][6:9], ["46%OFF", "45%OFF", "45%OFF"])   # the 46% sale ends 11/23 23:59, the 45% one starts 11/24 0:00

    def test_quantities_between_published_steps(self):
        r = by_id(compute([mk(35)])[0])
        self.assertEqual(r["square"]["min"], 4159 + 85 * 35 )          # band 31-40 (46% OFF, before 11/24)
        self.assertFalse(r["aisatsu"]["estimate"])                     # 35 is in the official 5-step table
        self.assertEqual(r["aisatsu"]["print"], 4801)
        self.assertTrue(r["rakpo"]["estimate"])                        # rounded up to the 40-sheet price
        self.assertEqual((r["rakpo"]["print"], r["rakpo"]["printQty"], r["rakpo"]["postcard"]), (3015, 40, 80 * 35))

    def test_large_quantities(self):
        r = by_id(compute([mk(150)])[0])
        self.assertTrue(r["aisatsu"]["unavailable"] and r["rakpo"]["unavailable"])
        self.assertNotIn("min", r["aisatsu"])
        res = compute([mk(150)])[0]
        self.assertEqual([x["id"] for x in res["rows"][-2:]], ["aisatsu", "rakpo"])          # the two that cannot be computed come last
        r = by_id(compute([mk(200)])[0])
        self.assertEqual(r["square"]["print"], 8860)
        self.assertEqual((r["shimauma"]["print"], r["shimauma"]["shipping"]), (79 * 200, 880))   # 165 x 55% = 90, early 12% = 79
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
        for old, new in (("3912", "3913"),):
            with tempfile.TemporaryDirectory() as d:
                bad = Path(d) / "bad45.js"
                bad.write_text(src.replace(old, new), encoding="utf-8")
                self.assertNotEqual(by_id(compute([mk(30, now=AFTER)], js=bad)[0])["square"]["min"], 6462, old)
        for old, new in (("3842", "3843"), ("[30, 7370, 4422]", "[30, 7370, 4423]"), ("[30, 6200, 2790]", "[30, 6200, 2791]")):
            if old not in src:
                continue    # the number is not literally in the file (5174 is computed); the next one covers it
            with tempfile.TemporaryDirectory() as d:
                bad = Path(d) / "bad.js"
                bad.write_text(src.replace(old, new, 1), encoding="utf-8")
                r = by_id(compute([mk(30)], js=bad)[0])
                got = (r["square"]["min"], r["aisatsu"]["min"], r["rakpo"]["min"])
                self.assertNotEqual(got, (6392, 8061, 6015), old)


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
        self.assertLess(t.index("6,462円"), t.index("nsim-form"))
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
        for name in ("ラクスル", "郵便局"):
            self.assertIn(name, block)
        # no link to a company's price page (owner 2026-11-15, D26): the only link out of the block is the ad
        self.assertEqual(re.findall(r'<a [^>]*href="https?://([^/"]+)', block), ["px.a8.net"])
        self.assertIn("2026年11月24日", block)
        self.assertNotRegex(block, r"<ol[^>]*>\s*</ol>")     # sitecheck refuses an empty list


if __name__ == "__main__":
    unittest.main()
