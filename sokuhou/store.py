"""Persistence helpers: write only when content changed, and accumulate history the source page forgets."""
from __future__ import annotations

import json
import os
from pathlib import Path

VOLATILE = ("fetched_at",)


def _normalized(payload: dict) -> str:
    return json.dumps({k: v for k, v in payload.items() if k not in VOLATILE}, ensure_ascii=False, sort_keys=True)


def read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_if_changed(path: Path, payload: dict) -> bool:
    """Write payload unless it equals the stored one apart from fetched_at. Returns True when written."""
    old = read(path)
    if old is not None and _normalized(old) == _normalized(payload):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written file
    return True


def merge_incidents(old: dict | None, new: dict) -> dict:
    """Keep every incident ever seen; the source page only lists the latest ~10."""
    merged = {}
    for source in ((old or {}).get("incidents", []), new["incidents"]):
        for inc in source:
            key = (inc["started_at"], inc["place"], inc["kind"])
            merged[key] = {**merged.get(key, {}), **inc}  # a later observation updates status/resolution
    out = {k: v for k, v in new.items() if k != "incidents"}
    out["incidents"] = sorted(merged.values(), key=lambda i: i["started_at"], reverse=True)
    return out
