"""Daily refresh of the editors' picks: look every picked product up again, swap in a backup when one is gone, and write the page data.

    python -m sites.yorokobu.refresh --out out/yorokobu_items.json

content/picks.json (chosen by hand by Claude and Codex from data/yorokobu_candidates.json) holds, per page and idea, the product codes to show, each
with a one-line note, plus ordered backups.  A pick that is sold out, gone, no longer fits the rules or lost its image is replaced by the first
backup that is fine; the replacement is logged.  An idea without picks falls back to the keyword search used before curation.
Needs RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import fetch  # noqa: E402
from sites.yorokobu.picking import pick, usable  # noqa: E402
from sokuhou import rakuten  # noqa: E402

MAX_LOOKUP_ERROR_SHARE = 0.05


def lookup(client: rakuten.Client, code: str, state: dict, total: int) -> dict | None:
    """The product with this item code as it is now, or None when Rakuten no longer lists it."""
    try:
        raw = client.search(itemCode=code, hits=1)
    except rakuten.RakutenError as e:
        state["errors"] += 1
        print(f"warning: lookup {code}: {e}", file=sys.stderr)
        if state["errors"] > max(5, MAX_LOOKUP_ERROR_SHARE * total):
            raise
        return None
    for x in raw:
        item = rakuten.normalize(x)
        if item and item["code"] == code:
            return item
    return None


def _queue(sel: dict) -> list[tuple[str, str]]:
    """The picks first, then the backups, as (item code, note)."""
    out = [(x["code"], x.get("note", "")) for x in sel["picks"]]
    for b in sel.get("backups", []):
        out.append((b, "") if isinstance(b, str) else (b["code"], b.get("note", "")))
    return out


def refresh(c: dict, client: rakuten.Client, picks: dict, limit_pairs: int | None = None, now: datetime | None = None) -> dict:
    pairs = c["pairs"][:limit_pairs] if limit_pairs else c["pairs"]
    filters = c["filters"]
    total = sum(len(i.get("picks", [])) for p in pairs for i in picks.get(ct.pair_key(p), [])) or 1
    state = {"errors": 0}
    fallback_state = {"errors": 0}
    replaced, dropped, searched = [], [], 0
    cache: dict[str, dict | None] = {}

    def get(code: str):
        if code not in cache:
            cache[code] = lookup(client, code, state, total)
        return cache[code]

    out_pairs, nonempty = {}, 0
    for p in pairs:
        key = ct.pair_key(p)
        sel_all = picks.get(key, [])
        ideas_out, used = [], set()
        for i, idea in enumerate(p["ideas"]):
            sel = sel_all[i] if i < len(sel_all) else None
            items = []
            if sel:
                wanted = len(sel["picks"])
                for n, (code, note) in enumerate(_queue(sel)):
                    if len(items) >= wanted:
                        break
                    it = get(code)
                    if it and code not in used and usable(it, filters, p["recipient"], relaxed=True):
                        items.append({**it, "note": note} if note else it)
                        used.add(code)
                        if n >= wanted:
                            replaced.append((key, i, code))
                    elif n < wanted:
                        dropped.append((key, i, code))
            if len(items) < 2:  # nothing curated survives (or this idea was never curated): the keyword search fills in
                searched += 1
                found = fetch._search(client, f"{key} idea {i} fallback", fallback_state, 1000, keyword=idea["query"], hits=fetch.HITS)
                more = pick(found, None, filters, limit=4 - len(items), recipient=p["recipient"], exclude=used)
                items += more
                used |= {x["code"] for x in more}
            ideas_out.append({k: idea[k] for k in ("label", "type", "query", "why")} | {"items": items})
        union = [it for idea in ideas_out for it in idea["items"]]
        tiers = {t: pick(union, c["tiers"][t], filters, recipient=p["recipient"]) for t in p["tiers"]}
        out_pairs[key] = {"ideas": ideas_out, "tiers": tiers}
        nonempty += bool(union)
    if pairs and nonempty < fetch.MIN_PAIR_SHARE * len(pairs):
        raise rakuten.RakutenError(f"only {nonempty} of {len(pairs)} pages have any product; not using this refresh")
    portrait = []
    try:
        for x in client.search(shopCode=fetch.PORTRAIT_SHOP, hits=fetch.HITS, availability=1):
            item = rakuten.normalize(x)
            if item:
                portrait.append(item)
    except rakuten.RakutenError as e:
        print(f"warning: portrait shop: {e}", file=sys.stderr)
    now = now or datetime.now(fetch.JST)
    if replaced or dropped:
        print(f"replaced with backups: {len(replaced)}; picks gone with no backup left: {len(dropped)}; ideas filled by search: {searched}", file=sys.stderr)
    return {"version": 2, "curated": True, "fetched_at": now.isoformat(timespec="seconds"), "pairs": out_pairs, "portrait": portrait,
            "stats": {"requests": client.calls, "pages": len(pairs), "replaced": len(replaced), "dropped": len(dropped), "searched_ideas": searched,
                      "errors": state["errors"] + fallback_state["errors"]}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/yorokobu_items.json")
    ap.add_argument("--limit-pairs", type=int)
    a = ap.parse_args()
    c = ct.load()
    picks_file = ct.CONTENT_DIR / "picks.json"
    picks = json.loads(picks_file.read_text(encoding="utf-8")) if picks_file.exists() else {}
    app_id, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app_id and key):
        sys.exit("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY are not set")
    cfg = json.loads((ROOT / "sites" / "yorokobu" / "config.json").read_text(encoding="utf-8"))
    client = rakuten.Client(app_id, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=cfg.get("rakuten_affiliate_id"))
    data = refresh(c, client, picks, a.limit_pairs)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(data["stats"]))


if __name__ == "__main__":
    main()
