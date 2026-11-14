"""atomou: the shopping links (sites/atomou/affiliate.py).  Every link is a PR link made the way the affiliate rules say (a search page, the owner's IDs, rel nofollow sponsored noopener, target _blank,
words for the visible text, never an address); no sad page (grief, disaster, medical, legal), no day marked off-limits for ads, and no genre or category on the never-list shows one.
The gates are tried on days built for the purpose (a negative test: a quiet day must get nothing), and on the built pages."""
from __future__ import annotations

import re
import sys
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import affiliate, build, catalog, usecases  # noqa: E402
from tests.test_atomou_build import CFG  # noqa: E402

TODAY = date(2026, 11, 14)      # a day on which many days of the data have begun and not ended (the data only grows)

SHOP = re.compile(r'<section class="shop".*?</section>', re.S)
A = re.compile(r'<a ([^>]*)>(.*?)</a>', re.S)


def day(**kw) -> dict:
    return {"group": "学校・資格", "category": "資格", "subject": "日商簿記検定", "quiet": False, "ad_ok": True, **kw}


class Gates(unittest.TestCase):
    def test_a_normal_day_gets_words(self):
        self.assertEqual(affiliate.words_for(day()), ["日商簿記検定 参考書", "日商簿記検定 問題集"])

    def test_a_quiet_day_gets_nothing(self):
        for kw in ({"quiet": True}, {"ad_ok": False}, {"group": "天気・災害", "category": "防災", "subject": "防災の日"}, {"group": "経済・政治", "category": "選挙"},
                   {"group": "お金・税金・制度", "category": "ふるさと納税"}, {"group": "お金・税金・制度", "category": "年金・保険"}, {"group": "健康・くらし", "category": "健康"},
                   {"group": "グルメ・食のイベント", "category": "お酒"}, {"group": "国際", "category": "万博"}):
            self.assertEqual(affiliate.words_for(day(**kw)), [], kw)
            self.assertEqual(affiliate.links_for(day(**kw)), "", kw)

    def test_the_sky_is_open_but_the_rest_of_the_weather_group_is_not(self):
        self.assertTrue(affiliate.words_for(day(group="天気・災害", category="天文", subject="しし座流星群")))
        self.assertEqual(affiliate.words_for(day(group="天気・災害", category="暦・季節", subject="冬至")), [])

    def test_no_card_of_the_data_that_is_quiet_or_off_limits_has_words(self):
        entries, _ = catalog.build_catalog(date.today())
        self.assertGreater(len(entries), 1000)
        bad = [e["title"] for e in entries if (e["quiet"] or not e.get("ad_ok", True)) and affiliate.words_for(e)]
        self.assertEqual(bad, [])

    def test_the_use_pages_with_links_are_not_sad_ones(self):
        for slug in affiliate.USE_WORDS:
            u = usecases.by_slug(slug)
            self.assertIsNotNone(u, slug)
            self.assertFalse(u["quiet"], slug)


class Links(unittest.TestCase):
    def test_every_link_is_a_pr_search_link_with_words(self):
        html = affiliate.links_for(day()) + affiliate.use_links("couple-anniversary") + affiliate.home_links() + affiliate.genre_links("スポーツ", ["野球", "サッカー"])
        links = A.findall(html)
        self.assertGreaterEqual(len(links), 10)
        for attrs, text in links:
            self.assertIn('rel="nofollow sponsored noopener"', attrs)
            self.assertIn('target="_blank"', attrs)
            self.assertNotRegex(text, r"https?://|www\.|\.co\.jp|\.com")
            m = re.search(r'href="([^"]+)"', attrs).group(1).replace("&amp;", "&")
            u = urlparse(m)
            if u.netloc == "hb.afl.rakuten.co.jp":
                self.assertIn(affiliate.RAKUTEN_ID, u.path)
                self.assertTrue(unquote(parse_qs(u.query)["pc"][0]).startswith("https://search.rakuten.co.jp/search/mall/"))
            else:
                self.assertEqual(u.netloc, "www.amazon.co.jp")
                self.assertEqual(sorted(parse_qs(u.query)), ["k", "tag"])
                self.assertEqual(parse_qs(u.query)["tag"], [affiliate.AMAZON_TAG])
        self.assertIn("PR", html)


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)
        cls.entries, _ = catalog.build_catalog(TODAY)

    def blocks(self, path: str) -> list[str]:
        return SHOP.findall(self.pages[path])

    def test_a_day_a_use_page_a_genre_page_and_my_page_have_the_block(self):
        e = next(e for e in self.entries if affiliate.words_for(e) and e["status"] != "ended")
        self.assertEqual(len(self.blocks(f"e/{e['id']}/index.html")), 1)
        self.assertEqual(len(self.blocks("use/exam-university/index.html")), 1)
        self.assertEqual(len(self.blocks("c/exams/index.html")), 1)
        self.assertEqual(len(self.blocks("my/index.html")), 1)

    def test_no_sad_page_has_the_block(self):
        for path, html in self.pages.items():
            if not (isinstance(html, str) and path.endswith("index.html")):
                continue
            if path.startswith("e/"):
                eid = path.split("/")[1]
                e = next((x for x in self.entries if x["id"] == eid), None)
                if e and (e["quiet"] or not e.get("ad_ok", True) or not affiliate.words_for(e)):
                    self.assertEqual(SHOP.findall(html), [], path)
        for slug in ("memorial-day", "monthly-memorial", "memorial-services", "pet-memorial", "disaster-remembrance", "pet-birthday", "furusato-nozei", "health-checkup"):
            self.assertEqual(SHOP.findall(self.pages[f"use/{slug}/index.html"]), [], slug)
        for slug in ("politics", "world", "health"):
            if f"c/{slug}/index.html" in self.pages:
                self.assertEqual(SHOP.findall(self.pages[f"c/{slug}/index.html"]), [], slug)

    def test_every_block_on_every_page_is_made_as_the_rules_say(self):
        n = 0
        for path, html in self.pages.items():
            if not (isinstance(html, str) and path.endswith("index.html")):
                continue
            for b in SHOP.findall(html):
                for attrs, text in A.findall(b):
                    n += 1
                    self.assertIn('rel="nofollow sponsored noopener"', attrs, path)
                    self.assertIn('target="_blank"', attrs, path)
                    self.assertNotRegex(text, r"https?://", path)
                self.assertIn("PR", b, path)
        self.assertGreater(n, 300)


if __name__ == "__main__":
    unittest.main()
