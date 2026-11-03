"""Shared helpers of the generator of sites/shiken/content/*.json.

Dates, weekdays and "N days left" are computed here, never typed by hand: every date comes from data/ or from the table in facts.py,
which carries the source and the day it was checked.  python -m sites.shiken.gen  (from sokuhou-collector/) writes ../content/ and ../site.json.
"""
from __future__ import annotations

from datetime import date

TODAY = date(2026, 11, 3)          # the day the dates were checked against the primary sources
CHECKED = "2026-11-03"
WD = "月火水木金土日"


def d(s: str) -> date:
    return date.fromisoformat(s)


def wd(x: date) -> str:
    return WD[x.weekday()]


def jp(x: date | str, year: bool = True) -> str:
    """2027年2月16日(火)"""
    x = d(x) if isinstance(x, str) else x
    return f"{x.year}年{x.month}月{x.day}日({wd(x)})" if year else f"{x.month}月{x.day}日({wd(x)})"


def md(x: date | str) -> str:
    return jp(x, False)


def span(a: date | str, b: date | str) -> str:
    """2026年11月6日(金)から11月27日(金)  (the year is written once when both days share it)"""
    a, b = (d(a) if isinstance(a, str) else a), (d(b) if isinstance(b, str) else b)
    if a.year == b.year:
        return f"{jp(a)}から{md(b)}"
    return f"{jp(a)}から{jp(b)}"


def left(x: date | str) -> int:
    x = d(x) if isinstance(x, str) else x
    return (x - TODAY).days


def in_days(x: date | str) -> str:
    n = left(x)
    return "本日" if n == 0 else f"あと{n}日" if n > 0 else f"{-n}日前に終了"


def a(path: str, text: str) -> str:
    return f'<a href="{path}">{text}</a>'
