"""Run collectors and store results under data/.  Usage: python -m sokuhou.run daily|frequent

Each source is isolated: one failing source never blocks the others, and a result that fails its sanity
check is NOT stored (the previous good file stays). Exit code is 1 if any source failed, so CI shows it.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sokuhou import store
from sokuhou.sources import jgrants, mhlw_minwage, otsu_bear, otsu_fire

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SanityError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    collect: Callable[[], dict]
    check: Callable[[dict | None, dict], None] = lambda old, new: None
    merge: Callable[[dict | None, dict], dict] | None = None


def check_minwage(old, new):
    if old and new["latest_fiscal_year"] < old["latest_fiscal_year"]:
        raise SanityError("latest fiscal year went backwards")


def check_jgrants(old, new):
    if new["total"] == 0:
        raise SanityError("jGrants returned no subsidies")
    if old and old["total"] >= 20 and new["total"] < old["total"] * 0.3:
        raise SanityError(f"jGrants total dropped {old['total']} -> {new['total']}")


def check_bear(old, new):
    if new["unparsed"]:
        raise SanityError(f"{len(new['unparsed'])} placemarks could not be parsed")
    if old and len(new["sightings"]) < len(old["sightings"]) * 0.9:
        raise SanityError(f"sightings dropped {len(old['sightings'])} -> {len(new['sightings'])}")


def check_fire(old, new):
    if new["unparsed"]:
        raise SanityError(f"{len(new['unparsed'])} messages in an unknown format (page layout changed?)")


GROUPS: dict[str, list[Source]] = {
    "daily": [
        Source("minwage", mhlw_minwage.collect, check_minwage),
        Source("jgrants", jgrants.collect, check_jgrants),
        Source("otsu_bear", otsu_bear.collect, check_bear),
    ],
    "frequent": [
        Source("otsu_fire", otsu_fire.collect, check_fire, store.merge_incidents),
    ],
}


def run_group(sources: list[Source], data_dir: Path) -> tuple[list[str], dict[str, str]]:
    changed, errors = [], {}
    for src in sources:
        path = data_dir / f"{src.name}.json"
        try:
            new = src.collect()
            old = store.read(path)
            src.check(old, new)
            if src.merge:
                new = src.merge(old, new)
            if store.write_if_changed(path, new):
                changed.append(src.name)
        except Exception as e:  # noqa: BLE001 - isolate every source; report all failures at the end
            errors[src.name] = f"{type(e).__name__}: {e}"
    return changed, errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in GROUPS:
        print(f"usage: python -m sokuhou.run {'|'.join(GROUPS)}", file=sys.stderr)
        return 2
    changed, errors = run_group(GROUPS[argv[1]], DATA_DIR)
    print("changed:", ", ".join(changed) or "(none)")
    for name, msg in errors.items():
        print(f"FAILED {name}: {msg}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
