"""Hooks of sites/kurashi (sokuhou/newsite.py site_hooks): day counts, calendar files (.ics) and the print layout.  Nothing here writes a sentence of the site;
the few words of the parts (the buttons, the heading of the calendar block) are the constants HEADING / BUTTON / ... below.

* The pages carry markers instead of day counts: {days:DATE} {rel:DATE} {rel:DATE|text for a day that has passed} {weeks:DATE} {today} {todayy}.
  The build turns them into the numbers of the build day (JST; the deploy rebuilds every site at 07:00 JST), inside <span class="nd" ...> so that assets/tools.js can
  correct them to the reader's own day.  The HTML that a search engine reads therefore has the right numbers on the day it was built.
* Every upcoming dated deadline of a page gets a calendar button; the file is calendar/<id>.ics (an all-day entry on the day, an alert at 09:00 the day before).
  A page that shows two or more deadlines also gets one file with all of them (calendar/<page>.ics; the home page and /month/: calendar/all.ics).
* The pages of life events, moving and months can be printed: print CSS in assets/style.css; this adds the classes and the button it needs.
"""
from __future__ import annotations

import hashlib
import html
import os
import importlib.util
import re
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

SITE_URL = "https://kurashi-calendar.com"
WD = "月火水木金土日"
# the words of the parts (the owner's desk is responsible for sentences; these are labels)
HEADING = "カレンダーに登録"
BUTTON = "カレンダーに登録"
BUNDLE = "まとめて登録"
NOTE = "通知は前日の午前9時です。"
PRINT_BUTTON = "印刷"
ICON16 = '<link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16.png">'
ICON48 = '<link rel="icon" type="image/png" sizes="48x48" href="/assets/favicon-48.png">'
PRINT_PAGES = ("/life/birth/", "/life/kaigo/", "/life/kekkon/", "/life/shibo/", "/life/taishoku/", "/moving/", "/moving/tenshutsu/", "/moving/menkyo-sha/",
               "/month/11/", "/month/12/", "/month/1/", "/month/2/", "/month/3/")

MARK = re.compile(r"\{(days|rel|weeks):(\d{4}-\d\d-\d\d)(?:\|([^}]*))?\}|\{(today|todayy)\}")
STALE: list[str] = []          # a count that would be negative (a deadline that has passed): the page needs this season's review


_spec = importlib.util.spec_from_file_location("_kurashi_design", Path(__file__).with_name("design.py"))
design = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(design)


def today_jst() -> date:
    v = os.environ.get("KURASHI_TODAY")
    if v:
        return date.fromisoformat(v)
    return datetime.now(timezone(timedelta(hours=9))).date()


def md(x: date) -> str:
    return f"{x.month}月{x.day}日({WD[x.weekday()]})"


def jp(x: date) -> str:
    return f"{x.year}年{md(x)}"


def count_text(kind: str, iso: str, past: str, today: date) -> str:
    n = (date.fromisoformat(iso) - today).days
    if kind == "rel":
        return f"{n}日後" if n > 0 else "今日" if n == 0 else (past or "過ぎた")
    if n < 0:
        STALE.append(f"{kind}:{iso}")
        n = 0
    return str(n // 7 if kind == "weeks" else n)


def resolve(text: str, today: date) -> str:
    """markers -> <span class="nd" data-k=.. data-d=..>text</span> (the text is what the build day gives)"""
    def one(m: re.Match) -> str:
        if m.group(4):
            ymd = m.group(4) == "todayy"
            t = f"{today.year}年{today.month}月{today.day}日" if ymd else f"{today.month}月{today.day}日"
            return f'<span class="nd" data-k="{"ymd" if ymd else "md"}">{t}</span>'
        kind, iso, past = m.group(1), m.group(2), m.group(3) or ""
        extra = f' data-p="{html.escape(past, quote=True)}"' if past else ""
        return f'<span class="nd" data-k="{kind}" data-d="{iso}"{extra}>{count_text(kind, iso, past, today)}</span>'
    return MARK.sub(one, text)


def plain(text: str, today: date) -> str:
    """markers -> the plain text of the build day (for the fields that the checks and the search results read as text, not as markup)"""
    def one(m: re.Match) -> str:
        if m.group(4):
            return f"{today.year}年{today.month}月{today.day}日" if m.group(4) == "todayy" else f"{today.month}月{today.day}日"
        return count_text(m.group(1), m.group(2), m.group(3) or "", today)
    return MARK.sub(one, text)


# ---------------------------------------------------------------- prepare: the home page's "nearest deadlines" sentence and rows follow the day
def prepare(cfg, spec, pages, site_dir):
    today = today_jst()
    cat = spec.get("deadlines", [])
    for p in pages:
        if p["path"] != "/":
            continue
        upcoming = [c for c in cat if c.get("lead") and date.fromisoformat(c["date"]) >= today]
        if upcoming:
            near = "と、".join(f"{md(date.fromisoformat(c['date']))}の{c['lead']}" for c in upcoming[:2])
            p["answer"] = f"{{todayy}}時点でいちばん近い期限は、{near}です。"
        for s in p["sections"]:
            t = s.get("table")
            if t:   # a row whose deadline has passed is dropped from the 'nearest' table
                t["rows"] = [r for r in t["rows"] if not _passed(r, today)]
    for p in pages:         # the lead answer is measured and used as text (length checks, keywords): plain numbers there; post() puts the spans back in the page
        if MARK.search(p.get("answer") or ""):
            p["_answer_marked"] = p["answer"]
            p["answer"] = plain(p["answer"], today)
    return pages


def _passed(row: list, today: date) -> bool:
    for c in row:
        m = re.fullmatch(r"\{rel:(\d{4}-\d\d-\d\d)\}", c) if isinstance(c, str) else None
        if m and date.fromisoformat(m.group(1)) < today:
            return True
    return False


# ---------------------------------------------------------------- calendar files
def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """75 octets a line (UTF-8), the continuation lines start with one space; a character is never cut"""
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


def vevent(e: dict, stamp: str) -> list[str]:
    day = date.fromisoformat(e["date"])
    url = SITE_URL + e["url"]
    return ["BEGIN:VEVENT", f"UID:kurashi-{e['id']}-{day:%Y%m%d}@kurashi-calendar.com", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_esc(e['name'])}", f"DESCRIPTION:{_esc(url)}", f"URL:{url}", "TRANSP:TRANSPARENT",
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(e['name'])}", "TRIGGER:-PT15H", "END:VALARM",       # 09:00 the day before (the entry starts at 00:00 of the day)
            "END:VEVENT"]


def ics(events: list[dict], stamp: str) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//kurashi-calendar.com//JA", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for e in events:
        lines += vevent(e, stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(x for line in lines for x in _fold(line)) + "\r\n"


def slug(path: str) -> str:
    return "all" if path in ("/", "/month/") else path.strip("/").replace("/", "-")


def calendar_files(content: list[dict], spec: dict, today: date) -> tuple[dict, dict]:
    """({file: text}, {page path: ([events], bundle file or None)}); only the deadlines that have not passed"""
    cat = {c["id"]: c for c in spec.get("deadlines", [])}
    stamp = "20261103T000000Z"          # the day the dates were checked: the files do not change from day to day
    files, per_page = {}, {}
    for p in content:
        evs = [cat[i] for i in p.get("deadline_ids", []) if date.fromisoformat(cat[i]["date"]) >= today]
        if not evs:
            continue
        evs = sorted(evs, key=lambda e: e["date"])
        for e in evs:
            files[f"calendar/{e['id']}.ics"] = ics([e], stamp)
        bundle = None
        if len(evs) >= 2:
            bundle = f"calendar/{slug(p['path'])}.ics"
            files[bundle] = ics(evs, stamp)
        per_page[p["path"]] = (evs, bundle)
    return files, per_page


def calendar_block(evs: list[dict], bundle: str | None) -> str:
    items = "".join(
        f'<li><span class="cal-d">{html.escape(jp(date.fromisoformat(e["date"])))}</span> <span class="cal-n">{html.escape(e["name"])}</span> '
        f'<a class="btn cal-b" href="/calendar/{e["id"]}.ics" download>{BUTTON}</a></li>' for e in evs)
    more = f'<p><a class="btn" href="/{bundle}" download>{BUNDLE}</a></p>\n' if bundle else ""
    return f'<section class="cal noprint">\n<h2>{HEADING}</h2>\n<ul class="cal-list">{items}</ul>\n{more}<p class="notice">{NOTE}</p>\n</section>\n'


# ---------------------------------------------------------------- print
def print_ready(body: str, path: str) -> str:
    """class="chk" on the first table (the CSS puts a box before each row's first cell when printing); a section without a table does not print;
    the print button after the answer; the address at the end"""
    body = body.replace("<table>", '<table class="chk">', 1)
    a = body.find("<h2>")
    end = body.find('<p class="credit">')
    if end < 0:
        end = body.find('<p class="stamp">')
    if a < 0 or end < 0:
        return body
    parts = re.split(r"(?=<h2>)", body[a:end])
    kept = "".join(seg if "<table" in seg else f'<div class="noprint">{seg}</div>\n' for seg in parts if seg)
    head = body[:a]
    i = head.find("</p>", head.find('<p class="answer">')) + 4 if '<p class="answer">' in head else len(head)
    btn = f'<p class="noprint"><button type="button" class="btn" data-print hidden>{PRINT_BUTTON}</button></p>\n'
    head = head[:i] + "\n" + btn + head[i:].lstrip("\n")
    return head + kept + body[end:].rstrip("\n") + f'\n<p class="printonly">{SITE_URL}{path}</p>\n'


NL = chr(10)


def link_texts(content: list[dict]) -> dict:
    """the address of a page -> the words the site's own tables use for the link to it"""
    out: dict[str, str] = {}
    for p in content:
        for sec in p.get("sections", []):
            for row in (sec.get("table") or {}).get("rows", []):
                for c in row:
                    if isinstance(c, dict) and c.get("href") and c.get("text"):
                        out.setdefault(c["href"], c["text"])
    return out


def season_year(month: int, cat: dict) -> int:
    first = min(date.fromisoformat(c["date"]) for c in cat.values())
    return first.year if month >= 7 else first.year + 1


def add_design(body: str, p: dict, per_page: dict, spec: dict, today: date, links: dict) -> str:
    """the neon-white parts: the switch view (home), the month table (month pages), the month tables (the list of months), the deadline box (the other pages that have a deadline)"""
    path = p["path"]
    cat = {c["id"]: c for c in spec.get("deadlines", [])}
    a = body.find('<p class="answer">')
    if a < 0:
        return body
    i = body.find("</p>", a) + 4
    block = ""
    m = re.fullmatch(r"/month/(\d+)/", path)
    if path == "/":
        evs = [cat[x] for x in p.get("deadline_ids", []) if date.fromisoformat(cat[x]["date"]) >= today]
        if evs:
            block = design.switch_view(evs, cat, links, today)
    elif path == "/month/":
        months = [(season_year(n, cat), n) for n in (11, 12, 1, 2, 3)]
        block = design.month_overview(months, list(cat.values()), cat, today)
    elif m:
        n = int(m.group(1))
        block = design.month_view(season_year(n, cat), n, list(cat.values()), cat, links, today)
    elif path in per_page:
        ev = per_page[path][0][0]
        y, mo, dd = p["updated"].split("-")
        block = design.deadline_box(ev, f"{y}年{int(mo)}月{int(dd)}日")
    return body[:i] + NL + block + body[i:].lstrip(NL) if block else body


def post(pages, content, cfg, spec, site_dir):
    today = today_jst()
    links = link_texts(content)
    STALE.clear()
    files, per_page = calendar_files(content, spec, today)
    tools = (site_dir / "assets" / "tools.js").read_text(encoding="utf-8")
    tag = f'<script src="/assets/tools.js?v={hashlib.sha1(tools.encode()).hexdigest()[:8]}" defer></script>\n'
    for p in content:
        rel = "index.html" if p["path"] == "/" else p["path"].strip("/") + "/index.html"
        h = pages[rel]
        m = re.search(r"<main[^>]*>\n(.*?)\n</main>", h, re.S)
        if not m:
            continue
        body = m.group(1)
        if p["path"] in PRINT_PAGES:
            body = print_ready(body, p["path"])
        if p["path"] in per_page:
            evs, bundle = per_page[p["path"]]
            block = calendar_block(evs, bundle)
            j = body.find("</table></div>")
            if j >= 0:
                j += len("</table></div>")
                nx = re.match(r'\n?<p class="notice">.*?</p>', body[j:], re.S)
                j += nx.end() if nx else 0
                body = body[:j] + "\n" + block + body[j:].lstrip("\n")
            else:
                k = body.find("<h2>関連するページ</h2>")
                body = body[:k] + block + body[k:] if k >= 0 else body + "\n" + block
        if p.get("_answer_marked"):
            old = f'<p class="answer">{html.escape(p["answer"], quote=True)}</p>'
            if old in body:
                body = body.replace(old, f'<p class="answer">{html.escape(p["_answer_marked"], quote=True)}</p>', 1)
        body = add_design(body, p, per_page, spec, today, links)
        body = resolve(body, today)
        h = h[:m.start(1)] + body + h[m.end(1):]
        h = h.replace("<body>", f'<body data-cat="{design.category(p["path"])}">', 1)
        if 'class="nd"' in body or "cal-list" in body or "data-print" in body or 'class="kv' in body:
            h = h.replace("</body>", tag + "</body>", 1)
        pages[rel] = h
    pages["assets/tools.js"] = tools
    icon32 = '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">'
    for rel, h in list(pages.items()):         # the 16px and 48px icons beside the 32px one the shared head already has
        if isinstance(h, str) and rel.endswith(".html") and icon32 in h and "favicon-16.png" not in h:
            pages[rel] = h.replace(icon32, ICON16 + "\n" + icon32 + "\n" + ICON48, 1)
    pages.update(files)
    for s in sorted(set(STALE)):
        print(f"  warning kurashi: a day count that has passed ({s}): the page needs this season's review")
    return pages
