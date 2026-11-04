"""The material of one piece of writing (素材): confirmed facts, the reader memo, the advice that may be given, the 豆知識 that were confirmed.

A material file is private (it carries the confirmation record): it lives in KOBO_HOME/materials/, never in the repository.

{
  "id": "taifu31", "site": "wadai", "weight": "light" | "mid" | "heavy", "topic": "台風31号と停電の夜",
  "reader_memo": {"reader": ..., "trouble": ..., "feel": ..., "action": ...},
  "facts": [{"text": "...", "status": "primary" | "multi", "note": "private"}],
  "advice": ["a plain, widely held tip the article may give", ...],
  "tips": [{"title": "...", "text": "...", "status": "primary" | "multi"}],      # 豆知識: only confirmed ones; none -> no 豆知識 box
  "names": ["proper nouns the text may use"],
  "direction": ["editorial notes for this piece (what to stress, what not to say)"],
  "slot": "where a product card goes (optional; the tool adds the advertising note next to it, never the writer)",
  "history": "the update-history line (written by the editor, not generated)",
  "plan": "the chosen plan of the series (企画書), as text: the writer sees it",
  "parts": [{"mark": "[表: 人数別の早見表]", "what": "what it shows", "content": "the table / list itself (Markdown)"}]
                                      # fixed parts made by the editor (tables of computed numbers, checklists, a map, a poll): the writer only places the mark
}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WEIGHTS = ("light", "mid", "heavy")
OK_STATUS = ("primary", "multi", "calc")      # calc: computed from confirmed values (the formula is in the private note)
MEMO_KEYS = ("reader", "trouble", "feel", "action")
MEMO_JA = {"reader": "読者", "trouble": "読む前に困っていること", "feel": "冒頭で感じてほしいこと", "action": "読み終えてしてほしいこと"}


def load(path: Path | str) -> dict:
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(m)
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))
    return m


def validate(m: dict) -> list[str]:
    out = []
    if not m.get("id"):
        out.append("no id")
    if m.get("weight", "mid") not in WEIGHTS:
        out.append(f"weight must be one of {WEIGHTS}")
    memo = m.get("reader_memo") or {}
    for k in MEMO_KEYS:
        if not str(memo.get(k, "")).strip():
            out.append(f"reader_memo.{k} is empty (write the four lines before writing)")
    if not m.get("facts"):
        out.append("no facts")
    for i, f in enumerate(m.get("facts", [])):
        if f.get("status") not in OK_STATUS:
            out.append(f"fact {i} is not confirmed (status must be primary or multi; a single or conflicting source is left out)")
    for i, t in enumerate(m.get("tips", [])):
        if t.get("status") not in OK_STATUS:
            out.append(f"tip {i} is not confirmed (a 豆知識 that was not confirmed is not used)")
    return out


def usable_tips(m: dict) -> list[dict]:
    return [t for t in m.get("tips", []) if t.get("status") in OK_STATUS]


def source_text(m: dict) -> str:
    """Everything the text may draw on: a number or a name in the output must be found here."""
    parts = [f["text"] for f in m.get("facts", [])] + list(m.get("advice", [])) + [t.get("title", "") + " " + t.get("text", "") for t in usable_tips(m)]
    parts += list(m.get("names", [])) + [str(v) for v in (m.get("reader_memo") or {}).values()] + [m.get("topic", ""), m.get("slot", "") or "", m.get("date", "")]
    parts += list(m.get("direction", [])) + [m.get("plan", "")] + [p.get("content", "") + " " + p.get("what", "") for p in m.get("parts", [])]
    return "\n".join(p for p in parts if p)


def for_prompt(m: dict) -> str:
    """The material as the writer sees it (no confirmation notes: they are private and only make the text defensive)."""
    memo = m.get("reader_memo") or {}
    lines = ["【読者メモ】"] + [f"- {MEMO_JA[k]}: {memo.get(k, '')}" for k in MEMO_KEYS]
    lines += ["", "【確認済みの事実】(書いてよい事実はこれだけ。数字・名前・日付はこのまま使う)"]
    lines += [f"- {f['text']}" for f in m.get("facts", [])]
    if m.get("advice"):
        lines += ["", "【使ってよい助言】(言い方は自由に変えてよい。効き目や結果は約束しない)"]
        lines += [f"- {a}" for a in m["advice"]]
    tips = usable_tips(m)
    lines += ["", "【豆知識に使ってよい話】" + ("" if tips else "(なし。豆知識の囲みは作らない)")]
    lines += [f"- {t.get('title', '')}: {t.get('text', '')}" for t in tips]
    if m.get("direction"):
        lines += ["", "【この記事の編集方針】"] + [f"- {d}" for d in m["direction"]]
    if m.get("plan"):
        lines = ["【シリーズの企画(決定済み)】", m["plan"].strip(), ""] + lines
    if m.get("parts"):
        lines += ["", "【決まった部品】(編集の側で作ってある。本文の中の置きたい場所に、印の行だけを書く。中身の数字や項目を文で書き写さない。「下の表で〜」のように指して使う)"]
        for p in m["parts"]:
            lines += [f"- {p['mark']}: {p.get('what', '')}"] + [f"    {ln}" for ln in p.get("content", "").splitlines() if ln.strip()]
    if m.get("slot"):
        lines += ["", f"【商品カードの枠】{m['slot']}(本文の中で、行に「[商品カード]」とだけ書いて場所を示す。広告の表記や商品名は書かない)"]
    return "\n".join(lines)


# ---- import from the wadai article JSON (the reading edition of work/wadai_sample) ---------------------------------------------------------

def from_wadai(a: dict, weight: str = "heavy", mid: str = "") -> dict:
    """Build a material from a wadai reading article: the fact-layer paragraphs with their verification records, the confirmed 豆知識, the advice basis."""
    secs = a.get("sections", [])
    fact_paras = [t for s in secs if s.get("layer") == "fact" for t in s.get("paras", []) + s.get("bullets", [])]
    ver = {v.get("fact"): v for v in a.get("verification", [])}

    def status(i):
        v = ver.get(i) or {}
        if v.get("primary"):
            return "primary"
        return "multi" if len(set(v.get("sources", []))) >= 2 else "single"

    facts = [{"text": t, "status": status(i), "note": "; ".join(ver.get(i, {}).get("sources", []))} for i, t in enumerate(fact_paras)]
    tip_boxes = [b for s in secs for b in s.get("boxes", []) if b.get("kind") == "tip"]
    tips = []
    for j, b in enumerate(tip_boxes):
        i = len(fact_paras) + j
        tips.append({"title": b.get("title", ""), "text": b.get("text", ""), "status": status(i) if i in ver else "single"})
    advice = [x for ab in a.get("advice_basis", []) for x in ab.get("statements", [])]
    dropped = [t for t in tips if t["status"] not in OK_STATUS]          # a 豆知識 without a primary or two sources is not used
    return {"id": mid or a.get("id", ""), "dropped_tips": dropped, "site": "wadai", "weight": weight, "topic": a.get("title", ""),
            "date": a.get("updated", ""), "reader_memo": a.get("reader_memo", {}), "facts": facts, "advice": advice, "tips": [t for t in tips if t["status"] in OK_STATUS],
            "names": list(a.get("ledger", [])), "direction": [], "slot": "", "history": ""}


NUM_RE = re.compile(r"\d[\d,，.]*")


def numbers(text: str) -> set[str]:
    """Numbers as written, without separators: '15,821,184' -> '15821184'."""
    return {re.sub(r"[,，]", "", n).rstrip(".") for n in NUM_RE.findall(text)}
