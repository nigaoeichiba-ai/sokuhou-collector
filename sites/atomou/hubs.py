"""The hub robot (巡回ロボ): visits the pages that gather many dated events in one place (monthly calendars, release schedules) and lists the lines that carry a coming date.

    python sites/atomou/hubs.py --state hubs_state.json --out hubs_candidates.json [--max 40]

data/atomou/hubs.json lists the pages (a template with {YYYYMM} / {YYMM} / {Y} / {M} / {Y1} is asked for this month and the next ones).  The robot:
- reads robots.txt of the host first and does not go where it says no (and waits as long as its Crawl-delay says, at least 2 seconds between two requests to a host);
- takes from a page only lines (a table row, a list item, a paragraph) that have a date between today and 120 days ahead: the date, the words on the line (cut short) and the address of the page;
- remembers which lines it has seen, so that a run says what is NEW today;
- never makes a card: a line is a lead.  The date is checked on the official page behind it (by hand or by the checking robot) before it goes into the catalogue.
Pages of the 'aggregator' kind (sites that gather other people's news) are not visited until their terms have been read (enabled: false)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
HUBS = ROOT / "data" / "atomou" / "hubs.json"
UA = "atomou-bot/1.0 (+https://atomou.com; reads public schedule pages, takes dates and headlines only)"
AHEAD = 120
MIN_GAP = 2.0

R_FULL = re.compile(r"(20\d\d)\s*[年/.\-]\s*(\d{1,2})\s*[月/.\-]\s*(\d{1,2})\s*日?")
R_MD = re.compile(r"(?<![\d/.])(\d{1,2})\s*月\s*(\d{1,2})\s*日")
R_SLASH = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})\s*[(（][月火水木金土日祝][)）]")


def load_hubs() -> dict:
    return json.loads(HUBS.read_text(encoding="utf-8"))


def month_list(today: date, n: int) -> list[date]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def urls_for(hub: dict, today: date, months: int) -> list[str]:
    def fill(url: str, d: date) -> str:
        return (url.replace("{YYYYMM}", f"{d.year}{d.month:02d}").replace("{YYMM}", f"{d.year % 100:02d}{d.month:02d}")
                .replace("{Y1}", str(d.year + 1)).replace("{Y}", str(d.year)).replace("{M}", str(d.month)))
    if hub.get("monthly"):
        return [fill(hub["url"], d) for d in month_list(today, months)]
    return [fill(hub["url"], today)]


def decode(body: bytes, content_type: str = "") -> str:
    """The charset of the HTTP header, then of the page's own meta tag; if neither is there, UTF-8 when it fits, else Shift_JIS."""
    m = re.search(r"charset=[\"']?([\w-]+)", content_type or "", re.I) or re.search(rb"charset=[\"']?([\w-]+)", body[:30000], re.I)
    name = (m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)).lower() if m else ""
    enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932", "euc-jp": "euc_jp"}.get(name, name)
    if enc:
        try:
            return body.decode(enc, "replace")
        except LookupError:
            pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp932", "replace")


def lines_of(html_: str) -> list[str]:
    """One text line per table row / list item / paragraph (cells and links stay on the line of their row)."""
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html_)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?i)</?(tr|li|p|div|br|h[1-6]|dt|dd|table|ul|ol|section|article|header|footer|nav|main)\b[^>]*>", "\n", s)
    s = unescape(re.sub(r"<[^>]+>", " ", s))
    out = []
    for ln in s.split("\n"):
        ln = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", ln)).strip()
        if ln:
            out.append(ln)
    return out


def dates_in(line: str, today: date) -> list[date]:
    found = []
    for m in R_FULL.finditer(line):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for rx in (R_MD, R_SLASH):
        for m in rx.finditer(line):
            mo, d = int(m.group(1)), int(m.group(2))
            for y in (today.year, today.year + 1):
                try:
                    c = date(y, mo, d)
                except ValueError:
                    continue
                if c >= today - timedelta(days=30):
                    found.append(c)
                    break
    return found


def clean_title(line: str, m_start: int, m_end: int) -> str:
    t = line if len(line) <= 120 else line[max(0, m_start - 50): m_end + 50]
    t = R_FULL.sub(" ", t)
    t = R_MD.sub(" ", t)
    t = R_SLASH.sub(" ", t)
    t = re.sub(r"[〜~～\-–—]\s*[〜~～\-–—]*", " ", t)
    return re.sub(r"\s+", " ", t).strip(" ・|｜:：,，、。")[:80]


def candidates_from(html_: str, today: date, hub: dict, url: str) -> list[dict]:
    last = today + timedelta(days=AHEAD)
    out, seen = [], set()

    def add(d: date, title: str):
        bare = re.sub(r"[()（）\[\]［］【】\s]|[月火水木金土日祝]曜?日?", "", title)      # "(日曜)" or a bare weekday is not a headline
        if len(title) < 5 or len(bare) < 4 or not re.search(r"[぀-ヿ一-鿿A-Za-z]", bare):
            return
        key = (d.isoformat(), title)
        if key in seen:
            return
        seen.add(key)
        cid = hashlib.sha1(f"{hub['id']}|{d.isoformat()}|{title}".encode("utf-8")).hexdigest()[:10]
        out.append({"id": cid, "hub": hub["id"], "date": d.isoformat(), "title": title, "url": url, "genre": hub.get("genre", ""), "kind": hub.get("kind", "")})

    ctx: date | None = None      # a line that is only a date ("11月3日(火)") is a heading: the lines under it, up to the next date, belong to it
    under = 0
    for ln in lines_of(html_):
        if len(ln) > 600:
            continue
        ds = dates_in(ln, today)
        if not ds:
            if ctx and under < 8 and 4 <= len(ln) <= 120:
                add(ctx, ln[:80])
                under += 1
            continue
        inside = [d for d in ds if today <= d <= last]
        m = (R_FULL.search(ln) or R_MD.search(ln) or R_SLASH.search(ln))
        title = clean_title(ln, m.start() if m else 0, m.end() if m else len(ln))
        if len(title) < 4:
            ctx, under = (min(inside) if inside else None), 0     # a heading
            continue
        ctx = None
        if inside:
            add(min(inside), title)
    return out


class Robots:
    """robots.txt of each host, read once per run with our own name."""
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.urlopen
        self.by_host: dict[str, RobotFileParser | None] = {}

    def parser(self, url: str):
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self.by_host:
            rp = RobotFileParser()
            req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": UA})
            try:
                with self.opener(req, timeout=20) as r:
                    rp.parse(decode(r.read(500_000)).splitlines())
                self.by_host[host] = rp
            except urllib.error.HTTPError as e:
                if e.code in (401, 403) :
                    rp.parse(["User-agent: *", "Disallow: /"])
                    self.by_host[host] = rp
                elif 400 <= e.code < 500:
                    rp.parse([])             # no robots.txt: nothing is forbidden
                    self.by_host[host] = rp
                else:
                    self.by_host[host] = None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                self.by_host[host] = None
        return self.by_host[host]

    def allowed(self, url: str) -> bool | None:
        rp = self.parser(url)
        return None if rp is None else rp.can_fetch(UA, url)

    def delay(self, url: str) -> float:
        rp = self.parser(url)
        d = rp.crawl_delay(UA) if rp is not None else None
        return max(MIN_GAP, float(d)) if d else MIN_GAP


def fetch(url: str, opener=None) -> tuple[str | None, int]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=25) as r:
            body = r.read(3_000_000)
            ct = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, 0
    if body[:4] == b"%PDF" or "pdf" in ct.lower():
        return None, -1
    return decode(body, ct), 200


def run(hubs: dict, state: dict, today: date, now: datetime | None = None, max_pages: int = 40, opener=None, pause: float | None = None) -> tuple[dict, dict, dict]:
    now = now or datetime.now(timezone.utc)
    robots = Robots(opener)
    seen: dict[str, str] = dict(state.get("seen") or {})
    last_host: dict[str, float] = {}
    pages = 0
    statuses = []
    cands: list[dict] = []
    for hub in hubs["hubs"]:
        if not hub.get("enabled"):
            continue
        got = 0
        res = "ok"
        for url in urls_for(hub, today, int(hubs.get("months", 4))):
            if pages >= max_pages:
                res = "limit"
                break
            ok = robots.allowed(url)
            if ok is None:
                res = "robots-unreadable"
                continue
            if not ok:
                res = "robots-no"
                continue
            host = urlparse(url).netloc
            gap = robots.delay(url) if pause is None else pause
            wait = last_host.get(host, 0) + gap - time.time()
            if wait > 0:
                time.sleep(wait)
            last_host[host] = time.time()
            html_, code = fetch(url, opener)
            pages += 1
            if html_ is None:
                if res == "ok":
                    res = f"http-{code}" if code else "unreachable"
                continue
            found = candidates_from(html_, today, hub, url)
            got += len(found)
            cands += found
        statuses.append({"id": hub["id"], "result": res, "candidates": got})
    # a line is NEW the first time it is seen; lines whose day has passed are forgotten
    seen = {i: d for i, d in seen.items() if d >= (today - timedelta(days=30)).isoformat()}
    new = []
    for c in cands:
        if c["id"] not in seen:
            seen[c["id"]] = c["date"]
            new.append(c["id"])
    new_set = set(new)
    for c in cands:
        c["new"] = c["id"] in new_set
    cands.sort(key=lambda c: (c["date"], c["hub"], c["title"]))
    pub = {"v": 1, "generated": now.isoformat(timespec="minutes"), "pages": pages, "hubs": statuses, "candidates": cands}
    return pub, {"seen": seen}, {"pages": pages, "hubs": statuses, "candidates": len(cands), "new": len(new)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="hubs_state.json")
    ap.add_argument("--out", default="hubs_candidates.json")
    ap.add_argument("--report", default="hubs_report.md")
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--only", default="", help="comma-separated hub ids (a trial)")
    a = ap.parse_args(argv)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    hubs = load_hubs()
    if a.only:
        keep = set(a.only.split(","))
        hubs["hubs"] = [h for h in hubs["hubs"] if h["id"] in keep]
        for h in hubs["hubs"]:
            h["enabled"] = True
    sp = Path(a.state)
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    pub, new_state, rep = run(hubs, state, today, max_pages=a.max)
    Path(a.out).write_text(json.dumps(pub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sp.write_text(json.dumps(new_state, ensure_ascii=False), encoding="utf-8")
    lines = [f"# hubs {pub['generated']}", "", f"pages {rep['pages']}, lines with a coming date {rep['candidates']}, new today {rep['new']}", ""]
    lines += [f"- {s['id']}: {s['result']}, {s['candidates']} lines" for s in rep["hubs"]]
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
