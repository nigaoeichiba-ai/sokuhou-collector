"""Text statistics and the audit of what a rewrite added (the Codex research report, 2026-11-04, proposals 1 and 6).

stats(doc)        sentence length (mean, sd, CV), the longest run of the same ending, sentences per paragraph, commas per sentence; saved per article.
                  Marks are for a person to look at (never a score, never a rejection): the numbers are for finding what differs from the owner's own
                  articles, not for deciding that a text is AI-made.
audit(draft, final, m)   numbers, organisations, causal words, superlatives and definite claims that are in the final text and not in the draft.
styleloop_marks(texts)   the heavy rules and the learned rules of sokuhou.styleloop (compound words, office phrasing, coined labels, template phrases).
"""
from __future__ import annotations

import re
import statistics

from . import doc as D

CAUSAL = re.compile(r"ので|ため|おかげ|せい|によって|から、|そのため|だから|なぜなら")
SUPER = re.compile(r"いちばん|一番|最も|最大|最高|最安|最低限|最短|もっとも")
ORG = re.compile(r"[一-龥ァ-ヴー]{2,}(?:庁|省|県|府|都|市|区|町|村|社|会社|銀行|センター|協会|機構|委員会)")
NUM = re.compile(r"\d[\d,.]*")


def _ending(s: str) -> str:
    s = re.sub(r"[。!?！？」』)）\s]+$", "", s)
    return s[-3:]


def stats(doc: dict) -> dict:
    paras = [p for s in doc["sections"] for p in s["paras"]]
    sents = [x for p in [doc["lead"]] + paras for x in D.sentences(p)]
    if len(sents) < 4:
        return {"sentences": len(sents)}
    lens = [len(s) for s in sents]
    mean, sd = statistics.mean(lens), statistics.pstdev(lens)
    run = best = 1
    for a, b in zip(sents, sents[1:]):
        run = run + 1 if _ending(a) == _ending(b) else 1
        best = max(best, run)
    per_para = [len(D.sentences(p)) for p in paras if p]
    commas = sum(s.count("、") for s in sents) / len(sents)
    return {"sentences": len(sents), "len_mean": round(mean, 1), "len_sd": round(sd, 1), "len_cv": round(sd / mean, 2) if mean else 0,
            "longest_same_ending_run": best, "paras": len(per_para), "sentences_per_para_sd": round(statistics.pstdev(per_para), 2) if len(per_para) > 1 else 0,
            "commas_per_sentence": round(commas, 2)}


def stat_marks(st: dict) -> list[dict]:
    out = []

    def add(msg):
        out.append({"code": "ST", "label": "文の統計(参考)", "msg": msg, "detail": "", "strong": False})
    if st.get("sentences", 0) < 4:
        return out
    if st["len_cv"] < 0.40:
        add(f"文の長さのばらつきが小さい(変動係数 {st['len_cv']})。同じ長さの文が続いていないか、見てください。")
    if st["longest_same_ending_run"] >= 3:
        add(f"同じ終わり方が{st['longest_same_ending_run']}文続いています。")
    if st["paras"] >= 4 and st["sentences_per_para_sd"] == 0:
        add("すべての段落の文の数が同じです。内容より型に合わせていないか、見てください。")
    if st["commas_per_sentence"] > 1.6:
        add(f"読点が多い(1文あたり {st['commas_per_sentence']})。")
    return out


def _counts(text: str) -> dict:
    return {"num": set(NUM.findall(text)), "org": set(ORG.findall(text)), "causal": len(CAUSAL.findall(text)), "super": len(SUPER.findall(text))}


def audit(draft: str, final: str, material_text: str = "") -> list[dict]:
    """What the rewrite put into the final text that the draft did not have (and the material does not have for numbers and names)."""
    a, b = _counts(draft), _counts(final)
    out = []

    def add(msg, detail=""):
        out.append({"code": "AD", "label": "改稿で増えたもの", "msg": msg, "detail": detail, "strong": False})
    new_num = sorted(n for n in b["num"] - a["num"] if n not in material_text)
    if new_num:
        add(f"直す前になかった数字が入りました: {'、'.join(new_num[:6])}。素材にあるか確かめてください。")
    new_org = sorted(o for o in b["org"] - a["org"] if o not in material_text)
    if new_org:
        add(f"直す前になかった名前が入りました: {'、'.join(new_org[:4])}。素材にあるか確かめてください。")
    if b["causal"] > a["causal"]:
        add(f"理由・原因を表す言い方が{b['causal'] - a['causal']}か所増えました(のため・ので・によって など)。素材にある理由か確かめてください。")
    if b["super"] > a["super"]:
        add(f"最上級の言い方が{b['super'] - a['super']}か所増えました(いちばん・最も など)。素材にあるか確かめてください。")
    return out


def styleloop_marks(texts: list[str]) -> list[dict]:
    """The heavy and learned rules of styleloop on the sentences and headings (short-text rules)."""
    try:
        from .. import styleloop as SL
    except Exception:
        return []
    rules = list(SL._HEAVY) + list(SL.learned_rules())
    out, seen = [], set()
    for t in texts:
        for rid, pat, why in rules:
            if pat.search(t) and (rid, t) not in seen:
                seen.add((rid, t))
                out.append({"code": "SL", "label": "実物の文章から作った規則", "msg": f"{why}", "detail": t[:90], "strong": False})
    return out
