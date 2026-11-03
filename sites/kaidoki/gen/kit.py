"""Small builders for content/*.json pages."""
from __future__ import annotations

from .common import CHECKED

CLOSING = "最終的な日程は、主催者の公式発表でご確認ください。"


def R(path: str, text: str) -> dict:
    return {"path": path, "text": text}


def T(caption: str, cols: list[str], rows: list[list], num_cols: list[int] | None = None, note: str = "") -> dict:
    t = {"caption": caption, "cols": cols, "rows": [[str(c) for c in r] for r in rows]}
    if num_cols:
        t["num_cols"] = num_cols
    if note:
        t["note"] = note
    return t


def S(h2: str, *paras: str, table: dict | None = None, html: str = "") -> dict:
    s: dict = {"h2": h2}
    if paras:
        s["paras"] = list(paras)
    if table:
        s["table"] = table
    if html:
        s["html"] = html
    return s


def page(path, kind, parent, kw, title, h1, desc, answer, sections, related, *, intent=1, secondary=(), basis="", closing=True, noindex=False) -> dict:
    secs = list(sections)
    if closing:
        secs.append(S("最終確認は公式で", CLOSING + "日程は変更されることがあります。"))
    p = {"path": path, "kind": kind, "parent": parent, "primary_kw": kw, "secondary_kw": list(secondary), "intent": intent, "title": title, "h1": h1,
         "description": desc, "answer": answer, "updated": CHECKED, "sections": secs, "related": related, "sources": ["official"]}
    if basis:
        p["data_basis"] = basis
    if noindex:
        p["noindex"] = True
    return p
