"""atomou 案7: a day of every month that moves off the days the banks (or an office) are closed - "毎月15日、休みなら前の営業日".  assets/rule.js does the same count in the browser; both are
checked on the same hand-verified cases (tests/fixtures/atomou/date_vectors.json, "bizday").

The closed days of a bank, from the law (e-Gov, checked 2026-10-11): 銀行法第15条 "銀行の休日は、日曜日その他政令で定める日に限る" and 銀行法施行令第5条第1項: (1) the holidays of the
国民の祝日に関する法律 (including the substitute holidays), (2) 12月31日 to 1月3日, (3) 土曜日.  Together with Sunday: Saturday, Sunday, the holidays and 12/31-1/3.  A branch may close on
other days (施行令第5条第2項), so a result is a guide ("目安").  The pension (日本年金機構): paid on the 15th of the even months; "15日が土日または祝日のときは、その直前の平日に支払われます" - the
15th of an even month is never near the year end, so the bank rule and the weekday rule give the same day for it.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from sites.atomou import calendar_data as cal

PENSION_SOURCE = "https://www.nenkin.go.jp/section/faq/jukyu/uketori/uketori/shiharaiduki/20140421-01.html"
BANK_LAW = "https://laws.e-gov.go.jp/law/357CO0000000040"


def holiday_set(first_year: int, last_year: int) -> set[date]:
    """Every national holiday (and substitute holiday) from first_year to last_year; the rules of cal.holidays start in 2020."""
    out: set[date] = set()
    for y in range(max(first_year, 2020), last_year + 1):
        out.update(cal.holidays(y))
    return out


def is_closed(d: date, hol: set[date], bank: bool = True) -> bool:
    """A closed day: Saturday, Sunday, a holiday; for a bank also 12/31 to 1/3."""
    if d.weekday() >= 5 or d in hol:
        return True
    return bank and ((d.month == 12 and d.day == 31) or (d.month == 1 and d.day <= 3))


def adjust(d: date, how: str, hol: set[date], bank: bool = True) -> date:
    """how: 'prev' (the business day before, or the day itself), 'next' (the one after) or 'none'."""
    if how == "none":
        return d
    step = -1 if how == "prev" else 1
    n = 0
    while is_closed(d, hol, bank):
        d += timedelta(days=step)
        n += 1
        if n > 20:
            raise ValueError("no business day within 20 days")
    return d


def nominal(y: int, m: int, day: int) -> date:
    """The day of the month; 0, or a day the month does not have (31 in April), is the last day of the month."""
    last = calendar.monthrange(y, m)[1]
    return date(y, m, last if day == 0 or day > last else day)


def occurrences(rule: dict, start: date, n: int, hol: set[date]) -> list[date]:
    """The next n dates of a rule {day, how, bank, months} that are on or after start.  months: 'all', 'even' or 'odd'."""
    out: list[date] = []
    y, m = start.year, start.month - 1
    if m < 1:
        y, m = y - 1, 12
    for _ in range(n * 3 + 30):
        if rule.get("months", "all") == "all" or (m % 2 == 0) == (rule["months"] == "even"):
            d = adjust(nominal(y, m, rule["day"]), rule.get("how", "prev"), hol, rule.get("bank", True))
            if d >= start and d not in out:
                out.append(d)
        m += 1
        if m > 12:
            y, m = y + 1, 1
        if len(out) >= n:
            break
    return sorted(out)[:n]


def pension_dates(y: int, hol: set[date] | None = None) -> list[date]:
    """The six regular payment days of a year: the 15th of the even months, the weekday before when it falls on a Saturday, a Sunday or a holiday."""
    hol = hol if hol is not None else holiday_set(y, y)
    return [adjust(date(y, m, 15), "prev", hol, True) for m in (2, 4, 6, 8, 10, 12)]
