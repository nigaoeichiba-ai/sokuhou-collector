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
from fractions import Fraction
from pathlib import Path

from sites.saichin import build, content
from tests.test_saichin_pages import CFG, SiteFixture

CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                           "/usr/bin/google-chrome", "/usr/bin/chromium") if Path(p).exists()), None)


def reference(kind, pay, excluded, hours, days, minimum):
    """Ministry method, written independently of app.js and in EXACT arithmetic (fractions), so a verdict at the boundary has no tolerance to hide in:
    the hourly equivalent of the wage that counts, compared with the minimum."""
    pay, excluded, hours, days, minimum = (Fraction(x) for x in (pay, excluded, hours, days, minimum))
    effective = pay if kind == "hourly" else pay - excluded
    monthly_hours = hours * days / 12
    hourly = effective if kind == "hourly" else effective / hours if kind == "daily" else effective / monthly_hours
    gap = minimum - hourly
    return {"hourly": float(hourly), "ok": gap <= 0, "perMonth": float(max(gap, 0) * monthly_hours), "perYear": float(max(gap, 0) * hours * days)}


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
    // hourly and daily pay do not need the days of the year to be judged
    const noDays = ev({ kind: 'hourly', pay: 1200, excluded: 0, hours: '', days: '' }, { name: 'x', amount: 1163, prev: 1100, date: '2026-10-01' }, TODAY);
    out.hourly_no_days = [noDays.error || null, noDays.periods && noDays.periods[0].ok];
    const noDaysShort = ev({ kind: 'hourly', pay: 1000, excluded: 0, hours: '', days: '' }, { name: 'x', amount: 1163, prev: 1100, date: '2026-10-01' }, TODAY);
    out.hourly_no_days_short = [noDaysShort.error || null, noDaysShort.periods && noDaysShort.periods[0].ok, noDaysShort.periods && noDaysShort.periods[0].perMonth];
    out.daily_no_days = (() => { const r = ev({ kind: 'daily', pay: 8000, excluded: 0, hours: 8, days: '' }, { name: 'x', amount: 1163, prev: 1100, date: '2026-10-01' }, TODAY);
      return [r.error || null, r.periods && r.periods[0].ok, r.periods && r.periods[0].perMonth]; })();
    out.monthly_needs_days = ev({ kind: 'monthly', pay: 200000, excluded: 0, hours: 8, days: '' }, { name: 'x', amount: 1163, prev: 1100, date: '2026-10-01' }, TODAY).error;
    // garbage that must be refused, never judged as a pass
    out.garbage = [
      ev({ kind: 'hourly', pay: Infinity, excluded: 0, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'hourly', pay: NaN, excluded: 0, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 190000, excluded: -10000, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'monthly', pay: 190000, excluded: Infinity, hours: 8, days: 250 }, row, TODAY).error,
      ev({ kind: 'daily', pay: 8000, excluded: 0, hours: 'abc', days: 250 }, row, TODAY).error,
    ];
    // a tiny shortfall is shown as a shortfall (rounded up), never as 0 yen
    const tiny = ev({ kind: 'hourly', pay: 1099.99, excluded: 0, hours: 8, days: 250 }, { name: 'x', amount: 1100, prev: 1050, date: '2026-10-01' }, TODAY);
    out.tiny = [tiny.periods[0].ok, tiny.periods[0].gap > 0];
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
    // a negative allowance must not cancel a positive one: it counts as 0
    type(q('#chk-pay'), '190000'); type(q('#chk-x-commute'), '10000'); type(q('#chk-x-family'), '-10000');
    out.negative_allowance = q('#chk-out .chk-sum').textContent;
    type(q('#chk-x-commute'), ''); type(q('#chk-x-family'), '');
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
        cases.append(_case(kind, pay, excluded, hours, days, minimum, prev, date))
    # exactly on the boundary and one yen either side, for every pay type (the verdict must not depend on float noise)
    for minimum in (1000, 1080, 1163, 1226, 1280):
        for delta in (-1, 0, 1):
            cases.append(_case("hourly", minimum + delta, 0, 8, 240, minimum, minimum - 50, "2026-10-01"))
            cases.append(_case("daily", minimum * 8 + delta, 0, 8, 240, minimum, minimum - 50, "2026-10-01"))
            cases.append(_case("daily", minimum * 8 + delta + 800, 800, 8, 240, minimum, minimum - 50, "2026-10-01"))
            cases.append(_case("monthly", minimum * 160 + delta, 0, 8, 240, minimum, minimum - 50, "2026-10-01"))          # 8 h x 240 days / 12 = 160 h
            cases.append(_case("monthly", minimum * 160 + delta + 5000, 5000, 8, 240, minimum, minimum - 50, "2026-10-01"))
    # monthly wages that are EXACTLY the minimum, where plain float division lands just below it (30,000 / (4 x 100 / 12) = 899.9999999999999 yen):
    # they meet the minimum, and one yen less does not
    noise = [(h, d, m, int(Fraction(m) * Fraction(h) * d / 12)) for h in (4, 6, 7.5, 8) for d in range(100, 301, 7) for m in range(900, 1400, 11)
             if (Fraction(m) * Fraction(h) * d / 12).denominator == 1 and (Fraction(m) * Fraction(h) * d / 12) / 1 == int(Fraction(m) * Fraction(h) * d / 12)
             and int(Fraction(m) * Fraction(h) * d / 12) / (h * d / 12) < m]
    for h, d, m, pay in noise[:40]:
        cases.append(_case("monthly", pay, 0, h, d, m, m - 50, "2026-10-01"))
        cases.append(_case("monthly", pay - 1, 0, h, d, m, m - 50, "2026-10-01"))
    return cases


def _case(kind, pay, excluded, hours, days, minimum, prev, date, today="2026-10-10"):
    now_min = minimum if date <= today else prev
    exp_last = reference(kind, pay, excluded, hours, days, minimum)
    exp_now = reference(kind, pay, excluded, hours, days, now_min)
    return {"kind": kind, "pay": float(pay), "excluded": float(excluded), "hours": hours, "days": days, "amount": minimum, "prev": prev, "date": date,
            "expected": {"hourly": exp_last["hourly"], "ok_now": exp_now["ok"], "ok_last": exp_last["ok"],
                         "perMonth_last": exp_last["perMonth"], "perYear_last": exp_last["perYear"]}}


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

    def test_hourly_and_daily_pay_do_not_need_the_days_of_the_year(self):
        o = self.out
        self.assertEqual(o["hourly_no_days"], [None, True])
        self.assertEqual(o["hourly_no_days_short"], [None, False, None])      # judged; month and year not computable, so not shown
        self.assertEqual(o["daily_no_days"], [None, False, None])
        self.assertTrue(o["monthly_needs_days"] and "年間の所定労働日数" in o["monthly_needs_days"])

    def test_garbage_input_is_refused_never_judged_as_a_pass(self):
        self.assertEqual(len(self.out["garbage"]), 5)
        for message in self.out["garbage"]:
            self.assertIsInstance(message, str, self.out["garbage"])
            self.assertTrue(message)

    def test_a_tiny_shortfall_is_still_a_shortfall(self):
        self.assertEqual(self.out["tiny"], [False, True])

    def test_a_negative_allowance_does_not_cancel_a_positive_one(self):
        self.assertIn("除外する手当 10,000円", self.out["negative_allowance"])

    def test_the_sample_has_cases_where_float_division_alone_would_be_wrong(self):
        flipped = [c for c in self.cases if c["kind"] == "monthly" and c["expected"]["ok_last"]
                   and c["pay"] / (c["hours"] * c["days"] / 12) < c["amount"]]
        self.assertGreaterEqual(len(flipped), 20)

    def test_the_sample_has_boundary_cases_on_both_sides_for_every_pay_type(self):
        edge = [c for c in self.cases if c["date"] == "2026-10-01" and c["prev"] == c["amount"] - 50]
        self.assertGreaterEqual(len(edge), 60)
        for kind in ("hourly", "daily", "monthly"):
            verdicts = {c["expected"]["ok_last"] for c in edge if c["kind"] == kind}
            self.assertEqual(verdicts, {True, False}, kind)
            on_the_line = [c for c in edge if c["kind"] == kind and c["expected"]["ok_last"] and abs(c["expected"]["hourly"] - c["amount"]) < 1e-9]
            self.assertTrue(on_the_line, kind)         # exactly equal to the minimum counts as meeting it

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
