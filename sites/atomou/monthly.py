"""The monthly thanks of atomou.com (run by .github/workflows/atomou-monthly.yml with a copy of the server's members folder).

    python -m sites.atomou.monthly rank   --dir <members copy> --month 2026-11 [--adopted data/atomou/adopted.json]
    python -m sites.atomou.monthly export --dir <members copy> --state data/inbox/state.json --out new_monitor.jsonl

rank:   counts last month's QUALIFIED referrals per member (the server logs the month in "ref_log" when a referred person has used the site
        on two days a week apart) and the monitors whose opinion was adopted (data/atomou/adopted.json, written by the AI session that read the
        answers: {"month", "ref", "note"}; the note says what was changed, it is never the member's own text).  Writes into the folder:
          awards.json  {member id: [{"key", "months", "badge"}]}   applied by api/m.php on the member's next visit, once per key
          thanks.json  {"updated", "months": [{"month", "referrers": [{"rank", "name", "n"}], "adopted": [{"name", "note"}]}]}   public
        Names are pen names whose owner agreed to show them; otherwise 「匿名の方」.  Rewards: referrals 1st 3 months, 2nd-3rd 1 month;
        an adopted opinion 1 month and the badge "monitor_star" (once a month per member).  Time only, never money.
export: the monitors' questionnaire answers that were not exported yet, as inbox records (sokuhou.inbox read shows them); the workflow
        encrypts the file with sokuhou/inbox_cert.pem before it goes into the public repository.  Prints counts only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sites.atomou import members

ANON = "匿名の方"
REF_REWARD = {1: 3, 2: 1, 3: 1}
KEEP_MONTHS = 12
FREQ = {"daily": "ほぼ毎日", "weekly": "週に数回", "rarely": "ときどき"}
USE = {"count": "日数を数える", "calendar": "カレンダー", "todo": "やること", "official": "公式の日付", "notice": "通知", "other": "そのほか"}


def last_month(today: date | None = None) -> str:
    t = today or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    y, m = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def shown_name(m: dict) -> str:
    pen = str(m.get("pen") or "").strip()
    return pen if pen and m.get("pen_ok") else ANON


def rank(all_members: list[tuple[str, dict]], month: str, adopted: list[dict], old_awards: dict, old_thanks: dict) -> tuple[dict, dict]:
    by_ref = {m.get("ref_code"): (mid, m) for mid, m in all_members if m.get("ref_code")}
    counts = sorted(((sum(1 for x in (m.get("ref_log") or []) if x == month), mid, m) for mid, m in all_members), key=lambda t: -t[0])
    counts = [c for c in counts if c[0] > 0]
    awards = {k: [x for x in v if str(x.get("key", ""))[:7] >= _cut(month)] for k, v in (old_awards or {}).items()}
    referrers, rank_no, prev = [], 0, None
    for i, (n, mid, m) in enumerate(counts):
        if n != prev:
            rank_no, prev = i + 1, n
        if rank_no > 3:
            break
        referrers.append({"rank": rank_no, "name": shown_name(m), "n": n})
        awards.setdefault(mid, []).append({"key": f"{month}:ref", "months": REF_REWARD[rank_no], "badge": "referrer_star" if rank_no == 1 else ""})
    adopted_out, given = [], set()
    for a in adopted or []:
        if a.get("month") != month or a.get("ref") not in by_ref:
            continue
        mid, m = by_ref[a["ref"]]
        adopted_out.append({"name": shown_name(m), "note": str(a.get("note") or "")[:80]})
        if mid not in given:
            given.add(mid)
            awards.setdefault(mid, []).append({"key": f"{month}:adopted", "months": 1, "badge": "monitor_star"})
    for k in list(awards):
        seen, keep = set(), []
        for x in awards[k]:
            if x["key"] not in seen:
                seen.add(x["key"])
                keep.append(x)
        awards[k] = keep
        if not keep:
            del awards[k]
    months = [x for x in (old_thanks or {}).get("months", []) if x.get("month") != month]
    months.append({"month": month, "referrers": referrers, "adopted": adopted_out})
    months = sorted(months, key=lambda x: x["month"], reverse=True)[:KEEP_MONTHS]
    return awards, {"updated": datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d"), "months": months}


def _cut(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    y -= 1
    return f"{y:04d}-{m:02d}"


def export(all_members: list[tuple[str, dict]], state: dict) -> tuple[list[dict], dict]:
    done = set(state.get("atomou-monitor", {}).get("done", []))
    out = []
    for _mid, m in all_members:
        for n, ans in sorted((m.get("survey") or {}).items()):
            token = hashlib.sha256(f"{m.get('ref_code')}:{n}".encode()).hexdigest()[:16]
            if token in done or not isinstance(ans, dict):
                continue
            done.add(token)
            out.append({"id": str(m.get("ref_code") or ""), "at": str(ans.get("at") or ""), "site": "atomou",
                        "kind": f"モニターのアンケート {n}/2(使う頻度: {FREQ.get(ans.get('freq'), '?')}、よく使う: {USE.get(ans.get('use'), '?')})",
                        "message": str(ans.get("text") or "").strip() or "(自由記述なし)", "email": "", "page": ""})
    new_state = dict(state)
    new_state["atomou-monitor"] = {"done": sorted(done)}
    return out, new_state


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except ValueError:
        return default


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--dir", required=True)
    r.add_argument("--month", default=last_month())
    r.add_argument("--adopted", default=str(Path(__file__).resolve().parents[2] / "data" / "atomou" / "adopted.json"))
    e = sub.add_parser("export")
    e.add_argument("--dir", required=True)
    e.add_argument("--state", required=True)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    folder = Path(a.dir)
    if not (folder / "key").exists():
        print(json.dumps({"skipped": "no members yet"}))
        return 0
    all_members = members.load_members(folder, members.load_key(folder))
    if a.cmd == "rank":
        awards, thanks = rank(all_members, a.month, _load_json(Path(a.adopted), []), _load_json(folder / "awards.json", {}), _load_json(folder / "thanks.json", {}))
        (folder / "awards.json").write_text(json.dumps(awards, ensure_ascii=False), encoding="utf-8")
        (folder / "thanks.json").write_text(json.dumps(thanks, ensure_ascii=False), encoding="utf-8")
        cur = thanks["months"][0] if thanks["months"] and thanks["months"][0]["month"] == a.month else {"referrers": [], "adopted": []}
        print(json.dumps({"month": a.month, "members": len(all_members), "referrers": len(cur["referrers"]), "adopted": len(cur["adopted"]), "awarded_members": len(awards)}))
    else:
        state_path = Path(a.state)
        out, new_state = export(all_members, _load_json(state_path, {}))
        Path(a.out).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8", newline="\n")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
        print(json.dumps({"exported": len(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
