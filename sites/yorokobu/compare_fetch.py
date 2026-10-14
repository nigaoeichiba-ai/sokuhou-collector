"""The data of /compare/: for each kind of gift in content/compare.json, the Rakuten Ichiba search results (what a visitor would see searching the kind), with the shop's point
multiplier, written to data/yorokobu_compare.json.  The site build only READS this file (no network at build time), so a page always says when its numbers were taken.

    python -m sites.yorokobu.compare_fetch --out data/yorokobu_compare.json      (needs RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY; the workflow yorokobu-compare.yml runs it daily)

A request every REQUEST_GAP seconds (the deploy's fetch uses the same application ID); 3 requests per kind: the first two pages of the default order and the most reviewed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sokuhou import rakuten

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JST = timezone(timedelta(hours=9))
REQUEST_GAP = 3.0
HITS = 30
KEEP = 60                       # products kept per kind (the build shows the best 20 after its own rules)
PASSES = (("standard", 1), ("standard", 2), ("-reviewCount", 1))


def groups() -> list[dict]:
    return json.loads((HERE / "content" / "compare.json").read_text(encoding="utf-8"))["groups"]


def fetch(client: rakuten.Client, gs: list[dict], now: datetime | None = None, log=print) -> dict:
    out: dict[str, list[dict]] = {}
    errors = 0
    for g in gs:
        seen: dict[str, dict] = {}
        for sort, page in PASSES:
            try:
                raw = client.search(keyword=g["query"], hits=HITS, page=page, sort=sort, availability=1, imageFlag=1)
            except rakuten.RakutenError as e:
                errors += 1
                log(f"warning: {g['slug']} {sort} p{page}: {e}", file=sys.stderr)
                if errors > 6:
                    raise
                continue
            for x in raw:
                it = rakuten.normalize(x)
                if it:
                    seen.setdefault(it["code"], it)
        out[g["slug"]] = list(seen.values())[:KEEP]
        log(f"{g['slug']}: {len(out[g['slug']])}")
    return {"version": 1, "fetched_at": (now or datetime.now(JST)).isoformat(timespec="seconds"), "groups": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "yorokobu_compare.json"))
    ap.add_argument("--limit", type=int, help="only the first N kinds (a trial)")
    a = ap.parse_args()
    app_id, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app_id and key):
        sys.exit("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY are not set")
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    client = rakuten.Client(app_id, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=cfg.get("rakuten_affiliate_id"), min_interval=REQUEST_GAP)
    gs = groups()[: a.limit] if a.limit else groups()
    data = fetch(client, gs)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{sum(len(v) for v in data['groups'].values())} products in {len(data['groups'])} kinds, {client.calls} requests")


if __name__ == "__main__":
    main()
