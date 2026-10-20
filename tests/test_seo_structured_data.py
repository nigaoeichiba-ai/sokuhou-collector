"""sitekit.structured_data: the JSON-LD every page gets from what it already shows (breadcrumbs -> BreadcrumbList, home -> WebSite)."""
from __future__ import annotations

import json
import re
import unittest

from sokuhou import sitekit

CFG = {"site_url": "https://example.test/", "site_name": "テスト速報"}
CRUMBS = '<nav class="crumbs" aria-label="パンくず"><a href="/">全国</a> &gt; <a href="/area/kanto/">関東</a> &gt; <span>東京都</span></nav>'


def blocks(html: str) -> list[dict]:
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


class StructuredDataTest(unittest.TestCase):
    def test_breadcrumbs_become_a_breadcrumblist_with_absolute_urls_and_the_last_item_without_a_link(self):
        (ld,) = blocks(sitekit.structured_data(CFG, "/tokyo/", CRUMBS + "<h1>東京都</h1>"))
        self.assertEqual(ld["@type"], "BreadcrumbList")
        rows = ld["itemListElement"]
        self.assertEqual([r["name"] for r in rows], ["全国", "関東", "東京都"])
        self.assertEqual([r["position"] for r in rows], [1, 2, 3])
        self.assertEqual(rows[1]["item"], "https://example.test/area/kanto/")
        self.assertNotIn("item", rows[2])

    def test_the_home_page_gets_a_website_with_the_site_name_only(self):
        (ld,) = blocks(sitekit.structured_data(CFG, "/", "<h1>トップ</h1>"))
        self.assertEqual(ld["@type"], "WebSite")
        self.assertEqual(ld["name"], "テスト速報")
        self.assertEqual(ld["url"], "https://example.test/")
        for key in ("author", "publisher", "creator", "copyrightHolder"):      # no operator or company name in the markup (owner's rule)
            self.assertNotIn(key, ld)

    def test_no_markup_for_a_page_without_breadcrumbs_or_with_a_single_item(self):
        self.assertEqual(sitekit.structured_data(CFG, "/about/", "<h1>運営者情報</h1>"), "")
        one = '<nav class="crumbs"><span>ここだけ</span></nav>'
        self.assertEqual(sitekit.structured_data(CFG, "/x/", one), "")

    def test_a_page_that_already_has_its_own_breadcrumblist_or_website_is_left_alone(self):
        own = '<script type="application/ld+json">{"@type": "BreadcrumbList"}</script>'
        self.assertEqual(sitekit.structured_data(CFG, "/tokyo/", CRUMBS + own), "")
        self.assertEqual(sitekit.structured_data(CFG, "/tokyo/", CRUMBS, existing=own), "")
        self.assertEqual(sitekit.structured_data(CFG, "/", "", existing='{"@type": "WebSite"}'), "")

    def test_a_breadcrumb_with_a_relative_link_is_not_turned_into_wrong_urls(self):
        odd = '<nav class="crumbs"><a href="tokyo/">東京</a> &gt; <span>市</span></nav>'
        self.assertEqual(sitekit.structured_data(CFG, "/x/", odd), "")

    def test_layout_puts_the_markup_in_the_head_and_escapes_a_closing_script_tag_in_a_label(self):
        site = {"assets": sitekit.Path(__file__).parent, "nav": [], "glyph": "x", "source_html": ""}
        body = '<nav class="crumbs"><a href="/">全国</a> &gt; <span>&lt;/script&gt;</span></nav><h1>t</h1>'
        html = sitekit.layout(site, CFG, False, path="/p/", title="t", description="d", body=body)
        head = html.split("</head>")[0]
        self.assertEqual(len(blocks(head)), 1)
        self.assertNotIn("</script></script>", head)


if __name__ == "__main__":
    unittest.main()
