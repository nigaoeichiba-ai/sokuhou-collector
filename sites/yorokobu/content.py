"""The editorial data of よろこぶプレゼント: occasions, recipients, occasion x recipient pairs and the product filters.

The JSON files live in sites/yorokobu/content/.  `load` checks every cross reference so a typo in a slug fails the
build instead of producing a broken page.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sokuhou.sitekit import BuildError

HERE = Path(__file__).resolve().parent
CONTENT_DIR = HERE / "content"

OCCASION_FIELDS = ("slug", "name", "blurb", "season", "timing", "tips", "avoid")
RECIPIENT_FIELDS = ("slug", "name", "blurb", "likes", "avoid", "keyword")
PAIR_FIELDS = ("occasion", "recipient", "title", "lead", "reasons", "how_to_choose", "queries", "tiers")
FILTER_FIELDS = ("min_review_count", "min_review_average", "ng_words", "max_per_list", "tiers")


THEME_GROUPS = [
    {"slug": "feeling", "name": "気持ちから選ぶ", "blurb": "感謝を伝えたい、外したくない、記憶に残したい。贈りたい気持ちから、プレゼントを探します。", "icon": "heart"},
    {"slug": "giver", "name": "贈る側から選ぶ", "blurb": "男性から、女性から。もらってうれしいものを、贈る側の立場から探します。", "icon": "gift"},
    {"slug": "interest", "name": "相手の興味から選ぶ", "blurb": "美容、料理、アウトドア、推し活。相手の好きなことや気になることから、プレゼントを探します。", "icon": "star"},
]
THEME_FIELDS = ("slug", "group", "name", "title", "lead", "reasons", "how_to_choose", "ideas", "keywords", "tiers")


def pair_key(p: dict) -> str:
    """The page key: occasion-recipient for a pair page, theme-<slug> for a theme page (which carries its own key)."""
    return p.get("key") or f"{p['occasion']}-{p['recipient']}"


def pages(c: dict) -> list[dict]:
    """Every page that shows products: the occasion x recipient pairs, then the theme pages."""
    return c["pairs"] + c.get("themes", [])


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
    guides_file = content_dir / "guides.json"
    guides = {g["occasion"]: g for g in json.loads(guides_file.read_text(encoding="utf-8"))["guides"]} if guides_file.exists() else {}
    for slug, g in guides.items():
        if slug not in occ:
            raise BuildError(f"guide for unknown occasion {slug}")
    groups = _load_groups(content_dir)
    themes = _load_themes(content_dir, rec, tiers, {g["slug"] for g in groups})
    theme = {t["slug"]: t for t in themes}
    articles = _load_articles(content_dir, theme)
    messages = _load_messages(content_dir, occ)
    etiquette = _load_etiquette(content_dir, occ)
    amazon, amazon_checked = _load_amazon(content_dir, occ, rec)
    return {"messages": messages, "etiquette": etiquette, "amazon": amazon, "amazon_checked": amazon_checked, "occasions": occasions, "recipients": recipients, "pairs": pairs, "filters": filters,
            "occ": occ, "rec": rec, "tiers": tiers, "guides": guides, "themes": themes,
            "theme": theme, "theme_groups": groups, "articles": articles,
            "stats": _load_stats(content_dir), "taboo": _load_taboo(content_dir), "persona": _load_persona(content_dir, theme), "map_tags": _load_map_tags(content_dir)}


def _load_stats(content_dir: Path) -> dict:
    """The outside numbers of the data room (stats.json, optional): public statistics and one survey, each with its source.  A table that does not add up
    (survey shares that are not 100%, a year without a number) is refused: a chart built on it would look exact and be wrong."""
    data = _optional(content_dir, "stats.json") or {}
    for key, v in data.get("vital", {}).items():
        _need(v, ("label", "unit", "series", "source", "url"), f"stats vital {key}")
        if not v["url"].startswith("https://") or any(not isinstance(n, int) or n <= 0 for n in v["series"].values()):
            raise BuildError(f"stats vital {key}: a bad url or a number that is not a positive integer")
    for key, v in data.get("survey_budget", {}).items():
        _need(v, ("title", "source", "url", "method", "bands", "years", "checked"), f"stats survey {key}")
        for year, shares in v["years"].items():
            if len(shares) != len(v["bands"]) or abs(sum(shares) - 100) > 1.5:
                raise BuildError(f"stats survey {key} {year}: the shares do not add up to 100% ({sum(shares):.1f})")
    return data


def _load_messages(content_dir: Path, occ: dict) -> dict:
    """Message examples per occasion (messages.json, optional): {occasion slug: entry}."""
    data = _optional(content_dir, "messages.json")
    out: dict = {}
    for m in (data or {}).get("messages", []):
        _need(m, ("occasion", "intro", "sets", "manners", "closing"), f"messages {m.get('occasion')}")
        if m["occasion"] not in occ:
            raise BuildError(f"messages for unknown occasion {m['occasion']}")
        if m["occasion"] in out:
            raise BuildError(f"duplicate messages for {m['occasion']}")
        for s in m["sets"]:
            _need(s, ("to", "style", "lines"), f"messages {m['occasion']} set")
        out[m["occasion"]] = m
    return out


ETIQUETTE_RANGE = re.compile(r"[0-9][0-9,]*(〜[0-9][0-9,]*)?円(以上|以内)?")
ETIQUETTE_CONFIDENCE = ("high", "medium", "low")


def _load_etiquette(content_dir: Path, occ: dict) -> dict:
    """The 'before you give' sheet per occasion (etiquette.json, optional): amounts by relation, timing, noshi, cautions, and the sources they come from.
    An amount is published only with two sources, and never at low confidence: a wrong figure on a manners page is worse than none."""
    data = _optional(content_dir, "etiquette.json")
    out: dict = {}
    for e in (data or {}).get("occasions", []):
        slug = e.get("slug")
        _need(e, ("slug", "timing", "noshi", "cautions", "confidence", "sources"), f"etiquette {slug}")
        if slug not in occ:
            raise BuildError(f"etiquette for unknown occasion {slug}")
        if slug in out:
            raise BuildError(f"duplicate etiquette for {slug}")
        if e["confidence"] not in ETIQUETTE_CONFIDENCE:
            raise BuildError(f"etiquette {slug}: confidence must be one of {ETIQUETTE_CONFIDENCE}")
        if "applicable" not in e["noshi"]:
            raise BuildError(f"etiquette {slug}: noshi needs applicable (true or false)")
        if e["noshi"]["applicable"] and not (e["noshi"].get("omote") and e["noshi"].get("mizuhiki")):
            raise BuildError(f"etiquette {slug}: noshi needs omote and mizuhiki")
        budget = e.get("budget") or []
        for r in budget:
            _need(r, ("to", "range"), f"etiquette {slug} budget")
            if not ETIQUETTE_RANGE.fullmatch(r["range"]):
                raise BuildError(f"etiquette {slug}: amount '{r['range']}' is not like 5,000〜10,000円")
        if budget and e["confidence"] == "low":
            raise BuildError(f"etiquette {slug}: an amount needs medium or high confidence")
        if not budget and not e.get("budget_note"):
            raise BuildError(f"etiquette {slug}: no amount and no budget_note")
        if len(e["sources"]) < 2 or any(not (s.get("name") and str(s.get("url", "")).startswith("https://")) for s in e["sources"]):
            raise BuildError(f"etiquette {slug}: at least two sources with a name and an https url")
        out[slug] = e
    return out


ASIN = re.compile(r"[A-Z0-9]{10}")


def _load_amazon(content_dir: Path, occ: dict, rec: dict) -> tuple[list[dict], str]:
    """Hand-picked Amazon products (amazon_picks.json, optional): shown as a text card with a link, never with a price or a picture."""
    data = _optional(content_dir, "amazon_picks.json")
    out: list[dict] = []
    seen: set[str] = set()
    for p in (data or {}).get("picks", []):
        _need(p, ("asin", "name", "maker", "kind", "occasions", "why", "source"), f"amazon pick {p.get('asin')}")
        if not ASIN.fullmatch(p["asin"]) or p["asin"] in seen:
            raise BuildError(f"amazon pick {p['asin']}: a bad or repeated ASIN")
        seen.add(p["asin"])
        bad = [o for o in p["occasions"] if o not in occ] + [r for r in p.get("recipients", []) if r not in rec]
        if bad:
            raise BuildError(f"amazon pick {p['asin']}: unknown occasion or recipient {bad}")
        if "円" in p["why"] or "¥" in p["why"] or "￥" in p["why"]:
            raise BuildError(f"amazon pick {p['asin']}: no price in the text (a price may only come from Amazon's API)")
        out.append(p)
    return out, (data or {}).get("checked", "")


def _optional(content_dir: Path, name: str):
    return _read(content_dir, name) if (content_dir / name).exists() else None


def _load_taboo(content_dir: Path) -> list[dict]:
    data = _optional(content_dir, "taboo.json")
    entries = data["entries"] if data else []
    ids = set()
    for e in entries:
        _need(e, ("id", "names", "level", "title", "why", "tip"), f"taboo {e.get('id')}")
        if e["level"] not in ("care", "note", "ok"):
            raise BuildError(f"taboo {e['id']}: unknown level {e['level']}")
        if e["id"] in ids:
            raise BuildError(f"duplicate taboo {e['id']}")
        ids.add(e["id"])
        e.setdefault("avoid_for", [])
        e.setdefault("alternatives", [])
    return entries


def _load_persona(content_dir: Path, theme: dict) -> dict | None:
    data = _optional(content_dir, "persona.json")
    if not data:
        return None
    slugs = {p["slug"] for p in data["personas"]}
    for p in data["personas"]:
        _need(p, ("slug", "name", "tagline", "about", "likes", "avoid", "themes", "line"), f"persona {p.get('slug')}")
        bad = [s for s in p["themes"] if theme and s not in theme]
        if bad:
            raise BuildError(f"persona {p['slug']}: unknown theme {bad}")
    for q in data["questions"]:
        for o in q["options"]:
            if any(s not in slugs for s in o["w"]):
                raise BuildError(f"question {q['id']}: weight for an unknown persona")
    return data


def _load_map_tags(content_dir: Path) -> dict:
    data = _optional(content_dir, "map_tags.json")
    if not data:
        return {}
    for k, dots in data.items():
        if any(len(d) != 2 or not all(-2 <= float(v) <= 2 for v in d) for d in dots):
            raise BuildError(f"map_tags {k}: dots must be [x, y] within -2..2")
    return data


def _load_groups(content_dir: Path) -> list[dict]:
    """The theme groups: THEME_GROUPS plus any the content factory added in content/theme_groups.json."""
    extra = _optional(content_dir, "theme_groups.json")
    groups = list(THEME_GROUPS)
    for g in (extra or {}).get("groups", []):
        _need(g, ("slug", "name", "blurb"), f"theme group {g.get('slug')}")
        if g["slug"] in {x["slug"] for x in groups}:
            raise BuildError(f"duplicate theme group {g['slug']}")
        groups.append(g)
    return groups


def _load_articles(content_dir: Path, theme: dict) -> list[dict]:
    """Free-form reading articles (articles.json, optional), newest first."""
    data = _optional(content_dir, "articles.json")
    arts = (data or {}).get("articles", [])
    seen = set()
    for a in arts:
        _need(a, ("slug", "title", "lead", "sections", "faq", "themes", "date"), f"article {a.get('slug')}")
        if a["slug"] in seen:
            raise BuildError(f"duplicate article {a['slug']}")
        seen.add(a["slug"])
        bad = [s for s in a["themes"] if theme and s not in theme]
        if bad:
            raise BuildError(f"article {a['slug']}: unknown theme {bad}")
        a.setdefault("checklist", [])
    return sorted(arts, key=lambda a: (a["date"], a["slug"]), reverse=True)


def _load_themes(content_dir: Path, rec: dict, tiers: dict, group_slugs: set[str] | None = None) -> list[dict]:
    """The theme pages (themes.json, optional): a page that starts from a feeling or an interest instead of an occasion x recipient."""
    path = content_dir / "themes.json"
    if not path.exists():
        return []
    themes = _read(content_dir, "themes.json")["themes"]
    groups = group_slugs or {g["slug"] for g in THEME_GROUPS}
    seen = set()
    for t in themes:
        _need(t, THEME_FIELDS, f"theme {t.get('slug')}")
        if t["slug"] in seen:
            raise BuildError(f"duplicate theme {t['slug']}")
        seen.add(t["slug"])
        if t["group"] not in groups:
            raise BuildError(f"theme {t['slug']}: unknown group {t['group']}")
        if t.get("recipient") and t["recipient"] not in rec:
            raise BuildError(f"theme {t['slug']}: unknown recipient")
        for x in t["tiers"]:
            if x not in tiers:
                raise BuildError(f"theme {t['slug']}: unknown tier {x}")
        t["key"] = f"theme-{t['slug']}"
        t["recipient"] = t.get("recipient") or None
        t.setdefault("avoid", [])
    return themes
