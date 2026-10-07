"""Shared core of the "counts only" prefecture adapters whose data sits in an ArcGIS hosted FeatureServer (Fukushima, Niigata, Toyama).

These prefectures do not state that their data may be re-used, so nothing is kept except municipality, month and count:
  * only the date column and the municipality column are ever requested (`outFields`), and no geometry (`returnGeometry=false`);
  * the rows live in memory only: they go straight into `kumalib.package_counts()` and only its result is stored;
  * every request goes through `kumalib.polite_fetch` (robots.txt, an identifying User-Agent), at least one second apart.

The layer address is not hard-coded: it is read from the public web map that the prefecture's own map page embeds (a prefecture renames its
service every year, e.g. "..._202606_view"), and refused if that web map no longer points at exactly one matching layer.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote, unquote, urlencode

from sokuhou.sources import kumalib

PORTAL = "https://www.arcgis.com/sharing/rest/content/items/"
PAGE_SIZE = 1000
PAUSE = 1.0   # seconds between two requests to the same service


class ArcgisCountsError(ValueError):
    """The source's shape changed (or it is empty / broken): nothing is stored."""


def norm_city(city: str, prefecture: str) -> str:
    """Same idea as sites.kuma.live.norm_city, plus: width and spaces, a leading prefecture name, and a leading county ('安達郡大玉村' -> '大玉村').

    Anything that does not end in 市/町/村/区 afterwards (a blank, '不明', '県外') comes back as ''.
    """
    c = unicodedata.normalize("NFKC", city or "").replace(" ", "").replace("　", "").strip()
    if c.startswith(prefecture):
        c = c[len(prefecture):]
    c = re.sub(r"^[^市区町村]{1,5}郡(?=[^市区町村郡]+[町村]$)", "", c)
    return c if re.fullmatch(r".+[市区町村]", c) else ""   # 十日町市, 村上市, 上市町 contain these characters inside the name too


def window_start(today: date) -> date:
    """The current fiscal year plus the January-March before it (what kumalib.trim_for_store keeps for the row-storing sources)."""
    return date(kumalib.fiscal_start(today), 1, 1)


def _json(body: bytes, error: type[ArcgisCountsError], what: str) -> dict:
    try:
        data = json.loads(body)
    except ValueError as e:
        raise error(f"{what}: not JSON ({e})") from e
    if not isinstance(data, dict):
        raise error(f"{what}: unexpected JSON")
    if "error" in data:
        raise error(f"{what}: the server answered with an error: {str(data['error'])[:200]}")
    return data


def layer_url_from_webmap(webmap: dict, pattern: str, error: type[ArcgisCountsError]) -> str:
    """The one FeatureServer layer of the public web map whose (decoded) address matches `pattern`."""
    urls = {l["url"] for l in webmap.get("operationalLayers", []) if isinstance(l.get("url"), str) and "/FeatureServer/" in l["url"]
            and re.search(pattern, unquote(l["url"]))}
    if len(urls) != 1:
        raise error(f"the web map has {len(urls)} layers matching {pattern!r} (expected exactly 1)")
    return quote(urls.pop(), safe=":/%")   # a service name may be Japanese; already-encoded text is left alone


def check_layer(info: dict, date_field: str, city_field: str, error: type[ArcgisCountsError]) -> tuple[str, dict[str, str]]:
    """Both columns must exist (the date as a date); returns (the object-id field name, {code: name} if the city column is a coded-value domain)."""
    fields = {f.get("name"): f for f in info.get("fields", [])}
    if date_field not in fields or fields[date_field].get("type") != "esriFieldTypeDate":
        raise error(f"the date column {date_field!r} is gone or is no longer a date: {sorted(map(str, fields))}")
    if city_field not in fields:
        raise error(f"the municipality column {city_field!r} is gone: {sorted(map(str, fields))}")
    oid = next((n for n, f in fields.items() if f.get("type") == "esriFieldTypeOID"), None)
    if not oid:
        raise error("the layer has no object-id column")
    domain = fields[city_field].get("domain") or {}
    names = {str(c["code"]): str(c["name"]) for c in domain.get("codedValues", [])} if domain.get("type") == "codedValue" else {}
    return oid, names


def query_url(layer: str, *, date_field: str, city_field: str, oid: str, since: date, offset: int) -> str:
    """Only the date and the municipality are asked for, and no geometry.  `since` is a JST midnight, written in UTC for the server."""
    start = (datetime(since.year, since.month, since.day) - timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    params = {"where": f"{date_field} >= timestamp '{start}' OR {date_field} IS NULL", "outFields": f"{date_field},{city_field}",
              "returnGeometry": "false", "orderByFields": oid, "resultOffset": offset, "resultRecordCount": PAGE_SIZE, "f": "json"}
    return f"{layer}/query?{urlencode(params, quote_via=quote)}"


def fetch_rows(layer: str, *, date_field: str, city_field: str, oid: str, since: date, fetch, sleep, error: type[ArcgisCountsError]
               ) -> list[tuple[object, object]]:
    """[(raw date, raw city)] of every page; nothing else of a feature is looked at."""
    rows: list[tuple[object, object]] = []
    offset = 0
    for _ in range(50):
        data = _json(fetch(query_url(layer, date_field=date_field, city_field=city_field, oid=oid, since=since, offset=offset)), error, "query")
        feats = data.get("features")
        if not isinstance(feats, list):
            raise error("query: no 'features' list")
        for f in feats:
            a = f.get("attributes") or {}
            rows.append((a.get(date_field), a.get(city_field)))
        if not feats or not data.get("exceededTransferLimit"):
            return rows
        offset += len(feats)
        sleep(PAUSE)
    raise error("query: more than 50 pages")


def _day(raw: object) -> date | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(raw / 1000, kumalib.JST).date()
    except (OverflowError, OSError, ValueError):
        return None


def aggregate(raw_rows: list[tuple[object, object]], *, prefecture: str, names: dict[str, str], today: date, since: date, min_rows: int,
              unparsed_limit: float, empty_city_limit: float, source: str, credit: str, update_note: str, page: str, layer: str,
              error: type[ArcgisCountsError]) -> dict:
    """The stored shape (kumalib.package_counts).  Rows outside the window are ignored; bad dates and blank municipalities are counted and capped."""
    rows, unparsed, empty = [], 0, 0
    inside = 0
    newest_ok = today + timedelta(days=2)
    for raw_day, raw_city in raw_rows:
        d = _day(raw_day) if raw_day is not None else None
        if d is not None and d < since:
            continue                       # the server should not have sent it; it is not part of the window
        inside += 1
        if d is None or d > newest_ok:     # no date / not a date / after today + 2 days (a typo)
            unparsed += 1
            continue
        city = norm_city(names.get(str(raw_city), "" if names else str(raw_city or "")), prefecture)
        if not city:
            empty += 1
            continue
        rows.append({"observed_at": d.isoformat(), "city": city})
    if inside < min_rows:
        raise error(f"too few rows: {inside} < {min_rows}")
    if unparsed / inside > unparsed_limit:
        raise error(f"too many rows without a readable date: {unparsed}/{inside}")
    if empty / inside > empty_city_limit:
        raise error(f"too many rows without a municipality: {empty}/{inside}")
    if not rows:
        raise error("no usable rows")
    as_of = max(date.fromisoformat(r["observed_at"]) for r in rows)
    return kumalib.package_counts(source=source, credit=credit, update_note=update_note, as_of=as_of, rows=rows, page=page, files=[layer],
                                  unparsed=unparsed + empty)


def collect_counts(*, source: str, prefecture: str, webmap_id: str, layer_pattern: str, date_field: str, city_field: str, page: str,
                   credit: str, update_note: str, min_rows: int, unparsed_limit: float, empty_city_limit: float,
                   error: type[ArcgisCountsError], fetch=None, sleep=time.sleep, now: datetime | None = None) -> dict:
    fetch = fetch or kumalib.polite_fetch
    today = (now or datetime.now(kumalib.JST)).astimezone(kumalib.JST).date()
    webmap = _json(fetch(f"{PORTAL}{webmap_id}/data?f=json"), error, "web map")
    layer = layer_url_from_webmap(webmap, layer_pattern, error)
    sleep(PAUSE)
    oid, names = check_layer(_json(fetch(f"{layer}?f=json"), error, "layer"), date_field, city_field, error)
    since = window_start(today)
    sleep(PAUSE)
    raw = fetch_rows(layer, date_field=date_field, city_field=city_field, oid=oid, since=since, fetch=fetch, sleep=sleep, error=error)
    return aggregate(raw, prefecture=prefecture, names=names, today=today, since=since, min_rows=min_rows, unparsed_limit=unparsed_limit,
                     empty_city_limit=empty_city_limit, source=source, credit=credit, update_note=update_note, page=page, layer=layer, error=error)
