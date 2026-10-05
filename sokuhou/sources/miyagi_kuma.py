"""Miyagi prefecture bear sighting table (令和8年度クマ目撃等情報).

The source workbook is parsed as OOXML directly with zipfile/xml.  The current public
file has one future-dated row relative to the stated as-of date; monthly totals are
checked against the prefecture's summary sheet with that row included, and the count is
surfaced as dates_after_as_of.
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from sokuhou.http import fetch

PAGE = "https://www.pref.miyagi.jp/soshiki/sizenhogo/r8kumamokugeki.html"
CREDIT = "出典:宮城県「令和8年度クマ目撃等情報」を加工して作成"
UPDATE_NOTE = "宮城県が、市町村からの報告を取りまとめて、更新します(ほぼ毎日)"
MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_DATA_SHEETS = ("公表用シート（報告順）", "公表用シート（目撃順）")
_SUMMARY_SHEET = "市町村別・月別一覧"


class MiyagiKumaParseError(ValueError):
    pass


def find_xlsx_url(page_html: str) -> str:
    m = re.search(r"""href\s*=\s*["']\s*([^"']*koukaiyou_\d+\.xlsx)\s*["']""", page_html)
    if not m:
        raise MiyagiKumaParseError("Miyagi workbook link koukaiyou_*.xlsx not found")
    return urljoin(PAGE, m.group(1).strip())


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall(_NS + "si"):
        parts: list[str] = []
        direct = si.find(_NS + "t")
        if direct is not None and direct.text:
            parts.append(direct.text)
        for run in si.findall(_NS + "r"):
            text = run.find(_NS + "t")
            if text is not None and text.text:
                parts.append(text.text)
        strings.append("".join(parts))
    return strings


def _cell_value(cell: ET.Element, strings: list[str]) -> str:
    value = cell.find(_NS + "v")
    if value is not None and value.text is not None:
        return strings[int(value.text)] if cell.attrib.get("t") == "s" else value.text
    inline = cell.find(_NS + "is/" + _NS + "t")
    return inline.text if inline is not None and inline.text is not None else ""


def _sheet_paths(z: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    by_id = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(_PKG_REL_NS + "Relationship")}
    out = {}
    sheets = workbook.find(_NS + "sheets")
    if sheets is None:
        raise MiyagiKumaParseError("workbook sheets element not found")
    for sheet in sheets:
        rel_id = sheet.attrib[_REL_NS + "id"]
        target = by_id[rel_id]
        out[sheet.attrib["name"]] = "xl/" + target.lstrip("/")
    return out


def _sheet_rows(z: zipfile.ZipFile, path: str, strings: list[str]) -> list[dict[str, str]]:
    root = ET.fromstring(z.read(path))
    rows: list[dict[str, str]] = []
    for row in root.findall(".//" + _NS + "row"):
        out: dict[str, str] = {}
        for cell in row.findall(_NS + "c"):
            col = re.match(r"[A-Z]+", cell.attrib["r"])
            if col:
                out[col.group(0)] = _cell_value(cell, strings)
        rows.append(out)
    return rows


def _as_of(rows: list[dict[str, str]]) -> date:
    text = rows[1].get("A", "") if len(rows) > 1 else ""
    m = re.search(r"令和(\d+)年(\d+)月(\d+)日", unicodedata.normalize("NFKC", text))
    if not m:
        raise MiyagiKumaParseError("as-of date not found in row 2")
    return date(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _check_data_header(rows: list[dict[str, str]], label: str) -> None:
    if len(rows) < 5:
        raise MiyagiKumaParseError(f"{label}: sheet has too few rows")
    expected_3 = {"A": "番号", "B": "発見日時", "E": "事務所", "F": "市区町村", "G": "地区", "H": "発見頭数", "I": "痕跡", "J": "市街地判定"}
    expected_4 = {"B": "月", "C": "日", "D": "時刻"}
    for col, text in expected_3.items():
        if rows[2].get(col) != text:
            raise MiyagiKumaParseError(f"{label}: changed header at {col}3")
    for col, text in expected_4.items():
        if rows[3].get(col) != text:
            raise MiyagiKumaParseError(f"{label}: changed header at {col}4")


def _numbered_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if re.fullmatch(r"\d+", r.get("A", ""))]


def _fy_start(as_of: date) -> int:
    return as_of.year if as_of.month >= 4 else as_of.year - 1


def _fy_label(year: int) -> str:
    return f"R{year - 2018:02d}"


def _observed_date(month: int, day: int, fy_start: int) -> date:
    return date(fy_start if month >= 4 else fy_start + 1, month, day)


def _observed_at(day: date, raw_time: str) -> str:
    try:
        fraction = float(raw_time)
    except (TypeError, ValueError):
        return day.isoformat()
    minutes = round(fraction * 24 * 60)
    if minutes >= 24 * 60:
        minutes = 24 * 60 - 1
    t = time(minutes // 60, minutes % 60)
    return datetime.combine(day, t, timezone(timedelta(hours=9))).isoformat()


def _count(raw: str) -> int | None:
    text = unicodedata.normalize("NFKC", raw or "")
    m = re.search(r"(\d+)\s*頭", text)
    return int(m.group(1)) if m else None


def _summary_monthly(rows: list[dict[str, str]]) -> dict[str, int]:
    header = next((row for row in rows if row.get("B") == "市町村名"), None)
    if header is None or [header.get(c) for c in "CDEFGHIJKLMN"] != [str(m) for m in MONTHS]:
        raise MiyagiKumaParseError("summary sheet month header changed")
    for row in rows:
        if row.get("B", "").startswith("月別計"):
            monthly = {str(month): int(float(row[col])) for month, col in zip(MONTHS, "CDEFGHIJKLMN", strict=True)}
            total = int(float(row.get("O", "0")))
            if sum(monthly.values()) != total:
                raise MiyagiKumaParseError(f"summary monthly total {sum(monthly.values())} does not equal grand total {total}")
            return monthly
    raise MiyagiKumaParseError("summary sheet 月別計 row not found")


def _monthly_from_rows(rows: list[dict[str, str]], fy_start: int) -> dict[str, int]:
    out = {str(m): 0 for m in MONTHS}
    for row in rows:
        month = int(float(row["B"]))
        day = int(float(row["C"]))
        _observed_date(month, day, fy_start)  # refuses impossible dates
        out[str(month)] = out.get(str(month), 0) + 1
    return out


def parse_xlsx(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        strings = _shared_strings(z)
        paths = _sheet_paths(z)
        missing = [name for name in (*_DATA_SHEETS, _SUMMARY_SHEET) if name not in paths]
        if missing:
            raise MiyagiKumaParseError(f"required sheet(s) missing: {missing}")
        report_rows = _sheet_rows(z, paths[_DATA_SHEETS[0]], strings)
        sight_order_rows = _sheet_rows(z, paths[_DATA_SHEETS[1]], strings)
        summary_rows = _sheet_rows(z, paths[_SUMMARY_SHEET], strings)

    for label, rows in (("report order", report_rows), ("sighting order", sight_order_rows)):
        _check_data_header(rows, label)
    as_of = _as_of(report_rows)
    if _as_of(sight_order_rows) != as_of:
        raise MiyagiKumaParseError("as-of dates differ between data sheets")

    report_data = _numbered_rows(report_rows)
    sight_order_data = _numbered_rows(sight_order_rows)
    if len(report_data) != len(sight_order_data):
        raise MiyagiKumaParseError(f"data sheet row counts differ: report={len(report_data)} sighting={len(sight_order_data)}")
    report_ids = {row["A"] for row in report_data}
    sight_ids = {row["A"] for row in sight_order_data}
    if report_ids != sight_ids:
        raise MiyagiKumaParseError("numbered rows differ between report and sighting order sheets")
    if any(not row.get("F", "").strip() for row in report_data):
        raise MiyagiKumaParseError("municipality name is empty")

    fy_start = _fy_start(as_of)
    fy_current = _fy_label(fy_start)
    computed = _monthly_from_rows(report_data, fy_start)
    summary = _summary_monthly(summary_rows)
    if computed != summary:
        raise MiyagiKumaParseError(f"monthly totals differ: rows={computed}, summary={summary}")

    sightings_by_id: dict[str, dict] = {}
    dates_after_as_of = 0
    after_by_month: dict[str, int] = {}
    for row in report_data:
        month, day = int(float(row["B"])), int(float(row["C"]))
        observed_date = _observed_date(month, day, fy_start)
        if observed_date > as_of:
            dates_after_as_of += 1
            after_by_month[str(month)] = after_by_month.get(str(month), 0) + 1
        sightings_by_id[row["A"]] = {
            "observed_at": _observed_at(observed_date, row.get("D", "")),
            "city": row["F"].strip(),
            "place": row.get("G", "").strip(),
            "count": _count(row.get("H", "")),
            "kind": row.get("I", "").strip(),
            "species": "クマ",
        }

    order = {row["A"]: i for i, row in enumerate(sight_order_data)}
    sightings = sorted(sightings_by_id.items(), key=lambda item: order[item[0]])

    return {
        "source": "miyagi",
        "credit": CREDIT,
        "as_of": as_of.isoformat(),
        "update_note": UPDATE_NOTE,
        "fy_current": fy_current,
        "sightings": [rec for _, rec in sightings],
        "monthly": {fy_current: summary},
        "dates_after_as_of": dates_after_as_of,
        "dates_after_as_of_by_month": after_by_month,
        "monthly_note": "月別計は公表表の全行で検算し、as_of後の日付も含みます",
    }


def collect() -> dict:
    page = fetch(PAGE).body.decode("utf-8", errors="replace")
    url = find_xlsx_url(page)
    out = parse_xlsx(fetch(url).body)
    out.update({
        "source_page": PAGE,
        "source_file": url,
        "fetched_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    })
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
