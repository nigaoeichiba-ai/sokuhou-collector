"""Shared parts of the "counts only" adapters for Yamagata, Aomori, Nara, Gunma and Saitama (kuma-sokuho.com).

These prefectures do not state that their data may be re-used.  So an adapter reads only the date and the municipality of each record
(everything else is dropped the moment it is read), counts them in memory and hands the result to `kumalib.package_counts()`;
only that result is stored.  Every request goes through `kumalib.polite_fetch` (robots.txt, an identifying User-Agent) and the
paged ones wait at least a second between pages.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from sokuhou.sources import kumalib

PAUSE = 1.0   # seconds between two requests of one adapter


def fetch(url: str) -> bytes:
    """The default network function of every adapter (each adapter has its own `fetch` name, so a test can replace it)."""
    return kumalib.polite_fetch(url)


def pause() -> None:
    time.sleep(PAUSE)


def norm_city(city: object) -> str:
    """Same idea as sites.kuma.live.norm_city ('阿武郡阿武町' and '阿武町' are one municipality), plus spaces: '大淀町  奈良市' keeps one space."""
    c = re.sub(r"[\s　]+", " ", str(city or "")).strip()
    return re.sub(r"^[^市区町村 ]{1,5}郡(?=[^市区町村郡 ]+[町村]$)", "", c)


def is_municipality(city: str) -> bool:
    return bool(re.search(r"[市町村]$", city))


def jst_date(ms: object) -> date | None:
    """An ArcGIS date (milliseconds since the epoch) as a date in Japan; anything else -> None."""
    if isinstance(ms, bool) or not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, kumalib.JST).date()
    except (OverflowError, OSError, ValueError):
        return None


def window_start(today: date) -> date:
    """The current fiscal year plus the January-March before it."""
    return date(kumalib.fiscal_start(today), 1, 1)


def today_jst(now: datetime | None = None) -> date:
    return (now or datetime.now(kumalib.JST)).astimezone(kumalib.JST).date()


def build_counts(rows: list[tuple[date | None, object]], *, error: type[ValueError], today: date, source: str, credit: str, update_note: str,
                 page: str, files: list[str], min_rows: int, unparsed_limit: float, empty_limit: float, require_municipality: bool = True) -> dict:
    """rows: (date or None when unreadable, raw municipality).  Returns the stored shape (kumalib.package_counts).

    A row with no readable date or a date after today + 2 days is not counted but added to `unparsed`; so is a row without a municipality.
    Rows before January 1 of the current fiscal year are simply outside the window.
    Raises `error` (nothing is stored) when the rows are too few or too many of them are unreadable.
    """
    total = len(rows)
    if total == 0:
        raise error("no rows")
    start, newest = window_start(today), today + timedelta(days=2)
    kept: list[dict] = []
    bad_date = empty = 0
    for day, raw_city in rows:
        if day is None or day > newest:
            bad_date += 1
            continue
        if day < start:
            continue
        city = norm_city(raw_city)
        if not city or (require_municipality and not is_municipality(city)):
            empty += 1
            continue
        kept.append({"observed_at": day.isoformat(), "city": city})
    if len(kept) < min_rows:
        raise error(f"too few rows: {len(kept)} < {min_rows}")
    if bad_date / total > unparsed_limit:
        raise error(f"too many rows without a usable date: {bad_date}/{total}")
    if empty / total > empty_limit:
        raise error(f"too many rows without a municipality: {empty}/{total}")
    as_of = max(date.fromisoformat(r["observed_at"]) for r in kept)
    return kumalib.package_counts(source=source, credit=credit, update_note=update_note, as_of=as_of, rows=kept, page=page, files=files,
                                  unparsed=bad_date + empty)


def load_json(body: bytes, error: type[ValueError], what: str) -> dict:
    try:
        data = json.loads(body)
    except ValueError as e:
        raise error(f"{what}: not JSON ({e})") from e
    if not isinstance(data, dict):
        raise error(f"{what}: unexpected JSON")
    if "error" in data and "features" not in data and "result" not in data:
        raise error(f"{what}: the server answered with an error: {str(data['error'])[:200]}")
    return data


def query_all(fetch_fn, layer_url: str, params: dict, *, error: type[ValueError], page_size: int = 1000, max_pages: int = 30) -> list[dict]:
    """Every feature of an ArcGIS FeatureServer layer, paged with resultOffset (ordered by `orderByFields`, which the caller must give)."""
    feats: list[dict] = []
    offset = 0
    for page in range(max_pages):
        if page:
            pause()
        q = {**params, "f": "json", "resultOffset": offset, "resultRecordCount": page_size}
        data = load_json(fetch_fn(f"{layer_url}/query?{urlencode(q)}"), error, "query")
        got = data.get("features")
        if not isinstance(got, list):
            raise error("query: no 'features' list")
        feats += got
        if not got or not data.get("exceededTransferLimit"):
            return feats
        offset += len(got)
    raise error(f"query: more than {max_pages} pages")
