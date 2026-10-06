"""Which products to show: filter by availability, reviews, ng words and fit to the recipient; bucket by price tier; rank; keep variety.

Strict thresholds first; when a list would be short, the relaxed thresholds (fewer reviews, slightly lower rating) top it up, so a page is
rarely empty while still preferring well-reviewed products.
"""
from __future__ import annotations

import math

from sites.yorokobu import relevance


def usable(item: dict, filters: dict, recipient: str | None = None, relaxed: bool = False) -> bool:
    if not item.get("available"):
        return False
    lo = filters.get("relaxed", {}) if relaxed else {}
    if item["reviews"] < lo.get("min_review_count", filters["min_review_count"]) or item["rating"] < lo.get("min_review_average", filters["min_review_average"]):
        return False
    if item["price"] < filters.get("min_price", 0):  # engraving/option listings and trinkets are not gifts
        return False
    name = item["name"]
    if any(w and w in name for w in filters["ng_words"]):
        return False
    return relevance.fits(name, recipient)   # recipient None (a theme page): only the memorial / adult-only rules and the adult default apply


def score(item: dict) -> float:
    """Rewards both a high rating and many reviews, without letting review count alone decide."""
    return item["rating"] * math.log10(item["reviews"] + 1)


def in_tier(price: int, tier: dict | None) -> bool:
    if tier is None:
        return True
    return (tier.get("min") is None or price > tier["min"]) and (tier.get("max") is None or price <= tier["max"])


def pick(items: list[dict], tier: dict | None, filters: dict, limit: int | None = None, per_shop: int = 2,
         recipient: str | None = None, exclude: set | None = None) -> list[dict]:
    """Best items of one tier (None = any price): unique by item code, at most `per_shop` from one shop, highest score first."""
    limit = limit or filters["max_per_list"]
    seen, per, out = set(exclude or ()), {}, []
    for relaxed in (False, True):
        for it in sorted((i for i in items if usable(i, filters, recipient, relaxed) and in_tier(i["price"], tier)),
                         key=lambda i: (-score(i), i["price"])):
            if it["code"] in seen or per.get(it["shop_code"], 0) >= per_shop:
                continue
            seen.add(it["code"])
            per[it["shop_code"]] = per.get(it["shop_code"], 0) + 1
            out.append(it)
            if len(out) >= limit:
                return out
    return out
