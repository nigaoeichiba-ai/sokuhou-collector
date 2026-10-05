"""Wage-survey pages: figures are checked against values worked out by hand from the source tables."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.saichin import build, wage as wagelib
from sokuhou.sources import estat_wage
from tests.test_saichin_pages import CFG, _raw

WAGE_FIXTURE = Path(__file__).parent / "fixtures" / "estat_wage_ref1.xlsx"


def wage_raw():
    w = estat_wage.parse_xlsx(WAGE_FIXTURE.read_bytes())
    w.update({"source_page": estat_wage.SOURCE_PAGE, "source_file": estat_wage.SOURCE_FILE, "fetched_at": "2026-10-05T17:00:00+09:00"})
    return w


class EffectiveDateCorrectionTest(unittest.TestCase):
    """MHLW's workbook has the year of the decision, not the next year, for revisions effective in January to March."""

    def test_january_to_march_dates_of_the_decision_year_move_one_year_on(self):
        self.assertEqual(build.plausible_effective("秋田県", 2025, "2025-03-31"), ("2026-03-31", "2025-03-31"))
        self.assertEqual(build.plausible_effective("福島県", 2025, "2025-01-01"), ("2026-01-01", "2025-01-01"))

    def test_normal_dates_are_untouched(self):
        self.assertEqual(build.plausible_effective("東京都", 2025, "2025-10-03"), ("2025-10-03", None))
        self.assertEqual(build.plausible_effective("秋田県", 2025, "2026-03-31"), ("2026-03-31", None))

    def test_dates_that_cannot_be_explained_are_refused(self):
        for iso in ("2026-04-01", "2024-12-31", "2027-04-01"):  # after the window, a year too early, far too late
            with self.assertRaises(build.BuildError):
                build.plausible_effective("X", 2025, iso)

    def test_the_six_prefectures_with_a_delayed_reiwa_7_revision_are_corrected(self):
        d = build.prepare(_raw())
        fixed = {r["name"]: next(h for h in r["history"] if h["fy"] == 2025) for r in d["rows"]}
        wrong = sorted(n for n, h in fixed.items() if h["date_fixed_from"])
        self.assertEqual(wrong, ["大分県", "徳島県", "熊本県", "福島県", "秋田県", "群馬県"])
        self.assertEqual(fixed["秋田県"]["effective_date"], "2026-03-31")  # the Akita labour bureau: 31 March 2026
        self.assertEqual(fixed["群馬県"]["effective_date"], "2026-03-01")
        self.assertIsNone(fixed["東京都"]["date_fixed_from"])
        for h in fixed.values():
            self.assertGreaterEqual(h["effective_date"], "2025-10-01")  # no Reiwa 7 revision took effect before October 2025

    def test_the_page_says_so_only_where_a_date_was_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(_raw(), CFG, Path(tmp) / "s", release=True)
            akita = (Path(tmp) / "s" / "akita" / "index.html").read_text(encoding="utf-8")
            tokyo = (Path(tmp) / "s" / "tokyo" / "index.html").read_text(encoding="utf-8")
        self.assertIn("2025年3月31日となっています", akita)
        self.assertIn("2026年3月31日として表示しています", akita)
        self.assertNotIn("※ 厚生労働省の一覧表では", tokyo)


class WageViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = build.prepare(_raw())
        cls.v = wagelib.view(wage_raw(), cls.d)

    def test_survey_year(self):
        self.assertEqual(wagelib.survey_year("令和7年"), 2025)
        with self.assertRaises(wagelib.WageError):
            wagelib.survey_year("平成30年")

    def test_hourly_and_annual_by_hand(self):
        # Tokyo: 418.3 thousand yen / 159 h = 2,630.8 -> 2,631; (448.5 x 12 + 1,397.8) thousand yen = 6,779,800 yen.
        t = self.v["rows"]["東京都"]
        self.assertEqual(t["hourly"], 2631)
        self.assertEqual(t["annual"], 6779800)
        # Okinawa: 277.4 / 163 h = 1,701.8 -> 1,702.
        self.assertEqual(self.v["rows"]["沖縄県"]["hourly"], 1702)
        # National: 340.6 / 162 h = 2,102.5 -> 2,102 (round half to even is not used: 2102.469...).
        self.assertEqual(self.v["national"]["hourly"], 2102)

    def test_minimum_wage_in_force_in_june_2025_is_the_reiwa_6_amount(self):
        # The Reiwa 6 revisions (October 2024): Tokyo 1,163 yen, Okinawa 952 yen; national weighted average 1,055 yen.
        self.assertEqual(self.v["rows"]["東京都"]["min_then"], 1163)
        self.assertEqual(self.v["rows"]["沖縄県"]["min_then"], 952)
        self.assertEqual(self.v["national"]["min_then"], 1055)
        self.assertEqual(self.v["min_then_label"], "令和6年度")

    def test_ratios_by_hand(self):
        self.assertAlmostEqual(self.v["rows"]["東京都"]["ratio"], 1163 / 2631)
        self.assertAlmostEqual(self.v["national"]["ratio"], 1055 / 2102)
        self.assertEqual(f"{self.v['rows']['東京都']['ratio'] * 100:.1f}", "44.2")

    def test_ranks(self):
        rows = self.v["rows"]
        self.assertEqual(rows["東京都"]["hourly_rank"], 1)
        self.assertEqual(rows["青森県"]["hourly_rank"], 47)  # 263.9 thousand yen / 163 h = 1,619 yen is the lowest
        self.assertEqual(rows["東京都"]["ratio_rank"], 47)   # highest pay, lowest minimum-to-average ratio
        self.assertEqual(sorted(v["hourly_rank"] for v in rows.values())[0], 1)

    def test_a_survey_that_misses_a_prefecture_is_refused(self):
        w = wage_raw()
        w["prefectures"] = [p for p in w["prefectures"] if p["name"] != "東京都"]
        with self.assertRaises(wagelib.WageError):
            wagelib.view(w, self.d)

    def test_an_unreadable_year_label_is_refused(self):
        w = wage_raw()
        w["year_label"] = "2025年"
        with self.assertRaises(wagelib.WageError):
            wagelib.view(w, self.d)


class WagePagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(_raw(), CFG, cls.out, release=True, wage=wage_raw())
        cls.plain = Path(cls.tmp.name) / "plain"
        cls.plain_files = build.render_site(_raw(), CFG, cls.plain, release=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_new_pages_exist_and_are_in_the_sitemap(self):
        for kind in ("wage", "ratio"):
            self.assertIn(f"ranking/{kind}/index.html", self.files)
            self.assertIn(f"https://saichin-sokuho.com/ranking/{kind}/", self.read("sitemap.xml"))

    def test_site_without_wage_data_is_unchanged(self):
        self.assertNotIn("ranking/wage/index.html", self.plain_files)
        html = (self.plain / "tokyo" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("賃金の実態との比較", html)
        self.assertNotIn("/ranking/wage/", (self.plain / "ranking" / "high" / "index.html").read_text(encoding="utf-8"))

    def test_every_ranking_page_has_all_tabs_when_wage_is_present(self):
        for kind in ("high", "low", "raise", "wage", "ratio"):
            html = self.read(f"ranking/{kind}/index.html")
            for k in ("high", "low", "raise", "wage", "ratio"):
                self.assertIn(f'href="/ranking/{k}/"', html, (kind, k))
            self.assertEqual(html.count('class="on"'), 1, kind)

    def test_wage_ranking_is_sorted_and_complete(self):
        html = self.read("ranking/wage/index.html")
        rows = re.findall(r'<tr><td class="rk">(\d+)</td><td><a href="/([a-z]+)/">[^<]+</a></td><td>([\d,]+)円</td>', html)
        self.assertEqual(len(rows), 47)
        values = [int(v.replace(",", "")) for _, _, v in rows]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(rows[0][:2], ("1", "tokyo"))
        self.assertEqual(values[0], 2631)

    def test_ratio_ranking_is_sorted(self):
        html = self.read("ranking/ratio/index.html")
        pcts = [float(x) for x in re.findall(r'<td>(\d+\.\d)%</td>', html)]
        self.assertEqual(len(pcts), 47)
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_prefecture_page_section(self):
        html = self.read("tokyo/index.html")
        self.assertIn("賃金の実態との比較(令和7年賃金統計)", html)
        self.assertIn("2,631円", html)
        self.assertIn("44.2%", html)
        self.assertIn("678.0万円", html)
        self.assertIn("令和6年度の最低賃金(1,163円)", html)

    def test_definitions_page_states_what_the_numbers_are(self):
        html = self.read("ranking/ratio/index.html")
        for text in ("一般労働者", "6月分", "超過労働給与額", "標本誤差", "厚生労働省が作成したものではありません",
                     "https://www.e-stat.go.jp/stat-search/files?tclass=000001229518&amp;cycle=0",
                     "https://www.mhlw.go.jp/toukei/list/chinginkouzou.html"):
            self.assertIn(text, html)
        self.assertNotIn("{source}", html)

    def test_no_comparison_with_the_new_fiscal_years_minimum_wage(self):
        # The survey is June 2025; the page must say it compares with the amount in force then, not the Reiwa 8 amount.
        self.assertIn("最新の令和8年度の額とは比べていません", self.read("ranking/wage/index.html"))


if __name__ == "__main__":
    unittest.main()
