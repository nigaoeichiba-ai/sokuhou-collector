"""Keeps data/kuma_digest_snapshot.json up to date: `python -m sites.kuma.digest_snapshot` (run by kuma-live.yml before it commits data).

The file holds only week counts per prefecture, the first and last day with a row, and rows per municipality name:
numbers derived from the public lists, no text of the lists themselves.
"""
from __future__ import annotations

import json
from pathlib import Path

from sites.kuma import build, digest, live as live_mod

ROOT = Path(__file__).resolve().parents[2]
SNAP = "kuma_digest_snapshot.json"


def load_prefs(data: Path) -> dict:
    return {k: json.loads((data / f"{k}_kuma.json").read_text(encoding="utf-8"))
            for k in live_mod.LIVE_SOURCES if (data / f"{k}_kuma.json").exists()}


def load_snapshot(data: Path) -> dict | None:
    f = data / SNAP
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def update(data: Path) -> bool:
    from sokuhou.sources import kumalib
    prefs = {k: v for k, v in load_prefs(data).items() if not kumalib.is_stopped(k)}
    dig = digest.build(build.digest_sources(prefs or None))
    old = load_snapshot(data)
    new = digest.updated_snapshot(old, dig)
    if new == old:
        return False
    (data / SNAP).write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return True


if __name__ == "__main__":
    print("snapshot changed" if update(ROOT / "data") else "snapshot unchanged")
