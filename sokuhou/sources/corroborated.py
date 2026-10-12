"""Sightings that two independent publications agree on (kuma-sokuho.com).

Rule (owner, 2026-10-13): a fact that is published by two or more media is a widely known fact and may be shown; no source or link is named for it.
So a municipality's own page (medium 1) is read for its records (date, place, kind) and a record is KEPT only if the prefecture's list (medium 2,
already read by the counts adapter) holds a record of the same municipality on the same day.  Each prefecture record can confirm at most one municipal
record (a multiset match), so two sightings on one day need two prefecture rows.  Everything that is not confirmed stays what it was: a count.

The parsers read the municipalities' own pages (static HTML); every request goes through `kumalib.polite_fetch` (robots.txt, identifying User-Agent).
A page that cannot be read raises `CorroboratedError`; the caller then stores no records for that run (the counts are unaffected).
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from collections import Counter
from datetime import date

from sokuhou.sources import kumalib

ERA_REIWA_OFFSET = 2018      # Reiwa N = 2018 + N
MAX_PLACE = 80


class CorroboratedError(ValueError):
    pass


def decode(body: bytes) -> str:
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', body[:4000])
    enc = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def clean(text: str) -> str:
    """Tags removed, entities decoded, NFKC (full-width digits and letters become ASCII), spaces squeezed."""
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def kind_of(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    if re.search(r"痕跡|足跡|糞|食害|食痕|食べ|破損|爪|唸り声|うなり声|疑い", t) and not re.search(r"目撃", t):
        return "痕跡"
    if re.search(r"捕獲|駆除", t) and not re.search(r"目撃", t):
        return "捕獲"
    if "目撃" in t:
        return "目撃"
    return "その他"


def fy_year_from_heading(html: str) -> int:
    """The fiscal year (calendar year of April) from '令和8年度' in the page; refuses a page that does not say."""
    years = [int(x) for x in re.findall(r"令和\s*(\d+)\s*年度", unicodedata.normalize("NFKC", html))]
    if not years:
        raise CorroboratedError("no '令和N年度' on the page")
    return ERA_REIWA_OFFSET + max(years)       # a link to last year's list must not decide the year


def day_in_fy(fy_start: int, month: int, day: int) -> date:
    try:
        return date(fy_start if month >= 4 else fy_start + 1, month, day)
    except ValueError as e:
        raise CorroboratedError(f"impossible date {month}/{day}") from e


def reiwa_day(era: int, month: int, day: int) -> date:
    try:
        return date(ERA_REIWA_OFFSET + era, month, day)
    except ValueError as e:
        raise CorroboratedError(f"impossible date R{era} {month}/{day}") from e


def _record(day: date, city: str, place: str, kind: str, count: int | None) -> dict:
    place = re.sub(r"\s+", " ", place).strip(" 　,、。")[:MAX_PLACE]
    return {"observed_at": day.isoformat(), "city": city, "place": place, "kind": kind, "count": count}


# ---------------------------------------------------------------- the municipalities' pages

SAKATA_PAGE = "https://www.city.sakata.lg.jp/kurashi/doubutsu/yasei/kankyo0320260415.html"
YAMAGATA_CITY_PAGE = "https://www.city.yamagata-yamagata.lg.jp/kurashi/kankyohozen/1006552/1002384.html"
CHICHIBU_PAGE = "https://www.city.chichibu.lg.jp/10646.html"
OGANO_PAGE = "https://www.town.ogano.lg.jp/industry-bid-business/industry/kumanosyutubotujyouhou/"


def parse_sakata(html: str) -> list[dict]:
    """Sakata City: one table per month (No., date, time, area, place, summary)."""
    fy = fy_year_from_heading(html)
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", cells[1])
        if not m:
            raise CorroboratedError(f"Sakata: unreadable date {cells[1]!r}")
        summary = cells[5]
        detail = re.match(r"(字[^\s、。()（）]{1,10}?地内)", summary)
        place = cells[4] + (detail.group(1) if detail else "")
        count = kumalib.fullwidth_to_int(summary)
        out.append(_record(day_in_fy(fy, int(m.group(1)), int(m.group(2))), "酒田市", place, kind_of(summary), count))
    if not out:
        raise CorroboratedError("Sakata: no rows")
    return out


def parse_yamagata_city(html: str) -> list[dict]:
    """Yamagata City: lines 'No.108  10月3日(土曜)  午前11時00分頃  大字柏倉地内の山林にてクマ1頭を目撃' under a '令和8年度' heading."""
    fy_now = None                    # the fiscal year of the section a line is in: '【令和8年度クマ出没状況】' starts one
    out = []
    for line in re.split(r"<br\s*/?>|</p>", html):
        text = clean(line)
        head = re.search(r"【令和\s*(\d+)\s*年度", text)
        if head:
            fy_now = ERA_REIWA_OFFSET + int(head.group(1))
            continue
        if fy_now is None:
            continue
        fy = fy_now
        m = re.match(r"No\.\s*\d+\s+(\d{1,2})月(\d{1,2})日\s*\([^)]*\)\s*(?:午[前後]\d{1,2}時\d{1,2}分頃?)?\s*(.+)$", text)
        if not m:
            continue
        rest = m.group(3)
        place, _, tail = rest.partition("にて")
        if not tail:
            place, tail = rest, rest
        out.append(_record(day_in_fy(fy, int(m.group(1)), int(m.group(2))), "山形市", place, kind_of(tail), kumalib.fullwidth_to_int(tail)))
    if not out:
        raise CorroboratedError("Yamagata City: no rows")
    return out


def parse_chichibu(html: str) -> list[dict]:
    """Chichibu City (Arakawa district): numbered lines '9．令和8年10月9日  荒川上田野地内（諸上橋付近）' (a trace is marked '※ 出没痕跡')."""
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        text = clean(p)
        m = re.match(r"\d+[.．]\s*令和\s*(\d+)年\s*(\d+)月\s*(\d+)日\s*(.+)$", text)
        if not m:
            continue
        rest = m.group(4)
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "秩父市", re.sub(r"※.*$", "", rest),
                           "痕跡" if "痕跡" in rest else "目撃", None))
    if not out:
        raise CorroboratedError("Chichibu: no rows")
    return out


def parse_ogano(html: str) -> list[dict]:
    """Ogano Town: lines '令和８年１０月６日  河原沢  大諸バス停北西１５０ｍ付近' (a two-day line such as '７月１５・１６日' counts for its first day)."""
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        text = clean(p)
        m = re.match(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)(?:・\d+)*日\s*(.+)$", text)
        if not m:
            continue
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "小鹿野町", m.group(4), "目撃", None))
    if not out:
        raise CorroboratedError("Ogano: no rows")
    return out


JOETSU_PAGE = "https://www.city.joetsu.niigata.jp/soshiki/kankyo/kinkyuzi-bear.html"
JOETSU_HEAD = re.compile(r"^\s*(\d+)\s+(\d{1,2})月(\d{1,2})日\([^)]*\)\s+\S+\s+(\S+?区)\s+(\S+)", re.M)


def joetsu_pdf_url(html: str, page_url: str = JOETSU_PAGE) -> str:
    """The PDF of the newest fiscal year ('令和8年度:90件 [PDFファイル]') on Joetsu City's page; its address changes with every update."""
    from urllib.parse import urljoin, urlparse
    best = None
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S):
        m = re.match(r"令和\s*(\d+)\s*年度", clean(label))
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), urljoin(page_url, href))
    if best is None:
        raise CorroboratedError("no PDF of a fiscal year on the page")
    if urlparse(best[1]).netloc != urlparse(page_url).netloc:
        raise CorroboratedError(f"the PDF is not on the city's host: {best[1]}")
    return best[1]


def parse_joetsu_text(text: str) -> list[dict]:
    """Joetsu City's list (text of its PDF): '№ 月日 時刻 地域自治区 場所 状況' per sighting, the status text running over several lines."""
    text = unicodedata.normalize("NFKC", text)
    fy = fy_year_from_heading(text)
    heads = list(JOETSU_HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        out.append(_record(day_in_fy(fy, int(m.group(2)), int(m.group(3))), "上越市", m.group(4) + m.group(5), kind_of(body), kumalib.fullwidth_to_int(body)))
    if not out:
        raise CorroboratedError("Joetsu: no rows")
    return out


def pdf_text(body: bytes) -> str:
    import io
    from pypdf import PdfReader
    return chr(10).join(p.extract_text() or "" for p in PdfReader(io.BytesIO(body)).pages)


def joetsu_reader(page_url: str = JOETSU_PAGE):
    def read(fetch, pause):
        pdf = joetsu_pdf_url(decode(fetch(page_url)), page_url)
        pause()
        return parse_joetsu_text(pdf_text(fetch(pdf)))
    read.label = page_url
    return read


# ---------------------------------------------------------------- the match

def confirm(prefecture_rows: list[tuple[date | None, object]], records: list[dict], norm_city=lambda c: str(c)) -> list[dict]:
    """The records that the prefecture's list also holds (same municipality, same day), newest first.

    prefecture_rows: (date or None, municipality) as the counts adapter reads them.  A prefecture row confirms one record only."""
    have = Counter((d.isoformat(), norm_city(c)) for d, c in prefecture_rows if d is not None)
    kept = []
    for r in sorted(records, key=lambda r: (r["observed_at"], r["place"]), reverse=True):
        key = (r["observed_at"], r["city"])
        if have[key] > 0:
            have[key] -= 1
            kept.append(r)
    return kept


def current_year(records: list[dict], today: date) -> list[dict]:
    """Only the current fiscal year (the January-March before it is not shown)."""
    start = date(kumalib.fiscal_start(today), 4, 1).isoformat()
    return [r for r in records if start <= r["observed_at"] <= today.isoformat()]


STORED_FIELDS = {"observed_at", "city", "place", "kind", "count"}


def html_reader(url: str, parser):
    """A reader of one static HTML page: read(fetch, pause) -> records."""
    def read(fetch, pause):
        return parser(decode(fetch(url)))
    read.label = url
    return read


def attach(result: dict, prefecture_rows, readers: list, fetch, today: date, pause=lambda: None,
           norm_city=lambda c: str(c)) -> dict:
    """Adds `corroborated` (the confirmed records, newest first) to a counts package.  Nothing is added when nothing could be confirmed;
    the problems of single pages are printed to stderr (the run goes on: the counts do not depend on these pages)."""
    import sys
    records, errors = collect_records(prefecture_rows, readers, fetch, today, pause, norm_city)
    for e in errors:
        print(f"corroborated: {e}", file=sys.stderr)
    if records:
        result["corroborated"] = records
    return result


def collect_records(prefecture_rows, readers: list, fetch, today: date, pause=lambda: None,
                    norm_city=lambda c: str(c)) -> tuple[list[dict], list[str]]:
    """readers: functions read(fetch, pause) -> records, each with a `label`.  Returns (what the prefecture also lists in the current
    fiscal year, [one message per reader that failed]).

    A reader that fails is skipped (its municipality shows no records that day); if every reader fails the caller stores no records at all."""
    found: list[dict] = []
    errors: list[str] = []
    for i, read in enumerate(readers):
        if i:
            pause()
        try:
            found += read(fetch, pause)
        except Exception as e:  # noqa: BLE001 - a municipality's page may change or be down; the counts must not depend on it
            errors.append(f"{getattr(read, 'label', read)}: {type(e).__name__}: {e}")
    return current_year(confirm(prefecture_rows, found, norm_city), today), errors
