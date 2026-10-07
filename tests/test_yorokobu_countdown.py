import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


class CountdownTest(unittest.TestCase):
    def test_days_left_today_and_past(self):
        t = date(2026, 12, 1)
        self.assertEqual(build.countdown(date(2026, 12, 25), t), "あと24日")
        self.assertEqual(build.countdown(date(2026, 12, 1), t), "今日")
        self.assertEqual(build.countdown(date(2026, 11, 30), t), "")

    def test_the_next_date_of_a_fixed_day_rolls_over_to_next_year_and_floating_days_have_none(self):
        self.assertEqual(build.next_fixed("christmas", date(2026, 12, 1)), date(2026, 12, 25))
        self.assertEqual(build.next_fixed("christmas", date(2026, 12, 26)), date(2027, 12, 25))
        self.assertEqual(build.next_fixed("christmas", date(2026, 12, 25)), date(2026, 12, 25))      # the day itself still counts
        self.assertEqual(build.next_fixed("mothers-day", date(2026, 5, 11)), date(2027, 5, 9))
        self.assertIsNone(build.next_fixed("birthday", date(2026, 12, 1)))


class BuildTest(unittest.TestCase):
    def render(self, today):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "site"
        c = content.load(FIX)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        build.render_site(c, items, CFG, out, release=True, today=today)
        return out

    def test_the_home_season_tile_and_the_month_row_show_the_days_left(self):
        out = self.render(date(2027, 4, 20))                                   # the fixture has Mother's Day (2027-05-09)
        home = (out / "index.html").read_text(encoding="utf-8")
        self.assertTrue("あと19日(5月9日)・" in home, "home season tile lacks the countdown")
        month = (out / "month/5/index.html").read_text(encoding="utf-8")
        self.assertTrue("5月9日<small>(あと19日)</small>" in month, "month row lacks the countdown")

    def test_a_day_that_has_passed_shows_no_countdown(self):
        out = self.render(date(2027, 5, 12))
        month = (out / "month/5/index.html").read_text(encoding="utf-8")
        self.assertTrue("5月9日" in month)
        self.assertFalse("5月9日<small>(あと" in month)


if __name__ == "__main__":
    unittest.main()
