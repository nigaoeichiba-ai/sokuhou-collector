"""Sharing a candidate list: the favourites become one link (/list/?c=code,code); whoever opens it sees the same products, with the shops' links."""
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

from sites.yorokobu import build, content
from sokuhou import sitecheck
from tests.test_yorokobu_e2e import CHROME, run_chrome

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}


def render(tmp: Path) -> Path:
    c = content.load(FIX)
    items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
    out = tmp / "site"
    build.render_site(c, items, CFG, out, release=True, today=date(2026, 10, 7))
    return out


class ShareListDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = render(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def test_the_data_file_has_every_product_the_pages_show_with_its_two_shop_links(self):
        db = json.loads((self.out / "list/items.json").read_text(encoding="utf-8"))
        shown = set()
        for f in self.out.rglob("*.html"):
            shown |= set(re.findall(r'<li class="item" data-code="([^"]+)"', f.read_text(encoding="utf-8")))
        own = {c for c in shown if c not in db}                       # the operator's own shop listing is not shared
        self.assertGreaterEqual(len(db), 5)
        self.assertLessEqual(len(own), 2, own)
        for code, it in list(db.items())[:50]:
            self.assertTrue(it["u"].startswith("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc="), code)
            self.assertIn("tag=amazonmacs-22", it["a"], code)
            self.assertTrue(it["i"].startswith("https://"), code)
            self.assertGreater(it["p"], 0)

    def test_the_list_page_is_noindex_not_in_the_sitemap_and_carries_the_notices(self):
        html = (self.out / "list/index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex,nofollow">', html)
        self.assertNotIn("/list/", (self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn("Amazonのアソシエイトとして", html)                 # its Amazon buttons are made by the script, the notice is there anyway
        self.assertIn("楽天アフィリエイト・Amazonアソシエイト", html)
        self.assertIn('data-src="/list/items.json"', html)
        self.assertEqual([p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "list" in p], [])

    def test_the_share_bar_offers_the_phones_own_share_sheet_and_the_script_knows_both(self):
        html = (self.out / "gift/birthday-boyfriend/index.html").read_text(encoding="utf-8")
        self.assertIn('class="share-btn native" hidden', html)
        js = (self.out / "assets/app.js").read_text(encoding="utf-8")
        for needle in ("navigator.share", "/list/?c=", "initList"):
            self.assertIn(needle, js)

    def test_without_products_there_is_no_list_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(content.load(FIX), None, CFG, out, release=False, today=date(2026, 10, 7))
            self.assertFalse((out / "list").exists())


SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    const db = await (await fetch('/list/items.json')).json();
    const codes = Object.keys(db).slice(0, 3);
    out.codes = codes.length;
    const f = document.createElement('iframe'); f.style.width = '1000px'; f.style.height = '900px'; document.body.appendChild(f);
    await new Promise(r => { f.onload = r; f.src = '/list/?c=' + codes.map(encodeURIComponent).join(',') + ',no-such-code'; }); await wait(900);
    const d = f.contentDocument;
    const cards = [...d.querySelectorAll('#list-items .item')];
    out.cards = cards.length;
    out.msg = d.querySelector('.list-msg').textContent;
    out.first = cards[0] && {name: cards[0].querySelector('h3').textContent, price: cards[0].querySelector('.price').textContent,
                             buttons: [...cards[0].querySelectorAll('.btn')].map(a => ({t: a.textContent, href: a.href, rel: a.rel}))};
    out.scroll = d.documentElement.scrollWidth;
    const g = document.createElement('iframe'); g.style.width = '300px'; g.style.height = '900px'; document.body.appendChild(g);
    await new Promise(r => { g.onload = r; g.src = '/list/?c=' + codes.map(encodeURIComponent).join(','); }); await wait(900);
    out.scroll300 = g.contentDocument.documentElement.scrollWidth;
    const h = document.createElement('iframe'); h.style.width = '500px'; h.style.height = '600px'; document.body.appendChild(h);
    await new Promise(r => { h.onload = r; h.src = '/list/'; }); await wait(500);
    out.empty = h.contentDocument.querySelector('.list-msg').textContent;
    const k = document.createElement('iframe'); k.style.width = '500px'; k.style.height = '600px'; document.body.appendChild(k);
    await new Promise(r => { k.onload = r; k.src = '/list/?c=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E'; }); await wait(700);
    out.hostile = k.contentDocument.querySelectorAll('#list-items img').length;
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally")
class ShareListBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = render(Path(cls.tmp.name))
        (root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{SCENARIO}</script>', encoding="utf-8")

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        cls.out = json.loads(_html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def test_a_shared_link_shows_the_same_products_with_both_shops_and_ignores_unknown_codes(self):
        o = self.out
        self.assertNotIn("error", o)
        self.assertEqual(o["cards"], o["codes"], o)                         # the unknown code is skipped, the known ones are shown
        self.assertEqual(o["msg"], f"{o['codes']}点の候補です。")
        b = o["first"]["buttons"]
        self.assertEqual([x["t"] for x in b], ["楽天市場で見る", "Amazonで探す"])
        self.assertTrue(b[0]["href"].startswith("https://hb.afl.rakuten.co.jp/"))
        self.assertIn("tag=amazonmacs-22", b[1]["href"])
        self.assertTrue(all("sponsored" in x["rel"] for x in b))
        self.assertTrue(o["first"]["price"].startswith("¥"))

    def test_it_fits_a_phone_and_handles_an_empty_or_hostile_link(self):
        o = self.out
        self.assertLessEqual(o["scroll"], 1001)
        self.assertLessEqual(o["scroll300"], 301)
        self.assertEqual(o["empty"], "候補が指定されていません。")
        self.assertEqual(o["hostile"], 0)                                   # a code that is not in the data file draws nothing, whatever it contains


if __name__ == "__main__":
    unittest.main()
