"""saichin: the ranking tables show each prefecture's raise minus the national weighted-average raise."""
import re
import unittest

from sites.saichin import build
from tests.test_saichin_build import BASE_CFG, BuildTestBase


class RaiseGapTest(BuildTestBase):
    def test_text(self):
        self.assertEqual(build.raise_gap_text(0), "同じ")
        self.assertEqual(build.raise_gap_text(3), "+3円")
        self.assertEqual(build.raise_gap_text(-2), "−2円")

    def test_every_ranking_row_carries_the_gap_matching_its_raise(self):
        out, _ = self.render(BASE_CFG)
        for kind in ("high", "low", "raise"):
            html = (out / "ranking" / kind / "index.html").read_text(encoding="utf-8")
            self.assertIn("<th>全国平均の引上げ額との差</th>", html)
            self.assertIn("全国加重平均の引上げ額(+", html)
            nat = int(re.search(r"全国加重平均の引上げ額\(\+(\d+)円\)", html).group(1))
            rows = re.findall(r"<td>\+(\d+)円</td><td>([^<]+)</td><td>\d+月", html)
            self.assertEqual(len(rows), 47)
            for raise_, gap in rows:
                self.assertEqual(gap, build.raise_gap_text(int(raise_) - nat))


if __name__ == "__main__":
    unittest.main()
