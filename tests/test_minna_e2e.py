"""Browser-level check of the card maker and the background switcher of みんなのイラスト (skipped without Chrome, and in CI)."""
import functools
import html as _html
import http.server
import json
import os
import re
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build
from tests.test_yorokobu_e2e import CHROME, run_chrome

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト", "contact_form_url": "https://example.com/f", "adsense_pub_id": None}

SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '1200px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(400); return f;
}
(async () => {
  try {
    let f = await load('/tool/card/?c=season-christmas'); let d = f.contentDocument, w = f.contentWindow;
    out.preselected = d.querySelector('[name="char"]').value;
    d.querySelector('[name="tpl"]').value = 'thanks'; d.querySelector('[name="to"]').value = 'ハナコ'; d.querySelector('[name="msg"]').value = 'いつもありがとう。ゆっくりしてね。';
    d.querySelector('[name="from"]').value = 'タロウ'; d.querySelector('[name="color"]').value = '#ffd6e0';
    d.querySelector('[name="color"]').dispatchEvent(new w.Event('change')); await wait(1500);
    const c = d.querySelector('canvas'), ctx = c.getContext('2d');
    const px = ctx.getImageData(5, 5, 1, 1).data; out.corner = [px[0], px[1], px[2]];                    // the chosen colour
    const mid = ctx.getImageData(540, 700, 1, 1).data; out.has_character = !(mid[0] === 255 && mid[1] === 214 && mid[2] === 224);
    out.size = [c.width, c.height];
    w.HTMLAnchorElement.prototype.click = function () {};                                                // the save button also starts a file download: not in a test (it hangs headless Chrome and fills the Downloads folder)
    d.querySelector('[data-save]').click(); await wait(1500);
    const img = d.querySelector('.card-img'); out.saved_visible = !img.hidden; out.saved_src = img.src.slice(0, 22);
    f = await load('/illust/season-christmas/'); d = f.contentDocument;
    const box = d.querySelector('#bgbox'); d.querySelector('.bgsw button[data-bg="#2b1b14"]').click();
    out.bg_dark = box.style.backgroundColor; out.solid = box.classList.contains('solid');
    d.querySelector('.bgsw button[data-bg=""]').click(); out.bg_reset = box.style.backgroundColor === '' && !box.classList.contains('solid');

    // the print makers: the holidays computed in the browser are the ones printables.py computes, and every kind of page is drawn
    f = await load('/tool/calendar/'); d = f.contentDocument; w = f.contentWindow; await wait(1500);
    out.hol = {}; for (let y = 2023; y <= 2040; y++) out.hol[y] = w.minnaMaker.holidays(y);
    d.querySelector('#mk-list button').click(); await wait(1500);
    const cc = d.getElementById('mk-canvas'), ink = (cv, y0, h) => { const x = cv.getContext('2d').getImageData(0, y0, cv.width, h).data; let n = 0; for (let i = 0; i < x.length; i += 4) if (x[i] < 120 && x[i + 1] < 120 && x[i + 2] < 120) n++; return n; };
    out.cal = { size: [cc.width, cc.height], msg: d.getElementById('mk-msg').textContent, header_ink: ink(cc, 800, 60), title_ink: ink(cc, 200, 160) };
    f = await load('/tool/nametag/'); d = f.contentDocument; w = f.contentWindow; await wait(1500);
    d.querySelector('#mk-list button').click(); await wait(1500);
    out.tag = {};
    for (const tpl of ['tag8', 'seat', 'cert']) {
      const sel = d.querySelector('[name="tpl"]'); sel.value = tpl; d.querySelector('[name="name"]').value = '山田 太郎'; sel.dispatchEvent(new w.Event('change')); await wait(500);
      const cv = d.getElementById('mk-canvas'); out.tag[tpl] = { ink: ink(cv, 0, cv.height), msg: d.getElementById('mk-msg').textContent, cert_fields_hidden: d.querySelector('[data-for="cert"]').hidden };
    }
    // the postcard maker: a greeting, a message and a sender are drawn, and it is a 100 x 148 mm page at 300 dpi
    f = await load('/tool/nenga/'); d = f.contentDocument; w = f.contentWindow; await wait(1500);
    d.querySelector('#mk-list button').click(); await wait(1500);
    d.querySelector('[name="from"]').value = '山田 太郎'; d.querySelector('[name="from"]').dispatchEvent(new w.Event('input')); await wait(500);
    const nc = d.getElementById('mk-canvas'), colored = (cv, y0, h) => { const x = cv.getContext('2d').getImageData(0, y0, cv.width, h).data; let n = 0; for (let i = 0; i < x.length; i += 4) if (x[i] < 235 || x[i + 1] < 235 || x[i + 2] < 235) n++; return n; };      // the greeting is in a colour, not black
    out.nenga = { size: [nc.width, nc.height], msg: d.getElementById('mk-msg').textContent, date: d.querySelector('[name="date"]').value, head_ink: colored(nc, 150, 130), body_ink: ink(nc, 420, 1000) };
    // phone width: the header links must stay readable (not squeezed into one-character-wide columns)
    {
      const f2 = document.createElement('iframe'); f2.style.width = '300px'; f2.style.height = '800px'; document.body.appendChild(f2);
      await new Promise(r => { f2.onload = r; f2.src = '/'; }); await wait(300);
      out.nav = [...f2.contentDocument.querySelectorAll('header.site nav a')].map(a => { const r = a.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; });
      out.scroll300 = f2.contentDocument.documentElement.scrollWidth;
    }
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally")
class MinnaBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        build.render_site(CFG, root, release=True, today=date(2026, 10, 7))
        (root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{SCENARIO}</script>', encoding="utf-8")
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        handler = functools.partial(Quiet, directory=str(root))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        cls.out = json.loads(_html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_card_maker_draws_and_saves(self):
        o = self.out
        self.assertNotIn("error", o)
        self.assertEqual(o["preselected"], "season-christmas")
        self.assertEqual(o["corner"], [255, 214, 224])
        self.assertTrue(o["has_character"])
        self.assertEqual(o["size"], [1080, 1350])
        self.assertTrue(o["saved_visible"])
        self.assertEqual(o["saved_src"], "data:image/png;base64,")

    def test_header_links_stay_readable_on_a_phone(self):
        self.assertTrue(self.out["nav"])
        for w, h in self.out["nav"]:
            self.assertGreaterEqual(w, 40)      # a two-character label such as 特集 is about 48 px; vertical text would be far narrower and taller
            self.assertLessEqual(h, 60)
        self.assertLessEqual(self.out["scroll300"], 301)

    def test_calendar_holidays_in_the_browser_match_the_python_ones(self):
        from sites.minna import printables
        for year, got in self.out["hol"].items():
            want = {d.isoformat(): n for d, n in printables.holidays(int(year)).items()}
            self.assertEqual(got, want, year)

    def test_calendar_and_name_pages_are_drawn(self):
        cal = self.out["cal"]
        self.assertEqual(cal["size"], [1240, 1754])
        self.assertIn("選んだイラスト", cal["msg"])
        self.assertGreater(cal["header_ink"], 200)       # the weekday names
        self.assertGreater(cal["title_ink"], 2000)       # the big month number
        tag = self.out["tag"]
        for tpl in ("tag8", "seat", "cert"):
            self.assertNotIn("表示できません", tag[tpl]["msg"])
            self.assertGreater(tag[tpl]["ink"], 3000, tpl)
        self.assertFalse(tag["cert"]["cert_fields_hidden"])
        self.assertTrue(self.out["tag"]["tag8"]["cert_fields_hidden"])

    def test_new_year_card_maker_draws_a_postcard(self):
        n = self.out["nenga"]
        self.assertEqual(n["size"], [1181, 1748])
        self.assertIn("選んだイラスト", n["msg"])
        self.assertRegex(n["date"], r"^令和\d+年 元旦$")
        self.assertGreater(n["head_ink"], 800)          # the greeting
        self.assertGreater(n["body_ink"], 3000)         # the picture and the message

    def test_background_switcher(self):
        self.assertEqual(self.out["bg_dark"], "rgb(43, 27, 20)")
        self.assertTrue(self.out["solid"])
        self.assertTrue(self.out["bg_reset"])


if __name__ == "__main__":
    unittest.main()
