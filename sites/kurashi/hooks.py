"""Hooks of sites/kurashi (sokuhou/newsite.py site_hooks): day counts, calendar files (.ics) and the page frame of the 2026-11-13 design (shell.py).  Nothing here writes a sentence of the site.

* The pages carry markers instead of day counts: {days:DATE} {rel:DATE} {rel:DATE|text for a day that has passed} {weeks:DATE} {today} {todayy}.
  The build turns them into the numbers of the build day (JST; the deploy rebuilds every site at 07:00 JST), inside <span class="nd" ...> so that assets/tools.js can
  correct them to the reader's own day.  The HTML that a search engine reads therefore has the right numbers on the day it was built.
* Every upcoming dated deadline of a page gets a calendar button; the file is calendar/<id>.ics (an all-day entry on the day, an alert at 09:00 the day before).
  A page that shows two or more deadlines also gets one file with all of them (calendar/<page>.ics; the home page and /month/: calendar/all.ics).
* post() puts every page into the frame of shell.py (header, hero, the checked guide, the sections, the official links, the footer) and writes assets/t/data.js for the browser's calendar.
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

MARK = re.compile(r"\{(days|rel|weeks):(\d{4}-\d\d-\d\d)(?:\|([^}]*))?\}|\{(today|todayy)\}")
STALE: list[str] = []          # a count that would be negative (a deadline that has passed): the page needs this season's review


_spec = importlib.util.spec_from_file_location("_kurashi_shell", Path(__file__).with_name("shell.py"))
shell = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shell)


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
            p["answer"] = f"{{todayy}}時点で最も近い期限は、{near}です。"
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


class Ctx:
    """what shell.render_page reads"""


def official_lists(content, guides_by_path, spec, tsite) -> dict:
    out = {}
    for p in content:
        if p["path"] == "/":
            continue
        v = shell.official_list(guides_by_path.get(p["path"]), p, spec, tsite)
        if v:
            out[p["path"]] = v
    return out


PLAIN = {"about/index.html": "/about/", "privacy/index.html": "/privacy/", "contact/index.html": "/contact/", "404.html": "/404.html", "contact/thanks.html": "/contact/thanks.html"}


def asset_version(site_dir: Path, extra: str) -> str:
    h = hashlib.sha1(extra.encode("utf-8"))
    for f in sorted((site_dir / "assets").rglob("*")):
        if f.is_file() and f.suffix in (".css", ".js"):
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:10]


def post(pages, content, cfg, spec, site_dir):
    from sokuhou.newsite import table_html
    today = today_jst()
    STALE.clear()
    files, per_page = calendar_files(content, spec, today)
    guides, tsite = shell.load_guides()
    ctx = Ctx()
    ctx.content, ctx.by_path, ctx.per_page = content, {p["path"]: p for p in content}, per_page
    ctx.page_guide, ctx.guides, ctx.tsite, ctx.table_html = shell.guide_of_page(guides), guides, tsite, table_html
    ctx.official = official_lists(content, ctx.page_guide, spec, tsite)
    index = shell.pages_index(content, guides)
    data = shell.data_js(guides, tsite, spec, index, today)
    ver = asset_version(site_dir, data)
    tools = (site_dir / "assets" / "tools.js").read_text(encoding="utf-8")
    tag = f'<script src="/assets/tools.js?v={hashlib.sha1(tools.encode()).hexdigest()[:8]}" defer></script>\n'
    tail = (site_dir / "home_tail.html").read_text(encoding="utf-8")
    for p in content:
        rel = "index.html" if p["path"] == "/" else p["path"].strip("/") + "/index.html"
        home = p["path"] == "/"
        if home:
            main, more = shell.home_main(p, ctx), ""
        else:
            main, more = shell.render_page(p, ctx)
        main = resolve(main, today)
        pages[rel] = shell.rewrap(pages[rel], main, path=p["path"], ver=ver, body_class="home-page" if home else "inner-page article-reading-page", modules="app" if home else "pages",
                                  with_tools=tag, head_more=more, home=home, foot_note=tail if home else "")
    # the pages that need the browser's saved list
    for rel, path, main in (("search/index.html", "/search/", shell.search_main(index)), ("saved/index.html", "/saved/", shell.saved_main())):
        title = "手続きを検索" if path == "/search/" else "あとで読むガイドと予定"
        base = pages["about/index.html"].replace("運営者情報", title)
        base = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{SITE_URL}{path}">', base)
        pages[rel] = shell.rewrap(base, resolve(main, today), path=path, ver=ver, body_class="inner-page", noindex=True, with_tools=tag)
    for rel, path in PLAIN.items():
        if rel not in pages:
            continue
        m = re.search(r'<main class="wrap">\n(.*?)\n</main>', pages[rel], re.S)
        if not m:
            continue
        pages[rel] = shell.rewrap(pages[rel], shell.plain_page_main(m.group(1), path, ""), path=path, ver=ver, body_class="inner-page", with_tools="", noindex=rel == "contact/thanks.html")
    for name in ("app", "calendar", "library", "pages", "illustrations"):
        pages[f"assets/t/{name}.js"] = pages[f"assets/t/{name}.js"].replace("__V__", ver)
    pages["assets/t/data.js"] = data
    pages["assets/tools.js"] = tools
    icon32 = '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">'
    for rel, h in list(pages.items()):         # the 16px and 48px icons beside the 32px one the shared head already has
        if isinstance(h, str) and rel.endswith(".html") and icon32 in h and "favicon-16.png" not in h:
            pages[rel] = h.replace(icon32, ICON16 + "\n" + icon32 + "\n" + ICON48, 1)
    pages.update(files)
    for s in sorted(set(STALE)):
        print(f"  warning kurashi: a day count that has passed ({s}): the page needs this season's review")
    return pages
