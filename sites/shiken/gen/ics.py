"""Calendar files (RFC 5545) and Google Calendar template links for the events of model.py.

A timed event is written with TZID=Asia/Tokyo and the VTIMEZONE it names; an event without a time is a whole-day event (VALUE=DATE).
The UID comes from the exam, the kind and the day, so the same event is the same event in a calendar after the file is made again.
DTSTAMP is the fixed day the dates were read, not the day of the build: the files do not change from day to day.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from urllib.parse import quote

from .common import CHECKED, d
from .model import EVENT_LIST, FILE_TYPE, TYPE_LABEL

SITE = "https://shiken-nittei.com"
CLOSING = "最終的な日程は、主催団体の公式発表でご確認ください。"
TZ = ("BEGIN:VTIMEZONE", "TZID:Asia/Tokyo", "BEGIN:STANDARD", "DTSTART:19700101T000000", "TZOFFSETFROM:+0900", "TZOFFSETTO:+0900", "TZNAME:JST", "END:STANDARD", "END:VTIMEZONE")


def file_name(e: dict) -> str:
    return f"shiken-{e['id']}.ics"


def title(e: dict) -> str:
    return f"［{TYPE_LABEL[e['type']]}］{e['name']}"


def _start_end(e: dict) -> tuple[datetime, datetime] | tuple[date, date]:
    day = d(e["iso"])
    if not e["time"]:
        return day, day + timedelta(days=1)
    h, m = map(int, e["time"].split(":"))
    start = datetime(day.year, day.month, day.day, h, m)
    if e["end"]:
        h2, m2 = map(int, e["end"].split(":"))
        return start, datetime(day.year, day.month, day.day, h2, m2)
    return start, start + timedelta(minutes=30 if e["type"] != "exam" else 60)


def description(e: dict) -> str:
    return f"{e['name']}の{TYPE_LABEL[e['type']]}です。詳細: {SITE}{e['url']}\n{CLOSING}"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """75 octets a line (UTF-8), the rest on lines that start with one space; a character is never cut"""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > 75 - (1 if out else 0):
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return [out[0]] + [" " + x for x in out[1:]]


def uid(e: dict) -> str:
    return hashlib.sha1(f"{e['exam']}|{e['type']}|{e['variant']}|{e['iso']}|{e['time']}".encode()).hexdigest()[:20] + "@shiken-nittei.com"


def alarms(e: dict) -> list[str]:
    if e["type"] == "application_deadline":
        return ["-P7D", "-P1D"]
    if e["type"] == "exam":
        return ["-P1D"]
    return []


def ics(e: dict) -> str:
    s, t = _start_end(e)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//shiken-nittei.com//JA", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", *TZ, "BEGIN:VEVENT", f"UID:{uid(e)}",
             f"DTSTAMP:{CHECKED.replace('-', '')}T000000Z"]
    if isinstance(s, datetime):
        lines += [f"DTSTART;TZID=Asia/Tokyo:{s:%Y%m%dT%H%M%S}", f"DTEND;TZID=Asia/Tokyo:{t:%Y%m%dT%H%M%S}"]
    else:
        lines += [f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{t:%Y%m%d}"]
    lines += [f"SUMMARY:{_esc(title(e))}", f"DESCRIPTION:{_esc(description(e))}", f"URL:{SITE}{e['url']}"]
    for trig in alarms(e):
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(title(e))}", f"TRIGGER:{trig}", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(x for line in lines for x in _fold(line)) + "\r\n"


def gcal(e: dict) -> str:
    s, t = _start_end(e)
    if isinstance(s, datetime):
        dates = f"{s:%Y%m%dT%H%M%S}/{t:%Y%m%dT%H%M%S}"
    else:
        dates = f"{s:%Y%m%d}/{t:%Y%m%d}"
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + quote(title(e), safe="") + "&dates=" + dates + "&ctz=Asia%2FTokyo"
            + "&details=" + quote(description(e), safe="") + "&location=")


def files() -> dict:
    return {f"ics/{file_name(e)}": ics(e) for e in EVENT_LIST}
