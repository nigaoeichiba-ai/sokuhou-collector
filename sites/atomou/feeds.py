"""atomou: calendar feeds (.ics) of the official days, one per genre and one for everything.

A visitor subscribes once (Google Calendar, iPhone, Mac, Outlook) and the days appear in the calendar app they already open; a day that is added later arrives by itself.
Each day carries a link back to its page here, so a calendar notice leads to the count, the notes and the source.
The files are public static data (built from the verified catalogue); the site never learns who subscribes: the calendar service fetches the file.
Only whole days are listed ("2027年1月ごろ" has no day to put in a calendar), and no quiet day (a memorial, a disaster) is ever put in a feed.
"""
from __future__ import annotations

from datetime import date, timedelta

FEED_DIR = "cal"


def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines are folded at 75 octets (never inside a UTF-8 character)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not out else 74):
            out.append(cur)
            cur, size = ch, n
        else:
            cur += ch
            size += n
    out.append(cur)
    return "\r\n ".join(out)


def feedable(e: dict) -> bool:
    return e["precision"] == "day" and not e["quiet"]


def ics_feed(name: str, description: str, entries: list[dict], base: str, now: date) -> str:
    """The calendar file: every day of `entries` as an all-day event (a range runs to its last day)."""
    stamp = now.strftime("%Y%m%d") + "T000000Z"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//atomou.com//あと何日、もう何日//JA", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_esc(name)}", f"NAME:{_esc(name)}", f"X-WR-CALDESC:{_esc(description)}", "X-WR-TIMEZONE:Asia/Tokyo",
             "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    for e in entries:
        if not feedable(e):
            continue
        d = date.fromisoformat(e["date"])
        last = date.fromisoformat(e.get("date_end") or e["date"])
        url = f"{base}/e/{e['id']}/"
        detail = f"詳しい日付と出典: {url}"
        lines += ["BEGIN:VEVENT", f"UID:{e['id']}@atomou.com", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(e['title'])}",
                  f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(last + timedelta(days=1)).strftime('%Y%m%d')}", "TRANSP:TRANSPARENT",
                  f"DESCRIPTION:{_esc(detail)}", f"URL:{url}", f"CATEGORIES:{_esc(e['group'])}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def feed_pages(live: list[dict], groups: list[str], slugs: dict[str, str], base: str, now: date) -> dict[str, str]:
    """{path: file} for every genre that has a day to list, plus cal/all.ics."""
    pages: dict[str, str] = {}
    usable = [e for e in live if feedable(e)]
    for g in groups:
        rows = [e for e in usable if e["group"] == g]
        if rows:
            pages[f"{FEED_DIR}/{slugs[g]}.ics"] = ics_feed(f"あと何日、もう何日 {g}", f"{g}の公式の日付(出典と確認日つき)。", rows, base, now)
    if usable:
        pages[f"{FEED_DIR}/all.ics"] = ics_feed("あと何日、もう何日 すべての日付", "締切・試験・大会・お祭りなど、公式の日付(出典と確認日つき)。", usable, base, now)
    return pages


def subscribe_html(path: str, base: str, host: str) -> str:
    """The two links under a genre page: Google Calendar's own 'add by URL' address and the webcal:// address that iPhone, Mac and Outlook open."""
    from urllib.parse import quote
    web = f"webcal://{host}/{FEED_DIR}/{path}"
    google = "https://calendar.google.com/calendar/r?cid=" + quote(web, safe=":/")
    return (f'<details class="more"><summary>このジャンルの日付を、カレンダーに購読する</summary>'
            '<p class="hint">一度入れると、あとから追加された日付も自動でカレンダーに届きます。</p>'
            f'<p><a class="btn small" href="{google}" target="_blank" rel="noopener">Googleカレンダーに追加</a> '
            f'<a class="btn small ghost" href="{web}">iPhone・Mac・Outlookで購読</a> '
            f'<a class="btn small ghost" href="/{FEED_DIR}/{path}" download>ファイルをダウンロード</a></p></details>')
