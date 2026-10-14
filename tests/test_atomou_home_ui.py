"""atomou: the owner's UI round of 2026-10-14, in a real Chrome (375px, today = 2026-10-14).
The home page has a switch (ON / OFF) for each part on the page itself, and the whole frame of a part is dragged (a mouse after 8px, a finger after a press and hold; the keyboard with Alt + arrows);
there are no arrow buttons and no "customize" button.  A past day's card says (過去).  Every page but the home has a bar with the way back and the way to the top page.
The add page: "3. 設定" (リピート, 通知するタイミング with four choices), no time field and no "やること" box, no "記録すると、このように表示されます。", the preview says 毎年の予定 / 毎月の予定 / 毎週の予定,
the line under the date shows the days too.  A seasonal skin can be put back on the same bar and by a button on the skin page."""
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
TODAY = date(2026, 10, 14)

HARNESS = r"""<!doctype html><meta charset="utf-8"><title>home ui</title><body><pre id="out">{}</pre><div id="host"></div><script>
window.onerror = function (m, s, l) { document.getElementById('out').textContent = JSON.stringify({ error: m + ' @' + l }); };
window.addEventListener('unhandledrejection', function (e) { document.getElementById('out').textContent = JSON.stringify({ error: String((e.reason && e.reason.stack) || e.reason) }); });
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function seed(fn) {
  var st = { v: 1, updated: '2026-10-14T00:00:00.000Z', entries: [], deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', setup: true, intro: true, tour: { home: true, calendar: true, plan: true, add: true, search: true } } };
  if (fn) fn(st);
  localStorage.setItem('atomou.v1', JSON.stringify(st));
}
function prefs() { return JSON.parse(localStorage.getItem('atomou.v1')).prefs; }
async function open(path, w) {
  var f = document.createElement('iframe'); f.style.cssText = 'width:' + (w || 375) + 'px;height:812px;border:0'; document.getElementById('host').appendChild(f);
  var hp = path.split('#'); await new Promise(function (res) { f.onload = res; f.src = hp[0] + (hp[0].indexOf('?') < 0 ? '?' : '&') + 'today=2026-10-14' + (hp[1] ? '#' + hp[1] : ''); });
  await wait(900); return f;
}
function pe(f, type, el, x, y, kind) {
  var W = f.contentWindow;
  el.dispatchEvent(new W.PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: kind || 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1, clientX: x, clientY: y, isPrimary: true }));
}
function center(el) { var r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }
function order(d) { return [].map.call(d.querySelectorAll('#parts > li'), function (l) { return l.getAttribute('data-k'); }); }
function blocks(d) { return [].map.call(d.querySelectorAll('#blocks > [data-block]'), function (b) { return b.getAttribute('data-block'); }); }
function tray(f) { var w = f.contentWindow, u = w.document.getElementById('parts'); w.scrollTo({ top: u.getBoundingClientRect().top + w.pageYOffset - 20, behavior: 'instant' }); }   // the list is brought into the frame's own viewport, where a pointer can be put
async function dragFrom(f, fromK, toK, kind, byName) {
  tray(f); await wait(60);
  var d = f.contentDocument, a = d.querySelector('#parts li[data-k="' + fromK + '"]' + (byName ? ' .part-n' : '')), b = d.querySelector('#parts li[data-k="' + toK + '"]');
  var p = center(a), q = center(b);
  pe(f, 'pointerdown', a, p[0], p[1], kind);
  if (kind === 'touch') await wait(450);
  pe(f, 'pointermove', a, p[0] + 12, p[1] + 12, kind);
  var over = d.elementFromPoint(q[0], q[1]);
  if (!over) { window.dbg = (window.dbg || []).concat([[fromK, toK, p, q, f.contentWindow.innerHeight, f.contentWindow.innerWidth]]); over = b; }
  pe(f, 'pointermove', over, q[0], q[1], kind);
  pe(f, 'pointerup', over, q[0], q[1], kind);
  await wait(120);
}
(async function () {
  var out = {}, f, d, i;
  // 1. a new visitor: the tray is open, ten switches, the arrows are gone
  localStorage.removeItem('atomou.v1'); localStorage.removeItem('atomou.partsfold'); seed(function (st) { st.prefs.setup = true; });
  f = await open('/'); d = f.contentDocument;
  out.fresh = { open: d.getElementById('home-parts').open, n: d.querySelectorAll('#parts li').length, sw: d.querySelectorAll('#parts [role="switch"]').length, arrows: d.querySelectorAll('[data-p="up"],[data-p="down"]').length, customBtn: !!d.getElementById('custom-open'),
    order: order(d), blocks: blocks(d), checked: [].map.call(d.querySelectorAll('#parts [role="switch"]'), function (b) { return b.getAttribute('aria-checked'); }).join('') };
  // 2. a tap on the frame switches the part off and on again, on the page
  var li = d.querySelector('#parts li[data-k="daily"]');
  li.click(); await wait(80);
  out.off = { hidden: prefs().blocks.hidden, shown: d.querySelector('[data-block="daily"]').offsetParent !== null, state: d.querySelector('#parts li[data-k="daily"] [role="switch"]').getAttribute('aria-checked'), text: d.querySelector('#parts li[data-k="daily"] .tg-t').textContent };
  d.querySelector('#parts li[data-k="daily"]').click(); await wait(80);
  out.on = { hidden: prefs().blocks.hidden, shown: d.querySelector('[data-block="daily"]').offsetParent !== null, text: d.querySelector('#parts li[data-k="daily"] .tg-t').textContent };
  // 3. a mouse takes the frame by its name (not by a handle) and moves it
  await dragFrom(f, 'cats', 'soon', 'mouse', true);
  out.dragMouse = { ui: order(d), blocks: blocks(d), saved: prefs().blocks.order, hidden: prefs().blocks.hidden };
  // 4. a finger: press and hold, then move; a finger that moves at once is a scroll and moves nothing
  await dragFrom(f, 'live', 'region', 'touch', false);
  out.dragTouch = { ui: order(d), saved: prefs().blocks.order };
  var before = order(d).join(','); tray(f); await wait(60);
  var a = d.querySelector('#parts li[data-k="todo"]'), b = d.querySelector('#parts li[data-k="usecases"]'), p = center(a), q = center(b);
  pe(f, 'pointerdown', a, p[0], p[1], 'touch'); pe(f, 'pointermove', a, p[0] + 30, p[1] + 30, 'touch'); await wait(450); pe(f, 'pointermove', b, q[0], q[1], 'touch'); pe(f, 'pointerup', b, q[0], q[1], 'touch'); await wait(100);
  out.scroll = { same: order(d).join(',') === before };
  // 5. the keyboard: Alt + arrow moves the focused frame
  var sw = d.querySelector('#parts li[data-k="usecases"] [role="switch"]'); sw.focus();
  sw.dispatchEvent(new f.contentWindow.KeyboardEvent('keydown', { key: 'ArrowLeft', altKey: true, bubbles: true, cancelable: true })); await wait(80);
  var ord = order(d); out.keyboard = { idx: ord.indexOf('usecases'), len: ord.length, focus: d.activeElement && d.activeElement.closest('li') && d.activeElement.closest('li').getAttribute('data-k') };
  // 6. back to the first order
  d.getElementById('parts-reset').click(); await wait(100);
  out.reset = { saved: prefs().blocks, ui: order(d) };
  f.remove();
  // 7. a visitor with days of their own: the tray is folded, and what they choose is kept
  seed(function (st) { st.entries.push({ id: 'p1', title: '昔の日', date: '2000-10-14', precision: 'day', kind: 'memo', quiet: false, yearly: false, every100: false, alarm: '', time: '' }); });
  localStorage.removeItem('atomou.partsfold');
  f = await open('/'); d = f.contentDocument;
  out.entries = { open: d.getElementById('home-parts').open, rel: (d.querySelector('#mine-grid .card .rel') || {}).textContent, word: (d.querySelector('#mine-grid .card .word') || {}).textContent };
  d.getElementById('home-parts').open = true; await wait(100);
  out.kept = localStorage.getItem('atomou.partsfold');
  f.remove();
  // 8. the bar of where you are, on a page that is not the home
  f = await open('/search/'); d = f.contentDocument;
  var wb = d.querySelector('nav.where');
  out.where = { has: !!wb, top: wb && wb.querySelector('[data-where="top"]') ? wb.querySelector('[data-where="top"]').getAttribute('href') : '', text: wb ? wb.textContent : '', first: d.querySelector('main').firstElementChild === wb };
  f.remove();
  f = await open('/'); d = f.contentDocument; out.homeHasNoBar = !d.querySelector('nav.where'); f.remove();
  // 9. the add page
  seed(null);
  f = await open('/add/?kind=event&date=2026-10-20'); d = f.contentDocument;
  var txt = d.getElementById('wizard').innerText;
  out.add = { s3: !!d.querySelector('#s3 h2') && d.querySelector('#s3 h2').textContent, s4: d.querySelector('#s4 h2').textContent, time: !!d.getElementById('f-time'), task: !!d.getElementById('f-task') || !!d.getElementById('f-before'),
    alarm: [].map.call(d.querySelectorAll('#f-alarm option'), function (o) { return o.textContent; }), alarmValue: d.getElementById('f-alarm').value, label: d.querySelector('label[for="f-alarm"]').textContent, rep: d.getElementById('rep-lab').textContent,
    once: txt.indexOf('1回だけの日です') >= 0, preview: txt.indexOf('このように表示されます') >= 0, previewName: (d.querySelector('#live .lv-name') || {}).textContent };
  function rep(v) { d.querySelector('[data-rep="' + v + '"]').click(); return (d.querySelector('#live .lv-name') || {}).textContent; }
  out.add.names = [rep('year'), rep('month'), rep('week'), rep('')];
  d.querySelector('[data-rep="year"]').click();
  out.add.liveSub = (d.querySelector('#live .muted') || {}).textContent;
  var inp = d.getElementById('f-day'); inp.value = '2000-10-14'; inp.dispatchEvent(new f.contentWindow.Event('input', { bubbles: true })); await wait(80);
  out.add.dateLine = d.getElementById('date-line').textContent;
  var ti = d.getElementById('f-title'); ti.value = '友だちの会'; ti.dispatchEvent(new f.contentWindow.Event('input', { bubbles: true })); d.querySelector('[data-rep="week"]').click(); await wait(50);
  out.add.named = (d.querySelector('#live .lv-name') || {}).textContent;
  d.getElementById('f-save').click(); await wait(300);
  var e0 = JSON.parse(localStorage.getItem('atomou.v1')).entries[0] || {};
  out.add.saved = { alarm: e0.alarm, time: e0.time, repeat: e0.repeat, title: e0.title };
  f.remove();
  // 10. the settings page: the wipe sits next to the transfer
  seed(null); f = await open('/my/'); d = f.contentDocument;
  var wipe = d.getElementById('wipe-h').nextElementSibling;
  out.my = { wipeText: wipe.innerText, backup2: !!wipe.querySelector('#backup2'), link: !!wipe.querySelector('a[href="#move"]'), alarmOpts: [].map.call(d.querySelectorAll('#p-alarm option'), function (o) { return o.textContent; }), editLink: !!d.querySelector('a[href="/?edit=1"]') };
  f.remove();
  // 11. a seasonal skin: the way back is on the bar and on a button
  seed(function (st) { st.prefs.skin = 'halloween'; });
  f = await open('/skins/'); d = f.contentDocument;
  out.skin = { on: d.documentElement.getAttribute('data-skin'), bar: d.getElementById('season').textContent, resetBtn: !!d.getElementById('skin-reset') };
  d.querySelector('[data-season-reset]').click(); await wait(120);
  out.skin.after = { attr: d.documentElement.getAttribute('data-skin'), saved: prefs().skin };
  seed(function (st) { st.prefs.skin = 'halloween'; });
  f.remove(); f = await open('/skins/'); d = f.contentDocument; d.getElementById('skin-reset').click(); await wait(120);
  out.skin.after2 = { attr: d.documentElement.getAttribute('data-skin'), saved: prefs().skin };
  f.remove();
  out.dbg = window.dbg || [];
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


class HomeUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=TODAY), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__ui.html").write_text(HARNESS, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=240000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__ui.html"], capture_output=True, timeout=600)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.res = json.loads(html.unescape(m.group(1)))
        assert "error" not in cls.res, cls.res["error"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_the_home_has_ten_switches_and_no_arrows_or_customize_button(self):
        f = self.res["fresh"]
        self.assertTrue(f["open"])                                      # a new visitor sees the switches at once
        self.assertEqual((f["n"], f["sw"], f["arrows"]), (10, 10, 0))
        self.assertFalse(f["customBtn"])
        self.assertEqual(f["checked"], "true" * 10)
        self.assertEqual(f["order"], f["blocks"])                       # the list is in the order of the page

    def test_a_tap_on_the_frame_switches_the_part_off_and_on(self):
        self.assertEqual(self.res["off"]["hidden"], ["daily"])
        self.assertFalse(self.res["off"]["shown"])
        self.assertEqual((self.res["off"]["state"], self.res["off"]["text"]), ("false", "OFF"))
        self.assertEqual(self.res["on"]["hidden"], [])
        self.assertTrue(self.res["on"]["shown"])
        self.assertEqual(self.res["on"]["text"], "ON")

    def test_the_whole_frame_is_dragged_by_a_mouse_and_by_a_finger_after_a_press_and_hold(self):
        m = self.res["dragMouse"]
        self.assertEqual(m["ui"], m["blocks"])                          # the page follows the list
        self.assertEqual(m["saved"], m["ui"])
        self.assertEqual(m["hidden"], [])                               # a drag is not a tap: nothing was switched
        self.assertGreater(m["ui"].index("cats"), m["ui"].index("daily"))   # cats went down, past the ones between it and soon
        self.assertEqual(self.res["dragTouch"]["saved"], self.res["dragTouch"]["ui"])
        self.assertTrue(self.res["scroll"]["same"])                     # a finger that moves before the press-and-hold scrolls: nothing is moved

    def test_the_keyboard_moves_a_frame_and_the_reset_puts_the_order_back(self):
        k = self.res["keyboard"]
        self.assertEqual(k["idx"], k["len"] - 2)                        # usecases was last: one place up
        self.assertEqual(k["focus"], "usecases")                        # the focus stays on it
        self.assertEqual(self.res["reset"]["saved"], {"order": [], "hidden": []})

    def test_the_tray_is_folded_for_someone_with_days_of_their_own_and_the_choice_is_kept(self):
        e = self.res["entries"]
        self.assertFalse(e["open"])                                     # their cards come first on the screen
        self.assertEqual(self.res["kept"], "0")
        self.assertEqual((e["rel"], e["word"]), ("(過去)", "もう"))        # a past day's card says so

    def test_every_page_but_the_home_has_the_bar_of_where_you_are(self):
        w = self.res["where"]
        self.assertTrue(w["has"] and w["first"])
        self.assertEqual(w["top"], "/")
        self.assertIn("トップページ", w["text"])
        self.assertTrue(self.res["homeHasNoBar"])

    def test_the_add_page_has_the_new_words_and_no_time_or_task_field(self):
        a = self.res["add"]
        self.assertEqual(a["s3"], "3. 設定")
        self.assertEqual(a["s4"], "4. メモ(任意)")
        self.assertFalse(a["time"])
        self.assertFalse(a["task"])
        self.assertEqual(a["label"], "通知するタイミング")
        self.assertEqual(a["alarm"], ["当日の午前中(8時〜12時)", "前日", "一週間前", "なし"])
        self.assertEqual(a["alarmValue"], "morning")
        self.assertEqual(a["rep"], "リピート")
        self.assertFalse(a["once"])
        self.assertFalse(a["preview"])
        self.assertEqual(a["previewName"], "予定")
        self.assertEqual(a["names"], ["毎年の予定", "毎月の予定", "毎週の予定", "予定"])
        self.assertIn("合計", a["dateLine"])                             # the days are written after the years ("もう26年 (合計 9,xxx日)")
        self.assertIn("過去", a["dateLine"])
        self.assertEqual(a["named"], "友だちの会")                         # a name that was typed is shown as it is
        self.assertEqual(a["saved"], {"alarm": "morning", "time": "", "repeat": "week", "title": "友だちの会"})

    def test_the_wipe_has_the_backup_beside_it_and_the_alarm_words_are_the_new_ones(self):
        m = self.res["my"]
        self.assertTrue(m["backup2"] and m["link"])
        self.assertIn("消す前に、ファイルに書き出して", m["wipeText"])
        self.assertEqual(m["alarmOpts"], ["当日の午前中(8時〜12時)", "前日", "一週間前", "なし"])
        self.assertFalse(m["editLink"])                                  # the old link to the panel is gone

    def test_a_seasonal_skin_can_be_put_back_on_the_bar_and_by_a_button(self):
        s = self.res["skin"]
        self.assertEqual(s["on"], "halloween")
        self.assertIn("ベーシックに戻す", s["bar"])
        self.assertTrue(s["resetBtn"])
        self.assertEqual(s["after"], {"attr": None, "saved": "basic"})
        self.assertEqual(s["after2"], {"attr": None, "saved": "basic"})

    def test_the_region_boxes_are_not_filled_by_the_browser(self):
        pages = build.build_pages(CFG, release=True, today=TODAY)
        self.assertIn('id="reg-select" autocomplete="off"', pages["interests/index.html"])
        self.assertIn('id="setup-reg" autocomplete="off"', (ROOT / "sites/atomou/assets/setup.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
