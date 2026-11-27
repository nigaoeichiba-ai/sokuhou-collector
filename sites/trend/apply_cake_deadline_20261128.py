#!/usr/bin/env python3
"""2026-11-28: the Aeon early-order deadline (11/27 15:00) has passed, so the cake article now leads with the
deadlines that are still open (checked on 11/15, stated as such).  Safe to run twice."""
import json
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "trend-xmas-cake-hayawari.json")

SWAPS = [
    ("早割の締切は、最も早いイオンのネット予約が2026年11月27日15時です。ここから12月1日までに、大手コンビニとスーパーの締切が固まっています。",
     "早割で次に来る締切は、セブンイレブンのアプリ予約の11月30日23時59分です。ファミリーマートとローソンも12月1日で区切られます。イオンのネット予約の早割は、11月27日15時で締め切られました。"),
    ("<li>早割の締切は、イオンのネット予約が11月27日15時、セブンイレブンのアプリ予約が11月30日23時59分、ファミリーマートとローソンが12月1日まで（2026年11月15日確認）</li>",
     "<li>早割の締切は、セブンイレブンのアプリ予約が11月30日23時59分、ファミリーマートとローソンが12月1日まで（2026年11月15日確認）。イオンのネット予約の早割は11月27日15時で終了</li>"),
    ("11月27日15時（ネット予約）", "終了（11月27日15時まで）"),
    ("<li>買いたい店を絞り、この記事の表で早割の締切を確認する（イオンのネット予約は11月27日15時が最初の山場）</li>",
     "<li>買いたい店を絞り、この記事の表で早割の締切を確認する（次の山場はセブンイレブンの11月30日23時59分）</li>"),
]


def main():
    d = json.load(open(P, encoding="utf-8"))
    if d["updated"] == "2026-11-28":
        return print("already applied")
    body = json.dumps(d["sections"], ensure_ascii=False)
    for old, new in SWAPS:
        o, n = (json.dumps(x, ensure_ascii=False)[1:-1] for x in (old, new))
        assert o in body, old[:30]
        body = body.replace(o, n)
    d["sections"] = json.loads(body)
    d["sections"][0]["html"] = d["sections"][0]["html"].replace("締切は11月27日から12月1日に集中", "次の締切は11月30日と12月1日")
    d.update({
        "updated": "2026-11-28",
        "data_basis": "各社の締切は2026年11月15日確認。2026年11月28日に終了分を反映",
        "title": "クリスマスケーキの早割、次の締切は11月30日と12月1日",
        "h1": "クリスマスケーキの早割、次の締切は11月30日と12月1日。受け取り日を先に決めよう",
        "top_lead": "クリスマスケーキの早割、次の締切は11月30日と12月1日。受け取り日を先に決めましょう。",
        "description": "2026年のクリスマスケーキの早割は、セブンが11月30日23時59分、ファミマ・ローソンが12月1日まで。割引の中身と対象の条件、予約の決め方を表でまとめました。",
        "answer": "クリスマスケーキの早割で次に来る締切は、セブンが11月30日23時59分、ファミマとローソンが12月1日です。",
        "secondary_kw": ["クリスマスケーキ 早割 締切 2026", "クリスマスケーキ 早割 コンビニ"],
        "todo": {"deadline": "2026-11-30", "badge": "セブンは30日まで", "title": "ケーキの早割、受け取り日を決めて予約する",
                 "text": "セブンイレブンのアプリ予約は11月30日23時59分まで。ファミマとローソンは12月1日が締切です。"},
    })
    open(P, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed")


if __name__ == "__main__":
    main()
