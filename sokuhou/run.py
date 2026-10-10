"""Run collectors and store results under data/.  Usage: python -m sokuhou.run daily|frequent

Each source is isolated: one failing source never blocks the others, and a result that fails its sanity
check is NOT stored (the previous good file stays). Exit code is 1 if any source failed, so CI shows it.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sokuhou import store
from sokuhou.sources import kumalib
from sokuhou.sources import (
    akita_kuma,
    aomori_kuma,
    env_capture_kuma,
    env_kuma,
    fukushima_kuma,
    estat_wage,
    jgrants,
    mhlw_minwage,
    miyagi_kuma,
    nara_kuma,
    niigata_kuma,
    okayama_kuma,
    otsu_bear,
    otsu_fire,
    saitama_kuma,
    sorachi_kuma,
    toyama_kuma,
    yamagata_kuma,
    yamaguchi_kuma,
    yamanashi_kuma,
)

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


def check_estat_wage(old, new):
    def reiwa(label):
        m = re.fullmatch(r"令和(\d+)年", label)
        return int(m.group(1)) if m else -1

    if old and reiwa(new["year_label"]) < reiwa(old["year_label"]):
        raise SanityError("year label went backwards")


def check_env_kuma(old, new):
    """The ministry revises provisional figures, so values may move; the update dates may not go backwards."""
    for key in ("sightings", "injuries"):
        if old and new[key]["updated"] < old[key]["updated"]:
            raise SanityError(f"{key}: update date went backwards")
    if old and len(new["injuries"]["years"]) < len(old["injuries"]["years"]):
        raise SanityError("injury table lost fiscal years")


def check_env_capture(old, new):
    """Provisional figures may be revised, but the table keeps its fiscal years and its update date does not go backwards."""
    if old and new["updated"] < old["updated"]:
        raise SanityError("capture table: update date went backwards")
    if old and len(new["years"]) < len(old["years"]):
        raise SanityError("capture table lost fiscal years")


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


def _sighting_fy(observed_at: str) -> str:
    year, month = int(observed_at[:4]), int(observed_at[5:7])
    fy_start = year if month >= 4 else year - 1
    return f"R{fy_start - 2018:02d}"


def _sightings_by_fy(data: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for sighting in data.get("sightings", []):
        fy = _sighting_fy(sighting["observed_at"])
        out[fy] = out.get(fy, 0) + 1
    return out


def check_pref_bear(old, new):
    """A source's current fiscal year must not lose rows (older years are stored only in part, so they are not compared)."""
    if not old:
        return
    old_counts = _sightings_by_fy(old)
    new_counts = _sightings_by_fy(new)
    if not new_counts:
        raise SanityError(f"{new['source']} has no sightings")
    fy = max(new_counts)
    if fy in old_counts and new_counts[fy] < old_counts[fy] * 0.7:
        raise SanityError(f"{new['source']} {fy} sightings dropped {old_counts[fy]} -> {new_counts[fy]}")


def check_counts_bear(old, new):
    """A source without an explicit licence is stored as counts only: refuse anything that looks like a row list, and a shrinking year."""
    if new.get("mode") != "counts" or {"sightings", "places", "lat", "lon"} & set(new):
        raise SanityError("a counts-only source must not store rows, places or coordinates")
    for city, m in new["municipalities"].items():
        if set(m) != {"monthly", "latest"}:
            raise SanityError(f"{city}: unexpected fields {sorted(m)}")
    if old and old.get("fy_current") == new["fy_current"] and new["total_fy"] < old["total_fy"] * 0.7:
        raise SanityError(f"{new['source']} {new['fy_current']} count dropped {old['total_fy']} -> {new['total_fy']}")


def check_fire(old, new):
    if new["unparsed"]:
        raise SanityError(f"{len(new['unparsed'])} messages in an unknown format (page layout changed?)")


GROUPS: dict[str, list[Source]] = {
    "daily": [
        Source("minwage", mhlw_minwage.collect, check_minwage),
        Source("estat_wage", estat_wage.collect, check_estat_wage),
        Source("env_kuma", env_kuma.collect, check_env_kuma),
        Source("env_capture_kuma", env_capture_kuma.collect, check_env_capture),
        Source("jgrants", jgrants.collect, check_jgrants),
    ],
    # kuma-sokuho.com's municipal sightings: collected several times a day by kuma-live.yml, which then deploys only that site
    "kuma": [
        Source("miyagi_kuma", miyagi_kuma.collect, check_pref_bear),
        Source("akita_kuma", akita_kuma.collect, check_pref_bear),
        Source("yamaguchi_kuma", yamaguchi_kuma.collect, check_pref_bear),
        Source("okayama_kuma", okayama_kuma.collect, check_pref_bear),
        Source("yamanashi_kuma", yamanashi_kuma.collect, check_pref_bear),
        Source("sorachi_kuma", sorachi_kuma.collect, check_pref_bear),
        Source("toyama_kuma", toyama_kuma.collect, check_pref_bear),   # the prefecture's written permission (2026-10-06): records, no coordinates
        # no explicit licence: counts only (municipality, month, count, latest date), see kumalib.package_counts
        Source("fukushima_kuma", fukushima_kuma.collect, check_counts_bear),
        Source("niigata_kuma", niigata_kuma.collect, check_counts_bear),
        Source("yamagata_kuma", yamagata_kuma.collect, check_counts_bear),
        Source("aomori_kuma", aomori_kuma.collect, check_counts_bear),
        Source("nara_kuma", nara_kuma.collect, check_counts_bear),
        Source("saitama_kuma", saitama_kuma.collect, check_counts_bear),
        Source("otsu_bear", otsu_bear.collect, check_bear),
    ],
    "frequent": [
        Source("otsu_fire", otsu_fire.collect, check_fire, store.merge_incidents),
    ],
}


def run_group(sources: list[Source], data_dir: Path) -> tuple[list[str], dict[str, str]]:
    changed, errors = [], {}
    for src in sources:
        if kumalib.is_stopped(src.name):      # the publisher asked us to stop: not collected (and the site ignores its stored file)
            continue
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
