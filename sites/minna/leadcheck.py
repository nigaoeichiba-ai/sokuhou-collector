"""みんなのイラスト: find the sets whose lead names a subject that none of their pictures shows (2026-10-29: 12 sets did, e.g. a lead with 鶴・富士・凧 over eight pictures of 達磨・竹・梅・独楽…).

    python -m sites.minna.leadcheck

A subject is a word of the lead's opening list ("A・B・C・Dなど", "AやB"); it is found when it is a part of a picture's title, description or keyword.  The check is blunt: a spelling
that differs (眠気 / 眠い, 鶴亀 / 鶴と亀, お団子 / おだんご) is listed too, so read the list; it only helps to see a lead that was written before pictures were taken out by review.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

LIBRARY = Path(__file__).resolve().parent / "library"


def lead_misses(lead: str, hay: str) -> list[str]:
    m = re.match(r"^(.*?)(など|の素材|の絵|を|が|の)", lead)
    head = m.group(1) if m else ""
    if "・" not in head and "、" not in head:
        return []
    toks = [t for t in re.split(r"[・、,/／や]", head) if t and not re.search(r"[使印刷]|から|まで|ハイキング|風|で描いた|素材", t)]
    return [t for t in toks if t not in hay]


def main() -> None:
    rows = []
    for f in sorted(LIBRARY.glob("*/series.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        items = [it for it in d["items"] if os.path.exists(f.parent / it["file"])]
        hay = "".join(it["title"] + it["desc"] + " ".join(it["tags"]) for it in items) + d["title"] + " ".join(d.get("tags", []))
        miss = lead_misses(d["lead"], hay)
        if miss:
            rows.append((d["slug"], len(items), miss, " / ".join(it["title"] for it in items)[:160]))
    print(f"{len(rows)} set(s) whose lead names a subject found in none of its pictures")
    for slug, n, miss, titles in rows:
        print(f"  {slug} ({n} pictures): {'、'.join(miss)}  <- {titles}")


if __name__ == "__main__":
    main()
