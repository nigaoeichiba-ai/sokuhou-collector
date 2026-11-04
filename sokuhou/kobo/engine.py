"""The workshop's loop: write -> machine checks -> fact-support judge -> reader gate -> rewrite (at most 3 times) -> output only what passed.

The reader gate never sees the machine checks (it reads like a reader, not like a rule book).  Every round is recorded in the private folder.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from . import checks as C
from . import doc as D
from . import lexicon
from . import textstats
from . import runner
from .material import for_prompt, source_text

HERE = Path(__file__).resolve().parent
PROMPTS = HERE / "prompts"
CARDS = HERE / "cards"
TOOLS = ("article", "title", "lead", "outline", "tldr", "tips", "threads", "rewrite", "note")
MULTI = {"title", "lead"}           # tools that return several candidates: the ones the reader passes are the output
MAX_REWRITES = 3
PASS_LEVEL = 2                      # a reader mark of this level or higher stops the text
PASS_L2_CHARS = 200                 # an article may keep one level-2 mark per 200 characters. Calibration 2026-11-04 (whole articles, 3 reads each): old articles one mark per <=132 chars, the corrected v2 one per >=283; the line sits between
# the writer by the weight of the piece (owner 2026-11-04): short and breaking news -> light, the body of a reading piece -> middle, disaster / money / contracts -> top
WRITER_BY_WEIGHT = {"light": "haiku", "mid": "sonnet", "heavy": "opus"}
TOOL_WEIGHT = {"title": "light", "lead": "light", "tldr": "light", "threads": "light", "tips": "mid", "outline": "mid"}


def home() -> Path:
    """The private folder (outside git): materials, calibration sets, records, outputs."""
    p = os.environ.get("KOBO_HOME")
    return Path(p) if p else HERE.parents[2] / "sokuhou-sites" / "work" / "kobo"


def load_card(site: str) -> dict:
    return json.loads((CARDS / f"{site}.json").read_text(encoding="utf-8"))


def prompt_file(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def fill(tpl: str, **kw) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


def card_parts(card: dict) -> dict:
    samples = "\n".join(f"- {s['text']}" for s in card.get("samples", [])) or "(見本はまだない)"
    return {"tone": "\n".join(f"- {t}" for t in card.get("tone", [])), "reader": card.get("reader", ""), "samples": samples,
            "site_name": card.get("name", card.get("site", "")), "headings": card.get("headings", ""), "length": card.get("length", "")}


def head_text(m: dict, card: dict, extra: str = "") -> str:
    cp = card_parts(card)
    return fill(prompt_file("common_head"), tone=cp["tone"], reader=cp["reader"], samples=cp["samples"], material=for_prompt(m), extra=extra)


def writer_prompt(tool: str, m: dict, card: dict, source: str = "") -> str:
    cp = card_parts(card)
    if tool == "rewrite":
        return fill(prompt_file("rewrite"), source=source, **cp)
    if tool == "note":
        return fill(prompt_file("note"), head=head_text(m, card), source=source, **cp)
    return fill(prompt_file(tool), head=head_text(m, card), **cp)


def pick_writer(tool: str, m: dict, writer: str | None) -> str:
    if writer:
        return writer
    return WRITER_BY_WEIGHT[TOOL_WEIGHT.get(tool, m.get("weight", "mid"))]


# ---- parsing the writer's answer into units ----------------------------------------------------------------------------------------------

def _strip_fence(t: str) -> str:
    t = t.strip()
    t = re.sub(r"^```[a-z]*\n|\n```$", "", t)
    return t.strip()


def units(tool: str, text: str) -> list[dict]:
    """One unit = {"doc": parsed doc, "raw": text}.  Title and lead give one unit per candidate."""
    text = _strip_fence(text)
    if tool == "title":
        cands = [re.sub(r"^\s*(?:[-・*]|\d+[.)．、])\s*", "", ln).strip() for ln in text.splitlines()]
        return [{"doc": _doc(title=c), "raw": c} for c in cands if c][:8]
    if tool == "lead":
        cands = [re.sub(r"^\s*(?:[-・*]|\d+[.)．、]|案\d+[:：])\s*", "", ln).strip() for ln in text.splitlines()]
        return [{"doc": _doc(lead=c), "raw": c} for c in cands if c][:5]
    if tool == "tldr":
        lines = [re.sub(r"^\s*[-・*]\s*", "", ln).strip() for ln in text.splitlines() if ln.strip()]
        return [{"doc": _doc(tldr=lines), "raw": text}]
    if tool == "threads":
        body, reply = text, ""
        mm = re.search(r"本文[:：]\s*\n(.*?)\n\s*返信[:：]\s*\n(.*)$", text, re.S)
        if mm:
            body, reply = mm.group(1).strip(), mm.group(2).strip()
        d = _doc(lead=body.replace("\n", ""))
        d["post"], d["reply"] = body, reply
        return [{"doc": d, "raw": text}]
    if tool == "rewrite":
        d = D.parse(text) if re.search(r"^#{1,2} ", text, re.M) else _doc(sections=[{"heading": "", "paras": [ln for ln in text.splitlines() if ln.strip()], "bullets": [], "boxes": [], "slot": False}])
        return [{"doc": d, "raw": text}]
    if tool in ("tips", "outline"):
        d = D.parse(("## 囲み\n" if tool == "tips" else "") + text)
        return [{"doc": d, "raw": text}]
    return [{"doc": D.parse(text), "raw": text}]


def _doc(title="", lead="", tldr=None, sections=None) -> dict:
    return {"title": title, "lead": lead, "tldr": tldr or [], "sections": sections or []}


def kind_of(tool: str) -> str:
    return "article" if tool in ("article", "note") else tool


def plain_of(tool: str, us: list[dict], m: dict | None = None, describe_empty: bool = True) -> str:
    if tool in MULTI:
        return "\n".join(f"案{i + 1}: {u['raw']}" for i, u in enumerate(us))
    if tool == "threads":
        d = us[0]["doc"]
        return f"【投稿】\n{d['post']}\n\n【投稿への返信】\n{d['reply']}"
    if tool == "outline":
        return us[0]["raw"]
    if tool == "rewrite":
        return us[0]["raw"]
    return D.plain(us[0]["doc"], (m or {}).get("parts"), describe_empty)


# ---- judges ------------------------------------------------------------------------------------------------------------------------------

def parse_json(t: str) -> dict:
    t = _strip_fence(t)
    try:
        return json.loads(t)
    except ValueError:
        mm = re.search(r"\{.*\}", t, re.S)
        if mm:
            try:
                return json.loads(mm.group(0))
            except ValueError:
                pass
    return {"_unparsed": t[:2000]}


def read_gate(text: str, reader: str, confirm: bool = True) -> dict:
    """The reader's marks: {"marks": [{text, level, why, fix}], "impression"}.  An answer that cannot be read counts as not passed."""
    res = parse_json(runner.call(reader, fill(prompt_file("reader"), text=text)))
    marks = []
    for mk in res.get("marks", []) if isinstance(res.get("marks"), list) else []:
        try:
            lvl = int(mk.get("level", 2))
        except (TypeError, ValueError):
            lvl = 2
        marks.append({"text": str(mk.get("text", "")), "level": lvl, "why": str(mk.get("why", "")), "fix": str(mk.get("fix", ""))})
    out = {"marks": marks, "impression": res.get("impression", ""), "unparsed": "_unparsed" in res}
    if confirm and not out["unparsed"]:
        confirm_marks(text, out, reader)
    return out


def confirm_marks(text: str, g: dict, model: str) -> None:
    """A second, independent read of each stopping mark (same family as the reader, fresh context, the editor's role):
    a mark that most readers would not stumble on goes down to level 1.  Calibration 2026-11-04: one reader alone marked
    7 of 13 natural blocks; the second read keeps the marks the two agree on."""
    idx = [i for i, mk in enumerate(g["marks"]) if mk["level"] >= PASS_LEVEL]
    if not idx:
        return
    listing = "\n".join(f"{k}. 「{g['marks'][i]['text']}」 理由: {g['marks'][i]['why']} / 直し案: {g['marks'][i]['fix']}" for k, i in enumerate(idx))
    res = parse_json(runner.call(model, fill(prompt_file("confirm"), text=text, marks=listing)))
    if "_unparsed" in res or not isinstance(res.get("keep"), list):
        return                      # cannot read the second opinion: keep every mark (the safe side)
    keep = {int(k) for k in res["keep"] if str(k).isdigit()}
    reasons = res.get("reasons", {}) if isinstance(res.get("reasons"), dict) else {}
    for k, i in enumerate(idx):
        mk = g["marks"][i]
        mk["confirmed"] = k in keep
        mk["confirm_note"] = str(reasons.get(str(k), ""))
        if k not in keep:
            mk["level_first"], mk["level"] = mk["level"], 1


def gate_pass(g: dict, text: str = "", tool: str = "article") -> bool:
    return not g["unparsed"] and marks_ok(g["marks"], text, tool)


def marks_ok(marks: list[dict], text: str, tool: str = "article") -> bool:
    """No level-3 mark; level-2 marks: none for short pieces, at most one per PASS_L2_CHARS characters for an article (calibrated, see KOBO_WRITER.md)."""
    if any(mk["level"] >= 3 for mk in marks):
        return False
    n2 = sum(1 for mk in marks if mk["level"] == PASS_LEVEL)
    if tool in MULTI or not PASS_L2_CHARS:
        return n2 == 0
    return n2 <= len(text) // PASS_L2_CHARS


def score(rd: dict) -> int:
    """Lower is better: machine findings weigh most, then unsupported statements, then the reader's marks."""
    mb = sum(1 for fs in rd["findings"] for f in fs if f["block"])
    l3 = sum(1 for mk in rd["reader"]["marks"] if mk["level"] >= 3)
    l2 = sum(1 for mk in rd["reader"]["marks"] if mk["level"] == PASS_LEVEL)
    return 100 * mb + 10 * len(rd["support"]["unsupported"]) + 5 * l3 + 2 * l2


def support_check(m: dict, text: str, judge: str, tool: str, source: str = "") -> dict:
    material = ("【もとの文章(この内容から外れない)】\n" + source) if tool == "rewrite" else for_prompt(m)
    res = parse_json(runner.call(judge, fill(prompt_file("support"), material=material, text=text)))
    items = res.get("unsupported", []) if isinstance(res.get("unsupported"), list) else []
    return {"unsupported": [{"text": str(x.get("text", "")), "why": str(x.get("why", ""))} for x in items], "unparsed": "_unparsed" in res}


def support_judge_for(writer: str) -> str:
    """The fact-support judge: Claude sonnet, or opus when sonnet wrote (never the writer itself); codex wrote -> opus."""
    if writer == "sonnet":
        return "opus"
    return "sonnet" if writer != "codex" else "opus"


# ---- extra checks per tool ---------------------------------------------------------------------------------------------------------------

def tool_findings(tool: str, u: dict, m: dict, card: dict) -> list[C.Finding]:
    d = u["doc"]
    fs = C.check(d, m if tool != "rewrite" else u.get("_m", m), dict(card, _tool=tool), kind_of(tool))
    if tool == "threads":
        body = d.get("post", "")
        if len(body) > 250:
            fs.append(C.Finding("T01", True, f"投稿の本文が{len(body)}字です。250字以内にしてください。"))
        if re.search(r"https?://|#\S", body):
            fs.append(C.Finding("T01", True, "投稿の本文にリンクかハッシュタグがあります。"))
        rl = [ln for ln in d.get("reply", "").splitlines() if ln.strip()]
        if not rl or rl[0].strip() != "【PR】":
            fs.append(C.Finding("T01", True, "返信の1行目は【PR】だけにしてください。"))
        fs = [f for f in fs if not (f.code == "K07" and "PR" in f.detail and "PR" not in body)]
    if tool == "title":
        t = d["title"]
        if not 12 <= len(t) <= 40:
            fs.append(C.Finding("T02", True, f"タイトルが{len(t)}字です(30字前後)。"))
    return fs


# ---- 突っ込み役 (the desk, 2026-11-04): a picky editor asks 'what? who? of what?' sentence by sentence; its revised text is the next version --

TSUKKOMI_TOOLS = ("article", "rewrite", "outline", "tips", "tldr", "threads", "note")
TSUKKOMI_DEFAULT = os.environ.get("KOBO_TSUKKOMI", "haiku")     # 2026-11-04 comparison: haiku caught every point the owner made, with the least over-correction


def tsukkomi(text: str, model: str) -> dict:
    """{"points": [{text, kind, ask, fix}], "revised": full text, "ok": parsed}.  Not a pass / fail: every point is applied."""
    raw = runner.call(model, fill(prompt_file("tsukkomi"), text=text))
    pts, revised = [], ""
    mm = re.search(r"===突っ込み===\s*(.*?)\s*===直した全文===\s*(.*)$", raw, re.S)
    if mm:
        js = parse_json(mm.group(1))
        pts = js.get("points", []) if isinstance(js.get("points"), list) else []
        revised = _strip_fence(mm.group(2))
    ok = bool(mm) and bool(revised.strip())
    return {"model": model, "points": pts, "revised": revised if ok else text, "ok": ok}


def remaining(m: dict, text: str, model: str = "sonnet") -> dict:
    """After the 突っ込み役: what a reader with the problem still asks.  Questions the material can answer go to the first rewrite;
    the others are kept in the record (another page, the research role or a place to ask)."""
    res = parse_json(runner.call(model, fill(prompt_file("remaining"), material=for_prompt(m), text=text)))
    left = res.get("left", []) if isinstance(res.get("left"), list) else []
    return {"model": model, "answerable": [x for x in left if x.get("in_material")], "elsewhere": [x for x in left if not x.get("in_material")]}


def _apply_tsukkomi(tool: str, text: str, model: str | None, log: list) -> str:
    if not model or tool not in TSUKKOMI_TOOLS:
        return text
    t = tsukkomi(text, model)
    if tool == "article" and t["ok"] and not D.parse(t["revised"])["sections"]:
        t["ok"], t["revised"] = False, text            # the revised text lost the shape: keep the writer's version
    log.append({"model": model, "points": t["points"], "ok": t["ok"], "before": text})
    return t["revised"]


# ---- the loop ----------------------------------------------------------------------------------------------------------------------------

def _notes(fs: list[C.Finding], sup: dict) -> str:
    lines = [f"- {f.msg}" + (f"(該当: {f.detail})" if f.detail and f.detail not in f.msg else "") for f in C.blocking(fs)]
    lines += [f"- 素材にないこと: 「{x['text']}」 — {x['why']}" for x in sup.get("unsupported", [])]
    return "\n".join(lines) or "(なし)"


def _marks(g: dict) -> str:
    ms = [mk for mk in g["marks"] if mk["level"] >= PASS_LEVEL]
    return "\n".join(f"- 「{mk['text']}」 / {mk['why']} / 直し案: {mk['fix']}" for mk in ms) or "(なし)"


# ---- light mode (the standard since 2026-11-04, the owner: about a minute a page; heavy judging only cost time) -------------------------

LIGHT_WRITER = os.environ.get("KOBO_LIGHT_WRITER", "opus")
MARK_LABELS = {"K01": "同じ言い方の重なり", "K02": "同じ内容のくり返し", "K03": "素材にない数字", "K04": "素材にない固有名詞", "K05": "素材にない語(参考)",
               "K06": "ラベルのような見出し", "K07": "広告の表記", "K08": "確認のない豆知識", "K09": "出典・「分からない」の話", "K10": "形(冒頭・3行まとめ・長い文)",
               "K11": "決まった部品", "K12": "ほかの記事の話の混入", "K13": "note の決まり", "K14": "断定に読める言い方"}
from .style_rules import LABELS as _SL
MARK_LABELS.update(_SL)


def human_marks(fs: list[C.Finding]) -> list[dict]:
    """What a person should look at, from the machine checks only (nothing here passes or stops the text)."""
    out, seen = [], set()
    for f in fs:
        if f.code == "K05" or not (f.code[0] in "KS" or f.code in ("NJ", "SL")):
            continue                       # K05 word lists and the wadai codes (English, repeating K10, flagging what the material has): noise
        key = (f.code, f.msg)
        if key in seen:
            continue
        seen.add(key)
        out.append({"code": f.code, "label": MARK_LABELS.get(f.code, f.code), "msg": f.msg, "detail": f.detail, "strong": f.block})
    return out


# ---- the 突っ込み役 as several readers in parallel (the owner, 2026-11-04: one reader missed what someone who does not know the topic
# would have stopped on; all of them haiku) ------------------------------------------------------------------------------------------------

PERSONA_MODEL = os.environ.get("KOBO_PERSONA_MODEL", "haiku")
PERSONAS = [
    ("知らない人", "何の話題かも知らない人。ニュースを見ていない。題・冒頭・3行まとめ・見出しだけで、何の話か通じるかを特に見る。"),
    ("急いでいる人", "電車で斜め読みする、急いでいる人。題・3行まとめ・見出ししか読まない。それだけで、自分が何をすればよいか分かるかを見る。"),
    ("疑い深い人", "疑い深い人。「本当?」「誰が言っている?」「あおって売りたいのでは?」と思いながら読む。言い切り・大げさな言い方・根拠のない話を見る。"),
]
def proof_who() -> str:
    """The proofreaders' brief: the seven standards of the desk (2026-11-04) and, as examples, the words in the dictionary."""
    return ("日本語の校正者。次の7つの基準で読む: ①欠落(主語・述語・目的語・助詞) ②ねじれ(述語と主語の呼応、数の食い違い) ③見出し(動詞で終わるのに「何を」がない、名詞の列挙が文になっていない) "
            "④省略(何の数・何の体験・何の相談か分からない) ⑤語の使い方・選び方が適切か ⑥読み手に強いる言い方 ⑦初めて読む人に通じるか。"
            "直し案は、文の形(主語・目的語・述語の補い、語順、助詞)と語の置き換えだけにする。素材にない事実(誰が・どこが言ったか、新しい数字や説明)を足す直しは書かない。"
            "また、直し案の中に、次の語を残したり新しく入れたりしない。\n次のような語の使い方に気づく(例):\n" + lexicon.examples_text())


PROOFERS = [("校正(haiku)", None, "haiku"), ("校正(sonnet)", None, "sonnet"), ("校正(Codex)", None, "codex")]      # the union of the three (the desk, 2026-11-04)
CITATION_ASK = re.compile(r"出典|URL|リンク|ソース|引用元|情報源|報道")


def personas_for(m: dict) -> list[tuple[str, str]]:
    """The three standing readers, the article's own 当事者 (from the material, else the reader memo) and any extra readers the material names."""
    memo = m.get("reader_memo") or {}
    insider = m.get("insider") or f"当事者: {memo.get('reader', '')}。{memo.get('trouble', '')}。「うちの場合は?」「結局、何から?」「お金は?」と思いながら読む。"
    extra = [(p.get("name", f"追加{i + 1}"), p["who"]) if isinstance(p, dict) else (f"追加{i + 1}", str(p)) for i, p in enumerate(m.get("personas", []))]
    base = [PERSONAS[0], PERSONAS[1], ("当事者", insider)]            # the standard three (the desk, 2026-11-04: time)
    if m.get("deep_readers"):                                      # the sceptic and the extra readers only for the articles the desk names
        base += [PERSONAS[2]] + extra
    return base


def _key(s: str) -> str:
    return re.sub(r"[\s、。「」()（）!?！？・]", "", str(s))[:14]


def persona_points(text: str, m: dict, model: str = PERSONA_MODEL) -> dict:
    """Every persona reads at once. Returns {"readers": [{name, gist, points}], "points": [{text, asks, fixes, by}] (most readers first)}."""
    from concurrent.futures import ThreadPoolExecutor
    who = proof_who()
    proofers = PROOFERS if (m.get("deep_readers") or m.get("proof_all")) else [p for p in PROOFERS if p[2] == "codex"]
    ps = personas_for(m) + [(n, who, mo) for n, _, mo in proofers]
    # the readers see the page as a reader does (the fixed parts shown in place, not as bare work marks like '[商品カード]')
    view = D.plain(D.parse(text), m.get("parts"))

    def one(p):
        res = parse_json(runner.call(p[2] if len(p) > 2 else model, fill(prompt_file("persona_read"), persona=p[1], text=view)))
        pts = [x for x in (res.get("points") if isinstance(res.get("points"), list) else []) if isinstance(x, dict)]
        pts = [x for x in pts if not CITATION_ASK.search(str(x.get("ask", "")) + str(x.get("fix", "")))]    # the owner: no sources in the text
        return {"name": p[0], "gist": str(res.get("gist", "")), "points": pts}

    with ThreadPoolExecutor(max_workers=len(ps)) as ex:
        readers = list(ex.map(one, ps))
    groups: dict = {}
    for r in readers:
        for x in r["points"]:
            g = groups.setdefault(_key(x.get("text", "")), {"text": str(x.get("text", "")), "asks": [], "fixes": [], "by": []})
            if r["name"] not in g["by"]:
                g["by"].append(r["name"])
            g["asks"].append(str(x.get("ask", "")))
            g["fixes"].append(str(x.get("fix", "")))
    pts = sorted(groups.values(), key=lambda g: -len(g["by"]))
    return {"model": model, "readers": readers, "points": pts}


def persona_fix(text: str, m: dict, pp: dict, model: str = PERSONA_MODEL) -> str:
    many = [g for g in pp["points"] if len(g["by"]) >= 2]
    one = [g for g in pp["points"] if len(g["by"]) < 2]
    def fmt(g):
        return f"- 「{g['text'][:80]}」({'・'.join(g['by'])}) {' / '.join(a for a in g['asks'][:3] if a)} → 案: {g['fixes'][0][:80] if g['fixes'] else ''}"
    pts = "### 2人以上が引っかかった所\n" + ("\n".join(fmt(g) for g in many) or "(なし)") + "\n\n### 1人だけが引っかかった所\n" + ("\n".join(fmt(g) for g in one[:25]) or "(なし)")
    out = _strip_fence(runner.call(model, fill(prompt_file("persona_fix"), material=for_prompt(m), points=pts, text=text, words=lexicon.examples_text())))
    if not out.strip() or not D.parse(out)["sections"]:
        return text                                    # the fix lost the shape: keep the writer's version
    return out


# ---- the named-word check, the titles (the desk and the owner, 2026-11-04) ---------------------------------------------------------------

NAMED_MODELS = ("haiku", "sonnet", "codex")


def named_check(text: str, models=NAMED_MODELS) -> dict:
    """Every sentence with a word of the dictionary is shown to three models, short and all at once: 'is this word natural here? if not, why, and three
    alternatives'. (Asked about the whole text, the three models did not name the owner's words; asked about the word, all three did.)"""
    from concurrent.futures import ThreadPoolExecutor
    d = D.parse(text)
    texts = [d["title"]] + [s["heading"] for s in d["sections"]] + [x for t in [d["lead"]] + d["tldr"] + [p for s in d["sections"] for p in s["paras"] + s["bullets"] + [b["text"] for b in s["boxes"]]] for x in D.sentences(t)]
    items, seen = [], set()
    for h in lexicon.scan([t for t in texts if t]):
        if (h["id"], h["text"]) not in seen:
            seen.add((h["id"], h["text"]))
            items.append(h)
    items = items[:14]
    if not items:
        return {"asked": 0, "flagged": [], "learned": []}
    lines = "\n".join(f"{i + 1}. 【{h['match']}】 {h['text']}" for i, h in enumerate(items))

    def one(model):
        try:
            res = parse_json(runner.call(model, fill(prompt_file("named_check"), lines=lines)))
        except Exception:
            return model, []
        return model, [x for x in (res.get("items") if isinstance(res.get("items"), list) else []) if isinstance(x, dict)]

    with ThreadPoolExecutor(max_workers=len(models)) as ex:
        answers = list(ex.map(one, models))
    flagged, learned = [], []
    for i, h in enumerate(items):
        by, reasons, alts = [], [], []
        for model, its in answers:
            a = next((x for x in its if x.get("n") == i + 1), None)
            if a and a.get("natural") is False:
                by.append(model)
                reasons.append(str(a.get("reason", "")))
                alts += [str(t) for t in (a.get("alternatives") or [])][:3]
                learned.append({"id": h["id"], "model": model, "reason": str(a.get("reason", ""))[:140], "alternatives": [str(t) for t in (a.get("alternatives") or [])][:3]})
        if by:
            flagged.append({"id": h["id"], "code": h["code"], "text": h["text"], "by": by, "reasons": reasons, "alternatives": alts})
    return {"asked": len(items), "flagged": flagged, "learned": learned}


def named_notes(nc: dict) -> str:
    return "\n".join(f"- 語の使い方({'・'.join(f['by'])}が不自然と答えた): 「{f['text']}」 — {f['reasons'][0] if f['reasons'] else ''}。言い換え案: {' / '.join(dict.fromkeys(f['alternatives']))[:120]}"
                     for f in nc["flagged"])


def title_options(text: str, writer: str) -> list[str]:
    res = parse_json(runner.call(writer, fill(prompt_file("title_options"), text=text)))
    return [str(t).strip() for t in (res.get("titles") if isinstance(res.get("titles"), list) else []) if str(t).strip()][:5]


BAD_TITLE = re.compile(r"[:：]|について|てみよう|てみましょう|数えて|数えよう")


def pick_title(text: str, opts: list[str]) -> tuple[str, dict]:
    import random
    """Two haiku readers (the one who does not know the topic, the one in a hurry) each choose the title that hits home; the most votes win."""
    from concurrent.futures import ThreadPoolExecutor
    ok = list(dict.fromkeys(t for t in opts if not BAD_TITLE.search(t) and 8 <= len(t) <= 30))
    random.Random(len(text)).shuffle(ok)                    # the readers do not see who made an option or in what order
    if len(ok) < 2:
        return "", {"options": opts, "votes": []}
    lead = D.parse(text)["lead"]
    options = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ok))

    def one(p):
        try:
            res = parse_json(runner.call(PERSONA_MODEL, fill(prompt_file("title_pick"), persona=p[1], lead=lead, options=options)))
            n = int(res.get("best", 0))
            return n if 1 <= n <= len(ok) else 0
        except Exception:
            return 0

    with ThreadPoolExecutor(max_workers=2) as ex:
        votes = list(ex.map(one, PERSONAS[:2]))
    cnt = {v: votes.count(v) for v in votes if v}
    if not cnt:
        return "", {"options": ok, "votes": votes}
    best = max(cnt, key=lambda k: (cnt[k], -votes.index(k)))
    return ok[best - 1], {"options": ok, "votes": votes}


def set_title(text: str, title: str) -> str:
    return re.sub(r"^# .*$", "# " + title, text, count=1, flags=re.M)


def fix_endings(tool: str, text: str, fs: list, m: dict, card: dict, writer: str, system: str, extra: str = ""):
    """Monotony (the same ending / opening / phrase three times or more) is fixed by the writer in one more call that replaces only
    the named sentences (the desk, 2026-11-04). Returns (text, findings, number of sentences replaced)."""
    mono = [f for f in fs if (f.code == "K01" and f.block) or f.code[0] == "S" or f.code == "K14"]
    mono = sorted(mono, key=lambda f: f.code == "S13")[:12]        # the named sentences only: at most 12, the many 「数える」 last
    if tool not in ("article", "note") or not (mono or extra):
        return text, fs, 0
    notes = "\n".join(f"- {f.msg}(該当: {f.detail})" if f.detail else f"- {f.msg}" for f in mono)
    notes += ("\n" + extra) if extra else ""
    notes += "\n(挙がった文だけを言い換える。同じ言い方の重なりは、1つか2つだけ。事実・条件・数字の意味は変えない。素材にない事実は足さない。)"
    rp = fill(prompt_file("revise_patch"), head=head_text(m, card), draft=text, marks="(なし)", notes=notes)
    try:
        new, n = apply_edits(text, parse_json(runner.call(writer, rp, system)).get("edits"))
    except Exception:
        return text, fs, 0
    if not n:
        return text, fs, 0
    return new, [f for u in units(tool, new) for f in tool_findings(tool, u, m, card)], n


def added_explanations(draft: str, final: str, m: dict) -> list[dict]:
    """Explanations in brackets that the 突っ込み役 added and the material does not have (2026-11-04: '188(最寄りの消費生活センターに
    つながる番号)', a legal definition of クーリング・オフ): marked for a person, not removed."""
    src = source_text(m)
    out = []
    for mt in re.finditer(r"[（(]([^（）()]{4,40})[）)]", final):
        if mt.group(0) not in draft and mt.group(1) not in src:
            out.append({"code": "TK", "label": "突っ込み役が足した説明", "msg": f"「{mt.group(1)}」は素材にない説明です。正しいか、要るかを見てください。",
                        "detail": final[max(0, mt.start() - 15):mt.end()].replace("\n", " "), "strong": False})
    return out


def light(tool: str, m: dict, card: dict, writer: str | None = None, tsukkomi_model: str | None = "default", record: bool = True) -> dict:
    """素材 -> 書き手 (1 call) -> 機械の検査 -> 突っ込み役 (1 call, the full revised text) -> 機械の検査 -> output with the marks for a person.
    No reader gate, no fact judge, no rewrite rounds (those stay in run(), for topics the desk names: contracts, law, health, money)."""
    assert tool in TOOLS, tool
    writer = writer or LIGHT_WRITER
    if tool == "note":
        m = dict(m, parts=[], slot="")
    t0 = time.time()
    system = prompt_file("system_writer")
    prompt = writer_prompt(tool, m, card)
    draft = runner.call(writer, prompt, system)
    pre_n = 0
    if tool in ("article", "note"):
        draft, pre_n = lexicon.autofix(draft)              # the dictionary first (the desk's flow): the readers see the text without the known words
    t1 = time.time()
    fs0 = [f for u in units(tool, draft) for f in tool_findings(tool, u, m, card)]
    log: list = []
    pp = None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as tex:
        f_titles = tex.submit(title_options, draft, writer) if tool == "article" else None      # five titles, while the readers read
        if tsukkomi_model in ("default", "personas") and tool in ("article", "note"):
            # the standard: several haiku readers at once, one fix (the owner, 2026-11-04)
            tk = f"personas:{PERSONA_MODEL}"
            pp = persona_points(draft, m)
            final = _keep_shape(persona_fix(draft, m, pp), draft, tool)
        else:
            tk = TSUKKOMI_DEFAULT if tsukkomi_model == "default" else tsukkomi_model
            tk = None if tk in ("", "none") else tk
            final = _keep_shape(_apply_tsukkomi(tool, draft, tk, log), draft, tool)
        try:
            opts = f_titles.result() if f_titles else []
        except Exception:
            opts = []
    t2 = time.time()
    fs1 = [f for u in units(tool, final) for f in tool_findings(tool, u, m, card)]
    auto_n = pre_n
    if tool in ("article", "note"):
        # the words of the dictionary are replaced by machine (the readers' own fixes sometimes bring the word back), then named to the writer
        final, auto_n = lexicon.autofix(final)
        fs1 = [f for u in units(tool, final) for f in tool_findings(tool, u, m, card)]
    nc = {"asked": 0, "flagged": [], "learned": []}
    if tool in ("article", "note"):
        nc = named_check(final)                                   # the words of the dictionary still in the text, asked of three models by name
    final, fs1, ends_fixed = fix_endings(tool, final, fs1, m, card, writer, system, extra=named_notes(nc))
    title_info = {}
    if tool in ("article", "note"):
        final, k = lexicon.autofix(final)
        if k:
            auto_n += k
        if opts:
            new_title, title_info = pick_title(final, opts + list(m.get("title_candidates", [])))
            if new_title:
                final = set_title(final, new_title)
        if m.get("title_fixed"):
            final = set_title(final, m["title_fixed"])         # the desk's decision for the article (bousai parent)
        fs1 = [f for u in units(tool, final) for f in tool_findings(tool, u, m, card)]
    t3 = time.time()
    dd = D.parse(final)
    st = textstats.stats(dd)
    heads = [dd["title"]] + [s["heading"] for s in dd["sections"]]
    marks = (human_marks(fs1) + added_explanations(draft, final, m) + textstats.audit(draft, final, source_text(m)) + textstats.stat_marks(st)
             + textstats.styleloop_marks([h for h in heads if h] + [x for t in [dd["lead"]] + dd["tldr"] + [p for s in dd["sections"] for p in s["paras"]] for x in D.sentences(t)])
             + [{"code": f["code"], "label": "語の使い方(モデルの確認)", "msg": f"{'・'.join(f['by'])}が不自然と答えました: {f['reasons'][0] if f['reasons'] else ''}", "detail": f["text"][:90], "strong": False} for f in nc["flagged"]])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {"mode": "light", "tool": tool, "material": m.get("id"), "site": card.get("site"), "writer": writer, "tsukkomi": tk,
              "draft": draft, "output": final, "marks": marks, "draft_marks": human_marks(fs0),
              "tsukkomi_points": (pp["points"] if pp else (log[0]["points"] if log else [])), "tsukkomi_ok": bool(pp) or bool(log and log[0]["ok"]),
              "readers": ([{"name": r["name"], "gist": r["gist"], "points": len(r["points"])} for r in pp["readers"]] if pp else []),
              "endings_fixed": ends_fixed, "words_replaced": auto_n, "named_check": {"asked": nc["asked"], "flagged": len(nc["flagged"])}, "learned": nc["learned"],
              "title": title_info, "stats": st, "seconds": {"writer": round(t1 - t0), "tsukkomi": round(t2 - t1), "endings": round(t3 - t2), "total": round(time.time() - t0)}}
    if record:
        rec = home() / "runs" / datetime.now().strftime("%Y-%m-%d") / f"{m.get('id', 'x')}-{tool}-{writer}-light-{stamp}"
        rec.mkdir(parents=True, exist_ok=True)
        (rec / "material.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        (rec / "prompt.md").write_text(prompt, encoding="utf-8")
        (rec / "draft.md").write_text(draft, encoding="utf-8")
        (rec / "final.md").write_text(final, encoding="utf-8")
        (rec / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        result["record"] = str(rec)
        out = home() / "out" / str(m.get("id"))
        out.mkdir(parents=True, exist_ok=True)
        body = D.with_toc(final) if tool in ("article", "note") else final
        path = out / f"{tool}-{writer}.md"
        path.write_text(body, encoding="utf-8")
        (out / f"{tool}-{writer}.marks.md").write_text(marks_md(result), encoding="utf-8")
        if tool == "article":
            (out / f"{tool}-{writer}.json").write_text(json.dumps(D.to_wadai(D.parse(body), m), ensure_ascii=False, indent=1), encoding="utf-8")
        ledger_add(m, dict(result, reader="-"), path)
        result["out"] = str(path)
    return result


def marks_md(r: dict) -> str:
    lines = [f"# 人が見る印: {r['material']} / {r['tool']}(書き手 {r['writer']}、突っ込み役 {r['tsukkomi']}、{r['seconds']['total']}秒)", ""]
    if not r["marks"]:
        lines.append("(機械の検査で拾えたものはありません)")
    for x in r["marks"]:
        lines.append(f"- {'**' if x['strong'] else ''}{x['label']}{'**' if x['strong'] else ''}: {x['msg']}" + (f"(該当: {x['detail']})" if x["detail"] and x["detail"] not in x["msg"] else ""))
    if r.get("readers"):
        lines += ["", "## 読者役(題と冒頭だけで、何の話だと思ったか)"]
        lines += [f"- {x['name']}(指摘 {x['points']}件): {x['gist']}" for x in r["readers"]]
        pts = r.get("tsukkomi_points", [])
        lines += ["", f"## 2人以上が引っかかった所({sum(1 for p in pts if len(p['by']) >= 2)}件。直しに必ず反映)"]
        lines += [f"- 「{p['text'][:40]}」({'・'.join(p['by'])}) {p['asks'][0][:60] if p['asks'] else ''}" for p in pts if len(p["by"]) >= 2]
    elif r.get("tsukkomi_points"):
        lines += ["", f"## 突っ込み役の指摘({len(r['tsukkomi_points'])}件、全部反映済み)"]
        lines += [f"- 「{str(p.get('text', ''))[:40]}」 {p.get('ask', '')} → {str(p.get('fix', ''))[:60]}" for p in r["tsukkomi_points"]]
    return "\n".join(lines) + "\n"


def run(tool: str, m: dict, card: dict, writer: str | None = None, reader: str | None = None, source: str = "", rewrites: int = MAX_REWRITES,
        record: bool = True, label: str = "", tsukkomi_model: str | None = "default", ask_left: bool = True) -> dict:
    assert tool in TOOLS, tool
    writer = pick_writer(tool, m, writer)
    reader = reader or runner.other_family(writer)
    if runner.FAMILY[reader] == runner.FAMILY[writer]:
        raise ValueError(f"the reader ({reader}) must be of another family than the writer ({writer})")
    judge = support_judge_for(writer)
    if tool == "rewrite":
        m = dict(m, facts=[{"text": source, "status": "primary"}], advice=[], tips=[], names=m.get("names", []))
    if tool == "note":
        m = dict(m, parts=[], slot="")
    system = prompt_file("system_writer")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rec_dir = home() / "runs" / datetime.now().strftime("%Y-%m-%d") / f"{m.get('id', 'x')}-{tool}-{writer}{('-' + label) if label else ''}-{stamp}"
    rounds = []
    prompt = writer_prompt(tool, m, card, source)
    tk = TSUKKOMI_DEFAULT if tsukkomi_model == "default" else tsukkomi_model
    tk = None if tk in ("", "none") else tk
    tk_log: list = []
    text = _apply_tsukkomi(tool, runner.call(writer, prompt, system), tk, tk_log)
    left = remaining(m, text) if (ask_left and tool in ("article", "note")) else {"answerable": [], "elsewhere": []}
    t0 = time.time()
    result = None
    for r in range(rewrites + 1):
        us = units(tool, text)
        if tool == "rewrite":
            for u in us:
                u["_m"] = m
        fs_all = [tool_findings(tool, u, m, card) for u in us]
        plain = plain_of(tool, us, m)
        sup = support_check(m, plain_of(tool, us, m, describe_empty=False), judge, tool, source)
        g = read_gate(plain, reader)
        # which units pass: no blocking finding, nothing unsupported in it, no level-3 mark, and level-2 marks within the allowance
        passed = []
        for u, fs in zip(us, fs_all):
            raw = u["raw"]
            mine = [mk for mk in g["marks"] if tool not in MULTI or _in(mk["text"], raw)]
            bad_sup = any(tool not in MULTI or _in(x["text"], raw) for x in sup["unsupported"])
            if not C.blocking(fs) and not bad_sup and not g["unparsed"] and not sup["unparsed"] and marks_ok(mine, raw, tool):
                passed.append(u)
        rd = {"round": r, "writer": writer, "text": text, "tsukkomi": tk_log[0] if tk_log and r == 0 else None, "findings": [[f.as_dict() for f in fs] for fs in fs_all], "support": sup,
              "reader": g, "passed": len(passed), "units": len(us), "passed_units": [u["raw"] for u in passed]}
        rd["score"] = score(rd)
        rounds.append(rd)
        done = (len(passed) == len(us)) if tool not in MULTI else len(passed) >= min(2, len(us))
        if done or r == rewrites:
            # a rewrite can also make a text worse: the best round is kept, not the last one
            ok = [x for x in rounds if (x["passed"] == x["units"] if tool not in MULTI else x["passed"] >= min(2, x["units"]))]
            best = min(ok or rounds, key=lambda x: (x["score"], -x["round"]))
            result = {"tool": tool, "material": m.get("id"), "site": card.get("site"), "writer": writer, "reader": reader, "judge": judge,
                      "passed": bool(ok), "rewrites": r, "best_round": best["round"],
                      "output": best["passed_units"] if tool in MULTI else (best["text"] if ok else ""),
                      "last": text, "best": best["text"], "rounds": rounds, "seconds": round(time.time() - t0), "allowance": PASS_L2_CHARS, "tsukkomi": tk, "left": left}
            break
        fs_flat = [f for fs in fs_all for f in fs]
        # rewrite from the best version so far (a worse rewrite is not built on)
        base = min(rounds, key=lambda x: (x["score"], -x["round"]))
        if base is not rd:
            fs_flat = [C.Finding(**f) for fs in base["findings"] for f in fs]
            sup, g = base["support"], base["reader"]
        notes = _notes(fs_flat, sup)
        if r == 0 and left["answerable"]:
            notes += "\n" + "\n".join(f"- 読者にまだ残っている疑問: 「{x.get('q', '')}」(素材の「{str(x.get('from', ''))[:60]}」で答えられる。{x.get('where', '')})" for x in left["answerable"][:5])
        head = head_text(m, card) if tool != "rewrite" else "【もとの文章】\n" + source
        # the 突っ込み役 works on the first draft only (the desk's order: writer -> checks -> 突っ込み役 -> fixes -> reader gate);
        # run on every round, it reworked the writer's targeted fixes and the text swung back and forth (2026-11-04)
        text = None
        if tool in ("article", "note") and not any(f.code in STRUCTURAL for f in C.blocking(fs_flat)):
            # only the marked sentences change: the writer sends replacements and the tool applies them (2026-11-04: asked to keep
            # the other sentences, the writer still reworded them, and each rewrite fixed some marks and made new ones)
            rp = fill(prompt_file("revise_patch"), head=head, draft=base["text"], marks=_marks(g), notes=notes)
            text, n = apply_edits(base["text"], parse_json(runner.call(writer, rp, system)).get("edits"))
            if not n:
                text = None
        if text is None:
            rp = fill(prompt_file("revise"), head=head, draft=base["text"], marks=_marks(g), notes=notes)
            text = runner.call(writer, rp, system)
        text = _keep_shape(text, base["text"], tool)
    if record:
        save(rec_dir, m, prompt, result)
    result["record"] = str(rec_dir) if record else ""
    return result


STRUCTURAL = {"K06", "K10", "K11", "K13"}      # findings about the shape (headings, summary, parts, note line): the whole text is rewritten


def apply_edits(text: str, edits) -> tuple[str, int]:
    """Apply the writer's sentence replacements to the text; an 'old' that is not in the text is skipped. Returns (text, applied)."""
    n = 0
    for e in edits if isinstance(edits, list) else []:
        if not isinstance(e, dict):
            continue
        old, new = str(e.get("old", "")).strip(), str(e.get("new", "")).strip()
        if len(old) < 4 or old == new or old not in text:
            continue
        text = text.replace(old, new, 1)
        n += 1
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, n


def _keep_shape(new: str, old: str, tool: str) -> str:
    """A rewrite that drops the 3-line summary gets the old one back (2026-11-04: the battery page lost its summary in the last
    rewrite and stopped on K10 alone; the writer was asked to fix sentences, not to remove parts)."""
    if tool not in ("article", "note"):
        return new
    if D.parse(new)["tldr"] or not D.parse(old)["tldr"]:
        return new
    blk = re.search(r"^## (?:3行まとめ|三行まとめ)\s*\n(?:.*\S.*\n?)+", old, re.M)
    at = re.search(r"^## ", new, re.M)
    if not blk or not at:
        return new
    return new[:at.start()] + blk.group(0).rstrip() + "\n\n" + new[at.start():]


def _in(needle: str, hay: str) -> bool:
    n = re.sub(r"\s", "", needle)[:20]
    return bool(n) and n in re.sub(r"\s", "", hay)


def save(rec_dir: Path, m: dict, prompt: str, result: dict) -> None:
    rec_dir.mkdir(parents=True, exist_ok=True)
    (rec_dir / "material.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    (rec_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    for rd in result["rounds"]:
        (rec_dir / f"round{rd['round']}.md").write_text(rd["text"], encoding="utf-8")
    (rec_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if result["passed"]:
        out = home() / "out" / str(m.get("id"))
        out.mkdir(parents=True, exist_ok=True)
        name = f"{result['tool']}-{result['writer']}"
        body = result["output"] if isinstance(result["output"], str) else "\n".join(result["output"])
        if result["tool"] in ("article", "note"):
            body = D.with_toc(body)
        (out / f"{name}.md").write_text(body, encoding="utf-8")
        ledger_add(m, result, out / f"{name}.md")
        if result["tool"] == "article":
            a = D.to_wadai(D.parse(body), m)
            (out / f"{name}.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


# ---- the ledger: one row per passed piece, with fields for how it is read (filled later by the routines) ----------------------------------

READ_FIELDS = {"note_url": None, "note_views": None, "site_impressions": None, "site_clicks": None, "poll_answers": None, "updated": None}


def ledger_path() -> Path:
    return home() / "ledger.json"


def ledger_add(m: dict, result: dict, path: Path) -> None:
    lp = ledger_path()
    rows = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else []
    key = f"{m.get('id')}/{result['tool']}"
    row = next((x for x in rows if x["key"] == key), None)
    if row is None:
        row = {"key": key, "id": m.get("id"), "tool": result["tool"], "site": result.get("site"), "reading": dict(READ_FIELDS)}
        rows.append(row)
    body = path.read_text(encoding="utf-8")
    row.update(title=D.parse(body)["title"], writer=result["writer"], reader=result["reader"], file=str(path), passed_at=datetime.now().isoformat(timespec="seconds"))
    lp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def ledger_set(key: str, field: str, value) -> dict:
    lp = ledger_path()
    rows = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else []
    row = next(x for x in rows if x["key"] == key)
    if field not in READ_FIELDS:
        raise KeyError(f"{field}: one of {sorted(READ_FIELDS)}")
    row["reading"][field] = value
    row["reading"]["updated"] = datetime.now().isoformat(timespec="seconds")
    lp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return row
