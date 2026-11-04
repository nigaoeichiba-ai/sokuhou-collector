"""The word dictionary of the kobo (data/word_rules.json): wording the owner or the desk pointed out, one entry per word or sentence pattern.

scan(texts)      marks for a person: where an entry's pattern is in the text (never blocking)
autofix(text)    the mechanical replacements of the entries that have a safe 'auto' (the proofreaders' suggestions are never taken as they are:
                 their fixes sometimes bring the very word back, 2026-11-04)
examples_text()  the words as examples for the proofreaders' and the writer's instructions
add_entry(...)   a new point of the owner or the desk becomes an entry (pattern -> message -> replacements -> optional auto), at once
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

PATH = Path(__file__).parent / "data" / "word_rules.json"


def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def entries() -> list[dict]:
    return load()["entries"]


def scan(texts: list[str]) -> list[dict]:
    out = []
    for e in entries():
        pat, unless = re.compile(e["pattern"]), (re.compile(e["unless"]) if e.get("unless") else None)
        for t in texts:
            mt = pat.search(t)
            if mt and not (unless and unless.search(t)):
                out.append({"code": e["code"], "msg": e["msg"], "detail": t[:90], "id": e["id"], "text": t, "match": mt.group(0)})
    return out


def autofix(text: str) -> tuple[str, int]:
    """Replace line by line; table rows, part marks and the box names are left alone. Returns (text, replacements)."""
    n = 0
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith(("|", "[", "#")) and not line.startswith(("# ", "## ")) or re.match(r"^>\s*(?:ライフハック|豆知識)\s*[:：]", line):
            lines.append(line)
            continue
        for e in entries():
            if e.get("unless") and re.search(e["unless"], line):
                continue
            if e.get("only") and not re.search(e["only"], line):
                continue
            for pat, rep in e.get("auto", []):
                line, k = re.subn(pat, rep, line)
                n += k
        lines.append(line)
    return "\n".join(lines), n


def examples_text() -> str:
    """For an instruction: 「次の語の使い方に気づく」."""
    out = []
    for e in entries():
        rep = "・".join(e["replace"][:3])
        out.append(f"- {e['label']}: {e['msg'].split('。')[0]}。→ {rep}")
    return "\n".join(out)


def add_entry(pattern: str, msg: str, replace: list[str], code: str = "S99", label: str = "", auto: list | None = None, unless: str = "", source: str = "") -> dict:
    d = load()
    re.compile(pattern)
    n = len(d["entries"]) + 1
    e = {"id": f"w{n:02d}", "code": code, "label": label or msg[:20], "pattern": pattern, "msg": msg, "replace": replace, "auto": auto or [], "source": source or f"added {date.today()}"}
    if unless:
        e["unless"] = unless
    d["entries"].append(e)
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return e


LEARNED_PATH: Path | None = None        # private: the models' reasons quote sentences of the drafts, so they stay out of the repository


def learned_path() -> Path:
    if LEARNED_PATH is not None:
        return LEARNED_PATH
    from . import engine
    return engine.home() / "word_learned.json"


def merge_learned(items: list[dict]) -> int:
    """The models' answers (why a word is unnatural, alternatives, date, model) are kept per entry, in a private file; one write, after the runs."""
    if not items:
        return 0
    p = learned_path()
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    n = 0
    for it in items:
        if not it.get("reason"):
            continue
        L = d.setdefault(it["id"], [])
        if any(x["reason"] == it["reason"] for x in L):
            continue
        L.append({"date": str(date.today()), "model": it["model"], "reason": it["reason"], "alternatives": it.get("alternatives", [])})
        del L[:-12]
        n += 1
    if n:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return n
