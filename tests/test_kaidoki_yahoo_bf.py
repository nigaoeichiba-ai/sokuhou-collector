"""/yahoo/black-friday/ (買い回りの組み立て) and the top lead that names every running sale (修正依頼 2026-11-23).  The examples are computed; negatives: a total under the threshold gets nothing, the cap holds, one running sale keeps the old form."""
from __future__ import annotations

import unittest
from unittest import mock

from sites.kaidoki.gen import pages_misc, pages_yahoo as Y


class PointsTest(unittest.TestCase):
    def test_the_total_picks_the_rate_and_the_points_are_on_the_goods_without_tax(self):
        self.assertEqual(Y.points(22000), (7, 20000, 1400))
        self.assertEqual(Y.points(19800), (4, 18000, 720))
        self.assertEqual(Y.points(4400, 700), (4, 4000, 160))      # shipping counts for the threshold, not for the points

    def test_negative_under_the_threshold_and_over_the_cap(self):
        self.assertEqual(Y.points(4400), (0, 0, 0))
        self.assertEqual(Y.points(330000)[2], Y.CAP)


class LeadTest(unittest.TestCase):
    def ev(self, name, mall):
        return {"name": name, "mall": mall, "start": "2026-11-27", "start_t": "00:00", "end": "2026-11-29", "end_t": "23:59"}

    def test_every_running_sale_is_named(self):
        up = [self.ev("Yahoo!ショッピング ブラックフライデー 2026", "Yahoo!ショッピング"), self.ev("ブラックフライデー 2026 先行セール", "Amazon")]
        with mock.patch.object(pages_misc, "phase", return_value="now"):
            t = pages_misc.top_lead(up)
        self.assertIn("2件", t)
        self.assertIn("Amazonのブラックフライデー 2026 先行セール", t)
        self.assertNotIn("Yahoo!ショッピングのYahoo!ショッピング", t)

    def test_negative_one_running_sale_keeps_the_single_form(self):
        with mock.patch.object(pages_misc, "phase", return_value="now"):
            t = pages_misc.top_lead([self.ev("ブラックフライデー 2026 先行セール", "Amazon")])
        self.assertTrue(t.startswith("いま開催中なのは、Amazonの"))
        self.assertNotIn("件です", t)


if __name__ == "__main__":
    unittest.main()
