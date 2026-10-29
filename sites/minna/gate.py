"""みんなのイラスト: the gate that keeps a new set off the site until its thick page is ready (owner decision 2026-10-29: "publish a thick page from the start").

    python -m sites.minna.gate            # every set that is held back, and why; counts
    python -m sites.minna.gate --record   # add the sets that pass the gate to content/published_series.json (so they can never be held back later)

A set of the library is shown on the site when
  * it is in content/published_series.json (every set that was on the site on 2026-10-29: its URLs never go away), or
  * it has a guide (library/<slug>/guide.json, or sites/minna/setguides.py) that passes the checks below.
Otherwise it is held back: the build leaves out the set, its pictures, its page and the pictures' pages (sitemap, keyword pages, search data), and says so in the log:
    held back: <slug> (<reason>)
Sets of the old catalogue (legacy) are never held back.  The checks are about the guide, not about taste: every picture has its line, 4+ paragraphs of use of 450+ characters,
a picture-based example x2 whose files exist, no unknown number in a paragraph.  (The page itself must then have 800+ characters of sentences: tests/test_minna_setguides.py.)
"""
from __future__ import annotations

import json
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE / "content" / "published_series.json"
MIN_POINTS = 4
MIN_POINT_CHARS = 450
MIN_WHY = 40
MIN_EXAMPLES = 2

_logged: set[str] = set()


def published_slugs() -> set[str]:
    return set(json.loads(PUBLISHED.read_text(encoding="utf-8"))["slugs"]) if PUBLISHED.exists() else set()


def problems(slug: str, its: list[dict], spec: dict | None, examples_dir: Path | None = None) -> list[str]:
    """Why a set's guide is not good enough (empty list: it passes).  `its` are the set's pictures (dicts with id, w, h, path)."""
    from sites.minna import setguides
    ex_dir = examples_dir or setguides.EXAMPLES_DIR
    if not spec:
        return ["ガイドがない(使い分けの表・使い方・完成例)"]
    out: list[str] = []
    keys = {i["id"][len(slug) + 1:] for i in its}
    picks = set(spec.get("picks", {}))
    if keys - picks:
        out.append(f"行のない素材: {', '.join(sorted(keys - picks))}")
    if picks - keys:
        out.append(f"素材のない行: {', '.join(sorted(picks - keys))}")
    for k, v in spec.get("picks", {}).items():
        if len(str(v).strip()) < 8:
            out.append(f"使いどころの行が短すぎる: {k}")
    if len(spec.get("why", "")) < MIN_WHY:
        out.append("why(セットの紹介)が短い")
    points = spec.get("points", [])
    if len(points) < MIN_POINTS or sum(len(p) for p in points) < MIN_POINT_CHARS:
        out.append(f"使い方の段落が足りない({len(points)}段落・{sum(len(p) for p in points)}字。{MIN_POINTS}段落・{MIN_POINT_CHARS}字以上)")
    examples = spec.get("examples", [])
    if len(examples) < MIN_EXAMPLES:
        out.append(f"完成例が足りない({len(examples)}枚。{MIN_EXAMPLES}枚以上)")
    for ex in examples:
        name = ex["name"] if isinstance(ex, dict) else ex[0]
        if not (ex_dir / f"{name}.webp").exists():
            out.append(f"完成例の画像がない: {name}.webp")
    if its and not out:
        try:
            stats = setguides.guide_stats(its, spec)
            for p in points:
                p.format(**stats)
        except (KeyError, IndexError, ValueError) as e:
            out.append(f"段落に使えない書き込みがある: {e}")
    return out


def apply(items: list[dict], series: list[dict], published: set[str] | None = None, specs: dict | None = None,
          examples_dir: Path | None = None, log=print) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    """(items, series, held) without the sets that are held back.  `held` maps a slug to the reasons."""
    from sites.minna import setguides
    pub = published_slugs() if published is None else published
    spec_of = setguides.GUIDES if specs is None else specs
    held: dict[str, list[str]] = {}
    for s in series:
        if s.get("legacy") or s["slug"] in pub:
            continue
        its = [i for i in items if i["series"] == s["slug"]]
        why = problems(s["slug"], its, spec_of.get(s["slug"]), examples_dir)
        if why:
            held[s["slug"]] = why
    for slug, why in held.items():
        if slug not in _logged:
            _logged.add(slug)
            log(f"held back: {slug} ({'; '.join(why)})")
    if not held:
        return items, series, held
    return [i for i in items if i["series"] not in held], [s for s in series if s["slug"] not in held], held


def main(argv: list[str]) -> None:
    sys.path.insert(0, str(HERE.parent.parent))
    from sites.minna import model
    from sites.minna.catalog import CATEGORIES, build_catalog
    from sites.yorokobu import content as gift_content
    items, series = model.load_all(gift_content, build_catalog, CATEGORIES)
    for s in series:
        s["items"] = [i for i in items if i["series"] == s["slug"]]
    _, kept, held = apply(items, series, log=lambda *_: None)
    pub = published_slugs()
    new_pass = [s["slug"] for s in kept if not s.get("legacy") and s["slug"] not in pub]
    print(f"sets: {len([s for s in series if not s.get('legacy')])} (in published_series.json: {len(pub)}, passing the gate but not recorded: {len(new_pass)}, held back: {len(held)})")
    for slug, why in sorted(held.items()):
        print(f"held back: {slug} ({'; '.join(why)})")
    if "--record" in argv:
        PUBLISHED.write_text(json.dumps({"slugs": sorted(pub | set(new_pass))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="")
        print(f"recorded {len(new_pass)} set(s) in {PUBLISHED.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
