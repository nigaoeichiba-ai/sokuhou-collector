"""Fetch the products for every page of よろこぶプレゼント from the Rakuten API and keep only what the pages show.

    python -m sites.yorokobu.fetch --out out/yorokobu_items.json [--limit-pairs N] [--plan]

Needs RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY in the environment (GitHub secrets; --plan needs neither and only counts the first-pass requests).

Per page: one keyword search per IDEA (4 kinds of gift, each with its own search phrase), then price-bounded searches only for budget tiers
that stayed short.  The result per page is {"ideas": [{label, type, why, query, items}], "tiers": {tier: [items]}}; it is a build input, not
committed, because it changes every day.  Rakuten's rules: prices/stock may be cached at most 24 h and must be refreshed weekly at least.
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
from sites.yorokobu.picking import pick  # noqa: E402
from sokuhou import rakuten  # noqa: E402

JST = timezone(timedelta(hours=9))
HITS = 30
PORTRAIT_SHOP = "2gaoe"  # the operator's own caricature shop; shown with a disclosure, linked directly
MAX_ERROR_SHARE = 0.03
MIN_PAIR_SHARE = 0.7
IDEA_ITEMS = 8        # products kept per idea
TIER_MIN = 4          # a budget tier with fewer products than this gets a price-bounded search
TIER_EXTRA_REQUESTS = 2


def plan(c: dict) -> list[dict]:
    """The first-pass requests: one keyword search per idea of every page."""
    return [{"pair": ct.pair_key(p), "idea": i, "params": {"keyword": idea["query"], "hits": HITS}}
            for p in c["pairs"] for i, idea in enumerate(p["ideas"])]


def _tier_params(query: str, tier: dict) -> dict:
    params = {"keyword": query, "hits": HITS, "sort": "-reviewCount"}
    if tier.get("min"):
        params["minPrice"] = tier["min"] + 1
    if tier.get("max"):
        params["maxPrice"] = tier["max"]
    return params


def _search(client: rakuten.Client, label: str, state: dict, total: int, **params) -> list[dict]:
    try:
        raw = client.search(availability=1, imageFlag=1, **params)
    except rakuten.RakutenError as e:
        state["errors"] += 1
        print(f"warning: {label}: {e}", file=sys.stderr)
        if state["errors"] > max(3, MAX_ERROR_SHARE * total):
            raise
        return []
    return [it for it in (rakuten.normalize(x) for x in raw) if it]


def collect(c: dict, client: rakuten.Client, limit_pairs: int | None = None, now: datetime | None = None) -> dict:
    pairs = c["pairs"][:limit_pairs] if limit_pairs else c["pairs"]
    filters = c["filters"]
    total = sum(len(p["ideas"]) for p in pairs)
    state = {"errors": 0}
    out_pairs, nonempty, thin = {}, 0, []
    for p in pairs:
        key = ct.pair_key(p)
        pool = [[] for _ in p["ideas"]]
        for i, idea in enumerate(p["ideas"]):
            pool[i] = _search(client, f"{key} idea {i}", state, total, keyword=idea["query"], hits=HITS)
        everything = [it for lst in pool for it in lst]
        # budget tiers that are still short get a price-bounded search with the page's first idea
        tiers = {}
        for t in p["tiers"]:
            tier = c["tiers"][t]
            items = pick(everything, tier, filters, recipient=p["recipient"])
            extra = 0
            for idea in p["ideas"]:
                if len(items) >= TIER_MIN or extra >= TIER_EXTRA_REQUESTS:
                    break
                everything += _search(client, f"{key} tier {t}", state, total, **_tier_params(idea["query"], tier))
                extra += 1
                items = pick(everything, tier, filters, recipient=p["recipient"])
            tiers[t] = items
        used: set = set()
        ideas_out = []
        for i, idea in enumerate(p["ideas"]):
            items = pick(pool[i], None, filters, limit=IDEA_ITEMS, recipient=p["recipient"], exclude=used)
            used |= {it["code"] for it in items}
            ideas_out.append({k: idea[k] for k in ("label", "type", "query", "why")} | {"items": items})
        out_pairs[key] = {"ideas": ideas_out, "tiers": tiers}
        count = len({it["code"] for i in ideas_out for it in i["items"]} | {it["code"] for lst in tiers.values() for it in lst})
        nonempty += count > 0
        if count < 8:
            thin.append((key, count))
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
    if thin:
        print("pages with fewer than 8 products:", ", ".join(f"{k}={n}" for k, n in thin), file=sys.stderr)
    return {"version": 2, "fetched_at": now.isoformat(timespec="seconds"), "pairs": out_pairs, "portrait": portrait,
            "stats": {"requests": client.calls, "pages": len(pairs), "pages_with_products": nonempty, "thin_pages": len(thin), "errors": state["errors"]}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/yorokobu_items.json")
    ap.add_argument("--limit-pairs", type=int)
    ap.add_argument("--plan", action="store_true", help="count the first-pass requests and exit")
    a = ap.parse_args()
    c = ct.load()
    if a.plan:
        reqs = plan(c)
        print(f"{len(c['pairs'])} pages, {len(reqs)} first-pass requests (plus tier top-ups), about {len(reqs) * 1.2 / 60:.0f}+ minutes")
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
