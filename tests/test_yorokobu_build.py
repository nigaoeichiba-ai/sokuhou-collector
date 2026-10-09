import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from sokuhou.sitekit import BuildError

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}
TODAY = date(2026, 5, 3)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_page_set(self):
        for rel in ("index.html", "occasion/index.html", "for/index.html", "occasion/birthday/index.html", "for/mother/index.html",
                    "gift/birthday-boyfriend/index.html", "gift/birthday-mother/index.html", "gift/mothers-day-mother/index.html",
                    "about/index.html", "privacy/index.html", "contact/index.html", "404.html", "sitemap.xml", "robots.txt", ".htaccess"):
            self.assertIn(rel, self.files)

    def test_products_link_through_the_affiliate_id_and_are_marked(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=", html)
        self.assertIn('rel="sponsored nofollow noopener"', html)
        self.assertIn("楽天市場で見る", html)
        self.assertIn('<span class="pr-chip">PR</span>広告を含みます', html)          # a short label before any product link ...
        self.assertLess(html.index('class="pr-chip"'), html.index('class="item"'))
        self.assertIn("リンク先で購入されると、運営者に報酬が支払われることがあります", html)    # ... and the full notice in the footer
        self.assertGreater(html.index('class="pr-foot"'), html.index('class="item"'))
        self.assertIn("amazon.co.jp/s?k=", html)
        self.assertIn("Amazonのアソシエイトとして", html)

    def test_event_and_recipient_pages_offer_an_amazon_search_with_the_notice(self):
        for rel in ("occasion/birthday/index.html", "for/mother/index.html"):
            html = self.read(rel)
            self.assertIn("amazon.co.jp/s?k=", html, rel)
            self.assertIn("tag=amazonmacs-22", html, rel)
            self.assertIn("Amazonのアソシエイトとして", html, rel)
            self.assertIn("Amazonアソシエイト", html, rel)                       # the PR notice names Amazon because the page has the link
        with tempfile.TemporaryDirectory() as tmp:                                  # no tracking ID: no Amazon link and no mention
            out = Path(tmp) / "s"
            build.render_site(self.c, self.items, {**CFG, "amazon_tracking_id": None}, out, release=True, today=TODAY)
            html = (out / "occasion/birthday/index.html").read_text(encoding="utf-8")
            self.assertNotIn("amazon", html.lower())

    def test_rakuten_rules_for_displaying_prices(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn("価格・在庫は2026年10月7日 7:00時点の情報です", html)
        self.assertIn("このサイトで掲載されている情報は、よろこぶプレゼントの作成者により運営されています。", html)
        self.assertIn("購入時に楽天市場店舗(www.rakuten.co.jp)に表示されている価格が、その商品の販売に適用されます。", html)
        self.assertIn("Supported by Rakuten Developers", self.read("index.html"))

    def test_the_sommelier_proposes_kinds_of_gift_with_a_reason_and_a_search_link(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn("ソムリエの提案", html)
        for text in ("毎日使う財布", "名入れの小物", "毎日使う小物は、使うたびに思い出してもらえます。"):
            self.assertIn(text, html)
        self.assertIn("楽天市場で「誕生日 彼氏 財布」をもっと見る", html)
        self.assertIn("search.rakuten.co.jp%2Fsearch%2Fmall%2F", html)

    def test_filters_sorting_and_the_concierge_are_on_the_page(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        for needle in ('id="browse"', "data-sort", "data-ship", 'data-filter="tier"', 'data-filter="type"', 'class="kw-form"', 'data-trk="yorokobu"'):
            self.assertIn(needle, html)
        self.assertIn('data-tier="under3000"', html)
        self.assertIn('data-tier="3000-5000"', html)

    def test_products_for_the_wrong_person_are_not_shown(self):
        mother = self.read("gift/birthday-mother/index.html")
        self.assertIn("テスト商品b1", mother)
        self.assertNotIn("メンズ", mother.split('<ul class="items grid-all">')[1])   # a men's wallet never appears on a mother's page
        self.assertNotIn("本革 メンズ 長財布", mother)

    def test_own_shop_appears_only_as_a_plain_labelled_card_where_it_fits(self):
        bf = self.read("gift/birthday-boyfriend/index.html")
        self.assertNotIn("運営者のショップ", bf)                       # birthday x boyfriend has no portrait_note
        mother = self.read("gift/birthday-mother/index.html")
        self.assertIn("運営者のショップ", mother)
        self.assertIn("https://item.rakuten.co.jp/2gaoe/p1/", mother)
        self.assertNotIn("hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=https%3A%2F%2Fitem.rakuten.co.jp%2F2gaoe", mother)
        self.assertIn("手描きの似顔絵ギフト(誕生日に)", mother)
        self.assertNotIn("運営者のショップ", self.read("gift/mothers-day-mother/index.html"))   # no portrait_note there

    def test_the_top_page_finder_has_no_pre_selection_and_knows_which_pages_exist(self):
        html = self.read("index.html")
        self.assertIn('<option value="">イベント</option>', html)
        self.assertIn('<option value="">贈る相手</option>', html)
        self.assertNotIn("selected", html.split('class="finder"')[1].split("</form>")[0])
        m = re.search(r'data-map="([^"]+)"', html)
        fmap = json.loads(m.group(1).replace("&quot;", '"'))
        self.assertEqual(sorted(fmap["birthday"]), ["boyfriend", "mother"])
        self.assertEqual(fmap["birthday"]["boyfriend"], ["under3000", "3000-5000"])  # only budgets that have products

    def test_season_block_follows_the_build_date(self):
        self.assertIn("母の日", self.read("index.html").split('class="tiles wide">')[1].split("</ul>")[0])
        out = Path(self.tmp.name) / "winter"
        build.render_site(self.c, self.items, CFG, out, release=True, today=date(2026, 8, 1))
        block = (out / "index.html").read_text(encoding="utf-8").split('class="tiles wide">')[1].split("</ul>")[0]
        self.assertNotIn("母の日", block)  # fixtures have no occasion in season in August: falls back to the evergreen ones
        self.assertIn("誕生日", block)

    def test_every_internal_link_and_asset_resolves(self):
        bad = []
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            html = self.read(rel)
            for href in re.findall(r'(?:href|src)="(/[^"#?]*)', html):
                target = href.lstrip("/")
                if href.endswith("/"):
                    target += "index.html"
                if target and target not in self.files and not (self.out / target).exists():
                    bad.append((rel, href))
        self.assertEqual(bad, [])

    def test_names_are_shortened_and_escaped(self):
        self.assertEqual(build.short("x" * 100, 10), "x" * 9 + "…")
        self.assertEqual(build.short("  a   b  "), "a b")

    def test_every_page_has_its_own_share_card_and_share_buttons(self):
        from sites.yorokobu import ogimage
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn("https://line.me/R/share?text=", html)
        self.assertIn("https://twitter.com/intent/tweet?text=", html)
        self.assertIn("yorokobu-present.com%2Fgift%2Fbirthday-boyfriend%2F", html)       # our page URL, never an affiliate link
        self.assertNotIn("hb.afl.rakuten", html.split('class="share"')[1].split("</div>")[0])
        if ogimage.available():
            self.assertIn("og/gift/birthday-boyfriend.png", self.files)
            self.assertIn("https://yorokobu-present.com/og/gift/birthday-boyfriend.png", html)
            self.assertTrue((self.out / "og/gift/birthday-boyfriend.png").read_bytes().startswith(b"\x89PNG"))
            self.assertIn("/og/default.png", self.read("index.html"))

    def test_memo_and_calendar_pages_and_the_feed(self):
        for rel in ("memo/index.html", "calendar/index.html", "calendar/yorokobu-gift-days.ics"):
            self.assertIn(rel, self.files)
        memo = self.read("memo/index.html")
        for needle in ('id="memo-app"', 'name="rec"', 'name="occ"', 'name="date"', "この端末のブラウザだけに保存され、送信されません"):
            self.assertIn(needle, memo)
        cal = self.read("calendar/index.html")
        self.assertIn("webcal://yorokobu-present.com/calendar/yorokobu-gift-days.ics", cal)
        self.assertIn("2026年", cal)
        self.assertIn("BEGIN:VCALENDAR", self.read("calendar/yorokobu-gift-days.ics"))
        self.assertIn("/memo/?o=birthday&amp;r=boyfriend", self.read("gift/birthday-boyfriend/index.html"))
        self.assertIn('id="memo-strip"', self.read("index.html"))

    def test_every_product_gets_a_facts_only_note(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn('class="pick-note"', html)
        self.assertIn("レビューがいちばん多い一品です(平均4.5・200件)", html)       # a2 has the most reviews on this page
        self.assertNotIn("売れ筋", html)
        self.assertNotIn("人気No", html)

    def test_the_site_can_be_added_to_the_home_screen(self):
        m = json.loads(self.read("manifest.webmanifest"))
        self.assertEqual((m["display"], m["scope"], m["lang"]), ("standalone", "/", "ja"))
        self.assertTrue(all((self.out / i["src"].lstrip("/")).exists() for i in m["icons"]))
        self.assertIn('rel="manifest" href="/manifest.webmanifest"', self.read("index.html"))
        self.assertIn('name="theme-color"', self.read("memo/index.html"))

    def test_reading_guides_are_calm_extras_with_a_faq_and_links_from_the_pages(self):
        self.assertIn("guide/birthday/index.html", self.files)
        g = self.read("guide/birthday/index.html")
        for needle in ("届く日から逆算する", 'class="checklist"', '"@type": "FAQPage"', "/occasion/birthday/", "/gift/birthday-boyfriend/"):
            self.assertIn(needle, g)
        self.assertIn("/guide/birthday/", self.read("occasion/birthday/index.html"))
        self.assertIn("/guide/birthday/", self.read("gift/birthday-boyfriend/index.html"))
        self.assertNotIn("/guide/", self.read("gift/mothers-day-mother/index.html"))      # no guide for that occasion in the fixture

    def test_site_files(self):
        self.assertIn("Sitemap: https://yorokobu-present.com/sitemap.xml", self.read("robots.txt"))
        self.assertIn("楽天ウェブサービス", self.read("about/index.html"))
        self.assertIn("運営者は、楽天市場で、似顔絵のショップも運営", self.read("about/index.html"))


class ReleaseGateTest(unittest.TestCase):
    def test_release_needs_fetched_products_and_operator_info(self):
        c = content.load(FIX)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BuildError):
                build.render_site(c, None, CFG, Path(tmp) / "a", release=True, today=TODAY)
            with self.assertRaises(BuildError):
                build.render_site(c, {"pairs": {"x": {}}}, {**CFG, "operator_name": ""}, Path(tmp) / "b", release=True, today=TODAY)
            files = build.render_site(c, None, CFG, Path(tmp) / "c", release=False, today=TODAY)  # a preview build works without products
            self.assertIn("index.html", files)


class ContentValidationTest(unittest.TestCase):
    def test_unknown_slug_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for f in FIX.glob("*.json"):
                (tmp / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            pairs = json.loads((tmp / "pairs.json").read_text(encoding="utf-8"))
            pairs["pairs"][0]["recipient"] = "nobody"
            (tmp / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(tmp)


if __name__ == "__main__":
    unittest.main()


class NameCleanupTest(unittest.TestCase):
    def tearDown(self):
        build.set_keep()

    def test_other_occasions_are_dropped_and_the_pages_own_is_kept(self):
        raw = "＼楽天スーパーSALE／ 敬老の日 ミニブーケ 誕生日 プレゼント 花 父の日 ハロウィン"
        build.set_keep("誕生日")
        shown = build.short(raw)
        self.assertIn("誕生日", shown)
        self.assertNotIn("敬老の日", shown)
        self.assertNotIn("ハロウィン", shown)
        self.assertNotIn("＼", shown)
        build.set_keep()
        self.assertNotIn("誕生日", build.short(raw))

    def test_extra_occasion_words_and_shop_promotions_are_dropped(self):
        build.set_keep("昇進祝い")
        shown = build.short("卒業記念品 名入れ 1個から 父 プレゼント 昇進祝い 夫 メンズ ボールペン")
        self.assertIn("昇進祝い", shown)
        self.assertNotIn("卒業記念品", shown)
        build.set_keep()
        shown = build.short("楽天ランキング1位獲得！ マラソン期間中 ジャンル祭対象 ごまクッキー 18個入 詰め合わせ")
        for w in ("楽天ランキング", "マラソン", "ジャンル祭"):
            self.assertNotIn(w, shown)
        self.assertIn("ごまクッキー", shown)

    def test_a_shorter_word_does_not_cut_the_pages_own_word(self):
        build.set_keep("卒業祝い")
        self.assertIn("卒業祝い", build.short("卒業祝い 名入れ ボールペン 卒業記念品 ギフト 男性 女性"))

    def test_a_title_that_would_shrink_to_nothing_stays_as_it_is(self):
        self.assertEqual(build.short("敬老の日 画像送信サービス"), "敬老の日 画像送信サービス")


class FooterNoticeTest(unittest.TestCase):
    def test_amazon_is_named_only_where_a_page_has_an_amazon_link(self):
        cfg = {**CFG, "amazon_tracking_id": "amazonmacs-22"}
        self.assertNotIn("Amazon", build.pr_foot(cfg))
        self.assertIn("Amazonアソシエイト", build.pr_foot(cfg, amazon=True))
        page = build.page(cfg, False, path="/x/", title="t", description="d", body='<p class="pr-quiet">PR</p><a href="https://www.amazon.co.jp/s?k=a&tag=amazonmacs-22">a</a>')
        self.assertIn("Amazonアソシエイト", page)
        page = build.page(cfg, False, path="/y/", title="t", description="d", body='<p class="pr-quiet">PR</p>')
        self.assertNotIn("Amazonアソシエイト", page)

    def test_no_coming_of_age_page_for_children(self):
        from sites.yorokobu import content as real
        keys = {real.pair_key(p) for p in real.load()["pairs"]}
        self.assertNotIn("coming-of-age-child", keys)
        self.assertNotIn("coming-of-age-teen", keys)


class ThemeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_theme_pages_and_hub_are_built(self):
        self.assertEqual([t["key"] for t in self.c["themes"]], ["theme-thanks-daily", "theme-beauty"])
        hub = (self.out / "theme" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/theme/beauty/"', hub)
        self.assertIn("気持ちから選ぶ", hub)
        page = (self.out / "theme" / "beauty" / "index.html").read_text(encoding="utf-8")
        self.assertIn("美容に興味がある人へのプレゼント", page)
        self.assertIn("ソムリエの提案", page)
        self.assertIn('class="item"', page)
        self.assertIn("楽天市場で「フェイスローラー ギフト」をもっと見る", page)
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("/theme/thanks-daily/", sitemap)

    def test_home_and_nav_lead_to_the_themes(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/theme/"', home)
        self.assertIn("気持ち・興味から", home)

    def test_a_theme_without_a_recipient_still_filters_memorial_and_adult_goods(self):
        from sites.yorokobu.picking import usable
        it = {"available": True, "reviews": 50, "rating": 4.5, "price": 2000, "name": "お供え 線香 ギフト"}
        self.assertFalse(usable(it, self.c["filters"], None))
        self.assertTrue(usable({**it, "name": "ハンドタオル ギフト"}, self.c["filters"], None))

    def test_bad_theme_references_fail_the_build(self):
        import copy
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            for f in FIX.glob("*.json"):
                shutil.copy(f, Path(tmp) / f.name)
            data = json.loads((Path(tmp) / "themes.json").read_text(encoding="utf-8"))
            data["themes"][0]["group"] = "nope"
            (Path(tmp) / "themes.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(Path(tmp))
