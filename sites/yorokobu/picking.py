"""Which products to show: filter by availability, reviews and ng words, bucket by price tier, rank, keep variety."""
from __future__ import annotations

import math


def usable(item: dict, filters: dict) -> bool:
    if not item.get("available"):
        return False
    if item["reviews"] < filters["min_review_count"] or item["rating"] < filters["min_review_average"]:
        return False
    name = item["name"]
    return not any(w and w in name for w in filters["ng_words"])


def score(item: dict) -> float:
    """Rewards both a high rating and many reviews, without letting review count alone decide."""
    return item["rating"] * math.log10(item["reviews"] + 1)


def in_tier(price: int, tier: dict) -> bool:
    return (tier.get("min") is None or price > tier["min"]) and (tier.get("max") is None or price <= tier["max"])


def pick(items: list[dict], tier: dict, filters: dict, limit: int | None = None, per_shop: int = 2) -> list[dict]:
    """Best items of one tier: unique by item code, at most `per_shop` from one shop, highest score first."""
    limit = limit or filters["max_per_list"]
    seen, per, out = set(), {}, []
    for it in sorted((i for i in items if usable(i, filters) and in_tier(i["price"], tier)),
                     key=lambda i: (-score(i), i["price"])):
        if it["code"] in seen or per.get(it["shop_code"], 0) >= per_shop:
            continue
        seen.add(it["code"])
        per[it["shop_code"]] = per.get(it["shop_code"], 0) + 1
        out.append(it)
        if len(out) >= limit:
            break
    return out
