"""Helpers for the person (or routine) who writes the day's picks: find candidates, read a Rakuten product page as text.

    python -m sites.yorokobu.pickresearch candidates [--n 40]      Rakuten candidates from the stored ranking data (not used in the last 30 days)
    python -m sites.yorokobu.pickresearch featurable [YYYY-MM-DD]    the day's entries (r1.. a1..) for the deep-read article, each marked 記事済み when the product has an article already
    python -m sites.yorokobu.pickresearch page <item code> [...]   save the product page's visible text to work/picks/<code>.txt and print its key lines

The Amazon side is read in a real browser (see FACTORY_PLAYBOOK.md, 「毎日のおすすめ」): search pages and /dp/<ASIN> pages are fetched with `fetch()` from a tab that is
on amazon.co.jp.  Nothing here writes to the site: the day's file (content/daily/YYYY-MM-DD.json) is written by hand and has to pass dailypicks.problems.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import dailypicks as dp  # noqa: E402
from sites.yorokobu import features as feats  # noqa: E402

WORK = ROOT.parent / "sokuhou-sites" / "work" / "picks"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
KEY_LINES = re.compile(r"内容量|賞味期限|消費期限|保存方法|サイズ|重量|原材料|アレルゲン|アレルギー|のし|ラッピング|包装|配送|送料|素材|容量|対象年齢|産地|製造者|販売者|名称|冷凍|冷蔵|常温|総合評価|評価 ")


def visible_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|dt|dd|table)>", "\n", raw)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t　]+", " ", t)).strip()


def fetch_page(url: str) -> str:
    """The page's text.  Rakuten's item pages are EUC-JP: the charset is read from the page itself."""
    body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"}), timeout=40).read()
    m = re.search(rb"charset=([A-Za-z0-9_\-]+)", body[:3000])
    enc = {"euc-jp": "euc_jp", "shift_jis": "cp932", "x-sjis": "cp932"}.get((m.group(1).decode() if m else "utf-8").lower(), (m.group(1).decode() if m else "utf-8").lower())
    return visible_text(body.decode(enc, "ignore"))


def item_url(code: str, ranking: dict) -> str | None:
    for seg in ranking["segments"].values():
        for it in seg["items"]:
            if it["code"] == code:
                return it["url"].split("?")[0]
    for items in sources().values():                      # not in the ranking: the shortlist and the pages know it too
        for it in items:
            if it.get("code") == code and it.get("url"):
                return it["url"].split("?")[0]
    return None


def featured() -> dict[str, str]:
    """{product code or ASIN: slug} of the deep-read articles that exist."""
    return feats.featured_codes(_features(), dp.load_days())


def _features() -> list[dict]:
    d = ROOT / "sites" / "yorokobu" / "content" / "features"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []


def featurable(day_iso: str | None = None) -> list[tuple[str, str, str]]:
    """[(ref, product code or ASIN, 記事済み: slug | '')] for the entries of a day (the newest by default)."""
    days = dp.load_days()
    day = next((x for x in days if x["date"] == day_iso), days[0] if not day_iso else None)
    if not day:
        return []
    done = feats.featured_codes(_features(), days)
    rows = [(f"r{i}", e["code"]) for i, e in enumerate(day["rakuten"], 1)] + [(f"a{i}", e["asin"]) for i, e in enumerate(day["amazon"], 1)]
    return [(ref, key, f"記事済み: {done[key]}" if key in done else "") for ref, key in rows]


MIN_PRICE, MIN_REVIEWS, MIN_RATING = 900, 20, 4.4
DEFAULT_POOL = 80                      # the pool after the exclusions should not be smaller than this
WINDOWS = (30, 21, 14, 7)              # days a product rests after it was a pick; shortened step by step when the pool is too small


def _json(name: str, root: Path | None = None):
    f = (root or ROOT / "data") / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def sources(root: Path | None = None) -> dict[str, list[dict]]:
    """The products the next picks can come from, by source, each with a `genre` (what a round-robin spreads over).  All of it comes from the private store's files (data/, never
    the repository): the sales ranking by genre and by age and sex, the editors' shortlist of the theme and recipient searches (yorokobu_candidates.json), and the products of the
    pages (yorokobu_items.json).  A file that is not there is a source with nothing in it."""
    out: dict[str, list[dict]] = {"ranking-genre": [], "ranking-people": [], "candidates": [], "pages": []}
    rk = _json("yorokobu_ranking.json", root)
    for slug, seg in ((rk or {}).get("segments") or {}).items():
        name = "ranking-genre" if seg.get("kind") == "genre" else "ranking-people"
        out[name] += [{**it, "genre": seg["label"], "rank": i} for i, it in enumerate(seg.get("items") or [])]
    cd = _json("yorokobu_candidates.json", root)
    for key, lists in ((cd or {}).get("pairs") or {}).items():
        for i, lst in enumerate(lists if isinstance(lists, list) else []):
            out["candidates"] += [{**it, "genre": f"{key}#{i}", "rank": j} for j, it in enumerate(lst or [])]
    its = _json("yorokobu_items.json", root)
    for key, v in ((its or {}).get("pairs") or {}).items():
        for i, idea in enumerate(v.get("ideas") or []):
            out["pages"] += [{**it, "genre": f"{key}#{i}", "rank": j} for j, it in enumerate(idea.get("items") or [])]
    return out


def used_codes(days: int, today: date | None = None) -> set[str]:
    """The Rakuten codes of the daily files of the last `days` days, and every product that has a deep-read article."""
    today = today or date.today()
    used: set[str] = set()
    for d in dp.load_days():
        if date.fromisoformat(d["date"]) >= today - timedelta(days=days):
            used |= {e["code"] for e in d["rakuten"]}
    return used | set(featured())


def pool(src: dict[str, list[dict]], used: set[str]) -> tuple[list[dict], dict[str, int]]:
    """(the products to choose from, spread round by round over the genres and sources so that one genre does not fill the list; counts by source before and after the exclusions)."""
    counts = {k: [0, 0] for k in src}
    seen: set[str] = set()
    cand: dict[str, list[dict]] = {}
    for name, items in src.items():
        for it in items:
            if it.get("price", 0) < MIN_PRICE or it.get("reviews", 0) < MIN_REVIEWS or it.get("rating", 0) < MIN_RATING or not it.get("code"):
                continue
            counts[name][0] += 1
            if it["code"] in used or it["code"] in seen:
                continue
            seen.add(it["code"])
            counts[name][1] += 1
            cand.setdefault(f"{name}|{it['genre']}", []).append({**it, "src": name})
    rows = [sorted(v, key=lambda x: x.get("rank", 0)) for v in cand.values()]
    out = []
    for rnd in range(max((len(r) for r in rows), default=0)):
        for r in rows:
            if rnd < len(r):
                out.append(r[rnd])
    return out, {k: f"{v[0]} -> {v[1]}" for k, v in counts.items()}


def candidates(n: int, days: int = 30, root: Path | None = None, today: date | None = None, min_pool: int = DEFAULT_POOL) -> list[dict]:
    """About `n` products for the next picks.  The rest period after a pick starts at `days` and is shortened (WINDOWS) while fewer than `min_pool` products are left; the window used and
    the counts by source are printed to stderr.  2026-11-02: the ranking by genre alone gave 53 products after the 30 days, bunched in wedding, wine and baby goods."""
    src = sources(root)
    chosen = days
    for w in [days] + [x for x in WINDOWS if x < days]:
        chosen = w
        out, counts = pool(src, used_codes(w, today))
        if len(out) >= min_pool:
            break
    print(f"candidates: rest {chosen} days; pool {len(out)}; by source (usable -> after exclusions): {counts}", file=sys.stderr)
    return out[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--n", type=int, default=60)
    c.add_argument("--days", type=int, default=30)
    f = sub.add_parser("featurable")
    f.add_argument("day", nargs="?")
    g = sub.add_parser("page")
    g.add_argument("codes", nargs="+")
    a = ap.parse_args()
    if a.cmd == "candidates":
        for it in candidates(a.n, a.days):
            print(f'{it["code"]} | {it["src"]}:{it["genre"]} | {it["name"][:56]} | {it["price"]}円 ★{it["rating"]} ({it["reviews"]}件) | {it["shop"][:12]}')
        return
    if a.cmd == "featurable":
        for ref, key, mark in featurable(a.day):
            print(f"{ref:4} {key:28} {mark}")
        return
    ranking = json.loads((ROOT / "data" / "yorokobu_ranking.json").read_text(encoding="utf-8"))
    WORK.mkdir(parents=True, exist_ok=True)
    for code in a.codes:
        url = item_url(code, ranking)
        if not url:
            print(code, "not in the stored ranking data (give the item page URL to fetch_page instead)")
            continue
        text = fetch_page(url)
        (WORK / (code.replace(":", "_") + ".txt")).write_text(text, encoding="utf-8")
        print(f"===== {code} {url} ({len(text)} chars)")
        print("\n".join(l.strip()[:200] for l in text.splitlines() if KEY_LINES.search(l))[:3500])


if __name__ == "__main__":
    main()
