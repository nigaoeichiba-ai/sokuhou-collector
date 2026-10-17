"""lexicon: the shared dictionary of wording that is really in use (data/style/lexicon/*.json, made from real texts by the style-corpus research).

Used by sokuhou.styleloop: (1) the reference text handed to the judge ("what people actually write"), (2) a support score for a candidate rewording (does it use the wording
the real texts use, was that confirmed in a source that was really read), (3) the wording the owner has asked us to avoid (a rewording may not bring it back).

A term with strength `weak` (one real text, or only a search summary) is never decisive: it is shown to the judge as such and counts for nothing in the score.
Nothing here changes a text by itself; no network.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "style" / "lexicon"
STRENGTH_JA = {"strong": "強", "medium": "中", "weak": "弱=決め手にしない", "owner": "オーナー"}
SITE_FILES = {"yorokobu": "gift_ja.json", "kuma": "kuma_ja.json", "saichin": "saichin_ja.json", "minna": "minna_ja.json", "atomou": "atomou_ja.json"}
PLACEHOLDER = re.compile(r"[〇〜]|\bXX\b")


def _load(name: str) -> dict:
    try:
        return json.loads((DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=None)
def data(site: str | None) -> dict:
    return _load(SITE_FILES.get(site or "", "")) if site in SITE_FILES else {}


@lru_cache(maxsize=1)
def general() -> dict:
    return _load("general_ja.json")


@lru_cache(maxsize=1)
def sources() -> dict:
    return _load("sources.json").get("sources", {})


def clear_cache() -> None:
    data.cache_clear()
    general.cache_clear()
    sources.cache_clear()


def split_terms(s: str) -> list[str]:
    """'お礼の品 / お礼の品物' -> ['お礼の品', 'お礼の品物'];  a note in brackets and a placeholder (〇〇, 〜) are dropped."""
    out = []
    for part in re.split(r"\s*/\s*", s or ""):
        part = re.sub(r"[(（][^)）]*[)）]", "", part).strip()
        if len(part) >= 2 and not PLACEHOLDER.search(part):
            out.append(part)
    return out


def confirmed(entry: dict) -> bool:
    """Strong or medium, and at least one of its sources was really read (the research marks that in sources.json); the owner's own correction counts."""
    if entry.get("strength") == "owner" or entry.get("status") == "owner":
        return True
    if entry.get("strength") not in ("strong", "medium"):
        return False
    src = sources()
    return any((src.get(e) or {}).get("status") == "read" or e == "owner" for e in entry.get("evidence", []))


def _entries(site: str | None) -> tuple[list[dict], list[dict]]:
    """(preferred terms, avoided wordings) of a site as flat dicts: {term, weight} / {avoid, prefer[], owner}."""
    d = data(site)
    prefer, avoid = [], []
    for p in d.get("people", []):
        for t in p.get("prefer", []):
            prefer += [{"term": x, "confirmed": confirmed(t), "strength": t.get("strength")} for x in split_terms(t.get("term", ""))]
    for t in d.get("things_given", []):
        prefer += [{"term": x, "confirmed": confirmed(t), "strength": t.get("strength")} for x in split_terms(t.get("term", ""))]
    for k in ("terms", "stage_terms", "counting_terms", "calendar_terms"):
        for t in d.get(k, []):
            prefer += [{"term": x, "confirmed": confirmed(t), "strength": t.get("strength")} for x in split_terms(t.get("term", ""))]
    for a in d.get("avoid_to_prefer", []):
        owner = a.get("status") == "owner"
        avoided = [x for x in split_terms(a.get("avoid", "")) if "単独" not in a.get("avoid", "")]
        pref = []
        for x in a.get("prefer", []):
            pref += split_terms(x)
        for ar in avoided:
            avoid.append({"avoid": ar, "prefer": pref, "owner": owner})
        prefer += [{"term": x, "confirmed": owner or bool(a.get("evidence")) and any((sources().get(e) or {}).get("status") == "read" for e in a.get("evidence", [])),
                    "strength": "owner" if owner else "medium"} for x in pref]
    return prefer, avoid


def owner_avoided(site: str | None) -> list[str]:
    """Wordings the owner asked us not to use (a rewording may not bring one back)."""
    return sorted({a["avoid"] for a in _entries(site)[1] if a["owner"]})


def support(site: str | None, text: str) -> int:
    """How well a wording agrees with the real texts: +3 for a term the owner chose, +2 for a confirmed one, +1 for an unconfirmed medium/strong one, 0 for weak (never decisive);
    -3 for a wording that is on the avoid list."""
    prefer, avoid = _entries(site)
    score, seen = 0, set()
    for p in prefer:
        t = p["term"]
        if t in text and t not in seen:
            seen.add(t)
            if p["strength"] == "owner":
                score += 3
            elif p["confirmed"]:
                score += 2
            elif p["strength"] in ("strong", "medium"):
                score += 1
    for a in avoid:
        if a["avoid"] in text:
            score -= 3
    return score


def _tag(entry: dict) -> str:
    return STRENGTH_JA.get(entry.get("strength", ""), "")


def reference(site: str | None, max_chars: int = 7000) -> str:
    """The text for the judge's prompt: what the real texts do, short.  Weak terms are marked as not decisive."""
    lines: list[str] = []
    d = data(site)
    if d:
        if d.get("avoid_to_prefer"):
            lines.append("【避ける言い方 → 実物で使う言い方】(owner=オーナーの訂正。必ず守る)")
            for a in d["avoid_to_prefer"]:
                pick = f"({a['pick_by']})" if a.get("pick_by") else ""
                lines.append(f"- 「{a['avoid']}」→ {' / '.join(a.get('prefer', []))}{pick}" + (" [owner]" if a.get("status") == "owner" else ""))
        if d.get("people"):
            lines.append("【人の呼び方(場面別)】")
            for p in d["people"]:
                lines.append(f"- {p['scene']}: " + " / ".join(f"{t['term']}({_tag(t)})" for t in p.get("prefer", [])))
        if d.get("things_given"):
            lines.append("【贈るものの名詞】(単独の「お礼」「贈り物」は何を指すか曖昧)")
            for t in d["things_given"]:
                lines.append(f"- {t['term']}({_tag(t)}): {t.get('use', '')[:60]}")
        for k, title in (("terms", "語"), ("stage_terms", "段階の語"), ("counting_terms", "数え方の語"), ("calendar_terms", "暦の語")):
            if d.get(k) and site != "yorokobu":
                lines.append(f"【{title}】")
                for t in d[k]:
                    lines.append(f"- {t.get('term', '')}: {t.get('role') or t.get('stage') or ''}"[:110] + (f"({_tag(t)})" if t.get("strength") else ""))
        for w in d.get("word_choices", []):
            lines.append(f"- {w.get('pair', '')}: {w.get('rule_for_site', '')}"[:160])
    g = general()
    if g.get("patterns"):
        lines.append("【AIの文に見える型 → プロ・実物がしていること】(例は自作)")
        for p in g["patterns"]:
            ex = p.get("fix_examples_self_made") or []
            exs = (" 例: 「" + ex[0][0] + "」→「" + ex[0][1] + "」") if ex and len(ex[0]) == 2 else ""
            lines.append(f"- {p['looks_like_ai'][:70]} → {p['what_pros_do'][:70]}{exs}"[:260])
    out = "\n".join(lines)
    return out if len(out) <= max_chars else out[:max_chars].rsplit("\n", 1)[0]
