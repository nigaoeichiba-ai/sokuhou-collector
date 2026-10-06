"""Browser-level check of the scripts on よろこぶプレゼント: the finder, budget presets, filters, sorting, the concierge and the favourites.

Builds the site from the fixtures, serves it locally and drives it with a headless Chrome (skipped when Chrome is not installed).
"""
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                           "/usr/bin/google-chrome", "/usr/bin/chromium") if Path(p).exists()), None)
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None, "adsense_pub_id": None}

SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '1200px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(300); return f;
}
const vis = (d) => [...d.querySelectorAll('.grid-all li.item')].filter(li => !li.hidden).map(li => li.getAttribute('data-code'));
(async () => {
  try {
    // 1. the finder
    let f = await load('/'); let d = f.contentDocument, w = f.contentWindow;
    const fm = d.querySelector('form.finder');
    out.finder_default = [fm.o.value, fm.r.value, fm.b.value];
    fm.o.value = 'birthday'; fm.o.dispatchEvent(new w.Event('change'));
    out.recipients_after_event = [...fm.r.options].filter(o => o.value && !o.disabled).map(o => o.value).sort();
    fm.r.value = 'mother'; fm.r.dispatchEvent(new w.Event('change'));
    out.budgets_for_birthday_mother = [...fm.b.options].filter(o => o.value && !o.disabled).map(o => o.value);
    fm.r.value = ''; fm.r.dispatchEvent(new w.Event('change'));
    fm.o.value = ''; fm.o.dispatchEvent(new w.Event('change'));
    fm.r.value = 'mother'; fm.r.dispatchEvent(new w.Event('change'));
    out.events_after_recipient = [...fm.o.options].filter(o => o.value && !o.disabled).map(o => o.value).sort();
    fm.o.value = ''; fm.r.value = ''; fm.o.dispatchEvent(new w.Event('change'));
    fm.dispatchEvent(new w.Event('submit', {cancelable: true}));
    out.message_when_empty = d.querySelector('.finder-msg').hidden ? '' : d.querySelector('.finder-msg').textContent;
    fm.o.value = 'birthday'; fm.o.dispatchEvent(new w.Event('change')); fm.r.value = 'boyfriend'; fm.r.dispatchEvent(new w.Event('change')); fm.b.value = '3000-5000';
    fm.dispatchEvent(new w.Event('submit', {cancelable: true}));
    await wait(800);
    out.after_submit = f.contentWindow.location.pathname + f.contentWindow.location.search;
    d = f.contentDocument;
    out.preset_visible = vis(d);                          // ?b=3000-5000 preselects that budget
    // 2. filters and sorting
    const set = d.querySelector('.chipset[data-filter="tier"]');
    set.querySelector('.chipbtn[data-v=""]').click();
    out.all_visible = vis(d);
    const sel = d.querySelector('[data-sort]'); sel.value = 'price-desc'; sel.dispatchEvent(new f.contentWindow.Event('change'));
    out.price_desc = vis(d);
    sel.value = 'reviews'; sel.dispatchEvent(new f.contentWindow.Event('change'));
    out.reviews_first = vis(d)[0];
    sel.value = 'price-asc'; sel.dispatchEvent(new f.contentWindow.Event('change'));
    out.price_asc = vis(d);
    d.querySelector('.chipset[data-filter="type"] .chipbtn[data-v="思い出・名入れ"]').click();
    out.type_filter = vis(d);
    d.querySelector('.chipset[data-filter="type"] .chipbtn[data-v=""]').click();
    out.count_text = d.querySelector('.count').textContent;
    // 3. a budget the page does not have: nothing breaks, everything stays visible
    f = await load('/gift/birthday-mother/?b=3000-5000'); d = f.contentDocument;
    out.unavailable_budget = vis(d);
    out.no_such_chip = !d.querySelector('.chipset[data-filter="tier"] .chipbtn[data-v="3000-5000"]');
    // 4. the concierge
    f = await load('/gift/birthday-boyfriend/'); d = f.contentDocument; w = f.contentWindow;
    let opened = null; w.open = (u) => { opened = u; };
    const kw = d.querySelector('form.kw-form'); kw.elements.q.value = 'ガーデニングが好きな60代';
    kw.dispatchEvent(new w.Event('submit', {cancelable: true}));
    out.concierge_url = opened;
    // 5. favourites
    const fav = d.querySelector('.fav'); fav.click();
    out.fav_bar_visible = !d.querySelector('.fav-bar').hidden;
    out.fav_count = d.querySelector('.fav-open b').textContent;
    out.fav_line = d.querySelector('.fav-panel a.btn').href;
    out.fav_stored = w.localStorage.getItem('yorokobu.favs');
    fav.click();
    out.fav_after_remove = d.querySelector('.fav-open b').textContent;
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


def run_chrome(url: str) -> str:
    profile = tempfile.mkdtemp(prefix="yorokobu_e2e_")
    try:
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={profile}", "--virtual-time-budget=30000",
                            "--dump-dom", url], capture_output=True, timeout=180)
        return r.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(profile, ignore_errors=True)


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally; CI must not be blocked by a browser quirk")
class BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))
        (cls.root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{SCENARIO}</script>', encoding="utf-8")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cls.root))
        handler.log_message = lambda *a, **k: None
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        import html
        cls.out = json.loads(html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_no_script_error(self):
        self.assertNotIn("error", self.out)

    def test_finder_starts_empty_and_only_offers_pages_that_exist(self):
        o = self.out
        self.assertEqual(o["finder_default"], ["", "", ""])
        self.assertEqual(o["recipients_after_event"], ["boyfriend", "mother"])
        self.assertEqual(o["budgets_for_birthday_mother"], ["under3000"])
        self.assertEqual(o["events_after_recipient"], ["birthday", "mothers-day"])
        self.assertIn("選んでください", o["message_when_empty"])

    def test_finder_goes_to_the_page_with_the_budget_preselected(self):
        self.assertEqual(self.out["after_submit"], "/gift/birthday-boyfriend/?b=3000-5000")
        self.assertEqual(self.out["preset_visible"], ["a3"])          # only the 3,000-5,000 yen product
        self.assertEqual(sorted(self.out["all_visible"]), ["a1", "a2", "a3"])

    def test_sorting_and_type_filter(self):
        o = self.out
        self.assertEqual(o["price_desc"], ["a3", "a1", "a2"])
        self.assertEqual(o["price_asc"], ["a2", "a1", "a3"])
        self.assertEqual(o["reviews_first"], "a2")
        self.assertEqual(o["type_filter"], ["a3"])
        self.assertEqual(o["count_text"], "3点を表示中")

    def test_a_budget_the_page_does_not_have_changes_nothing(self):
        self.assertTrue(self.out["no_such_chip"])
        # the mother page keeps its one fitting product and the operator's own card; the men's wallet is gone
        self.assertEqual(sorted(self.out["unavailable_budget"]), ["b1", "p1"])

    def test_concierge_opens_a_rakuten_search_through_our_affiliate_id(self):
        url = self.out["concierge_url"]
        self.assertTrue(url.startswith("https://hb.afl.rakuten.co.jp/hgc/AFF.ID/trk?pc="))
        self.assertIn("%25E3%2582%25AC%25E3%2583%25BC%25E3%2583%2587%25E3%2583%258B%25E3%2583%25B3%25E3%2582%25B0", url)   # ガーデニング, double-encoded in pc
        self.assertIn("%2520%25E3%2582%25AE%25E3%2583%2595%25E3%2583%2588", url)                                              # " ギフト" was appended

    def test_favourites_are_kept_and_shareable(self):
        o = self.out
        self.assertTrue(o["fav_bar_visible"])
        self.assertEqual(o["fav_count"], "1")
        self.assertTrue(o["fav_line"].startswith("https://line.me/R/msg/text/?"))
        self.assertIn('"code"', o["fav_stored"])
        self.assertEqual(o["fav_after_remove"], "0")


if __name__ == "__main__":
    unittest.main()
