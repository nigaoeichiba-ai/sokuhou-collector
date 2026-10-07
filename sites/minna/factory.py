"""The illustration factory of みんなのイラスト: plan (specs) -> order sheets from the image generator (brief) -> cut and file them (ingest).

    python -m sites.minna.factory status
    python -m sites.minna.factory brief --out BRIEF.md [--series a,b] [--sheets-dir DIR] [--limit N]    # what still has to be drawn
    python -m sites.minna.factory ingest [--sheets-dir DIR]                                            # cut every finished sheet into the library

A spec (sites/minna/specs/<slug>.json) describes ONE series:
    slug, title, subject (Japanese noun, appended to each item name), genre, touch, lead (a paragraph about the series), tags,
    subject_en (what the generator must draw, kept identical on every sheet so the character stays the same),
    grid [cols, rows] (default [3, 2]), key (background colour, default #FF00FF), title_fmt ("{ja}{subject}" or "{ja}"),
    season {"from": "MM-DD", "to": "MM-DD"} (optional: the series is featured on the top page in that window),
    items [[id_suffix, japanese phrase, english pose / object, optional japanese description], ...]  (a multiple of cols*rows; chunked into sheets in order)
The ingest step writes sites/minna/library/<slug>/<id>.webp plus series.json (everything the build needs); the specs stay the plan.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.minna import sheetkit  # noqa: E402
from sites.minna.taxonomy import GENRE_BY_SLUG, TOUCH_BY_SLUG  # noqa: E402

SPECS = HERE / "specs"
LIBRARY = HERE / "library"
DEFAULT_SHEETS = ROOT.parent / "sokuhou-sites" / "docs" / "minna_sheets"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SpecError(Exception):
    pass


def load_spec(path: Path) -> dict:
    s = json.loads(path.read_text(encoding="utf-8"))
    s.setdefault("grid", [3, 2])
    s.setdefault("key", "#FFFFFF")
    s.setdefault("holes", False)
    s.setdefault("sheet_subjects", [])
    s.setdefault("exclude", [])
    s.setdefault("title_fmt", "{ja}{subject}")
    s.setdefault("tags", [])
    s.setdefault("season", None)
    s.setdefault("subject", "")
    s.setdefault("subject_en", "")
    cols, rows = s["grid"]
    per = cols * rows
    where = path.name
    for k in ("slug", "title", "genre", "touch", "lead", "items"):
        if not s.get(k):
            raise SpecError(f"{where}: missing {k}")
    if not SLUG.match(s["slug"]) or s["slug"] != path.stem:
        raise SpecError(f"{where}: slug must be lowercase ascii-with-hyphens and equal the file name")
    if s["genre"] not in GENRE_BY_SLUG:
        raise SpecError(f"{where}: unknown genre {s['genre']}")
    if s["touch"] not in TOUCH_BY_SLUG:
        raise SpecError(f"{where}: unknown touch {s['touch']}")
    if len(s["items"]) % per:
        raise SpecError(f"{where}: {len(s['items'])} items is not a multiple of {per} (grid {cols}x{rows})")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", s["key"]):
        raise SpecError(f"{where}: key must look like #FF00FF")
    seen = set()
    for it in s["items"]:
        if len(it) < 3 or not all(isinstance(x, str) and x for x in it[:3]):
            raise SpecError(f"{where}: bad item {it!r}")
        if not SLUG.match(it[0]):
            raise SpecError(f"{where}: bad item id {it[0]!r}")
        if it[0] in seen:
            raise SpecError(f"{where}: duplicate item id {it[0]}")
        seen.add(it[0])
    return s


def load_specs(only: list[str] | None = None) -> list[dict]:
    out = []
    for p in sorted(SPECS.glob("*.json")):
        if only and p.stem not in only:
            continue
        out.append(load_spec(p))
    return out


def item_id(spec: dict, suffix: str) -> str:
    return f"{spec['slug']}-{suffix}"


def sheets_of(spec: dict) -> list[dict]:
    cols, rows = spec["grid"]
    per = cols * rows
    return [{"file": f"{spec['slug']}__{k + 1:02d}", "idx": k, "items": spec["items"][k * per:(k + 1) * per]} for k in range(len(spec["items"]) // per)]


def item_title(spec: dict, it: list[str]) -> str:
    return spec["title_fmt"].format(ja=it[1], subject=spec["subject"])


def item_record(spec: dict, it: list[str], w: int, h: int) -> dict:
    touch = TOUCH_BY_SLUG[spec["touch"]]
    title = item_title(spec, it)
    desc = it[3] if len(it) > 3 and it[3] else f"{title}のイラスト。{touch[1]}のタッチ。"
    # a series of one character shares all its tags; a mixed series (twelve different animals, a set of icons) shares only its first four, broad tags,
    # and every other tag must appear in the item's own phrase - otherwise a search for "ひつじ" finds the cat of the Santa set
    own = spec["tags"] if spec["subject"] else [t for n, t in enumerate(spec["tags"]) if n < 4 or t in it[1] or t in item_title(spec, it)]
    tags = list(dict.fromkeys([*own, spec["subject"] or spec["title"], it[1], touch[1], GENRE_BY_SLUG[spec["genre"]][1]]))
    return {"id": item_id(spec, it[0]), "file": f"{item_id(spec, it[0])}.webp", "title": title, "desc": desc, "tags": [t for t in tags if t], "w": w, "h": h}


# ---------------------------------------------------------------- brief
HEADER = """# Image generation order (みんなのイラスト) - use your built-in image generation for every sheet below.

Reply in English at the end: a table of the files written (actual pixel size) and an honest critique (which sheets you regenerated and why).

HOW TO WORK
- Write each finished sheet as a PNG into the folder `{dir}` (it already exists; do NOT create folders elsewhere). File name = exactly the name given for the sheet. If a write is denied, say so.
- Image size: 1536x1024 (landscape). Do not edit any other file. Do not commit.
- Make each sheet one image generation call; look at the result; REGENERATE (at most once per sheet) only for content problems: wrong or missing items, illustrations touching each other or the border, a different character design inside the sheet, text/letters, malformed hands/limbs.

RULES FOR EVERY SHEET
- A grid of equal cells, left-to-right then top-to-bottom, exactly the number of illustrations stated, each one a SEPARATE complete illustration (never a scene that spans cells).
- BACKGROUND: plain pure WHITE (#FFFFFF), edge to edge, flat: no vignette, no glow, no halo, no floor line, no cast shadow, no gradient, no paper texture, no sparkles or confetti floating on the background. Do NOT use any coloured or dark background (the generator turns those into a dark vignette with a glowing halo, which cannot be cut out). Do not post-process the picture in any way: no recolouring, flood-fill, cropping or resizing. Save EXACTLY the image the generator returned (copy that file unchanged to the target name); the site's own tool removes the white background afterwards.
- Because the background is removed from white, the illustrations must have a CLEAR, CLOSED, darker outline all around, and light parts inside (white fur, cream, snow, eggshell, paper) must be a warm cream (#FFF6E0) or a tinted colour, never pure #FFFFFF, so they can be told apart from the background. Tiny pure-white eye highlights are fine.
- Each illustration is centred in its cell and fills about 80% of the cell height or width, with a clear empty band (at least 8% of the cell) on every side: nothing touches the sheet border, a cell border or another illustration. No grid lines, no cell frames.
- ABSOLUTELY NO text, letters, numbers, logos, watermarks or signatures anywhere (blank signs/cards/banners are fine).
- All illustrations are ORIGINAL: never imitate an existing character, brand, mascot, artist or anime style. No real people. Friendly and safe for all ages.
- Within one sheet, and across sheets of the same series, the character/design must stay identical (same proportions, colours, face) - only pose, expression and props change.
- Every pose/expression must be clear and readable at thumbnail size; faces (when present) show a definite cute emotion.

"""


def sheet_prompt(spec: dict, sheet: dict) -> str:
    cols, rows = spec["grid"]
    touch = TOUCH_BY_SLUG[spec["touch"]]
    n = len(sheet["items"])
    lines = [f"## Sheet `{sheet['file']}.png`  ({cols} columns x {rows} rows = {n} illustrations; plain white background)",
             f"Series: {spec['title']} ({spec['genre']}). Subject: {(spec.get('sheet_subjects') or [spec['subject_en'] or spec['title']] * 99)[sheet.get('idx', 0)]}",
             f"Art touch ({spec['touch']}): {touch[3]}", "Illustrations in order:"]
    for i, it in enumerate(sheet["items"], 1):
        lines.append(f"  {i}. {it[2]}")
    return "\n".join(lines) + "\n"


PRIORITY = (("shichigosan", 9), ("eto", 10), ("nenga", 10), ("newyear", 10), ("coloring-newyear", 10), ("christmas", 15), ("winter", 15), ("setsubun", 22), ("halloween", 30))


def priority_of(spec: dict) -> int:
    """Lower is drawn first: the season that is coming, then the rest; a spec may also carry its own "priority"."""
    if "priority" in spec:
        return int(spec["priority"])
    for prefix, n in PRIORITY:
        if spec["slug"].startswith(prefix):
            return n
    if spec["genre"] in ("people", "work", "school", "life"):      # people series: after the New Year and Christmas sets and the first animals
        return 25
    return 40


def pending_sheets(specs: list[dict], sheets_dir: Path) -> list[tuple[dict, dict]]:
    specs = sorted(specs, key=lambda x: (priority_of(x), x["slug"]))
    out = []
    for s in specs:
        lib = LIBRARY / s["slug"]
        for sh in sheets_of(s):
            ids = [item_id(s, it[0]) for it in sh["items"]]
            if all((lib / f"{i}.webp").exists() for i in ids):
                continue
            if (sheets_dir / f"{sh['file']}.png").exists():
                continue
            out.append((s, sh))
    return out


def cmd_brief(a) -> None:
    sheets_dir = Path(a.sheets_dir)
    only = a.series.split(",") if a.series else None
    pend = pending_sheets(load_specs(only), sheets_dir)
    if a.limit:
        pend = pend[:a.limit]
    if not pend:
        sys.exit("nothing to draw")
    rel = sheets_dir.relative_to(ROOT.parent).as_posix() if sheets_dir.is_relative_to(ROOT.parent) else sheets_dir.as_posix()
    sheets_dir.mkdir(parents=True, exist_ok=True)
    text = HEADER.format(dir=rel) + f"SHEETS TO PRODUCE ({len(pend)}):\n\n" + "\n".join(sheet_prompt(s, sh) for s, sh in pend)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"brief for {len(pend)} sheets -> {a.out}")


def cmd_batches(a) -> None:
    """Split everything still to be drawn into one brief per worker (w1.md, w2.md, ...), most urgent first, dealt out round-robin."""
    sheets_dir = Path(a.sheets_dir)
    pend = pending_sheets(load_specs(a.series.split(",") if a.series else None), sheets_dir)[: a.workers * a.per]
    if not pend:
        sys.exit("nothing to draw")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rel = sheets_dir.relative_to(ROOT.parent).as_posix() if sheets_dir.is_relative_to(ROOT.parent) else sheets_dir.as_posix()
    sheets_dir.mkdir(parents=True, exist_ok=True)
    groups: list[list] = [[] for _ in range(a.workers)]
    for i, item in enumerate(pend):
        groups[i % a.workers].append(item)
    for n, g in enumerate(groups, 1):
        if g:
            (out / f"{a.prefix}{n}.md").write_text(HEADER.format(dir=rel) + f"SHEETS TO PRODUCE ({len(g)}):\n\n" + "\n".join(sheet_prompt(s, sh) for s, sh in g), encoding="utf-8")
            print(f"{a.prefix}{n}.md: {len(g)} sheets: " + ", ".join(sh["file"] for _, sh in g))


# ---------------------------------------------------------------- ingest
def write_series_json(spec: dict) -> int:
    lib = LIBRARY / spec["slug"]
    from PIL import Image
    items = []
    for it in spec["items"]:
        f = lib / f"{item_id(spec, it[0])}.webp"
        if f.exists() and it[0] not in spec["exclude"]:
            with Image.open(f) as im:
                items.append(item_record(spec, it, im.width, im.height))
    if not items:
        return 0
    old = {}
    if (lib / "series.json").exists():
        old = json.loads((lib / "series.json").read_text(encoding="utf-8"))
    data = {"added": old.get("added") or date.today().isoformat(), "slug": spec["slug"], "title": spec["title"], "genre": spec["genre"], "touch": spec["touch"], "lead": spec["lead"], "tags": spec["tags"],
            "subject": spec["subject"], "season": spec["season"], "planned": len(spec["items"]), "items": items}
    (lib / "series.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(items)


def cmd_ingest(a) -> None:
    sheets_dir = Path(a.sheets_dir)
    specs = load_specs(a.series.split(",") if a.series else None)
    retry, done = [], 0
    for s in specs:
        lib = LIBRARY / s["slug"]
        touched = False
        for sh in sheets_of(s):
            ids = [item_id(s, it[0]) for it in sh["items"]]
            png = sheets_dir / f"{sh['file']}.png"
            if all((lib / f"{i}.webp").exists() for i in ids) or not png.exists():
                continue
            cols, rows = s["grid"]
            pieces, info = sheetkit.slice_sheet(png, cols, rows, s["key"], max_side=1024, holes=bool(s["holes"]))
            bad = [f"#{p.index + 1}: {'; '.join(p.problems)}" for p in pieces if any("edge" in q or "key colour" in q or "very little" in q for q in p.problems)]
            if info.get("count_problem") or bad:
                retry.append({"sheet": sh["file"], "problem": info.get("count_problem") or "; ".join(bad)})
                print(f"REJECT {sh['file']}: {retry[-1]['problem']}")
                continue
            lib.mkdir(parents=True, exist_ok=True)
            sheetkit.save_pieces(pieces, lib, names=ids)
            done += 1
            touched = True
            print(f"ok {sh['file']} -> {len(pieces)} items")
        if touched or (lib / "series.json").exists():
            write_series_json(s)
    (sheets_dir / "retry.json").write_text(json.dumps(retry, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ingested {done} sheets; {len(retry)} rejected (see retry.json)")


# ---------------------------------------------------------------- recover the generator's own files
def cmd_recover(a) -> None:
    """The image generator keeps every picture it returns under ~/.codex/generated_images/<session>/.  When a worker saved a post-processed copy into the
    inbox, find the unmodified original (the one whose pixels match the copy wherever the copy is not the key colour) and put it in the inbox instead."""
    import numpy as np
    from PIL import Image
    gen = Path.home() / ".codex" / "generated_images"
    inbox = Path(a.sheets_dir)
    since = datetime.now().timestamp() - a.hours * 3600
    raws = [f for f in gen.glob("*/*.png") if f.stat().st_mtime >= since]
    keep = inbox.parent / "processed"
    keep.mkdir(exist_ok=True)
    cache: dict[Path, np.ndarray] = {}
    done = 0

    def dark(arr):          # the outlines survive any background clean-up, so compare where both pictures are dark
        return (arr.astype(np.int32) @ np.array([299, 587, 114]) // 1000) < 100

    for f in sorted(inbox.glob("*__*.png")):
        cur = np.asarray(Image.open(f).convert("RGB"))
        keyed = (np.abs(cur.astype(int) - np.array([255, 0, 255])).sum(axis=2) < 30)
        content = ~keyed
        if content.sum() < 5000:
            continue
        cd = dark(cur) & content
        best, best_score = None, 0.0
        for r in raws:
            if r not in cache:
                cache[r] = np.asarray(Image.open(r).convert("RGB"))
            arr = cache[r]
            if arr.shape != cur.shape:
                continue
            rd = dark(arr)
            score = float((cd & rd).sum() / max(1, (cd | rd & content).sum()))
            if score > best_score:
                best, best_score = r, score
        if best is None or best_score < 0.5:
            print(f"{f.name}: no matching original (best {best_score:.2f})")
            continue
        if best.read_bytes() == f.read_bytes():
            continue
        shutil.copyfile(f, keep / f.name)
        shutil.copyfile(best, f)
        done += 1
        print(f"{f.name}: replaced by the generator's original {best.parent.name}/{best.name} (match {best_score:.2f})")
    print(f"recovered {done} originals; the post-processed copies are in {keep}")


# ---------------------------------------------------------------- review: a second pair of eyes (Codex looks at numbered contact sheets)
def cmd_review_prep(a) -> None:
    """For every series that has drawn items: a numbered contact sheet (review/<slug>.png, 4 x 3, number in the corner, magenta behind so that
    transparent parts show) and one brief that lists, per sheet, number -> title and the English phrase the generator was given."""
    from PIL import Image, ImageDraw
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    only = a.series.split(",") if a.series else None
    lines = []
    made = []
    for s in load_specs(only):
        lib = LIBRARY / s["slug"]
        if not (lib / "series.json").exists():
            continue
        reviewed = out / f"{s['slug']}.done"
        if reviewed.exists() and not a.force:
            continue
        have = [(n, it) for n, it in enumerate(s["items"], 1) if (lib / f"{item_id(s, it[0])}.webp").exists()]
        cell, cols = 260, 4
        rows = -(-len(have) // cols)
        sheet = Image.new("RGB", (cols * cell, rows * cell), (255, 0, 255))
        d = ImageDraw.Draw(sheet)
        for k, (n, it) in enumerate(have):
            im = Image.open(lib / f"{item_id(s, it[0])}.webp").convert("RGBA")
            im.thumbnail((cell - 24, cell - 24))
            cx, cy = (k % cols) * cell, (k // cols) * cell
            sheet.paste(im, (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2), im)
            d.rectangle([cx + 2, cy + 2, cx + 40, cy + 26], fill=(0, 0, 0))
            d.text((cx + 8, cy + 8), str(n), fill=(255, 255, 255))
        sheet.save(out / f"{s['slug']}.png")
        made.append(s["slug"])
        lines.append(f"## {s['slug']}  ({s['title']}; touch {s['touch']}; image: {s['slug']}.png)")
        lines.append(f"Intended character: {(s.get('sheet_subjects') or [s['subject_en']])[0][:400]}")
        for n, it in have:
            lines.append(f"  {n}. {it[1]} -- {it[2]}")
        lines.append("")
    (out / "review_brief.md").write_text(REVIEW_HEADER + "\n".join(lines), encoding="utf-8")
    print(f"review sheets for {len(made)} series in {out}")
    print(" ".join(f"-i {Path(out) / (m + '.png')}" for m in made))


REVIEW_HEADER = """# Review task: look at the attached contact sheets and report defects (you may NOT edit any picture or file except the one result file below)

Each attached image is one illustration series on a MAGENTA background (the magenta is only there so that transparent parts show; it is not part of the art). Items are numbered in the top-left corner. The list below says, per series, what each number was supposed to show.
For EVERY item judge:
 - match: does the drawing show the described pose/scene? (a wrong or different pose = mismatch)
 - defects: missing body parts or clothes that became transparent (pale/white clothes 'eaten' by the background), ghost-like faded drawing, extra or merged people, cut-off limbs, strange hands or too many fingers, wrong face (blank face where a face is expected, or a face where 'faceless' is expected), text/letters in the picture, a different character than the rest of the series, a plain blob instead of an illustration, anything that would embarrass a free-illustration site.
Write the result as JSON to `sokuhou-sites/docs/minna_sheets/review/result.json`:
{"series": {"<slug>": {"bad": [{"n": 6, "why": "short reason", "kind": "defect|mismatch|ghost|blob|overlap"}], "ok_count": 10, "notes": "one line"}}}
List only items that should be removed or redrawn (clear problems). Do not nitpick style. A pose that is slightly different from the English phrase but a good picture is NOT bad; a picture that cannot be used with its Japanese title IS a mismatch.
Be strict about ghosting (see-through or faded bodies) and white-on-white losses, and about blobs.
Reply in English with a one-line summary per series.

"""


def cmd_review_apply(a) -> None:
    """Take the review result (json) and hide the bad items: their suffixes go into the spec's "exclude" list and series.json is rewritten.  Reviewed series get a
    marker so review-prep does not offer them again."""
    res = json.loads(Path(a.result).read_text(encoding="utf-8"))["series"]
    out = Path(a.out)
    total = 0
    for slug, r in res.items():
        path = SPECS / f"{slug}.json"
        if not path.exists():
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        ex = set(spec.get("exclude", []))
        for b in r.get("bad", []):
            n = int(b["n"])
            if 1 <= n <= len(spec["items"]):
                ex.add(spec["items"][n - 1][0])
                total += 1
        spec["exclude"] = sorted(ex)
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        write_series_json(load_spec(path))
        (out / f"{slug}.done").write_text("reviewed", encoding="utf-8")
    print(f"hid {total} items in {len(res)} series")


def cmd_status(a) -> None:
    specs = load_specs()
    total_items = made = 0
    by_genre: dict[str, int] = {}
    by_touch: dict[str, int] = {}
    for s in specs:
        lib = LIBRARY / s["slug"]
        n = sum(1 for it in s["items"] if (lib / f"{item_id(s, it[0])}.webp").exists())
        total_items += len(s["items"])
        made += n
        by_genre[s["genre"]] = by_genre.get(s["genre"], 0) + n
        by_touch[s["touch"]] = by_touch.get(s["touch"], 0) + n
    print(f"{len(specs)} series planned, {total_items} items planned, {made} drawn")
    print("by genre:", by_genre)
    print("by touch:", by_touch)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("status", cmd_status), ("brief", cmd_brief), ("ingest", cmd_ingest), ("recover", cmd_recover), ("batches", cmd_batches), ("review-prep", cmd_review_prep), ("review-apply", cmd_review_apply)):
        p = sub.add_parser(name)
        p.add_argument("--series")
        p.add_argument("--sheets-dir", default=str(DEFAULT_SHEETS / "inbox"))
        if name == "review-prep":
            p.add_argument("--out", required=True)
            p.add_argument("--force", action="store_true")
        if name == "review-apply":
            p.add_argument("--out", required=True)
            p.add_argument("--result", required=True)
        if name == "batches":
            p.add_argument("--out", required=True)
            p.add_argument("--workers", type=int, default=5)
            p.add_argument("--per", type=int, default=8)
            p.add_argument("--prefix", default="b")
        if name == "recover":
            p.add_argument("--hours", type=float, default=24)
        if name == "brief":
            p.add_argument("--out", required=True)
            p.add_argument("--limit", type=int)
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    try:
        main()
    except SpecError as e:
        sys.exit(f"spec error: {e}")
