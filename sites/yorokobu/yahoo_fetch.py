"""The Yahoo!ショッピング side of /compare/: for each kind of gift in content/compare.json, the search results of the Shopping Web API v3 (itemSearch), written to
data/yorokobu_yahoo.json.  The site build only READS this file (no network at build time).

    python -m sites.yorokobu.yahoo_fetch --out data/yorokobu_yahoo.json            (needs YAHOO_CLIENT_ID; the workflow yorokobu-yahoo.yml runs it)
    python -m sites.yorokobu.yahoo_fetch --probe "お歳暮 ギフト"                    (prints the shape of one response: field names and a few values, never the ID)

Rules read from the developer network (2026-10-16): 30 requests a minute per application ID (a 429 means wait a minute); the credit (Web Services by Yahoo! JAPAN) must be shown on a page that shows
the data; the application ID is a secret and appears in no log or file.  Item links are made affiliate links by the API itself (affiliate_type=vc + affiliate_id).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JST = timezone(timedelta(hours=9))
ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
REQUEST_GAP = 2.2               # the limit is 30 requests a minute for each application ID (Developer Network notice of 2022-05-20; the 50,000 a day was abolished)
RETRY_WAIT = 65                 # after a 429 (limit reached): a minute and a little, once
RESULTS = 30
KEEP = 40
PASSES = (("-score", 1), ("-review_count", 1))


class YahooError(RuntimeError):
    pass


def vc_affiliate_id(vc: dict) -> str:
    """The affiliate_id the API wants for ValueCommerce: the referral link up to vc_url=."""
    return f"http://ck.jp.ap.valuecommerce.com/servlet/referral?sid={vc['sid']}&pid={vc['pid']}&vc_url="


class Client:
    def __init__(self, client_id: str, vc: dict | None, min_interval: float = REQUEST_GAP, retry_wait: float = RETRY_WAIT):
        self.client_id, self.vc, self.min_interval, self.retry_wait = client_id, vc, min_interval, retry_wait
        self.calls = 0
        self._last = 0.0

    def search(self, query: str, sort: str = "-score", start: int = 1, results: int = RESULTS) -> dict:
        p = {"appid": self.client_id, "query": query, "results": results, "start": start, "sort": sort, "in_stock": "true"}
        if self.vc:
            p["affiliate_type"] = "vc"
            p["affiliate_id"] = vc_affiliate_id(self.vc)
        url = ENDPOINT + "?" + urllib.parse.urlencode(p)
        for attempt in (1, 2):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            req = urllib.request.Request(url, headers={"User-Agent": "yorokobu-present.com compare (contact via the site)"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:                      # the message never carries the URL (and so never the ID)
                body = e.read().decode("utf-8", "replace")[:300].replace(self.client_id, "***")
                if e.code == 429 and attempt == 1:
                    time.sleep(self.retry_wait)
                    continue
                raise YahooError(f"HTTP {e.code}: {body}") from None
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                raise YahooError(f"{type(e).__name__}") from None


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def normalize(h: dict) -> dict | None:
    """The few fields the comparison needs; None when the item cannot be shown (no price, link or name)."""
    name = (h.get("name") or "").strip()
    url = (h.get("url") or "").strip()
    price = int(_num(h.get("price")))
    image = ((h.get("image") or {}).get("medium") or "").strip()
    if not (name and url.startswith("https://") and price > 0):
        return None
    review = h.get("review") or {}
    ship = h.get("shipping") or {}
    pt = h.get("point") or {}
    seller = h.get("seller") or {}
    points = sum(int(_num(pt.get(k))) for k in ("amount", "bonusAmount", "lyLimitedBonusAmount"))     # a member's own points; the premium-member fields are left out
    return {
        "code": h.get("code") or url,
        "name": name,
        "price": price,
        "url": url,                                              # already the affiliate link (affiliate_type=vc); used as it is
        "image": image,
        "shop": (seller.get("name") or "").strip(),
        "shop_code": seller.get("sellerId") or "",
        "reviews": int(_num(review.get("count"))),
        "rating": round(_num(review.get("rate")), 2),
        "available": bool(h.get("inStock", True)),
        "ship": int(_num(ship.get("code"), 1)),                  # 1 = not set, 2 = free, 3 = free under a condition (the real response, 2026-10-16)
        "free_shipping": int(_num(ship.get("code"), 1)) == 2,
        "points": points,
    }


def fetch(client: Client, gs: list[dict], now: datetime | None = None, log=print) -> dict:
    out: dict[str, list[dict]] = {}
    errors = 0
    for g in gs:
        seen: dict[str, dict] = {}
        for sort, start in PASSES:
            try:
                raw = client.search(g["query"], sort=sort, start=start)
            except YahooError as e:
                errors += 1
                log(f"warning: {g['slug']} {sort}: {e}", file=sys.stderr)
                if errors > 6:
                    raise
                continue
            for h in raw.get("hits") or []:
                it = normalize(h)
                if it:
                    seen.setdefault(it["code"], it)
        out[g["slug"]] = list(seen.values())[:KEEP]
        log(f"{g['slug']}: {len(out[g['slug']])}")
    return {"version": 1, "fetched_at": (now or datetime.now(JST)).isoformat(timespec="seconds"), "groups": out}


def shape(v, depth=0):
    """Field names with the type (and a short sample for scalars), to read a real response without storing it."""
    if isinstance(v, dict):
        return {k: shape(x, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        return [shape(v[0], depth + 1)] if v else []
    s = repr(v)
    return s if len(s) <= 60 else s[:57] + "..."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "yorokobu_yahoo.json"))
    ap.add_argument("--limit", type=int, help="only the first N kinds (a trial)")
    ap.add_argument("--probe", help="print the shape of one response for this query and stop")
    a = ap.parse_args()
    cid = os.environ.get("YAHOO_CLIENT_ID")
    if not cid:
        sys.exit("YAHOO_CLIENT_ID is not set")
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    client = Client(cid, cfg.get("yahoo_vc"))
    if a.probe:
        r = client.search(a.probe, results=3)
        print(json.dumps({k: shape(v) for k, v in r.items() if k != "hits"}, ensure_ascii=False, indent=1))
        for h in (r.get("hits") or [])[:2]:                       # one line a field, so a log viewer shows all of it
            for k, v in h.items():
                print(f"{k}: {json.dumps(shape(v), ensure_ascii=False, separators=(',', ':'))}")
            print("--")
        return
    gs = json.loads((HERE / "content" / "compare.json").read_text(encoding="utf-8"))["groups"]
    gs = gs[: a.limit] if a.limit else gs
    data = fetch(client, gs)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{sum(len(v) for v in data['groups'].values())} products in {len(data['groups'])} kinds, {client.calls} requests")


if __name__ == "__main__":
    main()
