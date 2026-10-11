"""atomou: every input, select and textarea keeps a usable size at 300px and 375px in several skins (owner, 2026-10-10 and 2026-10-11: the "やること" box of the card page was
squeezed to a few pixels between a select and a button).  A real headless Chrome loads each page in an iframe of that width, opens the parts that only exist after a click (the card
page's task rows), switches skins, and measures.  A text box under 110px, a select / date box under 80px, a number box under 64px, anything under 30px high or sticking out of
the screen is a problem.  The check is tried against the old rule too: it must find it."""
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import functools
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = "2026-10-11"
SKINS = ["basic", "large", "halloween", "contrast"]
WIDTHS = [300, 375]
# (path, steps run inside the page before measuring)
PAGES = [
    ("/", ""),
    ("/search/?q=%E5%B9%B4%E8%B3%80%E7%8A%B6", ""),
    ("/add/?kind=event&date=2026-10-20", ""),
    ("/add/?quick=1", ""),
    ("/my/", ""),
    ("/interests/", ""),
    ("/contact/?kind=date&page=https%3A%2F%2Fatomou.com%2Fe%2Fabc%2F", ""),
    ("/card/", "var t=d.querySelector('[data-tpl]'); if (t) t.click(); var a=d.getElementById('x-addtask'); if (a) a.click();"),
]

AUDIT = r"""
function audit(d, W) {
  var out = [];
  [].forEach.call(d.querySelectorAll('input,select,textarea'), function (e) {
    var t = (e.type || e.tagName).toLowerCase();
    if (['hidden', 'checkbox', 'radio', 'file', 'range', 'color'].indexOf(t) >= 0) return;
    if (e.closest('[hidden]') || e.closest('.cf-hp') || /(^| )vh( |$)/.test(e.className)) return;
    var cs = d.defaultView.getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return;
    var r = e.getBoundingClientRect(); if (!r.width) return;
    var tl = (t === 'text' || t === 'search' || t === 'email' || t === 'url' || t === 'tel' || e.tagName === 'TEXTAREA'), m = tl ? 110 : (t === 'number' ? 64 : 80);
    if (r.width < m || r.height < 30 || r.right > W + 1 || r.left < -1) out.push(e.tagName + '#' + (e.id || e.name || e.className || '') + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  return out;
}
"""


def harness(pages, widths, skins, extra_css=""):
    items = json.dumps([[p, s] for p, s in pages])
    return f"""<!doctype html><meta charset="utf-8"><title>controls</title><body><pre id="out">[]</pre><div id="host"></div><script>
{AUDIT}
var PAGES = {items}, WIDTHS = {json.dumps(widths)}, SKINS = {json.dumps(skins)}, EXTRA = {json.dumps(extra_css)}, results = [];
function wait(ms) {{ return new Promise(function (r) {{ setTimeout(r, ms); }}); }}
async function one(path, steps, w) {{
  var f = document.createElement('iframe'); f.style.cssText = 'width:' + w + 'px;height:900px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (res) {{ f.onload = res; f.src = path + (path.indexOf('?') < 0 ? '?' : '&') + 'today={TODAY}'; }});
  await wait(900);
  var d = f.contentDocument, A = f.contentWindow.AtomouApp, bad = [];
  if (EXTRA) {{ var st = d.createElement('style'); st.textContent = EXTRA; d.head.appendChild(st); }}
  if (steps) {{ try {{ new Function('d', steps)(d); }} catch (e) {{ bad.push('steps: ' + e); }} await wait(300); }}
  for (var i = 0; i < SKINS.length; i++) {{
    if (A) {{ A.state().prefs.skin = SKINS[i]; A.applyPrefs(); }}
    var r = audit(d, w); if (r.length) bad.push(SKINS[i] + ': ' + r.slice(0, 3).join('; '));
  }}
  results.push({{page: path, width: w, controls: d.querySelectorAll('input:not([type=hidden]),select,textarea').length, bad: bad}});
  f.remove();
}}
(async function () {{
  for (var p = 0; p < PAGES.length; p++) for (var k = 0; k < WIDTHS.length; k++) {{ try {{ await one(PAGES[p][0], PAGES[p][1], WIDTHS[k]); }} catch (e) {{ results.push({{page: PAGES[p][0], width: WIDTHS[k], controls: 0, bad: ['failed: ' + e]}}); }} }}
  document.getElementById('out').textContent = JSON.stringify(results);
}})();
</script>"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


class _Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):      # Chrome drops connections when an iframe is replaced: not an error
        pass


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chrome = layoutcheck.find_chrome()
        cls.tmp = tempfile.TemporaryDirectory()
        pages = build.build_pages(CFG, release=True)
        build.write_pages(pages, Path(cls.tmp.name))
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def measure(self, extra_css="", pages=PAGES):
        (Path(self.tmp.name) / "__controls.html").write_text(harness(pages, WIDTHS, SKINS, extra_css), encoding="utf-8")
        dom = ""
        for _ in range(2):   # a headless Chrome sometimes stalls: once more
            with tempfile.TemporaryDirectory() as prof:
                try:
                    r = subprocess.run([self.chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=180000",
                                        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"{self.base}/__controls.html"], capture_output=True, timeout=300)
                except subprocess.TimeoutExpired:
                    continue
            dom = r.stdout.decode("utf-8", "replace")
            if re.search(r'<pre id="out">\s*\[\s*\{', dom):
                break
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        self.assertTrue(m, "the harness page did not finish")
        import html as _h
        return json.loads(_h.unescape(m.group(1)))

    @unittest.skipUnless(layoutcheck.find_chrome(), "Chrome is needed")
    def test_every_control_is_usable_on_every_page_width_and_skin(self):
        res = self.measure()
        self.assertEqual(len(res), len(PAGES) * len(WIDTHS))
        self.assertGreater(sum(r["controls"] for r in res), 40)
        bad = [f"{r['page']} @{r['width']}: {r['bad']}" for r in res if r["bad"]]
        self.assertEqual(bad, [])

    @unittest.skipUnless(layoutcheck.find_chrome(), "Chrome is needed")
    def test_the_check_finds_the_old_card_task_rule(self):
        old = ".x-task{flex-wrap:nowrap!important}.x-task select{flex:0 0 auto!important;max-width:42%!important}.x-task input{flex:1 1 7em!important;min-width:5em!important}"
        res = self.measure(extra_css=old, pages=[p for p in PAGES if p[0] == "/card/"])
        self.assertTrue(any(r["bad"] for r in res), res)


if __name__ == "__main__":
    unittest.main()
