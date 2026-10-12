"""The sale calendar and the banner (sites/yorokobu/sales.py, assets/sale.js)."""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sites.yorokobu import build, content, sales
from tests.test_yorokobu_e2e import CHROME, run_chrome

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}
JST = sales.JST


def at(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=JST)


def ev(**kw) -> dict:
    base = {"id": "x", "store": "rakuten", "name": "お買い物マラソン", "start": "2026-10-14T20:00:00+09:00", "end": "2026-10-17T09:59:00+09:00",
            "url": "https://event.rakuten.co.jp/campaign/point-up/marathon/", "note": "n", "source": "https://event.rakuten.co.jp/campaign/point-up/marathon/", "verified": "2026-10-12"}
    base.update(kw)
    return base


def write(tmp: Path, events: list[dict]) -> Path:
    p = tmp / "sales.json"
    p.write_text(json.dumps({"events": events}, ensure_ascii=False), encoding="utf-8")
    return p


class CalendarTest(unittest.TestCase):
    def test_the_real_calendar_loads_and_every_event_names_the_page_its_dates_were_read_on(self):
        events = sales.load()
        self.assertGreaterEqual(len(events), 3)
        for e in events:
            self.assertTrue(e["source"].startswith("https://"))
            self.assertRegex(e["verified"], r"^\d{4}-\d\d-\d\d$")

    def test_a_wrong_file_stops_the_build(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            for bad, why in ((ev(url="https://example.com/sale"), "own page"), (ev(store="amazon"), "own page"), (ev(source=""), "missing"), (ev(start="2026-10-14T20:00:00"), "offset"),
                             (ev(end="2026-10-14T19:00:00+09:00"), "before"), (ev(store="x"), "store"), (ev(entry_start="2026-10-15T10:00:00+09:00"), "entry")):
                with self.assertRaises(sales.SalesError, msg=why):
                    sales.load(write(tmp, [bad]))
            with self.assertRaises(sales.SalesError):
                sales.load(write(tmp, [ev(), ev()]))                       # the same id twice
            self.assertEqual(sales.load(tmp / "none.json"), [])           # no file: no sales

    def test_phases_follow_the_clock(self):
        e = ev(entry_start="2026-10-12T10:00:00+09:00")
        cases = {"2026-10-11T12:00": "soon", "2026-10-12T09:00": "soon", "2026-10-12T10:00": "entry", "2026-10-14T19:59": "entry", "2026-10-14T20:00": "live",
                 "2026-10-17T09:59": "live", "2026-10-17T10:00": None, "2026-09-10T12:00": None, "2026-09-20T12:00": "ahead", "2026-09-30T12:00": "soon"}
        for now, want in cases.items():
            self.assertEqual(sales.phase(e, at(now)), want, now)

    def test_the_sentences_say_what_the_shop_announced_and_nothing_more(self):
        e = ev(entry_start="2026-10-12T10:00:00+09:00", after="ポイントアップにはエントリーが必要です。")
        live = sales.message(e, at("2026-10-15T12:00"))
        self.assertEqual(live["tag"], "開催中")
        self.assertIn("10月17日(土)9時59分まで", live["text"])
        self.assertIn("今がおすすめ", live["text"])
        soon = sales.message(ev(), at("2026-10-13T12:00"))
        self.assertEqual(soon["tag"], "あす")
        self.assertIn("10月14日(水)20時から楽天市場のお買い物マラソン", soon["text"])
        self.assertIn("それまでに贈り物を選んでおくと", soon["text"])
        for m in (live, soon, sales.message(ev(), at("2026-09-20T12:00"))):
            for banned in ("%", "最安", "半額", "絶対", "今だけ", "!"):
                self.assertNotIn(banned, m["text"])
        self.assertIsNone(sales.message(ev(), at("2026-10-18T00:00")))      # over: nothing

    def test_at_most_one_event_per_shop_and_the_one_on_now_comes_first(self):
        events = [ev(id="a1", store="amazon", name="先行セール", start="2026-10-13T00:00:00+09:00", end="2026-10-15T23:59:00+09:00", url="https://www.amazon.co.jp/primeappreciation"),
                  ev(id="a2", store="amazon", name="本番", start="2026-10-16T00:00:00+09:00", end="2026-10-19T23:59:00+09:00", url="https://www.amazon.co.jp/primeappreciation"),
                  ev(id="r1")]
        got = [e["id"] for e, m in sales.choose(events, at("2026-10-14T12:00"))]
        self.assertEqual(got, ["a1", "r1"])                                   # Amazon's pre-sale is on, Rakuten's marathon is next
        got = [e["id"] for e, m in sales.choose(events, at("2026-10-15T12:00"))]
        self.assertEqual(got, ["a1", "r1"])                                   # both on now: the one that ends first comes first
        got = [e["id"] for e, m in sales.choose(events, at("2026-10-16T12:00"))]
        self.assertEqual(got, ["r1", "a2"])                                   # the pre-sale is over: the main sale is the Amazon one
        self.assertEqual(sales.choose(events, at("2026-12-30T12:00")), [])


@unittest.skipUnless(CHROME, "Chrome is not installed")
class ScriptParityTest(unittest.TestCase):
    def test_the_script_says_the_same_sentences_as_the_build_at_every_moment(self):
        events = [ev(id="r", entry_start="2026-10-12T10:00:00+09:00", after="ポイントアップにはエントリーが必要です。"),
                  ev(id="a1", store="amazon", name="プライム感謝祭の先行セール", start="2026-10-13T00:00:00+09:00", end="2026-10-15T23:59:00+09:00", url="https://www.amazon.co.jp/primeappreciation",
                     after="Amazonプライム会員が対象です。"),
                  ev(id="a2", store="amazon", name="プライム感謝祭", start="2026-10-16T00:00:00+09:00", end="2026-10-19T23:59:00+09:00", url="https://www.amazon.co.jp/primeappreciation")]
        href = {e["id"]: f"https://example.com/{e['id']}" for e in events}
        moments = []
        t = at("2026-09-01T00:00")
        while t < at("2026-10-21T00:00"):
            moments.append(t)
            t += timedelta(hours=7, minutes=13)
        moments += [at("2026-10-14T19:59"), at("2026-10-14T20:00"), at("2026-10-17T09:59"), at("2026-10-17T10:00"), at("2026-10-12T09:59"), at("2026-10-12T10:00"), at("2026-10-12T23:59"), at("2026-10-13T00:00")]
        js = (Path(build.__file__).parent / "assets" / "sale.js").read_text(encoding="utf-8")
        data = sales.js_data(events, href)
        script = (f"<!doctype html><meta charset='utf-8'><pre id='out'></pre><script>{js}</script><script>"
                  f"var ev = {data}; var ms = {json.dumps([int(m.timestamp() * 1000) for m in moments])};"
                  "document.getElementById('out').textContent = JSON.stringify(ms.map(function (m) { return YorokobuSale.choose(ev, m).map(function (x) { return [x.e.id, x.m.phase, x.m.tag, x.m.short, x.m.text, x.m.cta]; }); }));"
                  "</script>")
        tmp = Path(tempfile.mkdtemp(prefix="sale_parity_"))
        try:
            (tmp / "p.html").write_text(script, encoding="utf-8")
            dom = run_chrome((tmp / "p.html").as_uri())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        import html as _h
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        self.assertTrue(m, dom[:300])
        got = json.loads(_h.unescape(m.group(1)))
        self.assertEqual(len(got), len(moments))
        shown = 0
        for now, row in zip(moments, got):
            want = [[e["id"], x["phase"], x["tag"], x["short"], x["text"], x["cta"]] for e, x in sales.choose(events, now)]
            self.assertEqual(row, want, now.isoformat())
            shown += bool(want)
        self.assertGreater(shown, 20)                                           # the comparison covered moments with a bar, not only empty ones


@unittest.skipUnless(CHROME, "Chrome is not installed")
class BarBehaviourTest(unittest.TestCase):
    def run_page(self, now: datetime, steps: str, before: str = "") -> dict:
        events = [ev(id="r", entry_start="2026-10-12T10:00:00+09:00"),
                  ev(id="a", store="amazon", name="プライム感謝祭", start="2026-10-16T00:00:00+09:00", end="2026-10-19T23:59:00+09:00", url="https://www.amazon.co.jp/primeappreciation")]
        href = {e["id"]: f"https://example.com/{e['id']}" for e in events}
        built = sales.bar(events, at("2026-10-12T12:00"), href)                    # the bar as the build made it, hours or days before the visit
        js = (Path(build.__file__).parent / "assets" / "sale.js").read_text(encoding="utf-8")
        page = (f"<!doctype html><meta charset='utf-8'><script>Date.now = function () {{ return {int(now.timestamp() * 1000)}; }}; {before}</script>{built}<pre id='out'></pre><script>{js}</script>"
                f"<script>document.addEventListener('DOMContentLoaded', function () {{ var out = {{}}; var bar = document.getElementById('sale-bar'); {steps}; document.getElementById('out').textContent = JSON.stringify(out); }});</script>")
        tmp = Path(tempfile.mkdtemp(prefix="sale_bar_"))
        try:
            (tmp / "p.html").write_text(page, encoding="utf-8")
            dom = run_chrome((tmp / "p.html").as_uri())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        import html as _h
        m = re.search(r"<pre id=.out.>(.*?)</pre>", dom, re.S)
        self.assertTrue(m, dom[:300])
        return json.loads(_h.unescape(m.group(1)))

    def test_a_bar_built_days_ago_says_what_is_true_at_the_visit_and_can_be_closed_for_the_day(self):
        o = self.run_page(at("2026-10-15T12:00"), "out.items = [].map.call(bar.querySelectorAll('.sale-tag'), function (e) { return e.textContent; });"
                          "out.hidden = bar.hidden; out.close = !!bar.querySelector('.sale-close');"
                          "bar.querySelector('.sale-close').click(); out.after_close = bar.hidden; out.stored = Object.keys(JSON.parse(localStorage.getItem('yorokobu.sale.closed'))).sort();")
        self.assertEqual(o["items"], ["開催中", "あす"])                       # the build said "soon" for Rakuten and "4 days" for Amazon; at the visit the marathon is on and Amazon's is tomorrow
        self.assertFalse(o["hidden"])
        self.assertTrue(o["close"])
        self.assertTrue(o["after_close"])
        self.assertEqual(o["stored"], ["a:soon", "r:live"])

    def test_links_of_the_bar_go_only_to_the_shops_hosts(self):
        o = self.run_page(at("2026-10-13T12:00"), "out.safe = [YorokobuSale.safe('javascript:alert(1)'), YorokobuSale.safe('https://evil.example.com/'), YorokobuSale.safe('https://www.amazon.co.jp/primeappreciation?tag=x'), YorokobuSale.safe('https://hb.afl.rakuten.co.jp/hgc/a')]")
        self.assertEqual(o["safe"], ["", "", "https://www.amazon.co.jp/primeappreciation?tag=x", "https://hb.afl.rakuten.co.jp/hgc/a"])

    def test_a_sale_lasts_to_the_end_of_its_last_minute(self):
        real = [e for e in sales.load() if e["id"] == "rakuten-marathon-2026-10"][0]
        self.assertEqual(sales.phase(real, at("2026-10-17T09:59")), "live")
        self.assertEqual(sales.phase(real, datetime.fromisoformat("2026-10-17T09:59:30+09:00")), "live")        # 9:59:30 is still 9時59分
        self.assertIsNone(sales.phase(real, at("2026-10-17T10:00")))

    def test_a_bar_whose_events_are_all_over_hides_itself_and_a_closed_one_stays_closed(self):
        o = self.run_page(at("2026-10-25T12:00"), "out.hidden = bar.hidden")
        self.assertTrue(o["hidden"])
        o = self.run_page(at("2026-10-13T12:00"), "out.hidden = bar.hidden", before="localStorage.setItem('yorokobu.sale.closed', JSON.stringify({'r:entry': Date.now() + 1000, 'a:soon': Date.now() + 1000}));")
        self.assertTrue(o["hidden"])                    # both shown lines were closed (the same phase, not over): the bar stays closed
        o = self.run_page(at("2026-10-13T12:00"), "out.hidden = bar.hidden", before="localStorage.setItem('yorokobu.sale.closed', JSON.stringify({'r:entry': Date.now() - 1000, 'a:soon': Date.now() - 1000}));")
        self.assertFalse(o["hidden"])                   # a day later it comes back


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.files = build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 10, 12))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_pages_with_a_pr_label_have_the_bar_with_affiliate_links_and_the_others_do_not(self):
        home = self.read("index.html")
        self.assertIn('id="sale-bar"', home)
        self.assertIn('src="/assets/sale.js"', home)
        bar = re.search(r'<aside class="sale-bar".*?</aside>', home, re.S).group(0)
        self.assertIn("hb.afl.rakuten.co.jp/hgc/AFF.ID/trk", bar)
        self.assertIn("https://www.amazon.co.jp/primeappreciation?tag=test-22", bar)
        self.assertIn('class="pr-chip"', bar)
        self.assertIn("Amazonのアソシエイトとして", home)                      # the page that carries an Amazon link has the Associates sentence
        self.assertNotIn("sale-bar", self.read("about/index.html"))
        self.assertNotIn("sale-bar", self.read("privacy/index.html"))

    def test_a_gift_page_ends_with_next_steps_and_offers_the_sale_only_while_one_is_on_or_near(self):
        gift = self.read("gift/birthday-mother/index.html")
        self.assertIn("迷ったときの、次の一歩", gift)
        self.assertIn('href="/favorites/"', gift)
        self.assertIn('href="/memo/?o=birthday&amp;r=mother"', gift)
        self.assertIn("セールの日に、合わせて買う", gift)
        self.assertIn("迷ったときの、次の一歩", self.read("picks/2026-10-11/index.html") if (self.root / "picks").exists() else "迷ったときの、次の一歩")
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "s"
            build.render_site(content.load(FIX), items, CFG, out, release=True, today=date(2026, 5, 3))
            far = (out / "gift" / "birthday-mother" / "index.html").read_text(encoding="utf-8")
            self.assertIn("迷ったときの、次の一歩", far)
            self.assertNotIn("セールの日に、合わせて買う", far)

    def test_the_sale_page_lists_the_announced_events_with_their_source_date_and_is_in_the_sitemap(self):
        html = self.read("sale/index.html")
        for text in ("お買い物マラソン", "プライム感謝祭", "確認日 2026-10-12", "10月14日(水)20時 から 10月17日(土)9時59分 まで", "エントリー"):
            self.assertIn(text, html)
        self.assertIn("/sale/", self.read("sitemap.xml"))
        self.assertNotIn("sale-bar", html)

    def test_without_events_there_is_no_bar_and_no_page_and_a_far_off_event_shows_no_bar_but_keeps_the_page(self):
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "s"
            build.render_site(content.load(FIX), items, CFG, out, release=True, today=date(2026, 5, 3))     # five months before: nothing is near
            self.assertNotIn("sale-bar", (out / "index.html").read_text(encoding="utf-8"))
            self.assertTrue((out / "sale" / "index.html").exists())
            html = (out / "sale" / "index.html").read_text(encoding="utf-8")
            self.assertIn("開催予定", html)
            out2 = Path(t) / "s2"
            build.render_site(content.load(FIX), items, CFG, out2, release=True, today=date(2026, 11, 2))   # all of them are over: the page stays and says so
            html2 = (out2 / "sale" / "index.html").read_text(encoding="utf-8")
            self.assertIn("いま発表されているセールはありません", html2)
            self.assertNotIn("sale-bar", (out2 / "index.html").read_text(encoding="utf-8"))

    def test_no_amazon_link_without_an_associates_id(self):
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "s"
            build.render_site(content.load(FIX), items, {**CFG, "amazon_tracking_id": None}, out, release=True, today=date(2026, 10, 12))
            home = (out / "index.html").read_text(encoding="utf-8")
            bar = re.search(r'<aside class="sale-bar".*?</aside>', home, re.S).group(0)
            self.assertNotIn("amazon.co.jp", bar)
            self.assertIn("お買い物マラソン", bar)


class PointsTest(unittest.TestCase):
    def render(self, today: date, n_points: int) -> Path:
        from tests.yorokobu_data import rich_boyfriend
        items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        seen = 0
        for idea in items["pairs"]["birthday-boyfriend"]["ideas"]:
            for it in idea["items"]:
                if seen < n_points:
                    it["point_rate"], it["point_end"] = 5, "2026-10-17 09:59"
                    seen += 1
        tmp = tempfile.mkdtemp(prefix="points_")
        self.addCleanup(shutil.rmtree, tmp, True)
        build.render_site(content.load(FIX), items, CFG, Path(tmp) / "s", release=True, today=today)
        return Path(tmp) / "s"

    def test_a_multiplier_the_shop_announced_shows_on_the_cards_and_in_a_list_on_the_sale_page(self):
        out = self.render(date(2026, 10, 15), 6)
        sale = (out / "sale" / "index.html").read_text(encoding="utf-8")
        self.assertIn("いま、ポイント倍率が付いている贈り物", sale)
        self.assertIn("ポイント5倍(10月17日まで)", sale)
        self.assertIn("楽天市場が倍率と終了の日時を表示しているもの", sale)
        gift = (out / "gift" / "birthday-boyfriend" / "index.html").read_text(encoding="utf-8")
        self.assertIn("ポイント5倍(10月17日まで)", gift)

    def test_an_ended_multiplier_and_a_short_list_say_nothing_on_the_sale_page(self):
        out = self.render(date(2026, 10, 18), 6)                                  # the end was 10-17 9:59
        self.assertNotIn("ポイント倍率", (out / "sale" / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("ポイント5倍", (out / "gift" / "birthday-boyfriend" / "index.html").read_text(encoding="utf-8"))
        out = self.render(date(2026, 10, 15), 3)                                  # three are not a list: the badges stay, the section does not
        self.assertNotIn("いま、ポイント倍率が付いている贈り物", (out / "sale" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("ポイント5倍(10月17日まで)", (out / "gift" / "birthday-boyfriend" / "index.html").read_text(encoding="utf-8"))

    def test_the_api_fields_become_a_multiplier_only_with_a_rate_of_two_or_more_and_an_end(self):
        from sokuhou import rakuten
        base = {"itemName": "ギフト タオル セット 箱入り", "itemUrl": "https://item.rakuten.co.jp/s/x/", "itemPrice": 2500, "mediumImageUrls": [{"imageUrl": "https://thumbnail.image.rakuten.co.jp/a.jpg"}], "itemCode": "s:1"}
        self.assertNotIn("point_rate", rakuten.normalize(base))
        self.assertNotIn("point_rate", rakuten.normalize({**base, "pointRate": 1, "pointRateEndTime": "2026-10-17 09:59"}))
        self.assertNotIn("point_rate", rakuten.normalize({**base, "pointRate": 5}))
        got = rakuten.normalize({**base, "pointRate": 5, "pointRateEndTime": "2026-10-17 09:59"})
        self.assertEqual((got["point_rate"], got["point_end"]), (5, "2026-10-17 09:59"))


if __name__ == "__main__":
    unittest.main()
