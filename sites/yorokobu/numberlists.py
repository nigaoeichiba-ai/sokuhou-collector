"""Lists of products picked by their own numbers (review count, rating, price), made from the products the site already fetched.

No new API calls: the pool is every product on every page (pairs and themes), once each.  Each list is a rule on numbers, so what the page says
about it ("reviews 1,000 or more, average 4.3 or more") is exactly what the rule did.  Review numbers are customers' opinions at the time of
fetching, and the pages say so; nothing here claims a product is good, only that it has these numbers.
"""
from __future__ import annotations

from sites.yorokobu import relevance

# slug, title, one line for the hub, rule on a product, sort key (smaller first), the sentence that says exactly what the rule is
LISTS = [
    {"slug": "reviews-10000", "title": "レビュー1万件以上の、実績のある商品", "short": "1万件以上のレビューが集まっている、定番の商品",
     "rule": lambda i: i["reviews"] >= 10000 and i["rating"] >= 4.3, "sort": lambda i: (-i["reviews"], -i["rating"]),
     "says": "レビュー件数が10,000件以上で、レビュー平均が4.3以上の商品を、レビュー件数の多い順に並べています。"},
    {"slug": "reviews-3000", "title": "レビュー3,000件以上の、たくさん選ばれている商品", "short": "3,000〜9,999件のレビューがある商品",
     "rule": lambda i: 3000 <= i["reviews"] < 10000 and i["rating"] >= 4.3, "sort": lambda i: (-i["reviews"], -i["rating"]),
     "says": "レビュー件数が3,000件以上10,000件未満で、レビュー平均が4.3以上の商品を、レビュー件数の多い順に並べています。"},
    {"slug": "reviews-1000", "title": "レビュー1,000件以上の、評価の安定した商品", "short": "1,000〜2,999件のレビューがある商品",
     "rule": lambda i: 1000 <= i["reviews"] < 3000 and i["rating"] >= 4.3, "sort": lambda i: (-i["reviews"], -i["rating"]),
     "says": "レビュー件数が1,000件以上3,000件未満で、レビュー平均が4.3以上の商品を、レビュー件数の多い順に並べています。"},
    {"slug": "hidden-gems", "title": "まだ知られていない、評価の高い商品", "short": "レビューは少なめでも、平均が4.7以上の商品",
     "rule": lambda i: 30 <= i["reviews"] <= 300 and i["rating"] >= 4.7, "sort": lambda i: (-i["rating"], -i["reviews"]),
     "says": "レビュー件数が30件以上300件以下で、レビュー平均が4.7以上の商品を、評価の高い順に並べています。件数が少ないぶん、数字は動きやすい点に、ご注意ください。"},
    {"slug": "cheap-and-loved", "title": "2,000円以下で、評価の高い商品", "short": "2,000円以下で、レビュー300件以上・平均4.6以上",
     "rule": lambda i: i["price"] <= 2000 and i["reviews"] >= 300 and i["rating"] >= 4.6, "sort": lambda i: (-i["reviews"], -i["rating"]),
     "says": "価格が2,000円以下で、レビュー件数が300件以上、レビュー平均が4.6以上の商品を、レビュー件数の多い順に並べています。"},
]
MIN_ITEMS = 6      # a list shorter than this has no page
MAX_ITEMS = 36


def pool(pairs: dict, filters: dict) -> list[dict]:
    """Every product of every page, once each, that the site would show: for sale, above the minimum price, no ng word, and passing the
    memorial / adult-only rules (no recipient is assumed)."""
    seen, out = set(), []
    for v in pairs.values():
        groups = [idea["items"] for idea in v.get("ideas", [])] + [lst for lst in v.get("tiers", {}).values() if isinstance(lst, list)]
        for lst in groups:
            for it in lst:
                if it["code"] in seen:
                    continue
                seen.add(it["code"])
                if not it.get("available", True) or it["price"] < filters.get("min_price", 0):
                    continue
                if any(w and w in it["name"] for w in filters.get("ng_words", [])):
                    continue
                if relevance.fits(it["name"], None):
                    out.append(it)
    return out


def view(pairs: dict, filters: dict) -> dict | None:
    products = pool(pairs, filters)
    lists = []
    for spec in LISTS:
        items = sorted((i for i in products if spec["rule"](i)), key=spec["sort"])
        if len(items) >= MIN_ITEMS:
            lists.append({"slug": spec["slug"], "title": spec["title"], "short": spec["short"], "says": spec["says"], "items": items[:MAX_ITEMS], "total": len(items)})
    return {"lists": lists, "pool": len(products)} if lists else None
