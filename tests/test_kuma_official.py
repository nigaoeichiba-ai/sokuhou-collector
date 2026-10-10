"""/official/ of the bear site: every prefecture's official bear page, what this site shows for it, and the ministry's figure.

The links are checked against sites/kuma/links.json counted another way; the numbers are checked against the ministry fixture and the stored sources.
"""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build
from sites.kuma import live as live_mod
from sokuhou import prefectures as pf
from sokuhou import sitecheck
from tests.test_kuma_build import AKITA, CFG, COUNTS_META, HAVE_PYPDF, MIYAGI, _counts_raw, raw_data
from tests.test_kuma_cite import make_raw

LINKS_FILE = Path(__file__).resolve().parents[1] / "sites" / "kuma" / "links.json"
LINKS = json.loads(LINKS_FILE.read_text(encoding="utf-8"))
TODAY = date(2026, 10, 7)


def text_of(html: str) -> str:
    body = html.split("<main", 1)[1].split("</main>", 1)[0]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


class LinksFileTest(unittest.TestCase):
    """The data behind the page: every address is https, labelled, listed once, and belongs to a prefecture of the site."""

    def test_every_link_is_an_https_address_with_a_label_and_appears_once(self):
        seen = set()
        for pref, items in LINKS.items():
            self.assertIn(pref, pf.SHORT, pref)
            self.assertTrue(items, pref)
            for x in items:
                self.assertEqual(set(x), {"label", "url", "source"}, x)
                self.assertRegex(x["url"], r"^https://[^\s\"<>]+$", x)
                self.assertTrue(x["label"].strip(), x)
                self.assertIn(x["source"], {"pref", "moe", "maff"}, x)
                self.assertNotIn(x["url"], seen, x["url"])
                seen.add(x["url"])

    def test_a_dead_page_that_was_found_is_not_listed_again(self):
        urls = {x["url"] for items in LINKS.values() for x in items}
        self.assertNotIn("https://www.pref.tokushima.lg.jp/ippannokata/kurashi/shizen/7241461/", urls)       # 404 on 2026-10-10 (opened in a browser)
        self.assertTrue(any("rinya.maff.go.jp/shikoku" in x["url"] for x in LINKS["徳島"]))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class OfficialPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = make_raw()
        cls.prefs = {"miyagi": MIYAGI, "akita": AKITA, "fukushima": _counts_raw()}
        cls.out = Path(cls.tmp.name) / "site"
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, links=LINKS, prefs=cls.prefs, today=TODAY)
        cls.html = (cls.out / "official/index.html").read_text(encoding="utf-8")
        cls.text = text_of(cls.html)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_page_exists_is_in_the_sitemap_and_passes_the_site_checker(self):
        self.assertIn("official/index.html", self.files)
        self.assertIn("/official/", (self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])
        self.assertIn("<title>都道府県の公式のクマ出没情報(リンク集・37都道府県)", self.html)

    def test_every_link_of_the_file_is_on_the_page_as_an_external_link(self):
        main = self.html.split("<main", 1)[1].split("</main>", 1)[0]          # the footer's own source link to the ministry is not part of the table
        hrefs = re.findall(r'<a href="(https://[^"]+)" rel="noopener" target="_blank">', main)
        want = [x["url"].replace("&", "&amp;") for items in LINKS.values() for x in items]
        self.assertEqual(sorted(hrefs), sorted(want))
        self.assertEqual(len(want), 58)

    def test_the_lead_numbers_are_counted_from_the_data(self):
        self.assertIn("37都道府県の公式のページへのリンク(58件)", self.text)
        self.assertIn("記録または件数を載せている都道府県(3か所)", self.text)           # Miyagi, Akita (records), Fukushima (counts)

    def test_the_39_prefectures_with_pages_are_in_regional_tables_in_the_fixed_order_and_the_rest_are_named(self):
        d = build.prepare(self.raw)
        rows = re.findall(r'<tr><td><a href="/([a-z]+)/">', self.html)
        self.assertEqual(rows, [pf.SLUG[s] for _, _, shorts in pf.REGIONS for s in shorts if pf.SLUG[s] in d["by_slug"]])
        self.assertEqual(len(rows), 39)
        regions_with_rows = [r for r in pf.REGIONS if any(pf.SLUG[s] in d["by_slug"] for s in r[2])]
        self.assertEqual(len(re.findall(r'<h2 id="(?!unlisted)', self.html)), len(regions_with_rows))
        unlisted = re.search(r'<h2 id="unlisted">.*?</p>', self.html, re.S).group(0)
        self.assertEqual(len(d["unlisted"]), 8)
        for name in ("福岡", "沖縄"):
            self.assertIn(name, unlisted)
        self.assertIn("「出没がない」という意味ではありません", unlisted)

    def test_a_prefecture_without_links_says_so_and_does_not_claim_there_are_no_bears(self):
        row = re.search(r'<tr><td><a href="/chiba/">.*?</tr>', self.html, re.S).group(0)
        self.assertIn("掲載しているリンクはありません", row)
        self.assertIn("環境省の出没件数の表に、数値がありません", row)
        self.assertNotIn("出没がない", re.sub(r"「出没がない」という意味ではありません", "", self.text))
        self.assertIn("「環境省の表に数値がありません」は、「出没がない」という意味ではありません", self.text)

    def test_what_this_site_shows_and_the_ministry_figure_per_prefecture(self):
        def row(slug):
            return text_of("<main>" + re.search(rf'<tr><td><a href="/{slug}/">.*?</tr>', self.html, re.S).group(0) + "</main>")
        own = sum(1 for x in MIYAGI["sightings"] if x["observed_at"][:10] <= MIYAGI["as_of"])         # rows after the prefecture's own as-of date are not shown
        self.assertEqual(own, 2)
        self.assertIn(f"記録を一覧・地図で({own}件)", row("miyagi"))
        self.assertIn('/live/miyagi/', re.search(r'<tr><td><a href="/miyagi/">.*?</tr>', self.html, re.S).group(0))
        self.assertIn("記録を一覧・地図で", row("akita"))
        self.assertIn("件数を月別・市町村別で(4件)", row("fukushima"))
        self.assertNotIn("このサイトで見られる", row("tokyo"))
        done = build.prepare(self.raw)["done"]
        for p in self.raw["sightings"]["prefectures"]:
            if p["name"] == "宮城":
                want = sum(v for v in p["monthly"][done] if v)
        self.assertIn(f"{want:,}", row("miyagi"))                          # the ministry's full-year figure, summed another way

    def test_the_digest_is_linked_only_when_a_week_page_exists(self):
        # this small fixture has no complete week, so there is no /digest/ page and no link to it (it was a broken link in the navigation and on the home page)
        self.assertNotIn("digest/index.html", self.files)
        for rel in ("index.html", "official/index.html", "live/index.html"):
            self.assertNotIn('href="/digest/"', (self.out / rel).read_text(encoding="utf-8"), rel)

    def test_it_is_linked_from_the_hub_and_the_home(self):
        for rel in ("live/index.html", "index.html"):
            self.assertIn('href="/official/"', (self.out / rel).read_text(encoding="utf-8"), rel)

    def test_the_page_copies_nothing_it_does_not_say_so_for_and_claims_no_check(self):
        self.assertIn("当サイトは、リンク先の内容を、写していません", self.text)
        self.assertNotIn("確認済", self.text)
        self.assertNotIn("日本一", self.text)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class OfficialWithoutLiveDataTest(unittest.TestCase):
    def test_it_builds_without_any_live_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "n"
            files = build.render_site(make_raw(), CFG, out, release=True, links=LINKS, today=TODAY)
            self.assertIn("official/index.html", files)
            text = text_of((out / "official/index.html").read_text(encoding="utf-8"))
            self.assertIn("記録または件数を載せている都道府県(0か所)", text)
            self.assertNotIn("記録を一覧", text)
            self.assertEqual(sitecheck.check_dir(out, CFG["site_url"]), [])


if __name__ == "__main__":
    unittest.main()
