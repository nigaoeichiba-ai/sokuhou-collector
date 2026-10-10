"""今日のおすすめギフト: every day a page of 10 products from Rakuten and 10 from Amazon, each with its own text.

The text of a day is content/daily/YYYY-MM-DD.json.  It is written from what was read on the product page, in the makers' public information and in the buyers'
voices (as tendencies, in the editors' own words: nothing is quoted).  `problems` is the gate that a day has to pass before it is committed, and again at every
build: a wrong day stops the build instead of publishing.

Rakuten products show their price, rating and picture from Rakuten's API (looked up again at every refresh by sites/yorokobu/refresh.py).  Amazon products have
no price and no picture of the product (Associates rules): the picture is a mood image (assets/mood/*.webp, made by Codex) that says so on the card.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from sites.yorokobu import quality

HERE = Path(__file__).resolve().parent
DAILY_DIR = HERE / "content" / "daily"
RAKUTEN_N = AMAZON_N = 10
KIND_KEY = {"実用品": "practical", "食べもの・飲みもの": "food", "ファッション小物": "fashion", "癒し・リラックス": "relax", "思い出・名入れ": "memory",
            "体験・お出かけ": "outing", "趣味・ホビー": "hobby", "おもしろ・サプライズ": "surprise", "子ども向け": "kids"}
MOOD_VARIANTS = 2
COPY_RUN = 14          # a stretch of this many characters shared with the shop's page counts as copied
# claims a shop may make and an editor may not: absolute words, medical effects, "the most", and the hype of an advertisement
BANNED = ["絶対", "必ず", "No.1", "No１", "ナンバーワン", "最安", "日本一", "世界一", "最高", "完璧", "全員", "誰でも", "間違いなく", "大人気", "爆売れ", "話題の",
          "効果", "効く", "治る", "改善", "若返", "痩せ", "予防", "デトックス", "口コミで"]
TEXT_FIELDS = {"headline": (12, 42), "summary": (60, 170), "good": (40, 150), "care": (30, 130), "scene": (4, 30)}
LABEL = {"good": "いいところ", "care": "気になるところ"}


def _blob(e: dict) -> str:
    return "。".join([e["headline"], e["summary"], e["good"], e["care"], e["scene"], *e["for"], *e["check"]])


def shingles(text: str, n: int = 10) -> set[str]:
    t = re.sub(r"[\s、。,.!?!?「」『』()()\-/・]", "", text)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def copied(text: str, source: str, n: int = 10) -> bool:
    """True when `text` repeats a stretch of `n` characters of `source` (a shop's title or description): the editors' words must be their own."""
    return bool(shingles(text, n) & shingles(source, n))


def problems(day: dict, sources: dict[str, str] | None = None, sizes: tuple[int, int] = (RAKUTEN_N, AMAZON_N)) -> list[str]:
    """Everything wrong with one day's file (empty = it can be published).  `sources` maps an entry id (r1 ... / a1 ...) to the shop's own text, when known."""
    out: list[str] = []
    d = day.get("date", "?")
    for f in ("date", "theme", "lede", "highlights", "rakuten", "amazon"):
        if not day.get(f):
            out.append(f"{d}: missing {f}")
    if out:
        return out
    try:
        date.fromisoformat(day["date"])
    except ValueError:
        return [f"{d}: bad date"]
    if not 8 <= len(day["theme"]) <= 40:
        out.append(f"{d}: theme length {len(day['theme'])}")
    if not 90 <= len(day["lede"]) <= 260:
        out.append(f"{d}: lede length {len(day['lede'])}")
    if len(day["rakuten"]) != sizes[0] or len(day["amazon"]) != sizes[1]:
        out.append(f"{d}: {len(day['rakuten'])} Rakuten and {len(day['amazon'])} Amazon products (need {sizes[0]} and {sizes[1]})")
    ids: dict[str, dict] = {}
    for store, rows, prefix in (("rakuten", day["rakuten"], "r"), ("amazon", day["amazon"], "a")):
        for i, e in enumerate(rows, 1):
            eid = f"{prefix}{i}"
            ids[eid] = e
            out += _entry_problems(d, store, eid, e, (sources or {}).get(eid, ""))
    heads = [e["headline"] for e in ids.values() if e.get("headline")]
    if len(set(heads)) != len(heads):
        out.append(f"{d}: two entries share a headline")
    opens = [e["summary"][:10] for e in ids.values() if e.get("summary")]
    if len(set(opens)) != len(opens):
        out.append(f"{d}: two summaries begin the same way")
    hl = day["highlights"]
    if len(hl) != 3 or len({h.get("ref") for h in hl}) != 3 or any(h.get("ref") not in ids or not h.get("tag") for h in hl):
        out.append(f"{d}: highlights need three different entries with a tag")
    out += quality.language_problems(day["lede"] + day["theme"], f"{d} lede")
    out += [f"{d} lede: banned word {w}" for w in BANNED if w in day["lede"] + day["theme"]]
    return out


def _entry_problems(d: str, store: str, eid: str, e: dict, source: str) -> list[str]:
    at = f"{d} {eid}"
    out = []
    need = ("name", "kind", "headline", "summary", "for", "good", "care", "check", "scene", "verified") + (("code", "img", "url") if store == "rakuten" else ("asin", "maker", "mood"))
    miss = [f for f in need if not e.get(f)]
    if miss:
        return [f"{at}: missing {', '.join(miss)}"]
    if e["kind"] not in KIND_KEY:
        out.append(f"{at}: unknown kind {e['kind']}")
    if store == "rakuten" and not re.fullmatch(r"[a-z0-9_\-]+:\d+", e["code"]):
        out.append(f"{at}: bad Rakuten item code {e['code']}")
    if store == "amazon":
        if not re.fullmatch(r"[A-Z0-9]{10}", e["asin"]):
            out.append(f"{at}: bad ASIN")
        if not re.fullmatch(r"[a-z]+-\d", e["mood"]) or e["mood"].split("-")[0] not in KIND_KEY.values():
            out.append(f"{at}: bad mood image {e['mood']}")
    for f, (lo, hi) in TEXT_FIELDS.items():
        if not lo <= len(e[f]) <= hi:
            out.append(f"{at}: {f} is {len(e[f])} characters (need {lo}-{hi})")
    if not 2 <= len(e["for"]) <= 3 or any(not 3 <= len(x) <= 22 for x in e["for"]):
        out.append(f"{at}: 'for' needs 2-3 short phrases")
    if not 1 <= len(e["check"]) <= 4 or any(not 6 <= len(x) <= 60 for x in e["check"]):
        out.append(f"{at}: 'check' needs 1-4 notes of 6-60 characters")
    blob = _blob(e)
    out += [f"{at}: banned word {w}" for w in BANNED if w in blob]
    out += quality.language_problems(blob, at)
    if store == "amazon" and (re.search(r"[0-9,]+円|[0-9]+万円|[¥￥]|[★☆]|[0-9]+(?:\.[0-9])?つ星|レビュー[0-9]|[0-9,万千]+件", blob)):
        out.append(f"{at}: an Amazon text may not carry a price, a rating or a review count (only Amazon's API may)")
    prose = "。".join([e["headline"], e["summary"], e["good"], e["care"]])
    if source and copied(prose, source, COPY_RUN):                 # names and spec lists repeat the page by nature; the editors' sentences must not
        out.append(f"{at}: repeats {COPY_RUN} or more characters of the shop's own text")
    return out


# ---------------------------------------------------------------- files

def load_days(directory: Path = DAILY_DIR) -> list[dict]:
    """Every day file, newest first; a file that fails the gate raises (it must never reach the site)."""
    days = []
    for f in sorted(directory.glob("*.json"), reverse=True) if directory.exists() else []:
        day = json.loads(f.read_text(encoding="utf-8"))
        if day.get("date") != f.stem:
            raise ValueError(f"{f.name}: the date inside is {day.get('date')}")
        bad = problems(day)
        if bad:
            raise ValueError(f"{f.name}: " + "; ".join(bad[:6]))
        days.append(day)
    return days


def rakuten_codes(days: list[dict], limit: int = 45) -> list[str]:
    """The Rakuten item codes of the newest `limit` days (what the daily refresh looks up again)."""
    return [e["code"] for day in days[:limit] for e in day["rakuten"]]


def mood_path(e: dict, position: int = 0) -> str:
    return f"/assets/mood/{e['mood']}.webp"


def pick_mood(kind: str, seed: int) -> str:
    """The mood image key (kind-variant) for an entry of this kind: the variant alternates with `seed` (the entry's place in the day)."""
    return f"{KIND_KEY[kind]}-{seed % MOOD_VARIANTS + 1}"


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        day = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        bad = problems(day)
        print("\n".join(bad) or "OK")
        sys.exit(1 if bad else 0)
    sys.exit("usage: python -m sites.yorokobu.dailypicks check content/daily/YYYY-MM-DD.json")


if __name__ == "__main__":
    main()
