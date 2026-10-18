"""今月の贈りどき: one page per month, built only from the SEASON table and the fixed-date gift days."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, giftcal
from tests.test_yorokobu_build import CFG, FIX

TODAY = date(2026, 5, 3)


class MonthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.files = build.render_site(cls.c, items, CFG, cls.out, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_hub_and_month_pages_exist_and_are_in_the_sitemap(self):
        self.assertIn("month/index.html", self.files)
        self.assertIn("month/5/index.html", self.files)
        self.assertIn("/month/5/", self.read("sitemap.xml"))

    def test_may_page_names_mothers_day_with_this_years_date(self):
        t = self.read("month/5/index.html")
        self.assertIn("母の日", t)
        self.assertIn("5月10日", t)  # the 2nd Sunday of May 2026
        self.assertIn("/occasion/mothers-day/", t)

    def test_start_dates_come_from_the_gift_calendar_not_typed(self):
        # Father's Day (3rd Sunday of June) is 2026-06-21: choosing starts 21 days earlier, in May.
        t = self.read("month/5/index.html")
        self.assertEqual(giftcal.gift_days(2026)[[g["slug"] for g in giftcal.gift_days(2026)].index("fathers-day")]["start"], date(2026, 5, 31))
        self.assertIn("5月31日", t)
        self.assertIn("父の日", t)

    def test_a_month_already_past_shows_next_years_dates(self):
        self.assertEqual(build.month_year(3, TODAY), 2027)
        self.assertEqual(build.month_year(5, TODAY), 2026)
        self.assertIn("2027年のものです", self.read("month/3/index.html"))

    def test_home_and_calendar_link_to_the_months(self):
        self.assertIn('href="/month/5/"', self.read("index.html"))
        self.assertIn('href="/month/"', self.read("calendar/index.html"))

    def test_every_month_page_links_to_existing_pages_only(self):
        import re
        months = build.month_pages(self.c, TODAY)
        for m in months:
            t = self.read(f"month/{m}/index.html")
            for href in re.findall(r'href="(/[^"#?]*)', t):
                target = href.lstrip("/") + ("index.html" if href.endswith("/") else "")
                self.assertTrue(target in self.files or (self.out / target).exists(), (m, href))

    def test_the_hub_never_links_to_a_month_without_a_page(self):
        import re
        months = build.month_pages(self.c, TODAY)
        for today in (date(2026, 5, 3), date(2026, 10, 7)):
            hub = build.month_hub_page({"c": self.c}, CFG, False, today, months)
            for m in re.findall(r'href="/month/(\d+)/"', hub):
                self.assertIn(int(m), months, (today, m))


class MonthReadsTest(unittest.TestCase):
    D = {"live_themes": [{"slug": "rainy-season-care", "title": "梅雨のテーマ"}, {"slug": "typhoon-ready", "title": "台風のテーマ"}],
         "c": {"articles": [{"slug": "storm-readiness-gift", "title": "備えの記事"}, {"slug": "other", "title": "別の記事"}]}}

    def test_only_listed_pages_of_that_month_are_returned(self):
        themes, arts = build.month_reads(self.D, 6)
        self.assertEqual([t["slug"] for t in themes], ["rainy-season-care"])
        self.assertEqual(arts, [])
        themes, arts = build.month_reads(self.D, 9)
        self.assertEqual([t["slug"] for t in themes], ["typhoon-ready"])
        self.assertEqual([a["slug"] for a in arts], ["storm-readiness-gift"])

    def test_a_page_missing_from_the_build_is_not_listed(self):
        themes, _ = build.month_reads({"live_themes": [], "c": {"articles": []}}, 6)
        self.assertEqual(themes, [])

    def test_mapping_slugs_exist_in_the_real_content(self):
        c = content.load()
        self.assertTrue(set(build.THEME_MONTHS) <= {t["slug"] for t in c["themes"]})
        self.assertTrue(set(build.ARTICLE_MONTHS) <= {a["slug"] for a in c["articles"]})
