import io
import re
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou.sources import estat_wage as wage

FIX = Path(__file__).parent / "fixtures"
WBOOK = FIX / "estat_wage_ref1.xlsx"

EXPECTED_PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 "
    "新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 "
    "奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 "
    "長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()


def _by_name(data):
    return {p["name"]: p for p in data["prefectures"]}


def _replace_xlsx(data: bytes, replacements: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename in replacements:
                content = replacements[item.filename].encode("utf-8")
            zout.writestr(item, content)
    return buf.getvalue()


def _set_cell(data: bytes, sheet: str, cell: str, value: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read(sheet).decode("utf-8")

    pattern = rf'(<c r="{cell}"[^>]*><v>)(.*?)(</v></c>)'
    xml, n = re.subn(pattern, lambda m: m.group(1) + value + m.group(3), xml, count=1)
    if n != 1:
        raise AssertionError(f"{cell} was not found")
    return _replace_xlsx(data, {sheet: xml})


def _remove_row(data: bytes, sheet: str, row: int) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read(sheet).decode("utf-8")
    xml, n = re.subn(rf'<row[^>]*r="{row}"[^>]*>.*?</row>', "", xml, count=1, flags=re.S)
    if n != 1:
        raise AssertionError(f"row {row} was not found")
    return _replace_xlsx(data, {sheet: xml})


class EstatWageSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.raw = WBOOK.read_bytes()
        self.d = wage.parse_xlsx(self.raw)
        self.p = _by_name(self.d)

    def test_year_label_and_prefecture_order(self):
        self.assertEqual(self.d["year_label"], "令和7年")
        self.assertEqual(len(self.d["prefectures"]), 47)
        self.assertEqual([p["name"] for p in self.d["prefectures"]], EXPECTED_PREFECTURES)

    def test_known_national_and_prefecture_values(self):
        self.assertEqual(self.d["national"]["scheduled_pay_k"], 340.6)
        self.assertEqual(self.d["national"]["total_cash_k"], 370.5)
        self.assertEqual(self.d["national"]["bonus_k"], 1009.6)

        tokyo = self.p["東京都"]
        self.assertEqual(tokyo["scheduled_pay_k"], 418.3)
        self.assertEqual(tokyo["total_cash_k"], 448.5)
        self.assertEqual(tokyo["bonus_k"], 1397.8)
        self.assertEqual(tokyo["scheduled_hours"], 159)

        okinawa = self.p["沖縄県"]
        self.assertEqual(okinawa["scheduled_pay_k"], 277.4)
        self.assertEqual(okinawa["total_cash_k"], 294.8)
        self.assertEqual(okinawa["bonus_k"], 576.8)

    def test_sex_specific_pay_fields_are_included(self):
        self.assertEqual(self.d["national"]["male"]["scheduled_pay_k"], 373.4)
        self.assertEqual(self.d["national"]["female"]["scheduled_pay_k"], 285.9)
        self.assertEqual(self.p["東京都"]["male"]["total_cash_k"], 493.1)
        self.assertEqual(self.p["東京都"]["female"]["bonus_k"], 1020.3)

    def test_men_plus_women_equal_all_workers_within_rounding(self):
        # Independent of the column layout: the male and female blocks must add up to the all-worker block.
        # The source rounds each block separately, so a difference of one (ten workers) is allowed.
        for rec in [self.d["national"], *self.d["prefectures"]]:
            gap = rec["male"]["workers_x10"] + rec["female"]["workers_x10"] - rec["workers_x10"]
            self.assertLessEqual(abs(gap), 1, rec.get("name", "全国"))
        self.assertGreater(self.d["national"]["male"]["scheduled_pay_k"], self.d["national"]["female"]["scheduled_pay_k"])

    def test_worker_weighted_prefecture_means_reproduce_the_national_figures(self):
        total = sum(p["workers_x10"] for p in self.d["prefectures"])
        for key, tolerance in (("scheduled_pay_k", 0.2), ("total_cash_k", 0.2), ("bonus_k", 1.0)):
            mean = sum(p[key] * p["workers_x10"] for p in self.d["prefectures"]) / total
            self.assertAlmostEqual(mean, self.d["national"][key], delta=tolerance, msg=key)

    def test_collect_adds_source_metadata_without_network(self):
        with mock.patch.object(wage, "fetch", lambda url: SimpleNamespace(body=self.raw)):
            out = wage.collect()
        self.assertEqual(out["source_file"], wage.SOURCE_FILE)
        self.assertEqual(out["source_page"], wage.SOURCE_PAGE)
        self.assertRegex(out["fetched_at"], r"\+09:00$")
        self.assertEqual(out["national"]["scheduled_pay_k"], 340.6)


class EstatWageFailureTest(unittest.TestCase):
    def setUp(self):
        self.raw = WBOOK.read_bytes()

    def test_title_must_be_the_wage_structure_survey(self):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            strings = z.read("xl/sharedStrings.xml").decode("utf-8")
        strings = strings.replace("賃金構造基本統計調査", "別調査")
        with self.assertRaisesRegex(ValueError, "title"):
            wage.parse_xlsx(_replace_xlsx(self.raw, {"xl/sharedStrings.xml": strings}))

    def test_value_ranges_are_checked(self):
        with self.assertRaisesRegex(ValueError, "scheduled_pay_k"):
            wage.parse_xlsx(_set_cell(self.raw, "xl/worksheets/sheet1.xml", "J26", "700"))
        with self.assertRaisesRegex(ValueError, "bonus_k"):
            wage.parse_xlsx(_set_cell(self.raw, "xl/worksheets/sheet1.xml", "K26", "4000"))
        with self.assertRaisesRegex(ValueError, "scheduled_hours"):
            wage.parse_xlsx(_set_cell(self.raw, "xl/worksheets/sheet1.xml", "G26", "80"))

    def test_total_cash_cannot_be_below_scheduled_pay(self):
        with self.assertRaisesRegex(ValueError, "total_cash_k"):
            wage.parse_xlsx(_set_cell(self.raw, "xl/worksheets/sheet1.xml", "I26", "100"))

    def test_missing_prefecture_row_raises(self):
        with self.assertRaisesRegex(ValueError, "not exactly 47 prefectures"):
            wage.parse_xlsx(_remove_row(self.raw, "xl/worksheets/sheet1.xml", 60))

    def test_extra_prefecture_row_raises(self):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        duplicate = (
            '<row r="13"><c r="C13" t="s"><v>16</v></c><c r="E13"><v>45.8</v></c>'
            '<c r="F13"><v>12</v></c><c r="G13"><v>162</v></c><c r="H13"><v>11</v></c>'
            '<c r="I13"><v>322.8</v></c><c r="J13"><v>297.1</v></c><c r="K13"><v>792</v></c>'
            '<c r="L13"><v>105134</v></c></row>'
        )
        xml, n = re.subn(r'<row[^>]*r="13"[^>]*>.*?</row>', duplicate, xml, count=1, flags=re.S)
        self.assertEqual(n, 1)
        with self.assertRaisesRegex(ValueError, "not exactly 47 prefectures"):
            wage.parse_xlsx(_replace_xlsx(self.raw, {"xl/worksheets/sheet1.xml": xml}))


if __name__ == "__main__":
    unittest.main()
