"""Otsu City black-bear sighting map (Google My Maps published by the city).

KML layout: one <Folder> per fiscal year ("令和８年度ツキノワグマ目撃情報"), one <Placemark> per
sighting named "<M>/<D> <H:MM>頃 <place>" (full-width digits, colons and spaces occur), and
Document/description carries the city's own per-year counts, which we use as a cross-check.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from sokuhou.http import fetch

MID = "1rE5HcSdJnm2gX3iT1FMt0aCVuQ9ArDs"
URL = f"https://www.google.com/maps/d/kml?mid={MID}&forcekml=1"
JST = timezone(timedelta(hours=9))
_NS = {"k": "http://www.opengis.net/kml/2.2"}
_FY = re.compile(r"令和(\d+)年度")
_NAME = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(?:(\d{1,2}):(\d{2})頃?\s+)?(.+)$", re.S)
_COUNT = re.compile(r"令和(\d+)年度[^0-9]*?(?:\d+月\d+日現在\s*)?(\d+)件")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def _observed(fy_reiwa: int, month: int, day: int, hour: int | None, minute: int | None) -> str:
    """Fiscal year runs April..March: Jan-Mar belong to the following calendar year."""
    year = 2018 + fy_reiwa + (1 if month <= 3 else 0)
    if hour is None:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return datetime(year, month, day, hour, minute, tzinfo=JST).isoformat()


def parse(kml: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(JST)
    root = ET.fromstring(kml)
    doc = root.find("k:Document", _NS)
    desc = _norm(doc.findtext("k:description", default="", namespaces=_NS).replace("<br>", " "))
    official_counts = {f"令和{n}年度": int(c) for n, c in _COUNT.findall(desc)}

    sightings, unparsed = [], []
    for folder in doc.findall("k:Folder", _NS):
        folder_name = _norm(folder.findtext("k:name", default="", namespaces=_NS))
        fy = _FY.search(folder_name)
        for pm in folder.findall("k:Placemark", _NS):
            raw = pm.findtext("k:name", default="", namespaces=_NS)
            coords = (pm.findtext("k:Point/k:coordinates", default="", namespaces=_NS) or "").strip()
            m = _NAME.match(_norm(raw))
            if not (fy and m and coords):
                unparsed.append({"folder": folder_name, "name": raw.strip(), "coordinates": coords})
                continue
            lon, lat = (float(x) for x in coords.split(",")[:2])
            hour = int(m.group(3)) if m.group(3) else None
            minute = int(m.group(4)) if m.group(4) else None
            sightings.append({
                "observed_at": _observed(int(fy.group(1)), int(m.group(1)), int(m.group(2)), hour, minute),
                "place": m.group(5),
                "lat": lat,
                "lon": lon,
                "fiscal_year": f"令和{fy.group(1)}年度",
            })
    sightings.sort(key=lambda s: s["observed_at"], reverse=True)

    counted: dict[str, int] = {}
    for s in sightings:
        counted[s["fiscal_year"]] = counted.get(s["fiscal_year"], 0) + 1
    mismatch = {
        fy: {"official": official_counts[fy], "parsed": counted.get(fy, 0)}
        for fy in official_counts
        if official_counts[fy] != counted.get(fy, 0)
    }
    return {
        "source": URL,
        "fetched_at": now.isoformat(),
        "official_counts": official_counts,
        "parsed_counts": counted,
        "count_mismatch": mismatch,
        "sightings": sightings,
        "unparsed": unparsed,
    }


def collect() -> dict:
    return parse(fetch(URL).body.decode("utf-8"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
