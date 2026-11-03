"""Measuring partner-link clicks, time on page and return visits without knowing who anybody is (sokuhou/measure.py, read by sokuhou/accesslog.py).

The promise is part of the sites' privacy page, so the tests check it: the script sends only the kind of event and a bucketed number, never an address, a page, a
referrer or an identifier, and what comes out of the log is counts.  The script itself is run in headless Chrome where Chrome exists (CI has it)."""
from __future__ import annotations

import http.server
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from sokuhou import accesslog, layoutcheck, measure, newsite, sitekit
from sokuhou.layoutcheck import find_chrome
from tests.test_accesslog import line

HUMAN = "Mozilla/5.0 (Windows NT 10.0) Chrome/120"


def beacon(q: str, ua: str = HUMAN, status: int = 200, method: str = "GET") -> str:
    return line(path=f"/m/t.gif?{q}", ua=ua, status=status, method=method)


class ParseTest(unittest.TestCase):
    def test_our_three_events_parse(self):
        self.assertEqual(measure.parse_beacon("/m/t.gif?k=s&r=1&_=ab12"), {"k": "s", "r": 1})
        self.assertEqual(measure.parse_beacon("/m/t.gif?k=c&t=aff"), {"k": "c", "t": "aff"})
        self.assertEqual(measure.parse_beacon("/m/t.gif?k=e&d=30&n=2"), {"k": "e", "d": 30, "n": 2})

    def test_anything_else_is_ignored(self):
        for t in ("/m/t.gif", "/m/t.gif?k=c&t=https://shop.example/x", "/m/t.gif?k=c&t=other", "/m/t.gif?k=e&d=31&n=2", "/m/t.gif?k=e&d=30&n=99",
                  "/m/t.gif?k=s&r=7", "/m/other.gif?k=s&r=1", "/m/t.gif?k=x"):
            self.assertIsNone(measure.parse_beacon(t), t)


class AggregateTest(unittest.TestCase):
    def lines(self, visits=120, returning=30, aff=6, leaves=240):
        out = [beacon("k=s&r=0")] * (visits - returning) + [beacon("k=s&r=1")] * returning
        out += [beacon("k=c&t=aff")] * aff + [beacon("k=c&t=out")] * 4
        out += [beacon("k=e&d=15&n=1")] * (leaves // 2) + [beacon("k=e&d=60&n=2")] * (leaves // 2)
        return out

    def test_the_numbers_of_l4_and_l5(self):
        r = accesslog.aggregate(self.lines(), "x.example")
        s = measure.summary(r["measure"])
        self.assertEqual((s["visits"], s["aff_clicks"], s["out_clicks"], s["page_leaves"]), (120, 6, 4, 240))
        self.assertAlmostEqual(s["L4_aff_per_visit"], 6 / 120)
        self.assertAlmostEqual(s["L5_return_rate"], 30 / 120)
        self.assertAlmostEqual(s["L5_pages_per_visit"], 2.0)
        self.assertEqual(s["L5_median_dwell_bucket_sec"], 15)

    def test_too_few_visits_are_not_judged(self):
        """6-3: no signal below 100 sessions.  The number must be None (printed as 測れなかった), never a small, tempting rate."""
        s = measure.summary(accesslog.aggregate(self.lines(visits=40, returning=10, leaves=60), "x.example")["measure"])
        self.assertIsNone(s["L4_aff_per_visit"])
        self.assertIsNone(s["L5_return_rate"])
        self.assertIsNone(s["L5_median_dwell_bucket_sec"])
        out = accesslog.render(accesslog.aggregate(self.lines(visits=40, returning=10, leaves=60), "x.example"), "x.example")
        self.assertIn("測れなかった", out)

    def test_bots_and_odd_requests_do_not_count_and_are_not_page_views(self):
        bot = "Mozilla/5.0 (compatible; Googlebot/2.1)"
        ls = [beacon("k=s&r=0", ua=bot)] * 5 + [beacon("k=s&r=0", status=404)] * 5 + [beacon("k=s&r=0", method="POST")] * 5 + [beacon("k=c&t=https://a.example/")] * 5
        r = accesslog.aggregate(ls, "x.example")
        self.assertEqual(r["measure"]["visits"], 0)
        self.assertEqual(r["measure"]["ignored"], 20)
        self.assertEqual(r["human_views"], 0)          # the file is not a page

    def test_no_beacon_is_said_plainly(self):
        out = accesslog.render(accesslog.aggregate([line()], "x.example"), "x.example")
        self.assertIn("受信なし", out)

    def test_the_report_has_no_identifier(self):
        ls = [line(ip="198.51.100.77", path="/m/t.gif?k=s&r=1&_=zz99", ua=HUMAN + " UniqueAgent/7")] * 5
        out = accesslog.render(accesslog.aggregate(ls, "x.example"), "x.example")
        for secret in ("198.51.100.77", "UniqueAgent", "zz99"):
            self.assertNotIn(secret, out)


class ScriptTest(unittest.TestCase):
    JS = measure.MEASURE_JS

    def test_the_script_sends_nothing_that_identifies(self):
        """The promise of the privacy page, as text: no cookie, no page address, no referrer, no storage value sent; only k t r d n and a cache-buster."""
        for forbidden in ("document.cookie", "location.href", "location.pathname", "location.search", "referrer", "userAgent", "innerText", "getAttribute(\"href\")", ".href"):
            self.assertNotIn(forbidden, self.JS, forbidden)
        keys = set(re.findall(r'"([a-z_]+)=', self.JS)) | set(re.findall(r'&([a-z_]+)=', self.JS))
        self.assertEqual(keys, {"k", "r", "t", "d", "n", "_"})

    def test_do_not_track_and_automation_are_respected(self):
        self.assertIn('doNotTrack==="1"', self.JS)
        self.assertIn("webdriver", self.JS)

    def test_gif_is_a_real_image(self):
        self.assertTrue(measure.GIF.startswith(b"GIF89a"))


class _Log(http.server.BaseHTTPRequestHandler):
    seen: list[str] = []
    page = b""

    def do_GET(self):
        if self.path.startswith("/m/t.gif"):
            _Log.seen.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.end_headers()
            self.wfile.write(measure.GIF)
        elif self.path.startswith("/measure.js"):
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.end_headers()
            self.wfile.write(measure.MEASURE_JS.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_Log.page)

    def log_message(self, *a):
        pass


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>t</title><script src="/measure.js"></script></head><body>
<a id="aff" href="#x" rel="sponsored noopener">partner</a><a id="out" href="https://other.example/">other</a><a id="mark" href="#y" data-m="dl">dl</a><a id="own" href="#z">own</a>
<script>
document.addEventListener("click", function (e) { e.preventDefault(); });
window.addEventListener("load", function () {
  ["aff", "out", "mark", "own"].forEach(function (id) { document.getElementById(id).click(); });
  setTimeout(function () { window.dispatchEvent(new Event("pagehide")); }, 300);
});
</script></body></html>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class BrowserTest(unittest.TestCase):
    def run_page(self, page: str) -> list[str]:
        _Log.seen, _Log.page = [], page.encode()
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Log)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        profile = tempfile.mkdtemp(prefix="measure_")
        try:
            subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={profile}",
                            "--virtual-time-budget=4000", "--dump-dom", f"http://127.0.0.1:{srv.server_address[1]}/"], capture_output=True, timeout=120)
        finally:
            srv.shutdown()
            shutil.rmtree(profile, ignore_errors=True)
        return list(_Log.seen)

    def test_the_script_sends_the_events_and_nothing_else(self):
        seen = self.run_page(PAGE)
        kinds = sorted(re.sub(r"&_=[a-z0-9]*$", "", p.split("?", 1)[1]) for p in seen)
        self.assertEqual(kinds, sorted(["k=s&r=0", "k=c&t=aff", "k=c&t=out", "k=c&t=dl", "k=e&d=5&n=1"]), seen)
        for p in seen:                 # the same promise, on what really went over the wire
            self.assertNotIn("127.0.0.1", p)
            self.assertNotIn("other.example", p)
            self.assertRegex(p, r"^/m/t\.gif\?k=[sce](&[a-z]=[a-z0-9]+)*&_=[a-z0-9]{0,4}$")

    def test_a_click_on_an_own_page_link_sends_nothing(self):
        seen = self.run_page(PAGE.replace('<a id="aff"', '<a id="aff2" style="display:none"').replace('"aff", "out", "mark", "own"', '"own"'))
        self.assertFalse([p for p in seen if "k=c" in p], seen)


class SiteIntegrationTest(unittest.TestCase):
    def test_measured_site_ships_script_gif_privacy_text_and_no_cache_rule(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            d = newsite.init_site("msite", "m.example", "計測サイト", "計", tmp, "2026-11-03")
            pages, _ = newsite.build_pages(d, release=True, allow_example=True)
            self.assertIn("/assets/measure.js?v=", pages["index.html"])
            self.assertEqual(pages["assets/measure.js"], measure.MEASURE_JS)
            self.assertEqual(pages["m/t.gif"], measure.GIF)
            self.assertIn('Request_URI "^/m/" Ngx_Cache_NoCacheMode=on', pages[".htaccess"])
            self.assertIn("クッキーは使いません", pages["privacy/index.html"])
            self.assertNotIn("使用していません。使用を始める", pages["privacy/index.html"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unmeasured_site_and_preview_keep_the_old_text_and_no_script(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            d = newsite.init_site("nsite", "n.example", "計測なし", "計", tmp, "2026-11-03")
            cfg = (d / "config.json").read_text(encoding="utf-8").replace('"measure": true', '"measure": false')
            (d / "config.json").write_text(cfg, encoding="utf-8")
            pages, _ = newsite.build_pages(d, release=True, allow_example=True)
            self.assertNotIn("measure.js", pages["index.html"])
            self.assertNotIn("m/t.gif", pages)
            self.assertIn("アクセス解析ツールを使用していません", pages["privacy/index.html"])
            (d / "config.json").write_text(cfg.replace('"measure": false', '"measure": true').replace("株式会社MACS", ""), encoding="utf-8")
            pre, _ = newsite.build_pages(d, allow_example=True)          # a preview (operator unset) is not counted
            self.assertNotIn("measure.js", pre["index.html"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_other_sites_privacy_text_is_unchanged(self):
        self.assertEqual(sitekit.analytics_text({}), sitekit.NO_ANALYTICS_TEXT)
        self.assertIn("Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は", sitekit.NO_ANALYTICS_TEXT)


if __name__ == "__main__":
    unittest.main()
