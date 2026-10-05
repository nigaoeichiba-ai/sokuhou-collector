import io
import re
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou.sources import miyagi_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
WBOOK = FIX / "miyagi_kuma_r8.xlsx"


def _replace_xlsx(data: bytes, replacements: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            content = replacements.get(item.filename, zin.read(item.filename))
            if isinstance(content, str):
                content = content.encode("utf-8")
            zout.writestr(item, content)
    return buf.getvalue()


def _remove_row(data: bytes, sheet: str, row: int) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read(sheet).decode("utf-8")
    xml, n = re.subn(rf'<row[^>]*r="{row}"[^>]*>.*?</row>', "", xml, count=1, flags=re.S)
    if n != 1:
        raise AssertionError(f"row {row} was not found")
    return _replace_xlsx(data, {sheet: xml})


class MiyagiKumaSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.raw = WBOOK.read_bytes()
        self.d = kuma.parse_xlsx(self.raw)

    def test_as_of_first_reported_row_and_future_date_note(self):
        self.assertEqual(self.d["as_of"], "2026-10-05")
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertEqual(self.d["dates_after_as_of"], 1)
        self.assertEqual(self.d["dates_after_as_of_by_month"], {"10": 1})
        self.assertEqual(self.d["sightings"][-1], {
            "observed_at": "2026-04-01T07:00:00+09:00",
            "city": "仙台市青葉区",
            "place": "錦ケ丘中央",
            "count": 1,
            "kind": "目撃",
            "species": "クマ",
        })

    def test_month_counts_match_the_summary_sheet(self):
        monthly = self.d["monthly"]["R08"]
        self.assertEqual(monthly["4"], 141)
        self.assertEqual(monthly["5"], 318)
        self.assertEqual(monthly["6"], 347)
        self.assertEqual(monthly["7"], 222)
        self.assertEqual(monthly["8"], 132)
        self.assertEqual(monthly["9"], 129)
        self.assertEqual(monthly["10"], 13)
        self.assertEqual(sum(monthly.values()), 1302)
        self.assertEqual(len(self.d["sightings"]), 1302)

    def test_link_finder(self):
        html = '<a href=" /documents/64667/koukaiyou_20261005.xlsx ">Excel</a>'
        self.assertEqual(kuma.find_xlsx_url(html), "https://www.pref.miyagi.jp/documents/64667/koukaiyou_20261005.xlsx")

    def test_collect_without_network(self):
        page = b'<a href="/documents/64667/koukaiyou_20261005.xlsx">x</a>'

        def fake(url):
            return SimpleNamespace(body=page if url == kuma.PAGE else self.raw)

        with mock.patch.object(kuma, "fetch", fake):
            out = kuma.collect()
        self.assertEqual(out["source"], "miyagi")
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertTrue(out["source_file"].endswith("/documents/64667/koukaiyou_20261005.xlsx"))
        self.assertRegex(out["fetched_at"], r"\+09:00$")
        self.assertEqual(out["monthly"]["R08"]["10"], 13)


class MiyagiKumaFailureTest(unittest.TestCase):
    def setUp(self):
        self.raw = WBOOK.read_bytes()

    def test_deleted_data_row_is_refused(self):
        bad = _remove_row(self.raw, "xl/worksheets/sheet1.xml", 5)
        with self.assertRaisesRegex(kuma.MiyagiKumaParseError, "row counts differ"):
            kuma.parse_xlsx(bad)

    def test_changed_header_is_refused(self):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            strings = z.read("xl/sharedStrings.xml").decode("utf-8")
        strings = strings.replace(">番号<", ">通番<", 1)
        with self.assertRaisesRegex(kuma.MiyagiKumaParseError, "changed header"):
            kuma.parse_xlsx(_replace_xlsx(self.raw, {"xl/sharedStrings.xml": strings}))


if __name__ == "__main__":
    unittest.main()
