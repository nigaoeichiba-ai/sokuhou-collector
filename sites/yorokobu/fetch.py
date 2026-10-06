"""Fetch the products for every page of よろこぶプレゼント from the Rakuten API and keep only what the pages show.

    python -m sites.yorokobu.fetch --out out/yorokobu_items.json [--limit-pairs N] [--plan]

Needs RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY in the environment (GitHub secrets; --plan needs neither and only counts
the requests).  The result is a build input, not committed: it changes every day and the site is rebuilt from it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu.picking import in_tier, pick  # noqa: E402
from sokuhou import rakuten  # noqa: E402

JST = timezone(timedelta(hours=9))
HITS = 30
PORTRAIT_SHOP = "2gaoe"  # the operator's own caricature shop; shown with a disclosure, linked directly
MAX_ERROR_SHARE = 0.03
MIN_PAIR_SHARE = 0.7


def plan(c: dict) -> list[dict]:
    """The API requests: per pair, one untiered search per extra query and one price-bounded search per tier."""
    reqs = []
    for p in c["pairs"]:
        key = ct.pair_key(p)
        q0, rest = p["queries"][0], p["queries"][1:]
        for q in rest:
            reqs.append({"pair": key, "tier": None, "params": {"keyword": q, "hits": HITS}})
        for t in p["tiers"]:
            tier = c["tiers"][t]
            params = {"keyword": q0, "hits": HITS, "sort": "-reviewCount"}
            if tier.get("min"):
                params["minPrice"] = tier["min"] + 1
            if tier.get("max"):
                params["maxPrice"] = tier["max"]
            reqs.append({"pair": key, "tier": t, "params": params})
    return reqs


def collect(c: dict, client: rakuten.Client, limit_pairs: int | None = None, now: datetime | None = None) -> dict:
    pairs = c["pairs"][:limit_pairs] if limit_pairs else c["pairs"]
    sub = {**c, "pairs": pairs}
    reqs = plan(sub)
    pool: dict[str, list[dict]] = {ct.pair_key(p): [] for p in pairs}
    errors = 0
    for r in reqs:
        common = {"availability": 1, "imageFlag": 1}
        try:
            raw = client.search(**common, **r["params"])
        except rakuten.RakutenError as e:
            errors += 1
            print(f"warning: {r['pair']} {r['params'].get('keyword')}: {e}", file=sys.stderr)
            if errors > max(3, MAX_ERROR_SHARE * len(reqs)):
                raise
            continue
        for x in raw:
            item = rakuten.normalize(x)
            if item:
                pool[r["pair"]].append(item)
    filters = c["filters"]
    out_pairs, nonempty = {}, 0
    for p in pairs:
        key = ct.pair_key(p)
        lists = {t: pick(pool[key], c["tiers"][t], filters) for t in p["tiers"]}
        out_pairs[key] = lists
        nonempty += any(lists.values())
    if pairs and nonempty < MIN_PAIR_SHARE * len(pairs):
        raise rakuten.RakutenError(f"only {nonempty} of {len(pairs)} pages have any product; not using this fetch")
    portrait = []
    try:
        for x in client.search(shopCode=PORTRAIT_SHOP, hits=HITS, availability=1):
            item = rakuten.normalize(x)
            if item:
                portrait.append(item)
    except rakuten.RakutenError as e:
        print(f"warning: portrait shop: {e}", file=sys.stderr)
    now = now or datetime.now(JST)
    return {"version": 1, "fetched_at": now.isoformat(timespec="seconds"), "pairs": out_pairs, "portrait": portrait,
            "stats": {"requests": client.calls, "pages": len(pairs), "pages_with_products": nonempty, "errors": errors}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/yorokobu_items.json")
    ap.add_argument("--limit-pairs", type=int)
    ap.add_argument("--plan", action="store_true", help="count the requests and exit")
    a = ap.parse_args()
    c = ct.load()
    if a.plan:
        reqs = plan(c)
        print(f"{len(c['pairs'])} pages, {len(reqs)} requests, about {len(reqs) * 1.1 / 60:.0f} minutes")
        return
    app_id, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app_id and key):
        sys.exit("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY are not set")
    cfg = json.loads((ROOT / "sites" / "yorokobu" / "config.json").read_text(encoding="utf-8"))
    client = rakuten.Client(app_id, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=cfg.get("rakuten_affiliate_id"))
    data = collect(c, client, a.limit_pairs)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(data["stats"]))


if __name__ == "__main__":
    main()
