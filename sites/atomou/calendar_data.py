"""atomou: the calendar facts behind the three 特集 pages under /kyou/ (holidays, the 24 solar terms, December), worked out here and not copied from anywhere.

holidays: the national holidays of Japan are worked out from the Act on National Holidays (fixed days, "Happy Monday" days, the two equinoxes by the usual approximation valid 1980-2099,
substitute holidays and the sandwiched day), for 2020 on.  The result is checked against the lists the Cabinet Office publishes (tests/test_atomou_specials.py holds the years 2024-2027).
The Cabinet Office's CSV file is NOT used or passed on: only the rules and our own counts.
solar terms: the dates are those the National Astronomical Observatory publishes in its 暦要項 (data/atomou/solar_terms.json: year, name, month-day, time in Japan Standard Time, the page).
A year that is not in the file has no terms (the page then says nothing about it): the next year is added in February, when the Observatory publishes it."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WD = "月火水木金土日"


def wd(d: date) -> str:
    return WD[d.weekday()]


def _nth_monday(y: int, m: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(0 - d.weekday()) % 7)
    return d + timedelta(days=7 * (n - 1))


def equinoxes(y: int) -> tuple[int, int]:
    """(day of March, day of September) of the spring and autumn equinox: the usual formula for 1980-2099 (checked against the Observatory's 2026 and 2027 dates in the tests)."""
    return int(20.8431 + 0.242194 * (y - 1980) - int((y - 1980) / 4)), int(23.2488 + 0.242194 * (y - 1980) - int((y - 1980) / 4))


def base_holidays(y: int) -> dict[date, str]:
    """The holidays that have a day of their own (before substitutes), for 2020 on."""
    if y < 2020:
        raise ValueError("2020 on")
    sp, au = equinoxes(y)
    h = {
        date(y, 1, 1): "元日", _nth_monday(y, 1, 2): "成人の日", date(y, 2, 11): "建国記念の日", date(y, 2, 23): "天皇誕生日", date(y, 3, sp): "春分の日",
        date(y, 4, 29): "昭和の日", date(y, 5, 3): "憲法記念日", date(y, 5, 4): "みどりの日", date(y, 5, 5): "こどもの日",
        _nth_monday(y, 9, 3): "敬老の日", date(y, 9, au): "秋分の日", date(y, 11, 3): "文化の日", date(y, 11, 23): "勤労感謝の日",
    }
    if y == 2020:   # the Olympic year: three holidays were moved
        h.update({date(2020, 7, 23): "海の日", date(2020, 7, 24): "スポーツの日", date(2020, 8, 10): "山の日"})
    elif y == 2021:
        h.update({date(2021, 7, 22): "海の日", date(2021, 7, 23): "スポーツの日", date(2021, 8, 8): "山の日"})
    else:
        h.update({_nth_monday(y, 7, 3): "海の日", date(y, 8, 11): "山の日", _nth_monday(y, 10, 2): "スポーツの日"})
    return h


def holidays(y: int) -> dict[date, str]:
    """All the days off by law in year y (holidays, substitute holidays, the sandwiched day), date -> name."""
    h = dict(base_holidays(y))
    out = dict(h)
    for d in sorted(h):               # a holiday on Sunday: the next day that is not a holiday is a day off
        if d.weekday() == 6:
            n = d + timedelta(days=1)
            while n in h or n in out:
                n += timedelta(days=1)
            out[n] = "振替休日"
    for d in sorted(h):               # a day between two holidays (not a Sunday, not itself a holiday): a day off
        n = d + timedelta(days=2)
        mid = d + timedelta(days=1)
        if n in h and mid not in out and mid.weekday() != 6:
            out[mid] = "国民の休日"
    return dict(sorted(out.items()))


def is_rest(d: date, hol: dict[date, str]) -> bool:
    return d.weekday() >= 5 or d in hol


def runs(y: int, minimum: int = 3) -> list[dict]:
    """The runs of days off (Saturdays, Sundays, holidays) of at least `minimum` days that touch year y: {start, end, days, holidays}."""
    hol = {**(holidays(y - 1) if y > 2020 else {}), **holidays(y), **holidays(y + 1)}
    d, end = date(y, 1, 1) - timedelta(days=7), date(y, 12, 31) + timedelta(days=7)
    out, cur = [], []
    while d <= end:
        if is_rest(d, hol):
            cur.append(d)
        else:
            if len(cur) >= minimum and cur[-1].year >= y and cur[0].year <= y and any(x.year == y for x in cur):
                out.append(cur)
            cur = []
        d += timedelta(days=1)
    return [{"start": c[0], "end": c[-1], "days": len(c), "holidays": [hol[x] for x in c if x in hol]} for c in out if any(x in hol for x in c)]


def bridges(y: int, minimum: int = 5) -> list[dict]:
    """Where taking ONE working day off joins two blocks of days off into a run of at least `minimum` days with a holiday in it: {take, start, end, days}, by start day.
    The day sits between two blocks (rest on both sides); a day that only lengthens one block is not listed."""
    hol = {**(holidays(y - 1) if y > 2020 else {}), **holidays(y), **holidays(y + 1)}
    best: dict[date, dict] = {}
    d, end = date(y, 1, 1), date(y, 12, 31)
    while d <= end:
        if not is_rest(d, hol) and is_rest(d - timedelta(days=1), hol) and is_rest(d + timedelta(days=1), hol):
            a = d - timedelta(days=1)
            while is_rest(a - timedelta(days=1), hol):
                a -= timedelta(days=1)
            b = d + timedelta(days=1)
            while is_rest(b + timedelta(days=1), hol):
                b += timedelta(days=1)
            days = (b - a).days + 1
            if days >= minimum and any(a + timedelta(days=i) in hol for i in range(days)) and (a.year == y or b.year == y):
                best.setdefault(a, {"take": d, "start": a, "end": b, "days": days})
        d += timedelta(days=1)
    return [best[k] for k in sorted(best)]


def weekend_overlaps(y: int) -> int:
    """How many holidays fall on a Saturday or a Sunday (the ones that 'did not give a day off')."""
    return sum(1 for d, n in base_holidays(y).items() if d.weekday() >= 5)


def month_counts(y: int) -> dict[int, int]:
    c = {m: 0 for m in range(1, 13)}
    for d in holidays(y):
        c[d.month] += 1
    return c


def year_stats(y: int) -> dict:
    h = holidays(y)
    r = runs(y, 3)
    return {"year": y, "days_off_by_holiday": len(h), "overlap": weekend_overlaps(y), "runs3": len(r), "longest": max((x["days"] for x in r), default=0)}


# ---------- the 24 solar terms ----------
TERM_MEANING = {
    "小寒": "寒さが本格的になる頃。「寒の入り」とも言います。", "大寒": "一年でもっとも寒さが厳しい頃です。", "立春": "暦の上で春が始まる日です。",
    "雨水": "雪が雨に変わり、氷がとけ始める頃です。", "啓蟄": "冬ごもりをしていた虫が、地中から出てくる頃です。", "春分": "昼と夜の長さがほぼ等しくなる日。春のお彼岸の中日です。",
    "清明": "草木が芽ぶき、空気が澄んで明るくなる頃です。", "穀雨": "穀物を育てる春の雨が降る頃です。", "立夏": "暦の上で夏が始まる日です。",
    "小満": "草木が育ち、あたりに生気が満ちてくる頃です。", "芒種": "稲など、穂の出る作物の種をまく頃です。", "夏至": "一年で昼がもっとも長い日です。",
    "小暑": "暑さが増して、夏の盛りに向かう頃です。", "大暑": "一年でもっとも暑さが厳しい頃です。", "立秋": "暦の上で秋が始まる日。この日からは「残暑」と言います。",
    "処暑": "暑さがおさまり始める頃です。", "白露": "草花に露がつき、秋の気配が深まる頃です。", "秋分": "昼と夜の長さがほぼ等しくなる日。秋のお彼岸の中日です。",
    "寒露": "草木に冷たい露がつく頃です。", "霜降": "霜が降り始める頃です。", "立冬": "暦の上で冬が始まる日です。",
    "小雪": "冷え込みが増し、北の地方から雪の便りが届く頃です。", "大雪": "雪が本格的に降り始める頃です。", "冬至": "一年で昼がもっとも短い日です。",
}


def solar_terms() -> dict:
    return json.loads((ROOT / "data" / "atomou" / "solar_terms.json").read_text(encoding="utf-8"))


def terms_of(y: int) -> list[dict]:
    """[{name, date, time}] of the 24 solar terms of year y (empty when the Observatory's figures for that year are not in the file)."""
    rows = solar_terms()["years"].get(str(y)) or []
    return [{"name": n, "date": date(y, int(md[:2]), int(md[3:])), "time": t} for n, md, t in rows]


def term_span(today: date) -> tuple[dict | None, dict | None]:
    """(the term that began last, the next term) as of today, over this year's and the next year's figures."""
    allt = terms_of(today.year - 1) + terms_of(today.year) + terms_of(today.year + 1)
    cur = [t for t in allt if t["date"] <= today]
    nxt = [t for t in allt if t["date"] > today]
    return (cur[-1] if cur else None), (nxt[0] if nxt else None)
