"""お気に入り, 最近チェックした商品 and the count of pressed products (assets/mine.js, sites/yorokobu/minepage.py, the pop counters of api/ask.php)."""
import functools
import html as html_lib
import http.server
import json
import re
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from tests import items_mock
from sites.yorokobu import build, content, minepage
from tests import ask_mock
from tests.test_yorokobu_e2e import CHROME, run_chrome

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}


def product(code, n=1):
    return {"code": code, "name": f"商品{code}", "price": 2000, "url": f"https://item.rakuten.co.jp/s/{code}/", "image": "https://thumbnail.image.rakuten.co.jp/x.jpg", "shop": "s",
            "shop_code": f"s{n}", "reviews": 10, "rating": 4.5, "available": True, "free_shipping": True, "gift": False, "appoint": False}


class RankingTest(unittest.TestCase):
    PRODUCTS = {c: product(c, i) for i, c in enumerate(("a:1", "b:2", "c:3", "d:4", "e:5"))}

    def stats(self, **counts):
        return {"total": {f"pop.r.{k.replace('_', ':')}": v for k, v in counts.items()}}

    def test_too_few_presses_say_nothing(self):
        self.assertEqual(minepage.ranking(self.stats(a_1=20, b_2=9, c_3=5, d_4=3), self.PRODUCTS), [])            # 37 in all
        self.assertEqual(minepage.ranking(self.stats(a_1=58, b_2=2), self.PRODUCTS), [])                         # many presses, but of one product
        self.assertEqual(minepage.ranking({}, self.PRODUCTS), [])

    def test_enough_presses_rank_the_products_that_are_still_on_the_site(self):
        got = minepage.ranking(self.stats(a_1=20, b_2=18, c_3=9, d_4=5, e_5=2, gone_9=40), self.PRODUCTS)
        self.assertEqual([p["code"] for p in got], ["a:1", "b:2", "c:3", "d:4"])          # e has 2 (below the line), the product gone from the site is left out

    def test_the_block_says_what_the_number_is(self):
        d = {"pairs": {}, "popstats": {}}
        self.assertEqual(minepage.section(d, CFG, {}), "")
        self.assertIn("購入された数や、品質を表すものではありません", minepage.COUNT_PRIVACY + "購入された数や、品質を表すものではありません")


class CounterKeyTest(unittest.TestCase):
    def test_the_server_twin_accepts_product_keys_and_nothing_else(self):
        for good in ("pop.r.chashoan:10002052", "pop.a.B0FC23Y4T6", "dock.occ.birthday"):
            self.assertTrue(ask_mock.STAT.match(good), good)
        for bad in ("pop.x.abc", "pop.r.", "pop.r.a b", "pop.r.../etc", "pop.r.<script>", "ask.q1.home", "pop.r." + "a" * 70, "POP.r.abc"):
            self.assertFalse(ask_mock.STAT.match(bad), bad)

    def test_the_php_receiver_and_the_stats_merge_use_the_same_rule(self):
        php = (Path(build.__file__).parent / "ask_receiver.php.tpl").read_text(encoding="utf-8")
        self.assertIn(r"pop\.[ra]\.[A-Za-z0-9._:-]{3,64}", php)
        from sites.yorokobu import askstats
        self.assertTrue(askstats.KEY.match("pop.r.chashoan:10002052"))
        self.assertFalse(askstats.KEY.match("pop.r.a b"))


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.files = build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_every_page_loads_mine_js_and_the_footer_links_to_the_favourites(self):
        for rel in ("index.html", "gift/birthday-boyfriend/index.html", "ranking/index.html" if "ranking/index.html" in self.files else "index.html"):
            self.assertIn('src="/assets/mine.js"', self.read(rel), rel)
        self.assertIn('href="/favorites/"', self.read("index.html"))

    def test_the_favourites_page_is_noindex_and_not_in_the_sitemap(self):
        html = self.read("favorites/index.html")
        self.assertIn('content="noindex,follow"', html)
        self.assertIn('id="myitems"', html)
        self.assertIn('data-src="/api/items.php"', html)
        self.assertNotIn("/favorites/", self.read("sitemap.xml"))

    def test_the_privacy_page_says_what_is_counted(self):
        html = self.read("privacy/index.html")
        self.assertIn("商品のボタンが押された回数", html)
        self.assertIn("IPアドレス、時刻は記録しません", html)
        self.assertIn("トラッキングしない", html)


@unittest.skipUnless(CHROME, "Chrome is not installed")
class BrowserTest(unittest.TestCase):
    SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '1000px'; f.style.height = '800px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(400); return f;
}
(async () => {
  try {
    let f = await load('/gift/birthday-boyfriend/'); let d = f.contentDocument, w = f.contentWindow;
    w.localStorage.clear();
    const calls = []; w.fetch = (u, o) => { calls.push([u, o && o.body]); return Promise.resolve({}); };
    const a = d.querySelector('li.item[data-code] .btn > a');
    const code = a.closest('li.item').getAttribute('data-code');
    out.code = code;
    out.pressed = w.YorokobuMine.press(a);
    w.YorokobuMine.press(a);                                   // the same product on the same day: counted once
    out.calls = calls.map(c => c[1]);
    out.recent = JSON.parse(w.localStorage.getItem('yorokobu.recent')).map(x => x.code);
    // a script-made click is not a person's press
    const calls2 = calls.length; a.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true })); out.scripted_added = calls.length - calls2;
    // do not track: nothing is counted (the recent list still is)
    w.localStorage.removeItem('yorokobu.pop');
    Object.defineProperty(w.navigator, 'doNotTrack', { value: '1', configurable: true });
    const n3 = calls.length; w.YorokobuMine.press(a); out.dnt_added = calls.length - n3;
    // links that come from a data file go only to the shops' hosts
    out.safe = ['javascript:alert(1)', 'https://evil.example.com/x', 'https://hb.afl.rakuten.co.jp/hgc/x', 'http://www.amazon.co.jp/s?k=a', 'https://www.amazon.co.jp/s?k=a', 'data:text/html,x'].map(u => w.YorokobuMine.safeUrl(u));
    // Do Not Track in the other spellings
    for (const v of ['yes']) {
      w.localStorage.removeItem('yorokobu.pop');
      Object.defineProperty(w.navigator, 'doNotTrack', { value: v, configurable: true });
      const n4 = calls.length; w.YorokobuMine.press(a); out['dnt_' + v] = calls.length - n4;
    }
    Object.defineProperty(w.navigator, 'doNotTrack', { value: null, configurable: true });
    // without localStorage the once-a-day rule still holds inside the page
    const n5 = calls.length;
    const realSet = w.Storage.prototype.setItem; w.Storage.prototype.setItem = function () { throw new Error('private window'); };
    w.localStorage.removeItem('yorokobu.pop');
    const other = d.querySelectorAll('li.item[data-code]')[1].querySelector('.btn > a'); w.YorokobuMine.press(other); w.YorokobuMine.press(other);
    out.nostorage_calls = calls.length - n5; w.Storage.prototype.setItem = realSet;
    // the header heart
    w.localStorage.setItem('yorokobu.favs', JSON.stringify([{ code: code, name: 'x', price: '1' }]));
    out.fav_link_before = !!d.querySelector('header.site .fav-link');
    // the favourites page draws the saved and the recent products from items.json
    w.localStorage.setItem('yorokobu.recent', JSON.stringify([{ id: 'r:' + code, code: code, name: 'n', price: '1', t: 1 }, { id: 'r:nonexistent:1', code: 'nonexistent:1', name: '消えた商品', price: '1200', t: 2 }]));
    f = await load('/favorites/'); d = f.contentDocument; w = f.contentWindow;
    out.fav_cards = d.querySelectorAll('#my-favs li.item').length;
    out.fav_has_buttons = d.querySelectorAll('#my-favs .btn > a[rel~="sponsored"]').length;
    out.recent_cards = d.querySelectorAll('#my-recent li.item').length;
    out.card_imgs = [...d.querySelectorAll('#my-favs li.item img, #my-recent li.item img')].map(i => i.getAttribute('src'));
    out.safe_img = ['https://thumbnail.image.rakuten.co.jp/@0_mall/s/a.jpg?_ex=300x300', 'https://image.rakuten.co.jp/s/a.jpg', 'http://thumbnail.image.rakuten.co.jp/a.jpg', 'https://m.media-amazon.com/images/I/a.jpg', 'https://evil.example.com/a.jpg', 'javascript:alert(1)'].map(u => w.YorokobuMine.safeImg(u));
    out.empty_hidden = d.querySelector('#my-favs-empty').hidden;
    out.fav_n = d.querySelector('#my-favs-n').textContent;
    out.header_link = (d.querySelector('header.site .fav-link') || {}).textContent;
    d.querySelector('.fav-rm').click();
    out.after_remove = d.querySelectorAll('#my-favs li.item').length;
    out.empty_shown = !d.querySelector('#my-favs-empty').hidden;
    d.querySelector('#my-recent-clear').click();
    out.recent_after_clear = JSON.parse(w.localStorage.getItem('yorokobu.recent')).length;
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        raw = (FIX / "items.json").read_text(encoding="utf-8")
        items = json.loads(re.sub(r'"code": "([^"]+)"', lambda m: '"code": "t:' + m.group(1) + '"', raw))              # item codes as Rakuten writes them ("shop:number")
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))
        (cls.root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{cls.SCENARIO}</script>', encoding="utf-8")
        cls.server = items_mock.serve(cls.root)                          # a static server that also answers api/items.php from the build's private files
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        cls.out = json.loads(html_lib.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_no_script_error(self):
        self.assertNotIn("error", self.out)

    def test_a_press_is_remembered_and_counted_once_a_day_as_one_counter_key(self):
        o = self.out
        self.assertTrue(o["pressed"])
        self.assertEqual(len(o["calls"]), 1)
        body = json.loads(o["calls"][0])
        self.assertEqual(body, {"v": 1, "op": "stat", "k": [f"pop.r.{o['code']}"]})       # the counter key and nothing else: no name, no id, no time
        self.assertEqual(o["recent"], [o["code"]])

    def test_a_scripted_click_and_do_not_track_count_nothing(self):
        self.assertEqual(self.out["scripted_added"], 0)
        self.assertEqual(self.out["dnt_added"], 0)
        self.assertEqual(self.out["dnt_yes"], 0)                            # the older spelling of the setting counts too

    def test_links_from_a_data_file_are_drawn_only_when_they_go_to_a_shop_and_the_daily_rule_holds_without_storage(self):
        self.assertEqual(self.out["safe"], ["", "", "https://hb.afl.rakuten.co.jp/hgc/x", "", "https://www.amazon.co.jp/s?k=a", ""])
        self.assertEqual(self.out["nostorage_calls"], 1)                    # pressed twice in a private window: counted once

    def test_the_favourites_page_shows_saved_and_recent_products_and_what_is_gone(self):
        o = self.out
        self.assertEqual(o["fav_cards"], 1)
        self.assertGreaterEqual(o["fav_has_buttons"], 1)
        self.assertGreaterEqual(len(o["card_imgs"]), 2)           # a saved and a recent product: each card shows its Rakuten picture (a card without one showed only its alt text)
        self.assertTrue(all(x.startswith("https://thumbnail.image.rakuten.co.jp/") for x in o["card_imgs"]), o["card_imgs"])
        self.assertEqual(o["safe_img"], ["https://thumbnail.image.rakuten.co.jp/@0_mall/s/a.jpg?_ex=300x300", "https://image.rakuten.co.jp/s/a.jpg", "", "", "", ""])   # Rakuten's picture hosts only, over https; never an Amazon picture
        self.assertEqual(o["recent_cards"], 1)                    # the one that is still on the site (the other one has no picture or price to show)
        self.assertTrue(o["empty_hidden"])
        self.assertEqual(o["fav_n"], "1")
        self.assertIn("お気に入り", o["header_link"])
        self.assertEqual(o["after_remove"], 0)
        self.assertTrue(o["empty_shown"])
        self.assertEqual(o["recent_after_clear"], 0)


if __name__ == "__main__":
    unittest.main()
