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
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


def render(tmp: Path) -> Path:
    c = content.load(FIX)
    items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
    out = tmp / "site"
    build.render_site(c, items, CFG, out, release=True, today=date(2026, 10, 7))
    return out


class GachaDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = render(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def test_the_data_file_lists_products_per_recipient_and_budget_without_repeats(self):
        data = json.loads((self.out / "tool/gacha/items.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["rec"]), 2)
        for slug, r in data["rec"].items():
            self.assertTrue(r["name"])
            for tier, rows in r["tiers"].items():
                self.assertTrue(rows)
                self.assertLessEqual(len(rows), 12)
                urls = [x[3] for x in rows]
                self.assertEqual(len(urls), len(set(urls)), (slug, tier))
                for name, price, image, url, reviews, rating10 in rows:
                    self.assertTrue(url.startswith("https://") and "hb.afl.rakuten" not in url)    # the plain item page: the link is built on the page
                    self.assertGreater(price, 0)
                    self.assertTrue(image.startswith("https://"))
        self.assertEqual({t["slug"] for t in data["tiers"]}, {t for r in data["rec"].values() for t in r["tiers"]})

    def test_every_product_sits_in_the_budget_it_is_filed_under(self):
        c = content.load(FIX)
        tiers = {t["slug"]: t for t in c["filters"]["tiers"]}
        data = json.loads((self.out / "tool/gacha/items.json").read_text(encoding="utf-8"))
        for r in data["rec"].values():
            for tier, rows in r["tiers"].items():
                for row in rows:
                    t = tiers[tier]
                    self.assertTrue((t.get("min") is None or row[1] > t["min"]) and (t.get("max") is None or row[1] <= t["max"]), (tier, row[1]))

    def test_the_page_has_the_form_the_notice_the_disclaimer_and_is_linked_from_the_tools_hub(self):
        html = (self.out / "tool/gacha/index.html").read_text(encoding="utf-8")
        for needle in ('id="gacha"', 'data-src="/tool/gacha/items.json"', 'data-aff="aaaa1111.bbbb2222.cccc3333.dddd4444"', 'name="r"', 'name="t"', "ガチャを回す",
                       '<span class="pr-chip">PR</span>', "価格・在庫は2026年10月7日"):
            self.assertIn(needle, html)
        self.assertIn('href="/tool/gacha/"', (self.out / "tool/index.html").read_text(encoding="utf-8"))
        self.assertIn("/tool/gacha/", (self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual([p for p in sitecheck.check_dir(self.out, CFG["site_url"]) if "gacha" in p], [])


SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    const f = document.createElement('iframe'); f.style.width = '1000px'; f.style.height = '900px'; document.body.appendChild(f);
    await new Promise(r => { f.onload = r; f.src = '/tool/gacha/'; }); await wait(800);
    const d = f.contentDocument, form = d.querySelector('.gacha-form');
    out.recipients = [...form.elements.r.options].map(o => o.value);
    out.before = d.querySelector('.gacha-out').children.length;
    form.elements.r.value = out.recipients[0];
    const ts = [...form.elements.t.options].map(o => o.value);
    let shown = null;
    for (const t of ts) {
      form.elements.t.value = t; form.querySelector('button[type="submit"]').click(); await wait(200);
      const card = d.querySelector('.gacha-card');
      if (card) { shown = {title: card.querySelector('h2').textContent, href: card.querySelector('a.btn').href, rel: card.querySelector('a.btn').rel, price: card.querySelector('.price').textContent}; break; }
    }
    out.card = shown;
    out.msg = d.querySelector('.gacha-msg').textContent;
    const again = d.querySelector('.gacha-actions button'); out.again = !!again;
    if (again) { again.click(); await wait(100); out.after = !!d.querySelector('.gacha-card'); }
    out.scroll = d.documentElement.scrollWidth;
    // the same on a 300px phone: the card must not push the page sideways
    const g = document.createElement('iframe'); g.style.width = '300px'; g.style.height = '900px'; document.body.appendChild(g);
    await new Promise(r => { g.onload = r; g.src = '/tool/gacha/'; }); await wait(800);
    const d2 = g.contentDocument, f2 = d2.querySelector('.gacha-form');
    f2.elements.r.value = out.recipients[0];
    for (const t of [...f2.elements.t.options].map(o => o.value)) { f2.elements.t.value = t; f2.querySelector('button[type="submit"]').click(); await wait(200); if (d2.querySelector('.gacha-card')) break; }
    out.card300 = !!d2.querySelector('.gacha-card'); out.scroll300 = d2.documentElement.scrollWidth;
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally")
class GachaBrowserTest(unittest.TestCase):
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

    def test_turning_the_gacha_shows_a_product_with_an_affiliate_link_and_can_be_turned_again(self):
        o = self.out
        self.assertNotIn("error", o)
        self.assertEqual(o["before"], 0)
        self.assertIsNotNone(o["card"], o)
        self.assertTrue(o["card"]["href"].startswith("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc="))
        self.assertIn("sponsored", o["card"]["rel"])
        self.assertTrue(o["card"]["price"].endswith("円"))
        self.assertTrue(o["again"] and o["after"])
        self.assertTrue(o["card300"])
        self.assertLessEqual(o["scroll300"], 301)


if __name__ == "__main__":
    unittest.main()
