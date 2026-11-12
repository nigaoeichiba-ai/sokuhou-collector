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
        # the one thing allowed: an owner-approved affiliate link to a Rakuten SEARCH page (no product data in it: no item name, price, image or item URL)
        text = re.sub(r"https://hb\.afl\.rakuten\.co\.jp/hgc/[0-9a-f.]+/\?pc=https%3A%2F%2Fsearch\.rakuten\.co\.jp%2Fsearch%2Fmall%2F[^\"\\ ]*", "", text)
        # also allowed: the top page of Rakuten Travel and of Rakuten Furusato Nozei (fixed pages, no product data)
        text = re.sub(r"https://hb\.afl\.rakuten\.co\.jp/hgc/[0-9a-f.]+/\?pc=https%3A%2F%2F(?:travel\.rakuten\.co\.jp%2F|event\.rakuten\.co\.jp%2Ffurusato%2F)(?=\\\")", "", text)
        # also allowed: an Amazon SEARCH page link (k= and the associate tag only: AFFILIATE_RULES.md; no price, image or item data)
        text = re.sub(r"https://www\.amazon\.co\.jp/s\?k=[^&\"\\ ]+&(?:amp;)?tag=amazonmacs-22", "", text)
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
            html = re.sub(r'<img [^>]*src="https://www\d*\.a8\.net/0\.gif[^>]*>', "", html)   # the ASP's 1x1 counter pixel (alt="" by design, code used as provided)
            for src in re.findall(r'<img src="/assets/img/([^"]+)"', html):
                self.assertTrue((SITE / "assets" / "img" / src).exists(), f"{name}: {src}")
            self.assertEqual(len(re.findall(r"<img ", html)), len(re.findall(r'alt="[^"]{8,}"', html)), name)

    def test_the_parent_links_the_four_children_and_nothing_that_does_not_exist(self):
        pages = _pages()
        paths = {p["path"] for p in pages.values()} | {"/about/", "/privacy/", "/contact/"} | {f"/cat/{slug}/" for slug, _, _ in newsite.site_hooks(SITE).CATS}   # legal pages and category pages are made by the build
        html = "".join(s.get("html", "") for s in pages["bousai.json"]["sections"])
        for child in ("/bousai-mizu-shokuryo/", "/bousai-keitai-toilet/", "/bousai-light/", "/bousai-denchi-juden/"):
            self.assertIn(f'href="{child}"', html)
        for page in pages.values():
            for href in re.findall(r'href="(/[^"#]*)"', "".join(s.get("html", "") for s in page["sections"])):
                self.assertIn(href, paths, f"{page['path']} links to {href}")

    def test_no_mark_of_the_writing_stage_is_left_in_a_page(self):
        for name, page in _pages().items():
            text = json.dumps(page, ensure_ascii=False)
            for mark in ("[イラスト", "[アフィリ候補", "[表:", "[チェックリスト]", "[子ページの案内]"):
                self.assertNotIn(mark, text, f"{name}: {mark}")                      # seen on 2026-11-07: a mark at the end of a paragraph stayed in four pages

    def test_each_child_has_its_own_source_line_and_never_the_typhoons(self):
        for name in ("bousai-mizu-shokuryo", "bousai-keitai-toilet", "bousai-light", "bousai-denchi-juden"):
            page = _pages()[name + ".json"]
            self.assertTrue(page.get("credit"), name)
            self.assertNotIn("気象庁", page["credit"], name)                          # seen on 2026-11-07: the typhoon's source line was shown on the four child pages

    def test_the_home_page_does_not_rule_out_politics(self):
        home = json.dumps(_pages()["home.json"], ensure_ascii=False)
        about = json.loads((SITE / "site.json").read_text(encoding="utf-8"))["purpose"]            # the long text of the old home page lives on /about/ since 2026-11-08
        for text in (home, about):
            self.assertNotIn("政治などの重い話題", text)                               # owner's decision 2026-11-07: politics and economy count when written for their effect on daily life
        self.assertIn("暮らしへの影響", about)

    def test_the_parent_intro_does_not_repeat_the_answer(self):
        page = _pages()["bousai.json"]
        intro = " ".join(x for sec in page["sections"] for x in sec.get("paras", []))
        self.assertEqual(intro.count(page["answer"]), 0)

    def test_the_search_console_file_is_shipped(self):
        cfg = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
        self.assertRegex(cfg["google_site_verification"], r"^google[0-9a-f]{16}\.html$")

    def test_the_footer_has_the_rakuten_credit_as_the_official_text_link(self):
        site = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        self.assertIn('<a href="https://developers.rakuten.com/" target="_blank">Supported by Rakuten Developers</a>', site["footer_html"])


if __name__ == "__main__":
    unittest.main()
