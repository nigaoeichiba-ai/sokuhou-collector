"""Which date pages (/e/<id>/) search engines may index: decided by the page's own content, by rule, every build.

    python sites/atomou/indexpolicy.py [--today YYYY-MM-DD]      # the counts per reason, and a sample of each side

A page is indexed when it is worth finding for someone who searches (a question the page really answers, with something of its own on it) and
is not a near-copy of its neighbours.  Everything else stays on the site exactly as usable (cards, search, calendar, links all work); it only
carries "noindex,follow" and is left out of the sitemap.  Nothing here changes what a visitor sees.

1. Gates (a "no" is final; the reason is kept):
   - not public yet (publish_on is later than today)
   - the day is over, and it is not a kept day and has no result: nobody searches "もう○日" for a short-lived notice
   - the date is not announced (estimated), or only a month / a year is known, unless it is a kept day: the page would change or say little
   - the source check is stale (status is neither active nor kept)
2. Always yes: a day with a result written for it (the page has text of its own that no other page has).
3. Otherwise a score (points; `THRESHOLD` or more is indexed):
   - kept day (long-lasting demand: festivals, milestones, big events) +30
   - verified by an official page +10, by two press reports +4; an official page we can link to +8
   - a table of earlier dates (history) +10: content of its own
   - a day (not a month) +8; has a place +3; has an end date +3; a title and a "what" with something to read +3
   - lead time: within 0-120 days +20 (when people search), 121-400 days +10, later +0 (kept days: always +20, the demand does not wait)
   - a deadline / exam / revision / enforcement day +8, a release or announcement +4 (people search "いつ" for these)
   - a subject guide exists +4 (the text is shared by the subject, so it is worth little alone)
   - a generic template title (the subject repeated with only a number or a place changed, 5 or more times on one day) -15 for the copies after the first
   The score of a page is a number the build prints; a tie is broken by the soonest date.
4. A ramp: a young domain should not show a thousand new pages at once.  At most `per_week` x (weeks since launch) pages (the best score first) are indexed;
   days with a result are outside the ramp.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

THRESHOLD = 50
FAR_DAYS = 400
NEAR_DAYS = 120


def _days_to(e: dict, today: date) -> int:
    return (date.fromisoformat(e["date"]) - today).days


def gate(e: dict, today: date) -> str | None:
    """The reason a page may not be indexed, or None."""
    if e.get("result"):
        return None
    if e["publish_on"] > today.isoformat():
        return "not-public-yet"
    kept = bool(e.get("keep"))
    end = e.get("date_end") or e["date"]
    if (end < today.isoformat() or e["status"] == "ended") and not kept:
        return "over"
    if not (e["status"] == "active" or kept):
        return "source-stale"
    if (e.get("estimated") or e["precision"] != "day") and not kept:
        return "date-not-exact"
    return None


def copies(entries: list[dict]) -> dict[str, int]:
    """id -> how many pages of the same subject on the same day came before it (a run of template pages)."""
    seen: dict[tuple, int] = defaultdict(int)
    total = Counter((e["subject"], e["date"]) for e in entries)
    out = {}
    for e in sorted(entries, key=lambda x: (x["date"], x["title"])):
        k = (e["subject"], e["date"])
        out[e["id"]] = seen[k] if total[k] >= 5 else 0
        seen[k] += 1
    return out


def score(e: dict, today: date, copy_no: int = 0, guided: bool = False) -> tuple[int, list[str]]:
    pts, why = 0, []

    def add(n: int, label: str) -> None:
        nonlocal pts
        pts += n
        why.append(f"{label}{n:+d}")
    if e.get("keep"):
        add(30, "keep")
    if e.get("basis") == "official":
        add(10, "official")
    else:
        add(4, "press")
    if e.get("official_url"):
        add(8, "official-link")
    if e.get("history"):
        add(10, "history")
    if e["precision"] == "day":
        add(8, "day")
    if (e.get("place") or "").strip():
        add(3, "place")
    if e.get("date_end"):
        add(3, "range")
    if len(e.get("title", "")) >= 8 and len(e.get("what", "")) >= 4:
        add(3, "text")
    n = _days_to(e, today)
    if e.get("keep") or 0 <= n <= NEAR_DAYS:
        add(20, "near")
    elif NEAR_DAYS < n <= FAR_DAYS:
        add(10, "ahead")
    if e.get("kind") in ("試験日", "締切", "改定", "施行"):
        add(8, "deadline")      # a day people must not miss: they search "いつ" for it
    elif e.get("kind") in ("発表", "発売"):
        add(4, "release")
    if guided:
        add(4, "guide")
    if copy_no:
        add(-15, "template-copy")
    return pts, why


def decide(entries: list[dict], today: date, launch: date, per_week: int = 60, guided=lambda e: False) -> dict[str, dict]:
    """id -> {"index": bool, "score": int, "reason": str}.  The reason is the gate that stopped it, "result", "ramp", "score" (below the threshold) or "ok"."""
    cp = copies(entries)
    weeks = max(0, (today - launch).days // 7) + 1
    cap = per_week * weeks
    out: dict[str, dict] = {}
    cands = []
    for e in entries:
        if e.get("result"):
            out[e["id"]] = {"index": True, "score": 100, "reason": "result"}
            continue
        g = gate(e, today)
        if g:
            out[e["id"]] = {"index": False, "score": 0, "reason": g}
            continue
        s, _ = score(e, today, cp[e["id"]], bool(guided(e)))
        if s < THRESHOLD:
            out[e["id"]] = {"index": False, "score": s, "reason": "score"}
        else:
            cands.append((-s, e["date"], e["title"], e["id"], s))
    cands.sort()
    for i, (_, _, _, eid, s) in enumerate(cands):
        out[eid] = {"index": i < cap, "score": s, "reason": "ok" if i < cap else "ramp"}
    return out


def indexable_ids(entries: list[dict], today: date, launch: date, per_week: int = 60, guided=lambda e: False) -> set[str]:
    return {i for i, d in decide(entries, today, launch, per_week, guided).items() if d["index"]}


def main() -> None:
    from sites.atomou import catalog, build
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    a = ap.parse_args()
    today = date.fromisoformat(a.today)
    entries, _ = catalog.build_catalog(today)
    cfg = build.load_config() if hasattr(build, "load_config") else {}
    launch = date.fromisoformat(cfg.get("launch_date") or "2026-10-08")
    d = decide(entries, today, launch, int(cfg.get("index_per_week", 60)), lambda e: e["subject"] in build.GUIDES)
    print(f"{len(entries)} pages; indexed {sum(v['index'] for v in d.values())}")
    for k, n in Counter(v["reason"] for v in d.values()).most_common():
        print(f"  {k}: {n}")
    by = {e["id"]: e for e in entries}
    for label, want in (("INDEX", True), ("NO (score)", False)):
        rows = [(v["score"], by[i]["title"], by[i]["date"]) for i, v in d.items() if v["index"] is want and (want or v["reason"] == "score")]
        rows.sort(reverse=True)
        print(label)
        for s, t, dt in rows[:8]:
            print(f"   {s:3d} {dt} {t}")


if __name__ == "__main__":
    main()
