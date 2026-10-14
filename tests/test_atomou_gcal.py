"""atomou: sending the visitor's days to a calendar of their own in Google Calendar, straight from the browser (assets/gcal.js).  The real script runs in a headless Chrome against a
fake Google: the events are built the way the API wants them, sending twice updates instead of duplicating, a day taken away is taken away from Google, a calendar deleted in Google is
made again, a refusal is reported, and the one permission asked is the narrow one (calendar.app.created).  The page and the privacy page say what is sent."""
import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402
from tests.test_atomou_core_js import find_chrome  # noqa: E402

ASSETS = ROOT / "sites" / "atomou" / "assets"
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))

PAGE = """<!doctype html><meta charset="utf-8"><script src="@@core@@"></script><script src="@@ics@@"></script><script src="@@gcal@@"></script><pre id="out">pending</pre>
<script>
(function () {
  var C = AtomouCore, G = AtomouGcal, P = C.parse, res = {};
  function fake(handler, log) {
    return function (url, opt) {
      var path = url.replace('https://www.googleapis.com/calendar/v3', ''), body = opt.body ? JSON.parse(opt.body) : null;
      log.push(opt.method + ' ' + path);
      var r = handler(opt.method, path, body, opt.headers.Authorization);
      return Promise.resolve({ status: r[0], json: function () { return Promise.resolve(r[1] || {}); } });
    };
  }
  res.ids = ['m-abc', 'e-0123456789', 'm-abc-100', 'm-a', 'm-あ'].map(G.idOf);
  res.ids2 = ['m-abc'].map(G.idOf);
  var allday = G.body({ uid: 'm-abc', title: '結婚記念日', date: P('2027-05-03'), yearly: true, alarm: 'eve', reminds: [7, 14] });
  res.allday = allday;
  res.alarms = ['morning', 'eve', 'week', 'none'].map(function (a) { return G.body({ uid: 'm-x', title: 't', date: P('2027-05-03'), alarm: a }).reminders.overrides.map(function (o) { return o.minutes; }); });
  res.timed = G.body({ uid: 'm-t', title: '会議', date: P('2027-05-03'), time: '23:30', alarm: 'morning' });
  res.timedEarly = G.body({ uid: 'm-t2', title: '朝', date: P('2027-05-03'), time: '08:00', alarm: 'morning' });
  res.leap = G.body({ uid: 'm-l', title: 'うるう日', date: P('2028-02-29'), yearly: true, alarm: 'none' }).recurrence;
  res.many = G.body({ uid: 'm-m', title: 'x', date: P('2027-05-03'), alarm: 'week', reminds: [1, 2, 3, 4, 5, 6, 40] }).reminders.overrides.map(function (o) { return o.minutes; });
  res.expand = G.expand([{ uid: 'm-h', title: '出会った日', date: P('2026-10-01'), every100: true, alarm: 'none' }]).map(function (e) { return [e.uid, C.iso(e.date), e.rrule || '']; });

  var A = { uid: 'm-a1', title: 'A', date: P('2027-01-10'), alarm: 'none' }, B = { uid: 'm-b2', title: 'B', date: P('2027-02-10'), alarm: 'none', every100: true };
  var log1 = [], st1 = null, log2 = [], log3 = [], log4 = [], log5 = [], log6 = [], log7 = [];
  var chain = G.send('TOK', [A, B], { cal: '', sent: [] }, fake(function (m, p) { if (m === 'POST' && p === '/calendars') return [200, { id: 'cal123@group.calendar.google.com' }]; return [200, {}]; }, log1))
    .then(function (r) {
      res.first = { added: r.added, updated: r.updated, removed: r.removed, state: r.state, log: log1 };
      // the second press: the same days again, one taken away and a new one
      var C2 = { uid: 'm-c3', title: 'C', date: P('2027-03-10'), alarm: 'none' };
      return G.send('TOK', [A, C2], r.state, fake(function () { return [200, {}]; }, log2));
    }).then(function (r) {
      res.second = { added: r.added, updated: r.updated, removed: r.removed, sent: r.state.sent, log: log2 };
      // a new device: the calendar is known, the list of sent days is empty and the ids are taken (409) -> updated
      return G.send('TOK', [A], { cal: 'cal123@group.calendar.google.com', sent: [] }, fake(function (m) { return m === 'POST' ? [409, {}] : [200, {}]; }, log3));
    }).then(function (r) {
      res.taken = { added: r.added, updated: r.updated, log: log3 };
      // the calendar was deleted in Google: every call under it answers 404 until a new one is made
      return G.send('TOK', [A], { cal: 'gone@group.calendar.google.com', sent: ['m-a1'] }, fake(function (m, p) {
        if (p === '/calendars' && m === 'POST') return [200, { id: 'new456@group.calendar.google.com' }];
        if (p.indexOf('gone%40group') >= 0) return [404, {}];
        return [200, {}];
      }, log4));
    }).then(function (r) {
      res.gone = { cal: r.state.cal, added: r.added, updated: r.updated, log: log4 };
      // a refusal (the Calendar API is not allowed for this app, or the permission is missing)
      return G.send('TOK', [A], { cal: '', sent: [] }, fake(function (m, p) { return [403, { error: 'x' }]; }, log5)).then(function () { res.refused = 'no error'; }, function (e) { res.refused = e.status; });
    }).then(function () {
      return G.unlink('TOK', { cal: 'cal123@group.calendar.google.com', sent: ['m-a1'] }, fake(function () { return [204, null]; }, log6));
    }).then(function (st) {
      res.unlink = { state: st, log: log6 };
      return G.unlink('TOK', { cal: '', sent: [] }, fake(function () { return [500]; }, log7)).then(function (s2) { res.unlinkNone = { state: s2, calls: log7.length }; });
    }).then(function () { document.getElementById('out').textContent = JSON.stringify(res); },
            function (e) { document.getElementById('out').textContent = JSON.stringify({ error: String(e && e.stack || e) }); });
})();
</script>"""


class GcalInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest("browser checks run locally")
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "g.html"
            src = PAGE
            for k in ("core", "ics", "gcal"):        # not "%": the script has a JavaScript remainder operator
                src = src.replace("@@" + k + "@@", (ASSETS / f"{k}.js").as_uri())
            page.write_text(src, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=5000",
                                "--dump-dom", page.as_uri()], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))
        assert "error" not in cls.res, cls.res

    def test_event_ids_are_base32hex_and_stable(self):
        for i in self.res["ids"]:
            self.assertRegex(i, r"^[0-9a-v]{5,1024}$")
        self.assertEqual(len(set(self.res["ids"])), 5)
        self.assertEqual(self.res["ids"][0], self.res["ids2"][0])

    def test_a_day_without_a_time_is_an_all_day_event_that_repeats_yearly_with_its_alerts(self):
        e = self.res["allday"]
        self.assertEqual((e["start"], e["end"]), ({"date": "2027-05-03"}, {"date": "2027-05-04"}))
        self.assertEqual(e["recurrence"], ["RRULE:FREQ=YEARLY"])
        self.assertEqual(e["transparency"], "transparent")
        self.assertEqual(e["reminders"]["useDefault"], False)
        # the evening before (18:00) = 360 minutes; the days before at 9:00: 7 days = 7*1440-540, 14 days = 14*1440-540
        self.assertEqual([o["minutes"] for o in e["reminders"]["overrides"]], [360, 7 * 1440 - 540, 14 * 1440 - 540])
        self.assertTrue(all(o["method"] == "popup" for o in e["reminders"]["overrides"]))

    def test_the_alert_settings(self):
        # morning of the day: the API cannot say "after the start", and the start is midnight (never at night): the evening before at 18:00 stands in; the evening before; the week before at 9:00; none
        self.assertEqual(self.res["alarms"], [[360], [360], [9540], []])
        self.assertEqual(self.res["many"], [9540, 1 * 1440 - 540, 2 * 1440 - 540, 3 * 1440 - 540, 4 * 1440 - 540])      # at most five; 40 days is past the 28 days the API takes

    def test_a_day_with_a_time_is_a_one_hour_event_in_japan_time_and_may_end_the_next_day(self):
        t = self.res["timed"]
        self.assertEqual(t["start"], {"dateTime": "2027-05-03T23:30:00", "timeZone": "Asia/Tokyo"})
        self.assertEqual(t["end"], {"dateTime": "2027-05-04T00:30:00", "timeZone": "Asia/Tokyo"})
        self.assertEqual(t["transparency"], "opaque")
        self.assertEqual(t["reminders"]["overrides"], [{"method": "popup", "minutes": 23 * 60 + 30 - 540}])      # 9:00 of the day
        self.assertEqual(self.res["timedEarly"]["reminders"]["overrides"], [{"method": "popup", "minutes": 8 * 60 + 360}])    # 08:00 is too early for a morning alert: the evening before at 18:00 (14 hours before)

    def test_leap_day_and_the_hundred_day_marks(self):
        self.assertEqual(self.res["leap"], ["RRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=-1"])
        self.assertEqual(self.res["expand"], [["m-h", "2026-10-01", ""], ["m-h-100", "2027-01-09", "FREQ=DAILY;INTERVAL=100;COUNT=60"]])

    def test_the_first_press_makes_the_calendar_and_adds_every_day(self):
        f = self.res["first"]
        self.assertEqual(f["log"][0], "POST /calendars")
        self.assertEqual(sorted(f["log"][1:]), sorted(["POST /calendars/cal123%40group.calendar.google.com/events"] * 3))     # A, B and B's 100-day marks
        self.assertEqual((f["added"], f["updated"], f["removed"]), (3, 0, 0))
        self.assertEqual(f["state"], {"cal": "cal123@group.calendar.google.com", "sent": ["m-a1", "m-b2", "m-b2-100"]})

    def test_the_second_press_updates_what_was_sent_adds_the_new_and_takes_away_what_is_gone(self):
        s = self.res["second"]
        self.assertEqual((s["added"], s["updated"], s["removed"]), (1, 1, 2))      # C is new, A is updated, B and B's 100-day marks are taken away
        self.assertEqual(s["sent"], ["m-a1", "m-c3"])
        self.assertEqual(len([l for l in s["log"] if l.startswith("DELETE ")]), 2)
        self.assertEqual(len([l for l in s["log"] if l.startswith("PUT ")]), 1)
        self.assertFalse(any(l == "POST /calendars" for l in s["log"]))            # the calendar is not made twice

    def test_an_id_that_is_taken_is_updated(self):
        t = self.res["taken"]
        self.assertEqual((t["added"], t["updated"]), (0, 1))
        self.assertEqual([l.split(" ")[0] for l in t["log"]], ["POST", "PUT"])

    def test_a_calendar_deleted_in_google_is_made_again(self):
        g = self.res["gone"]
        self.assertEqual(g["cal"], "new456@group.calendar.google.com")
        self.assertEqual((g["added"], g["updated"]), (1, 0))
        self.assertIn("POST /calendars", g["log"])

    def test_a_refusal_is_reported_with_its_status(self):
        self.assertEqual(self.res["refused"], 403)

    def test_unlinking_deletes_only_the_calendar_of_its_own(self):
        self.assertEqual(self.res["unlink"]["log"], ["DELETE /calendars/cal123%40group.calendar.google.com"])
        self.assertEqual(self.res["unlink"]["state"], {"cal": "", "sent": []})
        self.assertEqual(self.res["unlinkNone"], {"state": {"cal": "", "sent": []}, "calls": 0})


class Wording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False)

    def test_only_the_narrow_permission_is_ever_asked_for_the_calendar(self):
        js = (ASSETS / "gcal.js").read_text(encoding="utf-8") + (ASSETS / "app.js").read_text(encoding="utf-8")
        scopes = set(re.findall(r"https://www\.googleapis\.com/auth/[a-z.]+", js))
        self.assertEqual(scopes, {"https://www.googleapis.com/auth/calendar.app.created", "https://www.googleapis.com/auth/drive.appdata"})

    def test_the_my_page_has_the_box_and_the_privacy_page_says_what_is_sent(self):
        my = self.pages["my/index.html"]
        self.assertIn('id="gcal-box"', my)
        self.assertIn('id="gcal-send"', my)
        self.assertIn('id="gcal-unlink"', my)
        text = re.sub(r"<[^>]+>", "", self.pages["privacy/index.html"])
        for must in ("Google カレンダーに送る", "メイン以外の Google カレンダーの作成", "いつもの予定を読み取る許可は求めません", "当サイトのサーバーには、予定の内容を送りません", "読み戻しません"):
            self.assertIn(must, text, must)

    def test_the_script_is_in_the_bundle_before_the_app(self):
        self.assertLess(build.BUNDLE.index("gcal"), build.BUNDLE.index("app"))
        self.assertGreater(build.BUNDLE.index("gcal"), build.BUNDLE.index("ics"))

    def test_the_settings_keep_only_known_shapes(self):
        js = (ASSETS / "app.js").read_text(encoding="utf-8")
        self.assertIn("s.prefs.gcal", js)
        self.assertIn("[A-Za-z0-9._@-]{5,200}", js)


if __name__ == "__main__":
    unittest.main()
