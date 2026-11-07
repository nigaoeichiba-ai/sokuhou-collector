"""Shared helpers of the generator of sites/shiken/content/*.json.

Dates, weekdays and "N days left" are computed here, never typed by hand: every date comes from data/ or from the table in facts.py,
which carries the source and the day it was checked.  python -m sites.shiken.gen  (from sokuhou-collector/) writes ../content/ and ../site.json.
"""
from __future__ import annotations

from datetime import date

import os
from datetime import datetime, timedelta, timezone

CHECKED = "2026-11-03"           # the day the dates were checked against the primary sources (the pages' update day)
TODAY = date.fromisoformat(os.environ.get("SHIKEN_TODAY") or datetime.now(timezone(timedelta(hours=9))).date().isoformat())   # "N days left" counts from today (JST), the day of the build


def set_today(x: str) -> None:
    global TODAY
    TODAY = date.fromisoformat(x)


def today_j() -> str:
    return f"{TODAY.year}年{TODAY.month}月{TODAY.day}日"
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


def rel(x: date | str) -> str:
    """'あと22日' / '今日' / '3日前': a sentence that must stay true after the day has passed"""
    n = left(x)
    return "今日" if n == 0 else f"あと{n}日" if n > 0 else f"{-n}日前"


def ver(x: date | str, now: str = "です", then: str = "でした") -> str:
    """the ending of a sentence about the day x: 'です' until it has come, 'でした' after"""
    return now if left(x) >= 0 else then


# The day the new design (and its pages) went out: the pages that were rebuilt carry it as their update day.
DESIGN_DATE = "2026-11-08"
# The owner's rule of 2026-11-03: no link to an official page on the site.  The spec of the new design has one ('公式で申し込む'); it stays off until the owner says yes.
OFFICIAL_LINKS = False
