"""Calibration: does the reader gate stop the texts the owner found unnatural, and let the natural ones through?

The set is private (KOBO_HOME/calib/set.json; unpublished drafts): items {"id", "label": "bad" | "good", "source", "text"}.
`build` cuts it from the files of the wadai sample (the old version the owner pointed at, read back from the read-aloud log; the desk's v2;
the voice reference; the excerpts of the four-model comparison).  `run` reads every item with the gate and reports
the share of bad items marked (target >= 0.9) and of good items passed (target: all; report the share).
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import engine as E

SKIP_HEADS = ("更新履歴", "アンケート", "次に読む", "作り直しの注意")


def _blocks(md: str, src: str, label: str, prefix: str) -> list[dict]:
    """Cut an article into items: the lead (with the 3-line summary) and each '## ' section; child pages and history are left out."""
    items, cur, head = [], [], "冒頭"
    for line in md.split("\n"):
        if line.startswith("## ") or line.startswith("---- 子ページ") or line.startswith("■■"):
            if cur and not any(h in head for h in SKIP_HEADS):
                items.append((head, "\n".join(cur).strip()))
            head = line.lstrip("#■- ").strip()
            cur = [line] if line.startswith("## ") else []
            if line.startswith("---- 子ページ"):
                head = "子ページ"
            continue
        if head == "子ページ":
            continue
        cur.append(line)
    if cur and not any(h in head for h in SKIP_HEADS):
        items.append((head, "\n".join(cur).strip()))
    out = []
    for i, (h, t) in enumerate(items):
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        if len(t) >= 40 and not t.startswith("【図】"):
            out.append({"id": f"{prefix}-{i}", "label": label, "source": src, "head": h, "text": t})
    return out


def build(sample_dir: Path) -> list[dict]:
    items: list[dict] = []
    log = (sample_dir / "codex_read.log").read_text(encoding="utf-8", errors="replace").split("\n")
    # the old (owner-criticised) input the reader was given: the four articles between the first '■■' and the reader's answer
    start = next(i for i, ln in enumerate(log) if ln.startswith("■■ 記事"))
    end = next(i for i in range(start, len(log)) if log[i].strip() == "codex")
    old = "\n".join(log[start:end])
    for k, art in enumerate(re.split(r"\n(?=■■ 記事)", old)):
        items += _blocks(art, "旧版(オーナー指摘)codex_read.log", "bad", f"old{k}")
    v2 = (sample_dir / "VOICE_ARTICLE_taifu31_v2.md").read_text(encoding="utf-8").split("\n---\n")[0]
    # editor's notes inside v2 are not article text; the 豆知識 placeholder note is replaced by the confirmed text that went into taifu31.json
    tip = ""
    try:
        art = json.loads((sample_dir / "taifu31.json").read_text(encoding="utf-8"))
        tip = next(b["text"] for s in art["sections"] for b in s.get("boxes", []) if b.get("kind") == "tip")
    except (OSError, ValueError, StopIteration, KeyError):
        pass
    lines = []
    for ln in v2.split("\n"):
        if ln.startswith("> (") and "確認してから" in ln:
            if tip:
                lines.append("> " + tip)
            continue
        if ln.startswith("# ") or ln.startswith("この文章を元に") or ln.startswith("【図】") or ln.startswith("(ここに"):
            continue
        lines.append(ln)
    items += _blocks("\n".join(lines).replace("## タイトル\n", "").replace("## 冒頭\n", ""), "窓口 v2", "good", "v2")
    # the first voice reference (VOICE_REFERENCE_taifu31.md) is left out: v2 replaced it after the owner's remarks
    bake = (sample_dir / "WRITER_BAKEOFF_taifu31_2026-11-04.md").read_text(encoding="utf-8")
    for name in ("fable", "opus", "sonnet"):
        mm = re.search(rf"## {name}\n(.+?)\n", bake)
        if mm:
            items.append({"id": f"bake-{name}", "label": "good", "source": f"比較 {name}(抜粋)", "head": "冒頭", "text": mm.group(1).strip()})
    return items


def build_articles(sample_dir: Path, items: list[dict]) -> list[dict]:
    """Whole articles (the reader reads each in its context; 2026-11-04: blocks cut out of an article drew marks for missing context):
    the four old articles (bad) and the desk's v2 (good), made from the block items."""
    arts: dict = {}
    for it in items:
        if it["id"].endswith("fix") or it["id"].startswith("bake"):
            continue
        key = it["id"].rsplit("-", 1)[0]
        arts.setdefault(key, {"id": key, "label": it["label"], "source": it["source"], "head": "全文", "parts": []})["parts"].append(it["text"])
    return [dict({k: v for k, v in a.items() if k != "parts"}, text="\n\n".join(a["parts"])) for a in arts.values()]


def density(it: dict) -> float:
    """Stopping marks (level >= 2 after the second read) per 300 characters."""
    n = sum(1 for m in it["gate"]["marks"] if m["level"] >= 2)
    return round(n * 300 / max(1, len(it["text"])), 2)


def run(items: list[dict], reader: str, workers: int = 4) -> dict:
    def one(it):
        try:
            g = E.read_gate(it["text"], reader)
        except Exception as e:        # noqa: BLE001
            g = {"marks": [], "impression": "", "unparsed": True, "error": str(e)}
        return dict(it, gate=g, marked=not E.gate_pass(g))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(one, items))
    bad = [r for r in res if r["label"] == "bad"]
    good = [r for r in res if r["label"] == "good"]
    errors = [r["id"] for r in res if r["gate"].get("error") or r["gate"].get("unparsed")]
    summary = {"reader": reader, "bad": len(bad), "bad_marked": sum(r["marked"] for r in bad), "good": len(good),
               "good_passed": sum(not r["marked"] for r in good), "errors": errors}
    summary["bad_rate"] = round(summary["bad_marked"] / max(1, len(bad)), 3)
    summary["good_rate"] = round(summary["good_passed"] / max(1, len(good)), 3)
    return {"summary": summary, "items": res}
