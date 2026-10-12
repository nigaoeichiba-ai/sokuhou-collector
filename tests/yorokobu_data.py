"""Helpers for tests that build the REAL content with fixture products."""
import copy

from sites.yorokobu import content


def with_musts(items: dict, c: dict) -> dict:
    """The fixture products carry the first must-word of the idea they sit under in their titles, as a product that really belongs to the idea does
    (the real ideas keep only products of their own kind, so products with unrelated fixture titles would all be left out)."""
    out = copy.deepcopy(items)
    spec = {content.pair_key(p): p["ideas"] for p in content.pages(c)}
    for key, v in out["pairs"].items():
        for n, idea in enumerate(v.get("ideas", [])):
            must = (spec.get(key) or [])
            word = (must[n].get("must") or [""])[0] if n < len(must) else ""
            for it in idea["items"]:
                it["name"] = f'{it["name"]} {word}'.strip()
    return out


def rich_boyfriend(items: dict) -> dict:
    """The fixture with a birthday x boyfriend page that has enough products for every part of a gift page: the first four, the cards of the proposals
    and a list of what is left (the shared fixture has three products, which all fit into the first four)."""
    out = copy.deepcopy(items)
    base = out["pairs"]["birthday-boyfriend"]["ideas"]
    more = [("e1", 3500, "s4", 300, 4.0, False, True), ("e2", 4800, "s5", 10, 4.9, True, False), ("e3", 1200, "s6", 80, 3.5, False, False),
            ("e4", 2900, "s7", 120, 4.2, True, True), ("e5", 3200, "s8", 500, 4.1, False, True), ("e6", 1500, "s9", 20, 4.7, True, False),
            ("e7", 4500, "s10", 60, 4.3, True, True), ("e8", 3800, "s11", 90, 4.4, True, True), ("e9", 3600, "s12", 40, 4.0, True, True)]
    proto = base[0]["items"][0]
    for n, (code, price, shop, reviews, rating, ship, gift) in enumerate(more):
        item = {**proto, "code": code, "name": f"テスト商品{code} 贈り物にぴったりのギフトセット", "price": price, "url": f"https://item.rakuten.co.jp/{shop}/{code}/",
                "shop": f"店{shop}", "shop_code": shop, "reviews": reviews, "rating": rating, "free_shipping": ship, "gift": gift}
        base[1 if code in ("e8", "e9") else 0]["items"].append(item)
    return out
