"""Which municipality pages and weekly pages ask search engines to index them (the rest: noindex,follow and left out of the sitemap, still linked for readers).

Search Console (2026-10-20): most of the 127 municipality pages and 28 week pages were never shown in a search.  A page of the same shape for every municipality or week,
with few records behind it, adds little for a searcher and makes the site look like one table repeated.  What stays indexed:
  - a municipality page with enough records (live.INDEX_CITY_ROWS, and NO_DEMAND_CITY_ROWS unless Search Console showed the page), or one Google has shown;
  - no week page (2026-11-09): the 9 week pages that were left had 20 impressions and 1 click in 34 days, a text overlap of 0.83 between any two, and the same table every week.
    The pages stay on the site and linked from /digest/; they only ask search engines not to index them, and the loader of the ad script stays (the page is still part of the site).
demand.json lists the municipality pages that Search Console showed; the acquisition routine refreshes it.  Its digest_weeks list is no longer read.
"""
from __future__ import annotations

import json
from pathlib import Path

from sites.kuma import live as live_mod

NO_DEMAND_CITY_ROWS = 15     # a municipality page that Search Console has not shown stays out of the index while it has fewer records than this

_DEMAND = json.loads((Path(__file__).with_name("demand.json")).read_text(encoding="utf-8"))


def city_hash(slug: str, city: str) -> str:
    return live_mod.city_slug(slug, city)[2:]


def city_is_thin(slug: str, city: str, rows: list) -> bool:
    if len(rows) < live_mod.INDEX_CITY_ROWS:
        return True
    return city_hash(slug, city) not in _DEMAND["live_cities"] and len(rows) < NO_DEMAND_CITY_ROWS


def thin_weeks(weeks: list[str]) -> set[str]:
    """weeks: the week keys (as digest.build lists them).  Every week page is noindex: they are all of one shape and were almost never shown in a search."""
    return set(weeks)
