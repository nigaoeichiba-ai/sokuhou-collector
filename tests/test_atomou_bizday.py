"""atomou 案7: a day of every month that moves off the closed days.  Python (sites/atomou/bizday.py) and the browser (assets/rule.js) are run on the same hand-verified cases of
tests/fixtures/atomou/date_vectors.json ("bizday"); the pension's payment days of 2026 and 2027 are counted by hand below; the pages are opened in a real Chrome (a rule is saved, a day is put
into the planner, a rule is deleted)."""
import functools
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import bizday, build, calendar_data as cal  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

ASSETS = ROOT / "sites" / "atomou" / "assets"
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
V = json.loads((ROOT / "tests" / "fixtures" / "atomou" / "date_vectors.json").read_text(encoding="utf-8"))["bizday"]
TODAY = date(2026, 10, 11)
HOL = {date.fromisoformat(x) for x in V["holidays"]}

# the 15th of the even months, a Saturday / Sunday / holiday moved to the weekday before (counted by hand; 2026-02-15 and 2027-08-15 are Sundays, 2026-08-15 a Saturday)
PENSION = {2026: ["2026-02-13", "2026-04-15", "2026-06-15", "2026-08-14", "2026-10-15", "2026-12-15"], 2027: ["2027-02-15", "2027-04-15", "2027-06-15", "2027-08-13", "2027-10-15", "2027-12-15"]}


class InPython(unittest.TestCase):
    def test_adjust(self):
        for c in V["adjust"]:
            self.assertEqual(bizday.adjust(date.fromisoformat(c["d"]), c["how"], HOL, c["bank"]).isoformat(), c["want"], c)

    def test_the_day_of_a_month(self):
        for c in V["nominal"]:
            self.assertEqual(bizday.nominal(c["y"], c["m"], c["day"]).isoformat(), c["want"], c)

    def test_the_next_dates_of_a_rule(self):
        for c in V["occurrences"]:
            got = bizday.occurrences(c["rule"], date.fromisoformat(c["start"]), c["n"], HOL)
            self.assertEqual([d.isoformat() for d in got], c["want"], c)

    def test_the_pension_days_of_two_years(self):
        for y, want in PENSION.items():
            self.assertEqual([d.isoformat() for d in bizday.pension_dates(y)], want, y)
            self.assertEqual([d.isoformat() for d in bizday.pension_dates(y, bizday.holiday_set(y, y))], want)

    def test_a_wrong_rule_is_caught(self):
        # a bank that was open on a Saturday, or one that forgot the year end, would give other days than the hand-verified ones
        self.assertNotEqual(bizday.adjust(date(2026, 8, 15), "prev", HOL, True).isoformat(), "2026-08-15")
        self.assertNotEqual(bizday.adjust(date(2026, 12, 31), "next", HOL, True), date(2026, 12, 31))
        self.assertEqual(bizday.adjust(date(2026, 12, 31), "next", HOL, False), date(2026, 12, 31))

    def test_every_closed_day_of_2026_is_a_weekend_a_holiday_or_the_year_end(self):
        hol = bizday.holiday_set(2026, 2026)
        self.assertEqual({d.isoformat() for d in hol}, {d.isoformat() for d in cal.holidays(2026)})
        self.assertTrue(bizday.is_closed(date(2026, 1, 2), hol, True))
        self.assertFalse(bizday.is_closed(date(2026, 1, 2), hol, False))      # a Friday: an office is open
        self.assertFalse(bizday.is_closed(date(2026, 1, 5), hol, True))


PAGE = """<!doctype html><meta charset="utf-8"><script src="@@core@@"></script><script src="@@rule@@"></script><pre id="out">pending</pre>
<script>
(function () {
  var C = AtomouCore, B = AtomouBiz, V = %(vectors)s, P = C.parse, hol = {}, res = {};
  V.holidays.forEach(function (x) { hol[x] = 1; });
  res.adjust = V.adjust.map(function (c) { var d = B.adjust(P(c.d), c.how, hol, c.bank); return d && C.iso(d); });
  res.nominal = V.nominal.map(function (c) { return C.iso(B.nominal(c.y, c.m, c.day)); });
  res.occ = V.occurrences.map(function (c) { return B.occurrences(c.rule, P(c.start), c.n, hol).map(C.iso); });
  res.clean = [B.clean({ id: 'a1', title: 'x', day: 15, months: 'even', how: 'prev', bank: true }), B.clean({ id: 'a1', title: 'x', day: 99, months: 'even', how: 'prev' }),
    B.clean({ id: 'a 1', title: 'x', day: 1, months: 'all', how: 'prev' }), B.clean({ id: 'a1', title: 'x', day: 1, months: 'sometimes', how: 'prev' }), B.clean({ id: 'a1', day: 1, months: 'all', how: 'sideways' })];
  document.getElementById('out').textContent = JSON.stringify(res);
})();
</script>"""

HARNESS = """<!doctype html><meta charset="utf-8"><title>rule</title><body><pre id="out">{}</pre><div id="host"></div><script>
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
async function open() {
  var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:1200px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (res) { f.onload = res; f.src = '/rule/?today=2026-10-11&preset=pension'; });
  await wait(800); return f;
}
(async function () {
  var out = {};
  localStorage.removeItem('atomou.rules.v1'); localStorage.removeItem('atomou.v1');
  var f = await open(), d = f.contentDocument;
  out.preview = d.getElementById('rule-preview').innerText;
  out.presetFields = [d.getElementById('r-title').value, d.getElementById('r-day').value, d.getElementById('r-months').value, d.getElementById('r-how').value, d.getElementById('r-bank').value];
  d.getElementById('r-save').click(); await wait(300);
  out.saved = d.getElementById('rule-list').innerText;
  out.storedRules = localStorage.getItem('atomou.rules.v1');
  d.querySelector('#rule-list [data-add]').click(); await wait(300);
  var st = JSON.parse(localStorage.getItem('atomou.v1') || '{}');
  out.entries = (st.entries || []).map(function (e) { return [e.title, e.date, e.kind, e.precision]; });
  f.remove();
  f = await open(); d = f.contentDocument;   // opened again: the rule is still there
  out.again = d.querySelectorAll('#rule-list .rule-item').length;
  out.wide = d.documentElement.scrollWidth > 376;
  d.getElementById('r-title').value = ''; d.querySelector('#rule-list [data-del]').click(); await wait(300);
  out.afterDelete = d.getElementById('rule-list').innerText; out.storedAfter = localStorage.getItem('atomou.rules.v1');
  // an own rule: the last day of each month, the next business day; and an empty name is not saved
  d.getElementById('r-title').value = ''; d.getElementById('r-day').value = '0'; d.getElementById('r-months').value = 'all'; d.getElementById('r-how').value = 'next'; d.getElementById('r-bank').value = 'office';
  d.getElementById('r-day').dispatchEvent(new Event('change', { bubbles: true }));
  out.ownPreview = d.getElementById('rule-preview').innerText;
  d.getElementById('r-save').click(); await wait(200);
  out.emptyName = localStorage.getItem('atomou.rules.v1');
  localStorage.setItem('atomou.rules.v1', JSON.stringify([{ id: 'ok1', title: '良い', day: 5, months: 'all', how: 'prev', bank: true }, { id: 'bad id', title: 'x', day: 5, months: 'all', how: 'prev' }, { id: 'ok2', day: 99, months: 'all', how: 'prev' }, 'junk']));
  f.remove(); f = await open(); d = f.contentDocument;
  out.junkKept = d.querySelectorAll('#rule-list .rule-item').length;
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


class InChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.html"
            src = PAGE % {"vectors": json.dumps(V)}
            p.write_text(src.replace("@@core@@", (ASSETS / "core.js").as_uri()).replace("@@rule@@", (ASSETS / "rule.js").as_uri()), encoding="utf-8")
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=6000", "--dump-dom", p.as_uri()],
                               capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=TODAY), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__rule.html").write_text(HARNESS, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=60000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__rule.html"], capture_output=True, timeout=240)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.ui = json.loads(html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_the_browser_gives_the_same_days_as_python_and_the_hand_counts(self):
        self.assertEqual(self.res["adjust"], [c["want"] for c in V["adjust"]])
        self.assertEqual(self.res["nominal"], [c["want"] for c in V["nominal"]])
        self.assertEqual(self.res["occ"], [c["want"] for c in V["occurrences"]])

    def test_a_rule_read_from_storage_is_checked(self):
        c = self.res["clean"]
        self.assertEqual(c[0], {"id": "a1", "title": "x", "day": 15, "months": "even", "how": "prev", "bank": True})
        self.assertEqual(c[1:], [None, None, None, None])

    def test_the_pension_preset_counts_the_next_days_and_a_day_can_be_put_into_the_planner(self):
        u = self.ui
        self.assertEqual(u["presetFields"], ["年金の支払日", "15", "even", "prev", "bank"])
        self.assertIn("偶数月の15日(休みなら前の銀行の営業日)", u["preview"])
        # today 2026-10-11: the 15th (a Thursday) is 4 days away; then 12/15, 2027-02-15, 2027-04-15
        for want in ("10月15日(木) あと4日", "12月15日(火) あと65日", "2月15日(月) あと127日", "4月15日(木) あと186日"):
            self.assertIn(want, u["preview"].replace("\n", " "))
        self.assertEqual(json.loads(u["storedRules"])[0]["title"], "年金の支払日")
        self.assertEqual(u["entries"], [["年金の支払日", "2026-10-15", "event", "day"]])

    def test_a_rule_is_kept_between_visits_deleted_and_never_wide(self):
        u = self.ui
        self.assertEqual(u["again"], 1)
        self.assertFalse(u["wide"])
        self.assertIn("保存したルールは、まだありません", u["afterDelete"])
        self.assertEqual(json.loads(u["storedAfter"]), [])

    def test_the_last_day_of_the_month_with_the_next_business_day(self):
        # 2026-10-31 is a Saturday -> Monday 11/2 (an office: weekend and holidays only); this month's turn is 21 days away
        self.assertIn("11月2日(月) あと22日", self.ui["ownPreview"].replace("\n", " "))

    def test_an_empty_name_is_not_saved_and_junk_is_dropped(self):
        self.assertIn(self.ui["emptyName"], ("[]", None))
        self.assertEqual(self.ui["junkKept"], 1)


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=True, today=TODAY)

    def test_the_pension_page_lists_two_years_with_the_hand_counted_days(self):
        p = self.pages["kyou/pension/index.html"]
        text = re.sub(r"<[^>]+>", " ", p)
        for y, days in PENSION.items():
            self.assertIn(f"{y}年の支払日", text)
            for iso in days:
                d = date.fromisoformat(iso)
                self.assertIn(f"{d.month}月{d.day}日({cal.wd(d)})", text.replace(" ", ""))
        flat = text.replace(" ", "")
        self.assertIn("15日は日曜日のため、前の平日", flat)        # 2026-02 and 2027-08
        self.assertIn("15日は土曜日のため、前の平日", flat)        # 2026-08
        self.assertIn("nenkin.go.jp", p)
        self.assertIn("かならず確かめてください", text)
        self.assertIn('href="/kyou/pension/"', self.pages["kyou/index.html"])
        self.assertIn("/kyou/pension/", self.pages["sitemap.xml"])
        self.assertNotIn("/kyou/pension/", self.pages["index.html"])        # not in the home page: it hangs under /kyou/ (owner, 2026-10-11)

    def test_the_rule_page_has_the_holidays_and_is_not_listed(self):
        r = self.pages["rule/index.html"]
        hol = json.loads(html.unescape(re.search(r'data-hol="([^"]*)"', r).group(1)))
        self.assertIn("2027-01-01", hol)
        self.assertIn("2028-11-23", hol)
        self.assertEqual(hol, sorted(hol))
        self.assertIn('data-last="2028-12-31"', r)
        self.assertIn("noindex", r)
        self.assertNotIn("pagead2.googlesyndication", r)
        self.assertNotIn("/rule/", self.pages["sitemap.xml"])
        self.assertIn("rule", build.BUNDLE)
        flat = re.sub(r"<[^>]+>", "", r)
        for must in ("銀行法施行令", "目安であること", "確かめてください", "この端末の中にだけ残ります"):
            self.assertIn(must, flat)


if __name__ == "__main__":
    unittest.main()
