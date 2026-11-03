"""Pick events from facts.EVENTS by day, and render rows."""
from __future__ import annotations

from .common import TODAY, d, ev_span, phase, state
from .facts import BY_ID, EVENTS


def grp(g: str) -> list[dict]:
    return sorted((e for e in EVENTS if e["group"] == g), key=lambda e: e["start"])


def upcoming(g: str | None = None) -> list[dict]:
    return [e for e in sorted(EVENTS, key=lambda e: e["start"]) if phase(e) != "done" and (g is None or e["group"] == g)]


def latest_done(g: str) -> dict | None:
    xs = [e for e in grp(g) if phase(e) == "done"]
    return xs[-1] if xs else None


def days(e) -> int:
    return (d(e["end"]) - d(e["start"])).days + 1


def row(e, with_state=True) -> list:
    r = [e["name"], ev_span(e)]
    if with_state:
        r.append(state(e))
    return r


def dur(e) -> str:
    """Length of an event as '6日6時間' (the end minute counts as the whole minute: 1:59 means until 2:00)."""
    from datetime import datetime, timedelta
    def at(day, t, default):
        h, m = (t or default).split(":")
        return datetime(d(day).year, d(day).month, d(day).day, int(h), int(m))
    a = at(e["start"], e.get("start_t"), "00:00")
    b = at(e["end"], e.get("end_t"), "23:59") + timedelta(minutes=1)
    mins = int((b - a).total_seconds() // 60)
    days_, hrs = divmod(mins // 60, 24)
    return f"{days_}日{hrs}時間" if hrs else f"{days_}日"
