"""kurashi-calendar.com (sites/kurashi), the design of 2026-11-13 (the owner's template 「暮らしの準備と手続き」) and the checked guides merged into it.

Past failures this guards against: the old site name left in a title or a footer; a template that has no affiliate link at all (the template had none); a fact that the
fact check of 2026-11-13 corrected coming back (each corrected sentence is listed in CORRECTED and must be absent); a calendar in the browser that disagrees with the deadline
catalog; a reviewer's name invented for an unreviewed article; a page the owner's template put on a URL the old site did not have (no URL may change without a 301).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from sokuhou import newsite
from sites.kurashi.gen.shop_links import A8_SECTIONS, SHOP_PAGES

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kurashi"
OLD_NAME = "暮らしの年間カレンダー"
NEW_NAME = "暮らしの準備と手続き"

# the sentences the fact check corrected: they must not appear on any page again
CORRECTED = [
    "転入先から指定された", "2027年2月分から</td><td>請求した1月の翌月", "12月29日と30日は、平日なら営業します", "令和8年分の公式な日付は未発表",
    "12月27日(日)までに出せば元日に届きます", "医療保険証が要ります", "5年間の保管が必要です", "休日に当たるときの扱いは、市区町村によって窓口の案内が違う",
    "原則として寄附した翌年1月10日まで。郵送は必着です", "を、その日の14日後と15日後に読み替え", "慌てずにすみます",
]
OLD_URLS = ["/", "/month/", "/month/1/", "/month/2/", "/month/3/", "/month/11/", "/month/12/", "/life/", "/life/birth/", "/life/kaigo/", "/life/kekkon/", "/life/shibo/",
            "/life/taishoku/", "/moving/", "/moving/menkyo-sha/", "/moving/tenshutsu/", "/kakutei-shinkoku/", "/kakutei-shinkoku/furusato/", "/kakutei-shinkoku/hitsuyo/",
            "/kakutei-shinkoku/junbi/", "/kakutei-shinkoku/kanpu/", "/furusato/deadline/", "/furusato/one-stop/", "/nengajo/", "/nenmatsu-chosei/", "/nenmatsu-nenshi/",
            "/iryouhi-koujo/", "/kafun/", "/shin-seikatsu/", "/method/", "/about/", "/privacy/", "/contact/"]


def rel_of(path: str) -> str:
    return "index.html" if path == "/" else path.strip("/") + "/index.html"


def build(day: str = "2026-11-13"):
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "out"
    old = os.environ.get("KURASHI_TODAY")
    os.environ["KURASHI_TODAY"] = day
    try:
        newsite.main_build(SITE, ["--out", str(out), "--release", "--strict-seo"])
    finally:
        if old is None:
            os.environ.pop("KURASHI_TODAY")
        else:
            os.environ["KURASHI_TODAY"] = old
    return tmp, out


def guides() -> dict:
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (SITE / "guides").glob("*.json") if not f.name.startswith("_")}


def links_without_rel(html: str) -> list[str]:
    """the links to a shop or an ad network: each needs rel nofollow sponsored noopener, target=_blank, and a word (not the address) as its text"""
    bad = []
    for attrs, text in re.findall(r'<a ([^>]*href="https?://(?:hb\.afl\.rakuten\.co\.jp|px\.a8\.net|www\.amazon\.co\.jp)[^"]*"[^>]*)>(.*?)</a>', html, re.S):
        if not all(w in attrs for w in ("nofollow", "sponsored", "noopener", 'target="_blank"')):
            bad.append("rel/target: " + attrs[:60])
        if re.match(r"^\s*(https?://|www\.)", re.sub(r"<[^>]+>", "", text)):
            bad.append("address as the text: " + text[:40])
    return bad


class Renewal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = build()
        cls.pages = {p.relative_to(cls.out).as_posix(): p.read_text(encoding="utf-8") for p in cls.out.rglob("*.html")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, path: str) -> str:
        return self.pages[rel_of(path)]

    # ---- the name
    def test_the_old_site_name_is_nowhere(self):
        for rel, html in self.pages.items():
            self.assertNotIn(OLD_NAME, html, rel)
        for f in self.out.rglob("*"):
            if f.suffix in (".js", ".css", ".xml", ".txt", ".json", ".ics"):
                self.assertNotIn(OLD_NAME, f.read_text(encoding="utf-8"), f.name)
        self.assertIn(f"| {NEW_NAME}</title>", self.page("/nengajo/"))
        self.assertIn(NEW_NAME, self.page("/about/"))
        self.assertIn(NEW_NAME, self.page("/privacy/"))
        self.assertIn(f"&copy; {NEW_NAME}", self.page("/"))

    def test_no_url_of_the_old_site_is_lost(self):
        for path in OLD_URLS:
            self.assertIn(rel_of(path), self.pages, f"{path} would answer 404")
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        for path in OLD_URLS:
            if path in ("/contact/",):
                continue
            self.assertIn(f"https://kurashi-calendar.com{path}</loc>", sitemap, path)

    def test_the_helper_pages_are_not_in_the_sitemap_and_are_noindex(self):
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        for path in ("/saved/", "/search/"):
            self.assertNotIn(path, sitemap)
            self.assertIn('content="noindex', self.page(path))

    # ---- the frame
    def test_every_page_has_the_frame_and_one_h1(self):
        for rel, html in self.pages.items():
            if rel in ("contact/thanks.html",) or rel.startswith("google"):
                continue
            self.assertIn('class="site-header wrap"', html, rel)
            self.assertIn('class="site-footer wrap"', html, rel)
            self.assertEqual(len(re.findall(r"<h1[ >]", html)), 1, rel)
            self.assertNotIn("/assets/style.css", html, rel)
            self.assertNotIn("__V__", html, rel)

    def test_the_browser_files_have_their_version_and_exist(self):
        for rel, html in self.pages.items():
            for href in re.findall(r'(?:href|src)="(/assets/[^"?]+)(?:\?v=[0-9a-f]+)?"', html):
                self.assertTrue((self.out / href.lstrip("/")).exists(), (rel, href))
        for name in ("app", "pages", "calendar", "library", "illustrations", "data"):
            js = (self.out / "assets" / "t" / f"{name}.js").read_text(encoding="utf-8")
            self.assertNotIn("__V__", js, name)
        self.assertTrue((self.out / "assets" / "t" / "ZenMaruGothic-Bold.woff2").exists())
        self.assertFalse(list((self.out / "assets").rglob("*.ttf")))          # the full font is 3.7MB: only the woff2 of the characters is shipped
        self.assertFalse(list((self.out / "assets").rglob("*.png")) and any(p.stat().st_size > 400_000 for p in (self.out / "assets").rglob("*.png")))

    # ---- the facts
    def test_the_corrected_sentences_do_not_come_back(self):
        blob = "\n".join(self.pages.values()) + "\n".join(f.read_text(encoding="utf-8") for f in (SITE / "guides").glob("*.json"))
        for s in CORRECTED:
            self.assertNotIn(s, blob, s)

    def test_the_child_allowance_row_names_the_15_day_rule(self):
        html = self.page("/life/birth/")
        self.assertIn("2027年1月4日(月)</td><td>2027年1月分から", html)
        self.assertIn("15日特例", html)

    def test_a_corrected_sentence_would_be_caught(self):
        self.assertIn("転入先から指定された", "転出証明書など転入先から指定されたもの")
        self.assertTrue(any(s in "転出証明書など転入先から指定されたもの" for s in CORRECTED))

    # ---- the guides
    def test_each_guide_is_on_its_page_with_checklist_official_links_and_faq(self):
        by_path = {g["path"]: g for g in guides().values() if not g.get("light")}
        self.assertEqual(len(by_path), 11)
        for path, g in by_path.items():
            html = self.page(path)
            self.assertEqual(html.count('type="checkbox" data-check="'), len(g["documents"]), path)
            self.assertIn(f'data-save-guide="{g["id"]}"', html, path)
            for sid in g["source"]:
                self.assertIn(f'href="{json.loads((SITE / "guides" / "_site.json").read_text(encoding="utf-8"))["sources"][sid]["url"]}"', html, (path, sid))
            for fq in g["faq"]:
                self.assertIn(fq["question"], html, path)
            self.assertIn('"@type": "FAQPage"', html, path)
            self.assertIn("official-list", html, path)

    def test_no_article_is_marked_as_approved_by_someone(self):
        for g in guides().values():
            if g.get("light"):
                continue
            self.assertIs(g["review"]["approved"], False, g["id"])
            self.assertIsNone(g["review"]["reviewedBy"], g["id"])
            self.assertIsNone(g["review"]["reviewedAt"], g["id"])
            self.assertEqual(g["factCheck"]["status"], "source-checked")

    def test_every_source_of_a_guide_exists_and_every_guide_page_exists(self):
        site = json.loads((SITE / "guides" / "_site.json").read_text(encoding="utf-8"))
        for g in guides().values():
            self.assertIn(rel_of(g["path"]), self.pages, g["id"])
            for sid in g["source"]:
                self.assertIn(sid, site["sources"], (g["id"], sid))
                self.assertTrue(site["sources"][sid]["url"].startswith("https://"), sid)
            for d in g.get("deadlines", []):
                self.assertIn(d["source"], g["source"], g["id"])

    # ---- the calendar in the browser
    def test_the_browser_calendar_has_the_same_deadlines_as_the_catalog(self):
        spec = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        js = (self.out / "assets" / "t" / "data.js").read_text(encoding="utf-8")
        for c in spec["deadlines"]:
            self.assertRegex(js, r'"id":"%s","date":"%s"' % (re.escape(c["id"]), c["date"]), c["id"])
        for path in ("/moving/", "/nengajo/", "/kakutei-shinkoku/"):
            self.assertIn(f'"url":"{path}"', js)
        self.assertIn("export const recordsForMonth", js)

    def test_the_home_page_has_the_calendar_and_this_days_nearest_deadlines(self):
        html = self.page("/")
        for needle in ('id="calendar-content"', 'id="event-guides"', 'data-view="quarter"', 'data-d="2026-12-20"'):
            self.assertIn(needle, html)
        self.assertIn("2026年11月13日時点でいちばん近い期限は", re.sub(r"<[^>]+>", "", html))
        self.assertIn("/assets/t/app.js?v=", html)

    # ---- the affiliate links
    def test_every_topic_page_has_its_search_links_with_pr_rel_and_target(self):
        for path, (_h2, _intro, rk, am) in SHOP_PAGES.items():
            html = self.page(path)
            self.assertIn("hb.afl.rakuten.co.jp/hgc/583f273a.77c989b6.583f273b.0a6a5fff/", html, path)
            self.assertIn("（PR）", html, path)
            if am:
                self.assertIn("tag=amazonmacs-22", html, path)
            self.assertEqual(links_without_rel(html), [], path)

    def test_the_a8_link_is_on_each_of_its_pages(self):
        for path in A8_SECTIONS:
            html = self.page(path)
            self.assertIn("a8mat=4BGH3G+CRMSF6+33J0+15UCEA", html, path)
            self.assertIn('src="https://www11.a8.net/0.gif?a8mat=4BGH3G+CRMSF6+33J0+15UCEA"', html, path)
            self.assertIn("【PR】", html, path)
            self.assertEqual(links_without_rel(html), [], path)

    def test_no_affiliate_link_shows_its_address_as_the_text(self):
        for rel, html in self.pages.items():
            self.assertEqual(links_without_rel(html), [], rel)

    def test_a_missing_rel_and_an_address_text_are_caught(self):
        self.assertTrue(links_without_rel('<a href="https://px.a8.net/svt/ejp?a8mat=A" rel="nofollow">x</a>'))
        self.assertTrue(links_without_rel('<a href="https://hb.afl.rakuten.co.jp/hgc/I/?pc=x" rel="nofollow sponsored noopener" target="_blank">https://hb.afl.rakuten.co.jp/</a>'))
        self.assertEqual(links_without_rel('<a href="https://px.a8.net/svt/ejp?a8mat=A" rel="nofollow sponsored noopener" target="_blank">年賀状印刷</a>'), [])

    # ---- the pages the guides did not reach are still reached
    def test_no_page_is_an_orphan(self):
        linked = set()
        for rel, html in self.pages.items():
            for href in re.findall(r'<a [^>]*href="(/[^"#?]*)', html):
                linked.add(href)
        for path in OLD_URLS:
            if path == "/":
                continue
            self.assertIn(path, linked, f"nothing links to {path}")

    def test_the_official_links_open_in_a_new_tab_and_name_the_office(self):
        html = self.page("/moving/")
        self.assertRegex(html, r'<a href="https://www\.digital\.go\.jp/[^"]*" target="_blank" rel="noopener noreferrer"><span class="official-link-label"><span class="official-agency">デジタル庁｜')


if __name__ == "__main__":
    unittest.main()
