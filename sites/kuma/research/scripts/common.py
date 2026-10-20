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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


# ---- the Ministry of the Environment's tables (data/env_kuma.json, data/env_capture_kuma.json): notes built from them name the page that was opened

MOE_PAGE = "https://www.env.go.jp/nature/choju/effort/effort12/effort12.html"
MOE_CREDIT = "出典:環境省「クマに関する各種情報・取組」の公表資料(速報値)を加工して作成。環境省が作成したものではありません"
MOE_CHECKED = "2026-10-20"     # the day the Ministry's page was opened and the PDFs named in each note were seen to be listed there
MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def load_env() -> dict:
    return json.loads((DATA / "env_kuma.json").read_text(encoding="utf-8"))


def load_capture() -> dict:
    return json.loads((DATA / "env_capture_kuma.json").read_text(encoding="utf-8"))


def fy(y: str) -> str:
    """'R07' -> '令和7年度', 'H20' -> '平成20年度'."""
    return f"{'平成' if y[0] == 'H' else '令和'}{int(y[1:])}年度"


def full_name(short: str) -> str:
    from sokuhou import prefectures as pf
    return pf.full(short)


def jp(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.year}年{x.month}月{x.day}日"
