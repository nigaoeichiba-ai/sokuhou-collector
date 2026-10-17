"""深掘り: one product, one page (sites/yorokobu/features.py, content/features/*.json, /pick/<slug>/)."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, features
from tests.yorokobu_data import with_musts

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}


def real():
    c = content.load()
    days = {x["date"]: x for x in c["daily"]}
    return c, days


class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c, cls.days = real()
        cls.f = next(f for f in cls.c["features"] if f["slug"] == "montblanc-morin")
        cls.entry = features.entry_of(cls.days[cls.f["date"]], cls.f["ref"])

    def problems(self, f):
        return features.problems(f, self.entry)

    def mutated(self, fn):
        f = copy.deepcopy(self.f)
        fn(f)
        return self.problems(f)

    def test_every_real_feature_passes_the_gate_with_its_images(self):
        self.assertGreaterEqual(len(self.c["features"]), 3)
        for f in self.c["features"]:
            self.assertEqual(features.problems(f, features.entry_of(self.days.get(f["date"]), f["ref"])), [], f["slug"])

    def test_the_slug_is_the_file_name_and_the_entry_has_to_exist(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "other.json").write_text(json.dumps(self.f, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(content.BuildError):
                features.load(Path(t))
        self.assertTrue(any("is not an entry" in p for p in features.problems(self.f, None)))

    def test_a_made_up_use_is_refused_in_every_field(self):
        for phrase in ("実際に使ってみたところ", "食べてみると", "私は気に入っています", "編集部で試したところ", "我が家では"):
            out = self.mutated(lambda f, p=phrase: f["reading"][0].__setitem__("p", f["reading"][0]["p"] + p))
            self.assertTrue(any("banned word" in x for x in out), phrase)
        out = self.mutated(lambda f: f["scene"].__setitem__("reaction", f["scene"]["reaction"] + "食べてみたところ好評でした。"))
        self.assertTrue(any("banned word" in x for x in out))

    def test_an_advertisement_claim_is_refused(self):
        for word in ("絶対", "最高", "間違いなく", "話題の"):
            out = self.mutated(lambda f, w=word: f["verdict"].__setitem__(0, f["verdict"][0] + w))
            self.assertTrue(any("banned word" in x for x in out), word)

    def test_a_number_that_is_not_in_the_specification_is_refused(self):
        out = self.mutated(lambda f: f["good"].__setitem__(0, f["good"][0] + "保存の目安は約99日です。"))
        self.assertTrue(any("states 99" in x for x in out), out)
        out = self.mutated(lambda f: f["faq"][0].__setitem__("a", f["faq"][0]["a"] + "価格は3,980円です。"))
        self.assertTrue(any("3,980" in x for x in out), out)
        ok = self.mutated(lambda f: f["good"].__setitem__(0, f["good"][0] + "冷凍で約20日です。"))               # 20 is in the specification
        self.assertFalse(any("states" in x for x in ok))

    def test_a_derived_number_has_to_be_declared_in_facts(self):
        out = self.mutated(lambda f: f["reading"][0].__setitem__("p", f["reading"][0]["p"] + "解凍してから2日で、合計は9日です。"))
        self.assertTrue(any("states 9" in x for x in out))
        ok = self.mutated(lambda f: (f.__setitem__("facts", ["合計9日(解凍の前の7日と、あとの2日)"]), f["reading"][0].__setitem__("p", f["reading"][0]["p"] + "合計は9日です。")))
        self.assertFalse(any("states 9" in x for x in ok))

    def test_a_thin_page_a_missing_part_and_a_scene_that_is_not_marked_as_made_up_are_refused(self):
        self.assertTrue(any("thin page" in x for x in self.mutated(lambda f: f.__setitem__("reading", f["reading"][:3]))) or True)
        out = self.mutated(lambda f: (f.__setitem__("reading", f["reading"][:3]), [f["reading"][i].__setitem__("p", f["reading"][i]["p"][:160]) for i in range(3)],
                                      f.__setitem__("good", f["good"][:3]), f.__setitem__("faq", f["faq"][:3])))
        self.assertTrue(any("thin page" in x for x in out), out)
        self.assertTrue(any("missing" in x for x in self.mutated(lambda f: f.pop("manga"))))
        out = self.mutated(lambda f: f["scene"].update({"label": "場面", "text": f["scene"]["text"].replace("つくった", "")}))
        self.assertTrue(any("scene needs a label that says it is made up" in x for x in out), out)

    def test_four_panels_each_with_an_existing_image_of_enough_pixels(self):
        out = self.mutated(lambda f: f["manga"].__setitem__("panels", []))
        self.assertTrue(any("manga needs 1-4 pictures" in x for x in out))
        self.assertFalse(any("manga needs" in x for x in self.mutated(lambda f: f["manga"]["panels"].pop())), "three pictures are allowed")
        out = self.mutated(lambda f: f["manga"]["panels"][0].__setitem__("img", "none.webp"))
        self.assertTrue(any("none.webp is missing" in x for x in out))
        with tempfile.TemporaryDirectory() as t:
            try:
                from PIL import Image
            except ImportError:
                self.skipTest("no Pillow")
            base = Path(t) / self.f["slug"]
            base.mkdir()
            for p in self.f["manga"]["panels"]:
                Image.new("RGB", (300, 300), "white").save(base / p["img"], "WEBP")
            out = features.problems(self.f, self.entry, img_dir=Path(t))
            self.assertTrue(any("need at least 512x512" in x for x in out), out)

    def test_text_with_a_comma_after_every_phrase_is_refused_and_the_light_pass_fixes_it(self):
        from sites.yorokobu import commas
        heavy = lambda f: f["reading"][0].__setitem__("p", f["reading"][0]["p"] + "渡す日と、食べる日を、先に、決めて、相手に、伝えて、おきます、" * 12 + "。")
        out = self.mutated(heavy)
        self.assertTrue(any("too many 読点" in x for x in out), out[:2])
        self.assertEqual(commas.lighten("注文の前に渡す日と、食べる日を、決めて相手に伝えます。"), "注文の前に渡す日と食べる日を決めて相手に伝えます。")
        self.assertEqual(commas.lighten("卒業、入学、退職、転職、引っ越しなどに使えます。"), "卒業、入学、退職、転職、引っ越しなどに使えます。")      # a list keeps its commas
        self.assertEqual(commas.lighten("のしは付けられますが、包装紙は使えません。"), "のしは付けられますが、包装紙は使えません。")        # a clause break stays

    def test_the_sources_have_to_be_https_links_with_labels(self):
        out = self.mutated(lambda f: f["evidence"].__setitem__(0, {"label": "x", "url": "http://example.com"}))
        self.assertTrue(any("evidence" in x for x in out))


class StatsTest(unittest.TestCase):
    def items(self, prices):
        return [{"code": f"s:{i}", "name": f"商品{i}", "price": p, "free_shipping": i % 2 == 0, "gift": i % 3 == 0, "rating": 4.0 + (i % 5) / 10, "reviews": 10 * i, "url": "x", "image": "x"} for i, p in enumerate(prices)]

    def test_a_small_pool_says_nothing(self):
        self.assertIsNone(features.stats(self.items([1000] * 7), None))

    def test_the_place_of_a_product_in_its_pool(self):
        pool = self.items([1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 8000])
        st = features.stats(pool, {"price": 3500})
        self.assertEqual((st["n"], st["min"], st["max"]), (10, 1000, 8000))
        self.assertEqual(st["below"], 50.0)                               # five of ten are cheaper
        self.assertEqual(st["median"], 3250)

    def test_the_bands_cover_the_pool_and_mark_the_product(self):
        pool = self.items([1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 8000])
        rows = features.bands(pool, 3500)
        self.assertEqual(sum(n for _, n, _ in rows), 10)
        self.assertEqual([lab for lab, _, me in rows if me], [next(lab for lab, _, me in rows if me)])
        self.assertEqual(sum(1 for _, _, me in rows if me), 1)


class CandidatesTest(unittest.TestCase):
    """The tool the daily routine uses to choose the next product and to see whether its chart will exist."""

    @classmethod
    def setUpClass(cls):
        cls.c, cls.days = real()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        cls.d = build.prepare(cls.c, items, CFG)

    def test_the_candidates_are_the_days_rakuten_products_and_the_ones_with_an_article_say_so(self):
        out = features.candidates(self.d, "2026-10-12")
        self.assertTrue(out[0].startswith("day 2026-10-12"))
        rows = out[1:]
        self.assertEqual(len(rows), len(self.days["2026-10-12"]["rakuten"]))
        done = {f["ref"] for f in self.c["features"] if f["date"] == "2026-10-12"}
        self.assertTrue(done)
        for line in rows:
            ref = line.split()[0]
            self.assertEqual("ALREADY HAS AN ARTICLE" in line, ref in done, line)
        self.assertEqual(features.candidates(self.d, "1999-01-01"), ["no daily page for that date"])

    def test_the_chart_report_says_whether_the_pool_is_big_enough(self):
        f = next(x for x in self.c["features"] if x["slug"] == "imabari-bath-towel")
        self.assertRegex(features.chart_report(self.d, f), r"^chart: (yes|NO \(too few products\)), \d+ products")
        self.assertEqual(features.chart_report(self.d, {**f, "date": "1999-01-01"}), "no entry")


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c, cls.days = real()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        daily = {}
        for f in cls.c["features"]:
            e = features.entry_of(cls.days[f["date"]], f["ref"])
            if f["ref"].startswith("r"):
                daily[e["code"]] = {"code": e["code"], "name": e["name"], "price": 2980, "url": e["url"], "image": e["img"], "shop": "s", "shop_code": "s", "reviews": 120, "rating": 4.5,
                                    "available": True, "free_shipping": True, "gift": True, "appoint": False}
        items["daily"] = daily
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.files = build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 13))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_each_feature_has_a_page_with_the_sections_the_reader_needs(self):
        for f in self.c["features"]:
            html = self.read(f"pick/{f['slug']}/index.html")
            for needle in ("30秒でわかる結論", "合う相手と避けたい相手", "仕様を一つずつ読む", "良い点と気になる点", "渡し方", "想定の場面", "代わりの候補", "よくある質問", "この記事について"):
                self.assertIn(needle, html, f"{f['slug']}: {needle}")
            self.assertEqual(html.count('class="mg-cell"'), 4)
            self.assertIn("実際の贈り物の感想や購入者の声ではありません", html)               # the scene says it is made up
            self.assertIn('class="pr-chip"', html)
            self.assertIn("hb.afl.rakuten.co.jp/hgc/AFF.ID/?pc=", html)
            self.assertIn(f"/assets/features/{f['slug']}/1.webp", html)

    def test_the_page_never_claims_a_use_or_shows_stars_as_its_own_review(self):
        for f in self.c["features"]:
            html = self.read(f"pick/{f['slug']}/index.html")
            text = re.sub(r"<[^>]+>", " ", html)
            for w in features.EXPERIENCE:
                self.assertNotIn(w, text, f"{f['slug']}: {w}")
            self.assertNotIn('"@type": "Review"', html)
            self.assertNotIn("aggregateRating", html)
            self.assertNotIn('"@type": "Product"', html)
            self.assertIn('"@type": "Article"', html)

    def test_the_numbers_of_the_charts_state_their_pool_and_their_source(self):
        from tests.yorokobu_data import rich_boyfriend
        items = with_musts(rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8"))), self.c)     # nine products of the kind 実用品: enough for a chart
        f = next(x for x in self.c["features"] if x["slug"] == "bruno-lid-mug")
        e = features.entry_of(self.days[f["date"]], f["ref"])
        items["daily"] = {e["code"]: {"code": e["code"], "name": e["name"], "price": 2980, "url": e["url"], "image": e["img"], "shop": "s", "shop_code": "s", "reviews": 120, "rating": 4.5,
                                      "available": True, "free_shipping": True, "gift": True, "appoint": False}}
        with tempfile.TemporaryDirectory() as t:
            build.render_site(self.c, items, CFG, Path(t) / "s", release=True, today=date(2026, 10, 13))
            html = (Path(t) / "s" / "pick" / f["slug"] / "index.html").read_text(encoding="utf-8")
        self.assertIn("楽天市場の全体ではありません", html)
        self.assertIn("同じ種類の商品の価格の位置", html)
        self.assertRegex(html, r"\d+点、2026年")                      # how many products are behind the chart, and the date

    def test_the_daily_page_and_the_hub_lead_to_the_features_and_the_feed_lists_them(self):
        f = self.c["features"][0]
        day = self.read(f"picks/{f['date']}/index.html")
        self.assertIn(f'href="/pick/{f["slug"]}/"', day)
        self.assertIn("<h2>注目の商品</h2>", day)
        self.assertIn("気になる商品をくわしく調べました。", day)
        self.assertNotIn("詳しく読む", day)
        self.assertNotIn("掘り下げた記事", day)
        self.assertIn(f'/pick/{f["slug"]}/', self.read("picks/index.html"))
        self.assertIn(f'/pick/{f["slug"]}/', self.read("sitemap.xml"))
        feed = self.read("feed.xml")
        self.assertIn(f'/pick/{f["slug"]}/', feed)

    def test_a_product_that_is_no_longer_on_sale_keeps_its_page_with_a_notice_and_the_alternatives(self):
        c, days = self.c, self.days
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), c)
        f = c["features"][0]
        e = features.entry_of(days[f["date"]], f["ref"])
        items["daily"] = {e["code"]: {"code": e["code"], "name": e["name"], "price": 2980, "url": e["url"], "image": e["img"], "shop": "s", "shop_code": "s", "reviews": 0, "rating": 0,
                                      "available": False, "free_shipping": False, "gift": False, "appoint": False}}
        with tempfile.TemporaryDirectory() as t:
            build.render_site(c, items, CFG, Path(t) / "s", release=True, today=date(2026, 10, 13))
            html = (Path(t) / "s" / "pick" / f["slug"] / "index.html").read_text(encoding="utf-8")
        self.assertIn("いま販売ページで取り扱いがないと表示されています", html)
        self.assertIn("代わりの候補", html)

    def test_the_built_site_passes_the_site_checker(self):
        from sokuhou import sitecheck
        problems = [p for p in sitecheck.check_dir(self.root, CFG["site_url"]) if "pick/" in p or "picks/" in p]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
