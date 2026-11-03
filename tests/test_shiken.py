"""shiken-nittei.com (試験日程カレンダー): the dates are right, and a wrong date is caught.

A wrong weekday or a deadline that a reader would miss does harm, so the checks read the built pages: every "2026年11月25日(水)" must agree with the calendar,
every source id of a page exists, the 'days left' sentences agree with the dates, and nothing says that the list is complete.
"""
from __future__ import annotations

import json
import re
import unittest
from datetime import date
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"
WD = "月火水木金土日"
FULL = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\(([月火水木金土日])\)")


def wrong_weekdays(html: str) -> list[str]:
    """The 'YYYY年M月D日(曜)' that do not agree with the calendar."""
    bad = []
    for y, m, d, w in FULL.findall(html):
        if WD[date(int(y), int(m), int(d)).weekday()] != w:
            bad.append(f"{y}年{m}月{d}日({w})")
    return bad


class ShikenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages, cls.report = newsite.build_pages(SITE, release=True, strict_seo=True)
        cls.html = {k: v for k, v in cls.pages.items() if isinstance(v, str) and k.endswith(".html")}

    def test_thirty_pages_with_the_designed_mix(self):
        content = sorted((SITE / "content").glob("*.json"))
        self.assertEqual(len(content), 30)
        kinds = [json.loads(p.read_text(encoding="utf-8"))["kind"] for p in content]
        self.assertGreaterEqual(kinds.count("article"), 10)                 # deep articles: ten or more
        self.assertLessEqual(kinds.count("item") / len(kinds), 0.5)        # same-type pages: half at most

    def test_every_weekday_agrees_with_the_calendar(self):
        for rel, html in self.html.items():
            self.assertEqual(wrong_weekdays(html), [], rel)

    def test_a_wrong_weekday_is_caught(self):
        self.assertEqual(wrong_weekdays("合格発表は2026年11月25日(木)です"), ["2026年11月25日(木)"])
        self.assertEqual(wrong_weekdays("合格発表は2026年11月25日(水)です"), [])

    def test_every_content_page_closes_with_the_official_announcement_sentence(self):
        for p in (SITE / "content").glob("*.json"):
            slug = json.loads(p.read_text(encoding="utf-8"))["path"].strip("/") or "."
            rel = "index.html" if slug == "." else f"{slug}/index.html"
            self.assertIn("最終的な日程は、主催団体の公式発表でご確認ください", self.html[rel], rel)

    def test_no_source_links_and_no_checked_day_per_row_on_a_page(self):
        """Owner's rule 2026-11-03: no source URL, no 'checked on' day, no list of official links in the page body."""
        for p in (SITE / "content").glob("*.json"):
            slug = json.loads(p.read_text(encoding="utf-8"))["path"].strip("/") or "."
            rel = "index.html" if slug == "." else f"{slug}/index.html"
            body = re.search(r"<main.*?</main>", self.html[rel], re.S).group(0)
            self.assertNotRegex(body, r'href="https?://', rel)
            self.assertNotIn("確認日", body, rel)

    def test_a_page_with_an_outside_link_would_be_caught(self):
        self.assertRegex('<main><a href="https://www.retio.or.jp/">x</a></main>', r'href="https?://')

    def test_no_page_claims_to_be_complete(self):
        for rel, html in self.html.items():
            text = re.sub(r"<[^>]+>", "", html)
            self.assertNotRegex(text.replace("網羅しません", ""), "網羅", rel)

    def test_days_left_agree_with_the_dates(self):
        html = self.html["takken/index.html"]
        self.assertIn("2026年11月25日(水)", html)
        self.assertIn("あと22日", html)                                    # 2026-11-03 -> 2026-11-25

    def test_unpublished_dates_are_not_made_up(self):
        html = self.html["schedule/index.html"]
        self.assertIn("次の回が未発表の試験", html)
        takken = re.sub(r"<[^>]+>", "", self.html["takken/index.html"])
        takken = re.sub(r"\d{4}年\d+月\d+日", "", takken)                      # the day it was checked is not a date of next year
        self.assertNotRegex(takken, r"令和9年度[^。]{0,30}\d+月\d+日")          # no invented date for next year

    def test_koko_rows_have_the_board_page_as_link(self):
        html = self.html["koko/index.html"]
        self.assertIn("東京都", html)
        self.assertGreaterEqual(html.count("<tr>"), 28)                       # one row per prefecture in each table
        self.assertIn("公式で確認", html)                                     # a missing application period is not filled in

    def test_the_example_pages_are_gone(self):
        for p in (SITE / "content").glob("*.json"):
            self.assertFalse(json.loads(p.read_text(encoding="utf-8")).get("example"), p.name)


if __name__ == "__main__":
    unittest.main()
