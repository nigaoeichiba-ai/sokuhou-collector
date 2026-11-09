"""Which municipality pages and weekly pages ask search engines to index them (the rest: noindex,follow and left out of the sitemap, still linked for readers).

Search Console (2026-10-20): most of the 127 municipality pages and 28 week pages were never shown in a search.  A page of the same shape for every municipality or week,
with few records behind it, adds little for a searcher and makes the site look like one table repeated.  What stays indexed:
  - a municipality page that Search Console gave a click or 50 impressions (keep_cities.json), or one with KEEP_BY_RECORDS records or more (rule B, decided 2026-11-09:
    34 of 152 pages; the other 118 had no click in 34 days and read as one table repeated; /live/<prefecture>/ lists every municipality, so the information stays);
  - no week page (2026-11-09): the 9 week pages that were left had 20 impressions and 1 click in 34 days, a text overlap of 0.83 between any two, and the same table every week.
    The pages stay on the site and linked from /digest/; they only ask search engines not to index them (the shared rule then drops the ad script from them).
keep_cities.json lists the pages Search Console showed with a click or 50 impressions; the acquisition routine refreshes it.  demand.json is no longer read by the build.
"""
from __future__ import annotations

import json
from pathlib import Path

from sites.kuma import live as live_mod

KEEP_BY_RECORDS = live_mod.KEEP_BY_RECORDS        # a municipality page exists only with this many records, or when keep_cities.json lists it

_KEEP = json.loads((Path(__file__).with_name("keep_cities.json")).read_text(encoding="utf-8"))
_DEMAND = json.loads((Path(__file__).with_name("demand.json")).read_text(encoding="utf-8"))      # kept for the acquisition routine's refresh; not read by the build


def city_hash(slug: str, city: str) -> str:
    return live_mod.city_slug(slug, city)[2:]


def city_is_thin(slug: str, city: str, rows: list) -> bool:
    return city_hash(slug, city) not in _KEEP["cities"] and len(rows) < KEEP_BY_RECORDS


live_mod.PAGE_RULE = lambda slug, city, rows: not city_is_thin(slug, city, rows)     # a thin municipality has no page: it is listed on its prefecture page and its old URL redirects (301)


PREF_MIN_SIGHTINGS = 10      # a prefecture page whose last full year AND whose year so far are both under this many sightings asks not to be indexed (the page stays, like Chiba's)


def pref_is_thin(d: dict, r: dict) -> bool:
    """A prefecture with almost no sightings (2026-11-09: Ibaraki, Ehime, Kagawa, Kochi, Tokushima): nothing of its own can be said, and its readers (no click in 34 days) are served by the
    page staying on the site.  It returns to the index by itself when the counts reach PREF_MIN_SIGHTINGS."""
    return bool(r["has"]) and r["total"][d["done"]] < PREF_MIN_SIGHTINGS and (r["ytd"][d["cur"]] or 0) < PREF_MIN_SIGHTINGS


def thin_weeks(weeks: list[str]) -> set[str]:
    """weeks: the week keys (as digest.build lists them).  Every week page is noindex: they are all of one shape and were almost never shown in a search."""
    return set(weeks)
