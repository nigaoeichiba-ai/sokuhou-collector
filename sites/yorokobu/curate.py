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
from sites.yorokobu.relevance import fits, fits_occasion  # noqa: E402

CANDIDATES = ROOT / "data" / "yorokobu_candidates.json"
PICKS = ct.CONTENT_DIR / "picks.json"
PICKS_PER_IDEA = 3
BACKUPS_MIN, BACKUPS_MAX = 1, 3
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


def batches(size: int, missing: bool = False) -> list[str]:
    c = ct.load()
    cand = _load_candidates()
    have = json.loads(PICKS.read_text(encoding="utf-8")) if missing and PICKS.exists() else {}
    pairs = [p for p in ct.pages(c) if ct.pair_key(p) in cand and ct.pair_key(p) not in have]
    out = []
    for i in range(0, len(pairs), size):
        out.append("\n\n".join(render_pair(p, cand[ct.pair_key(p)]) for p in pairs[i:i + size]))
    return out


def validate(answer: dict, c: dict, cand: dict, repair: bool = False) -> tuple[dict, list[str]]:
    """The answer with indices turned into codes, plus every rule it breaks.  With repair=True a pick or backup that breaks a rule is replaced by the next
    good one from the editor's own list (a promoted backup has no hand-written note, the page then shows the fact note), and only an idea that cannot be filled is an error."""
    errors: list[str] = []
    out: dict = {}
    by_key = {ct.pair_key(p): p for p in ct.pages(c)}
    for key, ideas in ((k.split(" | ")[0].strip(), v) for k, v in answer.items()):   # a header copied from the batch file ("key | title") is fine
        if key not in by_key or key not in cand:
            errors.append(f"{key}: unknown page")
            continue
        p, lists = by_key[key], cand[key]
        if len(ideas) != len(lists):
            errors.append(f"{key}: {len(ideas)} ideas answered, page has {len(lists)}")
            continue
        used: set[str] = set()
        sel_out = []
        occ_name = c["occ"].get(p.get("occasion", ""), {}).get("name", "")
        for n, (sel, items) in enumerate(zip(ideas, lists)):
            where = f"{key} idea {n}"
            if repair:
                row, errs = _repaired(sel, items, p, occ_name, used, where, p["ideas"][n])
                errors += errs
                sel_out.append(row)
                continue
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
                if not fits(it["name"], p.get("recipient")) or not fits_occasion(it["name"], p.get("occasion", ""), c["occ"].get(p.get("occasion", ""), {}).get("name", "")):
                    errors.append(f"{where}: {it['code']} does not fit the recipient or the occasion")
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
                if it["code"] in used or not fits(it["name"], p.get("recipient")) or not fits_occasion(it["name"], p.get("occasion", ""), c["occ"].get(p.get("occasion", ""), {}).get("name", "")):
                    errors.append(f"{where}: backup {it['code']} is used or does not fit")
                row_backups.append(it["code"])
            sel_out.append({"picks": row_picks, "backups": row_backups})
        out[key] = sel_out
    return out, errors


GENERIC = set("プレゼント 贈り物 祝い 誕生日 母の日 父の日 敬老の日 レディース メンズ 女性 男性 名入れ 母 父 祖母 祖父 夫 妻 彼氏 彼女 上司 同僚 義父母 子ども 子供 おしゃれ 人気 セット 長寿祝い 退職祝い".split())


def on_topic(name: str, idea: dict) -> bool:
    """The title shares at least a two-character piece with the idea's own search words (generic gift words do not count), so an idea about
    bath goods is not filled with wallets just because the search pool for it was thin."""
    grams = set()
    for tok in idea["query"].split():
        if tok in GENERIC or "ギフト" in tok:
            continue
        grams |= {tok[i:i + 2] for i in range(max(1, len(tok) - 1))}
    return not grams or any(g in name for g in grams)


def _repaired(sel: dict, items: list[dict], p: dict, occ_name: str, used: set, where: str, idea: dict | None = None) -> tuple[dict, list[str]]:
    """Fill 3 picks and 2-3 backups from the editor's ordered list (picks first, then backups), skipping what breaks a rule."""
    order = [(x.get("i"), (x.get("note") or "").strip()) for x in sel.get("picks", [])] + [(i, "") for i in sel.get("backups", [])]
    picks, backups, shops, seen = [], [], {}, set()
    for i, note in order:
        if not isinstance(i, int) or not 0 <= i < len(items) or i in seen:
            continue
        seen.add(i)
        it = items[i]
        if it["code"] in used or not fits(it["name"], p.get("recipient")) or not fits_occasion(it["name"], p.get("occasion", ""), occ_name):
            continue
        if idea and not on_topic(it["name"], idea):
            continue
        if len(picks) < PICKS_PER_IDEA:
            if shops.get(it["shop_code"], 0) >= 2:
                continue
            if not NOTE_MIN <= len(note) <= NOTE_MAX or any(w in note for w in NOTE_FORBIDDEN):
                note = ""
            shops[it["shop_code"]] = shops.get(it["shop_code"], 0) + 1
            picks.append({"code": it["code"], "note": note})
        elif len(backups) < BACKUPS_MAX:
            backups.append(it["code"])
    errs = []   # an idea with fewer than three on-topic products is kept as it is; with none, the daily refresh fills it from the keyword search
    used |= {x["code"] for x in picks}
    return {"picks": picks, "backups": backups}, errs


def merge(files: list[str], dry: bool = False) -> int:
    c = ct.load()
    cand = _load_candidates()
    picks = json.loads(PICKS.read_text(encoding="utf-8")) if PICKS.exists() else {}
    bad = 0
    for f in files:
        answer = json.loads(Path(f).read_text(encoding="utf-8"))
        merged, errors = validate(answer, c, cand, repair=True)
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
    keys = [ct.pair_key(p) for p in ct.pages(c)]
    done = [k for k in keys if k in picks]
    print(f"{len(done)} of {len(keys)} pages curated; missing: {', '.join(k for k in keys if k not in picks)[:600]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batch")
    b.add_argument("--size", type=int, default=10)
    b.add_argument("--out", required=True)
    b.add_argument("--missing", action="store_true", help="only pages that have no picks yet")
    m = sub.add_parser("merge")
    m.add_argument("--dry", action="store_true", help="only check the answers")
    m.add_argument("files", nargs="+")
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "batch":
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        texts = batches(a.size, a.missing)
        for n, t in enumerate(texts, 1):
            (out / f"batch_{n}.txt").write_text(t, encoding="utf-8", newline="\n")
        print(f"{len(texts)} batches in {out}")
    elif a.cmd == "merge":
        sys.exit(1 if merge(a.files, a.dry) else 0)
    else:
        report()


if __name__ == "__main__":
    main()
