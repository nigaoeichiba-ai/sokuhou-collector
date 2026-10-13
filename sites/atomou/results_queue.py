"""The days whose result is waiting to be written: finished in the last days, no result yet, not a quiet day.

    python sites/atomou/results_queue.py [--days 8] [--max 40] [--json]

The daily research reads this list, finds each result on the organizer's page (and on another site's), writes it in its own words, and passes it through resultcheck.py.
Order: a day people look for long after it (keep) first, then sports, then the other kinds of days that have a result (a race, a final, an announcement); the newest first."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import catalog  # noqa: E402

RESULT_KINDS = {"開催", "決勝", "発表", "試験日", "終了"}      # a day that has an outcome (a start or a release date has none)
GROUP_WEIGHT = {"スポーツ": 3, "エンタメ・音楽・賞": 2, "イベント・チケット": 1, "国際": 1, "経済・政治": 1, "学校・資格": 1}


def queue(entries: list[dict], today: date, days: int = 8, limit: int = 40) -> list[dict]:
    lo, hi = (today - timedelta(days=days)).isoformat(), (today - timedelta(days=1)).isoformat()
    rows = []
    for e in entries:
        last = e.get("date_end") or e["date"]
        if not (lo <= last <= hi) or e["precision"] != "day" or e["quiet"] or e.get("result") or e["kind"] not in RESULT_KINDS or e.get("estimated"):
            continue
        score = (3 if e.get("keep") else 0) + GROUP_WEIGHT.get(e["group"], 0)
        rows.append({"title": e["title"], "date": e["date"], "date_end": e.get("date_end"), "kind": e["kind"], "group": e["group"], "place": e["place"], "keep": bool(e.get("keep")), "score": score})
    rows.sort(key=lambda r: (-r["score"], r["date"], r["title"]))
    return rows[:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    entries, _ = catalog.build_catalog(today)
    rows = queue(entries, today, a.days, a.max)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{r['date']}  {r['score']}  {r['group']}  {r['title']}  ({r['kind']}, {r['place']})")
        print(f"{len(rows)} days waiting for a result")
    return 0


if __name__ == "__main__":
    sys.exit(main())
