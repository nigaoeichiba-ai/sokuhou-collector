"""What people search for around gifts, and which of it the site does not answer yet (run by the daily routine; see sokuhou-sites/docs/YOROKOBU_DEMAND_ROUTINE.md).

    python -m sites.yorokobu.demand run [--out DIR] [--limit N]      # widen seeds with the public autocomplete, add the Search Console queries, write <out>/<date>.json and QUEUE.md
    python -m sites.yorokobu.demand show [--out DIR]                 # print the newest queue

Inputs (all optional; a missing one is skipped, never guessed):
  - the public autocomplete of Google (seeds: every event and every person of the site, with a few usual words);
  - data/yorokobu_queries.json: the queries Search Console showed for the site ([{"query", "impressions", "clicks", "position"}], written by the routine that reads Search Console);
  - the counters and sentences of the concierge (voice.py) for the words the site could not read.
Each query is read with the same word lists as the concierge (content/concierge.json), then sorted into: answered (a page of the event × person exists), a missing PAIR page, or
words the site does not know (a theme / an idea / a word for concierge.json).  The queue is what the content factory (factory.py) is fed with, and what the routine turns into edits.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import concierge, content  # noqa: E402

OUT = ROOT.parent / "sokuhou-sites" / "docs" / "yorokobu_growth" / "demand"
QUERIES = ROOT / "data" / "yorokobu_queries.json"
SUGGEST = "https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q="
UA = {"User-Agent": "Mozilla/5.0 (compatible; yorokobu-demand/1.0)"}
MODIFIERS = ("", " 人気", " おすすめ", " 安い", " 予算", " 実用的", " おしゃれ", " 手作り", " 喜ばれる")
RUN = re.compile(r"[ァ-ヶー]{2,}|[一-龥々]{2,}")
FILLER = {"プレゼント", "ギフト", "贈り物", "おすすめ", "オススメ", "人気", "ランキング", "もの", "喜ばれる", "予算", "安い", "実用", "実用的", "おしゃれ", "手作り", "センス", "男性", "女性", "楽天", "通販", "アマゾン", "メルカリ", "万円", "千円", "代女性", "代男性", "から", "子供から"}


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").lower().strip()


class Lexicon:
    """The concierge's word lists, in Python: which event and which person a query names, which words it holds that the site does not know."""

    def __init__(self) -> None:
        c, raw = content.load(), concierge.load()
        self.occ = [(o["slug"], concierge._words(o["name"], raw["occasion_words"].get(o["slug"], []))) for o in c["occasions"]]
        self.rec = [(r["slug"], concierge._words(concierge.base_name(r["name"]), raw["recipient_words"].get(r["slug"], []))) for r in c["recipients"]]
        self.amb = raw["ambiguous_recipients"]
        self.pairs = {content.pair_key(p) for p in c["pairs"]}
        self.themes = [(t["slug"], [w for w in t.get("keywords", []) if len(w) >= 2] + [t["name"]]) for t in c["themes"]]
        self.known = {norm(w) for _, ws in self.occ + self.rec + self.themes for w in ws} | {norm(w) for w in self.amb} | {"セール", "マラソン", "ポイント", "プライム", "のし", "マナー", "お返し"}

    @staticmethod
    def _find(items, text):
        best = None
        for slug, words in items:
            for w in words:
                w = norm(w)
                i = text.find(w) if w else -1
                while i >= 0:
                    if len(w) == 1 and ("一" <= text[i - 1:i] <= "鿿" or "一" <= text[i + 1:i + 2] <= "鿿"):
                        i = text.find(w, i + 1)
                        continue
                    if not best or len(w) > len(best[1]):
                        best = (slug, w)
                    break
        return best

    def read(self, query: str) -> dict:
        text = norm(query)
        o = self._find(self.occ, text)
        rest = text.replace(o[1], " ") if o else text
        r = self._find(self.rec, rest)
        amb = next((w for w in self.amb if norm(w) in rest), "") if not r else ""
        words = [w for w in RUN.findall(text) if w not in FILLER and not any(k in norm(w) or norm(w) in k for k in self.known)]
        theme = next((s for s, ws in self.themes if any(norm(w) in text for w in ws)), "")
        return {"occ": o[0] if o else "", "rec": r[0] if r else "", "amb": amb, "theme": theme, "unknown": words}

    def classify(self, query: str) -> tuple[str, dict]:
        """('answered' | 'pair' | 'theme' | 'unknown' | 'other', the reading)."""
        r = self.read(query)
        if r["occ"] and r["rec"]:
            return ("answered" if f"{r['occ']}-{r['rec']}" in self.pairs else "pair"), r
        if r["unknown"]:
            return "unknown", r
        if r["theme"] or r["occ"] or r["rec"]:
            return "answered", r
        return "other", r


def seeds(limit: int | None = None) -> list[str]:
    c = content.load()
    base = [f"{o['name']} プレゼント" for o in c["occasions"]] + [f"{concierge.base_name(r['name'])} プレゼント" for r in c["recipients"]]
    out = [b + m for b in base for m in MODIFIERS]
    return out[:limit] if limit else out


def suggest(q: str, fetch=None) -> list[str]:
    try:
        raw = (fetch or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15).read()))(SUGGEST + urllib.parse.quote(q))
        data = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
        return [s for s in data[1] if isinstance(s, str)]
    except (OSError, ValueError, IndexError, TypeError):
        return []


def collect(qs: list[str], fetch=None, pause: float = 0.4) -> dict[str, int]:
    """{suggestion: how many seeds produced it} (a suggestion several seeds agree on is a stronger sign)."""
    seen: Counter = Counter()
    for q in qs:
        for s in set(suggest(q, fetch)):
            seen[s] += 1
        if fetch is None:
            time.sleep(pause)
    return dict(seen)


def load_queries(path: Path | None = None) -> list[dict]:
    try:
        d = json.loads((path or QUERIES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = d.get("queries", d) if isinstance(d, dict) else d
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("query"), str)]


def build(suggestions: dict[str, int], gsc: list[dict], lex: Lexicon) -> dict:
    """The queue: missing pairs, unknown words, and how the Search Console queries are answered."""
    pairs: dict[str, dict] = defaultdict(lambda: {"n": 0, "example": ""})
    words: dict[str, dict] = defaultdict(lambda: {"n": 0, "example": ""})
    for q, n in suggestions.items():
        kind, r = lex.classify(q)
        if kind == "pair":
            e = pairs[f"{r['occ']}-{r['rec']}"]
            e["n"] += n; e["example"] = e["example"] or q
        elif kind == "unknown":
            for w in r["unknown"]:
                e = words[w]
                e["n"] += n; e["example"] = e["example"] or q
    gsc_rows = []
    for row in gsc:
        kind, r = lex.classify(row["query"])
        gsc_rows.append({**{k: row.get(k) for k in ("query", "impressions", "clicks", "position")}, "kind": kind, "occ": r["occ"], "rec": r["rec"], "unknown": r["unknown"]})
    return {"date": date.today().isoformat(), "suggestions": len(suggestions),
            "pairs": sorted(({"key": k, **v} for k, v in pairs.items()), key=lambda x: -x["n"]),
            "words": sorted(({"word": k, **v} for k, v in words.items()), key=lambda x: -x["n"]),
            "gsc": sorted(gsc_rows, key=lambda x: -(x["impressions"] or 0))}


def queue_md(q: dict, voice_gaps: list[tuple[str, int]] | None = None) -> str:
    lines = [f"# よろこぶプレゼント 需要のキュー ({q['date']})", "", f"サジェスト {q['suggestions']}語を、サイトの辞書で読んだ結果。上から順に対応する。", ""]
    lines += ["## 1. ページが無い「イベント × 相手」(pairs.json に足す候補)"]
    lines += [f"- {p['key']}: {p['n']}回(例: {p['example']})" for p in q["pairs"][:20]] or ["- なし"]
    lines += ["", "## 2. サイトが知らない言葉(テーマ・案・concierge.json の言い換え語の候補)"]
    lines += [f"- {w['word']}: {w['n']}回(例: {w['example']})" for w in q["words"][:30]] or ["- なし"]
    if voice_gaps:
        lines += ["", "## 3. コンシェルジュに送られた文章の、サイトに無い言葉(回数のみ)"] + [f"- {w}: {n}" for w, n in voice_gaps[:20]]
    g = q["gsc"]
    if g:
        lines += ["", "## 4. Search Console の検索語(表示回数の多い順)", "| 検索語 | 表示 | クリック | 順位 | 状態 |", "|---|---|---|---|---|"]
        label = {"answered": "ページあり(タイトル・見出しを検索語に合わせる)", "pair": "ページ無し(pair を足す)", "unknown": "知らない言葉(テーマ・案)", "other": "読めない"}
        for r in g[:25]:
            lines.append(f"| {r['query']} | {r['impressions']} | {r['clicks']} | {r['position']} | {label.get(r['kind'], r['kind'])} |")
    lines += ["", "## 対応のしかた(毎日の routine)", "1. concierge.json の言い換え語に足す(すぐ効く。テストを通して公開)。", "2. 2回以上の言葉・ペアは、factory で テーマ(brief themes)に。ペアは pairs.json に。",
              "3. 表示回数が多い検索語のページは、title / description / 見出し / 冒頭を、検索語に合わせて直す(直す前の数字を残して、2週間後に見る)。"]
    return "\n".join(lines) + "\n"


def cmd_run(a: argparse.Namespace) -> int:
    lex = Lexicon()
    sug = collect(seeds(a.limit)) if not a.no_suggest else {}
    gsc = load_queries()
    q = build(sug, gsc, lex)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{q['date']}.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    vg = []
    try:
        from sites.yorokobu import voice
        vg = voice.gaps(voice.read_ledger(), voice.known_words())
    except Exception:                                                  # no ledger on this machine: the section is left out
        vg = []
    (out / "QUEUE.md").write_text(queue_md(q, vg), encoding="utf-8", newline="\n")
    print(f"suggestions {q['suggestions']}, missing pairs {len(q['pairs'])}, unknown words {len(q['words'])}, search console queries {len(gsc)}")
    return 0


def cmd_show(a: argparse.Namespace) -> int:
    p = Path(a.out) / "QUEUE.md"
    print(p.read_text(encoding="utf-8") if p.exists() else "(no queue yet)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", default=str(OUT))
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--no-suggest", action="store_true")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("show")
    s.add_argument("--out", default=str(OUT))
    s.set_defaults(fn=cmd_show)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
