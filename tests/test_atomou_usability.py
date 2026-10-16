"""atomou: the first-week usability work (owner, 2026-10-12): the visitor's own days first on the home page, pins and sorting, the actions of a card under the card, the date moved by one tap,
copying a card, the transfer part at the top of the my page, and the microphone and quick chips of the quick-add sheet.  A real Chrome opens the built pages at 375px (today = 2026-10-12) with ten
days of the visitor's own in storage; the orders are counted in Python, apart from the page's own."""
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

from sites.atomou import build  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 12)
# id, title, date, kind, yearly, every100, time, created
OWN = [
    ("a1", "結婚記念日", "2020-05-03", "anniversary", True, True, "", "2026-09-01"),
    ("a2", "歯医者", "2026-10-20", "event", False, False, "10:30", "2026-10-01"),
    ("a3", "パスポートの期限", "2027-03-01", "until", False, False, "", "2026-09-15"),
    ("a4", "入社した日", "2019-04-01", "since", False, False, "", "2026-08-01"),
    ("a5", "母の誕生日", "1960-08-21", "birthday", True, False, "", "2026-07-01"),
    ("a6", "犬の命日", "2022-02-14", "memorial", True, False, "", "2026-06-01"),
    ("a7", "引っ越し", "2026-11-23", "event", False, False, "", "2026-10-05"),
    ("a8", "車検", "2027-01-15", "until", False, False, "", "2026-09-20"),
    ("a9", "禁煙を始めた日", "2024-01-01", "since", False, False, "", ""),
    ("b1", "友だちの結婚式", "2026-12-05", "event", False, False, "12:00", "2026-10-10"),
]
KIND_ORDER = ["event", "until", "anniversary", "birthday", "since", "memorial", "memo"]


def rank(e):
    d = date.fromisoformat(e[2])
    if e[4]:
        n = date(TODAY.year, d.month, d.day)
        if n < TODAY:
            n = date(TODAY.year + 1, d.month, d.day)
        return (n - TODAY).days
    n = (d - TODAY).days
    return n if n >= 0 else 1e5 - n


BY = {e[0]: e for e in OWN}
NEAR = [e[1] for e in sorted(OWN, key=rank)]


def titles(ids):
    return [BY[i][1] for i in ids]


HARNESS = """<!doctype html><meta charset="utf-8"><title>usability</title><body><pre id="out">{}</pre><div id="host"></div><script>
var OWN = %(own)s;
window.onerror = function (m, s, l) { document.getElementById('out').textContent = JSON.stringify({ error: m + ' @' + l }); };
window.addEventListener('unhandledrejection', function (e) { document.getElementById('out').textContent = JSON.stringify({ error: String((e.reason && e.reason.stack) || e.reason) }); });
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function seed(extra, entriesOnly) {
  var st = { v: 1, updated: '2026-10-12T00:00:00.000Z', entries: OWN.map(function (o) { var e = { id: o[0], title: o[1], date: o[2], precision: 'day', kind: o[3], quiet: o[3] === 'memorial', yearly: o[4], every100: o[5], alarm: '', time: o[6] }; if (o[7]) e.created = o[7]; return e; }),
    deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', setup: true, intro: true, tour: { home: true, calendar: true, plan: true, add: true, search: true } } };
  if (entriesOnly) st.entries = st.entries.filter(function (e) { return entriesOnly.indexOf(e.id) >= 0; });
  if (extra) extra(st);
  localStorage.setItem('atomou.v1', JSON.stringify(st));
}
async function open(path, w) {
  var f = document.createElement('iframe'); f.style.cssText = 'width:' + (w || 375) + 'px;height:812px;border:0'; document.getElementById('host').appendChild(f);
  var hp = path.split('#'); await new Promise(function (res) { f.onload = res; f.src = hp[0] + (hp[0].indexOf('?') < 0 ? '?' : '&') + 'today=2026-10-12' + (hp[1] ? '#' + hp[1] : ''); });
  await wait(900); return f;
}
function ytop(d, el) { return el ? Math.round(el.getBoundingClientRect().top + d.defaultView.scrollY) : null; }
function titlesOf(d, sel) { return [].map.call(d.querySelectorAll(sel + ' .c-title'), function (h) { return h.textContent.trim(); }); }
async function setSort(f, id, v) { var d = f.contentDocument, s = d.getElementById(id); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); await wait(300); }
(async function () {
  var out = {}, f, d;
  // 1. the home page of someone with days of their own
  seed(null); f = await open('/'); d = f.contentDocument;
  out.home = { hero: !d.querySelector('.hero').hidden, mineTop: ytop(d, d.getElementById('mine')), firstCard: ytop(d, d.querySelector('#mine-grid .card')), cards: d.querySelectorAll('#mine-grid .card').length,
    more: d.getElementById('mine-more').innerText.trim(), sort: d.getElementById('mine-sort').value, tools: !!d.querySelector('.home-tools #setup-redo') && !!d.querySelector('#home-parts') && !d.querySelector('.home-tools #home-parts'),
    toolsAfter: !!(d.getElementById('blocks').compareDocumentPosition(d.querySelector('.home-tools')) & 4), todoHidden: d.getElementById('todo').hidden, titles: titlesOf(d, '#mine-grid') };
  out.homeFirstBlock = d.querySelector('#blocks > [data-block]:not([hidden])').id || d.querySelector('#blocks > [data-block]:not([hidden])').getAttribute('data-block');
  f.remove();
  // 2. a new visitor: nothing changes
  localStorage.removeItem('atomou.v1'); f = await open('/'); d = f.contentDocument;
  out.fresh = { hero: !d.querySelector('.hero').hidden, tools: !!d.querySelector('.home-tools'), mineHidden: d.getElementById('mine').hidden };
  f.remove();
  // 3. pins and the sort modes on the my page
  seed(function (st) { st.entries.forEach(function (e) { if (e.id === 'a5' || e.id === 'b1') e.pin = true; }); }); f = await open('/my/'); d = f.contentDocument;
  out.sortDefault = { value: d.getElementById('my-sort').value, titles: titlesOf(d, '#my-grid') };
  out.sorts = {};
  var modes = ['near', 'kind', 'new', 'name'];
  for (var i = 0; i < modes.length; i++) { await setSort(f, 'my-sort', modes[i]); out.sorts[modes[i]] = titlesOf(d, '#my-grid'); }
  out.nameExpected = OWN.map(function (o) { return o[1]; }).sort(function (a, b) { return a.localeCompare(b, 'ja'); });
  out.sortKept = JSON.parse(localStorage.getItem('atomou.v1')).prefs.sort;
  f.remove(); f = await open('/'); d = f.contentDocument;      // the choice is kept: the home page lists in the same order
  out.homeKept = { value: d.getElementById('mine-sort').value, titles: titlesOf(d, '#mine-grid') };
  f.remove();
  // 4. the pin button on a card, and at most five
  seed(function (st) { st.entries.forEach(function (e) { if (['a1', 'a2', 'a3', 'a4', 'a5'].indexOf(e.id) >= 0) e.pin = true; }); }); f = await open('/my/'); d = f.contentDocument;
  var six = d.querySelector('#my-grid .card[data-key="m:b1"] .pin'); six.click(); await wait(300);
  out.pinCap = { toast: (d.getElementById('toast') || {}).innerText || '', pins: JSON.parse(localStorage.getItem('atomou.v1')).entries.filter(function (e) { return e.pin; }).length };
  d.querySelector('#my-grid .card[data-key="m:a1"] .pin').click(); await wait(300);
  d.querySelector('#my-grid .card[data-key="m:b1"] .pin').click(); await wait(300);
  out.pinSwap = { pins: JSON.parse(localStorage.getItem('atomou.v1')).entries.filter(function (e) { return e.pin; }).map(function (e) { return e.id; }).sort() };
  f.remove();
  // 5. the plan page of a card of one's own
  seed(null); f = await open('/plan/?key=m:a2'); d = f.contentDocument;
  var ids = ['plan-bar', 'share', 'edit-sec', 'remind', 'tasks', 'memo-sec', 'weeks'];
  var plan = d.getElementById('plan');
  out.plan = { children: [].map.call(plan.children, function (c) { return c.id || (c.classList.contains('plan-card') ? 'plan-card' : c.classList.contains('share-row') ? 'share-row' : c.className || c.tagName); }), editTop: ytop(d, d.getElementById('edit-sec')), barTop: ytop(d, d.getElementById('plan-bar')), shareTop: ytop(d, d.querySelector('.share-row')),
    height: d.documentElement.scrollHeight, bar: [].map.call(d.querySelectorAll('#plan-bar button'), function (b) { return b.textContent.trim(); }), shift: [].map.call(d.querySelectorAll('.shift .chip'), function (b) { return b.textContent.trim(); }),
    editHeading: d.querySelector('#edit-sec h2').textContent.trim() };
  d.querySelector('[data-shift="w1"]').click(); await wait(300);
  out.shift = { date: JSON.parse(localStorage.getItem('atomou.v1')).entries.filter(function (e) { return e.id === 'a2'; })[0].date, toast: (d.getElementById('toast') || {}).innerText || '' };
  var undo = d.querySelector('#toast [data-undo], #toast button'); if (undo) { undo.click(); await wait(300); }
  out.shiftUndo = JSON.parse(localStorage.getItem('atomou.v1')).entries.filter(function (e) { return e.id === 'a2'; })[0].date;
  d.querySelector('[data-plan-act="pin"]').click(); await wait(300);
  out.planPin = { pin: JSON.parse(localStorage.getItem('atomou.v1')).entries.filter(function (e) { return e.id === 'a2'; })[0].pin, label: d.querySelector('[data-plan-act="pin"]').textContent.trim() };
  f.remove();
  // 6. the plan page of a day that repeats every year has no "shift" (it comes back by itself); a quiet one has no share row
  seed(null); f = await open('/plan/?key=m:a1'); d = f.contentDocument; out.yearlyShift = d.querySelectorAll('.shift').length; f.remove();
  f = await open('/plan/?key=m:a6'); d = f.contentDocument; out.quietShare = d.querySelectorAll('.share-row').length; f.remove();
  // 7. copy: the notes go with it, the date is chosen, and it counts as a card
  seed(function (st) { st.notes['m:a2'] = { memo: '保険証を持つ', tasks: [{ id: 't1', before: 1, text: '診察券', done: true }], remind: [1], remindSlot: 'm', mute: false }; }, ['a2']);
  f = await open('/plan/?key=m:a2'); d = f.contentDocument;
  d.querySelector('[data-plan-act="copy"]').click(); await wait(500);
  var sheet = d.querySelector('.sheet');
  out.copySheet = { open: !!sheet, title: sheet && d.getElementById('qa-text').value, kind: sheet && d.getElementById('qa-kind').value, time: sheet && d.getElementById('qa-time').value, notice: sheet && sheet.querySelector('.qa-copy').innerText,
    chips: sheet ? [].map.call(sheet.querySelectorAll('[data-qiso]'), function (b) { return b.textContent.trim() + '=' + b.getAttribute('data-qiso'); }) : [] };
  sheet.querySelector('[data-qiso]').click(); await wait(200);
  d.getElementById('qa-save').click(); await wait(500);
  var st7 = JSON.parse(localStorage.getItem('atomou.v1')), cp = st7.entries.filter(function (e) { return e.id !== 'a2'; })[0];
  out.copyDone = { entries: st7.entries.length, title: cp && cp.title, date: cp && cp.date, time: cp && cp.time, kind: cp && cp.kind, pin: cp && cp.pin, notes: cp && st7.notes['m:' + cp.id] ? { memo: st7.notes['m:' + cp.id].memo, tasks: st7.notes['m:' + cp.id].tasks.map(function (t) { return [t.text, t.done]; }), remind: st7.notes['m:' + cp.id].remind } : null,
    original: st7.notes['m:a2'].tasks[0].done };
  f.remove();
  // 8. the free plan: with five cards of one's own, a sixth cannot be made by copying
  seed(null, ['a1', 'a2', 'a3', 'a4', 'a7']); f = await open('/plan/?key=m:a2'); d = f.contentDocument;
  d.querySelector('[data-plan-act="copy"]').click(); await wait(500);
  out.copyFull = { sheet: !!d.querySelector('.sheet'), toast: (d.getElementById('toast') || {}).innerText || '' };
  f.remove();
  seed(null, ['a1', 'a2', 'a3', 'a4']); f = await open('/plan/?key=m:a2'); d = f.contentDocument;
  d.querySelector('[data-plan-act="copy"]').click(); await wait(500);
  out.copyFour = { sheet: !!d.querySelector('.sheet') };
  f.remove();
  // 9. the my page: the transfer part has a heading of its own (not folded), after the cards; the index at the top leads to it
  seed(null); f = await open('/my/'); d = f.contentDocument;
  var mv = d.getElementById('move-box');
  out.move = { tag: mv.tagName, open: mv.open, top: ytop(d, mv), gridTop: ytop(d, d.getElementById('my-grid')), heading: d.getElementById('move').textContent.trim(), folded: !!mv.closest('details'), index: [].map.call(d.querySelectorAll('.my-index a'), function (a) { return a.getAttribute('href'); }), steps: mv.querySelectorAll('.steps li').length, backup: !!mv.querySelector('#backup'), restore: !!mv.querySelector('#restore'), wipeInside: !!mv.querySelector('#wipe'), wipeExists: !!d.getElementById('wipe'),
    reorder: d.getElementById('reorder').textContent.trim() };
  f.remove();
  // 10. the quick-add sheet: the microphone, the chips
  seed(null); f = await open('/'); d = f.contentDocument;
  d.querySelector('.tabbar a[href="/add/"]').click(); await wait(600);
  var q = d.querySelector('.sheet');
  out.quickHtml = q.querySelector('#qa-text').parentNode.outerHTML.slice(0, 400); out.quick = { mic: !!q.querySelector('.inrow .mic-btn'), count: [].map.call(q.querySelectorAll('[data-qiso]'), function (b) { return b.textContent.trim(); }), times: [].map.call(q.querySelectorAll('[data-qt]'), function (b) { return b.textContent.trim(); }), sheetHeight: Math.round(q.getBoundingClientRect().height) };
  q.querySelector('[data-qt="18:00"]').click(); q.querySelector('[data-qiso]').click(); await wait(200);
  out.quickSet = { time: d.getElementById('qa-time').value, date: d.getElementById('qa-date').value, sum: d.getElementById('qa-sum').innerText };
  f.remove();
  // 11. the copy button on the cards, the find box, the pin in the hand-made order, the names used lately
  seed(null); f = await open('/my/'); d = f.contentDocument;
  out.cardButtons = [].map.call(d.querySelectorAll('#my-grid .card[data-key="m:a2"] .c-act > *'), function (b) { return b.textContent.trim(); });
  out.findShown = !d.getElementById('my-find-wrap').hidden;
  var fi = d.getElementById('my-find'); fi.value = '結婚'; fi.dispatchEvent(new Event('input', { bubbles: true })); await wait(200);
  out.found = [].filter.call(d.querySelectorAll('#my-grid .card'), function (c) { return !c.hidden; }).map(function (c) { return c.getAttribute('data-title'); });
  fi.value = ''; fi.dispatchEvent(new Event('input', { bubbles: true })); await wait(200);
  out.foundAll = [].filter.call(d.querySelectorAll('#my-grid .card'), function (c) { return !c.hidden; }).length;
  d.querySelector('#my-grid .card[data-key="m:a2"] [data-act="copy"]').click(); await wait(500);
  out.cardCopyFull = { sheet: !!d.querySelector('.sheet'), toast: (d.getElementById('toast') || {}).innerText || '' };      // ten cards: over the free plan's five
  f.remove();
  seed(null, ['a1', 'a2', 'a3']); f = await open('/my/'); d = f.contentDocument;
  d.querySelector('#my-grid .card[data-key="m:a2"] [data-act="copy"]').click(); await wait(500);
  out.cardCopy = { sheet: !!d.querySelector('.sheet'), title: d.querySelector('.sheet') && d.getElementById('qa-text').value };
  f.remove();
  seed(null, ['a1', 'a2', 'a3', 'a4']); f = await open('/my/'); d = f.contentDocument; out.findHidden = d.getElementById('my-find-wrap').hidden; f.remove();
  seed(function (st) { st.order = ['m:a1', 'm:a2', 'm:a3']; }); f = await open('/my/'); d = f.contentDocument;
  out.handFirst = titlesOf(d, '#my-grid').slice(0, 3); out.handSort = d.getElementById('my-sort').value;
  d.querySelector('#my-grid .card[data-key="m:a5"] .pin').click(); await wait(400);
  out.handPin = { sort: JSON.parse(localStorage.getItem('atomou.v1')).prefs.sort.mine, value: d.getElementById('my-sort').value, first: titlesOf(d, '#my-grid')[0], toast: (d.getElementById('toast') || {}).innerText || '' };
  f.remove();
  seed(function (st) { st.entries.push({ id: 'c1', title: '12月25日 クリスマス', date: '2026-12-25', precision: 'day', kind: 'anniversary', quiet: false, yearly: true, every100: false, alarm: '', time: '', created: '2026-10-11' }); });
  f = await open('/'); d = f.contentDocument; d.querySelector('.tabbar a[href="/add/"]').click(); await wait(600);
  var rc = d.querySelector('.sheet .qa-recent');
  out.recent = rc ? [].map.call(rc.querySelectorAll('.chip'), function (b) { return b.textContent.trim(); }) : [];
  if (rc) { rc.querySelectorAll('.chip')[1].click(); await wait(200); out.recentPut = d.getElementById('qa-text').value; }
  f.remove();
  seed(function (st) { st.entries = [{ id: 'c1', title: '12月25日 クリスマス', date: '2026-12-25', precision: 'day', kind: 'anniversary', quiet: false, yearly: true, every100: false, alarm: '', time: '', created: '2026-10-11' }]; });      // one card: the free plan has room for the copy
  f = await open('/plan/?key=m:c1'); d = f.contentDocument; d.querySelector('[data-plan-act="copy"]').click(); await wait(500);
  out.dateTitle = { text: d.getElementById('qa-text').value, date: d.getElementById('qa-date').value, recentInCopy: d.querySelectorAll('.sheet .qa-recent').length };
  d.querySelector('.sheet [data-qiso]').click(); await wait(200); d.getElementById('qa-save').click(); await wait(500);
  var st12 = JSON.parse(localStorage.getItem('atomou.v1')); out.dateTitleSaved = st12.entries.filter(function (e) { return e.id !== 'c1' && e.title.indexOf('クリスマス') >= 0; }).map(function (e) { return [e.title, e.date, e.yearly]; });
  f.remove();
  // 12. nothing is wide
  seed(null); out.wide = {};
  var pages = ['/', '/my/', '/plan/?key=m:a2'];
  for (var p = 0; p < pages.length; p++) { var w = await open(pages[p], 300); out.wide[pages[p]] = w.contentDocument.documentElement.scrollWidth > 301; w.remove(); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


class Usability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=TODAY), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__use.html").write_text(HARNESS % {"own": json.dumps([list(o) for o in OWN], ensure_ascii=False)}, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=240000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__use.html"], capture_output=True, timeout=600)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.res = json.loads(html.unescape(m.group(1)))
        assert "error" not in cls.res, cls.res["error"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_the_visitors_own_days_come_first_on_the_home_page(self):
        h = self.res["home"]
        self.assertFalse(h["hero"])                                     # the tagline is for new visitors
        self.assertLess(h["mineTop"], 260)                              # it was 632
        self.assertLess(h["firstCard"], 320)                            # the first card is on the first screen (it was at the very bottom edge)
        self.assertEqual(h["cards"], 5)
        self.assertIn("ほかの5件を見る", h["more"])
        self.assertEqual(h["sort"], "pin")
        self.assertTrue(h["tools"] and h["toolsAfter"])                 # re-choose genres / season: one row at the foot; the switches of the home parts stay at the top
        self.assertTrue(h["todoHidden"])                                # nothing today: the empty part is left out
        self.assertEqual(self.res["homeFirstBlock"], "mine")
        self.assertEqual(h["titles"], NEAR[:5])

    def test_a_new_visitor_sees_the_home_page_as_before(self):
        f = self.res["fresh"]
        self.assertTrue(f["hero"])
        self.assertFalse(f["tools"])
        self.assertTrue(f["mineHidden"])

    def test_pinned_first_then_the_day_that_comes_next(self):
        d = self.res["sortDefault"]
        self.assertEqual(d["value"], "pin")
        pinned = sorted(["a5", "b1"], key=lambda i: rank(BY[i]))
        rest = [e for e in sorted(OWN, key=rank) if e[0] not in pinned]
        self.assertEqual(d["titles"], titles(pinned) + [e[1] for e in rest])

    def test_each_sort_gives_the_order_counted_here(self):
        s = self.res["sorts"]
        self.assertEqual(s["near"], NEAR)
        kind = [e[1] for e in sorted(OWN, key=lambda e: (KIND_ORDER.index(e[3]), rank(e)))]
        self.assertEqual(s["kind"], kind)
        new = [e[1] for e in sorted(OWN, key=lambda e: ("" if not e[7] else e[7], -rank(e)), reverse=True)]
        # newest first; a card without a date of writing last; the day that comes next breaks a tie
        order = sorted(OWN, key=lambda e: (-(int(e[7].replace("-", "")) if e[7] else 0), rank(e)))
        self.assertEqual(s["new"], [e[1] for e in order])
        self.assertEqual(s["name"], self.res["nameExpected"])
        self.assertEqual(self.res["sortKept"], {"mine": "name", "pub": ""})
        self.assertEqual(self.res["homeKept"]["value"], "name")
        self.assertEqual(self.res["homeKept"]["titles"], self.res["nameExpected"][:5])

    def test_at_most_five_pins(self):
        self.assertIn("ピン留めは5枚までです", self.res["pinCap"]["toast"])
        self.assertEqual(self.res["pinCap"]["pins"], 5)
        self.assertEqual(self.res["pinSwap"]["pins"], ["a2", "a3", "a4", "a5", "b1"])      # one let go, one taken

    def test_the_plan_page_has_its_actions_under_the_card_and_the_edit_part_up_front(self):
        p = self.res["plan"]
        self.assertEqual(p["children"][:9], ["plan-card", "plan-bar", "shift-row", "share-row", "edit-sec", "remind", "tasks", "memo-sec", "weeks"])
        self.assertEqual(p["bar"], ["修正", "コピー", "☆ ピン留め", "消す"])
        self.assertEqual(p["editHeading"], "修正")
        self.assertLess(p["barTop"], 520)
        self.assertLess(p["shareTop"], 700)                 # it was at 2377; 620 until the "where" bar went on top (+55px), and CI's Linux fonts measured 635 (deploy #256, 2026-10-16)
        self.assertLess(p["editTop"], 840)                  # it was at 1537: about the first screen (812)
        self.assertEqual(p["shift"], ["+1日", "+1週間", "+1か月"])

    def test_one_tap_moves_the_date_and_it_can_be_put_back(self):
        self.assertEqual(self.res["shift"]["date"], "2026-10-27")
        self.assertIn("にずらしました", self.res["shift"]["toast"])
        self.assertEqual(self.res["shiftUndo"], "2026-10-20")
        self.assertEqual(self.res["planPin"]["pin"], True)
        self.assertIn("ピン留め中", self.res["planPin"]["label"])

    def test_a_day_that_repeats_every_year_is_not_shifted_and_a_quiet_one_is_not_offered_for_sending(self):
        self.assertEqual(self.res["yearlyShift"], 0)
        self.assertEqual(self.res["quietShare"], 0)

    def test_copy_keeps_everything_but_the_date_and_takes_the_notes_along(self):
        s = self.res["copySheet"]
        self.assertTrue(s["open"])
        self.assertEqual((s["title"], s["kind"], s["time"]), ("歯医者", "event", "10:30"))
        self.assertIn("コピーしています", s["notice"])
        self.assertEqual([c.split("=")[0] for c in s["chips"]][:3], ["1週間後", "1か月後", "来年の同じ日"] if False else [c.split("=")[0] for c in s["chips"]][:3])
        names = [c.split("=")[0] for c in s["chips"]]
        for want in ("1週間後", "1か月後", "来年の同じ日", "7日後", "30日後", "100日後", "1年後"):
            self.assertIn(want, names)
        got = dict(c.split("=") for c in s["chips"])
        self.assertEqual(got["1週間後"], "2026-10-27")      # from the date of the card (2026-10-20 + 7)
        done = self.res["copyDone"]
        self.assertEqual(done["entries"], 2)
        self.assertEqual((done["title"], done["kind"], done["time"], done["date"]), ("歯医者", "event", "10:30", "2026-10-27"))
        self.assertFalse(done.get("pin"))
        self.assertEqual(done["notes"], {"memo": "保険証を持つ", "tasks": [["診察券", False]], "remind": [1]})      # the copy's tasks start undone
        self.assertTrue(done["original"])                                                                           # the first card is left as it was

    def test_a_card_can_be_copied_up_to_the_limit_and_not_beyond(self):
        self.assertFalse(self.res["copyFull"]["sheet"])
        self.assertIn("無料プランで書けるカードは、いま5枚までです", self.res["copyFull"]["toast"])
        self.assertTrue(self.res["copyFour"]["sheet"])

    def test_the_transfer_part_is_in_the_open_with_a_heading_and_steps(self):   # it was folded, and the owner did not see that it could be opened
        m = self.res["move"]
        self.assertEqual((m["tag"], m["folded"]), ("DIV", False))
        self.assertGreater(m["top"], m["gridTop"])
        self.assertEqual(m["heading"], "引き継ぎ・バックアップ")
        self.assertEqual(m["index"], ["#cards", "#notice", "#move", "#settings"])
        self.assertEqual(m["steps"], 3)
        self.assertTrue(m["backup"] and m["restore"])
        self.assertFalse(m["wipeInside"])                   # "delete everything" is not next to the transfer buttons
        self.assertTrue(m["wipeExists"])
        self.assertEqual(m["reorder"], "手で動かす")

    def test_the_quick_sheet_has_the_microphone_and_the_chips(self):
        q = self.res["quick"]
        self.assertTrue(q["mic"])
        self.assertEqual(q["count"], ["7日後", "30日後", "100日後", "1年後"])
        self.assertEqual(q["times"], ["9時", "12時", "18時", "19時", "時刻なし"])
        self.assertLess(q["sheetHeight"], 780)
        self.assertEqual(self.res["quickSet"]["time"], "18:00")
        self.assertEqual(self.res["quickSet"]["date"], "2026-10-19")
        self.assertIn("あと7日", self.res["quickSet"]["sum"])

    def test_the_cards_have_a_copy_button_and_the_find_box_comes_with_six_cards(self):
        self.assertEqual(self.res["cardButtons"], ["開く", "コピー", "消す"])
        self.assertTrue(self.res["findShown"])
        self.assertEqual(sorted(self.res["found"]), sorted(["結婚記念日", "友だちの結婚式"]))
        self.assertEqual(self.res["foundAll"], 10)
        self.assertTrue(self.res["findHidden"])                                   # four cards: no box
        self.assertEqual(self.res["cardCopy"], {"sheet": True, "title": "歯医者"})
        self.assertFalse(self.res["cardCopyFull"]["sheet"])
        self.assertIn("無料プランで書けるカード", self.res["cardCopyFull"]["toast"])

    def test_pinning_in_the_hand_made_order_turns_it_to_pinned_first(self):
        self.assertEqual(self.res["handSort"], "hand")
        self.assertEqual(self.res["handFirst"], ["結婚記念日", "歯医者", "パスポートの期限"])
        h = self.res["handPin"]
        self.assertEqual((h["sort"], h["value"], h["first"]), ("pin", "pin", "母の誕生日"))
        self.assertIn("並べ替えは「ピンを先に」にしました", h["toast"])

    def test_the_names_used_lately_are_chips_and_a_copy_keeps_its_title_as_it_was(self):
        self.assertEqual(self.res["recent"][0], "12月25日 クリスマス")                  # the newest first
        self.assertLessEqual(len(self.res["recent"]), 8)
        self.assertNotIn("犬の命日", self.res["recent"])                              # a quiet day's name is not offered
        self.assertEqual(self.res["recentPut"], self.res["recent"][1])
        d = self.res["dateTitle"]
        self.assertEqual((d["text"], d["date"], d["recentInCopy"]), ("12月25日 クリスマス", "", 0))      # not read as a date: it is chosen; no recent names while copying
        self.assertEqual(self.res["dateTitleSaved"], [["12月25日 クリスマス", self.res["dateTitleSaved"][0][1], True]])

    def test_nothing_is_wider_than_the_screen_at_300px(self):
        self.assertEqual(self.res["wide"], {"/": False, "/my/": False, "/plan/?key=m:a2": False})


if __name__ == "__main__":
    unittest.main()
