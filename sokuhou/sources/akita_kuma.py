"""Akita prefecture Kumadas open-data CSV.

The CSV is valid UTF-8 with BOM and contains quoted multiline fields, so this parser uses
the stdlib csv module over decoded text.  Only the current and previous fiscal years are
kept in the result's sightings list.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone

from sokuhou.http import fetch

DATASET_PAGE = "https://ckan.pref.akita.lg.jp/dataset/f801a10f-f076-47e4-b5a6-0bb5569639e0"
SOURCE_FILE = (
    "https://ckan.pref.akita.lg.jp/dataset/f801a10f-f076-47e4-b5a6-0bb5569639e0/resource/"
    "0678f9b3-4bf7-4212-9c0e-c0cb9b09b3cf/download/050008_kumadas.csv"
)
CREDIT = "出典:秋田県「クマダス」(秋田県オープンデータ、CC BY 4.0)を加工して作成"
UPDATE_NOTE = "秋田県の「クマダス」のオープンデータ。更新は月に1回ほどで、最新の目撃は、更新時点から遅れます"
HEADER = [
    "出没情報ID", "情報種別", "市町村", "地番情報", "目撃日時", "獣種",
    "性別", "単独か親子", "頭数", "目撃時の状況", "x(緯度)", "y(経度)",
]
BEAR_SPECIES = {"ツキノワグマ", "ヒグマ"}
MIN_ROWS = 20_000
BAD_COORD_LIMIT = 0.01
UNPARSED_LIMIT = 0.01
JST = timezone(timedelta(hours=9))


class AkitaKumaParseError(ValueError):
    pass


def _parse_observed(raw: str) -> tuple[datetime | None, bool]:
    if re.fullmatch(r"\d+(\.\d+)?", raw or ""):
        value = float(raw)
        whole = int(value)
        seconds = round((value - whole) * 24 * 60 * 60)
        day = date(1899, 12, 30) + timedelta(days=whole)
        if seconds <= 0:
            return datetime.combine(day, datetime.min.time(), JST), False
        return datetime.combine(day, datetime.min.time(), JST) + timedelta(seconds=seconds), True
    try:
        return datetime.strptime(raw, "%Y/%m/%d %H:%M").replace(tzinfo=JST), True
    except ValueError:
        return None, False


def _observed_text(dt: datetime, has_time: bool) -> str:
    return dt.isoformat() if has_time else dt.date().isoformat()


def _fiscal_start(dt: datetime) -> int:
    return dt.year if dt.month >= 4 else dt.year - 1


def _fy_label(fy_start: int) -> str:
    return f"R{fy_start - 2018:02d}"


def _clean_address(raw: str) -> str:
    out = re.sub(r"^日本、", "", raw or "").strip()
    out = re.sub(r"^〒\d{3}-\d{4}\s*", "", out).strip()
    return out


def _int_or_none(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _read_rows(data: bytes) -> tuple[list[str], list[dict[str, str]], int]:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    try:
        header = next(reader)
    except StopIteration as e:
        raise AkitaKumaParseError("CSV is empty") from e
    rows: list[dict[str, str]] = []
    seen_exact: set[tuple[str, ...]] = set()
    duplicates_removed = 0
    for row in reader:
        exact = tuple(row)
        if exact in seen_exact:
            duplicates_removed += 1
            continue
        seen_exact.add(exact)
        try:
            rows.append(dict(zip(header, row, strict=True)))
        except ValueError as e:
            raise AkitaKumaParseError(f"CSV row has {len(row)} columns, expected {len(header)}") from e
    return header, rows, duplicates_removed


STORED_SIGHTINGS = 400


def parse_csv(data: bytes) -> dict:
    header, rows, duplicates_removed = _read_rows(data)
    if header != HEADER:
        raise AkitaKumaParseError(f"CSV header changed: {header}")
    if len(rows) < MIN_ROWS:
        raise AkitaKumaParseError(f"CSV has too few rows: {len(rows)} < {MIN_ROWS}")
    ids = [row["出没情報ID"] for row in rows]
    if len(set(ids)) != len(ids):
        raise AkitaKumaParseError("CSV IDs are not unique")

    parsed_rows: list[tuple[dict[str, str], datetime, bool]] = []
    unparsed = 0
    bad_coords = 0
    for row in rows:
        dt, has_time = _parse_observed(row["目撃日時"])
        if dt is None:
            unparsed += 1
        else:
            parsed_rows.append((row, dt, has_time))
        try:
            lat, lon = float(row["x(緯度)"]), float(row["y(経度)"])
        except ValueError:
            bad_coords += 1
        else:
            if not (38.8 <= lat <= 40.6 and 139.6 <= lon <= 141.1):
                bad_coords += 1

    total = len(rows)
    if unparsed / total > UNPARSED_LIMIT:
        raise AkitaKumaParseError(f"too many unparsed dates: {unparsed}/{total}")
    if bad_coords / total > BAD_COORD_LIMIT:
        raise AkitaKumaParseError(f"too many coordinates outside Akita box: {bad_coords}/{total}")
    if not parsed_rows:
        raise AkitaKumaParseError("no parseable observed dates")

    newest_dt = max(dt for _, dt, _ in parsed_rows)
    current_start = _fiscal_start(newest_dt)
    window = {_fy_label(current_start), _fy_label(current_start - 1)}
    monthly: dict[str, dict[str, int]] = {label: {} for label in sorted(window, reverse=True)}
    sightings = []
    for row, dt, has_time in parsed_rows:
        fy = _fy_label(_fiscal_start(dt))
        if row["獣種"] not in BEAR_SPECIES or fy not in window:
            continue
        if row["情報種別"] == "目撃":
            months = monthly.setdefault(fy, {})
            month = str(dt.month)
            months[month] = months.get(month, 0) + 1
        sightings.append({
            "_sort": dt,
            "observed_at": _observed_text(dt, has_time),
            "city": row["市町村"],
            "place": _clean_address(row["地番情報"]),
            "count": _int_or_none(row["頭数"]),
            "kind": row["情報種別"],
            "species": row["獣種"],
        })
    sightings.sort(key=lambda rec: rec["_sort"], reverse=True)
    for rec in sightings:
        del rec["_sort"]

    return {
        "source": "akita",
        "credit": CREDIT,
        "as_of": newest_dt.date().isoformat(),
        "newest_observed_at": newest_dt.isoformat(),
        "update_note": UPDATE_NOTE,
        "fy_current": _fy_label(current_start),
        "sightings": sightings,
        "monthly_kind": "目撃",
        "monthly": {fy: months for fy, months in monthly.items() if months},
        "bad_coords": bad_coords,
        "unparsed": unparsed,
        "duplicate_rows_removed": duplicates_removed,
    }


def collect() -> dict:
    out = parse_csv(fetch(SOURCE_FILE).body)
    # The monthly counts already cover the whole window; keep only the newest entries so the stored file stays small.
    out["sightings_in_window"] = len(out["sightings"])
    out["sightings"] = out["sightings"][:STORED_SIGHTINGS]
    out.update({
        "source_page": DATASET_PAGE,
        "source_file": SOURCE_FILE,
        "fetched_at": datetime.now(JST).isoformat(),
    })
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
