"""Editors' tooling for the hand-picked products (content/picks.json).

    python -m sites.yorokobu.curate batch --size 10 --out DIR      # write the shortlist as text batches for the editors
    python -m sites.yorokobu.curate merge FILE [FILE ...]          # validate editors' answers and merge them into content/picks.json
    python -m sites.yorokobu.curate report                         # how much of the site is curated

An editor answer is {"<pair key>": [ {"picks": [{"i": 3, "note": "..."}, x3], "backups": [i, i, i]}, x4 ideas ]}, where i counts the
products listed under that idea in the batch file.  The merge turns indices into item codes and refuses answers that break the rules.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu.relevance import fits  # noqa: E402

CANDIDATES = ROOT / "data" / "yorokobu_candidates.json"
PICKS = ct.CONTENT_DIR / "picks.json"
PICKS_PER_IDEA = 3
BACKUPS_MIN, BACKUPS_MAX = 2, 3
NOTE_MIN, NOTE_MAX = 8, 40
NOTE_FORBIDDEN = ["人気", "おすすめ", "オススメ", "最高", "ランキング", "No.1", "必ず", "絶対", "レビュー", "口コミ", "売れ", "話題", "楽天", "AI", "%", "％"]


def _load_candidates() -> dict:
    return json.loads(CANDIDATES.read_text(encoding="utf-8"))["pairs"]


def render_pair(p: dict, lists: list[list[dict]]) -> str:
    lines = [f"## {ct.pair_key(p)} | {p['title']}"]
    for n, (idea, items) in enumerate(zip(p["ideas"], lists)):
        lines.append(f"IDEA {n} [{idea['type']}] {idea['label']} -- {idea['why']}")
        for i, it in enumerate(items):
            rating = f"{it['rating']:.1f}({it['reviews']})" if it.get("reviews") else "-"
            lines.append(f" {i}| {it['price']}yen | {rating} | {it['shop'][:16]} | {it["name"][:64]}")
    return "\n".join(lines)


def batches(size: int) -> list[str]:
    c = ct.load()
    cand = _load_candidates()
    pairs = [p for p in c["pairs"] if ct.pair_key(p) in cand]
    out = []
    for i in range(0, len(pairs), size):
        out.append("\n\n".join(render_pair(p, cand[ct.pair_key(p)]) for p in pairs[i:i + size]))
    return out


def validate(answer: dict, c: dict, cand: dict) -> tuple[dict, list[str]]:
    """The answer with indices turned into codes, plus every rule it breaks."""
    errors: list[str] = []
    out: dict = {}
    by_key = {ct.pair_key(p): p for p in c["pairs"]}
    for key, ideas in answer.items():
        if key not in by_key or key not in cand:
            errors.append(f"{key}: unknown page")
            continue
        p, lists = by_key[key], cand[key]
        if len(ideas) != len(lists):
            errors.append(f"{key}: {len(ideas)} ideas answered, page has {len(lists)}")
            continue
        used: set[str] = set()
        sel_out = []
        for n, (sel, items) in enumerate(zip(ideas, lists)):
            where = f"{key} idea {n}"
            picks, backups = sel.get("picks", []), sel.get("backups", [])
            if len(picks) != PICKS_PER_IDEA:
                errors.append(f"{where}: {len(picks)} picks")
            if not BACKUPS_MIN <= len(backups) <= BACKUPS_MAX:
                errors.append(f"{where}: {len(backups)} backups")
            idx = [x.get("i") for x in picks] + list(backups)
            if len(set(idx)) != len(idx) or any(not isinstance(i, int) or not 0 <= i < len(items) for i in idx):
                errors.append(f"{where}: indices repeat or are out of range {idx}")
                continue
            shops = [items[x["i"]]["shop_code"] for x in picks]
            if len(set(shops)) < len(shops) - 1:
                errors.append(f"{where}: too many picks from one shop")
            row_picks = []
            for x in picks:
                it = items[x["i"]]
                note = (x.get("note") or "").strip()
                if it["code"] in used:
                    errors.append(f"{where}: {it['code']} already used on this page")
                if not fits(it["name"], p["recipient"]):
                    errors.append(f"{where}: {it['code']} does not fit the recipient")
                if not NOTE_MIN <= len(note) <= NOTE_MAX:
                    errors.append(f"{where}: note length {len(note)}: {note}")
                bad = [w for w in NOTE_FORBIDDEN if w in note]
                if bad:
                    errors.append(f"{where}: note uses {bad}: {note}")
                used.add(it["code"])
                row_picks.append({"code": it["code"], "note": note})
            row_backups = []
            for i in backups:
                it = items[i]
                if it["code"] in used or not fits(it["name"], p["recipient"]):
                    errors.append(f"{where}: backup {it['code']} is used or does not fit")
                row_backups.append(it["code"])
            sel_out.append({"picks": row_picks, "backups": row_backups})
        out[key] = sel_out
    return out, errors


def merge(files: list[str], dry: bool = False) -> int:
    c = ct.load()
    cand = _load_candidates()
    picks = json.loads(PICKS.read_text(encoding="utf-8")) if PICKS.exists() else {}
    bad = 0
    for f in files:
        answer = json.loads(Path(f).read_text(encoding="utf-8"))
        merged, errors = validate(answer, c, cand)
        for e in errors:
            print(f"{Path(f).name}: {e}", file=sys.stderr)
        # a page is taken only when all of its ideas passed
        bad_keys = {e.split(":")[0].split(" idea")[0] for e in errors}
        good = {k: v for k, v in merged.items() if k not in bad_keys}
        picks.update(good)
        bad += len(bad_keys)
        print(f"{Path(f).name}: {len(good)} pages merged, {len(bad_keys)} pages refused")
    if not dry:
        PICKS.write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return bad


def report() -> None:
    c = ct.load()
    picks = json.loads(PICKS.read_text(encoding="utf-8")) if PICKS.exists() else {}
    keys = [ct.pair_key(p) for p in c["pairs"]]
    done = [k for k in keys if k in picks]
    print(f"{len(done)} of {len(keys)} pages curated; missing: {', '.join(k for k in keys if k not in picks)[:600]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batch")
    b.add_argument("--size", type=int, default=10)
    b.add_argument("--out", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--dry", action="store_true", help="only check the answers")
    m.add_argument("files", nargs="+")
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "batch":
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        texts = batches(a.size)
        for n, t in enumerate(texts, 1):
            (out / f"batch_{n}.txt").write_text(t, encoding="utf-8", newline="\n")
        print(f"{len(texts)} batches in {out}")
    elif a.cmd == "merge":
        sys.exit(1 if merge(a.files, a.dry) else 0)
    else:
        report()


if __name__ == "__main__":
    main()
