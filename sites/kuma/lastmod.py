"""The sitemap's <lastmod> of every page of the bear site: the day the page's own data last changed, not the day it was built.

A search engine (and IndexNow, which sends the URLs whose lastmod changed) treats lastmod as "this page changed on that day", so it must not be the build date.

  data pages   the newest date of the data the page shows (the ministry's publication dates; the newest record of a municipal source; the end of a digest week)
  static pages guides, about, privacy, contact, notify, goods: the day their text last changed.  A hash of the page's <main> is kept in
               sites/kuma/lastmod_static.json together with that day; a page whose text differs from the stored hash gets today's date (the build
               prints which pages) until `python sites/kuma/build.py --update-lastmod` is run and the file is committed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

from sites.kuma import digest
from sites.kuma.live import city_has_page, city_url

STATIC_FILE = Path(__file__).resolve().parent / "lastmod_static.json"
STATIC_PATHS = ("about/", "privacy/", "contact/", "notify/", "goods/")
STATIC_PREFIXES = ("guide/",)


def is_static(rel: str) -> bool:
    d = rel[: -len("index.html")] if rel.endswith("index.html") else rel
    return d in STATIC_PATHS or d.startswith(STATIC_PREFIXES)


def main_hash(html: str) -> str:
    main = html.split("<main", 1)[1].split("</main>", 1)[0] if "<main" in html else html
    return hashlib.sha256(re.sub(r"\s+", " ", main).encode("utf-8")).hexdigest()[:16]


def load_static() -> dict:
    return json.loads(STATIC_FILE.read_text(encoding="utf-8")) if STATIC_FILE.exists() else {}


def emergency_date(d: dict) -> str | None:
    emg = d["emergency"].get(d["cur"]) if isinstance(d.get("emergency"), dict) else None
    if isinstance(emg, str):
        return emg
    return emg.get("updated") if isinstance(emg, dict) else None


def ministry_date(d: dict) -> str:
    """The newest of the ministry's dates the pages use (sightings, injuries, emergency shootings, the notices, the captures table)."""
    out = [d["sight_updated"], d["inj_updated"]]
    if emergency_date(d):
        out.append(emergency_date(d))
    out += [x["date"] for x in d.get("notices", [])[:1]]
    cap = d.get("captures")
    if isinstance(cap, dict) and cap.get("updated"):
        out.append(cap["updated"])
    return max(out)


def live_dates(lv: dict | None) -> tuple[dict[str, str], dict[str, str]]:
    """({prefecture slug: newest record date of the sources shown for it}, {municipality page path: newest record of that municipality})."""
    pref: dict[str, str] = {}
    city: dict[str, str] = {}
    if not lv:
        return pref, city
    for r in lv["records"]:
        pref[r["slug"]] = max(pref.get(r["slug"], ""), r["at"][:10])
    for c in lv["counts"]:
        pref[c["slug"]] = max(pref.get(c["slug"], ""), c["latest"])
    for slug, cities in lv["by_pref"].items():
        for name, rows in cities.items():
            if city_has_page(rows):
                city[city_url(slug, name)] = rows[0]["at"][:10]
    return pref, city


def compute(pages: dict, d: dict, lv: dict | None, today: date, stored: dict | None = None) -> tuple[dict[str, str], list[str]]:
    """({url path: ISO date}, [static pages whose text differs from the stored hash]) for every index.html of `pages`."""
    stored = load_static() if stored is None else stored
    mins = ministry_date(d)
    pref, city = live_dates(lv)
    live_all = max(pref.values(), default="")
    changed: list[str] = []
    out: dict[str, str] = {}
    for rel in pages:
        if not rel.endswith("index.html"):
            continue
        url = "/" + rel[: -len("index.html")]
        parts = url.strip("/").split("/") if url != "/" else []
        head = parts[0] if parts else ""
        if is_static(rel):
            h = main_hash(pages[rel])
            rec = stored.get(rel)
            if rec and rec.get("hash") == h:
                out[url] = rec["date"]
            else:
                out[url] = today.isoformat()
                changed.append(rel)
        elif not parts:
            out[url] = max(mins, live_all)
        elif head == "live" and len(parts) == 2:
            out[url] = pref.get(parts[1], live_all or mins)
        elif head == "live" and len(parts) >= 3:
            out[url] = city.get(url, pref.get(parts[1], live_all or mins))
        elif head == "live":
            out[url] = live_all or mins
        elif head in ("map", "search"):
            out[url] = live_all or mins
        elif head in ("official", "cite"):
            out[url] = max(live_all, mins)
        elif head == "digest":
            out[url] = (digest.week_start(parts[1]) + timedelta(days=6)).isoformat() if len(parts) > 1 else (live_all or mins)
        elif head == "ranking" and len(parts) > 1 and parts[1] == "injuries":
            out[url] = d["inj_updated"]
        elif head == "ranking" and len(parts) > 1 and parts[1] == "captures":
            out[url] = (d.get("captures") or {}).get("updated", mins)
        elif head == "trend":
            out[url] = max(d["sight_updated"], d["inj_updated"])
        elif head in ("ranking", "season"):
            out[url] = d["sight_updated"]
        elif head == "emergency":
            out[url] = emergency_date(d) or mins
        elif head == "news":
            out[url] = d["notices"][0]["date"] if d.get("notices") else mins
        elif len(parts) == 1 and head in d["by_slug"]:
            out[url] = max(mins, pref.get(head, ""))
        else:
            out[url] = mins
    return out, changed


def apply(sitemap: str, dates: dict[str, str], base: str) -> str:
    """Rewrite every <lastmod> of the sitemap with the page's own date (a page without a date keeps what it had)."""
    def one(m: re.Match) -> str:
        loc = m.group(1)
        path = loc[len(base):] if loc.startswith(base) else loc
        return f"<url><loc>{loc}</loc><lastmod>{dates.get(path, m.group(2))}</lastmod></url>"
    return re.sub(r"<url><loc>([^<]+)</loc><lastmod>([^<]+)</lastmod></url>", one, sitemap)


def update_static(pages: dict, today: date, path: Path = STATIC_FILE) -> list[str]:
    """Rewrite the stored hashes: a page whose text changed gets today's date.  Returns the pages that changed."""
    stored = load_static() if path == STATIC_FILE else (json.loads(path.read_text(encoding="utf-8")) if path.exists() else {})
    new, changed = {}, []
    for rel in sorted(pages):
        if rel.endswith("index.html") and is_static(rel):
            h = main_hash(pages[rel])
            old = stored.get(rel)
            if old and old.get("hash") == h:
                new[rel] = old
            else:
                new[rel] = {"hash": h, "date": today.isoformat()}
                changed.append(rel)
    path.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return changed
