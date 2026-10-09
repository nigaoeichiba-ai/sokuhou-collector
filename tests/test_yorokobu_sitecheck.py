"""The gift site, built from its REAL content on several dates, must pass the site-wide checks.

The old link test built a small fixture on two fixed dates, so a month page that linked to a page which only exists in October went unnoticed.
Here the real themes, pairs, articles, guides and tools are built on dates in different seasons (the products are a fixture: they come from the
Rakuten API at deploy time, and the deploy runs the same checks on the real build before uploading it).
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from sokuhou import sitecheck

HERE = Path(__file__).parent
SITE = Path(__file__).resolve().parents[1] / "sites" / "yorokobu"
DATES = [date(2026, 10, 7), date(2027, 1, 1), date(2027, 4, 1), date(2027, 12, 1)]


class RealContentSiteCheckTest(unittest.TestCase):
    def test_every_page_link_sitemap_entry_and_table_is_sound_on_each_date(self):
        cfg = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
        items = json.loads((HERE / "fixtures" / "yorokobu" / "items.json").read_text(encoding="utf-8"))
        c = content.load()
        for day in DATES:
            with self.subTest(day=day.isoformat()), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "site"
                build.render_site(c, items, cfg, out, release=True, today=day)
                problems = sitecheck.check_dir(out, cfg["site_url"])
                self.assertEqual(problems, [], f"{day}: " + "\n".join(problems[:15]))
                self.assertGreaterEqual(len(list((out / "month").glob("*/index.html"))), 6)   # a month with nothing to show has no page, and nothing links to it

    def test_pages_without_a_product_list_carry_the_amazon_search_the_pr_label_and_a_footer_naming_only_amazon(self):
        cfg = {**json.loads((SITE / "config.json").read_text(encoding="utf-8")), "amazon_tracking_id": "amazonmacs-22"}
        items = json.loads((HERE / "fixtures" / "yorokobu" / "items.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build.render_site(content.load(), items, cfg, out, release=True, today=DATES[0])
            checked = 0
            for sub in ("guide", "message", "month", "numbers", "occasion", "for"):
                for f in sorted((out / sub).glob("*/index.html")):
                    html = f.read_text(encoding="utf-8")
                    rel = f.relative_to(out).as_posix()
                    self.assertIn("amazon.co.jp/s?k=", html, rel)
                    self.assertIn("tag=amazonmacs-22", html, rel)
                    self.assertIn("Amazonのアソシエイトとして", html, rel)
                    self.assertIn('class="pr-quiet"', html, rel)                  # the label is at the top of every page with a paid link
                    self.assertIn("Amazonアソシエイト", html[html.index('class="pr-foot"'):], rel)
                    if "rakuten.co.jp/" not in html.replace("Supported by Rakuten", ""):
                        self.assertNotIn("楽天アフィリエイト", html[html.index('class="pr-foot"'):], rel)    # no Rakuten link on the page: not named
                    checked += 1
            self.assertGreater(checked, 60, checked)


if __name__ == "__main__":
    unittest.main()
