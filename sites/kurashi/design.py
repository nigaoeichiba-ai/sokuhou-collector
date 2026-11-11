"""The parts of the 'neon white' design (redesign case I, 2026-11-11) that are made of data: the month table, the Gantt chart, the detail panel, the deadline box.

Nothing here writes a sentence of the site.  Every name, date and day count comes from the deadline catalog (site.json "deadlines" = gen/deadlines.py); the words that are
the parts' own labels are the constants below.  The markup is plain HTML; assets/tools.js only switches the views and selects a day (without JS everything is shown, stacked).
Day counts are the markers of hooks.py ({days:DATE}), turned into numbers at build time and corrected in the browser.
"""
from __future__ import annotations

import calendar
import html
from datetime import date, timedelta

WD_HEAD = "日月火水木金土"            # a month table starts on Sunday
LBL_CAL = "カレンダー"
LBL_GANTT = "ガント"
LBL_LEFT = ("あと", "日")
LBL_MORE = "詳しい記事"
LBL_CHECKED = "確認日"
BUTTON = "カレンダーに登録"

# the deadlines that are periods (id -> where the period ends): a bar in the Gantt chart, a band or a run in the month table
PERIOD_END = {"gyosei-yasumi": "closed-to", "shinkoku-start": "shinkoku-end"}
CLOSED_TO = date(2027, 1, 3)           # the last day of the national offices' year-end holiday (gen/pages_hub.CLOSED_TO)

CAT_OF_PREFIX = (("/life/", "violet"), ("/moving/", "violet"), ("/kafun/", "lime"))


def category(path: str) -> str:
    """the colour of a page: pink = deadlines (default), violet = life events and moving, lime = a season with a period"""
    for pre, c in CAT_OF_PREFIX:
        if path.startswith(pre):
            return c
    return "pink"


def e(s: str) -> str:
    return html.escape(s, quote=True)


def d(x: str) -> date:
    return date.fromisoformat(x)


def jp(x: date) -> str:
    return f"{x.year}年{x.month}月{x.day}日({'月火水木金土日'[x.weekday()]})"


def left(iso: str, cls: str = "left") -> str:
    return f'<span class="{cls}">{LBL_LEFT[0]}{{days:{iso}}}{LBL_LEFT[1]}</span>'


def period_of(ev: dict, cat: dict) -> tuple[date, date] | None:
    end = PERIOD_END.get(ev["id"])
    if not end:
        return None
    to = CLOSED_TO if end == "closed-to" else d(cat[end]["date"])
    return d(ev["date"]), to


# ---------------------------------------------------------------- the detail panel (one per day that has a deadline)
def panels(events: list[dict], links: dict, today: date, selected: str) -> str:
    by_day: dict[str, list[dict]] = {}
    for ev in events:
        by_day.setdefault(ev["date"], []).append(ev)
    out = []
    for iso, evs in sorted(by_day.items()):
        items = []
        for ev in evs:
            more = f'<a class="more" href="{e(ev["url"])}">{e(links.get(ev["url"], LBL_MORE))}</a>'
            btn = f'<a class="btn cal-b" href="/calendar/{ev["id"]}.ics" download>{BUTTON}</a>' if d(ev["date"]) >= today else ""
            items.append(f'<div class="dp-item"><p class="dp-name">{e(ev["name"])}</p>'
                         f'<p class="dp-when"><span class="dp-date">{jp(d(ev["date"]))}</span> {left(ev["date"], "left pill")}</p>'
                         f'<p class="dp-act">{btn}{more}</p></div>')
        out.append(f'<div class="dpanel" id="dp-{iso}" data-day="{iso}"{" data-on" if iso == selected else ""}>{"".join(items)}</div>')
    return '<div class="dpanels" aria-live="polite">' + "".join(out) + "</div>"


# ---------------------------------------------------------------- the month table
def month_table(year: int, month: int, events: list[dict], cat: dict, today: date, *, mini: bool = False, selected: str = "") -> str:
    marks = {ev["date"]: ev for ev in events}
    bands: set[str] = set()
    runs: set[str] = set()
    for ev in events:
        per = period_of(ev, cat)
        if not per:
            continue
        x = per[0]
        while x <= per[1]:
            (bands if ev["id"] == "gyosei-yasumi" else runs).add(x.isoformat())
            x += timedelta(days=1)
    n = calendar.monthrange(year, month)[1]
    lead = (date(year, month, 1).weekday() + 1) % 7           # Sunday = 0
    cells = [f'<span class="wh">{c}</span>' for c in WD_HEAD]
    cells += ['<span class="blank"></span>'] * lead
    for day in range(1, n + 1):
        iso = date(year, month, day).isoformat()
        cls = ["dc"]
        if iso == today.isoformat():
            cls.append("today")
        if iso in marks:
            cls.append("dl")
        elif iso in bands:
            cls.append("dh")
        elif iso in runs:
            cls.append("dr")
        inner = f'<b class="dn">{day}</b>'
        if iso in marks and not mini:
            pressed = ' aria-pressed="true"' if iso == selected else ' aria-pressed="false"'
            cells.append(f'<button type="button" class="{" ".join(cls)}" data-day="{iso}"{pressed}>{inner}{left(iso, "left cl")}</button>')
        else:
            cells.append(f'<span class="{" ".join(cls)}">{inner}</span>')
    return f'<div class="mt{" mini" if mini else ""}"><p class="mt-h">{year}年{month}月</p><div class="mt-g">{"".join(cells)}</div></div>'


# ---------------------------------------------------------------- the Gantt chart
def gantt(events: list[dict], cat: dict, today: date) -> str:
    first = min([today] + [d(ev["date"]) for ev in events])
    last = max([d(ev["date"]) for ev in events] + [p[1] for p in (period_of(ev, cat) for ev in events) if p])
    start = date(first.year, first.month, 1)
    end = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
    total = (end - start).days + 1

    def pos(x: date) -> float:
        return round((x - start).days / total * 100, 3)

    scale = f'data-start="{start.isoformat()}" data-end="{end.isoformat()}"'
    ticks = []
    x = start
    while x <= end:
        nxt = date(x.year + (x.month == 12), x.month % 12 + 1, 1)
        ticks.append(f'<span class="gt" style="left:{pos(x)}%;width:{round((min(nxt, end + timedelta(days=1)) - x).days / total * 100, 3)}%">{x.month}月</span>')
        x = nxt
    rows = []
    for ev in sorted(events, key=lambda v: v["date"]):
        day = d(ev["date"])
        per = period_of(ev, cat)
        shapes = ""
        if per:
            col = "band" if ev["id"] == "gyosei-yasumi" else "run"
            w = max(round(((per[1] - per[0]).days + 1) / total * 100, 3), 1.2)
            shapes += f'<span class="gb {col}" style="left:{pos(per[0])}%;width:{w}%"></span>'
        flip = pos(day) > 62
        shapes += f'<span class="gm" style="left:{pos(day)}%"><i class="dot"></i></span>'
        if flip:
            shapes += f'<span class="gx" style="right:calc({round(100 - pos(day), 3)}% + 14px)">{left(ev["date"], "left gl")}</span>'
        else:
            shapes += f'<span class="gx" style="left:calc({pos(per[1] if per else day)}% + 14px)">{left(ev["date"], "left gl")}</span>'
        rows.append(f'<div class="gr"><p class="gn">{e(ev["name"])}</p><div class="gk" {scale}>{shapes}<span class="gtoday" style="left:{pos(today)}%"></span></div></div>')
    return (f'<div class="gantt"><div class="gr gh"><span class="gn"></span><div class="gk gaxis" {scale}>{"".join(ticks)}</div></div>{"".join(rows)}</div>')


# ---------------------------------------------------------------- the pieces the hooks insert
def switch_view(events: list[dict], cat: dict, links: dict, today: date) -> str:
    """the top page: one set of deadlines as a month table or a Gantt chart, one pill switch; the detail panel is shared"""
    ev = sorted(events, key=lambda v: v["date"])
    pick = next((v for v in ev if d(v["date"]) >= today), ev[0])
    y, m = d(pick["date"]).year, d(pick["date"]).month
    in_month = [v for v in ev if d(v["date"]).year == y and d(v["date"]).month == m]
    return (f'<section class="kv noprint" data-view="cal">'
            f'<div class="sw" role="tablist"><button type="button" class="sw-b" role="tab" data-v="cal" aria-selected="true">{LBL_CAL}</button>'
            f'<button type="button" class="sw-b" role="tab" data-v="gantt" aria-selected="false">{LBL_GANTT}</button></div>'
            f'<div class="kv-cal">{month_table(y, m, ev, cat, today, selected=pick["date"])}{panels(in_month, links, today, pick["date"])}</div>'
            f'<div class="kv-gantt">{gantt(ev, cat, today)}</div></section>\n')


def month_view(year: int, month: int, events: list[dict], cat: dict, links: dict, today: date) -> str:
    """a month page: the month table with the same detail panel (the deadlines of the month; none when the month has none)"""
    ev = sorted((v for v in events if d(v["date"]).year == year and d(v["date"]).month == month), key=lambda v: v["date"])
    pick = next((v for v in ev if d(v["date"]) >= today), ev[0] if ev else None)
    sel = pick["date"] if pick else ""
    return (f'<section class="kv noprint">{month_table(year, month, events, cat, today, selected=sel)}{panels(ev, links, today, sel) if ev else ""}</section>\n')


def month_overview(months: list[tuple[int, int]], events: list[dict], cat: dict, today: date) -> str:
    grids = "".join(month_table(y, m, events, cat, today, mini=True) for y, m in months)
    return f'<section class="kv-all noprint">{grids}</section>\n'


def deadline_box(ev: dict, checked: str) -> str:
    return (f'<section class="dbox noprint"><p class="dbox-left">{left(ev["date"], "left")}</p>'
            f'<div class="dbox-main"><p class="dbox-date">{jp(d(ev["date"]))}</p><p class="dbox-name">{e(ev["name"])}</p>'
            f'<p class="dbox-act"><a class="btn cal-b" href="/calendar/{ev["id"]}.ics" download>{BUTTON}</a>'
            f'<span class="dbox-chk">{LBL_CHECKED} {checked}</span></p></div></section>\n')
