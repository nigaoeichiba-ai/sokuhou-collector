"""The counters of the 診断ドック and of all "それとなく聞く" answers, merged into data/yorokobu_ask_stats.json (run by .github/workflows/yorokobu-ask-stats.yml).

    python -m sites.yorokobu.askstats --dir <folder with the monthly counter files> --out data/yorokobu_ask_stats.json
    python -m sites.yorokobu.askstats --report data/yorokobu_ask_stats.json        # a short reading of the numbers, for the routines that improve the site

A counter file is {"dock.occ.birthday": 12, "ask.q1.home": 7, ...}: how often an option was chosen in a month.  Nothing in it says who chose it, or in which survey.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KEY = re.compile(r"^((dock|ask)\.[a-z0-9]{1,8}\.[a-z0-9_-]{1,32}|pop\.[ra]\.[A-Za-z0-9._:-]{3,64})$")
MIN_SHOWN = 50          # the public page of the data room shows a counter only once at least this many answers / reports are behind it


def merge(folder: Path) -> dict:
    months: dict[str, dict[str, int]] = {}
    for p in sorted(folder.glob("*.json")):
        m = re.fullmatch(r"(\d{4}-\d{2})\.json", p.name)
        if not m:
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            months[m.group(1)] = {k: int(v) for k, v in raw.items() if KEY.match(str(k)) and isinstance(v, int) and v >= 0}
    total: dict[str, int] = {}
    for counts in months.values():
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
    return {"months": months, "total": dict(sorted(total.items()))}


def load(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"months": {}, "total": {}}
    return d if isinstance(d, dict) and isinstance(d.get("total"), dict) else {"months": {}, "total": {}}


def report(d: dict) -> str:
    t = d.get("total", {})
    n_ask, n_new = t.get("ask.n.all", 0), t.get("ask.new.o", 0) + t.get("ask.new.s", 0)
    lines = [f"surveys made: {n_new} (open {t.get('ask.new.o', 0)}, secret {t.get('ask.new.s', 0)}); answers: {n_ask}"]
    by_q: dict[str, dict[str, int]] = {}
    for k, v in t.items():
        p = k.split(".")
        if p[0] == "ask" and re.fullmatch(r"q\d+", p[1]):
            by_q.setdefault(p[1], {})[p[2]] = v
    for q in sorted(by_q, key=lambda s: int(s[1:])):
        top = sorted(by_q[q].items(), key=lambda kv: -kv[1])[:4]
        lines.append(f"  {q}: " + ", ".join(f"{o} {c}" for o, c in top))
    dock = {}
    for k, v in t.items():
        p = k.split(".")
        if p[0] == "dock":
            dock.setdefault(p[1], {})[p[2]] = v
    if dock:
        lines.append(f"dock reports: {dock.get('n', {}).get('all', 0)}")
        for g, c in sorted(dock.items()):
            if g != "n":
                lines.append(f"  {g}: " + ", ".join(f"{o} {n}" for o, n in sorted(c.items(), key=lambda kv: -kv[1])[:6]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--out")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    if a.report:
        print(report(load(Path(a.report))))
        return 0
    if not (a.dir and a.out):
        ap.error("--dir and --out, or --report")
    data = merge(Path(a.dir))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"months: {len(data['months'])}, counters: {len(data['total'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
