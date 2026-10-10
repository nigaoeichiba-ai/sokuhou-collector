"""The checking robot (検証ロボ): opens the official page behind every day of the catalogue again and again, and says which days it can no longer find there.

    python sites/atomou/recheck.py --state recheck_state.json --out recheck.v1.json [--max 60]

A day is kept with the page it came from (source_url) and the words of that page it stands on (source_quote).  A day's date can change; the page then changes too.  So:
- the page is fetched again (the nearer the day, the more often: within 7 days every run, within 30 days daily, otherwise weekly);
- the quote (or, when the page was written again, the title and the date near each other) must still be on the page;
- a page that cannot be fetched says nothing (a site that is down is not a changed date);
- a day whose page was fetched but no longer has it is "changed": the app shows "出典のページで、この日付が見つかりません。変わったかもしれません" on it (assets/live.js reads recheck.v1.json),
  and the report lists it so that the day can be corrected from the new page.  The robot never edits a date by itself.
Politeness: a name in the User-Agent, one request per host per second, at most --max pages a run, a page once per run even when many days stand on it."""
from __future__ import annotations

import argparse
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import catalog  # noqa: E402

UA = "atomou-bot/1.0 (+https://atomou.com; checks that an official date is still on its page)"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s　,，、。・:：()（）「」『』\"'“”‘’\-‐–—ー〜~/／|｜]", "", s).lower()


def interval_days(entry_date: str, today: date) -> float:
    """How long a page may rest before it is checked again."""
    try:
        d = date.fromisoformat(entry_date)
    except ValueError:
        return 7
    away = (d - today).days
    return 0.2 if away <= 7 else 1 if away <= 30 else 7   # 0.2 = about 5 hours: every run of a 6-hourly schedule


def date_forms(iso: str) -> list[str]:
    y, m, d = (int(x) for x in iso.split("-"))
    return [f"{y}年{m}月{d}日", f"{y}年{m}月{d:02d}日", f"{m}月{d}日", f"{m}月{d:02d}日", f"{y}/{m}/{d}", f"{y}/{m:02d}/{d:02d}", f"{y}.{m}.{d}", f"{y}.{m:02d}.{d:02d}", f"{m}/{d}", f"{m}.{d}", f"{y}-{m:02d}-{d:02d}",
            f"{d}日", f"{d}(", f"{d}（"]


def still_there(entry: dict, page: str) -> bool:
    """The day's words are on the page: its quote, or its title's core and its date within 90 characters of each other."""
    np_ = norm(page)
    q = norm(entry.get("source_quote") or "")
    if len(q) >= 6 and q in np_:
        return True
    core = re.sub(r"第\d+回|[()（）]|20\d\d年?|\s", "", entry["title"])[:5]
    if len(core) < 2:
        return False
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", page))
    forms = [unicodedata.normalize("NFKC", f) for f in date_forms(entry["date"])]
    for cm in re.finditer(re.escape(unicodedata.normalize("NFKC", core)), text):
        near = text[max(0, cm.start() - 90): cm.end() + 90]
        if any(f in near for f in forms):
            return True
    return False


def verdict(entry: dict, page: str) -> str:
    """"ok": the day's words are on the page (the quote, or the title and the date near each other, or both somewhere on it);
    "changed": the page still speaks of the event but its date is no longer there (the date moved: shown on the day as 再確認);
    "lost": the page no longer speaks of the event at all (a page of another shape, a script-made page, a removed page: only listed in the report)."""
    if still_there(entry, page):
        return "ok"
    text = unicodedata.normalize("NFKC", page)
    core = unicodedata.normalize("NFKC", re.sub(r"第\d+回|[()（）]|20\d\d年?|\s", "", entry["title"])[:5])
    has_core = len(core) >= 2 and core in re.sub(r"\s+", "", text)
    forms = [unicodedata.normalize("NFKC", f) for f in date_forms(entry["date"])[:8]]
    squashed = re.sub(r"\s+", "", text)
    has_date = any(re.sub(r"\s+", "", f) in squashed for f in forms)
    if has_core and has_date:
        return "ok"
    return "changed" if has_core else "lost"


def fetch(url: str, opener=None) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=25) as r:
            body = r.read(5_000_000)
            ct = r.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if body[:4] == b"%PDF" or "pdf" in ct.lower():
        return None            # not read here (a PDF's text needs a reader); it is neither "found" nor "gone"
    m = re.search(rb"charset=[\"']?([\w-]+)", body[:6000], re.I)
    enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932"}.get((m.group(1).decode() if m else "utf-8").lower(), (m.group(1).decode() if m else "utf-8"))
    try:
        text = body.decode(enc, "replace")
    except LookupError:
        text = body.decode("utf-8", "replace")
    return page_text(text)


def page_text(html_: str) -> str:
    """The words of a page: no scripts, no styles, no tags (a quote runs across table cells and links)."""
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</>", " ", html_)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    return unescape(re.sub(r"<[^>]+>", " ", s))


def run(entries: list[dict], state: dict, today: date, now: datetime | None = None, max_pages: int = 60, opener=None, pause: float = 1.0) -> tuple[dict, dict, dict]:
    """-> (public file, new state, report).  state = {"url": {"at": iso, "found": {id: bool}}}."""
    now = now or datetime.now(timezone.utc)
    by_url: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("status") == "ended" or not str(e.get("source_url", "")).startswith("https://"):
            continue
        by_url.setdefault(e["source_url"], []).append(e)
    due = []
    for url, es in by_url.items():
        last = (state.get(url) or {}).get("at")
        gap = min(interval_days(e["date"], today) for e in es)
        if not last or now - datetime.fromisoformat(last) >= timedelta(days=gap):
            due.append((min(e["date"] for e in es), url))
    due.sort()                      # the nearest day first
    new_state = {u: s for u, s in state.items() if u in by_url}
    last_host: dict[str, float] = {}
    report = {"checked": 0, "unreadable": 0, "changed": [], "lost": [], "due": len(due)}
    for _, url in due[:max_pages]:
        host = urlparse(url).netloc
        wait = last_host.get(host, 0) + pause - time.time()
        if wait > 0:
            time.sleep(wait)
        last_host[host] = time.time()
        page = fetch(url, opener)
        report["checked"] += 1
        if page is None:
            report["unreadable"] += 1
            new_state[url] = {**(state.get(url) or {}), "at": now.isoformat(timespec="minutes"), "fail": int((state.get(url) or {}).get("fail", 0)) + 1}
            continue
        found = {e["id"]: verdict(e, page) for e in by_url[url]}
        new_state[url] = {"at": now.isoformat(timespec="minutes"), "found": found, "fail": 0}
    changed = sorted(i for s in new_state.values() for i, v in (s.get("found") or {}).items() if v == "changed")
    lost = sorted(i for s in new_state.values() for i, v in (s.get("found") or {}).items() if v == "lost")
    titles = {e["id"]: (e["title"], e["date"], e["source_url"]) for es in by_url.values() for e in es}
    report["changed"] = [{"id": i, "title": titles[i][0], "date": titles[i][1], "url": titles[i][2]} for i in changed if i in titles]
    report["lost"] = [{"id": i, "title": titles[i][0], "date": titles[i][1], "url": titles[i][2]} for i in lost if i in titles]
    pub = {"v": 1, "generated": now.isoformat(timespec="minutes"), "checked": sum(1 for s in new_state.values() if s.get("found") is not None), "changed": changed}
    return pub, new_state, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="recheck_state.json")
    ap.add_argument("--out", default="recheck.v1.json")
    ap.add_argument("--report", default="recheck_report.md")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args(argv)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    entries, _ = catalog.build_catalog(today)
    sp = Path(a.state)
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    pub, new_state, rep = run(entries, state, today, max_pages=a.max)
    Path(a.out).write_text(json.dumps(pub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sp.write_text(json.dumps(new_state, ensure_ascii=False), encoding="utf-8")
    lines = [f"# recheck {pub['generated']}", "", f"pages due {rep['due']}, checked {rep['checked']}, unreadable {rep['unreadable']}, dates changed: {len(rep['changed'])}, events not found on their page: {len(rep.get('lost', []))}", ""]
    lines += [f"- changed: {c['date']} {c['title']} — {c['url']}" for c in rep["changed"]]
    lines += [f"- lost (the page does not speak of it any more; look by hand): {c['date']} {c['title']} — {c['url']}" for c in rep.get("lost", [])]
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
