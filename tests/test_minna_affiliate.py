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

    def test_box_with_both_programmes(self):
        html = build.pr_box({**BASE, **IDS}, "年賀状づくりに", [("年賀状の印刷サービス", "年賀状 印刷 2027")])
        self.assertIn('class="pr-note">PR<', html)
        self.assertEqual(html.count('rel="sponsored noopener nofollow"'), 2)
        self.assertIn("hb.afl.rakuten.co.jp/hgc/aaaa.bbbb.cccc.dddd/minna?pc=", html)
        self.assertIn("tag=amazonmacs-22", html)
        self.assertIn("適格販売により収入を得ています", html)
        self.assertIn("広告(楽天アフィリエイト・Amazonアソシエイト)", html)

    def test_only_rakuten_does_not_claim_amazon(self):
        html = build.pr_box({**BASE, "rakuten_affiliate_id": "aaaa.bbbb.cccc.dddd"}, "x", [("a", "kw")])
        self.assertNotIn("amazon", html.lower())
        self.assertNotIn("適格販売", html)
        self.assertIn("楽天アフィリエイト", html)

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
