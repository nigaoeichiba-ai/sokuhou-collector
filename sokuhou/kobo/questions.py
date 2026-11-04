"""当事者の疑問出し (the desk, 2026-11-04): readers with a real problem, played one by one, ask what the article does not answer yet.

Twice in the workshop: right after the plan (before the body) and after the 突っ込み役 (what is still left).  Each question carries
the action the person can take, the kind of answer (1 public record / 2 general / 3 differs by person or area -> how to find out / 4 do not
answer -> where to ask) and where it goes (a section / another page / a series / a checklist / a calculator / the Q&A page).

Research: the questions of kind 1 go to a research role that may read the web; it proposes an answer, a public page (go.jp / lg.jp) and an
exact quote.  The tool fetches that page itself and accepts the answer only when the quote is in the page text: then it becomes a fact of the
material with the record (URL, quote, date).  Anything else is dropped (never written as 'not known').
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import date
from urllib.parse import urlparse

from . import engine as E
from . import runner
from .material import for_prompt

PERSONAS = {
    "pt": ["契約前で、体験に申し込んだ人", "契約済みで、解約したい人", "入会するか迷っている人", "地方に住んでいる人", "自宅トレーニングやふつうのジムも考えている人",
           "家族(親や子)の契約が心配な人"],
}
DEFAULT_PERSONAS = ["これから行動しようとしている人", "もう当事者になってしまった人", "迷っている人", "地方に住んでいる人", "別の方法を考えている人", "家族のことが心配な人"]
PUBLIC = re.compile(r"(^|\.)(go\.jp|lg\.jp)$")
QUOTE_MIN = 12


def ask(m: dict, personas: list[str] | None = None, draft: str = "", model: str = "sonnet") -> dict:
    ps = personas or PERSONAS.get(str(m.get("id")), DEFAULT_PERSONAS)
    prompt = E.fill(E.prompt_file("questions"), topic=m.get("topic", ""), material=for_prompt(m),
                    draft=("\n## いまの記事(書いたあと)\n" + draft) if draft else "", personas="\n".join(f"- {p}" for p in ps))
    res = E.parse_json(runner.call(model, prompt))
    qs = []
    for p in res.get("personas", []) if isinstance(res.get("personas"), list) else []:
        for q in p.get("questions", []):
            try:
                at = int(q.get("answer_type", 2))
            except (TypeError, ValueError):
                at = 2
            qs.append({"who": p.get("who", ""), "q": str(q.get("q", "")), "action": str(q.get("action", "")), "answer_type": at,
                       "place": str(q.get("place", "")), "search": str(q.get("search", ""))})
    for i, q in enumerate(qs, 1):
        q["no"] = i
    return {"model": model, "personas": ps, "questions": qs, "unparsed": "_unparsed" in res}


# ---- research and the quote check --------------------------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[\s　、。,.・「」『』()（）\-－―:：]", "", html.unescape(s))


def page_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; kobo-quote-check/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:        # noqa: S310 (public pages only, checked by the caller)
        raw = r.read(3_000_000)
        cs = r.headers.get_content_charset() or ""
    for enc in [cs, "utf-8", "cp932", "euc-jp"]:
        if not enc:
            continue
        try:
            t = raw.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    else:
        t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", t)
    return re.sub(r"<[^>]+>", " ", t)


def quote_found(url: str, quote: str, fetch=page_text) -> tuple[bool, str]:
    host = urlparse(url).hostname or ""
    if not PUBLIC.search(host):
        return False, "not a public page (go.jp / lg.jp)"
    if len(_norm(quote)) < QUOTE_MIN:
        return False, "the quote is too short"
    try:
        text = fetch(url)
    except Exception as e:      # noqa: BLE001
        return False, f"could not fetch: {e}"
    return (_norm(quote) in _norm(text)), ("found" if _norm(quote) in _norm(text) else "the quote is not in the page")


def research(questions: list[dict], model: str = "sonnet", fetch=page_text) -> dict:
    """Ask the research role for the kind-1 questions; keep only the answers whose quote is on the public page."""
    todo = [q for q in questions if q["answer_type"] == 1]
    if not todo:
        return {"accepted": [], "dropped": []}
    listing = "\n".join(f"{q['no']}. {q['q']}" + (f"(手がかり: {q['search']})" if q.get("search") else "") for q in todo)
    res = E.parse_json(runner.call_with_web(model, E.fill(E.prompt_file("research"), questions=listing)))
    acc, drop = [], []
    for a in res.get("answers", []) if isinstance(res.get("answers"), list) else []:
        if not a.get("found"):
            drop.append({"q": a.get("q", ""), "why": "the research role did not find it on a public page"})
            continue
        ok, why = quote_found(str(a.get("url", "")), str(a.get("quote", "")), fetch)
        rec = {"q": a.get("q", ""), "answer": str(a.get("answer", "")), "url": a.get("url", ""), "quote": a.get("quote", ""), "check": why}
        (acc if ok else drop).append(rec)
    return {"accepted": acc, "dropped": drop}


def add_to_material(m: dict, accepted: list[dict]) -> dict:
    """The checked answers become facts of the material (primary, with the record in the private note)."""
    m = dict(m)
    m["facts"] = list(m.get("facts", [])) + [{"text": a["answer"], "status": "primary", "note": f"{a['url']} 「{a['quote']}」 quote checked {date.today()}",
                                              "question": a["q"]} for a in accepted if a.get("answer")]
    return m


def structure(m: dict, qs: list[dict], accepted: list[dict], card: dict, model: str = "opus") -> str:
    listing = "\n".join(f"{q['no']}. [{q['who']}] {q['q']} (type {q['answer_type']} / {q['place']} / 行動: {q['action']})" for q in qs)
    answers = "\n".join(f"- {a['q']} → {a['answer']}" for a in accepted) or "(なし)"
    prompt = E.fill(E.prompt_file("structure"), site_name=E.card_parts(card)["site_name"], material=for_prompt(m), questions=listing, answers=answers)
    return E._strip_fence(runner.call(model, prompt, E.prompt_file("system_writer")))


def run(m: dict, card: dict, draft: str = "", ask_model: str = "sonnet", research_model: str = "sonnet", structure_model: str = "opus") -> dict:
    q = ask(m, draft=draft, model=ask_model)
    r = research(q["questions"], research_model)
    m2 = add_to_material(m, r["accepted"])
    s = structure(m2, q["questions"], r["accepted"], card, structure_model)
    return {"questions": q, "research": r, "material": m2, "structure": s}


def summary_md(res: dict) -> str:
    q, r = res["questions"], res["research"]
    lines = [f"# 当事者の疑問出し(疑問 {len(q['questions'])} 件 / 当事者 {len(q['personas'])} 人 / 疑問出し {q['model']})", ""]
    for who in q["personas"]:
        lines += [f"## {who}"]
        lines += [f"- {x['no']}. {x['q']} — 行動: {x['action']} / 答えの種類 {x['answer_type']} / 置き場所: {x['place']}" for x in q["questions"] if x["who"] == who]
        lines.append("")
    lines += ["## 公的資料で確かめられた答え(引用がページの本文にあることを、道具が取得して確かめた)"]
    lines += [f"- {a['q']} → {a['answer']}(内部の記録: {a['url']})" for a in r["accepted"]] or ["- なし"]
    lines += ["", "## 確かめられず、書かないもの"] + [f"- {a.get('q', '')}: {a.get('why') or a.get('check', '')}" for a in r["dropped"]]
    lines += ["", res["structure"]]
    return "\n".join(lines) + "\n"
