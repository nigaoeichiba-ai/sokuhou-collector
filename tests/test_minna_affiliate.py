"""Affiliate boxes: shown only with the owner's ids, always marked as advertising, with the links tagged sponsored."""
import json
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build

BASE = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト", "contact_own": True}
IDS = {"rakuten_affiliate_id": "aaaa.bbbb.cccc.dddd", "rakuten_tracking_id": "minna", "amazon_tracking_id": "amazonmacs-22"}


class AffiliateTest(unittest.TestCase):
    def test_no_ids_no_box(self):
        self.assertEqual(build.pr_box(BASE, "x", [("a", "kw")]), "")
        self.assertFalse(build.affiliates_on(BASE))

    def test_the_box_is_a_rakuten_box_only_while_amazon_is_off(self):
        html = build.pr_box({**BASE, **IDS}, "年賀状づくりに", [("プリンターのインク", "プリンター インク 純正")])
        self.assertIn('class="pr-note">PR<', html)
        self.assertEqual(html.count('rel="nofollow sponsored noopener"'), 1)
        self.assertIn("hb.afl.rakuten.co.jp/hgc/aaaa.bbbb.cccc.dddd/?pc=", html)
        self.assertIn("広告(楽天アフィリエイト)", html)
        self.assertNotIn("amazon", html.lower())
        self.assertNotIn("適格販売", html)

    def test_a_box_never_holds_the_links_of_two_stores(self):
        """2026-11-09: AFFILIATE_RULES.md says a Rakuten part gets Rakuten links only.  With both stores on, each gets its own box with its own notice."""
        import re
        from unittest import mock
        with mock.patch.dict(build.PR_STORES, {"amazon": build.amazon_box}):
            html = build.pr_box({**BASE, **IDS}, "x", [("インク", "プリンター インク"), ("用紙", "年賀状 プリンター用紙")])
        boxes = re.findall(r"<aside class=\"pr-box\">.*?</aside>", html, re.S)
        self.assertEqual(len(boxes), 2)
        rakuten, amazon = [b for b in boxes if "rakuten" in b][0], [b for b in boxes if "amazon" in b.lower()][0]
        self.assertIsNot(rakuten, amazon)
        self.assertNotIn("amazon", rakuten.lower())
        self.assertNotIn("rakuten", amazon.lower().replace("楽天", ""))
        self.assertNotIn("適格販売", rakuten)
        self.assertIn("適格販売", amazon)
        for b in boxes:
            self.assertEqual(len(re.findall(r"<a ", b)), 2)
            self.assertIn("pr-small", b)

    def test_links_are_exactly_what_the_programmes_give_and_nothing_is_added(self):
        """AFFILIATE_RULES.md 3b: Rakuten .../hgc/[id]/?pc=[URL]&m=[URL] (no tracking id), Amazon only k and tag, and the tag only href, target and rel."""
        import html as htmllib
        import re
        from unittest import mock
        from urllib.parse import parse_qs, urlsplit
        with mock.patch.dict(build.PR_STORES, {"amazon": build.amazon_box}):
            html = build.pr_box({**BASE, **IDS}, "年賀状づくりに", [("用紙", "年賀状 プリンター用紙"), ("インク", "プリンター インク")])
        tags = re.findall(r"<a ([^>]*)>(?:楽天市場|Amazon)で見る</a>", html)
        self.assertEqual(len(tags), 4)
        for attrs in tags:
            self.assertEqual(sorted(re.findall(r'([a-z-]+)="', attrs)), ["href", "rel", "target"])       # no class, aria-label, data-* ...
            self.assertIn('target="_blank"', attrs)
            self.assertIn('rel="nofollow sponsored noopener"', attrs)
            url = urlsplit(htmllib.unescape(re.search(r'href="([^"]+)"', attrs).group(1)))
            q = parse_qs(url.query)
            if url.netloc == "hb.afl.rakuten.co.jp":
                self.assertEqual(url.path, "/hgc/aaaa.bbbb.cccc.dddd/")                                  # nothing after the id
                self.assertEqual(sorted(q), ["m", "pc"])
                self.assertEqual(q["pc"], q["m"])
            else:
                self.assertEqual(url.netloc, "www.amazon.co.jp")
                self.assertEqual(sorted(q), ["k", "tag"])                                                # no other parameter
                self.assertEqual(q["tag"], ["amazonmacs-22"])
        self.assertNotIn("minna?", html)

    def test_the_rakuten_link_is_the_one_rakuten_gives_in_the_default_build(self):
        import html as htmllib
        import re
        from urllib.parse import parse_qs, urlsplit
        html = build.pr_box({**BASE, **IDS}, "x", [("インク", "プリンター インク 純正")])
        href = htmllib.unescape(re.search(r'href="([^"]+)"', html).group(1))
        url = urlsplit(href)
        self.assertEqual((url.netloc, url.path), ("hb.afl.rakuten.co.jp", "/hgc/aaaa.bbbb.cccc.dddd/"))
        q = parse_qs(url.query)
        self.assertEqual(sorted(q), ["m", "pc"])
        self.assertEqual(q["pc"][0], "https://search.rakuten.co.jp/search/mall/%E3%83%97%E3%83%AA%E3%83%B3%E3%82%BF%E3%83%BC%20%E3%82%A4%E3%83%B3%E3%82%AF%20%E7%B4%94%E6%AD%A3/")

    def test_amazon_alone_gives_no_box_and_no_empty_frame(self):
        self.assertEqual(build.pr_box({**BASE, "amazon_tracking_id": "amazonmacs-22"}, "x", [("a", "kw")]), "")
        self.assertEqual(build.pr_box({**BASE, **IDS}, "x", []), "")

    def test_no_box_row_is_a_service_or_a_stamp(self):
        """2026-11-09: printing services belong in a partner (A8) box after the owner's approval; stamps may be outside the programmes.  Rows are things."""
        import re
        for table in (build.GUIDE_PR, build.SPECIAL_PR, build.PRINTABLE_PR):
            for heading, rows in table.values():
                for label, kw in rows:
                    self.assertNotRegex(label, r"サービス|の印刷$|切手", label)
                    self.assertNotIn("印刷", kw, kw)
                    self.assertNotIn("切手", kw, kw)

    def test_a_built_page_has_no_amazon_link_and_the_partner_box_only_where_it_belongs(self):
        items, series = build.load_data()
        for slug in ("nenga-tsukurikata", "kantyu-mimai", "nenga-2027-schedule", "oseibo-orei-jo"):
            g = next(x for x in build.load_guides() if x["slug"] == slug)
            html = build.guide_page({**BASE, **IDS}, False, g, series)
            self.assertEqual(html.count('<aside class="pr-box">'), 1, slug)
            self.assertNotIn("amazon.co.jp", html, slug)
            # the partner (A8) box is on nenga-tsukurikata only (tests/test_minna_partners.py); every other page shows none
            self.assertEqual(html.count('<aside class="pr-box pr-partner">'), 1 if slug == "nenga-tsukurikata" else 0, slug)

    def test_every_planned_box_is_for_a_page_that_exists(self):
        guides = {g["slug"] for g in json.loads((Path(build.__file__).parent / "content" / "guides.json").read_text(encoding="utf-8"))["guides"]}
        self.assertTrue(set(build.GUIDE_PR) <= guides)
        self.assertTrue(set(build.SPECIAL_PR) <= {s["slug"] for s in build.SPECIALS})
        self.assertEqual(set(build.PRINTABLE_PR), {"calendar", "shojo", "nafuda", "jikanwari"})
        for table in (build.GUIDE_PR, build.SPECIAL_PR, build.PRINTABLE_PR):
            for heading, rows in table.values():
                self.assertTrue(heading and 1 <= len(rows) <= 3)

    def test_a_built_guide_shows_the_box_only_with_ids(self):
        items, series = build.load_data()
        g = next(x for x in build.load_guides() if x["slug"] == "nurie-insatsu")
        without = build.guide_page(BASE, False, g, series)
        with_ids = build.guide_page({**BASE, **IDS}, False, g, series)
        self.assertNotIn("pr-box", without)
        self.assertIn("pr-box", with_ids)


if __name__ == "__main__":
    unittest.main()
