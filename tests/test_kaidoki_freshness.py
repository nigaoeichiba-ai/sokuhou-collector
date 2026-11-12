"""The daily freshness check of sale-calendar.com finds what is due, and says nothing when nothing is (negative tests included)."""
import unittest
from datetime import date

from sites.kaidoki.redesign.tools import freshness as F

T = date(2026, 11, 12)


def item(kind, **kw):
    base = {"id": "x", "kind": kind, "mall": "rakuten", "title": "テスト", "s": "2026-12-01", "e": "2026-12-05", "when": "12月1日から", "checked": "2026-11-12", "mo": None}
    base.update(kw)
    return base


class Freshness(unittest.TestCase):
    def test_ending_today_and_tomorrow(self):
        g = F.check_items([item("confirmed", s="2026-11-10", e="2026-11-12"), item("confirmed", s="2026-11-10", e="2026-11-13"), item("confirmed")], T)
        self.assertEqual(len(g["ending"]), 2)

    def test_nothing_due_is_empty(self):
        g = F.check_items([item("confirmed"), item("expected", s="2026-12-10"), item("notice", s="2026-11-20")], T)
        self.assertEqual(sum(len(v) for v in g.values()), 0)

    def test_expected_whose_day_came(self):
        self.assertEqual(len(F.check_items([item("expected", s="2026-11-11")], T)["expected_due"]), 1)
        self.assertEqual(len(F.check_items([item("expected", s=None, e=None, mo="2026-11")], T)["expected_due"]), 1)
        self.assertEqual(len(F.check_items([item("expected", s=None, e=None, mo="2026-12")], T)["expected_due"]), 0)

    def test_notice_day_came(self):
        self.assertEqual(len(F.check_items([item("notice", s="2026-11-12")], T)["notice_due"]), 1)

    def test_stale_checked_date(self):
        self.assertEqual(len(F.check_items([item("confirmed", checked="2026-11-01")], T)["stale"]), 1)
        self.assertEqual(len(F.check_items([item("confirmed", checked="2026-11-06")], T)["stale"]), 0)
        self.assertEqual(len(F.check_items([item("confirmed", checked="2026-11-01", s="2026-10-01", e="2026-10-31")], T)["stale"]), 0)

    def test_end_only_entry_is_not_a_start(self):
        g = F.check_items([item("confirmed", s="2026-11-12", e="2026-11-12", when="11月12日まで(開始日は確認していません)")], T)
        self.assertEqual(g["starting"], [])

    def test_product_rows(self):
        p = {"slug": "p", "checked": "2026年11月1日", "stores": [{"name": "A", "checked": "2026年11月1日", "rows": [["期間", "2026年11月10日まで"]]},
                                                               {"name": "B", "checked": "2026年11月12日", "rows": [["期間", "2025年8月20日〜終了日未定"]]}]}
        r = F.check_products([p], T)
        self.assertTrue(any("商品ページ p" in x for x in r))
        self.assertTrue(any("p / A" in x and "日前" in x for x in r))
        self.assertTrue(any("終了日が過ぎた行" in x and "/ A /" in x for x in r))
        self.assertFalse(any("/ B /" in x for x in r))

    def test_runs_on_real_data(self):
        text, n = F.run(T)
        self.assertIn("鮮度点検", text)
        self.assertGreaterEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
