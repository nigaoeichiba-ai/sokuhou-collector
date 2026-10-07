"""Yamanashi prefecture bear sightings (Yamanashi Prefecture open data catalog, CKAN).

Two datasets: "kuma1" (the fiscal year so far, updated about weekly) and "kuma0" (the last month, updated the same day).
They overlap, so rows are joined on the number ("No.").  The prefecture's open data terms
(https://www.pref.yamanashi.jp/opendata/kiyaku.html) allow free use, commercial use included, with a credit.
The coordinates are, by the prefecture's own note, "a rough position near the sighting".
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta

from sokuhou.http import fetch
from sokuhou.sources import kumalib

API = "https://catalog.dataplatform-yamanashi.jp/api/3/action/package_show?id="
DATASETS = ("kuma1", "kuma0")
PAGE = "https://catalog.dataplatform-yamanashi.jp/dataset/kuma1"
CREDIT = ("出典:「ツキノワグマ出没・目撃情報(令和8年度)」(山梨県)(https://catalog.dataplatform-yamanashi.jp/dataset/kuma1)を加工して作成"
          "(山梨県オープンデータ利用規約に基づく)")
UPDATE_NOTE = "山梨県が、ほぼ毎週更新します。最新の目撃は、更新時点から遅れます。位置は、県が「目撃地点の大まかな付近を表示した目安」としています"
HEADER_START = ["No.", "年月日", "目撃年月日", "時間", "目撃市町村", "場所", "天候", "目撃時のクマ", "目撃時の目撃者の行動", "目撃した環境",
                "その後の対応", "人身被害の有無", "推定年齢", "目撃頭数", "注意事項", "緯度", "経度"]
MIN_ROWS = 100
BOX = (34.9, 36.0, 138.0, 139.3)  # lat min / max, lon min / max
BAD_COORD_LIMIT = 0.02
UNPARSED_LIMIT = 0.02


class YamanashiKumaSourceError(ValueError):
    pass


def csv_url_from_package_show(body: bytes) -> str:
    result = json.loads(body)["result"]
    urls = [r["url"] for r in result["resources"] if (r.get("format") or "").upper() == "CSV"]
    if not urls:
        raise YamanashiKumaSourceError("package has no CSV resource")
    return urls[0]


def _rows(data: bytes) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    header = next(reader, None)
    if not header or [h.strip() for h in header[: len(HEADER_START)]] != HEADER_START:
        raise YamanashiKumaSourceError(f"CSV header changed: {header}")
    out = []
    for raw in reader:
        if not raw or not raw[0].strip():
            continue
        raw = (raw + [""] * len(HEADER_START))[: len(HEADER_START)]
        out.append(dict(zip(HEADER_START, (c.strip() for c in raw), strict=True)))
    return out


def _observed(day: str, clock: str) -> str | None:
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", day)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    t = re.fullmatch(r"(\d{1,2}):(\d{2})", clock or "")
    if t and int(t.group(1)) < 24 and int(t.group(2)) < 60:
        return datetime(d.year, d.month, d.day, int(t.group(1)), int(t.group(2)), tzinfo=kumalib.JST).isoformat()
    return d.isoformat()


def parse_csvs(files: list[bytes]) -> dict:
    by_no: dict[str, dict[str, str]] = {}
    for data in files:
        for row in _rows(data):
            by_no[row["No."]] = row  # the same number in both files is the same record: the later file wins
    rows = list(by_no.values())
    if len(rows) < MIN_ROWS:
        raise YamanashiKumaSourceError(f"too few rows: {len(rows)} < {MIN_ROWS}")
    sightings, unparsed, bad_coords = [], 0, 0
    for row in rows:
        at = _observed(row["年月日"], row["時間"])
        if at is None:
            unparsed += 1
            continue
        rec = {"observed_at": at, "city": row["目撃市町村"], "place": row["場所"], "count": _count(row["目撃頭数"]),
               "kind": "目撃", "species": "ツキノワグマ"}
        if row["緯度"] or row["経度"]:   # a blank pair is simply "no position"; a filled one must be a number inside the prefecture
            try:
                lat, lon = float(row["緯度"].strip(" ,")), float(row["経度"].strip(" ,"))
            except ValueError:
                bad_coords += 1
            else:
                if BOX[0] <= lat <= BOX[1] and BOX[2] <= lon <= BOX[3]:
                    rec.update(kumalib.coord(lat, lon))
                else:
                    bad_coords += 1
        if not rec["city"]:
            unparsed += 1
            continue
        sightings.append(rec)
    total = len(rows)
    if unparsed / total > UNPARSED_LIMIT:
        raise YamanashiKumaSourceError(f"too many unparsed rows: {unparsed}/{total}")
    if bad_coords / total > BAD_COORD_LIMIT:
        raise YamanashiKumaSourceError(f"too many bad coordinates: {bad_coords}/{total}")
    as_of = max(date.fromisoformat(s["observed_at"][:10]) for s in sightings)
    return kumalib.package(source="yamanashi", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, sightings=sightings, page=PAGE,
                           files=[], unparsed=unparsed, bad_coords=bad_coords)


def _count(raw: str) -> int | None:
    return int(raw) if re.fullmatch(r"\d+", raw or "") else None


def collect() -> dict:
    urls = [csv_url_from_package_show(fetch(API + name).body) for name in DATASETS]
    out = parse_csvs([fetch(u).body for u in urls])
    if date.fromisoformat(out["as_of"]) > datetime.now(kumalib.JST).date() + timedelta(days=2):
        raise YamanashiKumaSourceError(f"newest date {out['as_of']} lies in the future (a typo in the CSV?)")
    out["source_file"] = urls
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
