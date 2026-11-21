"""The "next year" table on each prefecture page, recomputed here from the workbook fixture by a separate calculation."""
import re
import unittest

from sites.saichin import build, history_old, outlook
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401
from tests.test_saichin_trend import all_series


def expected(series):
    """Return (raises of the last 3 years, amounts of the 3 scenarios, base) from {fy: amount}."""
    a = [series[fy] for fy in (2022, 2023, 2024, 2025, 2026)]
    raises = [a[2] - a[1], a[3] - a[2], a[4] - a[3]]
    rates = [a[2] / a[1] - 1, a[3] / a[2] - 1, a[4] / a[3] - 1]
    base = a[4]
    return raises, [base + raises[2], base + round(sum(raises) / 3), round(base * (1 + sum(rates) / 3))], base


class OutlookTest(SiteFixture):
    def page(self, slug):
        return self.read(f"{slug}/index.html")

    def test_every_prefecture_page_has_the_table_with_recomputed_numbers(self):
        raw = _raw()
        series, _ = all_series(raw, history_old.load())
        for p in raw["prefectures"]:
            slug = build.SLUGS[p["name"]]
            html = self.page(slug)
            self.assertIn("(試算)</h2>", html, slug)
            sect = html.split("(試算)</h2>", 1)[1].split("<h2>", 1)[0]
            cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td>(.*?)</td>", sect)]
            raises, amounts, base = expected(series[p["name"]])
            self.assertEqual(cells[1::2][:3], [f"{x:,}円" for x in amounts], slug)
            self.assertEqual(cells[0], f"+{raises[2]}円", slug)
            self.assertIn("令和9年度", html.split("(試算)</h2>", 1)[0][-80:], slug)

    def test_the_page_says_it_is_not_the_real_decision(self):
        self.assertIn("実際の額ではありません", self.page("saitama"))

    def test_short_series_or_stale_amount_gives_no_section(self):
        self.assertIsNone(outlook.scenarios({"amount": 1000, "long": [{"fy": 2025, "amount": 1000}]}))
        long = [{"fy": 2020 + i, "amount": 900 + 10 * i} for i in range(6)]
        self.assertIsNone(outlook.scenarios({"amount": 999, "long": long}))
        sc = outlook.scenarios({"amount": 950, "long": long})
        self.assertEqual(sc["same_raise"], (10, 960))
        self.assertEqual(sc["to1500"], (55, 2080))   # (1500-950)/10 = 55 years after 2025


if __name__ == "__main__":
    unittest.main()
