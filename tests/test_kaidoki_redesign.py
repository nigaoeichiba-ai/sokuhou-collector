"""sale-calendar.com redesign (SALEカレンダー, Muse's template kit 2026-11-12): built beside the current site, switched by KAIDOKI_REDESIGN=1 / config "redesign": true.

What is pinned here: the current build is unchanged when the switch is off; the new build has no old name, one h1 per page, no relative link left from the kit, the affiliate boxes of
the current site (one box per mall page, text and tag as before), no promise sentence, a hero headline that comes from hero.json by time, sale tiles from facts.py with no date for an
unannounced sale, noindex while demo=true and none when it is switched, a product page only when its private data is there, and no mall product data in the repository."""
from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")

from sites.kaidoki import gen  # noqa: E402
from sites.kaidoki.redesign import render  # noqa: E402
from sokuhou import newsite  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kaidoki"
AFF_BOX = re.compile(r'<aside class="aff-box">.*?</aside>', re.S)
PR_LINK = re.compile(r'<a href="[^"]+" target="_blank" rel="nofollow sponsored noopener">.*?</a>', re.S)
PROMISE = re.compile(r"その日のうちに|発表されたら.{0,12}足します|発表の日に.{0,12}足します|毎日つくり直|更新は、主催者が発表した日に行います")

FIXTURE = {"slug": "test-phone", "title": "テスト機のお得情報", "kicker": "スマートフォン", "h1_html": "テスト機<br><span class=\"gold\">4店</span>", "sub": "価格は出さない。",
           "meta": "確認日：2026年11月9日", "lead": "テスト機は発売済みです。並び順は固定です。", "stores_burst": "4店", "stores_h2": "ストア別", "note": "確認できなかった店は行を作っていません。",
           "calc_big": "結局いくら", "calc_text": "価格は出しません。", "howto_h2": "調べ方", "howto": ["載せるもの。", "載せないもの。"], "checked": "2026-11-09", "category": "electronics", "crumb": "スマートフォン",
           "stores": [{"name": "店A", "tag": "固定順 1", "icon": "🏬", "headline": {"pre": "最大", "big": "15%", "post": "OFF", "note": "条件あり"}, "rows": [["割引", "表示なし"]], "checked": "2026年11月9日", "links": [["公式ページ", "https://example.com/a"]]},
                      {"name": "店B", "tag": "固定順 2", "headline": {"text": "一律の割引表示なし"}, "rows": [["割引", "表示なし"]], "checked": "2026年11月9日", "links": []}],
           "fit": {"h2": "向き・不向き", "suits": ["ポイントを重視する人は、店Aです。"], "not_suits": ["急ぐ人には向きません。"]}}


def build(env: dict, products=None):
    """The site's pages under the given environment (and, when given, with these product files instead of the private folder)."""
    with mock.patch.dict(os.environ, env, clear=False):
        gen.write()
        if products is None:
            return newsite.build_pages(SITE, release=True)[0]
        with mock.patch.object(render, "load_products", return_value=products):
            return newsite.build_pages(SITE, release=True)[0]


class RedesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = build({"KAIDOKI_REDESIGN": "0"})
        cls.demo = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "1", "KAIDOKI_NOW": "2026-11-12T10:00"}, products=[FIXTURE])
        cls.live = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "0", "KAIDOKI_NOW": "2026-11-12T10:00"}, products=[FIXTURE])

    @staticmethod
    def html(pages):
        return {k: v for k, v in pages.items() if isinstance(v, str) and k.endswith(".html") and v.startswith("<!doctype")}      # (not the Search Console verification file)

    def test_switch_off_leaves_the_current_site_as_it_was(self):
        self.assertIn('<header class="fvh">', self.old["index.html"])
        self.assertFalse([k for k in self.old if k.startswith("assets/kit/")])
        self.assertNotIn("SALEカレンダー", self.old["index.html"])

    def test_no_old_name_in_any_page_and_the_new_name_everywhere(self):
        for rel, h in self.html(self.live).items():
            self.assertNotIn("買い時カレンダー", h, rel)
            self.assertIn("SALEカレンダー", h, rel)

    def test_no_title_carries_the_site_name_twice(self):
        for rel, h in self.html(self.live).items():
            title = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
            self.assertLessEqual(title.count("SALEカレンダー"), 1, f"{rel}: {title}")

    def test_the_title_check_catches_a_doubled_name(self):      # negative: the old behaviour (suffix always added) is detected
        doubled = "SALEカレンダー|セールの日程 | SALEカレンダー"
        self.assertGreater(doubled.count("SALEカレンダー"), 1)

    def test_one_h1_no_relative_leftovers_every_page_has_the_kit_layout(self):
        for rel, h in self.html(self.live).items():
            self.assertEqual(h.count("<h1"), 1, rel)
            self.assertNotRegex(h, r'(?:href|src)="(?!https?:|/|#|mailto:)', rel)
            self.assertIn('/assets/kit/styles/site.css', h, rel)
            self.assertNotIn("/assets/style.css", h, rel)

    def test_demo_is_noindex_and_the_switch_removes_it(self):
        for rel, h in self.html(self.demo).items():
            self.assertRegex(h, r'<meta name="robots" content="noindex', rel)
            self.assertIn("公開前の確認用ページ", h, rel)
        live = self.html(self.live)
        noindex = [rel for rel, h in live.items() if 'content="noindex' in h]
        self.assertEqual(sorted(noindex), ["contact/thanks.html", "corrections/index.html"])      # the form's thanks page and the archive page: noindex as before
        self.assertTrue(all("公開前の確認用ページ" not in h for h in live.values()))
        self.assertIn("<loc>https://sale-calendar.com/calendar/</loc>", self.live["sitemap.xml"])

    def test_the_switch_refuses_an_unreviewed_public_build(self):
        s = render._json(render.HERE / "site.json")
        with mock.patch.object(render, "settings", return_value=dict(s, demo=False, publication_reviewed=False)):
            with self.assertRaises(ValueError):
                render.apply({}, [], {"site_url": "https://sale-calendar.com"}, {}, SITE)

    def test_affiliate_boxes_are_the_current_ones(self):
        from sites.kaidoki import hooks
        cfg = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
        h = self.html(self.live)
        boxes = {rel: AFF_BOX.findall(t) for rel, t in h.items() if AFF_BOX.search(t)}
        self.assertTrue(set(hooks.AFF_LINKS) | set(hooks.AFF_LINKS_MULTI) <= set(boxes))          # the pages with their own place for it keep it; other pages that name a mall get the fallback box (add_missing_mall_links)
        for rel, bx in boxes.items():
            own = rel in hooks.AFF_LINKS or rel in hooks.AFF_LINKS_MULTI
            self.assertLessEqual(len(bx), 2 if own else 1, rel)          # the page's own box first; a second one only for another mall the page names (add_missing_mall_links)
            if not own:
                self.assertRegex(bx[0], r"nofollow sponsored noopener", rel)          # a fallback box: PR, sponsored, one line per mall
                continue
            if rel in hooks.AFF_LINKS_MULTI:
                self.assertEqual(bx[0], hooks.affiliate_multi_block(hooks.AFF_LINKS_MULTI[rel], dict(cfg, site_name="SALEカレンダー")).strip(), rel)
                continue
            mall, target, label = hooks.AFF_LINKS[rel]
            self.assertEqual(bx[0], hooks.affiliate_block(mall, target, label, dict(cfg, site_name="SALEカレンダー")).strip(), rel)      # the text is the same sentence as the current site's
            self.assertEqual(len(re.findall(r'href="', bx[0])), 1, rel)
            if mall == "rakuten":
                self.assertNotRegex(bx[0], r"amazon|yahoo|valuecommerce")

    def test_every_card_has_a_sentence(self):
        for rel, h in self.html(self.live).items():
            for a in re.findall(r'<div class="article-links">(.*?)</div>', h, re.S):
                for card in re.findall(r"<article>.*?</article>", a, re.S):
                    self.assertIn("<p>", card, rel)      # sitecheck reads a heading with nothing under it as a defect

    def test_no_promise_sentences(self):
        for rel, h in self.html(self.live).items():
            self.assertNotRegex(h, PROMISE, rel)

    def test_negative_the_checks_above_catch_what_they_are_for(self):
        self.assertRegex("日程が発表されたら、その日のうちに足します。", PROMISE)
        self.assertRegex("発表の日に、このページへ足します。", PROMISE)
        self.assertNotRegex("終わったセールは「終了」になります。", PROMISE)
        self.assertRegex("文は買い時カレンダーです", "買い時カレンダー")
        with self.assertRaises(ValueError):
            render.absolutize('<a href="unknown.html">x</a>')           # a kit link without a place on the site stops the build
        self.assertEqual(render.absolutize('<a href="calendar.html">x</a><img src="assets/polished-hero.webp">'), '<a href="/calendar/">x</a><img src="/assets/kit/assets/polished-hero.webp">')

    def test_outside_links_only_in_the_affiliate_box_and_the_product_page(self):
        for rel, h in self.html(self.live).items():
            body = PR_LINK.sub("", AFF_BOX.sub("", h.split("<main", 1)[-1]))
            body = re.sub(r'<section class="content-block shops-box".*?</section>', "", body, flags=re.S)      # the shops box of /yahoo/: the Yahoo! credit link is required (test_kaidoki_yahoo_shops.py)
            if rel.startswith(("kaden/test-phone/", "food/", "daily/", "fashion/", "beauty/", "home/", "hobby/", "service/", "rakuten/index", "yahoo/", "amazon/sale-calendar/")) or rel == "kaden/index.html":
                self.assertNotRegex(body, self.SOURCE_SHOWN, rel)          # 2026-11-15 (owner): no source link, no source button, no source line on a shop, genre or product page
            if rel.startswith(("contact", "privacy", "about")):
                continue
            self.assertNotRegex(body, r'href="(https?:)?//', rel)

    def test_hero_headline_comes_from_hero_json_by_time(self):
        def top(now):
            return build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_NOW": now}, products=[])["index.html"]
        self.assertIn("お買い物マラソン、<br>", top("2026-11-10T12:00"))
        self.assertIn("いよいよ開幕！", top("2026-11-12T12:00"))
        later = top("2026-12-01T12:00")
        self.assertIn("買う前にチェック！", later)
        self.assertNotIn("いよいよ開幕", later)
        self.assertIn("NO SALE, NO LIFE", later)      # the picture is permanent

    def test_sale_tiles_come_from_facts_and_an_unannounced_sale_shows_no_date(self):
        cal = self.live["calendar/index.html"]
        tiles = re.findall(r'<article class="sale-tile".*?</article>', cal, re.S)
        self.assertGreaterEqual(len(tiles), 20)
        for t in tiles:
            if 'data-status="日程未発表"' in t:
                self.assertEqual(re.findall(r'data-start="([^"]*)"', t), [""])
                self.assertNotRegex(t, r"\d{4}/\d{2}/\d{2}\(")
            self.assertRegex(t, r"確認日 2026/11/03|確認日 \d{4}/\d{2}/\d{2}")
        self.assertIn("Yahoo!ショッピング ブラックフライデー 2026", cal)
        self.assertIn('data-status="開催予定"', cal)
        self.assertNotRegex(cal, r"[¥￥]\s?\d|\d円(?!に|ま)", "no product price on the calendar")

    def test_state_of_a_sale_by_the_minute(self):
        s = {"start": "2026-11-04T20:00:00+09:00", "end": "2026-11-11T01:59:00+09:00"}
        at = lambda x: render.datetime.fromisoformat(x + "+09:00")
        self.assertEqual(render.state(s, at("2026-11-04T19:59:00")), "開催予定")
        self.assertEqual(render.state(s, at("2026-11-11T01:59:30")), "開催中")      # "1:59" means until 2:00
        self.assertEqual(render.state(s, at("2026-11-11T02:00:00")), "終了")
        self.assertEqual(render.state({"start": None, "end": None}, at("2026-11-11T02:00:00")), "日程未発表")

    def test_product_page_exists_only_with_its_private_data(self):
        self.assertIn("kaden/test-phone/index.html", self.live)
        self.assertNotIn("固定順 1", self.live["kaden/index.html"])
        none = build({"KAIDOKI_REDESIGN": "1"}, products=[])
        self.assertFalse([k for k in none if k.startswith("kaden/test-phone")])
        for k, h in self.html(none).items():
            self.assertNotIn("/kaden/test-phone/", h, k)

    # a mall's product, store or shelf address is product data and stays out of the repository; a mall's own campaign page (event., corp. news, /promotion/) is a campaign fact, as on every other page of the site
    MALL_PRODUCT_URL = (r"amazon\.co\.jp|amzn\.|(?<!event\.)(?<!corp\.)rakuten\.co\.jp/(?!campaign)|item\.rakuten|store\.shopping\.yahoo|item\.shopping\.yahoo|"
                        r"paypaymall|shopping\.yahoo\.co\.jp/(?!promotion)|(?<!shopping)(?<!lohaco)\.yahoo\.co\.jp|www\.rakuten\.co\.jp")

    def test_mall_product_address_check_catches_product_pages_and_lets_campaign_pages_through(self):
        for bad in ("https://item.rakuten.co.jp/shop/x/", "https://www.rakuten.co.jp/nitori/", "https://store.shopping.yahoo.co.jp/a/b.html", "https://www.amazon.co.jp/dp/B0ABCDEFGH", "https://shopping.yahoo.co.jp/search?p=x"):
            self.assertRegex(bad, self.MALL_PRODUCT_URL, bad)
        for ok in ("https://event.rakuten.co.jp/beauty/korea/", "https://corp.rakuten.co.jp/news/update/2026/1112_01.html", "https://shopping.yahoo.co.jp/promotion/gateway/brand/red/"):
            self.assertNotRegex(ok, self.MALL_PRODUCT_URL, ok)

    def test_the_repository_holds_no_product_data(self):
        out = subprocess.run(["git", "ls-files", "sites/kaidoki"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split()
        self.assertFalse([f for f in out if "/private/" in f])
        for f in (SITE / "redesign" / "products").glob("*.json"):
            txt = f.read_text(encoding="utf-8")
            self.assertNotRegex(txt, self.MALL_PRODUCT_URL, str(f))
        ignored = subprocess.run(["git", "check-ignore", "sites/kaidoki/private/products/x.json"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertIn("private", ignored)
        for f in (SITE / "redesign").rglob("*"):
            if f.is_file() and f.suffix in (".json", ".html", ".py"):
                self.assertNotRegex(f.read_text(encoding="utf-8"), r"amazon\.co\.jp/[A-Za-z-]+/dp/|B0[A-Z0-9]{8}", str(f))

    # ---- 2026-11-15: every genre has its page; the partnered programmes' links are all there, as advertisements, with words and not addresses ----
    BARE_URL_TEXT = re.compile(r"<a [^>]*>\s*(?:https?:)?//[^<]*</a>")

    def test_genre_pages_exist_for_every_category_and_carry_the_partner_links(self):
        from sites.kaidoki.redesign import genres, affiliate
        cats = json.loads((SITE / "redesign" / "categories.json").read_text(encoding="utf-8"))
        self.assertEqual({c["id"] for c in cats}, set(genres.GENRES))
        for gid, items in genres.PARTNERS.items():
            html = render.genre_partners(gid)
            self.assertEqual(html.count('rel="nofollow sponsored noopener"'), len(items), gid)
            self.assertEqual(html.count('target="_blank"'), len(items), gid)
            self.assertEqual(html.count('class="pr-chip"'), len(items), gid)
            self.assertNotRegex(html, self.BARE_URL_TEXT)
            for kind, key, label in items:
                self.assertIn(label, html)
                self.assertTrue(key in affiliate.A8_MAT or key in affiliate.VC_PID, key)

    def test_negative_a_link_whose_words_are_its_address_is_caught(self):
        self.assertRegex('<a href="https://px.a8.net/x" rel="nofollow">https://example.com/x</a>', self.BARE_URL_TEXT)
        self.assertNotRegex('<a href="https://px.a8.net/x" rel="nofollow">お名前.comを見る</a>', self.BARE_URL_TEXT)

    def test_every_product_row_link_of_the_data_has_a_programme_code(self):
        from sites.kaidoki.redesign import affiliate
        for f in (SITE / "redesign" / "products").glob("*.json"):
            for st in json.loads(f.read_text(encoding="utf-8"))["stores"]:
                for spec in st.get("aff", []):
                    if spec["k"] == "a8":
                        self.assertIn(spec["key"], affiliate.A8_MAT, f)
                    if spec["k"] in ("vc", "vctext"):
                        self.assertIn(spec["key"], affiliate.VC_PID, f)

    def test_a_merged_page_redirects_and_nothing_links_to_its_old_address(self):
        from sites.kaidoki.redesign import genres
        real = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "0", "KAIDOKI_NOW": "2026-11-12T10:00"})          # the real product files
        ht = real.get(".htaccess", "")
        self.assertTrue(genres.REDIRECTS)
        for old, new in genres.REDIRECTS.items():
            self.assertIn(f"Redirect 301 {old} {new}", ht)
            self.assertIn(new.strip("/") + "/index.html", real)          # the new page exists
            self.assertNotIn(old.strip("/") + "/index.html", real)       # the old one is gone
            for rel, h in self.html(real).items():
                self.assertNotIn(f'href="{old}"', h, rel)                # no page links to the old address
            self.assertNotIn(f"sale-calendar.com{old}", real.get("sitemap.xml", ""))

    def test_negative_a_merge_without_a_redirect_is_caught(self):
        ht = "RewriteEngine on"
        self.assertNotIn("Redirect 301 /hobby/steam/ /hobby/game-sales/", ht)

    # ---- 2026-11-15: the top page's table 'いま分かっている日程' is the calendar's data (every shop), not the malls' two rows ----
    def _top_table_names(self, html):
        sec = html.split("<h2>いま分かっている日程</h2>", 1)[1].split("</section>", 1)[0]
        return [re.sub(r"<[^>]+>", "", r[1]) for r in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td>", sec)]

    def _expected_top_names(self, today):
        from datetime import date, timedelta
        from sites.kaidoki.redesign import schedule
        end = today + timedelta(days=13)
        rows = [it for it in schedule.all_items() if it["kind"] in ("confirmed", "notice") and it.get("s") and "(終了日)" not in it["title"]
                and date.fromisoformat(it["e"] or it["s"]) >= today and date.fromisoformat(it["s"]) <= end]
        return {("【発表予定日】" if it["kind"] == "notice" else "") + it["title"] for it in rows}

    def test_the_top_table_follows_the_calendar_data(self):
        from datetime import date
        top = self.live["index.html"]
        names = self._top_table_names(top)
        expected = self._expected_top_names(date(2026, 11, 12))
        self.assertGreater(len(names), 4)
        self.assertTrue(set(names) <= expected, set(names) - expected)           # nothing on the top that the calendar does not have
        self.assertTrue(any(n.startswith("【発表予定日】") for n in names))        # an announcement day is shown, told apart from a confirmed date
        from sites.kaidoki.redesign import schedule
        self.assertIn("楽天ブラックフライデー 2026", names)
        self.assertGreater(len(set(names)), 2)                                    # not only the two malls' sales
        if len(expected) <= schedule.HOME_TABLE_MAX:
            self.assertEqual(set(names), expected)
        self.assertIn('href="/calendar/"', top.split("<h2>いま分かっている日程</h2>", 1)[1].split("</section>", 1)[0])

    def test_negative_a_top_table_with_only_the_malls_rows_is_caught(self):
        from datetime import date
        stale = "<h2>いま分かっている日程</h2><table><tr><td>楽天</td><td>楽天ブラックフライデー 2026</td></tr><tr><td>Yahoo!</td><td>Yahoo!ショッピング ブラックフライデー 2026</td></tr></table></section>"
        names = self._top_table_names(stale)
        expected = self._expected_top_names(date(2026, 11, 12))
        self.assertGreater(len(expected), len(names) + 2)          # the calendar has more: a table like this one would fail the test above

    # ---- 2026-11-15: no page keeps the old beige tables / plain notes: the red x gold parts are in the stylesheet for every page ----
    def test_the_old_beige_parts_are_restyled_in_the_new_design(self):
        css = (SITE / "redesign" / "static" / "styles" / "extra.css").read_text(encoding="utf-8")
        tail = css[css.index("2026-11-15 owner: the old parts"):]
        for sel in (".tablewrap caption", ".tablewrap thead th", ".notice", ".checklist li", ".article-links article", ".cal-item", ".cal-grid th", ".aff-box", ".toc", ".footer", ".btn-red"):
            self.assertRegex(tail, re.escape(sel) + r"[^{}]*\{[^}]*(var\(--p-|#000)", sel)
        self.assertRegex(tail, r"\.tablewrap caption[^{}]*\{[^}]*linear-gradient\(180deg,var\(--p-red\)")      # the table's title row is red, not the old beige (#fff0c9)
        for h in ("doc", "kit"):          # the red title block is on the explanation pages too, not only the shop / genre / product pages
            self.assertIn(f'[data-page-type="{h}"] .page-banner', css)

    def test_negative_a_stylesheet_without_the_new_table_rules_is_caught(self):
        old = ".doc caption{background:#fff0c9}.doc thead th{background:#fff0c9}"
        self.assertNotRegex(old, r"\.tablewrap caption[^{}]*\{[^}]*linear-gradient")

    # ---- 2026-11-15: a page that names a mall carries that mall's affiliate link (the linkage gate's affiliate-missing, baseline now empty) ----
    def test_every_page_that_names_a_mall_carries_its_affiliate_link(self):
        from sites.kaidoki import hooks
        n = 0
        for rel, h in self.html(self.live).items():
            if rel in hooks.NO_MALL_BOX or "<main" not in h or "noindex" in h.split("</head>", 1)[0]:
                continue
            text = re.sub(r"<[^>]+>", " ", h.split("<main", 1)[1])
            for mall, names in hooks.MALL_NAMES.items():
                if any(x in text for x in names):
                    n += 1
                    self.assertTrue(hooks._has_mall_link(h, mall), f"{rel}: names {names[0]} without its link")
        self.assertGreater(n, 20)

    def test_negative_a_page_naming_a_mall_without_its_link_is_caught(self):
        from sites.kaidoki import hooks
        self.assertFalse(hooks._has_mall_link("<main><p>楽天市場のセール</p><a href=\"https://example.com/\">楽天市場</a></main>", "rakuten"))
        self.assertTrue(hooks._has_mall_link('<a href="https://hb.afl.rakuten.co.jp/hgc/x/?pc=y" target="_blank" rel="nofollow sponsored noopener">楽天市場のページを見る</a>', "rakuten"))

    def test_the_privacy_optout_link_is_worded_not_an_address(self):
        h = self.live["privacy/index.html"]
        self.assertNotIn(">aboutads.info</a>", h)
        self.assertIn("オプトアウトのページ</a>", h)

    # ---- Muse's prototype of 2026-11-14 (shop pages / product pages) ----
    SOURCE_SHOWN = re.compile(r"公式サイトを開く|ほかの公式ページ|class=\"src\"|出典")

    def test_negative_a_source_button_or_source_line_is_caught(self):
        self.assertRegex('<a class="btn" href="https://example.com/a">公式サイトを開く</a>', self.SOURCE_SHOWN)
        self.assertRegex('<p class="src">ほかの公式ページ：</p>', self.SOURCE_SHOWN)
        self.assertRegex("<dt>出典</dt>", self.SOURCE_SHOWN)
        self.assertNotRegex("<p>確認日 2026年11月9日</p>", self.SOURCE_SHOWN)

    SOURCE_LABEL = re.compile(r"出典の種類|<p class=\"credit\">出典")

    def test_negative_the_source_type_label_is_caught(self):
        self.assertRegex('<p class="cal-src">出典の種類: 主催者の公式発表 ／ 確認日 2026/11/12</p>', self.SOURCE_LABEL)
        self.assertRegex('<th scope="col">出典の種類</th>', self.SOURCE_LABEL)
        self.assertRegex('<p class="credit">出典: 各主催者の発表と報道をもとに作成</p>', self.SOURCE_LABEL)
        self.assertNotRegex('<p class="cal-src">確認日 2026/11/12</p>', self.SOURCE_LABEL)

    def test_no_page_shows_a_source_label_but_the_check_day_and_one_general_sentence_stay(self):
        """Owner 2026-11-15 (D26): no named source or source type on a page. The calendar rows keep only the check day, and the top and calendar pages carry the one general sentence."""
        general = "公式の発表をはじめとする複数の情報をもとにしています"
        for rel, h in self.html(self.live).items():
            self.assertNotRegex(h, self.SOURCE_LABEL, rel)
        for rel in ("index.html", "calendar/index.html"):
            h = self.live[rel]
            self.assertIn(general, h, rel)
            self.assertRegex(h, r'<p class="cal-src">確認日 \d{4}/\d{2}/\d{2}</p>', rel)

    RANKING = re.compile(r"最安|最安値|1位|第1位|No\.?\s?1|ランキング|おすすめ順|安い順")

    def test_prototype_shop_page_parts(self):
        """The mall pages carry the prototype's sale-date blocks (ribbon + name + dates + check day) in the page type 'mall'; the genre page in 'genre'."""
        for rel in ("rakuten/index.html", "amazon/sale-calendar/index.html", "yahoo/index.html"):
            h = self.live[rel]
            self.assertIn('<body data-page-type="mall">', h, rel)
            blocks = re.findall(r'<article class="sale-block".*?</article>', h, re.S)
            self.assertTrue(blocks, rel)
            for b in blocks:
                self.assertRegex(b, r'<span class="ribbon( soon)?">(開催中|開催予定|日程未発表|終了)</span>', rel)
                self.assertRegex(b, r"確認日 \d{4}/\d{2}/\d{2}", rel)      # every block carries its check day
                self.assertIn('class="sale-date"', b)
                if 'data-status="日程未発表"' in b:
                    self.assertIn("日程未発表", re.search(r'<p class="sale-date">(.*?)</p>', b).group(1))
                    self.assertNotRegex(re.search(r'<p class="sale-date">(.*?)</p>', b).group(1), r"\d月\d+日")
                self.assertNotRegex(b, self.RANKING, rel)
        self.assertIn('<body data-page-type="genre">', self.live["kaden/index.html"])
        self.assertIn(".sale-block", (SITE / "redesign" / "static" / "styles" / "extra.css").read_text(encoding="utf-8"))

    def test_prototype_product_page_parts(self):
        h = self.live["kaden/test-phone/index.html"]
        self.assertIn('<body data-page-type="product">', h)
        rows = re.findall(r'<article class="store-row">.*?</article>', h, re.S)
        self.assertEqual(len(rows), 2)
        self.assertIn("店A", rows[0])
        self.assertIn("店B", rows[1])      # the order of the data is kept: no sorting, no ranking
        for r in rows:
            self.assertRegex(r, r"確認日 2026年11月9日")
            self.assertNotRegex(r, self.RANKING)
        self.assertIn('<p class="discount"><small>最大</small>15%<small>OFF</small></p>', rows[0])
        for r in rows:
            self.assertNotRegex(r, r'href="https?://')          # the official page address stays in the data and never on the screen (owner 2026-11-15)
            self.assertNotRegex(r, self.SOURCE_SHOWN)
        self.assertIn('<section class="fit-box"><h2>向き・不向き</h2>', h)
        self.assertIn("向かない場合", h)
        self.assertNotIn("store-burst", h)      # the old prototype's boxing-ring heading is gone

    def test_negative_ranking_words_are_caught_and_fixed_order_is_kept(self):
        for bad in ("最安はこの店", "第1位", "No.1の割引", "ランキング上位", "安い順に並べました"):
            self.assertRegex(bad, self.RANKING)
        self.assertNotRegex("最大15%OFF。確認日 2026年11月9日", self.RANKING)
        pr = dict(FIXTURE)
        reversed_row = render.store_row(pr, FIXTURE["stores"][1]) + render.store_row(pr, FIXTURE["stores"][0])
        self.assertLess(reversed_row.index("店B"), reversed_row.index("店A"))      # the helper keeps whatever order it is given: the order is the data's (the file test above pins it)

    def test_the_real_product_file_follows_the_prototype_rules(self):
        """The tracked product file: fixed order (official store first, Amazon last), a check day and a headline on every store, no price, a fit section."""
        for f in (SITE / "redesign" / "products").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            names = [s["name"] for s in d["stores"]]
            kind = "固定順" if d["slug"] == "iphone-18-pro" else "企画"          # a product page orders its stores; a shop page lists the shop's campaigns in the file's order
            self.assertEqual([s["tag"] for s in d["stores"]], [f"{kind} {i + 1}" for i in range(len(names))], f)
            if any(n.startswith("Amazon") for n in names):
                self.assertTrue(names[-1].startswith("Amazon"), f)
            for s in d["stores"]:
                self.assertTrue(s["checked"], f)
                self.assertTrue(s.get("headline"), f"{f} {s['name']}")
                self.assertNotRegex(json.dumps(s["headline"], ensure_ascii=False), self.RANKING)
            self.assertNotRegex(json.dumps(d, ensure_ascii=False), self.RANKING, f)
            self.assertTrue(all(s["links"] for s in d["stores"] if not s["name"].startswith("Amazon")), f)          # every row has its official link (Amazon: its page address stays out of the repository)
            if d["slug"] == "iphone-18-pro":
                self.assertTrue(d.get("fit", {}).get("suits"), f)
                self.assertTrue(d["fit"].get("not_suits"), f)


class ProductCheckedDayTest(unittest.TestCase):
    """The confirmation day of a product page comes from its store rows (the oldest one): moving the page's day means re-reading the rows (Muse 2026-11-16: iPhone's page said 11/9 after a re-check)."""

    def test_the_page_day_is_the_oldest_row_day_and_the_meta_line_follows(self):
        import copy
        for pr in render.load_products(SITE):
            days = [re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", st["checked"]).groups() for st in pr["stores"]]
            old = min((int(y), int(m), int(d)) for y, m, d in days)
            self.assertEqual(pr["checked"], "%04d-%02d-%02d" % old, pr["slug"])
            self.assertIn("確認日：%d年%d月%d日" % old, pr["meta"], pr["slug"])

    def test_negative_an_old_row_pulls_the_page_day_back_and_a_typed_page_day_cannot_hide_it(self):
        import copy
        pr = copy.deepcopy(render.load_products(SITE)[0])
        pr["stores"][0]["checked"] = "2026年11月1日"
        pr["checked"] = "2026-11-16"
        pr["meta"] = "確認日：2026年11月16日"
        out = render.derive_checked(pr)
        self.assertEqual(out["checked"], "2026-11-01")
        self.assertIn("確認日：2026年11月1日", out["meta"])


if __name__ == "__main__":
    unittest.main()
