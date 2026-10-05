"""e-Stat wage structure survey reference table 1 (賃金構造基本統計調査).

The source workbook is a simple OOXML .xlsx file.  We parse the ZIP/XML directly so the collector
keeps the same stdlib-only footprint as the other sources.
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from sokuhou.http import fetch

SOURCE_FILE = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040421202&fileKind=4"
SOURCE_PAGE = "https://www.e-stat.go.jp/stat-search/files?tclass=000001229518&cycle=0"
PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 "
    "新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 "
    "奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 "
    "長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_PAY_COLUMNS = {
    "age": "E",
    "tenure_years": "F",
    "scheduled_hours": "G",
    "overtime_hours": "H",
    "total_cash_k": "I",
    "scheduled_pay_k": "J",
    "bonus_k": "K",
    "workers_x10": "L",
}
_MALE_COLUMNS = _PAY_COLUMNS
_FEMALE_COLUMNS = {
    "age": "M",
    "tenure_years": "N",
    "scheduled_hours": "O",
    "overtime_hours": "P",
    "total_cash_k": "Q",
    "scheduled_pay_k": "R",
    "bonus_k": "S",
    "workers_x10": "T",
}


class EstatWageParseError(ValueError):
    pass


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


_PREF_BY_KEY: dict[str, str] = {}
for _pref in PREFECTURES:
    _PREF_BY_KEY[_compact(_pref)] = _pref
    _PREF_BY_KEY[_compact(re.sub(r"[都府県]$", "", _pref))] = _pref


def _prefecture(cell: str) -> str | None:
    s = _compact(cell)
    if s == "全国":
        return "全国"
    return _PREF_BY_KEY.get(s)


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
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


def _cell_value(cell: ET.Element, strings: list[str]) -> str | None:
    value = cell.find(_NS + "v")
    if value is None or value.text is None:
        inline = cell.find(_NS + "is/" + _NS + "t")
        return inline.text if inline is not None else None
    if cell.attrib.get("t") == "s":
        return strings[int(value.text)]
    return value.text


def _sheet_rows(z: zipfile.ZipFile, path: str, strings: list[str]) -> list[dict[str, str]]:
    root = ET.fromstring(z.read(path))
    rows: list[dict[str, str]] = []
    for row in root.findall(".//" + _NS + "row"):
        out: dict[str, str] = {}
        for cell in row.findall(_NS + "c"):
            value = _cell_value(cell, strings)
            if value is None:
                continue
            col = re.match(r"[A-Z]+", cell.attrib["r"])
            if col:
                out[col.group(0)] = value
        rows.append(out)
    return rows


def _num(row: dict[str, str], col: str, name: str) -> float | int:
    try:
        value = float(row[col])
    except KeyError as e:
        raise EstatWageParseError(f"missing {name} value in column {col}") from e
    if name in {"scheduled_hours", "overtime_hours", "workers_x10"}:
        return int(value)
    return round(value, 1)


def _record(row: dict[str, str], columns: dict[str, str]) -> dict:
    return {name: _num(row, col, name) for name, col in columns.items()}


def _title(rows: list[dict[str, str]]) -> str:
    for row in rows[:5]:
        for value in row.values():
            if "賃金構造基本統計調査" in value:
                return value
    raise EstatWageParseError("title does not contain 賃金構造基本統計調査")


def _year_label(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title)
    m = re.search(r"(令和\d+年)", normalized)
    if not m:
        raise EstatWageParseError(f"year label not found in title: {title}")
    return m.group(1)


def _all_worker_rows(rows: list[dict[str, str]]) -> tuple[dict, list[dict]]:
    national = None
    prefectures: list[dict] = []
    for row in rows:
        name = _prefecture(row.get("C", ""))
        if not name:
            continue
        rec = _record(row, _PAY_COLUMNS)
        if name == "全国":
            national = rec
        else:
            rec["name"] = name
            prefectures.append(rec)
    if national is None:
        raise EstatWageParseError("national row not found")
    return national, prefectures


def _sex_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for row in rows:
        name = _prefecture(row.get("C", ""))
        if not name:
            continue
        out[name] = {
            "male": _record(row, _MALE_COLUMNS),
            "female": _record(row, _FEMALE_COLUMNS),
        }
    return out


def _check_record(record: dict, label: str) -> None:
    scheduled = record["scheduled_pay_k"]
    bonus = record["bonus_k"]
    hours = record["scheduled_hours"]
    if not 150 <= scheduled <= 600:
        raise EstatWageParseError(f"{label} scheduled_pay_k out of plausible range: {scheduled}")
    if not 0 <= bonus <= 3000:
        raise EstatWageParseError(f"{label} bonus_k out of plausible range: {bonus}")
    if not 100 <= hours <= 200:
        raise EstatWageParseError(f"{label} scheduled_hours out of plausible range: {hours}")
    if record["total_cash_k"] < scheduled:
        raise EstatWageParseError(f"{label} total_cash_k is below scheduled_pay_k")


def _sanity_check(out: dict) -> None:
    prefs = out["prefectures"]
    if len(prefs) != 47:
        raise EstatWageParseError(f"not exactly 47 prefectures: {len(prefs)}")
    names = [p["name"] for p in prefs]
    if names != PREFECTURES:
        raise EstatWageParseError(f"prefectures are not in JIS order: {names}")

    _check_record(out["national"], "national")
    for sex in ("male", "female"):
        _check_record(out["national"][sex], f"national {sex}")
    for pref in prefs:
        _check_record(pref, pref["name"])
        for sex in ("male", "female"):
            _check_record(pref[sex], f"{pref['name']} {sex}")


def parse_xlsx(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        strings = _shared_strings(z)
        all_rows = _sheet_rows(z, "xl/worksheets/sheet1.xml", strings)
        sex_rows = _sex_rows(_sheet_rows(z, "xl/worksheets/sheet2.xml", strings))

    title = _title(all_rows)
    national, prefectures = _all_worker_rows(all_rows)
    for rec in [national, *prefectures]:
        sex = sex_rows.get(rec.get("name", "全国"))
        if sex is None:
            raise EstatWageParseError(f"sex-specific row missing for {rec.get('name', '全国')}")
        rec.update(sex)

    out = {"year_label": _year_label(title), "national": national, "prefectures": prefectures}
    _sanity_check(out)
    return out


def collect() -> dict:
    out = parse_xlsx(fetch(SOURCE_FILE).body)
    out.update({
        "source_file": SOURCE_FILE,
        "source_page": SOURCE_PAGE,
        "fetched_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    })
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
