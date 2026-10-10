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


# (what was typed or dictated, the precision chosen, the day it means with today = 2026-10-09)
SPOKEN = [
    ("12月25日", "day", [2026, 12, 25]), ("2027年3月3日", "day", [2027, 3, 3]), ("令和8年4月1日", "day", [2026, 4, 1]), ("平成元年1月8日", "day", [1989, 1, 8]),
    ("二〇二七年三月三日", "day", [2027, 3, 3]), ("十二月二十五日", "day", [2026, 12, 25]), ("2027/3/3", "day", [2027, 3, 3]), ("2027-03-03", "day", [2027, 3, 3]),
    ("２０２７年１２月２５日。", "day", [2027, 12, 25]), (" 12 月 25 日 ", "day", [2026, 12, 25]),
    ("今日", "day", [2026, 10, 9]), ("明日", "day", [2026, 10, 10]), ("明後日", "day", [2026, 10, 11]), ("昨日", "day", [2026, 10, 8]), ("あさって", "day", [2026, 10, 11]), ("きょう", "day", [2026, 10, 9]),
    ("10月9日", "day", [2026, 10, 9]), ("10月8日", "day", [2027, 10, 8]),     # no year: the next time that day comes, and today counts
    ("2月29日", "day", [2028, 2, 29]),                                       # 2027 has none
    ("2026年10月", "month", [2026, 10, 1]), ("11月", "month", [2026, 11, 1]), ("9月", "month", [2027, 9, 1]), ("1990年", "year", [1990, 1, 1]), ("1990", "year", [1990, 1, 1]),
    ("2027年3月", "day", None), ("2027年13月1日", "day", None), ("2027年2月30日", "day", None), ("abc", "day", None), ("", "day", None), ("2027年3月3日", "month", None),
    ("0年", "year", None), ("9999年", "year", None), ("12月25日", "year", None),
]


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
  res.spoken = %(spoken)s.map(function (c) { return C.parseSpoken(c[0], c[1], [2026, 10, 9]); });
  res.ics = ICS.build([{ uid: 'e-abc', title: 'テスト, 試験; 申込\\n締切', date: [2026, 11, 20], alarm: 'morning' },
    { uid: 'm-1', title: 'うるう日', date: [2024, 2, 29], yearly: true, every100: true, alarm: 'eve' }, { uid: 'q', title: '静か', date: [2020, 3, 1], alarm: 'none' },
    { uid: 'w', title: '一週間前', date: [2026, 12, 1], alarm: 'week' }],
    'あと何日、もう何日', new Date(Date.UTC(2026, 9, 8, 1, 2, 3)));
  res.icsTimed = ICS.build([{ uid: 't1', title: '歯医者', date: [2026, 12, 1], time: '15:30', alarm: 'morning' },
    { uid: 't2', title: '早朝', date: [2026, 12, 2], time: '07:00', alarm: 'morning' },
    { uid: 't3', title: '深夜', date: [2026, 12, 3], time: '23:30', alarm: 'eve', yearly: true },
    { uid: 't4', title: '一週間前', date: [2026, 12, 4], time: '10:00', alarm: 'week' },
    { uid: 't5', title: '時刻が不正', date: [2026, 12, 5], time: '25:99', alarm: 'none' }], 'x', new Date(Date.UTC(2026, 9, 8, 1, 2, 3)));
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
            page.write_text(PAGE % {"core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "app": (ASSETS / "app.js").as_uri(), "vectors": json.dumps(VECTORS), "spoken": json.dumps([c[:2] for c in SPOKEN], ensure_ascii=False)}, encoding="utf-8")
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

    def test_a_date_typed_or_dictated_as_words_is_read_the_way_it_was_said(self):
        for (text, p, want), got in zip(SPOKEN, self.res["spoken"]):
            self.assertEqual(got, want, f"{text!r} ({p})")

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

    def test_a_day_with_a_time_becomes_a_one_hour_event_in_japan_time(self):
        # 2026-10-09 core check: the time of an event used to be dropped, and it became an all-day entry
        ics = self.res["icsTimed"].replace("\r\n ", "")
        self.assertIn("BEGIN:VTIMEZONE\r\nTZID:Asia/Tokyo", ics)
        self.assertIn("DTSTART;TZID=Asia/Tokyo:20261201T153000", ics)
        self.assertIn("DTEND;TZID=Asia/Tokyo:20261201T163000", ics)
        self.assertIn("TRIGGER:-PT6H30M", ics)               # 15:30 with the 9:00 morning alert
        self.assertIn("TRIGGER:-PT30M", ics)                 # 07:00 is before 9:00: 30 minutes before
        self.assertIn("DTSTART;TZID=Asia/Tokyo:20261203T233000", ics)
        self.assertIn("DTEND;TZID=Asia/Tokyo:20261204T003000", ics)   # across midnight
        self.assertIn("TRIGGER:-P1DT2H30M", ics)             # the evening before at 21:00 for an event at 23:30: 26.5 hours
        self.assertIn("TRIGGER:-P7DT1H", ics)                # a week before at 9:00 for an event at 10:00: 7 days 1 hour
        self.assertIn("DTSTART;VALUE=DATE:20261205", ics)    # an invalid time stays all-day
        self.assertEqual(ics.count("BEGIN:VTIMEZONE"), 1)
        self.assertNotIn("BEGIN:VTIMEZONE", self.res["ics"])  # no timed event: no zone block

    def test_tips_are_gentle_and_correct(self):
        t = self.res["tips"]
        self.assertIn("三回忌", t["sanki"])          # 2024-10-20 -> the second anniversary of the death is the 三回忌
        self.assertIn("一周忌", t["isshuki"])
        self.assertNotIn("回忌", t["disaster"])     # a disaster day is not given a Buddhist memorial name
        self.assertIn("まもなく同じ日", t["disaster"])
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
window.ATOMOU = { v: 'x', groups: ['お金・税金・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } } };
localStorage.setItem('atomou.v1', %(stored)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(plan)s"></script>
<script>document.getElementById('out').textContent = JSON.stringify({ state: window.Atomou.state(), broken: localStorage.getItem('atomou.v1.broken'), plan: window.AtomouPlan ? (function () {
  var A = window.AtomouApp, P = window.AtomouPlan, items = P.planItems([]), D = function (s) { return A.C.parse(s); };
  return { n: items.length, on10: P.eventsOn(items, D('2026-10-10')).map(function (i) { return i.title + '@' + i.time; }), on12: P.eventsOn(items, D('2026-10-12')).map(function (i) { return i.title; }),
    on2030: P.eventsOn(items, D('2030-10-12')).map(function (i) { return i.title; }), off11: P.eventsOn(items, D('2026-10-11')).length,
    tasks07: P.tasksOn(items, D('2026-10-07')).map(function (o) { return o.t.text; }), tasks09: P.tasksOn(items, D('2026-10-09')).map(function (o) { return o.t.text; }),
    todo: P.todoRows(items).map(function (r) { return r.k + ':' + r.it.title + ':' + r.n + (r.t ? ':' + r.t.text : ''); }) };
})() : null });</script>"""


def run_store_page(stored_js: str, query: str = "") -> dict:
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "s.html"
        page.write_text(STORE_PAGE % {"stored": stored_js, "core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "app": (ASSETS / "app.js").as_uri(), "plan": (ASSETS / "plan.js").as_uri()}, encoding="utf-8")
        r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                            "--dump-dom", page.as_uri() + query], capture_output=True, timeout=120)
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
                "genre": {"お金・税金・制度": 99, "x": 5}, "prefs": {"skin": "nope", "big": 1, "alarm": "x", "blocks": {"order": ["search", "evil"], "hidden": ["cats", "x"]}}}
        res = run_store_page(json.dumps(json.dumps(evil)))
        st = res["state"]
        self.assertEqual(len(st["entries"]), 1)
        e = st["entries"][0]
        self.assertEqual((e["precision"], e["kind"], e["alarm"], e["date"]), ("day", "memo", "", "2026-10-10"))
        self.assertEqual(st["saved"], ["abcdef0123"])
        self.assertEqual(st["order"], ["c:abcdef0123"])
        self.assertEqual(st["genre"], {"お金・税金・制度": 20})
        self.assertEqual((st["prefs"]["skin"], st["prefs"]["big"], st["prefs"]["alarm"]), ("basic", True, "morning"))
        self.assertEqual(st["prefs"]["blocks"], {"order": ["search"], "hidden": ["cats"]})
        self.assertIsNone(res["broken"])

    def test_the_schedule_book_places_events_tasks_and_todays_list(self):
        stored = {"entries": [{"id": "e1", "title": "デート", "date": "2026-10-10", "kind": "event", "time": "19:00"},
                              {"id": "b1", "title": "誕生日", "date": "2000-10-12", "kind": "birthday", "yearly": True},
                              {"id": "w1", "title": "5月の予定", "date": "2026-05-01", "kind": "event"}],
                  "notes": {"m:e1": {"memo": "店を予約", "tasks": [{"id": "t1", "before": 3, "text": "予約", "done": False}, {"id": "t2", "before": 1, "text": "花", "done": True},
                                                                  {"id": "t3", "before": 400, "text": "範囲外", "done": False}]},
                            "m:nope!": {"memo": "x", "tasks": []}}}
        res = run_store_page(json.dumps(json.dumps(stored)), "?today=2026-10-08")
        pl = res["plan"]
        self.assertEqual(pl["n"], 3)
        self.assertEqual(pl["on10"], ["デート@19:00"])
        self.assertEqual(pl["on12"], ["誕生日"])
        self.assertEqual(pl["on2030"], ["誕生日"])   # a yearly day is on its date every later year
        self.assertEqual(pl["off11"], 0)
        self.assertEqual(pl["tasks07"], ["予約"])    # 3 days before 10-10
        self.assertEqual(pl["tasks09"], ["花"])      # done tasks stay on the calendar, they are only not in today's list
        self.assertEqual(len(res["state"]["notes"]["m:e1"]["tasks"]), 2)  # the out-of-range task and the odd key were dropped
        self.assertNotIn("m:nope!", res["state"]["notes"])
        # today's list (2026-10-08): the date is 2 days away; the "予約" task was due yesterday, so it is overdue; the done task and the far birthday are not there
        self.assertEqual(pl["todo"], ["task:デート:-1:予約", "event:デート:2"])

    def test_unreadable_data_is_kept_aside_not_overwritten(self):
        res = run_store_page(json.dumps("{not json"))
        self.assertEqual(res["state"]["entries"], [])
        self.assertEqual(res["broken"], "{not json")


DRAG_PAGE = """<!doctype html><meta charset="utf-8"><body data-page="x"><style>.card{display:block;height:80px;margin:0 0 10px;width:300px}</style>
<div class="cards" id="g" data-save-order="1">
<article class="card" data-key="c:aaaaaaaaaa"><h3>A</h3><div class="c-act"><button type="button">b</button></div></article>
<article class="card" data-key="c:bbbbbbbbbb"><h3>B</h3><div class="c-act"><button type="button">b</button></div></article>
<article class="card" data-key="c:cccccccccc"><h3>C</h3><div class="c-act"><button type="button">b</button></div></article></div>
<div class="cards" id="other"><article class="card" data-key="c:dddddddddd"><h3>D</h3></article></div>
<pre id="out">pending</pre><script src="%(core)s"></script><script src="%(ics)s"></script><script src="%(app)s"></script>
<script>
(function () {
  var g = document.getElementById('g'), out = { steps: [] };
  function keys() { return Array.prototype.map.call(g.querySelectorAll('.card'), function (c) { return c.getAttribute('data-key').charAt(2); }).join(''); }
  function pe(type, el, x, y) { el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: 'mouse', button: 0, clientX: x, clientY: y })); }
  function ctr(el, fx, fy) { var r = el.getBoundingClientRect(); return [r.left + r.width * (fx == null ? .5 : fx), r.top + r.height * (fy == null ? .5 : fy)]; }
  var cards = g.querySelectorAll('.card'), A = cards[0], C = cards[2], a = ctr(A.querySelector('h3'), .2, .5), c = ctr(C, .9, .9);
  pe('pointerdown', A.querySelector('h3'), a[0], a[1]); pe('pointermove', document.body, a[0] + 3, a[1]); out.steps.push(['small move keeps order', keys()]);
  pe('pointermove', document.body, a[0] + 30, a[1] + 5); out.ghost = !!document.querySelector('.card.ghost'); out.dimmed = A.classList.contains('dragging');
  pe('pointermove', document.body, c[0], c[1]); pe('pointerup', document.body, c[0], c[1]);
  out.mouse = keys(); out.ghostGone = !document.querySelector('.card.ghost'); out.order = JSON.stringify(window.Atomou.state().order);
  var bt = g.querySelector('.c-act button'), bb = ctr(bt); pe('pointerdown', bt, bb[0], bb[1]); pe('pointermove', document.body, bb[0] + 40, bb[1] + 40); pe('pointerup', document.body, bb[0] + 40, bb[1] + 40);
  out.buttonSafe = keys() === out.mouse;
  var D = document.querySelector('#other .card'), d = ctr(D); pe('pointerdown', D, d[0], d[1]); pe('pointermove', document.body, d[0] + 50, d[1]); out.otherGhost = !!document.querySelector('.card.ghost'); pe('pointerup', document.body, d[0], d[1]);
  function te(type, el, x, y) {
    var t = new Touch({ identifier: 1, target: el, clientX: x, clientY: y }), list = type === 'touchend' ? [] : [t];
    el.dispatchEvent(new TouchEvent(type, { bubbles: true, cancelable: true, touches: list, targetTouches: list, changedTouches: [t] }));
  }
  var first = g.querySelectorAll('.card')[0], f = ctr(first), last = g.querySelectorAll('.card')[2], l = ctr(last, .9, .9), before = keys();
  te('touchstart', first.querySelector('h3'), f[0], f[1]);
  setTimeout(function () {
    out.touchHeld = !!document.querySelector('.card.ghost');
    te('touchmove', document.body, l[0], l[1]); te('touchend', document.body, l[0], l[1]);
    out.touch = keys(); out.touchBefore = before; out.touchGhostGone = !document.querySelector('.card.ghost');
    var one = g.querySelectorAll('.card')[0], o = ctr(one), k0 = keys();
    te('touchstart', one.querySelector('h3'), o[0], o[1]); te('touchmove', document.body, o[0], o[1] + 60);
    setTimeout(function () { out.swipeSafe = !document.querySelector('.card.ghost') && keys() === k0; te('touchend', document.body, o[0], o[1] + 60);
      document.getElementById('out').textContent = JSON.stringify(out); }, 600);
  }, 450);
})();
</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class CardsCanBeDragged(unittest.TestCase):
    """The cards of the home / my page: grabbed anywhere with the mouse, held with a finger, not from a button, not in a grid that does not save its order."""

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "d.html"
            page.write_text(DRAG_PAGE % {"core": (ASSETS / "core.js").as_uri(), "ics": (ASSETS / "ics.js").as_uri(), "app": (ASSETS / "app.js").as_uri()}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=6000", "--force-prefers-reduced-motion",
                                "--window-size=800,900", "--dump-dom", page.as_uri() + "?today=2026-10-08"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_mouse_drag_from_the_card_text(self):
        r = self.res
        self.assertEqual(r["steps"][0][1], "abc")           # a 3px wobble is a click, not a drag
        self.assertTrue(r["ghost"] and r["dimmed"])          # a floating copy follows the pointer; the real card is dimmed
        self.assertEqual(r["mouse"], "bca")                  # A was dropped after C
        self.assertTrue(r["ghostGone"])
        self.assertEqual(json.loads(r["order"]), ["c:bbbbbbbbbb", "c:cccccccccc", "c:aaaaaaaaaa"])  # and the order is kept

    def test_buttons_and_other_grids_do_not_start_a_drag(self):
        self.assertTrue(self.res["buttonSafe"])
        self.assertFalse(self.res["otherGhost"])

    def test_touch_press_and_hold_drags_but_a_swipe_scrolls(self):
        r = self.res
        self.assertTrue(r["touchHeld"])
        self.assertNotEqual(r["touch"], r["touchBefore"])
        self.assertEqual(r["touch"], r["touchBefore"][1:] + r["touchBefore"][0])  # the first card went to the end
        self.assertTrue(r["touchGhostGone"])
        self.assertTrue(r["swipeSafe"])


if __name__ == "__main__":
    unittest.main()
