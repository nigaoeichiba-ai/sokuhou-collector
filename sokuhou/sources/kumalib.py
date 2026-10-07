"""Helpers shared by the prefecture / city bear-sighting adapters.

Every adapter stores `sightings` newest first and a `monthly` table; the site, the weekly digest and the map read them
without knowing which prefecture they came from.
"""
from __future__ import annotations

import re
import unicodedata
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


def package(*, source: str, credit: str, update_note: str, as_of: date, sightings: list[dict], page: str, files: list[str],
            unparsed: int = 0, bad_coords: int = 0, extra: dict | None = None) -> dict:
    """The stored shape every prefecture / city source shares (see build.prepare_prefs).

    sightings: dicts with observed_at (ISO date or datetime), city, place, count, kind, species and optionally lat / lon, in any order.
    monthly is counted from ALL the rows (per fiscal year), then only the current fiscal year (plus the previous January-March) is stored.
    """
    rows = sorted((s for s in sightings if s.get("observed_at")), key=lambda s: (s["observed_at"], s["place"]), reverse=True)
    monthly: dict[str, dict[str, int]] = {}
    for s in rows:
        d = date.fromisoformat(s["observed_at"][:10])
        months = monthly.setdefault(fy_label(fiscal_start(d)), {})
        months[str(d.month)] = months.get(str(d.month), 0) + 1
    out = {
        "source": source, "credit": credit, "as_of": as_of.isoformat(), "update_note": update_note,
        "fy_current": fy_label(fiscal_start(as_of)), "sightings": trim_for_store(rows, as_of), "sightings_in_window": len(rows),
        "monthly": monthly, "unparsed": unparsed, "bad_coords": bad_coords,
        "source_page": page, "source_file": files[0] if len(files) == 1 else files, "fetched_at": now_jst_iso(),
    }
    out.update(extra or {})
    return out


def fullwidth_to_int(text: str) -> int | None:
    """'親子グマ２頭' -> 2, 'ヒグマ１頭' -> 1, nothing numeric -> None."""
    m = re.search(r"(\d+)\s*頭", unicodedata.normalize("NFKC", text or ""))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- sources WITHOUT an explicit re-use licence ("counts" mode)
#
# For these, only municipality, month, count and the latest date are kept (no place, no coordinates, no row list), the pages show
# nothing else, and the data file in the public repository holds nothing else either.  The adapter aggregates in memory.

COUNTS_UA = "kuma-sokuho-collector/1.0 (+https://kuma-sokuho.com/about/)"
STOPPED: set[str] = set()   # source names whose publisher asked us to stop: never collected, never shown (see docs/KUMA_COMPETITORS_AND_ROADMAP.md)


def package_counts(*, source: str, credit: str, update_note: str, as_of: date, rows: list[dict], page: str, files: list[str],
                   unparsed: int = 0) -> dict:
    """rows: dicts with observed_at (ISO date or datetime) and city only; everything else is ignored on purpose."""
    muni: dict[str, dict] = {}
    monthly: dict[str, dict[str, int]] = {}
    for r in rows:
        if not r.get("observed_at") or not r.get("city"):
            continue
        d = date.fromisoformat(r["observed_at"][:10])
        fy = fy_label(fiscal_start(d))
        m = muni.setdefault(r["city"], {"monthly": {}, "latest": d.isoformat()})
        m["monthly"].setdefault(fy, {})[str(d.month)] = m["monthly"].get(fy, {}).get(str(d.month), 0) + 1
        m["latest"] = max(m["latest"], d.isoformat())
        monthly.setdefault(fy, {})[str(d.month)] = monthly.get(fy, {}).get(str(d.month), 0) + 1
    fy_cur = fy_label(fiscal_start(as_of))
    return {
        "mode": "counts", "source": source, "credit": credit, "as_of": as_of.isoformat(), "update_note": update_note, "fy_current": fy_cur,
        "total_fy": sum(monthly.get(fy_cur, {}).values()), "monthly": monthly, "municipalities": dict(sorted(muni.items())),
        "unparsed": unparsed, "source_page": page, "source_file": files[0] if len(files) == 1 else files, "fetched_at": now_jst_iso(),
    }


_ROBOTS: dict[str, "object"] = {}


def polite_fetch(url: str, timeout: float = 30.0, legacy_tls: bool = False) -> bytes:
    """One GET with an identifying User-Agent, after checking the site's robots.txt (a disallowed or unreadable-by-rule URL is not fetched)."""
    import ssl
    import urllib.request
    from urllib.parse import urlparse
    from urllib.robotparser import RobotFileParser
    p = urlparse(url)
    rp = _ROBOTS.get(p.netloc)
    if rp is None:
        rp = RobotFileParser()
        try:
            req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": COUNTS_UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except Exception:  # noqa: BLE001 - no robots.txt (404) or none reachable: nothing forbids the fetch
            rp.parse([])
        _ROBOTS[p.netloc] = rp
    if not rp.can_fetch(COUNTS_UA, url):
        raise PermissionError(f"robots.txt of {p.netloc} disallows {url}")
    ctx = None
    if legacy_tls:
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    req = urllib.request.Request(url, headers={"User-Agent": COUNTS_UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()
