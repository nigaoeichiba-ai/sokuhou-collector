"""The year's gift days, and an iCalendar (.ics) feed of them: a "start choosing" reminder three weeks before each, and the day itself.

Only occasions whose date is the same for everybody are here (Mother's Day, Christmas ...).  Birthdays and anniversaries are personal and
are handled in the browser (the 「たいせつな日メモ」 page), which builds a calendar file for the person's own date.
"""
from __future__ import annotations

from datetime import date, timedelta

LEAD_DAYS = 21


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th given weekday (Monday = 0) of a month."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


# slug -> (label, date function(year), what the day is)
DAYS = {
    "valentine": ("バレンタイン", lambda y: date(y, 2, 14), "2月14日"),
    "white-day": ("ホワイトデー", lambda y: date(y, 3, 14), "3月14日"),
    "mothers-day": ("母の日", lambda y: nth_weekday(y, 5, 6, 2), "5月の第2日曜日"),
    "fathers-day": ("父の日", lambda y: nth_weekday(y, 6, 6, 3), "6月の第3日曜日"),
    "ochugen": ("お中元の時期のはじまり", lambda y: date(y, 7, 1), "7月1日ごろから"),
    "respect-for-aged-day": ("敬老の日", lambda y: nth_weekday(y, 9, 0, 3), "9月の第3月曜日"),
    "oseibo": ("お歳暮の時期のはじまり", lambda y: date(y, 12, 1), "12月1日ごろから"),
    "christmas": ("クリスマス", lambda y: date(y, 12, 25), "12月25日"),
    "year-end-gathering": ("年末年始の集まり", lambda y: date(y, 12, 29), "12月29日ごろ"),
    "coming-of-age": ("成人の日", lambda y: nth_weekday(y, 1, 0, 2), "1月の第2月曜日"),
}


def gift_days(year: int) -> list[dict]:
    """Every shared gift day of a calendar year, in date order: {slug, label, date, when, start}."""
    out = [{"slug": s, "label": label, "date": fn(year), "when": when, "start": fn(year) - timedelta(days=LEAD_DAYS)}
           for s, (label, fn, when) in DAYS.items()]
    return sorted(out, key=lambda d: d["date"])


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines are at most 75 octets; continuation lines start with a space (never split a UTF-8 character)."""
    out, cur = [], ""
    for ch in line:
        limit = 75 if not out else 74
        if len((cur + ch).encode("utf-8")) > limit:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n ".join(out)


def ics(base_url: str, years: list[int], stamp: str, occasion_names: dict[str, str] | None = None) -> str:
    """The feed: for each gift day, an all-day "start choosing" event 21 days before and one on the day, each linking to the occasion page."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//yorokobu-present.com//gift days//JA", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:よろこぶプレゼント 贈りどきカレンダー", "X-WR-TIMEZONE:Asia/Tokyo"]
    for y in years:
        for d in gift_days(y):
            url = f"{base_url.rstrip('/')}/occasion/{d['slug']}/"
            for kind, day, summary, note in (
                ("start", d["start"], f"{d['label']}まで3週間。贈り物を選びはじめよう",
                 f"{d['label']}({d['when']})の贈り物を、そろそろ考えませんか?\n選び方とおすすめ: {url}"),
                ("day", d["date"], f"{d['label']}", f"{d['label']}です。\n選び方とおすすめ: {url}"),
            ):
                lines += ["BEGIN:VEVENT", f"UID:{d['slug']}-{kind}-{y}@yorokobu-present.com", f"DTSTAMP:{stamp}",
                          f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
                          f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(note)}", f"URL:{url}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"
