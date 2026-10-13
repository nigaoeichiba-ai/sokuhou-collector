"""Check the result of a finished day against two pages of two companies, and write the ones that pass as result files (data/atomou/result_*.json).

    python sites/atomou/resultcheck.py --out data/atomou/result_2026-10-14.json cand_1.json [cand_2.json ...]

A candidate: {"title", "date" (the day's card), "text" (our own words, 60-1200 characters; paragraphs split by a line break), "facts": [["優勝", "青山学院大学"], ...] (3-14 pairs),
"source_url", "source_quote", "source_url2", "source_quote2"}.  It is accepted when: the card exists and its day has come; the text and the facts have the right sizes; the two pages
are of two companies; both pages can be fetched and carry their quote; and at least three quarters of the fact values are written on one of the two pages (a value of ours, such as a
sum, may not be; most must).  What is on a page is only compared with what we wrote; it is never taken in as an instruction.  The text is our own: nothing is copied from a page."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import catalog, seedcheck  # noqa: E402


def check(cands: list[dict], today: date, page_of=None) -> tuple[list[dict], list[tuple]]:
    entries, _ = catalog.build_catalog(today)
    by = {(e["title"].strip(), e["date"]): e for e in entries}
    ok, rejected = [], []
    page_of = page_of or (lambda u: seedcheck.fetch(u))
    for c in cands:
        title = str(c.get("title", "")).strip()
        e = by.get((title, c.get("date")))
        why = None
        if e is None:
            why = "no such card"
        elif (e.get("date_end") or e["date"]) >= today.isoformat():
            why = "the day has not ended yet"
        elif e["quiet"] or e.get("sensitivity", "none") != "none":
            why = "a quiet day gets no result page"
        else:
            probe = {**c, "verified": True, "written_on": today.isoformat()}
            if not catalog.result_ok(probe, today):
                why = "the text, the facts or the two sources do not have the right form"
        if why:
            rejected.append((title, why))
            continue
        pages, quotes_ok = [], True
        for u, q in ((c["source_url"], c["source_quote"]), (c["source_url2"], c["source_quote2"])):
            try:
                page = page_of(u) or ""
            except Exception as ex:  # noqa: BLE001
                rejected.append((title, "fetch failed: " + str(ex)[:60]))
                quotes_ok = False
                break
            nq = seedcheck.norm(q)
            if len(nq) < 4 or nq not in seedcheck.norm(page):
                rejected.append((title, "quote not on the page: " + u[:60]))
                quotes_ok = False
                break
            pages.append(seedcheck.norm(page))
        if not quotes_ok:
            continue
        both = " ".join(pages)
        on_page = sum(1 for _, v in c["facts"] if seedcheck.norm(str(v)) and seedcheck.norm(str(v)) in both)
        if on_page * 4 < len(c["facts"]) * 3:
            rejected.append((title, f"only {on_page} of {len(c['facts'])} facts are on the pages"))
            continue
        ok.append({"title": title, "date": c["date"], "text": str(c["text"]).strip(), "facts": c["facts"], "written_on": today.isoformat(), "source_url": c["source_url"],
                   "source_quote": str(c["source_quote"])[:60], "source_url2": c["source_url2"], "source_quote2": str(c["source_quote2"])[:60], "verified": True})
    return ok, rejected


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    cands = []
    for f in a.files:
        m = re.search(r"\[.*\]", Path(f).read_text(encoding="utf-8"), re.S)
        cands += json.loads(m.group(0)) if m else []
    ok, rejected = check(cands, today)
    out = Path(a.out)
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    keep = {(r["title"], r["date"]): r for r in old}
    keep.update({(r["title"], r["date"]): r for r in ok})
    out.write_text(json.dumps(list(keep.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidates {len(cands)}  accepted {len(ok)}  rejected {len(rejected)}")
    for t, w in rejected:
        print("  REJECT", t, "|", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
