"""The planning stage (企画): before any body text, three plans for a series from the news facts and the product kinds;
a reader of the other family points out the weak points and picks one; the picked plan is reworked until the reader has no
stopping point (at most 2 times); the desk makes the final choice.  Body text is written only from a decided plan.

A plan brief (private, KOBO_HOME/plans/<id>/brief.json):
{"id": "bousai", "site": "wadai", "facts": [{"text": ..., "status": "primary" | "multi" | "calc"}],
 "products": [{"kind": "携帯トイレ", "note": "what can be said about it"}], "direction": ["the desk's lines"]}
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import engine as E
from . import runner
from .material import OK_STATUS, numbers

SECTION_PRODUCTS = "置く商品の種類"
SECTION_ACTIONS = "読者に動いてもらう仕掛け"
SECTION_HONEST = "誠実さの線"
# alarm words; a negation right after ('直撃はしない') is the fact and is fine
ALARM = re.compile(r"直撃(?!\s*(?:は|も)?\s*(?:しない|しません|ではない|ではありません|とは書かない|と書かない))|命に関わる|命を守る|今すぐ買|手遅れ|大半の家|ほとんどの家|足りない家が多|必ず|絶対|買い占め|売り切れ")
MAX_REVISE = 2


def split_plans(text: str) -> list[str]:
    parts = re.split(r"\n(?=# 案)", "\n" + E._strip_fence(text))
    return [p.strip() for p in parts if p.strip().startswith("# 案")]


def sections(plan: str) -> dict:
    out, cur = {}, None
    for ln in plan.split("\n"):
        if ln.startswith("## "):
            cur = ln[3:].strip()
            out[cur] = []
        elif cur is not None and ln.strip():
            out[cur].append(ln.strip())
    return out


def _section(secs: dict, key: str) -> list[str]:
    return next((v for k, v in secs.items() if key in k), [])


def plan_checks(plan: str, brief: dict) -> list[dict]:
    """Machine checks of one plan: kinds of products, reader actions, alarm words, numbers that are not in the facts."""
    secs = sections(plan)
    out = []
    prods = [ln for ln in _section(secs, SECTION_PRODUCTS) if re.match(r"^[-・*\d]", ln) or "—" in ln]
    if len(prods) < 3:
        out.append({"code": "P01", "block": True, "msg": f"商品の種類が{len(prods)}つです。ニュースと困りごとにつながる種類を、3つ以上置いてください。"})
    acts = [ln for ln in _section(secs, SECTION_ACTIONS) if re.match(r"^[-・*\d]", ln)]
    if len(acts) < 2:
        out.append({"code": "P02", "block": True, "msg": f"読者に動いてもらう仕掛けが{len(acts)}つです。2つ以上にしてください。"})
    body = "\n".join(ln for k, v in secs.items() if SECTION_HONEST not in k for ln in v)
    for mm in ALARM.finditer(body):
        out.append({"code": "P03", "block": True, "msg": f"煽り・根拠のない断定の言葉「{mm.group(0)}」があります。危機感は事実と数字から作ってください。"})
    src = "\n".join(f["text"] for f in brief.get("facts", [])) + "\n".join(p.get("note", "") for p in brief.get("products", []))
    extra = sorted(numbers(plan) - numbers(src) - {str(i) for i in range(0, 11)})
    if extra:
        out.append({"code": "P04", "block": False, "msg": "事実にない数字(計算で出したものなら、式を素材に残す): " + "、".join(extra[:12])})
    if not secs:
        out.append({"code": "P05", "block": True, "msg": "企画の見出しがありません(書く形のとおりに)。"})
    return out


def _facts_text(brief: dict) -> str:
    return "\n".join(f"- {f['text']}" for f in brief.get("facts", []) if f.get("status") in OK_STATUS)


def _products_text(brief: dict) -> str:
    return "\n".join(f"- {p['kind']}" + (f": {p['note']}" if p.get("note") else "") for p in brief.get("products", []))


def review(plans: list[str], brief: dict, reader: str) -> dict:
    listing = "\n\n".join(plans)
    res = E.parse_json(runner.call(reader, E.fill(E.prompt_file("plan_review"), facts=_facts_text(brief), plans=listing)))
    if "_unparsed" in res:
        return {"plans": [], "choice": None, "unparsed": True, "raw": res["_unparsed"][:1500]}
    return res


def _stopping(rv: dict, no: int, level: int = 3) -> list[dict]:
    """Points that stop a plan: level 3 ('this plan cannot go out'). Level-2 points go to the desk with the plan (the desk decides)."""
    p = next((x for x in rv.get("plans", []) if int(x.get("no", 0) or 0) == no), {})
    return [i for i in p.get("issues", []) if int(i.get("level", 2) or 2) >= level]


def run(brief: dict, card: dict, writer: str = "opus", reader: str | None = None, record: bool = True) -> dict:
    reader = reader or runner.other_family(writer)
    if runner.FAMILY[reader] == runner.FAMILY[writer]:
        raise ValueError("the plan reviewer must be of another family than the writer")
    cp = E.card_parts(card)
    prompt = E.fill(E.prompt_file("plan"), site_name=cp["site_name"], reader=cp["reader"], tone=cp["tone"], facts=_facts_text(brief),
                    products=_products_text(brief), direction="\n".join(f"- {d}" for d in brief.get("direction", [])) or "(なし)")
    system = E.prompt_file("system_writer")
    plans = split_plans(runner.call(writer, prompt, system))
    checks = [plan_checks(p, brief) for p in plans]
    rv = review(plans, brief, reader)
    history = [{"plans": plans, "checks": checks, "review": rv}]
    choice = rv.get("choice")
    try:
        choice = int(choice)
    except (TypeError, ValueError):
        choice = None
    chosen = plans[choice - 1] if choice and 0 < choice <= len(plans) else None
    passed = False
    cur = choice
    if chosen is not None:
        issues = _stopping(rv, choice)
        mc = [c for c in plan_checks(chosen, brief) if c["block"]]
        for k in range(MAX_REVISE + 1):
            if not issues and not mc and k > 0:
                passed = True
                break
            if not issues and not mc and not _stopping(rv, cur, 2):
                passed = True
                break
            if k == MAX_REVISE:
                break
            notes = "\n".join(f"- {c['msg']}" for c in mc) + ("\n" if mc else "") + "\n".join(f"- {x}" for x in rv.get("improve", []))
            rp = E.fill(E.prompt_file("plan_revise"), facts=_facts_text(brief), products=_products_text(brief), plan=chosen,
                        issues="\n".join(f"- [{i.get('kind', '')}] {i.get('text', '')}" for i in issues) or "(なし)", notes=notes or "(なし)")
            new = split_plans(runner.call(writer, rp, system))
            if not new:
                break
            chosen = new[0]
            rv = review([chosen.replace("# 案", "# 案1", 1) if not chosen.startswith("# 案1") else chosen], brief, reader)
            cur = 1
            issues = _stopping(rv, cur)
            mc = [c for c in plan_checks(chosen, brief) if c["block"]]
            history.append({"plans": [chosen], "checks": [plan_checks(chosen, brief)], "review": rv})
    result = {"brief": brief.get("id"), "writer": writer, "reader": reader, "plans": plans, "choice": choice, "chosen": chosen or "",
              "passed": passed, "history": history}
    if record:
        out = E.home() / "plans" / str(brief.get("id")) / datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "plans.md").write_text(summary_md(result), encoding="utf-8")
        result["record"] = str(out)
    return result


def summary_md(r: dict) -> str:
    """The page the desk reads to decide: the three plans, the reader's points, the reworked pick."""
    rv0 = r["history"][0]["review"]
    lines = [f"# 企画の候補({r['brief']}) 書き手 {r['writer']} / 読者役 {r['reader']}", "",
             f"読者役の選択: 案{r['choice']}。理由: {rv0.get('why', '')}", f"直したあとの企画が読者役の指摘(重さ2以上)と機械の検査を通ったか: {'通った' if r['passed'] else '通っていない'}", ""]
    for i, p in enumerate(r["plans"], 1):
        rvp = next((x for x in rv0.get("plans", []) if int(x.get("no", 0) or 0) == i), {})
        lines += [p, "", f"**読者役の指摘(案{i})**: " + (rvp.get("good", "") or "")]
        lines += [f"- [{x.get('kind', '')}・{x.get('level', '')}] {x.get('text', '')}" for x in rvp.get("issues", [])]
        lines += [f"- 機械: {c['msg']}" for c in r["history"][0]["checks"][i - 1]]
        lines += ["", "---", ""]
    lines += ["# 選ばれた案(直したあと)", "", r["chosen"]]
    return "\n".join(lines) + "\n"
