"""MHLW industry-specific minimum wages (特定(産業別)最低賃金), all prefectures.

Source: the table "特定(産業別)最低賃金全国一覧" of the Ministry's minimum wage site (saiteichingin.mhlw.go.jp).  One row per prefecture and industry: the
industry's name, the hourly amount (and the daily amount where it has one), the effective date, and the mark "※" that the Ministry puts on an amount for which
the regional minimum wage applies instead.  The parser refuses partial data: every one of the 47 prefectures must have at least one row.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

from sokuhou.http import fetch
from sokuhou.sources.mhlw_minwage import PREFECTURES

PAGE = "https://saiteichingin.mhlw.go.jp/table/page_indlist_nationallist.html"
_ERA = {"昭和": 1925, "平成": 1988, "令和": 2018}


class IndustryParseError(ValueError):
    pass


def _short(name: str) -> str:
    return name if name == "北海道" else name[:-1]


def _date(text: str) -> str:
    m = re.fullmatch(r"(昭和|平成|令和)(\d+|元)\.(\d{1,2})\.(\d{1,2})", text.strip())
    if not m:
        raise IndustryParseError(f"unreadable date {text!r}")
    year = _ERA[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))
    return f"{year:04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"


def _amount(text: str) -> tuple[int | None, bool]:
    text = text.strip()
    star = "※" in text
    m = re.search(r"([\d,]+)円", text)
    return (int(m.group(1).replace(",", "")) if m else None), star


def parse(page_html: str) -> dict:
    body = re.sub(r"<!--.*?-->", "", page_html, flags=re.S)
    as_of = re.search(r"この表は(\d{4}/\d{2}/\d{2}) (\d{2}:\d{2}:\d{2})現在のもの", body)
    label = re.search(r'<th[^>]*>\s*<a [^>]*>((?:平成|令和)\d+年度)</a>\s*</th>', body)
    if not as_of:                                     # the line is the page's render time; it is only checked to be there, not stored
        raise IndustryParseError("the 'as of' line was not found")
    rows, pref = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        if len(cells) == 1 and re.fullmatch(r"北海道|.{2,3}[都府県]", cells[0]):       # the prefecture's name alone in a row (its rows follow)
            pref = _short(cells[0])
            continue
        if len(cells) == 5:
            pref = _short(cells[0])
            cells = cells[1:]
        if len(cells) != 4 or pref is None:
            continue
        industry, hourly, daily, eff = cells
        if not re.search(r"\d{1,2}\.\d{1,2}$", eff):
            continue
        h, star = _amount(hourly)
        d_, _ = _amount(daily)
        rows.append({"pref": pref, "industry": industry, "hourly": h, "daily": d_, "regional_applies": star, "effective_date": _date(eff)})
    found = {r["pref"] for r in rows}
    missing = [p for p in PREFECTURES if p not in found]
    unknown = sorted(found - set(PREFECTURES))
    if missing or unknown or len(rows) < 100:
        raise IndustryParseError(f"missing prefectures {missing}, unknown {unknown}, rows {len(rows)}")
    if any(r["hourly"] is None and r["daily"] is None for r in rows):
        raise IndustryParseError("a row without an amount")
    return {"source": PAGE, "table_label": label.group(1) if label else None, "rows": rows}


def collect() -> dict:
    out = parse(fetch(PAGE).body.decode("utf-8"))
    out["fetched_at"] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    return out
