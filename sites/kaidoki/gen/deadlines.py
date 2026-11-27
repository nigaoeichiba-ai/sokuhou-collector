"""The deadlines of the 締切カレンダー corner: read from deadlines.json (one row each), never typed into a sentence.

A row: id, kind (early = 早割終了, cancel = キャンセル・変更期限, close = 受付終了), title (what the reader can still do), deadline (ISO, JST, the real last minute), what (one or two plain sentences for the reader),
checked (the day it was read on the organiser's own page), basis (the page it was read on and the short passage: INTERNAL, never shown), aff (affiliate link specs in the form redesign/affiliate.product_links takes), group (the
subject a reader thinks in: 年賀状, おせち, クリスマスケーキ, ふるさと納税, 宅配, 旅行, セール).
What the screen shows: the day, the kind, the title, the days left (computed), the sentence, the check day.  Not the basis.  After the deadline a row moves to 'すぎた締切' by itself.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .common import NOW_T, TODAY, WD, d

DATA = Path(__file__).with_name("deadlines.json")
KINDS = {"early": "早割終了", "cancel": "キャンセル・変更期限", "close": "受付終了"}
KIND_ORDER = ("early", "cancel", "close")


def load() -> list[dict]:
    rows = json.loads(DATA.read_text(encoding="utf-8"))["rows"]
    for r in rows:
        r["dt"] = datetime.fromisoformat(r["deadline"])
    return sorted(rows, key=lambda r: (r["dt"], r["id"]))


def group_aff() -> dict:
    """Affiliate link specs shown once per group (not repeated on every row)."""
    return json.loads(DATA.read_text(encoding="utf-8")).get("group_aff", {})


def day(r: dict) -> date:
    return r["dt"].date()


def _t(r: dict) -> str:
    """The hour, unless the organiser names only a day (notime): then nothing is invented."""
    x = r["dt"]
    if r.get("notime"):
        return ""
    return f"{x.hour}時" if x.minute == 0 else f"{x.hour}時{x.minute}分"


def when(r: dict) -> str:
    """2026年12月25日(金)23時59分"""
    x = r["dt"]
    return f"{x.year}年{x.month}月{x.day}日({WD[x.weekday()]}){_t(r)}"


def when_short(r: dict) -> str:
    x = r["dt"]
    return f"{x.month}月{x.day}日({WD[x.weekday()]}){_t(r)}"


def left(r: dict) -> int:
    return (day(r) - TODAY).days


def until(r: dict) -> str:
    n = left(r)
    if over(r):
        return "終了"
    return "本日まで" if n == 0 else f"あと{n}日"


def over(r: dict) -> bool:
    """The deadline has passed: its day is past, or it is today and the build is later than the minute written for it (a row with no hour is over only from the next day)."""
    n = left(r)
    if n != 0:
        return n < 0
    return bool(NOW_T and not r.get("notime") and NOW_T > r["dt"].strftime("%H:%M"))


def coming(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not over(r)]


def passed(rows: list[dict]) -> list[dict]:
    return [r for r in rows if over(r)]


def of_month(rows: list[dict], year: int, month: int) -> list[dict]:
    return [r for r in rows if r["dt"].year == year and r["dt"].month == month]
