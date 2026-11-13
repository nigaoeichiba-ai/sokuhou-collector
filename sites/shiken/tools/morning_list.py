#!/usr/bin/env python3
"""データの朝チェックで見る公式ページの一覧を、日程の正本(renewal/template/schedule/registry.json)から機械的に作る(人手のリストは持たない)。

使い方: python3 morning_list.py [--days 30] [--back 7] [--today YYYY-MM-DD] [--json]
対象: 今日の --back 日前から --days 日後までにある出来事(申込締切・試験日・結果発表等)と、申込開始日。同じ出典のものは1行にまとめる。
日程を足せば、一覧も自動で変わる。出力は Markdown(--json で機械可読)。
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "renewal" / "template" / "schedule" / "registry.json"
TYPE_LABEL = {"deadline": "申込締切", "exam": "試験日", "result": "結果発表等", "start": "申込開始"}


def jst_today() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


def build(days: int, today: str | None, back: int = 7, registry: Path = REGISTRY) -> dict:
    r = json.loads(Path(registry).read_text(encoding="utf-8"))
    t = date.fromisoformat(today) if today else jst_today()
    lo, hi = t - timedelta(days=back), t + timedelta(days=days)
    exams = {e["id"]: e for e in r["exams"]}
    groups: dict[str, dict] = {}

    def add(sid, exam_id, kind, iso, time, label):
        d = date.fromisoformat(iso)
        if not (lo <= d <= hi):
            return
        s = r["sources"].get(sid, {})
        g = groups.setdefault(sid, {"source": sid, "org": s.get("title", sid), "url": s.get("url", ""), "events": []})
        g["events"].append({"exam": exams[exam_id]["name"] + "(" + exams[exam_id]["edition"] + ")", "type": TYPE_LABEL[kind], "iso": iso, "time": time or "", "left": (d - t).days,
                            "label": label, "page": f"/exams/{exam_id}/"})

    for x in r["rows"]:
        add(x["sourceId"], x["exam"], x["type"], x["date"], x.get("time"), x.get("label", ""))
    for eid, m in r["meta"].items():
        for a in m.get("application", []):
            if a.get("start"):
                add(a.get("sourceId") or (m.get("sourceIds") or [""])[0], eid, "start", a["start"], a.get("time"), a.get("label", ""))
    out = list(groups.values())
    for g in out:
        g["events"].sort(key=lambda e: (e["iso"], e["time"]))
    out.sort(key=lambda g: g["events"][0]["iso"])
    return {"today": t.isoformat(), "days": days, "sources": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--back", type=int, default=7, help="今日より前の何日分も入れる(合格発表の結果の反映漏れを拾う)")
    ap.add_argument("--today")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    data = build(a.days, a.today, a.back)
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    n_events = sum(len(g["events"]) for g in data["sources"])
    print(f"# データの朝チェック: 公式ページの一覧({data['today']} から {data['days']} 日以内。出典 {len(data['sources'])} 件、出来事 {n_events} 件)\n")
    for g in data["sources"]:
        print(f"## {g['org']}\n- 公式URL: {g['url']}")
        for e in g["events"]:
            print(f"  - {e['iso']} {e['time']} {e['exam']}({e['type']}・{e['label']}、あと{e['left']}日、ページ {e['page']})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
