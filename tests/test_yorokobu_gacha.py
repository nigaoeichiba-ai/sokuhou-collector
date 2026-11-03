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

from tests import items_mock
from sites.yorokobu import build, content
from sokuhou import sitecheck
from tests.yorokobu_data import rich_boyfriend
from tests.test_yorokobu_e2e import CHROME, run_chrome

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}


def render(tmp: Path) -> Path:
    c = content.load(FIX)
    items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
    out = tmp / "site"
    build.render_site(c, items, CFG, out, release=True, today=date(2026, 10, 7))
    return out


class GachaDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = render(Path(cls.tmp.name))
        cls.private = dict(build.PRIVATE)                                    # the files left for the server's private folder

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def test_the_products_are_a_private_file_not_a_public_one(self):
        self.assertFalse((self.out / "tool/gacha/items.json").exists())
        self.assertFalse((self.out / "list/items.json").exists())
        self.assertIn("yorokobu_gacha_db.json", self.private)
        self.assertTrue((self.out / "api/items.php").exists())

    def test_the_data_file_lists_products_per_recipient_and_budget_without_repeats(self):
        data = json.loads(self.private["yorokobu_gacha_db.json"])
        self.assertGreaterEqual(len(data["rec"]), 2)
        for slug, r in data["rec"].items():
            self.assertTrue(r["name"])
            for tier, rows in r["tiers"].items():
                self.assertTrue(rows)
                self.assertLessEqual(len(rows), 12)
                urls = [x[3] for x in rows]
                self.assertEqual(len(urls), len(set(urls)), (slug, tier))
                for name, price, image, url, reviews, rating10 in rows:
                    self.assertTrue(url.startswith("https://hb.afl.rakuten.co.jp/hgc/"))    # the affiliate link as it is (the API's, or the spec's formula for an old record): the page builds nothing
                    self.assertGreater(price, 0)
                    self.assertTrue(image.startswith("https://"))
        self.assertEqual({t["slug"] for t in data["tiers"]}, {t for r in data["rec"].values() for t in r["tiers"]})

    def test_every_product_sits_in_the_budget_it_is_filed_under(self):
        c = content.load(FIX)
        tiers = {t["slug"]: t for t in c["filters"]["tiers"]}
        data = json.loads(self.private["yorokobu_gacha_db.json"])
        for r in data["rec"].values():
            for tier, rows in r["tiers"].items():
                for row in rows:
                    t = tiers[tier]
                    self.assertTrue((t.get("min") is None or row[1] > t["min"]) and (t.get("max") is None or row[1] <= t["max"]), (tier, row[1]))

    def test_the_page_has_the_form_the_notice_the_disclaimer_and_is_linked_from_the_tools_hub(self):
        html = (self.out / "tool/gacha/index.html").read_text(encoding="utf-8")
        for needle in ('id="gacha"', 'data-src="/api/items.php"', 'data-aff="aaaa1111.bbbb2222.cccc3333.dddd4444"', 'name="r"', 'name="o"', 'name="t"', 'name="k"', 'id="gacha-pub"', "3点、提案してもらう",
                       'aria-label="広告を含みます">PR</span>', "価格・在庫は2026年10月7日"):
            self.assertIn(needle, html)
        self.assertIn('href="/tool/gacha/"', (self.out / "tool/index.html").read_text(encoding="utf-8"))
        self.assertIn("/tool/gacha/", (self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual([p for p in sitecheck.check_dir(self.out, CFG["site_url"]) if "gacha" in p], [])

    def test_the_pair_file_keeps_products_per_pair_budget_and_idea_and_the_public_part_only_the_editors_words(self):
        data = json.loads(self.private["yorokobu_gacha_db.json"])
        self.assertTrue(data["pair"])
        for key, v in data["pair"].items():
            self.assertGreaterEqual(len({r[0] for rows in v["tiers"].values() for r in rows}), 2, key)   # three kinds need two ideas at least (a thin band is filled from the near ones by the API)
            for tier, rows in v["tiers"].items():
                self.assertTrue(rows, (key, tier))
                for idea_no, kind, line, price, image, url, reviews, rating10 in rows:
                    self.assertTrue(url.startswith("https://hb.afl.rakuten.co.jp/hgc/"))
                    self.assertTrue(0 <= kind < len(build.TYPE_ORDER))
        html = (self.out / "tool/gacha/index.html").read_text(encoding="utf-8")
        pub = json.loads(re.search(r'<script type="application/json" id="gacha-pub">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(set(pub["pairs"]), set(data["pair"]))
        self.assertTrue({t for v in data["pair"].values() for t in v["tiers"]} <= set(data["order"]))          # the budget bands in their order: the API takes a thin band's help from the nearest ones
        blob = json.dumps(pub, ensure_ascii=False)
        for row in (r for v in data["pair"].values() for rows in v["tiers"].values() for r in rows):
            self.assertNotIn(row[5], blob)                                                      # no product link, price line or picture in the public part
            self.assertNotIn(row[4], blob)
        self.assertNotIn("rakuten.co.jp", blob)

    def test_the_static_page_holds_no_other_mall_link_and_no_product(self):
        html = (self.out / "tool/gacha/index.html").read_text(encoding="utf-8")
        card_part = html.split('id="gacha"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("amazon.co.jp", card_part)
        self.assertNotIn('<li class="item"', card_part)
        self.assertIn('data-amazon="amazonmacs-22"', card_part)                                # the Amazon part is made by the script, in a box of its own


SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    const f = document.createElement('iframe'); f.style.width = '1000px'; f.style.height = '900px'; document.body.appendChild(f);
    await new Promise(r => { f.onload = r; f.src = '/tool/gacha/'; }); await wait(800);
    const d = f.contentDocument, form = d.querySelector('.gacha-form');
    out.recipients = [...form.elements.r.options].map(o => o.value);
    out.occasions = [...form.elements.o.options].map(o => o.value);
    out.before = d.querySelector('.gacha-out').children.length;
    let shown = null;
    for (const t of [...form.elements.t.options].map(o => o.value)) {
      form.elements.t.value = t; form.querySelector('button[type="submit"]').click(); await wait(500);
      const cards = [...d.querySelectorAll('.gacha-card')];
      if (cards.length) {
        shown = {n: cards.length, links: cards.map(c => c.querySelector('.gacha-img a').href), rel: cards[0].querySelector('.gacha-img a').rel,
                 btn: cards.map(c => c.querySelector('.btn > a').href), why: cards.map(c => c.querySelector('.gacha-why').textContent), kinds: cards.map(c => c.querySelector('.gacha-kind').textContent),
                 price: cards[0].querySelector('.price').textContent, names: cards.map(c => (c.querySelector('.gacha-name') || {}).textContent || '')};
        break;
      }
    }
    out.cards = shown;
    out.msg = d.querySelector('.gacha-msg').textContent;
    const amz = [...d.querySelectorAll('.gacha-amazon a')];
    out.amazon = amz.map(a => ({href: a.href, rel: a.rel, text: a.textContent}));
    out.amazonInCards = d.querySelector('.gacha-out').innerHTML.indexOf('amazon.co.jp') >= 0;
    out.amazonPrice = d.querySelector('.gacha-amazon').textContent.indexOf('円') >= 0;
    const again = d.querySelector('.gacha-actions button'); out.again = !!again;
    if (again) { again.click(); await wait(500); out.after = d.querySelectorAll('.gacha-card').length; }
    out.scroll = d.documentElement.scrollWidth;
    // a link from a gift page: the conditions come with the address
    const h = document.createElement('iframe'); h.style.width = '1000px'; h.style.height = '900px'; document.body.appendChild(h);
    const tier = form.elements.t.value;
    await new Promise(r => { h.onload = r; h.src = '/tool/gacha/?o=' + out.occasions[0] + '&r=' + out.recipients[0] + '&t=' + tier; }); await wait(900);
    out.byUrl = h.contentDocument.querySelectorAll('.gacha-card').length;
    // the same on a 300px phone: the cards must not push the page sideways
    const g = document.createElement('iframe'); g.style.width = '300px'; g.style.height = '900px'; document.body.appendChild(g);
    await new Promise(r => { g.onload = r; g.src = '/tool/gacha/'; }); await wait(800);
    const d2 = g.contentDocument, f2 = d2.querySelector('.gacha-form');
    for (const t of [...f2.elements.t.options].map(o => o.value)) { f2.elements.t.value = t; f2.querySelector('button[type="submit"]').click(); await wait(500); if (d2.querySelector('.gacha-card')) break; }
    out.card300 = d2.querySelectorAll('.gacha-card').length; out.scroll300 = d2.documentElement.scrollWidth;
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

        cls.server = items_mock.serve(root)                              # a static server that also answers api/items.php from the build's private files
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

    def test_turning_the_gacha_shows_three_products_with_reasons_and_a_box_of_amazon_and_can_be_turned_again(self):
        o = self.out
        self.assertNotIn("error", o)
        self.assertEqual(o["before"], 0)
        self.assertIsNotNone(o["cards"], o)
        c = o["cards"]
        self.assertGreaterEqual(c["n"], 2)
        self.assertEqual(len(set(c["links"])), c["n"])                                           # different products
        self.assertEqual(len(set(c["kinds"])), c["n"])                                           # of different kinds (ideas)
        for href in c["links"] + c["btn"]:
            self.assertTrue(href.startswith("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/?pc="))
        self.assertIn("sponsored", c["rel"])
        self.assertTrue(c["price"].endswith("円"))
        for why in c["why"]:
            self.assertIn("誕生日に彼氏へ贈るなら、", why)                                             # the reason is the idea's own sentence with this occasion and this person
            self.assertIn("の中から選びました。", why)
        self.assertTrue(o["amazon"])                                                             # a box of its own, search links only
        for a in o["amazon"]:
            self.assertTrue(a["href"].startswith("https://www.amazon.co.jp/s?k="))
            self.assertIn("tag=amazonmacs-22", a["href"])
            self.assertEqual(a["href"].count("&"), 1)                                            # k and tag, nothing else
        self.assertFalse(o["amazonInCards"])
        self.assertFalse(o["amazonPrice"])
        self.assertTrue(o["again"])
        self.assertGreaterEqual(o["after"], 2)
        self.assertGreaterEqual(o["byUrl"], 2)                                                   # the conditions in the address run the proposal at once
        self.assertGreaterEqual(o["card300"], 2)
        self.assertLessEqual(o["scroll300"], 301)


if __name__ == "__main__":
    unittest.main()
