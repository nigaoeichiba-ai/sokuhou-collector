"""AI-word candidates found by machine (the owner, 2026-11-05: stop naming the words one by one).

The idea: a phrase the tool's output uses often and that human-written public documents (the n-gram counts in human_ngrams.json, made by
scratch/fetch_human_stats.py from kokusen.go.jp, bousai.go.jp, caa.go.jp ... — counts only, no text) almost never use is a candidate for an AI word.
Only phrases ending in ます / ません / ました / です are looked at (the verb forms the owner kept finding).  Candidates are then judged by a panel
(three haiku and one sonnet, `panel`) before anything goes into the dictionary.

    cands = candidates(texts, human)         # [{key, out, pages, human, example}]  best first
    human_count("進めます", human)           # how often the phrase appears in the human documents (0 = never seen)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

PANEL = [("haiku", "日本語の校正者。厳しめに見る。"), ("haiku", "ふつうの読者。違和感で答える。"), ("haiku", "ウェブ記事の編集者。読みやすさで答える。"),
         ("sonnet", "国語の専門家。文章の自然さを総合して答える。")]
ENDINGS = r"(?:ます|ません|ました)"
# a phrase = the stem (kanji / katakana / hiragana, 1-4 chars right before the ending) + the ending; the stem must contain at least one kanji or katakana
PHRASE = re.compile(r"((?:[一-龥ァ-ンー][ぁ-ん]{0,3})" + ENDINGS + r"|[一-龥]{2,3}です)")
SKIP = {"です", "ます", "あります", "できます", "います", "しています", "ありません", "でした", "ました"}


def load_human(path: Path | str | None = None) -> dict:
    """The counts: {gram: [occurrences, pages]} (n-grams of 3 to 6 characters)."""
    p = Path(path) if path else None
    if p is None:
        from .engine import home            # the private folder (work/kobo)
        p = home() / "human_ngrams.json"
    return json.loads(p.read_text(encoding="utf-8")).get("ngrams", {})


def human_count(phrase: str, human: dict) -> int:
    """Occurrences of the phrase in the human documents.  Phrases longer than 6 characters are looked up by their last 6; shorter than 3 by 3 (the end part)."""
    g = phrase[-6:] if len(phrase) > 6 else phrase
    if len(g) < 3:
        return 0
    return int(human.get(g, [0, 0])[0])


def candidates(texts: dict[str, str], human: dict, min_out: int = 3, max_human: int = 1, top: int = 30) -> list[dict]:
    """texts = {page: text}.  A candidate: seen at least `min_out` times in the outputs (on at least 2 pages or 4 times), and at most `max_human` times in the human documents."""
    out = defaultdict(lambda: {"n": 0, "pages": set(), "example": ""})
    for page, text in texts.items():
        for sent in re.split(r"(?<=[。!?！？])", text):
            for m in PHRASE.finditer(sent):
                k = m.group(1)
                if k in SKIP or len(k) < 3:
                    continue
                e = out[k]
                e["n"] += 1
                e["pages"].add(page)
                if not e["example"]:
                    e["example"] = sent.strip()[:90]
    rows = []
    for k, e in out.items():
        h = human_count(k, human)
        if e["n"] >= min_out and (len(e["pages"]) >= 2 or e["n"] >= 4) and h <= max_human:
            rows.append({"key": k, "out": e["n"], "pages": len(e["pages"]), "human": h, "example": e["example"], "score": e["n"] / (h + 0.5)})
    rows.sort(key=lambda r: (-r["score"], -r["pages"], r["key"]))
    return rows[:top]


def panel(text: str, word: str, question: str | None = None) -> list[dict]:
    """Four judges (three haiku, one sonnet): is `word` in `text` an unnatural / AI-sounding use?  [{model, answer(bool|None), why}]"""
    from . import engine, runner
    q = question or f"この文の「{word}」は、AIが書きがちな、あいまいで不自然な使い方ですか。(true=不自然で直したい / false=自然でそのままでよい)"
    out = []
    for model, who in PANEL:
        prompt = f"あなたは{who}\n\n----\n{text}\n----\n\n質問: {q}\n出力は JSON だけ: {{\"answer\": true か false, \"why\": \"1文\"}}"
        try:
            a = engine.parse_json(runner.call(model, prompt))
            out.append({"model": model, "answer": a.get("answer"), "why": str(a.get("why", ""))[:80]})
        except Exception as e:      # noqa: BLE001
            out.append({"model": model, "answer": None, "why": str(e)[:60]})
    return out


def verdict(votes: list[dict], need: int = 3) -> bool:
    """Adopted as an AI word when at least `need` of the four judges say it is unnatural."""
    return sum(1 for v in votes if v["answer"] is True) >= need
