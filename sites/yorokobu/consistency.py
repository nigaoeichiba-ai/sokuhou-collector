"""Does what a page says match what it shows?  A report over the data of one build (printed in the build log; the numbers go to the deploy log).

  * every product under an idea is of that idea's kind (its must-words),
  * how many ideas are shown (enough products of their own kind) and how many are too thin to show,
  * every line of a person's 「喜ばれやすいもの」 leads somewhere: products of that kind, or at least the search for them.
"""
from __future__ import annotations

from sites.yorokobu import content as ct
from sites.yorokobu import relevance


def audit(d: dict, min_items: int = 2) -> dict:
    from sites.yorokobu import build
    c = d["c"]
    out = {"pages": 0, "ideas": 0, "shown": 0, "thin": [], "wrong": [], "like_lines": 0, "like_lines_with_products": 0, "like_lines_without_search": []}
    spec = {(ct.pair_key(p), n): idea.get("must") for p in ct.pages(c) for n, idea in enumerate(p["ideas"])}
    for key in sorted(d["pairs"]):
        ideas = build.pair_items(d, key)[0]
        out["pages"] += 1
        for n, idea in enumerate(ideas):
            out["ideas"] += 1
            for it in idea["items"]:
                if not relevance.fits_idea(it["name"], spec.get((key, n)) or idea.get("must")):
                    out["wrong"].append((key, idea["label"], it["name"][:40]))
            if len(idea["items"]) >= min_items:
                out["shown"] += 1
            else:
                out["thin"].append((key, idea["label"], len(idea["items"])))
    for r in c["recipients"]:
        for i, row in enumerate(r.get("like_rows") or []):
            out["like_lines"] += 1
            if build.like_items(d, r, i):
                out["like_lines_with_products"] += 1
            if not row.get("queries"):
                out["like_lines_without_search"].append((r["slug"], i))
    return out


def summary(a: dict) -> str:
    return (f'consistency: {a["pages"]} pages, {a["ideas"]} ideas ({a["shown"]} shown, {len(a["thin"])} too thin), {len(a["wrong"])} products not of their idea\'s kind, '
            f'{a["like_lines_with_products"]}/{a["like_lines"]} 「喜ばれやすいもの」 lines with products')
