import io
import unittest
import zipfile
from pathlib import Path

from sokuhou.sources import mhlw_minwage as mw

FIX = Path(__file__).parent / "fixtures"


def _by_name(data):
    return {p["name"]: p["history"] for p in data["prefectures"]}


class MinimumWageSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.d = mw.parse_xlsx((FIX / "mhlw_minwage_history.xlsx").read_bytes())
        self.p = _by_name(self.d)

    def test_all_47_prefectures_and_latest_year(self):
        self.assertEqual(len(self.d["prefectures"]), 47)
        self.assertEqual(self.d["latest_fiscal_year"], 2026)
        self.assertEqual(self.d["fiscal_year_labels"]["2026"], "令和8年度")
        self.assertEqual(len(self.d["fiscal_year_labels"]), 25)  # 平成14年度 .. 令和8年度

    def test_fiscal_years_are_contiguous_including_reiwa_gannen(self):
        years = sorted(int(y) for y in self.d["fiscal_year_labels"])
        self.assertEqual(years, list(range(2002, 2027)))
        self.assertEqual(self.d["fiscal_year_labels"]["2019"], "令和元年度")
        self.assertEqual(self.p["東京"]["2019"]["amount"], 1013)

    def test_known_values_match_the_published_figures(self):
        self.assertEqual(self.p["東京"]["2026"], {"amount": 1280, "effective_date": "2026-10-01"})
        self.assertEqual(self.p["滋賀"]["2026"], {"amount": 1136, "effective_date": "2026-10-03"})
        self.assertEqual(self.p["沖縄"]["2026"], {"amount": 1086, "effective_date": "2026-12-02"})
        self.assertEqual(self.p["東京"]["2025"]["amount"], 1226)  # previous year, not shifted by a column

    def test_extremes_and_national_average_match_the_reported_ones(self):
        amounts = [h["2026"]["amount"] for h in self.p.values()]
        self.assertEqual((min(amounts), max(amounts)), (1085, 1280))
        self.assertEqual(round(self.d["national_weighted_average"]["2026"]), 1177)
        self.assertEqual(self.d["national_weighted_average"]["2025"], 1121)

    def test_effective_dates_fall_in_the_announced_window(self):
        dates = sorted(h["2026"]["effective_date"] for h in self.p.values())
        self.assertEqual((dates[0], dates[-1]), ("2026-10-01", "2026-12-02"))

    def test_every_prefecture_rose_this_year(self):
        for name, h in self.p.items():
            self.assertGreater(h["2026"]["amount"], h["2025"]["amount"], name)

    def test_link_is_found_on_the_page(self):
        page = (FIX / "mhlw_minwage_page.html").read_text(encoding="utf-8")
        self.assertTrue(mw.find_xlsx_url(page).endswith("/content/11200000/001753407.xlsx"))


class MinimumWageFailureTest(unittest.TestCase):
    @staticmethod
    def _workbook(rows_xml: str, strings: list[str]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/sharedStrings.xml", "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
            z.writestr("xl/worksheets/sheet1.xml", f"<worksheet><sheetData>{rows_xml}</sheetData></worksheet>")
        return buf.getvalue()

    def test_partial_data_raises_instead_of_returning_a_short_list(self):
        rows = (
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
            '<row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3"><v>1000</v></c><c r="C3"><v>46000</v></c></row>'
        )
        data = self._workbook(rows, ["年度", "令和8年度", "東京"])
        with self.assertRaises(mw.MinimumWageParseError):
            mw.parse_xlsx(data)

    def test_missing_link_raises(self):
        with self.assertRaises(mw.MinimumWageParseError):
            mw.find_xlsx_url("<a href='/x.pdf'>nothing</a>")


if __name__ == "__main__":
    unittest.main()
