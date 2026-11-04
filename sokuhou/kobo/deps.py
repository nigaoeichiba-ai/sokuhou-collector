"""Dependency-parse candidates (GiNZA), optional: "points where the reader has to supply a subject or object" (the Codex research report, 2026-11-04,
proposal 4). Candidates for a person to check; nothing is changed or rejected. Needs spaCy + ja-ginza, which are not in requirements.txt: this module
returns [] when they are not installed.

D01 a verb that usually takes an object has none in its sentence      D02 a heading whose last word is a verb with no object
D03 a pointing word (これ・それ・もの・ところ) as the object or subject
"""
from __future__ import annotations

_NLP = None
TRANS = {"数える", "確認", "確かめる", "見直す", "用意", "準備", "比べる", "調べる", "選ぶ", "買う", "入れる", "出す", "備える", "決める", "書く", "持つ", "そろえる", "点検", "チェック", "計算", "探す", "使う"}
POINTING = {"これ", "それ", "あれ", "もの", "ところ", "こと", "所"}


def available() -> bool:
    try:
        import spacy  # noqa: F401
        spacy.load("ja_ginza")
        return True
    except Exception:
        return False


def _nlp():
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load("ja_ginza")
    return _NLP


def check(sentences: list[str], headings: list[str] | None = None) -> list[dict]:
    try:
        nlp = _nlp()
    except Exception:
        return []
    out = []
    heads = set(headings or [])
    for s in list(sentences) + list(heads):
        doc = nlp(s)
        verbs = [t for t in doc if t.pos_ in ("VERB", "NOUN") and (t.lemma_ in TRANS or t.text in TRANS) and (t.pos_ == "VERB" or any(c.dep_ == "aux" or c.lemma_ in ("する", "し") for c in t.children))]
        for v in verbs:
            if not any(c.dep_ in ("obj", "iobj") for c in v.children) and not any(c.text == "を" for c in v.subtree):
                out.append({"code": "D01", "msg": "他動詞に目的語(何を)がありません。読み手が補う必要がないか、確認してください。", "detail": s[:90]})
                break
        if s in heads:
            root = next((t for t in doc if t.dep_ == "ROOT"), None)
            if root is not None and root.pos_ == "VERB" and not any(c.dep_ in ("obj", "iobj") for c in root.children):
                out.append({"code": "D02", "msg": "見出しが動詞で終わり、目的語(何を)がありません。", "detail": s[:90]})
        for t in doc:
            if t.text in POINTING and t.dep_ in ("obj", "nsubj", "obl") and not any(c.dep_ in ("acl", "amod", "det", "nmod") and c.i < t.i for c in t.children):
                out.append({"code": "D03", "msg": f"「{t.text}」が何を指すか、前の文を読まないと分かりません。具体的な名詞にできないか、確認してください。", "detail": s[:90]})
                break
    return out


if __name__ == "__main__":
    # a separate check tool (the desk, 2026-11-04): run with a Python that has spaCy + ja-ginza, from the collector folder:
    #   C:/work/sokuhou/ginza_venv/Scripts/python.exe -m sokuhou.kobo.deps <article.md>
    import sys
    from pathlib import Path

    from . import doc as D
    sys.stdout.reconfigure(encoding="utf-8")
    d = D.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sents = [x for t in [d["lead"]] + d["tldr"] + [q for s in d["sections"] for q in s["paras"] + s["bullets"]] for x in D.sentences(t)]
    hits = check(sents, [s["heading"] for s in d["sections"]])
    for h in hits:
        print(f"{h['code']} {h['detail']}  — {h['msg']}")
    print(f"{len(hits)} candidates in {len(sents)} sentences")
