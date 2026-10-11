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
