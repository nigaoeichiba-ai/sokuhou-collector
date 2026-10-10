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
- Cut generic praise that fits any gift and sounds machine-made: 上質, こだわり, 感謝の気持ちを伝える, 心に残る, 大切です/大切にしたい repeated. Say the concrete detail (what it is, when it is used, what to check) or leave the sentence out.
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


AI_TELLS = ("上質", "こだわり", "感謝の気持ち", "気持ちを伝え", "心に残る", "大切です")   # stock phrases that fit any gift and read as machine-made when they repeat across pages


def style_score(text: str) -> int:
    """Higher = the wording is more in need of a rewrite."""
    s = text.count("やすい") * 2 + text.count("やすいです。") * 3 + sum(text.count(w) for w in ("寄り添", "そっと", "さりげな"))
    s += sum(len(quality.PARTICLE_COMMA.findall(x)) >= 3 for x in re.split(r"(?<=。)", text)) * 4
    s += sum(len(x) > quality.MAX_SENTENCE for x in re.split(r"(?<=。)", text)) * 3
    s += sum(text.count(w) * 5 for w in quality.INTERNAL_WORDS + quality.YOUNG_TONE)
    s += sum(text.count(w) * 3 for w in AI_TELLS)
    return s


def issues_of(text: str, page_total: int = 0) -> list[str]:
    """What is off in one field, in words Codex can act on (empty = leave the field alone).  `page_total`: the 「〜やすい」 count of the whole page it belongs to."""
    out = []
    n = text.count("やすい")
    if n > 1:
        out.append(f"「〜やすい」が{n}回: 具体的な言い方に替える")
    elif n == 1 and page_total > quality.MAX_YASUI:
        out.append(f"このページ全体で「〜やすい」が{page_total}回あります(4回以下にしたい): この文の「〜やすい」を、具体的な言い方に替える")
    for w in ("寄り添", "そっと", "さりげな"):
        if w in text:
            out.append(f"「{w}」を普通の言葉に")
    for s in re.split(r"(?<=。)", text):
        if len(quality.PARTICLE_COMMA.findall(s)) >= 3 and len(s) < 80:
            out.append(f"読点が多すぎる文: {s[:24]}…")
        if len(s) > quality.MAX_SENTENCE:
            out.append(f"長すぎる文({len(s)}字): {s[:24]}…")
    out += [f"言葉「{w}」を使わない" for w in quality.INTERNAL_WORDS + quality.YOUNG_TONE if w in text]
    out += [f"決まり文句「{w}」: どんな贈り物にも当てはまる言い方なので、具体的な事実や場面に替えるか、文ごと削る" for w in AI_TELLS if w in text]
    return out


def ranked(kind: str) -> list[tuple[int, str]]:
    _, items = load(kind)
    key = KINDS[kind][2]
    return sorted(((style_score(" ".join(fields(kind, it).values())), key(it)) for it in items), reverse=True)


def accept(old: str, new: str, key: str) -> list[str]:
    """Why a rewritten field must NOT replace the old one (empty = accept)."""
    why = []
    if new.strip() == old.strip():
        return ["unchanged"]
    if style_score(new) >= style_score(old):
        why.append(f"not better (style score {style_score(new)} vs {style_score(old)})")
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
    payload, reasons = {}, []
    for k in order:                                   # only the fields that have something wrong, and what it is
        flds = fields(kind, by_key[k])
        total = sum(t.count("やすい") for t in flds.values())
        flagged = {p: t for p, t in flds.items() if issues_of(t, total)}
        if flagged:
            payload[k] = flagged
            reasons += [f"- {k} / {p}: " + " ; ".join(issues_of(t, total)) for p, t in flagged.items()]
    text = (f"Rewrite task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). "
            f"Do not edit anything else.\n\nSITE: \"よろこぶプレゼント\", a Japanese gift-recommendation site. Below are fields of {len(payload)} existing {kind} pages that have a wording problem "
            f"(listed under FLAGGED), as JSON {{page key: {{field path: text}}}}. Fix ONLY the flagged problem in each field with the SMALLEST edit that makes it read as natural, calm, concrete Japanese; "
            f"keep every other word and the order as they are. Do not add a new phrase, claim, example or product that the field does not already contain, and never add filler such as "
            f"a closing sentence. Write the same structure back: {{page key: {{field path: corrected text}}}} with exactly the same page keys and field paths (a field you judge fine stays unchanged).\n"
            f"{BRIEF_RULES}\n{factory.RULES}\n\nFLAGGED:\n" + "\n".join(reasons) + f"\n\nTEXTS:\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n")
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


def _changed(kind: str, before: Path) -> dict[str, dict[str, list[str]]]:
    """{page key: {field path: [text before the rewrite, text now]}} for the fields that differ from the `before` copy of the content file."""
    f, inner, key, _ = KINDS[kind]
    old = json.loads(before.read_text(encoding="utf-8"))
    old_items = old[inner] if isinstance(old, dict) else old
    old_by = {key(it): it for it in old_items}
    _, items = load(kind)
    out: dict[str, dict[str, list[str]]] = {}
    for it in items:
        k = key(it)
        if k not in old_by:
            continue
        a, b = fields(kind, old_by[k]), fields(kind, it)
        diff = {p: [a[p], b[p]] for p in b if p in a and a[p] != b[p]}
        if diff:
            out[k] = diff
    return out


REVIEW_RULES = """
You are the second reader of a rewrite. For each field below you get the ORIGINAL wording and the REWRITTEN wording of a Japanese gift-site text.
Judge the REWRITTEN one as a careful native editor would:
- Is it grammatical, natural written Japanese? Typical failures of a mechanical rewrite: 「〜やすい」 swapped for 「〜できる」 where the sentence no longer works (e.g. 「ものが扱えます」, 「受け取ってもらえます」 with the wrong subject), a noun that cannot take the verb, a changed meaning, a stiffer or odder phrase than the original, a doubled word.
- Does it keep the original meaning, every number and every kind of product, and add nothing new?
If it is fine, answer "ok". If not, answer with ONE corrected text: the best natural wording that keeps the meaning, keeps the length within 70-130% of the original, uses 「〜やすい」 at most once, and has no comma after every short phrase. You may return the original wording if it was better.
Answer as JSON {page key: {field path: "ok" or "corrected text"}} with exactly the same keys and paths.
"""


def review_brief(kind: str, before: Path, out: Path, answer: Path) -> None:
    ch = _changed(kind, before)
    payload = {k: {p: {"original": a, "rewritten": b} for p, (a, b) in d.items()} for k, d in ch.items()}
    n = sum(len(d) for d in ch.values())
    text = (f"Review task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). Do not edit anything else.\n"
            f"{REVIEW_RULES}\nFIELDS ({n}):\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"review brief for {n} fields of {len(ch)} {kind} pages written to {out}; Codex must write {answer}")


def review_merge(kind: str, before: Path, answer: Path) -> tuple[int, int, list[str]]:
    """Apply the second reader's corrections: a corrected text replaces the current one when it passes the gate against the ORIGINAL text; 'ok' keeps the rewrite."""
    ch = _changed(kind, before)
    data, items = load(kind)
    key = KINDS[kind][2]
    by_key = {key(it): it for it in items}
    verdict = json.loads(answer.read_text(encoding="utf-8"))
    fixed = kept = 0
    notes: list[str] = []
    for k, flds in verdict.items():
        for path, v in flds.items():
            if k not in ch or path not in ch[k]:
                notes.append(f"{k}.{path}: not a changed field")
                continue
            orig, now = ch[k][path]
            if v.strip().lower() == "ok" or v.strip() == now.strip():
                kept += 1
                continue
            why = [w for w in accept(orig, v, f"{k}.{path}") if not w.startswith("not better")]
            if why:
                notes.append(f"{k}.{path}: correction refused ({'; '.join(why)}); the rewrite stays")
                continue
            _set(by_key[k], path, v)
            fixed += 1
    if fixed:
        f = KINDS[kind][0]
        raw = (CONTENT / f).read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        out = json.dumps(data, ensure_ascii=False, indent=1).replace("\n", nl) + (nl if raw.endswith("\n") else "")
        (CONTENT / f).write_bytes(out.encode("utf-8"))
    return fixed, kept, notes


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
    rb = sub.add_parser("review-brief")
    rb.add_argument("kind", choices=sorted(KINDS))
    rb.add_argument("--before", type=Path, required=True)
    rb.add_argument("--out", type=Path, required=True)
    rb.add_argument("--answer", type=Path, required=True)
    rm = sub.add_parser("review-merge")
    rm.add_argument("kind", choices=sorted(KINDS))
    rm.add_argument("--before", type=Path, required=True)
    rm.add_argument("answer", type=Path)
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
    if a.cmd == "review-brief":
        review_brief(a.kind, a.before, a.out, a.answer)
        return 0
    if a.cmd == "review-merge":
        fixed, kept, notes = review_merge(a.kind, a.before, a.answer)
        print(f"corrected {fixed} fields, kept {kept} rewrites")
        for n in notes[:60]:
            print(" ", n)
        return 0
    done, kept, notes = merge(a.kind, a.answer)
    print(f"rewrote {done} fields, kept {kept} old ones")
    for n in notes[:60]:
        print(" ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
