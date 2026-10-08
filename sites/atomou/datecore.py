"""Date arithmetic of 「あと何日、もう何日」, shared by the build (static values) and the browser (assets/core.js implements the same functions).

Everything works on calendar dates (year, month, day); there is no time of day and no time zone.  "Today" is always passed in by the caller
(the build uses Asia/Tokyo's date, the browser uses the visitor's local date); nothing here reads the clock or uses JavaScript-style Date parsing.
The same rules are checked on both sides with tests/fixtures/atomou/date_vectors.json (hand-verified cases) in a real Chrome.

Rules (SPEC 2-4, 3):
  * total days is the difference of the calendar dates;
  * years / months / days: the largest whole number of months N for which (start + N months) <= end, where "+ N months" keeps the day of the month
    and falls back to the last day of a shorter month (31 Jan + 1 month = 28 Feb); days = the rest;
  * the breakdown is always measured from the earlier date to the later one, so past and future are symmetric.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

ERAS = {"reiwa": ("令和", 2018), "heisei": ("平成", 1988), "showa": ("昭和", 1925), "taisho": ("大正", 1911), "meiji": ("明治", 1867)}
SHORT_DAYS = 100  # below this many days the days are the big number; from here on the years/months/days are


def add_months(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) + n
    y, m = divmod(total, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def total_days(a: date, b: date) -> int:
    """Signed days from a to b (positive when b is later)."""
    return (b - a).days


def ymd(a: date, b: date) -> tuple[int, int, int]:
    """Whole years, months and days between two dates (order does not matter)."""
    s, e = (a, b) if a <= b else (b, a)
    n = (e.year - s.year) * 12 + (e.month - s.month)
    if add_months(s, n) > e:
        n -= 1
    base = add_months(s, n)
    return n // 12, n % 12, (e - base).days


def next_thousand(start: date, today: date) -> tuple[int, date]:
    """The next multiple of 1000 days since `start` that is after today (or today itself when today is one)."""
    since = (today - start).days
    k = max(1, -(-since // 1000)) if since > 0 else 1
    n = k * 1000
    return n, start + timedelta(days=n)


def is_thousand_day(start: date, today: date) -> bool:
    d = (today - start).days
    return d > 0 and d % 1000 == 0


def day_of_year(d: date) -> tuple[int, int]:
    """(this is day N, N days remain after it) within the year."""
    n = d.timetuple().tm_yday
    total = 366 if calendar.isleap(d.year) else 365
    return n, total - n


def fiscal_year(d: date) -> tuple[int, int, int]:
    """Japanese fiscal year (1 Apr - 31 Mar): (year it started in, day number within it, days remaining after today)."""
    y = d.year if d.month >= 4 else d.year - 1
    start, end = date(y, 4, 1), date(y + 1, 3, 31)
    return y, (d - start).days + 1, (end - d).days


def wareki_to_year(era: str, n: int) -> int:
    return ERAS[era][1] + n


def unit_text(y: int, m: int, d: int) -> str:
    parts = []
    if y:
        parts.append(f"{y}年")
    if m:
        parts.append(f"{m}か月")
    if d or not parts:
        parts.append(f"{d}日")
    return "".join(parts)


def countdown(target: date, today: date, precision: str = "day") -> dict:
    """What the cards show.  dir: 'ato' (future), 'mou' (past), 'today'.  big: the large text; sub: the small one (total days or '');
    total: signed days (target - today); ymd: the breakdown; approx: True for month/year precision."""
    if precision == "year":
        n = today.year - target.year
        word = "もう" if n > 0 else ("あと" if n < 0 else "")
        return {"dir": "mou" if n > 0 else ("ato" if n < 0 else "today"), "big": ("今年" if n == 0 else f"{word}約{abs(n):,}年"), "sub": "", "total": None,
                "ymd": (abs(n), 0, 0), "approx": True}
    if precision == "month":
        n = (today.year - target.year) * 12 + (today.month - target.month)
        a = abs(n)
        txt = unit_text(a // 12, a % 12, 0) if a else "今月"
        return {"dir": "mou" if n > 0 else ("ato" if n < 0 else "today"), "big": (txt if a == 0 else ("もう約" if n > 0 else "あと約") + txt), "sub": "", "total": None,
                "ymd": (a // 12, a % 12, 0), "approx": True}
    t = total_days(today, target)
    if t == 0:
        return {"dir": "today", "big": "今日", "sub": "", "total": 0, "ymd": (0, 0, 0), "approx": False}
    word = "あと" if t > 0 else "もう"
    y, m, d = ymd(today, target)
    if abs(t) < SHORT_DAYS:
        return {"dir": "ato" if t > 0 else "mou", "big": f"{word}{abs(t)}日", "sub": "", "total": t, "ymd": (y, m, d), "approx": False}
    return {"dir": "ato" if t > 0 else "mou", "big": word + unit_text(y, m, d), "sub": f"{abs(t):,}日", "total": t, "ymd": (y, m, d), "approx": False}
