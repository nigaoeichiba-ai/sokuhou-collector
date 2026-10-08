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


PAGE = """<!doctype html><meta charset="utf-8"><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script>
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
    { uid: 'm-1', title: 'うるう日', date: [2024, 2, 29], yearly: true, every100: true, alarm: 'eve' }, { uid: 'q', title: '静か', date: [2020, 3, 1], alarm: 'none' },
    { uid: 'w', title: '一週間前', date: [2026, 12, 1], alarm: 'week' }],
    'あと何日、もう何日', new Date(Date.UTC(2026, 9, 8, 1, 2, 3)));
  var A = window.Atomou, T = function (kind, title, date, extra) { return A.tipFor(Object.assign({ kind: kind, title: title, date: date, precision: 'day' }, extra || {}), [2026, 10, 8]); };
  res.tips = {
    sanki: T('memorial', '命日', '2024-10-20', { yearly: true, quiet: true }),
    isshuki: T('memorial', 'ペットの命日', '2025-12-01', { yearly: true, quiet: true }),
    disaster: T('memorial', 'あの日', '2020-10-20', { yearly: true, quiet: true }),
    memorialFar: T('memorial', '命日', '2024-03-01', { yearly: true, quiet: true }),
    passed: T('anniversary', '付き合った日', '2020-10-01', { yearly: true }),
    soon: T('anniversary', '結婚記念日', '2020-10-12', { yearly: true }),
    birthday: T('birthday', '誕生日', '2000-10-08', { yearly: true }),
    birthdayPassed: T('birthday', '誕生日', '2000-09-20', { yearly: true }),
    since: T('since', '禁煙', '2026-07-01', { every100: true }),
    sinceFar: T('since', '禁煙', '2026-09-01', { every100: true }),
    future: T('anniversary', '未来', '2027-01-01', { yearly: true }),
    until: T('until', '旅行', '2026-01-01', {})
  };
  res.when = ['year-end', 'new-year', 'fy-start', 'fy-end', 'today', 'nope'].map(function (t) { var d = A.whenToken(t); return d ? C.iso(d) : null; });
  A.stat('view:home'); A.stat('act:add:memorial'); A.stat('act:skin:pastel-pink'); A.stat('act:search_miss');
  ['view:ホーム', 'act:add:' + 'x'.repeat(70), 'unknown:thing', 'act', 'act:a:b:c', 'act:Save', 'view:home;drop'].forEach(function (k) { A.stat(k); });
  res.statQ = A.statQueue();
  var a1 = A.normalize({ updated: '2026-10-08T10:00:00.000Z', entries: [{ id: 'x1', title: '端末A', date: '2024-01-01' }, { id: 'x2', title: '消した', date: '2024-01-02' }], saved: ['aaaaaaaaaa'], deleted: [],
    prefs: { skin: 'basic', big: false } });
  var b1 = A.normalize({ updated: '2026-10-08T11:00:00.000Z', entries: [{ id: 'x3', title: '端末B', date: '2024-01-03' }, { id: 'x1', title: '端末Bで直した', date: '2024-01-01' }], saved: ['bbbbbbbbbb'],
    deleted: ['x2'], prefs: { skin: 'basic', big: true, alarm: 'week' } });
  var m = A.mergeStates(a1, b1);
  res.merge = { ids: m.entries.map(function (e) { return e.id + ':' + e.title; }).sort(), saved: m.saved.sort(), deleted: m.deleted, big: m.prefs.big, alarm: m.prefs.alarm, updated: m.updated };
  var m2 = A.mergeStates(b1, a1);
  res.mergeSym = { ids: m2.entries.map(function (e) { return e.id + ':' + e.title; }).sort(), big: m2.prefs.big };
  document.getElementById('out').textContent = JSON.stringify(res);
})();
</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class CoreInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "t.html"
            page.write_text(PAGE % {"core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "app": (ASSETS / "app.js").as_uri(), "vectors": json.dumps(VECTORS)}, encoding="utf-8")
            prof = Path(td) / "prof"
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-08"], capture_output=True, timeout=120)
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
        self.assertEqual(unfolded.count("BEGIN:VALARM"), 4)  # the first two events and the 100-day series of the second; the third asked for none
        self.assertEqual(unfolded.count("BEGIN:VEVENT"), 5)  # four events + the 100-day series of the second
        self.assertIn("TRIGGER:-P6DT15H", unfolded)  # one week before, 9:00

    def test_tips_are_gentle_and_correct(self):
        t = self.res["tips"]
        self.assertIn("三回忌", t["sanki"])          # 2024-10-20 -> the second anniversary of the death is the 三回忌
        self.assertIn("一周忌", t["isshuki"])
        self.assertNotIn("回忌", t["disaster"])     # a disaster day is not given a Buddhist memorial name
        self.assertIn("もうすぐ同じ日", t["disaster"])
        self.assertEqual(t["memorialFar"], "")
        self.assertIn("プレゼント", t["passed"])
        self.assertIn("4日後", t["soon"])
        self.assertIn("今日は誕生日", t["birthday"])
        self.assertIn("メッセージ", t["birthdayPassed"])
        self.assertIn("もうすぐ100日目", t["since"])
        self.assertEqual((t["sinceFar"], t["future"], t["until"]), ("", "", ""))
        for k in ("sanki", "isshuki", "disaster"):  # grief entries: no congratulations, no gifts, no sales words
            for bad in ("おめでとう", "プレゼント", "お祝い", "セール", "おすすめ", "!", "!"):
                self.assertNotIn(bad, t[k], k)

    def test_statistics_keys_are_limited_to_the_fixed_vocabulary(self):
        q = self.res["statQ"]
        self.assertEqual(sorted(q), ["act:add:memorial", "act:search_miss", "act:skin:pastel-pink", "skin:basic", "view:home", "view:other"])  # the last two are the page view recorded at start
        self.assertTrue(all(v == 1 for v in q.values()))

    def test_sync_merge_unites_entries_and_respects_deletions(self):
        m = self.res["merge"]
        self.assertEqual(m["ids"], ["x1:端末Bで直した", "x3:端末B"])  # x2 was deleted on B; x1 exists on both: the newer side's copy wins
        self.assertEqual(m["saved"], ["aaaaaaaaaa", "bbbbbbbbbb"])
        self.assertEqual((m["big"], m["alarm"], m["deleted"]), (True, "week", ["x2"]))  # settings come from the newer device
        self.assertEqual(self.res["mergeSym"], {"ids": m["ids"], "big": True})  # the order of the two arguments does not matter

    def test_today_tokens(self):
        self.assertEqual(self.res["when"], ["2026-12-31", "2027-01-01", "2027-04-01", "2027-03-31", "2026-10-08", None])


STORE_PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['締切・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } } };
localStorage.setItem('atomou.v1', %(stored)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script>
<script>document.getElementById('out').textContent = JSON.stringify({ state: window.Atomou.state(), broken: localStorage.getItem('atomou.v1.broken') });</script>"""


def run_store_page(stored_js: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "s.html"
        page.write_text(STORE_PAGE % {"stored": stored_js, "core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "app": (ASSETS / "app.js").as_uri()}, encoding="utf-8")
        r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                            "--dump-dom", page.as_uri()], capture_output=True, timeout=120)
    dom = r.stdout.decode("utf-8", "replace")
    a = dom.index('<pre id="out">') + len('<pre id="out">')
    return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class StorageIsSanitised(unittest.TestCase):
    """Anything in localStorage (or in a restored backup file) is reduced to known shapes before it can reach innerHTML or a CSS selector."""

    def test_hostile_values_are_dropped_or_rounded(self):
        evil = {"entries": [{"id": "ok1", "title": "<img src=x onerror=1>", "date": "2026-10-10", "precision": 'day" onmouseover="x', "kind": "evil", "alarm": "zzz"},
                            {"id": "bad id", "date": "2026-10-10"}, {"id": "x2", "date": "2026-02-30"}, "str", None],
                "saved": ["abcdef0123", '"><script>', "ABCDEF0123"], "order": ["c:abcdef0123", "evil", 'm:"]'],
                "genre": {"締切・制度": 99, "x": 5}, "prefs": {"skin": "nope", "big": 1, "alarm": "x", "blocks": {"order": ["search", "evil"], "hidden": ["cats", "x"]}}}
        res = run_store_page(json.dumps(json.dumps(evil)))
        st = res["state"]
        self.assertEqual(len(st["entries"]), 1)
        e = st["entries"][0]
        self.assertEqual((e["precision"], e["kind"], e["alarm"], e["date"]), ("day", "memo", "morning", "2026-10-10"))
        self.assertEqual(st["saved"], ["abcdef0123"])
        self.assertEqual(st["order"], ["c:abcdef0123"])
        self.assertEqual(st["genre"], {"締切・制度": 20})
        self.assertEqual((st["prefs"]["skin"], st["prefs"]["big"], st["prefs"]["alarm"]), ("basic", True, "morning"))
        self.assertEqual(st["prefs"]["blocks"], {"order": ["search"], "hidden": ["cats"]})
        self.assertIsNone(res["broken"])

    def test_unreadable_data_is_kept_aside_not_overwritten(self):
        res = run_store_page(json.dumps("{not json"))
        self.assertEqual(res["state"]["entries"], [])
        self.assertEqual(res["broken"], "{not json")


if __name__ == "__main__":
    unittest.main()
