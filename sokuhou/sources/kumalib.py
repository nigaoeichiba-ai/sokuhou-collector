"""Helpers shared by the prefecture / city bear-sighting adapters.

Every adapter stores `sightings` newest first and a `monthly` table; the site, the weekly digest and the map read them
without knowing which prefecture they came from.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def fiscal_start(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def fy_label(start_year: int) -> str:
    """2026 -> 'R08' (the label used all over the site)."""
    return f"R{start_year - 2018:02d}"


def coord(lat: float, lon: float) -> dict:
    """Rounded to 4 decimals (about 10 m): keeps the stored files small and is no more precise than the sources."""
    return {"lat": round(lat, 4), "lon": round(lon, 4)}


def trim_for_store(sightings: list[dict], newest: date) -> list[dict]:
    """Keep the whole current fiscal year, plus the previous January-March (the weekly digest compares across the April boundary).

    Older rows are counted in `monthly` already; storing them would only make the data file (and every daily commit) bigger.
    """
    start = fiscal_start(newest)
    cutoff = date(start, 1, 1)
    return [s for s in sightings if s.get("observed_at") and date.fromisoformat(s["observed_at"][:10]) >= cutoff]


def now_jst_iso() -> str:
    return datetime.now(JST).isoformat()
