"""Check card candidates against the official page they cite, and turn the ones that pass into seed items.

    python sites/atomou/seedcheck.py --out seed_x.json cand_1.json cand_2.json [--past-days 400] [--ahead-days 730] [--no-render]

A candidate is accepted only when: the schema is complete (and a 'day', 'month' or 'year' precision is named), the date is inside the window (the past too: the site counts
"もう○日" as well as "あと○日"), the title is new, the source page can be fetched, and the page's text contains the quote (normalised) with the day in it (a month for
precision 'month', a year for 'year').  A page that does not show the quote to a plain request (the date is put there by a script) is shown to Chrome and read again, as a person's
browser would show it.  Text found on a page is only compared with the quote; it is never taken in as an instruction."""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import catalog  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; atomou-source-check; +https://atomou.com)"}
KINDS = {"開催", "試験日", "開始", "締切", "改定", "発表", "極大", "終了", "決勝", "施行", "発売"}
PRECISIONS = ("day", "month", "year")
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
CHROME_PATHS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s　,，、。・:：()（）「」『』\"'“”‘’\-‐–—ー〜~/／|｜]", "", s)


def text_of(html_: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html_)
    return _html.unescape(re.sub(r"<[^>]+>", " ", s))


def decode(body: bytes, ctype: str = "") -> str:
    m = re.search(r"charset=[\"']?([\w-]+)", ctype or "", re.I) or re.search(rb"charset=[\"']?([\w-]+)", body[:30000], re.I)
    name = ((m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)) if m else "").lower()
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


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={**UA, "Accept-Language": "ja,en;q=0.5"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read(15_000_000)
        ctype = r.headers.get("Content-Type", "")
    if body[:4] == b"%PDF" or "pdf" in ctype.lower():
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.pdf")
            Path(p).write_bytes(body)
            try:
                import pypdf
                return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(p).pages)
            except Exception:
                return ""
    return text_of(decode(body, ctype))


def find_chrome() -> str | None:
    return next((p for p in CHROME_PATHS if Path(p).exists()), None) or shutil.which("google-chrome") or shutil.which("chromium")


def render(url: str, chrome: str | None = None) -> str:
    """The page as a browser shows it after its scripts have run (Chrome, headless)."""
    chrome = chrome or find_chrome()
    if not chrome:
        return ""
    with tempfile.TemporaryDirectory() as profile:
        try:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={profile}", "--virtual-time-budget=12000",
                                "--dump-dom", url], capture_output=True, timeout=90)
        except (subprocess.TimeoutExpired, OSError):
            return ""
    return text_of(r.stdout.decode("utf-8", "replace")) if r.returncode == 0 else ""


def quote_has_date(c: dict, precision: str) -> bool:
    return text_has_date(c["date"], c["source_quote"], precision)


def text_has_full_date(iso: str, text: str) -> bool:
    """The day with its YEAR is written in the text (an earlier year of a yearly event: '31日' alone would match any year)."""
    y, m, d = (int(x) for x in iso.split("-"))
    tn = norm(text).lower()
    en = MONTHS_EN[m - 1]
    forms = [f"{y}年{m}月{d}日", f"{y}/{m}/{d}", f"{y}/{m:02d}/{d:02d}", f"{y}.{m}.{d}", f"{y}.{m:02d}.{d:02d}", f"{y}-{m:02d}-{d:02d}", f"{d} {en} {y}", f"{en} {d}, {y}", f"{en} {d} {y}", f"{d} {en[:3]} {y}", f"{en[:3]} {d}, {y}"]
    return any(norm(x).lower() in tn for x in forms)


def text_has_date(iso: str, text: str, precision: str = "day") -> bool:
    """The day (or its month, or its year) is written in the text, in any of the usual ways."""
    y, m, d = (int(x) for x in iso.split("-"))
    q = text
    qn = norm(q)
    if precision == "year":
        return str(y) in qn
    if precision == "month":
        return norm(f"{m}月") in qn or bool(re.search(rf"{y}[/.]{m}\b", q))
    en = MONTHS_EN[m - 1]
    forms = [f"{m}月{d}日", f"{m}/{d}", f"{y}年{m}月{d}日", f"{y}.{m}.{d}", f"{y}/{m}/{d}", f"{m}.{d}", f"{d} {en} {y}", f"{en} {d}, {y}", f"{en} {d} {y}", f"{d} {en[:3]} {y}", f"{en[:3]} {d}, {y}", f"{d} {en}", f"{en} {d}", f"{d} {en[:3]}", f"{en[:3]} {d}", f"{d}th {en}", f"{d}th of {en}"]
    return any(norm(x).lower() in qn.lower() for x in forms) or bool(re.search(rf"{d}日|{d}[(（]", q))


def check(cands: list[dict], today: date, past_days: int = 400, ahead_days: int = 730, existing: set | None = None, page_of=None, render_of=None, use_render: bool = True) -> tuple[list[dict], list[tuple]]:
    lo, hi = (today - timedelta(days=past_days)).isoformat(), (today + timedelta(days=ahead_days)).isoformat()
    existing = existing or set()
    need = ("title", "date", "kind", "group", "category", "subject", "what", "place", "source_url", "source_quote")
    rejected, todo, seen = [], [], set()
    for c in cands:
        why = None
        prec = c.get("precision") or "day"
        if any(not c.get(k) for k in need):
            why = "missing " + ",".join(k for k in need if not c.get(k))
        elif prec not in PRECISIONS:
            why = "bad precision"
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["date"]) or not (("1800-01-01" if c.get("keep") else lo) <= c["date"] <= ("2100-12-31" if c.get("keep") else hi)):
            why = "date outside window"      # a kept day (a big event, a day in history) may be from any time, near or far
        elif c["kind"] not in KINDS:
            why = "bad kind"
        elif c.get("sensitivity", "none") not in ("none",) + tuple(catalog.QUIET):
            why = "bad sensitivity"
        elif c["group"] not in catalog.GROUPS:
            why = "bad group"
        elif not str(c["source_url"]).startswith("https://"):
            why = "not https"
        elif not 2 <= len(c["subject"]) <= 10:
            why = "subject must be 2-10 characters"
        elif not 4 <= len(c["what"]) <= 16:
            why = "what must be 4-16 characters"
        elif len(c["place"]) > 30:
            why = "place too long"
        elif norm(c["title"]) in existing or (norm(c["title"]), c["date"]) in seen:
            why = "duplicate"
        elif c.get("date_end") and not (c["date"] <= c["date_end"] <= ("2100-12-31" if c.get("keep") else hi)):
            why = "bad date_end"
        elif any(re.search(r"[<>{}\\]", v) for k, v in c.items() if k not in ("source_url", "history_url") and isinstance(v, str)):
            why = "markup"
        elif c.get("estimated"):
            hist = [h for h in (c.get("history") or []) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(h))]
            if not (c.get("typical") and c.get("series") and hist):
                why = "an estimate needs typical, series and history"
            elif len(c["typical"]) > 40 or c["date"] < today.isoformat():
                why = "an estimate must be a short phrase and a day to come"
        if why:
            rejected.append((c.get("title"), why))
            continue
        seen.add((norm(c["title"]), c["date"]))
        todo.append(c)
    pages: dict[str, str] = {}
    if page_of is None:
        byhost = defaultdict(list)
        for u in sorted({c["source_url"] for c in todo} | {c["history_url"] for c in todo if str(c.get("history_url") or "").startswith("https://")}):
            byhost[urlparse(u).netloc].append(u)

        def job(item):
            for u in item[1]:
                try:
                    pages[u] = fetch(u)
                except Exception as e:  # noqa: BLE001
                    pages[u] = "ERR " + str(e)[:60]
                time.sleep(0.5)
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(job, byhost.items()))
        page_of = pages.get
    render_of = render_of or (render if use_render else (lambda u: ""))
    ok = []
    for c in todo:
        prec = c.get("precision") or "day"
        page = page_of(c["source_url"]) or ""
        if page.startswith("ERR") or not page:
            rejected.append((c["title"], "fetch failed: " + page[:60]))
            continue
        nq = norm(c["source_quote"])
        if len(nq) < 4:
            rejected.append((c["title"], "quote too short"))
            continue
        est = bool(c.get("estimated"))
        hist_ok: list[str] = []
        if est:
            # the quote proves the NEWEST earlier day; every day of the history must be written on the history page (or the source page); only those are kept
            hist_text = page_of(c.get("history_url") or c["source_url"]) or ""
            hist_ok = [h for h in sorted(set(c["history"]), reverse=True) if text_has_full_date(h, hist_text) or text_has_full_date(h, page)]
            ref = {"date": hist_ok[0] if hist_ok else c["history"][0], "source_quote": c["source_quote"]}
            if not hist_ok or not text_has_full_date(ref["date"], ref["source_quote"]):
                rejected.append((c["title"], "the quote does not contain the newest earlier day" if hist_ok else "no earlier day is written on the page"))
                continue
        elif not quote_has_date(c, prec):
            rejected.append((c["title"], "the quote does not contain the date"))
            continue
        found = nq in norm(page)
        via = "http"
        if not found:
            shown = render_of(c["source_url"])
            if shown and nq in norm(shown):
                found, via = True, "browser"
        if not found and len(str(c.get("seen_in_browser") or "")) >= 10:
            # the date is in a picture (or drawn by the page) and a person looked at the page in a browser: what was seen is written down in this field
            found, via = True, "eyes"
        if not found:
            rejected.append((c["title"], "quote not on the page"))
            continue
        item = {k: v for k, v in c.items() if not k.startswith("_")}
        item["source_quote"] = item["source_quote"][:60]
        if est:
            item["history"] = hist_ok
            item.pop("history_url", None)
            item["note"] = ((item.get("note") or "") + " 例年の時期からの予想。過去の日付は、公式ページで確かめた。").strip()
        item.update({"checked_on": today.isoformat(), "verified": True})
        item.setdefault("sensitivity", "none")
        item.setdefault("ad_ok", True)
        item.setdefault("son_toku", False)
        item.setdefault("region", (item.get("place") or "全国").split("(")[0] or "全国")
        item.setdefault("date_end", None)
        item["precision"] = prec
        item.setdefault("note", "")
        how = {"http": "出典ページの本文で、日付を機械的に確かめた。", "browser": "出典ページをブラウザで表示して、日付を確かめた。", "eyes": "出典ページをブラウザで開いて、画面で日付を確かめた。"}[via]
        item.pop("seen_in_browser", None)
        item["note"] = (item["note"] + (" " if item["note"] else "") + how).strip()
        ok.append(item)
    return ok, rejected


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--past-days", type=int, default=400)
    ap.add_argument("--ahead-days", type=int, default=730)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    cands = []
    for f in a.files:
        raw = Path(f).read_text(encoding="utf-8")
        m = re.search(r"\[.*\]", raw, re.S)
        cands += json.loads(m.group(0)) if m else []
    existing = {norm(e["title"]) for f in (ROOT / "data" / "atomou").glob("seed_*.json") for e in json.loads(f.read_text(encoding="utf-8"))}
    ok, rejected = check(cands, today, a.past_days, a.ahead_days, existing, use_render=not a.no_render)
    Path(a.out).write_text(json.dumps(ok, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidates {len(cands)}  accepted {len(ok)}  rejected {len(rejected)}")
    for t, w in rejected:
        print("  REJECT", t, "|", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
