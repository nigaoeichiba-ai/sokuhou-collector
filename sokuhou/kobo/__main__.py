"""文章工房 (kobo): write public Japanese text that reads naturally, check it, and let a reader of another model family pass it.

    python -m sokuhou.kobo plan <brief.json> [--writer opus] [--reader codex]   # 企画: 3案 -> 読者役が指摘して選ぶ -> 直す (窓口が決める)
    python -m sokuhou.kobo tsukkomi <draft.md> --models haiku,sonnet          # 突っ込み役 only: points and the revised text per model
    python -m sokuhou.kobo questions <material> [--draft text.md]   # 当事者の疑問出し -> 公的資料の確認(引用を取得して照合) -> 構成案
    python -m sokuhou.kobo tools                                   # the tools (like Catchy's forms)
    python -m sokuhou.kobo article <material> [--writer opus] [--reader codex]
    python -m sokuhou.kobo title|lead|outline|tldr|tips|threads <material> [--writer ...]
    python -m sokuhou.kobo rewrite --site wadai --in draft.txt     # make an existing text natural (facts unchanged)
    python -m sokuhou.kobo compare <material> --writers haiku,sonnet,opus,fable
    python -m sokuhou.kobo check <draft.md> <material>             # machine checks only (no model)
    python -m sokuhou.kobo read <draft.md> [--reader codex]        # the reader gate only
    python -m sokuhou.kobo import-wadai <article.json> [--weight heavy]
    python -m sokuhou.kobo calib build|run [--reader codex]

<material> is a path or an id in KOBO_HOME/materials/.  Records go to KOBO_HOME/runs/, passed texts to KOBO_HOME/out/<id>/.
KOBO_HOME is private (default: ../sokuhou-sites/work/kobo, outside git).  Nothing is published or posted; no API key is used.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import calibrate, checks, doc, engine, material
from . import plan as planmod
from . import questions as qmod

TOOL_HELP = {
    "article": "記事一本(タイトル・冒頭2文・3行まとめ・見出しごとの本文・ライフハック・豆知識)",
    "title": "タイトル案(5案。読者役が通したものだけ)",
    "lead": "導入文(2文。3案)",
    "outline": "見出し構成",
    "tldr": "3行まとめ",
    "tips": "ライフハック2つと豆知識(豆知識は素材で確認できた話だけ。なければ出さない)",
    "threads": "Threads の速報の本文と返信",
    "rewrite": "リライト(既存の文を自然な日本語に。事実は変えない)",
}


def _material(arg: str) -> dict:
    p = Path(arg)
    if not p.exists():
        p = engine.home() / "materials" / (arg if arg.endswith(".json") else arg + ".json")
    return material.load(p)


def _print_result(r: dict) -> None:
    print(f"[{r['tool']}] material={r['material']} writer={r['writer']} reader={r['reader']} judge={r['judge']} "
          f"passed={r['passed']} rewrites={r['rewrites']} ({r['seconds']}s)")
    for rd in r["rounds"]:
        n_block = sum(1 for fs in rd["findings"] for f in fs if f["block"])
        n_marks = sum(1 for mk in rd["reader"]["marks"] if mk["level"] >= engine.PASS_LEVEL)
        print(f"  round {rd['round']}: machine={n_block} unsupported={len(rd['support']['unsupported'])} reader_marks={n_marks} passed_units={rd['passed']}/{rd['units']}")
    if r["passed"]:
        out = r["output"] if isinstance(r["output"], str) else "\n".join(r["output"])
        print("\n" + out)
    else:
        print("\n(not passed: nothing is output. The last version is in the record.)")
    if r.get("record"):
        print(f"\nrecord: {r['record']}")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m sokuhou.kobo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tools")
    for t in engine.TOOLS:
        p = sub.add_parser(t)
        if t in ("rewrite", "note"):
            p.add_argument("--in", dest="inp", required=True)
            p.add_argument("--material", default="")
        else:
            p.add_argument("material")
        p.add_argument("--site", default="")
        p.add_argument("--writer", default=None)
        p.add_argument("--reader", default=None)
        p.add_argument("--rewrites", type=int, default=engine.MAX_REWRITES)
        p.add_argument("--tsukkomi", default="default", help="the 突っ込み役 model (haiku/sonnet/opus/fable/codex), or none")
        p.add_argument("--heavy", action="store_true", help="reader gate + fact judge + rewrite rounds (only for topics the desk names)")
    p = sub.add_parser("batch", help="light mode: several materials at once, in parallel")
    p.add_argument("materials", nargs="+")
    p.add_argument("--tool", default="article")
    p.add_argument("--writer", default=None)
    p.add_argument("--tsukkomi", default="default")
    p = sub.add_parser("plan")
    p.add_argument("brief")
    p.add_argument("--writer", default="opus")
    p.add_argument("--reader", default=None)
    p = sub.add_parser("questions")
    p.add_argument("material")
    p.add_argument("--draft", default="", help="a written text: ask what is still left after writing")
    p.add_argument("--ask-model", default="sonnet")
    p.add_argument("--research-model", default="sonnet")
    p.add_argument("--structure-model", default="opus")
    p = sub.add_parser("tsukkomi")
    p.add_argument("draft")
    p.add_argument("--models", default="haiku,sonnet")
    p = sub.add_parser("ledger")
    p.add_argument("action", choices=["list", "set"])
    p.add_argument("key", nargs="?", default="")
    p.add_argument("field", nargs="?", default="")
    p.add_argument("value", nargs="?", default="")
    p = sub.add_parser("compare")
    p.add_argument("material")
    p.add_argument("--writers", default="haiku,sonnet,opus,fable")
    p.add_argument("--reader", default=None)
    p.add_argument("--tool", default="article")
    p = sub.add_parser("check")
    p.add_argument("draft")
    p.add_argument("material")
    p.add_argument("--site", default="")
    p = sub.add_parser("read")
    p.add_argument("draft")
    p.add_argument("--reader", default="codex")
    p = sub.add_parser("import-wadai")
    p.add_argument("json")
    p.add_argument("--weight", default="heavy")
    p = sub.add_parser("calib")
    p.add_argument("action", choices=["build", "run"])
    p.add_argument("--reader", default="codex")
    p.add_argument("--sample-dir", default=str(engine.HERE.parents[2] / "sokuhou-sites" / "work" / "wadai_sample"))
    p.add_argument("--only", default="", help="comma-separated item ids")
    p.add_argument("--articles", action="store_true", help="read whole articles (in context) instead of blocks")
    p.add_argument("--repeat", type=int, default=1, help="read every item this many times (stability)")
    a = ap.parse_args(argv)

    if a.cmd == "tools":
        for k, v in TOOL_HELP.items():
            print(f"{k:8s} {v}")
        return 0
    if a.cmd == "plan":
        bp = Path(a.brief)
        if not bp.exists():
            bp = engine.home() / "plans" / a.brief / "brief.json"
        brief = json.loads(bp.read_text(encoding="utf-8"))
        r = planmod.run(brief, engine.load_card(brief.get("site", "wadai")), writer=a.writer, reader=a.reader)
        print(f"[plan] {brief.get('id')} writer={r['writer']} reader={r['reader']} plans={len(r['plans'])} choice={r['choice']} passed={r['passed']} rounds={len(r['history'])}")
        print(f"record: {r.get('record', '')}  (plans.md is the page for the desk)")
        return 0 if r["passed"] else 1
    if a.cmd == "questions":
        m = _material(a.material)
        card = engine.load_card(m.get("site", "wadai"))
        draft = Path(a.draft).read_text(encoding="utf-8") if a.draft else ""
        res = qmod.run(m, card, draft=draft, ask_model=a.ask_model, research_model=a.research_model, structure_model=a.structure_model)
        from datetime import datetime
        out = engine.home() / "questions" / str(m["id"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "summary.md").write_text(qmod.summary_md(res), encoding="utf-8")
        mq = engine.home() / "materials" / f"{m['id']}-q.json"
        mq.write_text(json.dumps(dict(res["material"], id=f"{m['id']}-q", structure=res["structure"]), ensure_ascii=False, indent=1), encoding="utf-8")
        r = res["research"]
        print(f"[questions] {m['id']} questions={len(res['questions']['questions'])} type1={sum(q['answer_type'] == 1 for q in res['questions']['questions'])} "
              f"checked={len(r['accepted'])} dropped={len(r['dropped'])}")
        print(f"record: {out} (summary.md)  material with the checked answers: {mq}")
        return 0
    if a.cmd == "ledger":
        if a.action == "set":
            v = int(a.value) if a.value.isdigit() else a.value
            print(json.dumps(engine.ledger_set(a.key, a.field, v), ensure_ascii=False, indent=1))
            return 0
        lp = engine.ledger_path()
        for r in (json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else []):
            rd = r["reading"]
            print(f"{r['key']:28s} {r.get('title', '')[:30]:30s} note={rd['note_views']} 表示={rd['site_impressions']} クリック={rd['site_clicks']} 回答={rd['poll_answers']}")
        return 0
    if a.cmd == "tsukkomi":
        src = Path(a.draft).read_text(encoding="utf-8")
        ms = a.models.split(",")
        with ThreadPoolExecutor(max_workers=len(ms)) as ex:
            res = list(ex.map(lambda mo: engine.tsukkomi(src, mo), ms))
        out = engine.home() / "tsukkomi"
        out.mkdir(parents=True, exist_ok=True)
        from collections import Counter
        for r in res:
            kinds = Counter(str(x.get("kind", "")) for x in r["points"])
            print(f"[{r['model']}] points={len(r['points'])} parsed={r['ok']} " + " ".join(f"{k}={v}" for k, v in kinds.most_common()))
            for x in r["points"]:
                print(f"   [{x.get('kind', '')}]「{str(x.get('text', ''))[:40]}」 {str(x.get('ask', ''))[:60]} → {str(x.get('fix', ''))[:50]}")
            stem = f"{Path(a.draft).stem}-{r['model']}"
            (out / f"{stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            (out / f"{stem}.md").write_text(r["revised"], encoding="utf-8")
        print(f"saved: {out}")
        return 0
    if a.cmd == "import-wadai":
        art = json.loads(Path(a.json).read_text(encoding="utf-8"))
        m = material.from_wadai(art, a.weight, Path(a.json).stem)
        dst = engine.home() / "materials" / f"{m['id']}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        probs = material.validate(m)
        print(f"wrote {dst}" + ("" if not probs else "\nproblems: " + "; ".join(probs)))
        return 0
    if a.cmd == "check":
        m = _material(a.material)
        card = engine.load_card(a.site or m.get("site", "wadai"))
        d = doc.parse(Path(a.draft).read_text(encoding="utf-8"))
        fs = checks.check(d, m, card)
        for f in fs:
            print(f"{'BLOCK' if f.block else 'note '} {f.code} {f.msg}" + (f"  [{f.detail}]" if f.detail and f.detail not in f.msg else ""))
        print(f"\n{len(checks.blocking(fs))} blocking, {len(fs) - len(checks.blocking(fs))} notes")
        return 1 if checks.blocking(fs) else 0
    if a.cmd == "read":
        g = engine.read_gate(Path(a.draft).read_text(encoding="utf-8"), a.reader)
        print(json.dumps(g, ensure_ascii=False, indent=1))
        return 0 if engine.gate_pass(g) else 1
    if a.cmd == "calib":
        cdir = engine.home() / "calib"
        cdir.mkdir(parents=True, exist_ok=True)
        if a.action == "build":
            items = calibrate.build(Path(a.sample_dir))
            (cdir / "set.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{len(items)} items: {sum(i['label'] == 'bad' for i in items)} bad, {sum(i['label'] == 'good' for i in items)} good -> {cdir / 'set.json'}")
            return 0
        items = json.loads((cdir / "set.json").read_text(encoding="utf-8"))
        if a.articles:
            items = calibrate.build_articles(Path(a.sample_dir), items)
        if a.repeat > 1:
            items = [dict(it, id=f"{it['id']}#{k + 1}") for it in items for k in range(a.repeat)]
        if a.only:
            keep = set(a.only.split(","))
            items = [i for i in items if i["id"] in keep]
        res = calibrate.run(items, a.reader)
        from datetime import datetime
        out = cdir / f"run-{a.reader}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        s = res["summary"]
        print(json.dumps(s, ensure_ascii=False))
        for r in res["items"]:
            top = max([mk["level"] for mk in r["gate"]["marks"]] or [0])
            n3 = sum(1 for mk in r["gate"]["marks"] if mk["level"] >= 3)
            print(f"  {r['label']:4s} {r['id']:10s} {'MARKED' if r['marked'] else 'pass  '} max_level={top} marks={len(r['gate']['marks'])} L3={n3} per300={calibrate.density(r)} len={len(r['text'])}  {r['head'][:20]}")
        print(f"result: {out}")
        return 0
    if a.cmd == "compare":
        m = _material(a.material)
        card = engine.load_card(m.get("site", "wadai"))
        ws = a.writers.split(",")
        with ThreadPoolExecutor(max_workers=len(ws)) as ex:
            rs = list(ex.map(lambda w: engine.run(a.tool, m, card, writer=w, reader=a.reader), ws))
        for r in rs:
            _print_result(r)
            print("=" * 60)
        return 0
    if a.cmd == "batch":
        import time as _t
        t0 = _t.time()
        def one(name):
            m = _material(name)
            return engine.light(a.tool, m, engine.load_card(m.get("site", "wadai")), writer=a.writer, tsukkomi_model=a.tsukkomi)
        with ThreadPoolExecutor(max_workers=len(a.materials)) as ex:
            rs = list(ex.map(one, a.materials))
        for r in rs:
            _print_light(r)
        print(f"batch: {len(rs)} pages in {round(_t.time() - t0)}s (in parallel)")
        return 0
    # the writing tools
    if a.cmd == "note":
        src = Path(a.inp).read_text(encoding="utf-8")
        m = _material(a.material)
        card = engine.load_card(a.site or m.get("site", "wadai"))
        r = engine.run("note", m, card, writer=a.writer, reader=a.reader, source=src, rewrites=a.rewrites, tsukkomi_model=a.tsukkomi)
        _print_result(r)
        return 0 if r["passed"] else 1
    if a.cmd == "rewrite":
        src = Path(a.inp).read_text(encoding="utf-8")
        m = _material(a.material) if a.material else {"id": Path(a.inp).stem, "site": a.site or "wadai", "weight": "mid", "names": []}
        card = engine.load_card(a.site or m.get("site", "wadai"))
        r = engine.run("rewrite", m, card, writer=a.writer, reader=a.reader, source=src, rewrites=a.rewrites, tsukkomi_model=a.tsukkomi)
    else:
        m = _material(a.material)
        card = engine.load_card(a.site or m.get("site", "wadai"))
        if not a.heavy:
            r = engine.light(a.cmd, m, card, writer=a.writer, tsukkomi_model=a.tsukkomi)
            _print_light(r)
            return 0
        r = engine.run(a.cmd, m, card, writer=a.writer, reader=a.reader, rewrites=a.rewrites, tsukkomi_model=a.tsukkomi)
    _print_result(r)
    return 0 if r["passed"] else 1


def _print_light(r: dict) -> None:
    sec = r["seconds"]
    print(f"[{r['tool']} light] material={r['material']} writer={r['writer']} tsukkomi={r['tsukkomi']} "
          f"marks={len(r['marks'])} (strong {sum(x['strong'] for x in r['marks'])}) time={sec['total']}s (writer {sec['writer']}s, tsukkomi {sec['tsukkomi']}s)")
    for x in r["marks"]:
        print(f"  - {x['label']}: {x['msg'][:90]}")
    if r.get("out"):
        print(f"  out: {r['out']}")


if __name__ == "__main__":
    raise SystemExit(main())
