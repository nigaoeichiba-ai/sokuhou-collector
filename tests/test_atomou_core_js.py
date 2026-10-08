"""atomou: the browser's date core (assets/core.js) and calendar writer (assets/ics.js), run in a real headless Chrome against the same hand-verified
vectors as the Python core (tests/fixtures/atomou/date_vectors.json).  Python and JavaScript must never disagree about a day count."""
import html
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ASSETS = ROOT / "sites" / "atomou" / "assets"
VECTORS = json.loads((ROOT / "tests" / "fixtures" / "atomou" / "date_vectors.json").read_text(encoding="utf-8"))
CHROME_PATHS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser")


def find_chrome():
    return next((p for p in CHROME_PATHS if Path(p).exists()), None) or shutil.which("google-chrome") or shutil.which("chromium")


PAGE = """<!doctype html><meta charset="utf-8"><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre>
<script>
(function () {
  var V = %(vectors)s, C = AtomouCore, ICS = AtomouICS, P = C.parse, res = {};
  res.ymd = V.ymd.map(function (c) { var r = C.ymd(P(c.a), P(c.b)); return [r[0], r[1], r[2], C.totalDays(P(c.a), P(c.b))]; });
  res.countdown = V.countdown.map(function (c) { var r = C.countdown(P(c.target), P(c.today)); return [r.dir, r.big, r.sub]; });
  res.prec = V.countdown_precision.map(function (c) { var r = C.countdown(P(c.target), P(c.today), c.precision); return [r.dir, r.big, r.approx]; });
  res.doy = V.day_of_year.map(function (c) { return C.dayOfYear(P(c.d)); });
  res.fy = V.fiscal_year.map(function (c) { return C.fiscalYear(P(c.d)); });
  res.nt = V.next_thousand.map(function (c) { var r = C.nextThousand(P(c.start), P(c.today)); return [r.days, C.iso(r.date)]; });
  res.wareki = V.wareki.map(function (c) { return C.warekiToYear(c.era, c.n); });
  res.bad = ['2026-02-30', '2026-13-01', 'abc', '2026-1-1'].map(function (s) { return P(s); });
  res.ics = ICS.build([{ uid: 'e-abc', title: 'テスト, 試験; 申込\\n締切', date: [2026, 11, 20], alarm: 'morning' },
    { uid: 'm-1', title: 'うるう日', date: [2024, 2, 29], yearly: true, every100: true, alarm: 'eve' }, { uid: 'q', title: '静か', date: [2020, 3, 1], alarm: 'none' }],
    'あと何日、もう何日', new Date(Date.UTC(2026, 9, 8, 1, 2, 3)));
  document.getElementById('out').textContent = JSON.stringify(res);
})();
</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class CoreInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "t.html"
            page.write_text(PAGE % {"core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "vectors": json.dumps(VECTORS)}, encoding="utf-8")
            prof = Path(td) / "prof"
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri()], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_ymd_and_total(self):
        self.assertEqual(self.res["ymd"], [[c["y"], c["m"], c["d"], c["total"]] for c in VECTORS["ymd"]])

    def test_countdown(self):
        self.assertEqual(self.res["countdown"], [[c["dir"], c["big"], c["sub"]] for c in VECTORS["countdown"]])

    def test_countdown_precision(self):
        self.assertEqual(self.res["prec"], [[c["dir"], c["big"], True] for c in VECTORS["countdown_precision"]])

    def test_day_year_fiscal_thousand_wareki(self):
        self.assertEqual(self.res["doy"], [[c["n"], c["left"]] for c in VECTORS["day_of_year"]])
        self.assertEqual(self.res["fy"], [[c["start"], c["n"], c["left"]] for c in VECTORS["fiscal_year"]])
        self.assertEqual(self.res["nt"], [[c["days"], c["date"]] for c in VECTORS["next_thousand"]])
        self.assertEqual(self.res["wareki"], [c["y"] for c in VECTORS["wareki"]])

    def test_invalid_dates_are_rejected(self):
        self.assertEqual(self.res["bad"], [None, None, None, None])

    def test_ics_is_well_formed(self):
        ics = self.res["ics"]
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n"))
        lines = ics.split("\r\n")[:-1]
        self.assertTrue(all(len(l.encode("utf-8")) <= 75 for l in lines), "a line is longer than 75 octets")
        unfolded = ics.replace("\r\n ", "")
        for key in ("DTSTART;VALUE=DATE:20261120", "DTEND;VALUE=DATE:20261121", "UID:e-abc@atomou.com", "TRIGGER:PT9H", "TRIGGER:-PT3H",
                    "RRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=-1", "DTSTART;VALUE=DATE:20240608", "RRULE:FREQ=DAILY;INTERVAL=100;COUNT=60", "DTSTAMP:20261008T010203Z"):
            self.assertIn(key, unfolded)
        self.assertIn("SUMMARY:テスト\\, 試験\\; 申込\\n締切", unfolded)  # comma, semicolon and newline are escaped
        self.assertEqual(unfolded.count("BEGIN:VEVENT"), unfolded.count("END:VEVENT"))
        self.assertEqual(unfolded.count("BEGIN:VALARM"), 3)  # the first two events and the 100-day series of the second; the third asked for none
        self.assertEqual(unfolded.count("BEGIN:VEVENT"), 4)  # three events + the 100-day series of the second


if __name__ == "__main__":
    unittest.main()
