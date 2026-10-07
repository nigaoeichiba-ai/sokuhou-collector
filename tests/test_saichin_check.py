"""The shortfall checker (/check/): the page is built and linked, and its arithmetic (assets/app.js) is right.

The arithmetic is checked in a real headless Chrome against an independent Python implementation of the Ministry's method
(skipped when Chrome is not installed; CI measures the built page with sokuhou.layoutcheck instead).
"""
import functools
import html
import http.server
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from sites.saichin import build, content
from tests.test_saichin_pages import CFG, SiteFixture

CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                           "/usr/bin/google-chrome", "/usr/bin/chromium") if Path(p).exists()), None)


def reference(kind, pay, excluded, hours, days, minimum):
    """Ministry method, written independently of app.js: hourly equivalent of the wage that counts, compared with the minimum."""
    effective = pay if kind == "hourly" else pay - excluded
    monthly_hours = hours * days / 12
    hourly = effective if kind == "hourly" else effective / hours if kind == "daily" else effective / monthly_hours
    gap = minimum - hourly
    return {"hourly": hourly, "ok": gap <= 1e-9, "perMonth": max(gap, 0) * monthly_hours, "perYear": max(gap, 0) * hours * days}


class CheckPageTest(SiteFixture):
    def test_the_page_exists_is_in_the_sitemap_and_the_nav(self):
        self.assertIn("check/index.html", self.files)
        self.assertIn("https://saichin-sokuho.com/check/", self.read("sitemap.xml"))
        self.assertIn('<a href="/check/">差額チェック</a>', self.read("index.html"))
        self.assertRegex(self.read("check/index.html"), r"<a href=\"/check/\" aria-current='page'>差額チェック</a>")

    def test_the_form_has_every_field_the_script_reads(self):
        page = self.read("check/index.html")
        for needle in ('id="chk-form"', 'id="chk-pref"', 'id="chk-pay"', 'id="chk-hours"', 'id="chk-days"', 'id="chk-out"', 'id="chk-print"',
                       'id="chk-pay-label"', 'id="chk-days-label"', 'id="chk-excl"', 'id="chk-excl-legend"', 'id="data"', 'name="chk-kind"'):
            self.assertIn(needle, page, needle)
        self.assertEqual(page.count("data-excl"), len(build.CHECK_EXCLUDED))
        self.assertEqual(page.count('name="chk-kind"'), 3)

    def test_the_data_has_every_prefecture_with_the_old_and_new_amount_and_the_date(self):
        data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', self.read("check/index.html"), re.S).group(1))
        self.assertEqual(len(data), 47)
        for item in data:
            self.assertEqual(set(item), {"name", "amount", "prev", "date"})
            self.assertGreater(item["amount"], item["prev"])
        self.assertEqual({d["name"] for d in data}, {r["name"] for r in self.d["rows"]})

    def test_every_exclusion_is_one_of_the_six_in_the_law_or_the_catch_all(self):
        labels = [label for label, _ in build.CHECK_EXCLUDED]
        for needle in ("通勤手当", "家族手当", "精皆勤手当", "時間外", "休日", "深夜", "臨時"):
            self.assertTrue(any(needle in label for label in labels), needle)

    def test_the_page_has_sources_and_a_verification_date_and_names_no_individual_advice(self):
        page = self.read("check/index.html")
        for name, url in content.CHECK_SOURCES:
            self.assertIn(url, page)
        self.assertIn(content.CHECK_VERIFIED_AT.replace("-0", "-").split("-")[0] + "年", page)
        self.assertIn("個別の相談には対応していません", page)

    def test_it_is_linked_from_the_front_page_and_from_every_prefecture_page_with_the_prefecture_preselected(self):
        self.assertIn('href="/check/"', self.read("index.html"))
        for r in self.d["rows"]:
            from urllib.parse import quote
            self.assertIn(f'href="/check/?pref={quote(r["name"])}"', self.read(f"{r['slug']}/index.html"), r["name"])

    def test_the_old_calculator_stays_only_on_the_calculate_guide(self):
        self.assertNotIn('id="calc"', self.read("check/index.html"))


SCENARIO = r"""
const CASES = __CASES__;
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '1000px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(300); return f;
}
(async () => {
  try {
    const f = await load('/check/?pref=' + encodeURIComponent('東京都')); const d = f.contentDocument, w = f.contentWindow;
    const ev = w.saichinCheck.evaluate;
    const TODAY = '2026-10-10';
    // 1. random cases against the independent implementation (done / not yet effective rows)
    out.mismatches = [];
    for (const c of CASES) {
      const row = { name: 'テスト県', amount: c.amount, prev: c.prev, date: c.date };
      const r = ev({ kind: c.kind, pay: c.pay, excluded: c.excluded, hours: c.hours, days: c.days }, row, TODAY);
      if (r.error) { out.mismatches.push(['error', r.error, c]); continue; }
      const last = r.periods[r.periods.length - 1];
      const now = r.periods[0];
      const minNow = c.date <= TODAY ? c.amount : c.prev;
      const exp = c.expected;
      const close = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(b));
      if (!close(r.hourly, exp.hourly) || r.periods.length !== (c.date <= TODAY ? 1 : 2) || now.min !== minNow ||
          now.ok !== exp.ok_now || last.ok !== exp.ok_last || !close(last.perMonth, exp.perMonth_last) || !close(last.perYear, exp.perYear_last)) {
        out.mismatches.push([c, r.hourly, now.ok, last.ok, last.perMonth, last.perYear]);
      }
    }
    // 2. fixed cases from the Ministry's worked example and edge cases
    const row = { name: 'テスト県', amount: 1081, prev: 1080, date: '2026-12-01' };
    const ex = ev({ kind: 'monthly', pay: 185000, excluded: 5000, hours: 8, days: 250 }, row, TODAY);   // 180,000 yen / (2,000 h / 12) = 1,080
    out.example = [ex.hourly, ex.periods.map(p => p.ok), Math.round(ex.periods[1].perMonth), Math.round(ex.periods[1].perYear), ex.periods[1].required];
    out.hourly_short = (() => { const r = ev({ kind: 'hourly', pay: 1000, excluded: 0, hours: 8, days: 250 }, { name: 'x', amount: 1100, prev: 1050, date: '2026-10-01' }, TODAY);
      return [r.periods.length, r.periods[0].ok, Math.round(r.periods[0].perMonth), Math.round(r.periods[0].perYear), r.periods[0].required]; })();
    out.on_the_day = ev({ kind: 'hourly', pay: 1100, excluded: 0, hours: 8, days: 250 }, { name: 'x', amount: 1100, prev: 1050, date: TODAY }, TODAY).periods.length;
    out.day_before = ev({ kind: 'hourly', pay: 1100, excluded: 0, hours: 8, days: 250 }, { name: 'x', amount: 1100, prev: 1050, date: '2026-10-11' }, TODAY).periods.map(p => p.min);
    out.errors = [
      ev({ kind: 'monthly', pay: 0, excluded: 0, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 100000, excluded: 100000, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 100000, excluded: 0, hours: 0, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 100000, excluded: 0, hours: 25, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 100000, excluded: 0, hours: 8, days: 400 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 100000, excluded: 0, hours: 8, days: 250 }, null, TODAY).error,
    ];
    // rounding is conservative: 1,099.96 yen an hour is shown as 1,099.9 and judged as short of 1,100
    const near = ev({ kind: 'hourly', pay: 1099.96, excluded: 0, hours: 8, days: 250 }, { name: 'x', amount: 1100, prev: 1050, date: '2026-10-01' }, TODAY);
    out.near = [near.periods[0].ok, near.steps[0]];

    // 3. the page itself: prefecture preselected from the URL, typing changes the result, hourly hides the allowances
    const q = (s) => d.querySelector(s);
    const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
    out.pref_from_url = q('#chk-pref').value;
    out.form_visible = !q('#chk-form').hidden;
    out.hint_text = q('#chk-out').textContent.trim();
    type(q('#chk-pay'), '1000000');      // a monthly wage far above any minimum
    out.big = (q('#chk-out').classList.contains('ok') ? 'ok' : q('#chk-out').classList.contains('ng') ? 'ng' : '?') + '|' + q('#chk-out .chk-head').textContent;
    type(q('#chk-pay'), '50000');        // far below
    out.small = (q('#chk-out').classList.contains('ok') ? 'ok' : q('#chk-out').classList.contains('ng') ? 'ng' : '?') + '|' + q('#chk-out .chk-head').textContent;
    out.has_table = q('#chk-out').querySelectorAll('section.chk-period').length >= 1;
    out.has_steps = !!q('#chk-out details.chk-steps');
    out.excl_visible_monthly = !q('#chk-excl').hidden;
    q('input[name="chk-kind"][value="hourly"]').checked = true; q('input[name="chk-kind"][value="hourly"]').dispatchEvent(new w.Event('input', { bubbles: true }));
    out.excl_hidden_hourly = q('#chk-excl').hidden;
    out.pay_label_hourly = q('#chk-pay-label').textContent.trim().split('\n')[0];
    q('input[name="chk-kind"][value="daily"]').checked = true; q('input[name="chk-kind"][value="daily"]').dispatchEvent(new w.Event('input', { bubbles: true }));
    out.legend_daily = q('#chk-excl-legend').textContent;
    type(q('#chk-x-commute'), '999999');  // more than the pay: refused with a message, not a number
    out.too_much = q('#chk-out').textContent;
    out.script_error = null;
  } catch (e) { out.error = String(e && e.stack || e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


def run_chrome(url: str, attempts: int = 4) -> str:
    for attempt in range(attempts):
        profile = tempfile.mkdtemp(prefix="saichin_e2e_")
        try:
            r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={profile}",
                                "--virtual-time-budget=30000", "--dump-dom", url], capture_output=True, timeout=30)
            return r.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            if attempt == attempts - 1:
                raise
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    return ""


def make_cases(n=300, seed=20261007):
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        kind = rng.choice(["hourly", "daily", "monthly"])
        hours = rng.choice([4, 5, 6, 7, 7.5, 8, 8.25])
        days = rng.choice([100, 150, 200, 240, 250, 260, 300])
        minimum = rng.randint(950, 1300)
        prev = minimum - rng.randint(30, 80)
        date = rng.choice(["2026-10-01", "2026-10-10", "2026-11-15", "2027-03-31"])
        if kind == "hourly":
            pay, excluded = float(rng.randint(900, 1500)), 0
        elif kind == "daily":
            excluded = float(rng.choice([0, 0, 200, 500, 800]))
            pay = float(rng.randint(6000, 14000))
        else:
            excluded = float(rng.choice([0, 0, 3000, 8000, 15000]))
            pay = float(rng.randint(120000, 320000))
        today = "2026-10-10"
        now_min = minimum if date <= today else prev
        exp_last = reference(kind, pay, excluded, hours, days, minimum)
        exp_now = reference(kind, pay, excluded, hours, days, now_min)
        cases.append({"kind": kind, "pay": pay, "excluded": excluded, "hours": hours, "days": days, "amount": minimum, "prev": prev, "date": date,
                      "expected": {"hourly": exp_last["hourly"], "ok_now": exp_now["ok"], "ok_last": exp_last["ok"],
                                   "perMonth_last": exp_last["perMonth"], "perYear_last": exp_last["perYear"]}})
    return cases


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally; CI must not be blocked by a browser quirk")
class CheckBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        from tests.test_saichin_pages import _raw
        build.render_site(_raw(), CFG, cls.root, release=True)
        cls.cases = make_cases()
        scenario = SCENARIO.replace("__CASES__", json.dumps(cls.cases))
        (cls.root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{scenario}</script>', encoding="utf-8")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cls.root))
        handler.log_message = lambda *a, **k: None
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        cls.out = json.loads(html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_no_script_error(self):
        self.assertNotIn("error", self.out)

    def test_the_arithmetic_matches_an_independent_implementation_on_300_random_cases(self):
        self.assertEqual(self.out["mismatches"], [])
        self.assertGreaterEqual(sum(1 for c in self.cases if not c["expected"]["ok_last"]), 30)   # the sample includes plenty of shortfalls
        self.assertGreaterEqual(sum(1 for c in self.cases if c["expected"]["ok_last"]), 30)

    def test_the_ministrys_worked_example(self):
        hourly, oks, per_month, per_year, required = self.out["example"]
        self.assertAlmostEqual(hourly, 1080.0)
        self.assertEqual(oks, [True, False])           # 1,080 meets the old 1,080 but not the new 1,081
        self.assertEqual(per_month, 167)               # 1 yen x 166.67 hours
        self.assertEqual(per_year, 2000)
        self.assertEqual(required, 180167 + 5000)      # the wage that counts must reach 1,081 x 166.67 = 180,167, plus the allowance

    def test_an_hourly_wage_below_the_minimum(self):
        self.assertEqual(self.out["hourly_short"], [1, False, 16667, 200000, 1100])

    def test_the_new_amount_applies_from_the_effective_date_itself(self):
        self.assertEqual(self.out["on_the_day"], 1)             # on the effective date only the new amount is shown
        self.assertEqual(self.out["day_before"], [1050, 1100])  # the day before, the old and the new one

    def test_bad_input_gets_a_message_not_a_number(self):
        self.assertEqual(len(self.out["errors"]), 6)
        for message in self.out["errors"]:
            self.assertIsInstance(message, str)
            self.assertTrue(message.endswith("。"), message)

    def test_rounding_never_turns_a_shortfall_into_a_pass(self):
        ok, step = self.out["near"]
        self.assertFalse(ok)

    def test_the_page_reads_the_prefecture_from_the_url_and_reacts_to_typing(self):
        o = self.out
        self.assertEqual(o["pref_from_url"], "東京都")
        self.assertTrue(o["form_visible"])
        self.assertIn("計算します", o["hint_text"])
        self.assertTrue(o["big"].startswith("ok|"), o["big"])
        self.assertIn("以上です", o["big"])
        self.assertTrue(o["small"].startswith("ng|"), o["small"])
        self.assertTrue(o["has_table"] and o["has_steps"])

    def test_the_allowance_fields_follow_the_pay_type(self):
        o = self.out
        self.assertTrue(o["excl_visible_monthly"])
        self.assertTrue(o["excl_hidden_hourly"])
        self.assertIn("時給", o["pay_label_hourly"])
        self.assertIn("1日あたり", o["legend_daily"])
        self.assertIn("以上になっています", o["too_much"])


if __name__ == "__main__":
    unittest.main()
