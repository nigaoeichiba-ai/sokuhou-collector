"""Yamaguchi Prefectural Police YP kumap CSV."""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from sokuhou.http import fetch
from sokuhou.sources.kumalib import coord, trim_for_store

DATASET_PAGE = "https://yamaguchi-opendata.jp/ckan/dataset/yp-2026"
PACKAGE_SHOW = "https://yamaguchi-opendata.jp/ckan/api/3/action/package_show?id=yp-2026"
CREDIT = "出典:山口県警察本部地域企画課「山口県内のクマ出没情報(YPくまっぷ)」(山口県オープンデータ、CC BY)を加工して作成"
UPDATE_NOTE = "山口県警察が認知した目撃・痕跡の情報です。随時更新されます"
HEADER = [
    "追番",
    "警察署",
    "目撃(発見)年月日",
    "目撃(発見)時間",
    "目撃(発見)場所",
    "状況",
    "頭数",
    "体長",
    "緯度",
    "経度",
]
TRACE_KEYWORDS = ("足跡", "痕跡", "糞", "爪痕", "食害", "樹皮")
MIN_ROWS = 100
BAD_COORD_LIMIT = 0.01
UNPARSED_LIMIT = 0.01
JST = timezone(timedelta(hours=9))


class YamaguchiKumaSourceError(ValueError):
    pass


def _fetch_yamaguchi(url: str):
    if urlparse(url).hostname != "yamaguchi-opendata.jp":
        raise YamaguchiKumaSourceError(f"unexpected Yamaguchi data host: {url!r}")
    return fetch(url, legacy_tls=True)


def csv_url_from_package_show(data: bytes) -> str:
    try:
        package = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise YamaguchiKumaSourceError("package_show returned invalid JSON") from e
    if not package.get("success"):
        raise YamaguchiKumaSourceError("package_show success is not true")
    result = package.get("result") or {}
    if result.get("license_id") != "cc-by":
        raise YamaguchiKumaSourceError(f"unexpected license_id: {result.get('license_id')!r}")
    resources = result.get("resources") or []
    csv_resources = [r for r in resources if str(r.get("format", "")).upper() == "CSV"]
    if len(csv_resources) != 1:
        raise YamaguchiKumaSourceError(f"expected exactly one CSV resource, found {len(csv_resources)}")
    url = csv_resources[0].get("url")
    if not isinstance(url, str) or not url:
        raise YamaguchiKumaSourceError("CSV resource has no URL")
    return url


def _clean_text(raw: str) -> str:
    return re.sub(r"[\s\u3000]+", " ", raw or "").strip()


def _parse_reiwa_date(raw: str) -> date | None:
    m = re.fullmatch(r"令和(\d+)年(\d+)月(\d+)日", _clean_text(raw))
    if not m:
        return None
    return date(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _parse_time(raw: str) -> time | None:
    text = _clean_text(raw)
    if not text:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not m:
        raise YamaguchiKumaSourceError(f"unparseable time: {raw!r}")
    return time(int(m.group(1)), int(m.group(2)))


def _observed_text(day: date, raw_time: str) -> str:
    parsed_time = _parse_time(raw_time)
    if parsed_time is None:
        return day.isoformat()
    return datetime.combine(day, parsed_time, JST).isoformat()


def _fiscal_start(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def _fy_label(fy_start: int) -> str:
    return f"R{fy_start - 2018:02d}"


def _count(raw: str) -> int | None:
    text = _clean_text(raw)
    if text == "不明" or not text:
        return None
    return int(text)


def kind_from_status(status: str) -> str:
    return "痕跡" if any(word in status for word in TRACE_KEYWORDS) else "目撃"


def _split_place(raw_place: str, police_station: str) -> tuple[str, str]:
    text = _clean_text(raw_place)
    m = re.search(r".+?[市町村]", text)
    if not m:
        return _clean_text(police_station) + "管内", text
    return m.group(0), text[m.end():].strip()


def _read_rows(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(data.decode("cp932")))
    try:
        header = next(reader)
    except StopIteration as e:
        raise YamaguchiKumaSourceError("CSV is empty") from e
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if len(raw_row) < len(header):
            raw_row = raw_row + [""] * (len(header) - len(raw_row))
        if len(raw_row) != len(header):
            raise YamaguchiKumaSourceError(f"CSV row has {len(raw_row)} columns, expected {len(header)}")
        if not raw_row[2].strip():
            continue
        rows.append(dict(zip(header, raw_row, strict=True)))
    return header, rows


def parse_csv(data: bytes) -> dict:
    header, rows = _read_rows(data)
    if header != HEADER:
        raise YamaguchiKumaSourceError(f"CSV header changed: {header}")
    if len(rows) < MIN_ROWS:
        raise YamaguchiKumaSourceError(f"CSV has too few dated rows: {len(rows)} < {MIN_ROWS}")
    ids = [row["追番"] for row in rows]
    if len(set(ids)) != len(ids):
        raise YamaguchiKumaSourceError("CSV 追番 values are not unique")

    parsed_rows: list[tuple[dict[str, str], date]] = []
    unparsed = 0
    bad_coords = 0
    for row in rows:
        day = _parse_reiwa_date(row["目撃(発見)年月日"])
        if day is None:
            unparsed += 1
        else:
            parsed_rows.append((row, day))
        try:
            lat = float(row["緯度"].strip())
            lon = float(row["経度"].strip())
        except ValueError:
            bad_coords += 1
            lat = lon = None
        else:
            if not (33.7 <= lat <= 34.8 and 130.7 <= lon <= 132.5):
                bad_coords += 1
                lat = lon = None
        row["_lat"], row["_lon"] = lat, lon

    total = len(rows)
    if unparsed / total > UNPARSED_LIMIT:
        raise YamaguchiKumaSourceError(f"too many unparsed dates: {unparsed}/{total}")
    if bad_coords / total > BAD_COORD_LIMIT:
        raise YamaguchiKumaSourceError(f"too many coordinates outside Yamaguchi box: {bad_coords}/{total}")
    if not parsed_rows:
        raise YamaguchiKumaSourceError("no parseable observed dates")

    newest = max(day for _, day in parsed_rows)
    current_start = _fiscal_start(newest)
    window = {_fy_label(current_start), _fy_label(current_start - 1)}
    monthly: dict[str, dict[str, int]] = {label: {} for label in sorted(window, reverse=True)}
    sightings = []
    for row, day in parsed_rows:
        fy = _fy_label(_fiscal_start(day))
        if fy not in window:
            continue
        month = str(day.month)
        months = monthly.setdefault(fy, {})
        months[month] = months.get(month, 0) + 1
        city, place = _split_place(row["目撃(発見)場所"], row["警察署"])
        parsed_time = _parse_time(row["目撃(発見)時間"])
        sort_dt = datetime.combine(day, parsed_time or time.min)
        sightings.append({
            "_sort": sort_dt,
            "observed_at": _observed_text(day, row["目撃(発見)時間"]),
            "city": city,
            "place": place,
            "count": _count(row["頭数"]),
            "kind": kind_from_status(row["状況"]),
            "species": "クマ",
            **(coord(row["_lat"], row["_lon"]) if row["_lat"] is not None else {}),
        })
    sightings.sort(key=lambda rec: rec["_sort"], reverse=True)
    for rec in sightings:
        del rec["_sort"]

    return {
        "source": "yamaguchi",
        "credit": CREDIT,
        "as_of": newest.isoformat(),
        "update_note": UPDATE_NOTE,
        "fy_current": _fy_label(current_start),
        "sightings": sightings,
        "monthly": {fy: months for fy, months in monthly.items() if months},
        "bad_coords": bad_coords,
        "unparsed": unparsed,
    }


def collect() -> dict:
    csv_url = csv_url_from_package_show(_fetch_yamaguchi(PACKAGE_SHOW).body)
    out = parse_csv(_fetch_yamaguchi(csv_url).body)
    out["sightings_in_window"] = len(out["sightings"])
    out["sightings"] = trim_for_store(out["sightings"], date.fromisoformat(out["as_of"]))
    out.update({
        "source_page": DATASET_PAGE,
        "source_file": csv_url,
        "fetched_at": datetime.now(JST).isoformat(),
    })
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
