"""Okayama prefecture bear sighting Google My Maps KML."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from sokuhou.http import fetch
from sokuhou.sources.kumalib import coord, trim_for_store

PAGE = "https://www.pref.okayama.jp/page/1006862.html"
SOURCE_FILE = "https://www.google.com/maps/d/kml?mid=1y64vgpv0Yc6srgFeVC5ZkJf37kNuuKI&forcekml=1"
CREDIT = "出典:岡山県「岡山県ツキノワグマ出没情報」を加工して作成(公共データ利用規約(第1.0版)に基づく)"
UPDATE_NOTE = "岡山県が、適宜、地図を更新します。最新の目撃は、更新時点から遅れます"
DOCUMENT_NAME = "岡山県ツキノワグマ出没情報"
KML_NS = {"k": "http://www.opengis.net/kml/2.2"}
DATA_LAT = "緯度"
DATA_LON = "経度"
DATA_WAREKI = "和暦"
DATA_CITY = "市町村"
DATA_PLACE = "大字"
MIN_PLACEMARKS = 50
BAD_COORD_LIMIT = 0.01
UNPARSED_LIMIT = 0.01
JST = timezone(timedelta(hours=9))


class OkayamaKumaSourceError(ValueError):
    pass


def _data_value(placemark: ET.Element, name: str) -> str:
    value = placemark.find(f".//k:Data[@name='{name}']/k:value", KML_NS)
    return (value.text or "").strip() if value is not None else ""


def _parse_date(raw: str) -> date | None:
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", (raw or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def _fiscal_start(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def _fy_label(fy_start: int) -> str:
    return f"R{fy_start - 2018:02d}"


def _wareki_fiscal_label(day: date) -> str:
    return f"R{_fiscal_start(day) - 2018}"


def parse_kml(data: bytes) -> dict:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise OkayamaKumaSourceError("KML XML is not parseable") from e
    if root.tag != "{http://www.opengis.net/kml/2.2}kml":
        raise OkayamaKumaSourceError("KML root changed")
    document = root.find("k:Document", KML_NS)
    if document is None:
        raise OkayamaKumaSourceError("KML Document is missing")
    if document.findtext("k:name", default="", namespaces=KML_NS) != DOCUMENT_NAME:
        raise OkayamaKumaSourceError("KML Document name changed")

    placemarks = document.findall(".//k:Placemark", KML_NS)
    if len(placemarks) < MIN_PLACEMARKS:
        raise OkayamaKumaSourceError(f"KML has too few placemarks: {len(placemarks)} < {MIN_PLACEMARKS}")

    parsed: list[tuple[ET.Element, date]] = []
    unparsed = 0
    bad_coords = 0
    wareki_mismatches = 0
    coords: dict[int, dict | None] = {}
    for placemark in placemarks:
        day = _parse_date(placemark.findtext("k:name", default="", namespaces=KML_NS))
        if day is None:
            unparsed += 1
        else:
            parsed.append((placemark, day))
            if _data_value(placemark, DATA_WAREKI) != _wareki_fiscal_label(day):
                wareki_mismatches += 1
        try:
            lat = float(_data_value(placemark, DATA_LAT))
            lon = float(_data_value(placemark, DATA_LON))
        except ValueError:
            bad_coords += 1
            coords[id(placemark)] = None
        else:
            if not (34.4 <= lat <= 35.4 and 133.2 <= lon <= 134.5):
                bad_coords += 1
                coords[id(placemark)] = None
            else:
                coords[id(placemark)] = coord(lat, lon)

    total = len(placemarks)
    if unparsed / total > UNPARSED_LIMIT:
        raise OkayamaKumaSourceError(f"too many unparseable dates: {unparsed}/{total}")
    if bad_coords / total > BAD_COORD_LIMIT:
        raise OkayamaKumaSourceError(f"too many coordinates outside Okayama box: {bad_coords}/{total}")
    if not parsed:
        raise OkayamaKumaSourceError("no parseable placemark dates")

    newest = max(day for _, day in parsed)
    current_start = _fiscal_start(newest)
    window = {_fy_label(current_start), _fy_label(current_start - 1)}
    monthly: dict[str, dict[str, int]] = {label: {} for label in sorted(window, reverse=True)}
    sightings = []
    for order, (placemark, day) in enumerate(parsed):
        fy = _fy_label(_fiscal_start(day))
        if fy not in window:
            continue
        months = monthly.setdefault(fy, {})
        month = str(day.month)
        months[month] = months.get(month, 0) + 1
        sightings.append({
            "_sort": day,
            "_order": order,
            "observed_at": day.isoformat(),
            "city": _data_value(placemark, DATA_CITY),
            "place": _data_value(placemark, DATA_PLACE),
            "count": None,
            "kind": "目撃",
            "species": "ツキノワグマ",
            **(coords.get(id(placemark)) or {}),
        })
    sightings.sort(key=lambda rec: (rec["_sort"], -rec["_order"]), reverse=True)
    for rec in sightings:
        del rec["_sort"]
        del rec["_order"]

    return {
        "source": "okayama",
        "credit": CREDIT,
        "as_of": newest.isoformat(),
        "update_note": UPDATE_NOTE,
        "fy_current": _fy_label(current_start),
        "sightings": sightings,
        "monthly": {fy: months for fy, months in monthly.items() if months},
        "monthly_note": "KMLは種別を示していないため、全件を目撃として集計しています。",
        "bad_coords": bad_coords,
        "unparsed": unparsed,
        "wareki_mismatches": wareki_mismatches,
        "wareki_note": "和暦は年度を示すものとして日付と照合しています。",
    }


def collect() -> dict:
    out = parse_kml(fetch(SOURCE_FILE).body)
    out["sightings_in_window"] = len(out["sightings"])
    out["sightings"] = trim_for_store(out["sightings"], date.fromisoformat(out["as_of"]))
    out.update({
        "source_page": PAGE,
        "source_file": SOURCE_FILE,
        "fetched_at": datetime.now(JST).isoformat(),
    })
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
