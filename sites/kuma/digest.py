"""Weekly digest of the sightings that municipalities publish (Mon-Sun weeks, ISO week keys like 2026-W40).

Pure functions: every number comes from the prefecture / city lists in data/*_kuma.json and data/otsu_bear.json.
A prefecture's list goes into the digest only for the months in which the number of rows equals that prefecture's own
monthly figure (so a truncated list, as Akita's is, is left out instead of being counted wrongly), and only up to the
as-of date the prefecture itself states.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start(key: str) -> date:
    y, w = key.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def fy_key(d: date) -> str:
    """Japanese fiscal year (April-March) as the sources label it: 2026-05-01 -> 'R08'."""
    return f"R{(d.year if d.month >= 4 else d.year - 1) - 2018:02d}"


def fy_first_day(d: date) -> date:
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1)


def _days(rows: list[dict]) -> list[date]:
    return [date.fromisoformat(r["observed_at"][:10]) for r in rows if r.get("observed_at")]


def pref_source(key: str, name: str, raw: dict) -> dict | None:
    """One prefecture's rows as dates, with the last day its figures cover; None when nothing can be trusted."""
    rows = _days(raw.get("sightings", []))
    if not rows:
        return None
    as_of = date.fromisoformat(raw["as_of"])
    monthly = raw.get("monthly", {})
    per_month = Counter((d.year, d.month) for d in rows)  # every row, including any dated after as_of
    return {"key": key, "name": name, "days": [d for d in rows if d <= as_of], "as_of": as_of, "per_month": per_month,
            "monthly": monthly, "note": ""}


def otsu_source(raw: dict) -> dict | None:
    rows = [r for r in raw.get("sightings", []) if r.get("observed_at")]
    if not rows:
        return None
    cov = date.fromisoformat(raw["fetched_at"][:10])
    return {"key": "otsu", "name": "滋賀県大津市", "days": [d for d in _days(rows) if d <= cov], "as_of": cov, "per_month": None,
            "monthly": None, "note": "大津市が公開している地図の件数を、このサイトが読み取ったものです(市の公表件数と、1件ほど違うことがあります)。"}


def covers(src: dict, ws: date) -> bool:
    """True when the whole week starting `ws` lies in the source's published range and in months whose rows add up."""
    we = ws + timedelta(days=6)
    if we > src["as_of"]:
        return False
    if src["per_month"] is None:
        return True
    return all(src["monthly"].get(fy_key(d), {}).get(str(d.month)) == src["per_month"].get((d.year, d.month), 0) for d in (ws, we))


def build(sources: list[dict], first_day: date | None = None) -> dict:
    """{weeks: [key newest first], by_week: {key: {source key: count}}, sources: {key: source}}."""
    sources = [s for s in sources if s]
    if not sources:
        return {"weeks": [], "by_week": {}, "sources": {}}
    latest = max(s["as_of"] for s in sources)
    first_day = first_day or fy_first_day(latest)
    ws = week_start(week_key(first_day))
    if ws < first_day:
        ws += timedelta(days=7)
    by_week: dict[str, dict[str, int]] = {}
    while ws + timedelta(days=6) <= latest:
        row = {}
        for s in sources:
            if covers(s, ws):
                row[s["key"]] = sum(1 for d in s["days"] if ws <= d <= ws + timedelta(days=6))
        if row:
            by_week[week_key(ws)] = row
        ws += timedelta(days=7)
    return {"weeks": sorted(by_week, reverse=True), "by_week": by_week, "sources": {s["key"]: s for s in sources}}


def prev_key(key: str) -> str:
    return week_key(week_start(key) - timedelta(days=7))


def common_total(dig: dict, key: str) -> tuple[int, int | None, list[str]]:
    """This week's total over the sources that also cover the previous week, and that previous total (None if none)."""
    cur = dig["by_week"][key]
    prev = dig["by_week"].get(prev_key(key), {})
    both = [k for k in cur if k in prev]
    return sum(cur[k] for k in both), (sum(prev[k] for k in both) if both else None), both
