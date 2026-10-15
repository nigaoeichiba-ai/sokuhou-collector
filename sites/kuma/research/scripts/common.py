"""Shared helpers of the research-note scripts (sites/kuma/research/scripts/<slug>.py): read the stored records, write the note.

Run a script from the repository root:  python sites/kuma/research/scripts/<slug>.py
It reads data/*_kuma.json, computes every number, and writes sites/kuma/research/<date>-<slug>.json (see sites/kuma/research.py for the format).
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "data"
OUT = ROOT / "sites" / "kuma" / "research"
JST = timezone(timedelta(hours=9))
FY_START = date(2026, 4, 1)          # the fiscal year the notes count (令和8年度)

sys.stdout.reconfigure(encoding="utf-8")


def today() -> date:
    return datetime.now(JST).date()


def load_source(key: str) -> dict:
    """{'credit', 'as_of', 'rows': [(datetime or date, kind, city, place)]} of one record source, this fiscal year only."""
    raw = json.loads((DATA / f"{key}_kuma.json").read_text(encoding="utf-8"))
    rows = []
    for x in raw["sightings"]:
        o = x["observed_at"]
        if o[:10] < FY_START.isoformat():
            continue
        has_time = "T" in o and not o.endswith("T00:00:00+09:00")
        rows.append((datetime.fromisoformat(o) if has_time else date.fromisoformat(o[:10]), x["kind"], x.get("city", ""), x.get("place", "")))
    return {"credit": raw["credit"], "as_of": raw["as_of"], "rows": rows}


def write_note(doc: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{doc['date']}-{doc['slug']}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", path.relative_to(ROOT))
    return path


def pct(part: int, whole: int, digits: int = 0) -> float:
    return round(part / whole * 100, digits) if whole else 0.0
