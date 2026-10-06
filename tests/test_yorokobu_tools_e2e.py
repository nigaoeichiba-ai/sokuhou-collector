"""Browser check of the quiz, the calculators and the etiquette checker (skipped without Chrome, and in CI)."""
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

from sites.yorokobu import build, content as ct
from tests.test_yorokobu_e2e import CHROME, run_chrome
from tests.test_yorokobu_tools import CFG

SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '1100px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(300); return f;
}
(async () => {
  try {
    let f = await load('/tool/calc/'), d = f.contentDocument, w = f.contentWindow;
    const set = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
    set(d.querySelector('[name="amount"]'), '12000');
    out.range = d.querySelector('[data-out="range"]').textContent;
    set(d.querySelector('[name="total"]'), '10000'); set(d.querySelector('[name="people"]'), '3');
    out.each = d.querySelector('[data-out="each"]').textContent;

    f = await load('/diagnosis/'); d = f.contentDocument;
    d.querySelector('[data-start]').click(); await wait(100);
    out.q1 = d.querySelector('.quiz-q').textContent;
    for (let i = 0; i < 6; i++) { d.querySelector('.quiz-opt').click(); await wait(150); }
    await wait(800);
    out.result = f.contentWindow.location.pathname;

    f = await load('/tool/taboo/'); d = f.contentDocument; w = f.contentWindow;
    const q = d.querySelector('[name="q"]');
    out.all = d.querySelectorAll('.tb:not([hidden])').length;
    q.value = 'クシ'; q.dispatchEvent(new w.Event('input', { bubbles: true }));
    out.kushi = d.querySelectorAll('.tb:not([hidden])').length;
    q.value = 'zzzzqq'; q.dispatchEvent(new w.Event('input', { bubbles: true }));
    out.none = d.querySelectorAll('.tb:not([hidden])').length; out.msg = d.querySelector('.tb-msg').textContent;
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally")
class ToolsBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.c = ct.load()
        build.render_site(cls.c, None, CFG, root, release=False, today=date(2026, 10, 7))
        (root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{SCENARIO}</script>', encoding="utf-8")

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        cls.out = json.loads(_html.unescape(re.search(r'<pre id="out">(.*?)</pre>', dom, re.S).group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_calculators(self):
        self.assertNotIn("error", self.out)
        self.assertEqual(self.out["range"], "4,000円 〜 6,000円")
        self.assertEqual(self.out["each"], "一人 3,340円")

    def test_quiz_ends_on_a_persona_page(self):
        slugs = [p["slug"] for p in self.c["persona"]["personas"]]
        self.assertIn(self.out["result"].strip("/").split("/")[-1], slugs)
        self.assertTrue(self.out["result"].startswith("/diagnosis/"))

    def test_checker_filters(self):
        if not self.c["taboo"]:
            self.skipTest("no etiquette entries yet")
        self.assertEqual(self.out["all"], len(self.c["taboo"]))
        self.assertGreaterEqual(self.out["kushi"], 1)
        self.assertLess(self.out["kushi"], self.out["all"])
        self.assertEqual(self.out["none"], 0)
        self.assertIn("見つかりませんでした", self.out["msg"])


if __name__ == "__main__":
    unittest.main()
