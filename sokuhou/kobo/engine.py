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
        rp = fill(prompt_file("revise"), head=head_text(m, card) if tool != "rewrite" else "【もとの文章】\n" + source, draft=base["text"], marks=_marks(g), notes=notes)
        # the 突っ込み役 works on the first draft only (the desk's order: writer -> checks -> 突っ込み役 -> fixes -> reader gate);
        # run on every round, it reworked the writer's targeted fixes and the text swung back and forth (2026-11-04)
        text = _keep_shape(runner.call(writer, rp, system), base["text"], tool)
    if record:
        save(rec_dir, m, prompt, result)
    result["record"] = str(rec_dir) if record else ""
    return result


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
