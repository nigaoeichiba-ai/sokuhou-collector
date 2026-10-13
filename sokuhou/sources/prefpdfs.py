"""Prefectures that publish their bear-sighting list as a PDF behind a page (Shizuoka, Kanagawa, Ishikawa): kuma-sokuho.com.

The prefecture's page links the current fiscal year's PDF (its address changes with every update, so it is found from the page).  The PDF's rows are read
(date, municipality, place, kind, number), counted by municipality and month, and stored with their place as well: the owner's rule (2026-10-13) is that
what two or more publications carry is public, and these lists are carried by several other sites (checked on 2026-10-13).  No coordinates, no free text.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

from sokuhou.sources import corroborated as co
from sokuhou.sources import kumacounts, kumalib

ISHIKAWA_MUNICIPALITIES = ["金沢市", "七尾市", "小松市", "輪島市", "珠洲市", "加賀市", "羽咋市", "かほく市", "白山市", "能美市", "野々市市", "川北町", "津幡町",
                           "内灘町", "志賀町", "宝達志水町", "中能登町", "穴水町", "能登町"]


class PdfListError(ValueError):
    pass


def pdf_link(html: str, base: str, *, label: str = "", href: str = "") -> str:
    """The first PDF link whose text contains `label` (and whose address contains `href`); it must be on the page's own host."""
    for h, inner in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S | re.I):
        if label in co.clean(inner) and href in h:
            url = urljoin(base, h)
            if urlparse(url).netloc != urlparse(base).netloc:
                raise PdfListError(f"the PDF is not on the page's host: {url}")
            return url
    raise PdfListError(f"no PDF link with {label!r} / {href!r}")


def _day(fy: int, month: int, day: int) -> date:
    return co.day_in_fy(fy, month, day)


def parse_shizuoka(text: str, fy: int) -> list[dict]:
    """'№ 目撃日 時間 市町 地名等 備考' then '1 4月2日 6:30 富士宮市 猪之頭' (a ward belongs to its city: '静岡市葵区')."""
    text = unicodedata.normalize("NFKC", text)
    out = []
    for m in re.finditer(r"^\s*(\d+)\s+(\d{1,2})月(\d{1,2})日\s+(\d{1,2}:\d{2})\s+(\S+?[市町村](?:[^\s]*区)?)\s+(.+?)\s*$", text, re.M):
        city, rest = m.group(5), m.group(6)
        out.append(co._record(_day(fy, int(m.group(2)), int(m.group(3))), city, rest, "捕獲" if "捕獲" in rest else "目撃", None))
    if not out:
        raise PdfListError("Shizuoka: no rows")
    return out


def parse_kanagawa(text: str, fy: int) -> list[dict]:
    """'月日 時間 頭数 状況 場所等 区分' then '1 4月4日 5時30分頃 1 目撃 松田町寄 人里 ○' (a culled bear: the place is on the next line)."""
    lines = [l.strip() for l in unicodedata.normalize("NFKC", text).splitlines()]
    head = re.compile(r"^(\d+)\s+(\d{1,2})月(\d{1,2})日\s+(\S+(?:\s*頃)?)\s+(\d+)\s+(目撃|痕跡|捕殺|捕獲|その他)(?:\s+(\S+))?")
    out = []
    for i, line in enumerate(lines):
        m = head.match(line)
        if not m:
            continue
        place = m.group(7)
        if not place or place in ("人里", "山中"):
            place = next((l.split()[0] for l in lines[i + 1:i + 3] if l and not head.match(l)), "")
        c = re.match(r".+?[市町村]", place or "")
        if not c:
            continue
        status = m.group(6)
        kind = status if status in ("目撃", "痕跡") else ("捕獲" if status in ("捕殺", "捕獲") else "その他")
        out.append(co._record(_day(fy, int(m.group(2)), int(m.group(3))), c.group(0), place, kind, int(m.group(5)) or None))
    if not out:
        raise PdfListError("Kanagawa: no rows")
    return out


def parse_ishikawa(text: str) -> list[dict]:
    """'208 R8.10.3 5時27分頃 七尾市鵜浦町地内 ...' with the status running over the following lines (full-width digits are folded)."""
    text = unicodedata.normalize("NFKC", text)
    heads = list(re.finditer(r"^\s*(\d+)\s+R(\d+)\.(\d{1,2})\.(\d{1,2})\s+(\S+(?:\s*頃)?)\s+(\S+)", text, re.M))
    out = []
    for i, m in enumerate(heads):
        place = m.group(6)
        city = next((c for c in sorted(ISHIKAWA_MUNICIPALITIES, key=len, reverse=True) if place.startswith(c)), None)
        if city is None:
            continue
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        try:
            day = co.reiwa_day(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except co.CorroboratedError:
            continue
        out.append(co._record(day, city, place, co.kind_of(place + body), kumalib.fullwidth_to_int(body)))
    if not out:
        raise PdfListError("Ishikawa: no rows")
    return out


def collect_list(*, source: str, page: str, credit: str, update_note: str, rows: list[dict], file_url: str, today: date, min_rows: int,
                 error: type[ValueError]) -> dict:
    """Counts by municipality and month (the shape of kumacounts.build_counts) plus the rows stored with their place."""
    pairs = [(date.fromisoformat(r["observed_at"]), r["city"]) for r in rows]
    result = kumacounts.build_counts(pairs, error=error, today=today, source=source, credit=credit, update_note=update_note, page=page, files=[file_url],
                                     min_rows=min_rows, unparsed_limit=0.03, empty_limit=0.03, require_municipality=False)       # a ward ('静岡市葵区') is a place too
    recs = sorted(co.current_year(rows, today), key=lambda r: (r["observed_at"], r["place"]), reverse=True)
    if recs:
        result["corroborated"] = recs
        result["corroborated_on"] = {city: today.isoformat() for city in sorted({r["city"] for r in recs})}
    return result


def read_pdf_rows(page: str, fetch, link_kwargs: dict, parser, pause) -> tuple[list[dict], str]:
    html = co.decode(fetch(page))
    url = pdf_link(html, page, **link_kwargs)
    pause()
    return parser(co.pdf_text(fetch(url))), url


def parse_nagano_city(text: str) -> list[dict]:
    """Nagano City's monthly PDF: '107 9月23日 14時50分 戸隠 砂田バス停西付 近 目撃 路上に…' (the place and the status can run over lines; '出没' = traces)."""
    text = unicodedata.normalize("NFKC", text)
    fy = co.fy_year_from_heading(text)
    heads = list(re.finditer(r"^\s*(\d+)\s+(\d{1,2})月(\d{1,2})日\s+(\S+)\s+(\S+)\s+", text, re.M))
    out = []
    for i, m in enumerate(heads):
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        s = re.search(r"(目撃|出没)", body)
        if not s:
            continue
        loc = re.sub(r"\s+", "", body[: s.start()])
        out.append(co._record(_day(fy, int(m.group(2)), int(m.group(3))), "長野市", f"{m.group(5)} {loc}".strip(), "目撃" if s.group(1) == "目撃" else "痕跡", None))
    if not out:
        raise PdfListError("Nagano City: no rows")
    return out
