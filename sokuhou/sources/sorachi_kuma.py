"""Sorachi General Subprefectural Bureau (Hokkaido): "そらち・ヒグマ情報" -- bear sightings and traces of the 24 cities and towns of Sorachi.

One HTML page, one table per municipality (date as month/day, place, number of bears, remarks); the year is the page's (令和8年, from 1 January).
The Hokkaido government's site policy (https://www.sorachi.pref.hokkaido.lg.jp/site-info/sitepolicy.html) states that all pages are open data
under CC-BY unless noted, so the page may be reused with a credit.  No coordinates are published.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta

from sokuhou.http import fetch
from sokuhou.sources import kumalib

PAGE = "https://www.sorachi.pref.hokkaido.lg.jp/hk/kks/245135.html"
CREDIT = "出典:空知総合振興局「そらち・ヒグマ情報」(北海道、CC-BY)を加工して作成"
UPDATE_NOTE = "空知総合振興局が、管内の市町の情報を集めて、随時更新します。日付だけで、時刻・座標は公表されていません"
MIN_ROWS = 50
UNPARSED_LIMIT = 0.03
TRACE_WORDS = ("足跡", "糞", "痕跡", "食痕", "爪", "剥", "被害", "掘")


class SorachiKumaError(ValueError):
    pass


def _text(fragment: str) -> str:
    out = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", out).strip()


def _as_of(page: str) -> date:
    flat = unicodedata.normalize("NFKC", re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", page))))
    m = re.search(r"令和(\d+)年(\d+)月(\d+)日.{0,12}?時点", flat)
    if not m:
        raise SorachiKumaError("the page's as-of time was not found")
    return date(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _kind(number: str, remark: str) -> str:
    count = kumalib.fullwidth_to_int(number)
    if "クマ様" in number:
        return "目撃(クマらしき)"
    if any(w in remark for w in TRACE_WORDS) and count is None:
        return "痕跡"
    return "目撃"


def parse_page(data: bytes) -> dict:
    page = data.decode("utf-8", errors="replace")
    as_of = _as_of(page)
    sightings, unparsed = [], 0
    city = None
    for m in re.finditer(r'<a[^>]*\bname="([^"]*?[市町村])"|<table.*?</table>', page, flags=re.S):
        if m.group(1):
            city = m.group(1)
            continue
        if city is None:
            continue
        for tr in re.findall(r"<tr.*?</tr>", m.group(0), flags=re.S):
            cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            if len(cells) < 4 or cells[0] == "日付":
                continue
            d = re.fullmatch(r"(\d{1,2})/(\d{1,2})", unicodedata.normalize("NFKC", cells[0]))
            try:
                day = date(as_of.year, int(d.group(1)), int(d.group(2))) if d else None
            except ValueError:
                day = None
            if day is None or day > as_of:
                unparsed += 1
                continue
            sightings.append({"observed_at": day.isoformat(), "city": city, "place": cells[1], "count": kumalib.fullwidth_to_int(cells[2]),
                              "kind": _kind(cells[2], cells[3]), "species": "ヒグマ"})
    total = len(sightings) + unparsed
    if len(sightings) < MIN_ROWS:
        raise SorachiKumaError(f"too few rows: {len(sightings)} < {MIN_ROWS}")
    if unparsed / total > UNPARSED_LIMIT:
        raise SorachiKumaError(f"too many unparsed rows: {unparsed}/{total}")
    return kumalib.package(source="sorachi", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, sightings=sightings, page=PAGE, files=[PAGE],
                           unparsed=unparsed)


def collect() -> dict:
    out = parse_page(fetch(PAGE).body)
    if date.fromisoformat(out["as_of"]) > datetime.now(kumalib.JST).date() + timedelta(days=2):
        raise SorachiKumaError(f"as-of date {out['as_of']} lies in the future")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
