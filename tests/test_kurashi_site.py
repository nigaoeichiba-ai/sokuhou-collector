"""kurashi-calendar.com (sites/kurashi): the generated content is the generator's output, the dates are computed, and the site passes the release checks.

Past failures this guards against: a deadline typed by hand and left wrong (the 5-year refund period was first written as ending in 2032 instead of 2031), a page below
the thin-page bar published as indexable, a main search term missing from the title, and mall product data / secrets in the public repository.
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sokuhou import newsite, seokit, sitecheck
from sites.kurashi import gen
from sites.kurashi.gen import common
from sites.kurashi.gen.pages_life import add_months

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kurashi"
BASE = "https://kurashi-calendar.com"


class Dates(unittest.TestCase):
    def test_weekdays_of_the_deadlines(self):
        self.assertEqual(common.wd(date(2027, 2, 16)), "火")          # the first day of the filing for reiwa 8
        self.assertEqual(common.wd(date(2027, 3, 15)), "月")
        self.assertEqual(common.wd(date(2026, 3, 15)), "日")          # reiwa 7: the 15th was a Sunday, so the NTA showed 3/16 (Mon)
        self.assertEqual(common.wd(date(2026, 12, 20)), "日")         # the new start of the New Year cards

    def test_counting_rules(self):
        self.assertEqual(common.last_day_inclusive(date(2026, 12, 1), 14), date(2026, 12, 14))      # the Family Register Act art. 43: the birth day is day 1
        self.assertEqual(common.last_day_exclusive(date(2027, 3, 27), 14), date(2027, 4, 10))       # Civil Code art. 140: the first day is not counted
        self.assertEqual(add_months(date(2026, 1, 6), 10), date(2026, 11, 6))                         # the NTA's own example of the 10-month inheritance tax deadline

    def test_refund_period_is_five_years(self):
        text = (SITE / "content" / "kakutei-shinkoku-kanpu.json").read_text(encoding="utf-8")
        self.assertIn("2031年12月31日", text)
        self.assertNotIn("2032年12月31日", text)


class Content(unittest.TestCase):
    def test_content_is_what_the_generator_writes(self):
        """A date edited by hand in content/*.json would be lost at the next generation: it has to match."""
        for p in gen.all_pages():
            f = SITE / "content" / gen.file_name(p["path"])
            self.assertTrue(f.exists(), f.name)
            self.assertEqual(json.loads(f.read_text(encoding="utf-8")), json.loads(json.dumps(p, ensure_ascii=False)), f"{f.name} differs from the generator")

    def test_thirty_pages_and_the_mix(self):
        pages = gen.all_pages()
        self.assertEqual(len(pages), 30)
        same_type = [p for p in pages if p["kind"] in ("hub", "list")]
        deep = [p for p in pages if p["kind"] in ("article", "analysis")]
        self.assertLessEqual(len(same_type), len(pages) // 2)
        self.assertGreaterEqual(len(deep), 10)

    def test_every_page_names_its_sources_with_a_checked_date(self):
        spec = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        for p in gen.all_pages():
            self.assertTrue(p["sources"], p["path"])
            for sid in p["sources"]:
                self.assertEqual(spec["sources"][sid]["fetched"], "2026-11-03", sid)
                self.assertTrue(spec["sources"][sid]["url"].startswith("https://"), sid)

    def test_no_mall_data_or_secrets_in_the_public_repository(self):
        blob = "".join(f.read_text(encoding="utf-8") for f in list((SITE / "content").glob("*.json")) + [SITE / "site.json", SITE / "config.json"])
        for bad in ("rakuten", "affiliate", "amazon.co.jp", "a8.net", "shopping.yahoo", "applicationId"):
            self.assertNotIn(bad, blob.lower(), bad)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        newsite.main_build(SITE, ["--out", str(cls.out), "--release", "--strict-seo"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_release_checks_pass_with_no_thin_page(self):
        pages = {str(p.relative_to(self.out)).replace("\\", "/"): p.read_text(encoding="utf-8") for p in self.out.rglob("*.html")}
        self.assertEqual(sitecheck.check_dir(self.out, BASE), [])
        for rel, html in pages.items():
            if rel.startswith(("about", "contact", "privacy", "policy")) or rel in ("index.html",):
                continue
            self.assertNotIn("noindex", html[:3000], rel)

    def test_search_console_verification_file_is_written(self):
        f = self.out / "googleabcac004d8b7d556.html"
        self.assertEqual(f.read_text(encoding="utf-8"), "google-site-verification: googleabcac004d8b7d556.html\n")

    def test_a_thin_page_would_be_caught(self):
        """The bar is real: a page with a table but a few lines is reported by the same function the build uses."""
        thin = "<main><h1>x</h1><p>短い。</p><table><tr><td>1</td></tr></table></main>"
        self.assertTrue(seokit.thin_reasons({"x/index.html": thin}, {"x/index.html": "article"}))

    def test_main_search_term_is_in_title_and_h1(self):
        metas = [{"path": p["path"], "kind": p["kind"], "primary_kw": p["primary_kw"], "secondary_kw": p.get("secondary_kw", []), "intent": p["intent"], "title": p["title"],
                  "h1": p["h1"], "description": p["description"], "answer": p["answer"]} for p in gen.all_pages()]
        errors, warnings = seokit.keyword_problems(metas)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
