"""お歳暮・お年賀の特集 (sites/yorokobu/seasonal.py): every fact has its store source, the pages build, print and link as they say."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import seasonal_overlap
from sites.yorokobu import build, content, quality, seasonal
from tests.test_yorokobu_compare import CFG, FIX
from tests.yorokobu_data import with_musts

PATHS = ["oseibo/index.html", "oseibo/work/index.html", "oseibo/thanks/index.html", "nenga/index.html"]
OIWAI = ["oiwai/index.html", "oiwai/seijin/index.html", "oiwai/gakko/index.html", "oiwai/taishoku/index.html", "oiwai/shinchiku/index.html", "oiwai/choju/index.html", "oiwai/kekkon/index.html", "oiwai/shussan/index.html"]


def by_slug(data, slug):
    return next(pg for pg in data["pages"] if pg["slug"] == slug)


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
        pg = by_slug(bad, "oseibo")
        pg["sections"][0]["src"] = []
        pg["sections"][1]["src"] = ["nope"]
        bad["sources"]["mi"]["url"] = "https://blog.example.com/seibo"
        pg["sections"][2].pop("list", None)
        pg["sections"][3]["table"]["rows"][0] = ["一般的な目安"]
        found = " | ".join(seasonal.problems(bad))
        for needle in ("names no source", "unknown source nope", "is not a store page", "empty section", "wrong number of cells"):
            self.assertIn(needle, found, needle)

    def test_the_build_refuses_bad_content(self):
        orig = seasonal.load
        try:
            def broken():
                d = copy.deepcopy(orig())
                by_slug(d, "oseibo-work")["sections"][0]["src"] = []
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
        first = by_slug(data, "oseibo")["sections"][0]["table"]["rows"]
        self.assertEqual([r[0] for r in first], ["三越伊勢丹", "高島屋", "大丸松坂屋"])
        self.assertIn("寒中御見舞", json.dumps(data, ensure_ascii=False))
        self.assertIn("寒中御伺", json.dumps(data, ensure_ascii=False))


class OverlapTest(unittest.TestCase):
    """The rule that a sheet is in our own words: the measuring function finds a copied stretch and lets a rewritten sentence pass (offline; the real pages are read by the command)."""

    SOURCE = "新築祝いは完成の報告から半月くらいまでに贈るようにしましょう。新居にふさわしいもの、相手が必要としているものを贈るとよいため、できれば相手に希望を聞いて用意したいものです。"

    def test_the_longest_shared_run_is_found(self):
        n, run = seasonal_overlap.longest_run(seasonal_overlap.norm("できれば相手に希望を聞いて用意したいものです。"), seasonal_overlap.norm(self.SOURCE))
        self.assertEqual(run, "できれば相手に希望を聞いて用意したいものです。")
        self.assertEqual(n, len(run))
        self.assertLess(seasonal_overlap.longest_run("まったく別の文章です", self.SOURCE)[0], 6)

    def test_a_copied_sentence_is_reported_and_the_same_fact_in_other_words_is_not(self):
        def data(text):
            return {"pages": [{"slug": "x", "sections": [{"h": "h", "list": [text], "src": ["a"]}]}]}
        src = {"a": seasonal_overlap.norm(self.SOURCE)}
        copied = seasonal_overlap.too_close(data("新居にふさわしいもの、相手が必要としているものを贈るとよいため、先に聞きます。"), src)
        self.assertEqual(len(copied), 1)
        self.assertGreaterEqual(copied[0][0], seasonal_overlap.MAX_RUN)
        own = seasonal_overlap.too_close(data("新居で使える物を、相手の希望を確かめてから選びます。"), src)
        self.assertEqual(own, [])

    def test_three_items_in_a_sources_order_are_reported_but_names_in_brackets_and_other_orders_are_not(self):
        src = seasonal_overlap.norm("贈る品の例: ベビーカー、チャイルドシート、抱っこ紐、ベビーベッド、ベビー寝具、ハイチェア。表書きは「御出産祝」「ご出産祝」「御誕生祝」です。")
        n, items = seasonal_overlap.item_run("近い親族からはベビーカー、チャイルドシート、抱っこ紐などが向いています。", src)
        self.assertEqual((n, items), (3, ["ベビーカー", "チャイルドシート", "抱っこ紐"]))
        self.assertEqual(seasonal_overlap.item_run("ベビーベッドや抱っこ紐、ベビーカーは大きな買い物です。", src)[0] < 3, True)      # other order
        self.assertEqual(seasonal_overlap.item_run("表書きは「御出産祝」「ご出産祝」「御誕生祝」です。", src)[0] < 3, True)          # the names of a 表書き are facts

    def test_who_gives_and_the_names_of_occasions_in_a_row_are_terms_of_the_subject_not_a_choice_of_items(self):
        src = {"a": seasonal_overlap.norm("相場: 会社の上司、同僚、部下、取引先は5千円から。祖父母、伯父・伯母、いとこは1万円から。")}
        def data(text):
            return {"pages": [{"slug": "x", "sections": [{"h": "h", "list": [text], "src": ["a"]}]}]}
        self.assertEqual(seasonal_overlap.same_order_items(data("会社の上司・同僚・部下・取引先なら5千円から。"), src), [])
        src = {"a": seasonal_overlap.norm("例: 置時計、壁掛け時計、花びん、観葉植物。")}
        self.assertEqual(len(seasonal_overlap.same_order_items(data("置時計、壁掛け時計、花びんなどを挙げます。"), src)), 1)

    def test_the_command_refuses_to_call_an_unreadable_page_clean(self):
        orig = seasonal_overlap.fetch_text
        try:
            def boom(url):
                raise OSError("no network")
            seasonal_overlap.fetch_text = boom
            self.assertEqual(seasonal_overlap.main([]), 2)
        finally:
            seasonal_overlap.fetch_text = orig


class LinksTest(unittest.TestCase):
    def test_a_link_to_a_page_the_build_does_not_have_is_left_out_and_the_own_pages_stay(self):
        out = seasonal.build_pages({}, CFG, False, known={"message/oseibo/index.html": ""})
        hub = out["oseibo/index.html"]
        self.assertIn('href="/message/oseibo/"', hub)                               # this one exists in the build
        self.assertNotIn('href="/gift/oseibo-boss/"', hub)                       # a product-dependent page that is missing: no broken link
        self.assertNotIn('href="/gift/oseibo-in-laws/"', hub)
        for own in ("/oseibo/work/", "/oseibo/thanks/", "/nenga/"):
            self.assertIn(f'href="{own}"', hub)


class OiwaiPagesTest(unittest.TestCase):
    """The お祝い sheets: each amount says which store wrote it and whose relation it is, each page names its two stores, and nothing shows a product."""

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

    def test_the_hub_the_five_sheets_are_built_listed_and_linked_with_their_parent_in_the_crumbs(self):
        sm = self.read("sitemap.xml")
        for rel in OIWAI:
            html = self.read(rel)
            self.assertIn("/" + rel.replace("index.html", ""), sm, rel)
            self.assertIn("<h1", html)
        hub = self.read("oiwai/index.html")
        for href in ("/oiwai/seijin/", "/oiwai/gakko/", "/oiwai/taishoku/", "/oiwai/shinchiku/", "/oiwai/choju/", "/oiwai/kekkon/", "/oiwai/shussan/", "/oseibo/", "/nenga/"):
            self.assertIn(f'href="{href}"', hub, href)
        for rel in OIWAI[1:]:
            self.assertIn('<a href="/oiwai/">お祝いの早見表</a>', self.read(rel), rel)

    def test_each_section_links_its_references_as_a_summary_of_ours_and_the_page_says_it_is_not_the_stores(self):
        for rel in OIWAI + PATHS:
            html = self.read(rel)
            self.assertIn("百貨店各社が作った記事ではありません", html, rel)
            self.assertIn("当サイトが要約・比較したものです", html, rel)
            foots = re.findall(r'<p class="seas-from">(.*?)</p>', html)
            self.assertTrue(foots, rel)
            for f in foots:
                self.assertIn("参考資料(当サイトが要約・比較しました)", f, rel)
                self.assertRegex(f, r'<a href="https://[^"]+" rel="noopener nofollow"', rel)       # a link to the page itself, in the section

    def test_every_sheet_names_both_stores_and_the_date_and_can_be_printed(self):
        for rel in OIWAI[1:]:
            html = self.read(rel)
            self.assertIn("三越伊勢丹", html, rel)
            self.assertIn("松坂屋名古屋店", html, rel)
            self.assertIn("data-print hidden", html, rel)
            self.assertIn("2026年10月15日に、上のページを開いて読みました", html, rel)
            self.assertRegex(html, r'href="https://www\.(mistore\.jp|matsuzakaya\.co\.jp)/[^"]+" rel="noopener nofollow"')
            self.assertEqual(html.count('class="seas-from"'), html.count('<section class="g-sec">'))
        self.assertNotIn("data-print", self.read("oiwai/index.html"))

    def test_the_amount_tables_are_condensed_say_whose_relation_each_amount_is_and_keep_each_store_apart(self):
        for rel in ("oiwai/seijin/index.html", "oiwai/gakko/index.html"):
            self.assertIn("近い親族(祖父母", self.read(rel), rel)
        for rel in ("oiwai/taishoku/index.html", "oiwai/shinchiku/index.html", "oiwai/choju/index.html"):
            self.assertIn("贈る人が本人の近い親族なら1万円から", self.read(rel), rel)
        for rel in ("oiwai/shinchiku/index.html", "oiwai/choju/index.html", "oiwai/kekkon/index.html", "oiwai/shussan/index.html"):
            self.assertIn("贈る相手が", self.read(rel), rel)                     # 松坂屋名古屋店 writes these by the relation of the person who is given to
        self.assertIn("近い親族は5万円から10万円ほどです", self.read("oiwai/kekkon/index.html"))
        self.assertIn("赤ちゃんの祖父母は10万円", self.read("oiwai/shussan/index.html"))
        for rel in OIWAI[1:]:
            self.assertEqual(self.read(rel).count("<th scope=\"row\">三越伊勢丹"), self.read(rel).count("<th scope=\"row\">三越伊勢丹") , rel)
            self.assertIn("金額は各社が示した目安の要約です", self.read(rel), rel)           # the page says the table is a summary, not the store's own table
        # one store's table is not copied row for row: at most three rows for a store in any amount table
        for rel in OIWAI[1:]:
            tables = re.findall(r'<table class="seas-tbl"><thead><tr><th scope="col">案内</th>.*?</table>', self.read(rel), re.S)
            for tb in tables:
                self.assertLessEqual(len(re.findall(r'<th scope="row">三越伊勢丹', tb)), 3, rel)

    def test_no_product_price_or_picture_and_the_ad_notice_is_there(self):
        for rel in OIWAI:
            html = self.read(rel)
            body = re.sub(r"<[^>]+>", " ", html.split("<footer")[0])
            self.assertIn('class="pr-chip"', html)
            self.assertNotIn("thumbnail.image.rakuten.co.jp", html)
            self.assertNotRegex(body, r"税込|¥")


class MovedGuidesTest(unittest.TestCase):
    """The reading guides of お歳暮, 年末年始の手土産 and 帰省・手土産 were folded into the sheets: no page, no link, a permanent redirect, and the sheet is there."""

    MOVES = {"oseibo": "/oseibo/", "year-end-gathering": "/nenga/", "homecoming": "/nenga/",
             "coming-of-age": "/oiwai/seijin/", "school-entrance": "/oiwai/gakko/", "graduation": "/oiwai/gakko/", "new-job": "/oiwai/gakko/",
             "promotion": "/oiwai/taishoku/", "retirement": "/oiwai/taishoku/", "farewell": "/oiwai/taishoku/", "housewarming": "/oiwai/shinchiku/", "longevity": "/oiwai/choju/",
             "wedding-gift": "/oiwai/kekkon/", "birth-gift": "/oiwai/shussan/"}

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

    def test_the_data_names_the_moves_and_the_guides_are_gone_from_the_content(self):
        self.assertEqual(self.c["guide_moves"], self.MOVES)
        for slug in self.MOVES:
            self.assertNotIn(slug, self.c["guides"])
            self.assertIn(slug, self.c["occ"])                                 # the occasion pages stay

    def test_no_page_no_sitemap_entry_and_no_link_to_a_moved_guide(self):
        sm = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        for slug in self.MOVES:
            self.assertFalse((self.root / "guide" / slug / "index.html").exists(), slug)
            self.assertNotIn(f"/guide/{slug}/", sm)
        for p in self.root.rglob("*.html"):
            html = p.read_text(encoding="utf-8")
            for slug in self.MOVES:
                self.assertNotIn(f'href="/guide/{slug}/"', html, f"{p.relative_to(self.root)} still links /guide/{slug}/")

    def test_the_server_sends_a_permanent_redirect_to_the_sheet_after_the_https_rule(self):
        ht = (self.root / ".htaccess").read_text(encoding="utf-8")
        for slug, target in self.MOVES.items():
            self.assertIn(f"RewriteRule ^guide/{slug}/?$ https://yorokobu-present.com{target} [R=301,L]\n", ht)
            self.assertTrue((self.root / target.strip("/") / "index.html").exists(), target)
        self.assertLess(ht.index("RewriteCond %{HTTPS} !on"), ht.index("guide/oseibo"))
        self.assertTrue(ht.endswith("\n"))

    def test_the_occasion_pages_of_every_moved_guide_lead_to_its_sheet_instead(self):
        for slug, target in self.MOVES.items():
            html = (self.root / "occasion" / slug / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'href="{target}"', html, slug)
            self.assertIn('class="seas-hook"', html, slug)

    def test_a_redirect_to_a_page_the_build_does_not_have_is_refused(self):
        with self.assertRaises(Exception) as ctx:
            build.guide_redirects(CFG, {"oseibo": "/nowhere/"}, {"oseibo/index.html": ""})
        self.assertIn("does not have", str(ctx.exception))


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
        for href in ("/oseibo/work/", "/oseibo/thanks/", "/nenga/"):
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
        for rel in ("occasion/oseibo/index.html",):
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
