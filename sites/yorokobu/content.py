"""The editorial data of よろこぶプレゼント: occasions, recipients, occasion x recipient pairs and the product filters.

The JSON files live in sites/yorokobu/content/.  `load` checks every cross reference so a typo in a slug fails the
build instead of producing a broken page.
"""
from __future__ import annotations

import json
from pathlib import Path

from sokuhou.sitekit import BuildError

HERE = Path(__file__).resolve().parent
CONTENT_DIR = HERE / "content"

OCCASION_FIELDS = ("slug", "name", "blurb", "season", "timing", "tips", "avoid")
RECIPIENT_FIELDS = ("slug", "name", "blurb", "likes", "avoid", "keyword")
PAIR_FIELDS = ("occasion", "recipient", "title", "lead", "reasons", "how_to_choose", "queries", "tiers")
FILTER_FIELDS = ("min_review_count", "min_review_average", "ng_words", "max_per_list", "tiers")


def pair_key(p: dict) -> str:
    return f"{p['occasion']}-{p['recipient']}"


def _read(content_dir: Path, name: str) -> dict:
    path = content_dir / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BuildError(f"missing content file: {path}") from None
    except json.JSONDecodeError as e:
        raise BuildError(f"{name} is not valid JSON: {e}") from None


def _need(entry: dict, fields: tuple, where: str) -> None:
    missing = [f for f in fields if f not in entry or entry[f] in (None, "", [])]
    if missing:
        raise BuildError(f"{where}: missing {', '.join(missing)}")


STOP = ("プレゼント", "ギフト", "贈り物", "祝い", "誕生日", "母の日", "父の日")


def _fallback_ideas(p: dict) -> list[dict]:
    """Until ideas.json has this page: one idea per search query, labelled with the query's last word, reasoned by the page's own reasons."""
    out = []
    for i, q in enumerate(p["queries"]):
        words = [w for w in q.split() if w not in STOP]
        label = words[-1] if words else q
        out.append({"label": label[:12], "type": "実用品", "query": q, "why": p["reasons"][min(i, len(p["reasons"]) - 1)]})
    return out


def load(content_dir: Path = CONTENT_DIR) -> dict:
    occasions = _read(content_dir, "occasions.json")["occasions"]
    recipients = _read(content_dir, "recipients.json")["recipients"]
    pairs = _read(content_dir, "pairs.json")["pairs"]
    filters = _read(content_dir, "filters.json")
    _need(filters, FILTER_FIELDS, "filters.json")
    for o in occasions:
        _need(o, OCCASION_FIELDS, f"occasion {o.get('slug')}")
    for r in recipients:
        _need(r, RECIPIENT_FIELDS, f"recipient {r.get('slug')}")
    occ = {o["slug"]: o for o in occasions}
    rec = {r["slug"]: r for r in recipients}
    tiers = {t["slug"]: t for t in filters["tiers"]}
    if len(occ) != len(occasions) or len(rec) != len(recipients):
        raise BuildError("duplicate occasion or recipient slug")
    seen = set()
    for p in pairs:
        _need(p, PAIR_FIELDS, f"pair {p.get('occasion')}-{p.get('recipient')}")
        key = pair_key(p)
        if key in seen:
            raise BuildError(f"duplicate pair {key}")
        seen.add(key)
        if p["occasion"] not in occ:
            raise BuildError(f"pair {key}: unknown occasion")
        if p["recipient"] not in rec:
            raise BuildError(f"pair {key}: unknown recipient")
        for t in p["tiers"]:
            if t not in tiers:
                raise BuildError(f"pair {key}: unknown tier {t}")
    ideas_file = content_dir / "ideas.json"
    ideas = json.loads(ideas_file.read_text(encoding="utf-8")) if ideas_file.exists() else {}
    for p in pairs:
        extra = ideas.get(pair_key(p))
        p["ideas"] = extra["ideas"] if extra and extra.get("ideas") else _fallback_ideas(p)
        p["keywords"] = extra["keywords"] if extra and extra.get("keywords") else [w for q in p["queries"] for w in [" ".join(x for x in q.split() if x not in STOP)] if w]
    return {"occasions": occasions, "recipients": recipients, "pairs": pairs, "filters": filters,
            "occ": occ, "rec": rec, "tiers": tiers}
