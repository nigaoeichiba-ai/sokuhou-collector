"""Bear sightings and injuries by prefecture, from the Ministry of the Environment's PDF tables.

Source page: https://www.env.go.jp/nature/choju/effort/effort12/effort12.html (public data licence 1.0:
credit the ministry and say the data was processed). Both PDFs are Excel exports with real text, so the cells are
read by position (pypdf's text visitor gives each cell's x/y). Figures are provisional ("速報値") and are
revised later; the tables are checked against their own totals so a changed layout is refused, not guessed.

  syutubotu.pdf   sightings: per prefecture, per month (Apr..Mar), for the last five fiscal years
  injury-qe.pdf   injuries: per prefecture and fiscal year (cases, people injured, deaths), Heisei 20 onwards
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

from sokuhou.http import fetch
from sokuhou.prefectures import SHORT

BASE = "https://www.env.go.jp/nature/choju/effort/effort12/"
PAGE = BASE + "effort12.html"
SIGHTINGS_PDF = BASE + "syutubotu.pdf"
INJURIES_PDF = BASE + "injury-qe.pdf"
MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
_SHORT = set(SHORT)
# The ministry's tables list Hokkaido to Kochi only (39 prefectures) and a national row; Fukuoka to Okinawa are not in them.
LISTED = SHORT[:39]
_DIGIT, _COMMA, _DASH, _WIDE = 0.515, 0.25, 0.3, 1.0  # advance widths in em (the tables use Calibri-like digits)


class EnvKumaError(ValueError):
    pass


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip()


def _advance(text: str, fs: float) -> float:
    w = 0.0
    for ch in text:
        w += _DIGIT if ch.isdigit() else _COMMA if ch in ",." else _DASH if ch == "-" else _WIDE
    return w * fs


def _tokens(pdf: bytes, page_no: int) -> list[dict]:
    from pypdf import PdfReader  # imported here so the other collectors and their tests do not need it

    page = PdfReader(io.BytesIO(pdf)).pages[page_no]
    out: list[dict] = []

    def visit(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if t:
            out.append({"x": tm[4], "y": tm[5], "text": t, "fs": font_size})

    page.extract_text(visitor_text=visit)
    return out


def _number(text: str):
    """int, None for a dash (no data), or raise: a cell that is neither is a layout change."""
    t = _nfkc(text).replace(",", "")
    if re.fullmatch(r"\d+", t):
        return int(t)
    if t in ("-", "－", "—", "ー"):
        return None
    raise EnvKumaError(f"unexpected cell {text!r}")


def _jp_date(tokens: list[dict]) -> str:
    for t in tokens:
        m = re.fullmatch(r"令和(\d+)年(\d+)月(\d+)日", _nfkc(t["text"]))
        if m:
            return f"{2018 + int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    raise EnvKumaError("update date not found")


def _label_column(tokens: list[dict]) -> tuple[float, float]:
    xs = [t["x"] for t in tokens if _nfkc(t["text"]) in _SHORT]
    if len(xs) < 30:
        raise EnvKumaError("prefecture label column not found")
    return min(xs) - 3, max(xs) + 10  # labels are centred, so their left edges differ by name length


def _rows(tokens: list[dict], label_x_range: tuple[float, float], below: float | None = None) -> list[dict]:
    """Rows keyed by a label cell (a prefecture's short name or 計) inside the label column."""
    lo, hi = label_x_range
    rows = []
    for t in tokens:
        name = _nfkc(t["text"])
        if lo <= t["x"] <= hi and (name in _SHORT or name in ("計", "合計")):
            if below is not None and t["y"] <= below:
                continue  # rows under the "reprint" title repeat the table for one species
            cells = [c for c in tokens if abs(c["y"] - t["y"]) <= 3 and c["x"] > t["x"] + 3 and c is not t]
            rows.append({"name": "計" if name in ("計", "合計") else name, "y": t["y"], "cells": cells})
    return rows


def parse_sightings(pdf: bytes) -> dict:
    tokens = _tokens(pdf, 0)
    updated = _jp_date(tokens)
    heads = sorted((t for t in tokens if re.fullmatch(r"R0[4-8]", _nfkc(t["text"]))), key=lambda t: t["x"])
    if len(heads) != 65 or len({round(t["y"], 0) for t in heads}) != 1:
        raise EnvKumaError(f"sightings table: expected 65 year headers in one row, found {len(heads)}")
    years = [_nfkc(t["text"]) for t in heads[:5]]
    if [_nfkc(t["text"]) for t in heads] != years * 13:
        raise EnvKumaError("sightings table: year headers are not five years repeated for 12 months and the total")
    # A cell's right edge sits about 24 px right of its header's left edge (numbers are right aligned).
    right = [t["x"] + 24.0 for t in heads]
    rows = _rows(tokens, _label_column(tokens))
    result = []
    for row in rows:
        grid: list = [None] * 65
        for c in row["cells"]:
            if c["x"] < right[0] - 40 or _nfkc(c["text"]) in ("-", "－"):
                continue  # not a data cell, or a dash (no data)
            re_ = c["x"] + _advance(c["text"], c["fs"])
            j = min(range(65), key=lambda k: abs(right[k] - re_))
            # A zero in the national row sits about 11 px left of the usual right edge; columns are 31 px apart.
            if abs(right[j] - re_) > (14 if _nfkc(c["text"]) == "0" else 8):
                raise EnvKumaError(f"{row['name']}: cell {c['text']!r} fits no column")
            if grid[j] is not None:
                raise EnvKumaError(f"{row['name']}: two cells in one column ({c['text']!r})")
            grid[j] = _number(c["text"])  # None for a dash: no data in that cell
        monthly = {}
        total = {}
        for ki, y in enumerate(years):
            vals = [grid[g * 5 + ki] for g in range(12)]
            monthly[y] = vals
            total[y] = grid[12 * 5 + ki]
        result.append({"name": row["name"], "monthly": monthly, "total": total})
    names = [r["name"] for r in result]
    if names != LISTED + ["計"]:
        raise EnvKumaError(f"sightings table: rows are {names}")
    national = result.pop()
    for r in result + [national]:
        for y in years:
            have = [v for v in r["monthly"][y] if v is not None]
            tot = r["total"][y]
            if tot is None:
                if have:
                    raise EnvKumaError(f"{r['name']} {y}: months without a total")
            elif sum(have) != tot:
                raise EnvKumaError(f"{r['name']} {y}: months add up to {sum(have)}, the total says {tot}")
    for y in years:
        for mi in range(12):
            col = [r["monthly"][y][mi] for r in result]
            if any(v is not None for v in col) and sum(v or 0 for v in col) != (national["monthly"][y][mi] or 0):
                raise EnvKumaError(f"{y} month {MONTHS[mi]}: prefectures do not add up to the national row")
        if sum(r["total"][y] or 0 for r in result) != (national["total"][y] or 0):
            raise EnvKumaError(f"{y}: prefecture totals do not add up to the national total")
    latest = None
    for mi in range(12):
        if any(r["monthly"][years[-1]][mi] is not None for r in result):
            latest = MONTHS[mi]
    return {"updated": updated, "years": years, "months": MONTHS, "latest_month": latest,
            "prefectures": result, "national": national}


def _cluster(values: list[float], gap: float = 6.0) -> list[float]:
    """Centres of groups of values that lie within `gap` of their neighbour."""
    values = sorted(values)
    groups: list[list[float]] = [[values[0]]]
    for v in values[1:]:
        if v - groups[-1][-1] <= gap:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def parse_injuries(pdf: bytes) -> dict:
    """Both pages; each fiscal year has three columns: cases, people injured, deaths."""
    by_year: dict[str, dict[str, list]] = {}
    national: dict[str, list] = {}
    updated = None
    as_of = None
    for page_no in (0, 1):
        tokens = _tokens(pdf, page_no)
        updated = updated or _jp_date(tokens)
        for t in tokens:
            m = re.search(r"\((R\d+年\d+月末)\)", _nfkc(t["text"]))
            if m:
                as_of = m.group(1)
        reprint = [t["y"] for t in tokens if "再" in t["text"] and "掲" in t["text"]]
        below = max(reprint) if reprint else None  # the "reprint" block below repeats the table for one species
        heads = sorted((t for t in tokens if re.fullmatch(r"[HR]\d+年度", _nfkc(t["text"]))
                        and (below is None or t["y"] > below)), key=lambda t: t["x"])
        labels = [_nfkc(t["text"]).replace("年度", "") for t in heads]  # "R07年度" -> "R07"
        if not heads:
            raise EnvKumaError(f"injury table page {page_no + 1}: headers not found")
        column = _label_column(tokens)
        rows = _rows(tokens, column, below)
        first = column[1]
        edges = [c["x"] + _advance(c["text"], c["fs"]) for r in rows for c in r["cells"] if c["x"] > first + 10]
        cols = _cluster(edges)
        if len(cols) != 3 * len(labels):
            raise EnvKumaError(f"injury table page {page_no + 1}: {len(cols)} columns for {len(labels)} years")
        for row in rows:
            vals: list = [None] * len(cols)
            for c in row["cells"]:
                if c["x"] <= first + 10:
                    continue
                re_ = c["x"] + _advance(c["text"], c["fs"])
                j = min(range(len(cols)), key=lambda k: abs(cols[k] - re_))
                vals[j] = _number(c["text"])
            for yi, label in enumerate(labels):
                triple = vals[yi * 3: yi * 3 + 3]
                if any(v is None for v in triple):
                    raise EnvKumaError(f"{row['name']} {label}: incomplete injury cells {triple}")
                (national if row["name"] == "計" else by_year.setdefault(row["name"], {}))[label] = triple
    names = list(by_year)
    if names != LISTED:
        raise EnvKumaError(f"injury table: rows are {names}")
    years = list(next(iter(by_year.values())))
    for y in years:
        for k in range(3):
            if sum(by_year[p][y][k] for p in LISTED) != national[y][k]:
                raise EnvKumaError(f"{y}: prefectures do not add up to the national row (column {k})")
        for p in LISTED:
            cases, injured, deaths = by_year[p][y]
            if not (deaths <= injured and cases <= injured and (injured == 0) == (cases == 0)):
                raise EnvKumaError(f"{p} {y}: implausible injury figures {by_year[p][y]}")
    return {"updated": updated, "as_of": as_of, "years": years,
            "prefectures": [{"name": p, "by_year": by_year[p]} for p in LISTED], "national": national}


_PREF = r"(北海道|東京都|京都府|大阪府|[^\s\d]{2,3}県)"


def _fiscal_date(month: int, day: int, fy_start: int) -> str:
    """April..December belong to the fiscal year's first calendar year, January..March to the next."""
    year = fy_start if month >= 4 else fy_start + 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _as_of(text: str, word: str) -> str:
    m = re.search(rf"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日[^\n]{{0,8}}?{word}", text)
    if not m:
        raise EnvKumaError(f"'{word}' date not found")
    return f"{2018 + int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _page_text(pdf: bytes) -> str:
    from pypdf import PdfReader

    return _nfkc("\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages))


def parse_fatal(pdf: bytes, fy_start: int) -> dict:
    """Fatal bear attacks of one fiscal year: date, victims (1 when the table has no column), place."""
    text = _page_text(pdf)
    as_of = _as_of(text, "現在")
    rows = []
    for m in re.finditer(rf"(?m)^(\d+)\s+(\d+)月(\d+)日\s*(※被害者発見日)?\s*(?:(\d+)人)?\s*{_PREF}(\S+)$", text):
        rows.append({"no": int(m.group(1)), "date": _fiscal_date(int(m.group(2)), int(m.group(3)), fy_start),
                     "found_date": bool(m.group(4)), "victims": int(m.group(5) or 1),
                     "prefecture": m.group(6), "place": m.group(7)})
    if not rows or [r["no"] for r in rows] != list(range(1, len(rows) + 1)):
        raise EnvKumaError("fatal accident list: rows missing or numbered out of order")
    return {"as_of": as_of, "fy_start": fy_start, "incidents": rows, "deaths": sum(r["victims"] for r in rows)}


def parse_emergency(pdf: bytes, fy_start: int) -> dict:
    """Emergency shootings ("緊急銃猟") of one fiscal year, with the species targeted."""
    text = _page_text(pdf)
    updated = _as_of(text, "更新")
    rows = []
    for m in re.finditer(rf"(?m)^(\d+)\s+(\d+)月(\d+)日\s+{_PREF}(\S+)\s+(\S+)$", text):
        rows.append({"no": int(m.group(1)), "date": _fiscal_date(int(m.group(2)), int(m.group(3)), fy_start),
                     "prefecture": m.group(4), "place": m.group(5), "species": m.group(6)})
    if not rows or [r["no"] for r in rows] != list(range(1, len(rows) + 1)):
        raise EnvKumaError("emergency shooting list: rows missing or numbered out of order")
    stated = re.search(r"事例は(\d+)件", text)
    if not stated or int(stated.group(1)) != len(rows):
        raise EnvKumaError(f"emergency shooting list: the page says {stated and stated.group(1)} cases, {len(rows)} rows read")
    return {"updated": updated, "fy_start": fy_start, "cases": rows}


def _fiscal_files(page_html: str) -> dict[int, dict[str, str]]:
    """{fy_start: {"fatal": url, "emergency": url}} for the files linked from the ministry's page."""
    found: dict[int, dict[str, str]] = {}
    for kind, pattern in (("fatal", r"r(\d{2})jiko-gaiyo\.pdf"), ("emergency", r"r(\d{2})kinkyu-jishi\.pdf")):
        for m in re.finditer(pattern, page_html):
            found.setdefault(2018 + int(m.group(1)), {})[kind] = BASE + m.group(0)
    return found


def parse_notices(page_html: str, limit: int = 12) -> list[dict]:
    """The ministry's dated notices (ministerial statements, notices to local governments...) linked from its page.

    Only entries whose link text carries a Reiwa date are taken; the date is the first one in the text. The title is
    the link text as the ministry wrote it, minus a trailing "(date, issuing office)" part.
    """
    base_url = PAGE
    from urllib.parse import urljoin

    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page_html, flags=re.S):
        label = re.sub(r"\s+", "", _nfkc(re.sub(r"<[^>]+>", "", m.group(2))))
        d = re.search(r"令和(\d+)年(\d+)月(\d+)日", label)
        if not d:
            continue
        url = urljoin(base_url, m.group(1).strip())
        title = re.sub(r"\(令和\d+年\d+月\d+日、[^)]*\)$", "", label)
        if url in seen:
            continue
        seen.add(url)
        out.append({"date": f"{2018 + int(d.group(1)):04d}-{int(d.group(2)):02d}-{int(d.group(3)):02d}", "title": title, "url": url})
    out.sort(key=lambda x: (x["date"], x["url"]), reverse=True)
    return out[:limit]


def collect() -> dict:
    sight = parse_sightings(fetch(SIGHTINGS_PDF).body)
    injur = parse_injuries(fetch(INJURIES_PDF).body)
    page = fetch(PAGE).body.decode("utf-8", errors="replace")
    notices = parse_notices(page)
    files = _fiscal_files(page)
    latest_two = sorted(files)[-2:]
    fatal, emergency = {}, {}
    for fy in latest_two:
        label = f"R{fy - 2018:02d}"
        if "fatal" in files[fy]:
            fatal[label] = parse_fatal(fetch(files[fy]["fatal"]).body, fy)
        if "emergency" in files[fy]:
            emergency[label] = parse_emergency(fetch(files[fy]["emergency"]).body, fy)
    return {"source_page": PAGE, "sightings_pdf": SIGHTINGS_PDF, "injuries_pdf": INJURIES_PDF,
            "fetched_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
            "sightings": sight, "injuries": injur, "fatal": fatal, "emergency": emergency, "notices": notices}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
