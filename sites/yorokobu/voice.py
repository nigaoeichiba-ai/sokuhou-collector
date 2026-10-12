"""What visitors typed into the 贈り物コンシェルジュ and chose to send (「送る」), and what the counters say: read it, keep a ledger, analyse it, so that the site can be improved from it.

    python -m sites.yorokobu.voice read [--mark] [--all]     # decrypt the new lines (data/inbox/yorokobu-voice-*.p7m) and add them to the ledger
    python -m sites.yorokobu.voice analyze                    # ANALYSIS.md: the counters (data/yorokobu_ask_stats.json) and the words of the ledger the site does not answer yet

How a line gets here: api/ask.php op "voice" keeps the sentence (2-80 characters; phone numbers, addresses, mail addresses and links are refused) in <site folder>/ask/voice/v-YYYYMM.jsonl
without any address; .github/workflows/yorokobu-voice.yml copies the new lines into data/inbox/ ENCRYPTED (the repository is public); only the owner's PC holds the private key.
The ledger lives next to the research notes (outside git).  **The sentences are never written to the repository, the logs or a report: counts and the words the site lacks only.**
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sokuhou import inbox  # noqa: E402

GROWTH = ROOT.parent / "sokuhou-sites" / "docs" / "yorokobu_growth" / "voice"
LEDGER = GROWTH / "ledger.jsonl"
ANALYSIS = GROWTH / "ANALYSIS.md"
SEEN = Path.home() / ".sokuhou" / "yorokobu_voice_seen.json"
STATS = ROOT / "data" / "yorokobu_ask_stats.json"
KINDS = ("miss", "why", "need", "other")
RUN = re.compile(r"[ァ-ヶー]{2,}|[一-龥々]{2,}")           # katakana and kanji words: what a visitor names (a thing, a person, an occasion)
FILLER = {"プレゼント", "ギフト", "贈り物", "おすすめ", "オススメ", "もの", "のもの", "したい", "たい", "について"}


def read_ledger(path: Path | None = None) -> list[dict]:
    path = path or LEDGER
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_ledger(rows: list[dict], path: Path | None = None) -> None:
    path = path or LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def to_row(rec: dict) -> dict | None:
    """A decrypted inbox record as a ledger row, or None when it is not one of the concierge's."""
    if rec.get("site") != "yorokobu" or rec.get("kind") not in KINDS:
        return None
    text = re.sub(r"\s+", " ", str(rec.get("message", ""))).strip()[:80]
    if not text:
        return None
    return {"id": f"V{str(rec.get('id', ''))[:10]}", "at": rec.get("at", ""), "kind": rec["kind"], "text": text, "status": "new", "note": ""}


def add_new(records: list[dict], ledger: list[dict]) -> list[dict]:
    have = {r["id"] for r in ledger}
    added = []
    for rec in records:
        row = to_row(rec)
        if row and row["id"] not in have:
            ledger.append(row)
            have.add(row["id"])
            added.append(row)
    return added


def known_words() -> set[str]:
    """Words the site already answers: the names and words of the events and people, the themes' keywords, the sale words (so they are not reported as gaps)."""
    from sites.yorokobu import concierge, content
    raw = concierge.load()
    words: set[str] = set()
    c = content.load()
    for o in c["occasions"]:
        words.add(o["name"])
        words.update(raw["occasion_words"].get(o["slug"], []))
    for r in c["recipients"]:
        words.update(raw["recipient_words"].get(r["slug"], []))
        words.add(concierge.base_name(r["name"]))
    for t in c["themes"]:
        words.add(t["name"])
        words.update(t.get("keywords", []))
    words.update(raw["ambiguous_recipients"])
    words.update(("セール", "マラソン", "ポイント", "プライム", "予算", "のし", "マナー", "お返し"))
    return {w for w in words if w}


def gaps(rows: list[dict], known: set[str], top: int = 30) -> list[tuple[str, int]]:
    """Words (katakana / kanji runs) of the sentences that the site does not know, most often first.  A word is counted once per sentence."""
    c: Counter = Counter()
    for r in rows:
        seen = set()
        for w in RUN.findall(r["text"]):
            if w in FILLER or w in seen or any(k and (k in w or w in k) for k in known):
                continue
            seen.add(w)
        c.update(seen)
    return c.most_common(top)


def counters(path: Path | None = None) -> dict[str, dict[str, int]]:
    """The cq.* counters of the stats file, by kind: {'need': {'who': 12, ...}, 'res': {...}, ...}."""
    try:
        d = json.loads((path or STATS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, int]] = {}
    for k, v in (d.get("total") or {}).items():
        p = str(k).split(".")
        if p[0] == "cq" and len(p) == 3 and isinstance(v, int):
            out.setdefault(p[1], {})[p[2]] = v
    return out


def analyze(rows: list[dict], cq: dict[str, dict[str, int]], known: set[str]) -> str:
    lines = ["# コンシェルジュの相談の分析", "", "(文章そのものは、ここに書かない。回数と、サイトにまだ無い言葉だけ)", ""]
    res = cq.get("res", {})
    asked = sum(res.values())
    lines.append(f"## 相談の結果(回数 {asked})")
    for k, label in (("hit", "ページに届いた"), ("part", "近いページに案内した"), ("theme", "テーマに案内した"), ("miss", "読み取れなかった")):
        lines.append(f"- {label}: {res.get(k, 0)}")
    fb = cq.get("fb", {})
    lines.append(f"- 「見つかった」{fb.get('yes', 0)} / 「見つからない」{fb.get('no', 0)}")
    lines += ["", "## 最初の質問で選ばれたこと"]
    for k, v in sorted(cq.get("need", {}).items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}")
    for title, key in (("相手", "rec"), ("イベント", "occ"), ("予算", "bud"), ("見つからなかった理由", "why")):
        items = sorted(cq.get(key, {}).items(), key=lambda kv: -kv[1])[:8]
        if items:
            lines += ["", f"## {title}(上位)"] + [f"- {k}: {v}" for k, v in items]
    by_kind = Counter(r["kind"] for r in rows)
    lines += ["", f"## 送られた文章: {len(rows)}件(読み取れなかった {by_kind['miss']}、理由 {by_kind['why']}、そのほか {by_kind['need'] + by_kind['other']})", "",
              "### サイトにまだ無い言葉(1文に1回数える。2回以上のものは、ページ・テーマ・言い換え語の候補)"]
    for w, n in gaps(rows, known):
        lines.append(f"- {w}: {n}" + (" ← 候補" if n >= 2 else ""))
    lines += ["", "## 直し方の目安", "- 「読み取れなかった」が多い言葉 → content/concierge.json の言い換え語に足す(すぐ効く)。",
              "- 同じ言葉が何度も → テーマ(content/themes.json)か、案(ideas)を足す。", "- 「見つからない」の理由が「予算」→ 価格帯の商品の取得を増やす。「届く日」→ 配送・短納期の読みものを足す。"]
    return "\n".join(lines) + "\n"


def cmd_read(a: argparse.Namespace) -> int:
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() and not a.all else set()
    ledger = read_ledger()
    new_files, added = [], []
    for f in sorted(inbox.INBOX.glob("yorokobu-voice-*.p7m")):
        if f.name in seen:
            continue
        added += add_new(inbox.decrypt(f), ledger)
        new_files.append(f.name)
    write_ledger(ledger)
    if a.mark and new_files:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen | set(new_files))), encoding="utf-8")
    print(f"{len(added)} new line(s) from {len(new_files)} file(s); ledger has {len(ledger)}")        # counts only: the sentences are not printed
    return 0


def cmd_analyze(a: argparse.Namespace) -> int:
    text = analyze(read_ledger(), counters(), known_words())
    ANALYSIS.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("--mark", action="store_true")
    r.add_argument("--all", action="store_true")
    r.set_defaults(fn=cmd_read)
    sub.add_parser("analyze").set_defaults(fn=cmd_analyze)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
