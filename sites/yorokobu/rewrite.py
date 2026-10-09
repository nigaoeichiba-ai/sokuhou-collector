"""Rewrites the wording of EXISTING pages for natural Japanese, field by field, with Codex doing the writing and this module deciding what is accepted.

    python -m sites.yorokobu.rewrite status
    python -m sites.yorokobu.rewrite brief pairs --n 12 --out BRIEF.md --answer ANSWER.json     # the 12 worst by the style score
    python -m sites.yorokobu.rewrite merge pairs ANSWER.json

Why field by field: the pages are fine in substance (concrete scenes, cautions); what the owner found off is the wording (「〜やすい」 in 797 places, the same endings,
commas after every phrase).  A rewritten field replaces the old one only when it keeps the meaning's anchors (every number, every kind of product named), stays within
70-130% of the old length, and passes quality.language_problems; otherwise the old text stays.  Titles, slugs, queries and keywords are never touched.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import factory, quality  # noqa: E402

CONTENT = ct.CONTENT_DIR
# kind -> (file, path to the list inside the file or None, key of an item, text paths: "*" stands for every index)
KINDS = {
    "pairs": ("pairs.json", "pairs", lambda x: f"{x['occasion']}-{x['recipient']}", ["lead", "reasons.*", "how_to_choose.*"]),
    "themes": ("themes.json", "themes", lambda x: x["slug"], ["lead", "reasons.*", "how_to_choose.*", "ideas.*.why"]),
    "guides": ("guides.json", "guides", lambda x: x["occasion"], ["intro", "sections.*.body", "faq.*.a", "checklist.*"]),
    "articles": ("articles.json", "articles", lambda x: x["slug"], ["lead", "sections.*.body", "faq.*.a", "checklist.*"]),
    "occasions": ("occasions.json", "occasions", lambda x: x["slug"], ["blurb", "timing", "tips.*", "avoid.*"]),
    "recipients": ("recipients.json", "recipients", lambda x: x["slug"], ["blurb", "likes.*", "avoid.*"]),
}
BRIEF_RULES = """
STYLE (adult readers who choose a gift calmly; polite です・ます; natural written Japanese like a careful editor, never like a template):
- Keep the meaning, the scenes and every number exactly. Do not add facts, products, claims or advice that the original does not contain; do not drop any.
- Cut the stock phrases: at most 4 uses of 「〜やすい」 in one item and at most 2 sentences ending 「〜やすいです。」. Say the concrete thing instead (分けられる, 持ち帰れる, 保管できる, 迷わない, 傷みにくい ...). Also avoid 寄り添う, そっと, さりげなく, 負担 where a plain word works.
- Vary how sentences start and end; do not end three sentences in a row the same way. Most sentences 35-75 characters; split anything over 90.
- A comma (、) only where the meaning breaks or in a list of three or more; never after every short phrase.
- Do not use: 切り口, ソムリエ, ナビゲーター, 見立て, ギフトマップ, コンシェルジュ, ガチャ, ね/よ endings, 「よく読まれている」「人気」.
- Each field keeps roughly its length (70-130% of the original).
"""


def _expand(obj, path: str):
    """Yield (concrete path, text) for a path pattern like 'sections.*.body'."""
    head, _, rest = path.partition(".")
    if head == "*":
        if isinstance(obj, list):
            for i, v in enumerate(obj):
                yield from _expand_sub(v, str(i), rest)
        return
    if isinstance(obj, dict) and head in obj:
        yield from _expand_sub(obj[head], head, rest)


def _expand_sub(value, name: str, rest: str):
    if not rest:
        if isinstance(value, str):
            yield name, value
        return
    for p, t in _expand(value, rest):
        yield f"{name}.{p}", t


def fields(kind: str, item: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for pat in KINDS[kind][3]:
        for p, t in _expand(item, pat):
            out[p] = t
    return out


def _set(item: dict, path: str, text: str) -> None:
    node = item
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(parts[-1])] = text
    else:
        node[parts[-1]] = text


def load(kind: str) -> tuple[dict | list, list[dict]]:
    f, inner, _, _ = KINDS[kind]
    data = json.loads((CONTENT / f).read_text(encoding="utf-8"))
    return data, (data[inner] if isinstance(data, dict) else data)


def style_score(text: str) -> int:
    """Higher = the wording is more in need of a rewrite."""
    s = text.count("やすい") * 2 + text.count("やすいです。") * 3 + sum(text.count(w) for w in ("寄り添", "そっと", "さりげな"))
    s += sum(len(quality.PARTICLE_COMMA.findall(x)) >= 3 for x in re.split(r"(?<=。)", text)) * 4
    s += sum(len(x) > quality.MAX_SENTENCE for x in re.split(r"(?<=。)", text)) * 3
    s += sum(text.count(w) * 5 for w in quality.INTERNAL_WORDS + quality.YOUNG_TONE)
    return s


def ranked(kind: str) -> list[tuple[int, str]]:
    _, items = load(kind)
    key = KINDS[kind][2]
    return sorted(((style_score(" ".join(fields(kind, it).values())), key(it)) for it in items), reverse=True)


def accept(old: str, new: str, key: str) -> list[str]:
    """Why a rewritten field must NOT replace the old one (empty = accept)."""
    why = []
    if new.strip() == old.strip():
        return ["unchanged"]
    if not 0.7 * len(old) <= len(new) <= 1.3 * len(old):
        why.append(f"length {len(new)} vs {len(old)}")
    if sorted(re.findall(r"[0-9]+", old)) != sorted(re.findall(r"[0-9]+", new)):
        why.append("numbers differ")
    why += quality.language_problems(new, key)
    why += [f"forbidden {w}" for w in quality._words(new) if w not in old]
    return why


def brief(kind: str, n: int, out: Path, answer: Path, offset: int = 0) -> None:
    _, items = load(kind)
    key = KINDS[kind][2]
    order = [k for sc, k in ranked(kind) if sc > 0][offset:offset + n]
    by_key = {key(it): it for it in items}
    payload = {k: fields(kind, by_key[k]) for k in order}
    text = (f"Rewrite task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). "
            f"Do not edit anything else.\n\nSITE: \"よろこぶプレゼント\", a Japanese gift-recommendation site. Below are the texts of {len(order)} existing {kind} pages as JSON "
            f"{{page key: {{field path: text}}}}. Rewrite EVERY field's wording so that it reads as natural, calm, concrete Japanese, and write the same structure back: "
            f"{{page key: {{field path: rewritten text}}}} with exactly the same page keys and field paths.\n{BRIEF_RULES}\n{factory.RULES}\n\nTEXTS:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=1)}\n")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"brief for {len(order)} {kind} written to {out}; Codex must write {answer}")


def merge(kind: str, answer: Path, write: bool = True) -> tuple[int, int, list[str]]:
    data, items = load(kind)
    key = KINDS[kind][2]
    by_key = {key(it): it for it in items}
    new = json.loads(answer.read_text(encoding="utf-8"))
    done = kept = 0
    notes: list[str] = []
    for k, flds in new.items():
        if k not in by_key:
            notes.append(f"{k}: unknown page")
            continue
        item = by_key[k]
        old = fields(kind, item)
        for path, text in flds.items():
            if path not in old:
                notes.append(f"{k}.{path}: unknown field")
                continue
            why = accept(old[path], text, f"{k}.{path}")
            if why:
                kept += 1
                if why != ["unchanged"]:
                    notes.append(f"{k}.{path}: kept old ({'; '.join(why)})")
                continue
            _set(item, path, text)
            done += 1
    if write and done:
        f = KINDS[kind][0]
        raw = (CONTENT / f).read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"      # the files use one space of indent, no final newline and (pairs) CRLF; keep that so a rewrite shows only the changed text
        out = json.dumps(data, ensure_ascii=False, indent=1).replace("\n", nl) + (nl if raw.endswith("\n") else "")
        (CONTENT / f).write_bytes(out.encode("utf-8"))
    return done, kept, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    b = sub.add_parser("brief")
    b.add_argument("kind", choices=sorted(KINDS))
    b.add_argument("--n", type=int, default=12)
    b.add_argument("--offset", type=int, default=0)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--answer", type=Path, required=True)
    m = sub.add_parser("merge")
    m.add_argument("kind", choices=sorted(KINDS))
    m.add_argument("answer", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        for kind in KINDS:
            r = ranked(kind)
            print(f"{kind}: {len(r)} pages, {sum(1 for s, _ in r if s > 0)} need work, worst {r[0] if r else '-'}")
        return 0
    if a.cmd == "brief":
        brief(a.kind, a.n, a.out, a.answer, a.offset)
        return 0
    done, kept, notes = merge(a.kind, a.answer)
    print(f"rewrote {done} fields, kept {kept} old ones")
    for n in notes[:60]:
        print(" ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
