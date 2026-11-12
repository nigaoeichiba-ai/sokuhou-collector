"""Pages that existed and are gone, with where their readers should go (301).

/live/shiga/m-4973b5/ was a page of Otsu city (Shiga).  The city's data turned out to be count-only (no permission to republish the records), so the page was dropped,
but Google had registered it (22 impressions, 2026-10-04 to 11-06) and the server answered 404.  A retired page is not a merged page: the target is the
page of the same prefecture that holds what is still published.
"""
from __future__ import annotations

import json
from pathlib import Path

KNOWN = json.loads(Path(__file__).with_name("known_cities.json").read_text(encoding="utf-8"))["urls"]
RETIRED = {"/live/shiga/m-4973b5/": "/live/shiga/"}
# Fukushima prefecture's count page: the prefecture did not allow its data on an ad-supported site (2026-11-12), so the page is not built (sites/kuma/live.py WITHHELD).
# Unlike RETIRED, this does not stop the build if the page exists again (test builds mock a source of that name); the redirect is written only while the page is absent.
WITHDRAWN = {"/live/fukushima/": "/fukushima/"}


def _rel(url: str) -> str:
    return url.strip("/") + "/index.html"


def redirects(pages: dict) -> dict[str, str]:
    """The redirects to write: those whose target is a page of this build (a build without the Shiga page, as in a test fixture, writes none).
    Refuses a source that is a page again, and a target that is itself redirected."""
    out = {}
    for src, dst in RETIRED.items():
        if _rel(src) in pages:
            raise ValueError(f"retired URL {src} is a page again: remove it from sites/kuma/retired.py")
        if dst in RETIRED:
            raise ValueError(f"retired URL {src} redirects to {dst}, which is itself redirected")
        if _rel(dst) in pages:
            out[src] = dst
    for src, dst in WITHDRAWN.items():
        if _rel(src) not in pages and _rel(dst) in pages:
            out[src] = dst
    # a municipality page that is no longer built (the municipality is not kept) sends its readers to the prefecture's page, which lists it
    for src in KNOWN:
        if _rel(src) in pages or src in out:
            continue
        dst = "/live/" + src.split("/")[2] + "/"
        if _rel(dst) in pages:
            out[src] = dst
    return out


def htaccess_lines(pages: dict) -> str:
    return "".join(f"Redirect 301 {src} {dst}\n" for src, dst in redirects(pages).items())
