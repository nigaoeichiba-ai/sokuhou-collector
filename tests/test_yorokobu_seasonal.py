"""お歳暮・お年賀の特集 (sites/yorokobu/seasonal.py): every fact has its store source, the pages build, print and link as they say."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, quality, seasonal
from tests.test_yorokobu_compare import CFG, FIX
from tests.yorokobu_data import with_musts

PATHS = ["oseibo/index.html", "oseibo/work/index.html", "oseibo/thanks/index.html", "nenga/index.html"]


def texts(data):
    for pg in data["pages"]:
        yield pg["lead"]
        for s in pg["sections"]:
            yield from s.get("p", [])
            yield from s.get("list", [])
            yield from s.get("check", [])
            if s.get("note"):
                yield s["note"]
            for r in (s.get("table") or {}).get("rows", []):
                yield from r


class ContentTest(unittest.TestCase):
    def test_the_real_content_passes_its_own_checks(self):
        self.assertEqual(seasonal.problems(seasonal.load()), [])

    def test_the_checks_catch_a_section_without_source_an_unknown_source_a_foreign_host_and_a_ragged_table(self):
        data = seasonal.load()
        bad = copy.deepcopy(data)
        bad["pages"][0]["sections"][0]["src"] = []
        bad["pages"][0]["sections"][1]["src"] = ["nope"]
        bad["sources"]["mi"]["url"] = "https://blog.example.com/seibo"
        bad["pages"][0]["sections"][2].pop("list", None)
        bad["pages"][0]["sections"][3]["table"]["rows"][0] = ["一般的な目安"]
        found = " | ".join(seasonal.problems(bad))
        for needle in ("names no source", "unknown source nope", "is not a store page", "empty section", "wrong number of cells"):
            self.assertIn(needle, found, needle)

    def test_the_build_refuses_bad_content(self):
        orig = seasonal.load
        try:
            def broken():
                d = copy.deepcopy(orig())
                d["pages"][1]["sections"][0]["src"] = []
                return d
            seasonal.load = broken
            with self.assertRaises(ValueError):
                seasonal.build_pages({}, CFG, False)
        finally:
            seasonal.load = orig

    def test_the_words_pass_the_language_gate_and_the_prices_agree_with_the_checked_etiquette_data(self):
        data = seasonal.load()
        for t in texts(data):
            self.assertEqual(quality.language_problems(t, "seasonal"), [], t)
        blob = " ".join(texts(data))
        etq = json.loads((Path(build.__file__).parent / "content" / "etiquette.json").read_text(encoding="utf-8"))
        oseibo = next(o for o in etq["occasions"] if o["slug"] == "oseibo")
        self.assertIn(oseibo["budget"][0]["range"], blob)                  # the amount the site already shows (two sources agreed) is the amount the sheet shows
        self.assertNotRegex(blob, r"必ず|絶対|間違い|失礼になりません")           # custom differs by region and family: no absolute words

    def test_what_the_stores_disagree_on_is_shown_per_store(self):
        data = seasonal.load()
        first = data["pages"][0]["sections"][0]["table"]["rows"]
        self.assertEqual([r[0] for r in first], ["三越伊勢丹", "高島屋", "大丸松坂屋"])
        self.assertIn("寒中御見舞", json.dumps(data, ensure_ascii=False))
        self.assertIn("寒中御伺", json.dumps(data, ensure_ascii=False))


class LinksTest(unittest.TestCase):
    def test_a_link_to_a_page_the_build_does_not_have_is_left_out_and_the_own_pages_stay(self):
        out = seasonal.build_pages({}, CFG, False, known={"guide/oseibo/index.html": ""})
        hub = out["oseibo/index.html"]
        self.assertIn('href="/guide/oseibo/"', hub)                               # this one exists in the build
        self.assertNotIn('href="/gift/oseibo-boss/"', hub)                       # a product-dependent page that is missing: no broken link
        self.assertNotIn('href="/message/oseibo/"', hub)
        for own in ("/oseibo/work/", "/oseibo/thanks/", "/nenga/"):
            self.assertIn(f'href="{own}"', hub)


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 15))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_four_pages_are_built_in_the_sitemap_and_lead_to_each_other(self):
        sm = self.read("sitemap.xml")
        for rel in PATHS:
            html = self.read(rel)
            self.assertIn(f"<h1", html)
            self.assertIn('rel="canonical"', html)
            self.assertIn("/" + rel.replace("index.html", ""), sm, rel)
        hub = self.read("oseibo/index.html")
        for href in ("/oseibo/work/", "/oseibo/thanks/", "/nenga/", "/guide/oseibo/"):
            self.assertIn(f'href="{href}"', hub, href)

    def test_every_page_names_its_store_pages_with_the_date_they_were_read(self):
        for rel in PATHS:
            html = self.read(rel)
            self.assertIn("出典と確認日", html)
            self.assertIn("2026年10月15日に、上のページを開いて読みました", html)
            self.assertRegex(html, r'href="https://www\.(mistore\.jp|takashimaya\.co\.jp|daimaru-matsuzakaya\.jp)/[^"]+" rel="noopener nofollow"')
            self.assertIn("しきたりには諸説があり", html)
            self.assertEqual(html.count('class="seas-from"'), html.count('<section class="g-sec">'))     # every section says where it comes from

    def test_every_table_sits_in_the_scroll_wrapper_the_site_checker_asks_for(self):
        for rel in PATHS:
            html = self.read(rel)
            self.assertEqual(html.count("<table"), html.count('<div class="tablewrap"><table'), rel)

    def test_the_sheets_can_be_printed_and_the_print_button_needs_scripts_so_it_starts_hidden(self):
        for rel in ("oseibo/index.html", "oseibo/work/index.html", "nenga/index.html"):
            html = self.read(rel)
            self.assertIn("data-print hidden", html, rel)
            self.assertIn("/assets/seasonal.js", html, rel)
        self.assertNotIn("data-print", self.read("oseibo/thanks/index.html"))
        self.assertIn("window.print", (self.root / "assets" / "seasonal.js").read_text(encoding="utf-8"))
        css = (self.root / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"@media print \{ \.seas-more, \.seas-hook, \.seas-print \{ display: none")
        self.assertIn('class="checklist"', self.read("oseibo/work/index.html"))

    def test_the_o_seibo_pages_of_the_site_lead_to_the_sheets_and_other_occasions_do_not(self):
        for rel in ("occasion/oseibo/index.html", "guide/oseibo/index.html"):
            self.assertIn('class="seas-hook"', self.read(rel), rel)
            self.assertIn('href="/oseibo/work/"', self.read(rel), rel)
        for slug in ("birthday", "ochugen"):
            p = self.root / "occasion" / slug / "index.html"
            if p.exists():
                self.assertNotIn("seas-hook", p.read_text(encoding="utf-8"), slug)

    def test_the_pages_show_no_product_price_or_picture_and_carry_the_ad_notice(self):
        for rel in PATHS:
            html = self.read(rel)
            body = re.sub(r"<[^>]+>", " ", html.split("<footer")[0])
            self.assertIn('class="pr-chip"', html)
            self.assertNotIn("thumbnail.image.rakuten.co.jp", html)
            self.assertNotIn("m.media-amazon.com", html)
            self.assertNotRegex(body, r"税込|¥")
            self.assertRegex(html, r'class="btn" href="https://hb\.afl\.rakuten\.co\.jp/hgc/AFF\.ID/trk[^"]*" rel="sponsored nofollow noopener"')


if __name__ == "__main__":
    unittest.main()
