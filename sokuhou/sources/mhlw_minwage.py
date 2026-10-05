"""MHLW regional minimum wages (地域別最低賃金).

Source: the Excel history table linked from the MHLW page. Each fiscal year occupies two columns
(amount, effective date); only the amount column carries the year header. Effective dates are Excel serials.
The parser refuses to return partial data: it raises unless all 47 prefectures and the weighted average are found.
"""
from __future__ import annotations

import html
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime, timedelta, timezone

from sokuhou.http import fetch

PAGE = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/minimumichiran/index.html"
BASE = "https://www.mhlw.go.jp"
PREFECTURES = (
    "北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 "
    "静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 "
    "熊本 大分 宮崎 鹿児島 沖縄"
).split()
_FY = re.compile(r"(平成|令和)(\d+|元)年度")  # 令和元年度 is written with 元, not 1
_ERA = {"平成": 1988, "令和": 2018}
_AVERAGE = "全国加重平均"


class MinimumWageParseError(ValueError):
    pass


def _col_to_n(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def _n_to_col(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def find_xlsx_url(page_html: str) -> str:
    for href, inner in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        text = re.sub(r"<[^>]+>", "", inner)
        if href.lower().endswith(".xlsx") and "改定状況" in text:
            return href if href.startswith("http") else BASE + href
    raise MinimumWageParseError("history workbook link not found on the MHLW page")


def _serial_to_date(v: str) -> str | None:
    if v and re.fullmatch(r"\d+(\.\d+)?", v):
        return (date(1899, 12, 30) + timedelta(days=int(float(v)))).isoformat()
    return None


def _prefecture(cell: str) -> str | None:
    s = re.sub(r"\s+", "", unicodedata.normalize("NFKC", cell))  # NFKC folds the ideographic space too
    if s.startswith(_AVERAGE):
        return _AVERAGE
    for p in PREFECTURES:
        if s.startswith(p):
            return p
    return None


def parse_xlsx(data: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    strings = [
        html.unescape(re.sub(r"<[^>]+>", "", si))
        for si in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S)
    ]
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")

    def cells(row: str) -> dict[str, str]:
        out = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
            v = re.search(r"<v>(.*?)</v>", m.group(3) or "", re.S)
            if v:
                out[m.group(1)] = strings[int(v.group(1))] if 't="s"' in m.group(2) else v.group(1)
        return out

    rows = [cells(r) for r in re.findall(r"<row [^>]*>(.*?)</row>", sheet, re.S)]
    years: dict[int, tuple[str, str, str]] = {}  # fiscal year -> (label, amount col, effective col)
    for col, text in rows[0].items():
        m = _FY.search(unicodedata.normalize("NFKC", text))
        if m:
            nth = 1 if m.group(2) == "元" else int(m.group(2))
            fy = _ERA[m.group(1)] + nth
            years[fy] = (f"{m.group(1)}{m.group(2)}年度", col, _n_to_col(_col_to_n(col) + 1))
    if not years:
        raise MinimumWageParseError("no fiscal-year headers found")

    prefectures: dict[str, dict] = {}
    average: dict[str, float] = {}
    for row in rows[1:]:
        name = _prefecture(row.get("A", ""))
        if not name:
            continue
        for fy, (label, amt_col, eff_col) in years.items():
            raw = row.get(amt_col)
            if raw is None or not re.fullmatch(r"\d+(\.\d+)?", raw):
                continue
            if name == _AVERAGE:
                average[str(fy)] = round(float(raw), 2)
            else:
                prefectures.setdefault(name, {})[str(fy)] = {
                    "amount": int(float(raw)),
                    "effective_date": _serial_to_date(row.get(eff_col, "")),
                }
    latest = max(years)
    missing = [p for p in PREFECTURES if str(latest) not in prefectures.get(p, {})]
    if missing or str(latest) not in average:
        raise MinimumWageParseError(f"incomplete data for {latest}: missing={missing}, average={str(latest) in average}")
    return {
        "latest_fiscal_year": latest,
        "fiscal_year_labels": {str(fy): v[0] for fy, v in years.items()},
        "prefectures": [{"name": p, "history": prefectures[p]} for p in PREFECTURES],
        "national_weighted_average": average,
    }


def collect() -> dict:
    page = fetch(PAGE).body.decode("utf-8", errors="replace")
    url = find_xlsx_url(page)
    out = parse_xlsx(fetch(url).body)
    out.update({"source_page": PAGE, "source_file": url, "fetched_at": datetime.now(timezone(timedelta(hours=9))).isoformat()})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
