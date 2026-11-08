#!/usr/bin/env python3
"""データの朝チェックで見る公式ページの一覧を、サイトのデータから機械的に作る(人手のリストは持たない)。

使い方: python3 morning_list.py [--days 30] [--today YYYY-MM-DD] [--json]
元: sites/shiken/gen/model.py の EVENT_LIST(申込開始・申込締切・試験日・合格発表。どの出典かを source で持つ)と、
    sites/shiken/gen/sources.py の SOURCES(出典の団体・ページ・公式URL)。
対象: 今日の --back 日前から --days 日後までにある出来事(申込締切・試験日・合格発表。申込開始も含める)。同じ出典のものは1行にまとめる。
データを足せば、一覧も自動で変わる。出力は Markdown(--json で機械可読)。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def build(days: int, today: str | None, back: int = 7):
    from sites.shiken.gen import common
    if today:
        common.set_today(today)
    from sites.shiken.gen import model
    from sites.shiken.gen.sources import OFFICIAL_PAGES as SOURCES
    todays = common.TODAY
    groups: dict[str, dict] = {}
    for e in model.EVENT_LIST:
        n = common.left(e["iso"])
        if not (-back <= n <= days):
            continue
        g = groups.setdefault(e["source"], {"source": e["source"], "events": []})
        g["events"].append({"exam": e["name"], "type": model.TYPE_LABEL[e["type"]], "iso": e["iso"], "time": e["time"], "left": n, "page": e["url"]})
    out = []
    for sid, g in groups.items():
        s = SOURCES.get(sid, {})
        g["org"] = s.get("org", "")
        g["table"] = s.get("table", "")
        g["url"] = s.get("url", "")
        g["events"].sort(key=lambda x: (x["iso"], x["time"]))
        out.append(g)
    out.sort(key=lambda g: g["events"][0]["iso"])
    return {"today": todays.isoformat(), "days": days, "sources": out}


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
        print(f"## {g['org']}: {g['table']}\n- 公式URL: {g['url']}")
        for e in g["events"]:
            print(f"  - {e['iso']} {e['time']} {e['exam']}({e['type']}、あと{e['left']}日、ページ {e['page']})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
