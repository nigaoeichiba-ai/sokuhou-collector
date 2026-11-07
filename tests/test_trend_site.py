"""trend-sokuho.com (今日の話題): the first article, the frame and the rules that must hold.

Past failures reproduced on purpose where a check is added: a number in the text that is not in the table, mall data in the public content, a page the build leaves out of the index.
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from sokuhou import newsite, sitecheck

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"


def _pages() -> dict:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (SITE / "content").glob("*.json")}


class TrendSite(unittest.TestCase):
    def test_article_is_indexable_and_has_the_numbers_table(self):
        a = _pages()["trend-typhoon32.json"]
        self.assertIn("台風32号", a["title"])
        self.assertIn(a["primary_kw"], a["title"])
        rows = [s["table"]["rows"] for s in a["sections"] if s.get("table")][0]
        years = {r[0]: int(r[1]) for r in rows}
        self.assertEqual(years["1994"], 36)
        self.assertEqual(min(years.values()), 32)
        self.assertEqual(len(years), 8)          # the eight years with 32 or more (the table of the JMA, read on 2026-11-07)

    def test_text_says_32_years_and_the_rank_is_marked_as_counted_here(self):
        text = json.dumps(_pages()["trend-typhoon32.json"], ensure_ascii=False)
        self.assertIn("32年ぶり", text)
        self.assertIn("表の数字から数えたもの", text)         # 6位タイ is the site's own count, not the JMA's wording

    def test_no_mall_data_in_the_public_content(self):
        text = "".join(p.read_text(encoding="utf-8") for p in (SITE / "content").glob("*.json"))
        for bad in ("rakuten.co.jp", "item.rakuten", "hb.afl", "affiliate", "applicationId", "accessKey", "amazon.co.jp", "shopping.yahoo"):
            self.assertNotIn(bad, text)

    def test_build_passes_the_site_check(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            newsite.build_site(SITE, out) if hasattr(newsite, "build_site") else newsite.main_build(SITE, ["--out", str(out)])
            self.assertEqual(sitecheck.main([str(out), "--base", "https://trend-sokuho.com"]) or 0, 0)

    def test_the_picture_has_alt_text_and_the_file_exists(self):
        a = _pages()["trend-typhoon32.json"]
        html = a["sections"][0]["html"]
        self.assertRegex(html, r'alt="[^"]{10,}"')
        self.assertTrue((SITE / "assets" / "img" / "typhoon-32.jpg").exists())

    def test_every_page_has_its_picture_and_every_picture_has_alt_text(self):
        for name, page in _pages().items():
            html = "".join(s.get("html", "") for s in page["sections"])
            for src in re.findall(r'<img src="/assets/img/([^"]+)"', html):
                self.assertTrue((SITE / "assets" / "img" / src).exists(), f"{name}: {src}")
            self.assertEqual(len(re.findall(r"<img ", html)), len(re.findall(r'alt="[^"]{8,}"', html)), name)

    def test_the_parent_links_the_four_children_and_nothing_that_does_not_exist(self):
        pages = _pages()
        paths = {p["path"] for p in pages.values()}
        html = "".join(s.get("html", "") for s in pages["bousai.json"]["sections"])
        for child in ("/bousai-mizu-shokuryo/", "/bousai-keitai-toilet/", "/bousai-light/", "/bousai-denchi-juden/"):
            self.assertIn(f'href="{child}"', html)
        for page in pages.values():
            for href in re.findall(r'href="(/[^"#]*)"', "".join(s.get("html", "") for s in page["sections"])):
                self.assertIn(href, paths, f"{page['path']} links to {href}")

    def test_the_footer_has_the_rakuten_credit_as_the_official_text_link(self):
        site = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        self.assertIn('<a href="https://developers.rakuten.com/" target="_blank">Supported by Rakuten Developers</a>', site["footer_html"])


if __name__ == "__main__":
    unittest.main()
