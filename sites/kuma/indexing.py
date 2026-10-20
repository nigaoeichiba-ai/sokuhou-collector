"""Which municipality pages and weekly pages ask search engines to index them (the rest: noindex,follow and left out of the sitemap, still linked for readers).

Search Console (2026-10-20): most of the 127 municipality pages and 28 week pages were never shown in a search.  A page of the same shape for every municipality or week,
with few records behind it, adds little for a searcher and makes the site look like one table repeated.  What stays indexed:
  - a municipality page with enough records (live.INDEX_CITY_ROWS, and NO_DEMAND_CITY_ROWS unless Search Console showed the page), or one Google has shown;
  - the newest KEEP_NEWEST_WEEKS week pages (they are what a searcher for "this week" looks for), and the week pages Google has shown.
demand.json lists the shown pages; the acquisition routine refreshes it from Search Console.
"""
from __future__ import annotations

import json
from pathlib import Path

from sites.kuma import live as live_mod

NO_DEMAND_CITY_ROWS = 15     # a municipality page that Search Console has not shown stays out of the index while it has fewer records than this
KEEP_NEWEST_WEEKS = 2        # the newest week pages stay indexed whether or not they have been shown yet

_DEMAND = json.loads((Path(__file__).with_name("demand.json")).read_text(encoding="utf-8"))


def city_hash(slug: str, city: str) -> str:
    return live_mod.city_slug(slug, city)[2:]


def city_is_thin(slug: str, city: str, rows: list) -> bool:
    if len(rows) < live_mod.INDEX_CITY_ROWS:
        return True
    return city_hash(slug, city) not in _DEMAND["live_cities"] and len(rows) < NO_DEMAND_CITY_ROWS


def thin_weeks(weeks: list[str]) -> set[str]:
    """weeks: the week keys, newest first (as digest.build lists them)."""
    keep = set(weeks[:KEEP_NEWEST_WEEKS]) | set(_DEMAND["digest_weeks"])
    return {k for k in weeks if k not in keep}
