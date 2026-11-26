#!/usr/bin/env python3
"""2026-11-27 deadline rows: the New Year card discount that ends tonight is no longer called "the next deadline", the
30th one (read on the company's page today) is given for after it, and the Misdo net-order status is re-dated (still
stopped on the official pages today).  Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
TODAY = "2026-11-27"

NENGA = [
    ("年賀状印刷の早割、次の締切は27日。30枚で約4,500円差", "年賀状印刷の早割、締切は27日と30日！30枚で約4,500円差"),
    ("年賀状の早割、次の締切は27日の年賀状スクエア（45％OFF）。割引率ではなく総額で比べましょう。",
     "年賀状の早割は、年賀状スクエア45％OFFが27日まで、しまうまプリント12％OFFが30日まで。総額で比べましょう。"),
    ("年賀状印刷の早割は、年賀状スクエア45％OFFが27日23:59まで、しまうまプリント12％OFFが30日まで。",
     "年賀状印刷の早割は、年賀状スクエア45％OFFが11月27日23:59まで、しまうまプリント12％OFFが30日12:59まで。"),
    ("年賀状印刷の早割は、年賀状スクエアの45％OFFが27日（金）23:59までで、次の締切です。",
     "年賀状印刷の早割は、年賀状スクエアの45％OFFが11月27日（金）23:59まで、しまうまプリントの12％OFFが30日（月）12:59まで。27日に間に合わない場合は、30日締切のほうが候補です。"),
    ("年賀状印刷の早割は、次の締切が27日の<a", "年賀状印刷の早割で、11月27日が締切なのは<a"),
    ("しまうまプリントの12％OFFは11月30日までです。</p>",
     "しまうまプリントの12％OFFは11月30日（月）12:59までで、27日の締切に間に合わない場合の候補です（11月27日確認）。年賀状スクエアの27日より後の割引は確認できていません。</p>"),
    ("27日の23:59までに年賀状スクエアで決めるなら、週末までに枚数とデザインを決めておくと余裕があります。",
     "年賀状スクエアの45％OFFで頼むなら、11月27日（金）の23:59までに注文を終えましょう。"),
]
MISDO = [("（2026年11月26日確認）。", "（2026年11月27日確認）。")]


def edit(slug, pairs, first_only=()):
    path = os.path.join(CONTENT, slug + ".json")
    d = json.load(open(path, encoding="utf-8"))
    if d["updated"] == TODAY:
        print("skip (already):", slug)
        return
    used = set()

    def walk(v):
        if isinstance(v, str):
            for old, new in pairs:
                if old in v:
                    if old in first_only and old in used:
                        continue
                    used.add(old)
                    v = v.replace(old, new)
            return v
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v

    d = walk(d)
    missing = [old for old, _ in pairs if old not in used]
    assert not missing, (slug, missing)
    d["updated"] = TODAY
    open(path, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed", slug)


if __name__ == "__main__":
    edit("trend-nengajo-hayawari", NENGA)
    # only the sentence about the stopped net order is re-dated
    edit("trend-misdo-fukubukuro-2027", [("再開時期は未定です（2026年11月26日確認）。", "再開時期は未定です（2026年11月27日確認）。")])
