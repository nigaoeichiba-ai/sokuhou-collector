"""One-off tool for the 2026-10-12 copy review: the series titles, lead paragraphs and item names live in specs/*.json (and are copied into library/*/series.json by the factory).

    python -m sites.minna.copypass export DIR [--chunk 18]     # DIR/in_01.json ... : {"slug", "title", "subject", "lead", "items": [[suffix, japanese phrase], ...]} per spec
    python -m sites.minna.copypass apply DIR                   # validate DIR/out_NN.json against in_NN.json, write the new wording into the specs and rebuild series.json

The reviewer (Codex) may change only the wording: slugs, item ids, item counts and order stay.  `apply` refuses a record that breaks the rules of docs/MINNA_COPY_STYLE.md
(AI named, a long or comma-heavy lead, a comma inside an item name, an item added or dropped) and says why; the rest is applied.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from sites.minna import factory  # noqa: E402

MAX_LEAD = 130
MAX_COMMAS = 2


def export(out: Path, chunk: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    specs = factory.load_specs()
    recs = [{"slug": s["slug"], "title": s["title"], "subject": s["subject"], "lead": s["lead"], "items": [[it[0], it[1]] for it in s["items"]]} for s in specs]
    n = 0
    for k in range(0, len(recs), chunk):
        n += 1
        (out / f"in_{n:02d}.json").write_text(json.dumps(recs[k:k + chunk], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(recs)} specs -> {n} chunk(s) in {out}")
    return n


def problems(old: dict, new: dict) -> list[str]:
    bad = []
    if set(new) != {"slug", "title", "subject", "lead", "items"}:
        return [f"keys {sorted(new)}"]
    if new["slug"] != old["slug"]:
        bad.append("slug changed")
    if [i[0] for i in new["items"]] != [i[0] for i in old["items"]]:
        bad.append("item ids/count/order changed")
    for field in ("title", "subject", "lead"):
        if not isinstance(new[field], str):
            bad.append(f"{field} is not text")
    if bad:
        return bad
    if bool(old["subject"]) != bool(new["subject"]):
        bad.append("subject emptied or filled")
    text = new["title"] + new["lead"] + "".join(i[1] for i in new["items"])
    if re.search(r"\bAI\b|ＡＩ|生成|人が選んで", text):
        bad.append("mentions AI/generation")
    if len(new["lead"]) > MAX_LEAD:
        bad.append(f"lead longer than {MAX_LEAD} characters")
    if new["lead"].count("、") > MAX_COMMAS * max(1, new["lead"].count("。")):
        bad.append("too many commas in the lead")
    if any("、" in i[1] or len(i[1]) > 32 or not i[1].strip() for i in new["items"]):
        bad.append("an item name has a comma, is empty or is too long")
    if re.search(r"(ね|よ|だよ|しよう|してみよう)[。!]", new["lead"]):
        bad.append("childish ending in the lead")
    if "<" in text or ">" in text or "{" in text or "}" in text or '"' in text:
        bad.append("markup or quotes in the text")
    return bad


def apply(src: Path) -> int:
    changed = refused = 0
    for fin in sorted(src.glob("in_*.json")):
        fout = src / fin.name.replace("in_", "out_")
        if not fout.exists():
            print(f"missing {fout.name}")
            continue
        old = {r["slug"]: r for r in json.loads(fin.read_text(encoding="utf-8"))}
        new = {r.get("slug"): r for r in json.loads(fout.read_text(encoding="utf-8"))}
        for slug, o in old.items():
            if slug not in new:
                print(f"  no result for {slug}")
                refused += 1
                continue
            why = problems(o, new[slug])
            if why:
                print(f"  REFUSED {slug}: {'; '.join(why)}")
                refused += 1
                continue
            path = factory.SPECS / f"{slug}.json"
            spec = json.loads(path.read_text(encoding="utf-8"))
            n = new[slug]
            spec["title"], spec["subject"], spec["lead"] = n["title"], n["subject"], n["lead"]
            for it, (_suffix, ja) in zip(spec["items"], n["items"]):
                it[1] = ja
            path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            factory.write_series_json(factory.load_spec(path))
            changed += 1
    print(f"applied {changed}, refused {refused}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "apply"])
    ap.add_argument("dir")
    ap.add_argument("--chunk", type=int, default=18)
    a = ap.parse_args(argv)
    return export(Path(a.dir), a.chunk) and 0 if a.cmd == "export" else apply(Path(a.dir))


if __name__ == "__main__":
    sys.exit(main())
