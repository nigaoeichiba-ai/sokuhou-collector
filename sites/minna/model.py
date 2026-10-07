"""What the build knows about the library: items, series (sets), and the season logic.

Two sources are merged:
  * the original 80 illustrations (catalog.py + src/): they keep their ids and URLs (/illust/<id>/, /category/<slug>/)
  * the factory library (library/<series>/series.json + <id>.webp): new series live at /series/<slug>/
Every item ends up with: id, title, desc, tags, genre, touch, series (slug), path, w, h, added.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE / "library"
LEGACY_ADDED = "2026-10-05"

# the original five categories become series of a genre/touch
LEGACY_GENRE = {"expressions": "shimaenaga", "jobs": "shimaenaga", "seasons": "shimaenaga", "event-icons": "icon", "people-icons": "people"}


def load_legacy(gift_content, build_catalog, categories) -> tuple[list[dict], list[dict]]:
    from PIL import Image
    c = gift_content.load()
    raw = build_catalog({o["slug"]: o["name"] for o in c["occasions"]}, {r["slug"]: r["name"] for r in c["recipients"]})
    items = []
    for it in raw:
        src = HERE / "src" / f"{it['src']}.webp"
        with Image.open(src) as im:
            w, h = im.size
        items.append({"id": it["id"], "title": it["title"], "desc": it["desc"], "tags": it["tags"], "genre": LEGACY_GENRE[it["category"]], "touch": "kawaii",
                      "series": it["category"], "path": src, "w": w, "h": h, "added": LEGACY_ADDED})
    series = []
    for slug, name, desc in categories:
        series.append({"slug": slug, "title": name, "lead": desc, "genre": LEGACY_GENRE[slug], "touch": "kawaii", "tags": [], "season": None,
                       "added": LEGACY_ADDED, "legacy": True, "url": f"/category/{slug}/", "ids": [i["id"] for i in items if i["series"] == slug]})
    return items, series


def load_library() -> tuple[list[dict], list[dict]]:
    items, series = [], []
    for f in sorted(LIBRARY.glob("*/series.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ids = []
        for it in d["items"]:
            p = f.parent / it["file"]
            if not p.exists():
                continue
            items.append({"id": it["id"], "title": it["title"], "desc": it["desc"], "tags": it["tags"], "genre": d["genre"], "touch": d["touch"], "series": d["slug"],
                          "path": p, "w": it["w"], "h": it["h"], "added": d.get("added", LEGACY_ADDED)})
            ids.append(it["id"])
        if ids:
            series.append({"slug": d["slug"], "title": d["title"], "lead": d["lead"], "genre": d["genre"], "touch": d["touch"], "tags": d.get("tags", []),
                           "season": d.get("season"), "added": d.get("added", LEGACY_ADDED), "legacy": False, "url": f"/series/{d['slug']}/", "ids": ids})
    return items, series


def in_season(season: dict | None, today: date, lead_days: int = 0) -> bool:
    """True when `today` (shifted `lead_days` ahead) falls in the {"from": "MM-DD", "to": "MM-DD"} window (the window may wrap over New Year)."""
    if not season:
        return False
    from datetime import timedelta
    d = today + timedelta(days=lead_days)
    key = (d.month, d.day)
    a = tuple(int(x) for x in season["from"].split("-"))
    b = tuple(int(x) for x in season["to"].split("-"))
    return (a <= key <= b) if a <= b else (key >= a or key <= b)


def load_all(gift_content, build_catalog, categories) -> tuple[list[dict], list[dict]]:
    li, ls = load_legacy(gift_content, build_catalog, categories)
    ni, ns = load_library()
    items, series = li + ni, ls + ns
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate item ids: {dup[:5]}")
    slugs = [s["slug"] for s in series]
    if len(slugs) != len(set(slugs)):
        raise ValueError("duplicate series slugs")
    return items, series
