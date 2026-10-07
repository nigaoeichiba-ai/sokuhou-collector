"""Permitted bear captures by prefecture (Ministry of the Environment, "クマ類の捕獲数(許可捕獲数)について [速報値]").

One PDF page with real text (an Excel export); the file name stays the same and is overwritten monthly.  Source page:
https://www.env.go.jp/nature/choju/effort/effort12/effort12.html -- the ministry's site is under the public data licence 1.0
(credit the ministry and say the data was processed).  Per prefecture and fiscal year (Heisei 20 onwards): total, killed, not killed
(released or moved); below the table, the national totals for the Asian black bear and the brown bear.  Prefectures with no recent
sightings or captures are not in the table (the PDF's note 2).  Every cell is read by position and the table is checked against its own
sums, so a changed layout is refused instead of guessed.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime

from sokuhou.http import fetch
from sokuhou.sources import env_kuma as env
from sokuhou.sources.kumalib import JST

PDF = env.BASE + "capture-qe.pdf"
LISTED = env.SHORT[:36]  # Hokkaido ... Tokushima: the 36 prefectures of the table
SPECIES = ("ツキノワグマ", "ヒグマ")


class EnvCaptureError(ValueError):
    pass


def _row_cells(tokens: list[dict], y: float, after_x: float) -> list[dict]:
    return [c for c in tokens if abs(c["y"] - y) <= 3 and c["x"] > after_x]


def parse_captures(pdf: bytes) -> dict:
    tokens = env._tokens(pdf, 0)
    updated = env._jp_date(tokens)
    as_of = next((m.group(1) for t in tokens if (m := re.search(r"\((R\d+年\d+月末)暫定値\)", env._nfkc(t["text"])))), None)
    if not as_of:
        raise EnvCaptureError("the provisional-figures month was not found")
    top = max(t["y"] for t in tokens if re.fullmatch(r"[HR]\d+年度", env._nfkc(t["text"])))
    heads = sorted((t for t in tokens if re.fullmatch(r"[HR]\d+年度", env._nfkc(t["text"])) and abs(t["y"] - top) < 60), key=lambda t: t["x"])
    labels = [env._nfkc(t["text"]).replace("年度", "") for t in heads]  # 'R07年度' -> 'R07'
    if len(labels) < 15 or labels[0] != "H20" or len(set(labels)) != len(labels):
        raise EnvCaptureError(f"fiscal year headers: {labels}")
    column = env._label_column(tokens)
    rows = [r for r in env._rows(tokens, column) if r["y"] < top - 10]
    species_rows = []
    for t in tokens:
        if t["x"] < column[1] + 10 and env._nfkc(t["text"]) in SPECIES:
            species_rows.append({"name": env._nfkc(t["text"]), "y": t["y"], "cells": _row_cells(tokens, t["y"], t["x"] + 3)})
    first = column[1]
    edges = [c["x"] + env._advance(c["text"], c["fs"]) for r in rows + species_rows for c in r["cells"] if c["x"] > first + 10]
    cols = env._cluster(edges)
    if len(cols) != 3 * len(labels):
        raise EnvCaptureError(f"{len(cols)} columns for {len(labels)} fiscal years")

    def read(row: dict) -> dict[str, list[int]]:
        vals: list = [None] * len(cols)
        for c in row["cells"]:
            if c["x"] <= first + 10:
                continue
            j = min(range(len(cols)), key=lambda k: abs(cols[k] - (c["x"] + env._advance(c["text"], c["fs"]))))
            if vals[j] is not None:
                raise EnvCaptureError(f"{row['name']}: two cells in one column")
            vals[j] = env._number(c["text"])
        out = {}
        for yi, label in enumerate(labels):
            triple = vals[yi * 3: yi * 3 + 3]
            if any(v is None for v in triple):
                raise EnvCaptureError(f"{row['name']} {label}: incomplete cells {triple}")
            out[label] = triple
        return out

    by_pref = {}
    national = None
    for row in rows:
        (by_pref.__setitem__(row["name"], read(row)) if row["name"] != "計" else None)
        if row["name"] == "計":
            national = read(row)
    if list(by_pref) != LISTED or national is None:
        raise EnvCaptureError(f"rows are {list(by_pref)}")
    species = {r["name"]: read(r) for r in species_rows}
    if set(species) != set(SPECIES):
        raise EnvCaptureError(f"species rows are {sorted(species)}")
    for label in labels:
        for k in range(3):
            if sum(by_pref[p][label][k] for p in LISTED) != national[label][k]:
                raise EnvCaptureError(f"{label}: prefectures do not add up to the national row (column {k})")
            if sum(species[s][label][k] for s in SPECIES) != national[label][k]:
                raise EnvCaptureError(f"{label}: the two species do not add up to the national row (column {k})")
        for who, tri in [(p, by_pref[p][label]) for p in LISTED] + [("計", national[label])]:
            if tri[0] != tri[1] + tri[2]:
                raise EnvCaptureError(f"{who} {label}: total is not killed + not killed ({tri})")
    return {"updated": updated, "as_of": as_of, "years": labels, "prefectures": [{"name": p, "by_year": by_pref[p]} for p in LISTED],
            "national": national, "species": species}


def collect() -> dict:
    out = parse_captures(fetch(PDF).body)
    out.update({"source_pdf": PDF, "source_page": env.PAGE, "fetched_at": datetime.now(JST).isoformat()})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
