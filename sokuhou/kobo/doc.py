"""The writer's Markdown, parsed: title, lead, 3-line summary, sections with paragraphs, bullets and boxes (ライフハック / 豆知識), the product slot.

The writer writes Markdown (it keeps the voice better than JSON); the tool turns it into the wadai reading-article shape for the existing checks.
"""
from __future__ import annotations

import re

BOX_RE = re.compile(r"^>\s*\**\s*(ライフハック|豆知識)\s*[:：]\s*(.*?)\**\s*$")
SLOT = "[商品カード]"
MARK_RE = re.compile(r"^\s*(\[[^\[\]]{1,40}\])\s*$")     # a fixed part placed by the writer: [表: …] [チェックリスト] [図: …] [アンケート]
TLDR_HEADS = ("3行まとめ", "三行まとめ")


def _clean(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).strip()


def parse(md: str) -> dict:
    doc = {"title": "", "lead": "", "tldr": [], "sections": []}
    lead_lines: list[str] = []
    cur = None          # current section
    box = None
    in_tldr = False
    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            box = None
            continue
        if line.startswith("# ") and not doc["title"]:
            doc["title"] = _clean(line[2:])
            continue
        if line.startswith("## "):
            head = _clean(line[3:])
            box = None
            if any(h in head for h in TLDR_HEADS):
                in_tldr, cur = True, None
                continue
            in_tldr = False
            cur = {"heading": head, "paras": [], "bullets": [], "boxes": [], "slot": False, "marks": []}
            doc["sections"].append(cur)
            continue
        if in_tldr:
            if re.match(r"^\s*[-・*]\s*", line):
                doc["tldr"].append(_clean(re.sub(r"^\s*[-・*]\s*", "", line)))
            continue
        m = BOX_RE.match(line)
        if m:
            box = {"kind": "hack" if m.group(1) == "ライフハック" else "tip", "title": _clean(m.group(2)), "text": ""}
            (cur["boxes"] if cur is not None else doc.setdefault("pre_boxes", [])).append(box)
            continue
        if line.startswith(">"):
            body = _clean(line.lstrip(">").strip())
            if box is not None:
                box["text"] = (box["text"] + body) if box["text"] else body
            elif cur is not None:
                cur["paras"].append(body)
            continue
        box = None
        if SLOT in line:
            if cur is not None:
                cur["slot"] = True
            continue
        mk = MARK_RE.match(line)
        if mk:
            (cur.setdefault("marks", []) if cur is not None else doc.setdefault("lead_marks", [])).append(mk.group(1))
            continue
        if cur is None:
            lead_lines.append(_clean(line))
            continue
        if re.match(r"^\s*(?:[-・*]|\d+[.)．])\s+", line):
            cur["bullets"].append(_clean(re.sub(r"^\s*(?:[-・*]|\d+[.)．])\s+", "", line)))
        else:
            cur["paras"].append(_clean(line))
    doc["lead"] = "".join(lead_lines)
    return doc


def sentences(text: str) -> list[str]:
    out = []
    for part in re.split(r"(?<=[。!?！？])", text):
        part = part.strip()
        if part:
            out.append(part)
    return out


def all_texts(doc: dict) -> list[tuple[str, str]]:
    """(role, text) for every public sentence-bearing text."""
    out = [("title", doc["title"]), ("lead", doc["lead"])] + [("tldr", t) for t in doc["tldr"]]
    for s in doc["sections"]:
        out.append(("heading", s["heading"]))
        out += [("para", t) for t in s["paras"]] + [("bullet", t) for t in s["bullets"]]
        out += [("box", b["title"] + "。" + b["text"]) for b in s["boxes"]]
    return [(r, t) for r, t in out if t]


def body_text(doc: dict) -> str:
    return "\n".join(t for _, t in all_texts(doc))


def plain(doc: dict, parts: list | None = None) -> str:
    """The text as a reader sees it (for the reader gate): no slot marker, boxes with their names, fixed parts shown with their content."""
    pc = {p["mark"]: p.get("content", "") for p in (parts or [])}
    lines = []
    if doc["title"]:
        lines += [doc["title"], ""]
    if doc["lead"]:
        lines += [doc["lead"], ""]
    if doc["tldr"]:
        lines += ["【3行まとめ】"] + [f"・{t}" for t in doc["tldr"]] + [""]
    for s in doc["sections"]:
        lines.append(f"■ {s['heading']}")
        lines += s["paras"]
        lines += [f"・{b}" for b in s["bullets"]]
        for b in s["boxes"]:
            lines.append(f"【{'ライフハック' if b['kind'] == 'hack' else '豆知識'}】{b['title']}  {b['text']}")
        lines.append("")
    return "\n".join(lines).strip()


def to_markdown(doc: dict) -> str:
    lines = [f"# {doc['title']}", "", doc["lead"], ""]
    if doc["tldr"]:
        lines += ["## 3行まとめ"] + [f"- {t}" for t in doc["tldr"]] + [""]
    for s in doc["sections"]:
        lines += [f"## {s['heading']}"]
        lines += [p for p in s["paras"]]
        lines += [f"- {b}" for b in s["bullets"]]
        lines += list(s.get("marks", []))
        if s.get("slot"):
            lines.append(SLOT)
        for b in s["boxes"]:
            lines += ["", f"> {'ライフハック' if b['kind'] == 'hack' else '豆知識'}: {b['title']}", f"> {b['text']}"]
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _grams(s: str) -> set:
    s = re.sub(r"[\s、。・「」()（）:：!?！？]", "", s)
    return {s[i:i + 3] for i in range(max(0, len(s) - 2))}


def to_wadai(doc: dict, m: dict) -> dict:
    """The wadai reading-article shape (sokuhou.wadaipost.check_reading / check_article). Layers are guessed from the text:
    a section mostly made of the material's facts is 'fact', the one with the product slot (or the last one with boxes) 'prep', the rest 'opinion'."""
    facts = _grams("".join(f["text"] for f in m.get("facts", [])))
    secs = []
    for s in doc["sections"]:
        g = _grams("".join(s["paras"] + s["bullets"]))
        share = len(g & facts) / len(g) if g else 0
        secs.append({"layer": "fact" if share >= 0.45 else "opinion", "heading": s["heading"], "paras": list(s["paras"]),
                     "bullets": list(s["bullets"]), "boxes": [dict(b) for b in s["boxes"]], **({"slot": "product"} if s.get("slot") else {})})
    prep = next((i for i, s in enumerate(secs) if s.get("slot")), None)
    if prep is None:
        prep = next((i for i in range(len(secs) - 1, -1, -1) if secs[i]["layer"] != "fact"), None)
    if prep is not None and secs[prep]["layer"] != "fact":
        secs[prep]["layer"] = "prep"
    if m.get("history"):
        secs.append({"layer": "history", "heading": "更新履歴", "bullets": [m["history"]]})
    return {"format": "reading", "id": m.get("id", "?"), "updated": m.get("date", ""), "title": doc["title"], "lead": doc["lead"],
            "tldr": list(doc["tldr"]), "reader_memo": m.get("reader_memo", {}), "ledger": list(m.get("names", [])), "sections": secs,
            "ads": any(s.get("slot") for s in doc["sections"])}
