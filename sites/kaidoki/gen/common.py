"""Shared helpers of the generator of sites/kaidoki/content/*.json.

Every date, weekday and "N days left" is computed here from data in facts.py, never typed in a sentence.
TODAY is the day in Japan when the build runs (KAIDOKI_TODAY=2026-11-03 fixes it for tests).  CHECKED is the day the facts were read on the organisers' own pages.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

CHECKED = "2026-11-03"
REVERIFIED = "2026-11-12"          # the day the sales of facts.py and the schedule of redesign/schedule.py were read again (the "確認日" of the top page and the calendars); CHECKED stays the day the pages were first written
WD = "月火水木金土日"
JST = timezone(timedelta(hours=9))


def _today() -> date:
    v = os.environ.get("KAIDOKI_TODAY")
    return date.fromisoformat(v) if v else datetime.now(JST).date()


TODAY = _today()


def d(s) -> date:
    return s if isinstance(s, date) and not isinstance(s, datetime) else date.fromisoformat(str(s)[:10])


def wd(x) -> str:
    return WD[d(x).weekday()]


def jp(x, year: bool = True) -> str:
    """2026年11月4日(水)"""
    x = d(x)
    return f"{x.year}年{x.month}月{x.day}日({wd(x)})" if year else f"{x.month}月{x.day}日({wd(x)})"


def md(x) -> str:
    return jp(x, False)


def hm(t: str) -> str:
    """'20:00' -> '20時', '01:59' -> '1時59分'"""
    h, m = t.split(":")
    return f"{int(h)}時" if m == "00" else f"{int(h)}時{int(m)}分"


def span(ev) -> str:
    """2026年11月4日(水)20時から11月11日(水)1時59分まで (year written once when both days share it)"""
    a, b = d(ev["start"]), d(ev["end"])
    left = f"{jp(a)}{hm(ev['start_t'])}" if ev.get("start_t") else jp(a)
    if a == b and not ev.get("end_t"):
        return left
    right = (md(b) if a.year == b.year else jp(b)) + (hm(ev["end_t"]) if ev.get("end_t") else "")
    return f"{left}から{right}まで"


def left_days(x) -> int:
    return (d(x) - TODAY).days


def until(x) -> str:
    """あと22日 / 本日 / 3日前"""
    n = left_days(x)
    return "本日" if n == 0 else f"あと{n}日" if n > 0 else f"{-n}日前"


def phase(ev) -> str:
    """before / now / done, by the day only (the hour is not used)."""
    if TODAY < d(ev["start"]):
        return "before"
    if TODAY <= d(ev["end"]):
        return "now"
    return "done"


def state(ev) -> str:
    p = phase(ev)
    if p == "before":
        return f"開始まで{until(ev['start'])}"
    if p == "now":
        return "開催中" if TODAY != d(ev["end"]) else "本日最終日"
    return "終了"


def a(path: str, text: str) -> str:
    return f'<a href="{path}">{text}</a>'


def ev_span(ev) -> str:
    """Like span(), but an event with no hours (Yahoo's 'noon', or no time at all) reads naturally."""
    a, b = d(ev["start"]), d(ev["end"])
    left = jp(a) + (hm(ev["start_t"]) if ev.get("start_t") and ev["start_t"] != "00:00" else ("0時" if ev.get("start_t") == "00:00" else ""))
    right = (md(b) if a.year == b.year else jp(b)) + (hm(ev["end_t"]) if ev.get("end_t") else "")
    return f"{left}から{right}" + ("まで" if ev.get("end_t") else "")
