"""Research note: how many bears does one sighting report name?  Share of sighting reports that name two or more bears, by prefecture and by season.
(Akita, Niigata, Toyama, Yamaguchi, Yamanashi: the sources that record a head count; only reports of kind 目撃 with a count of 1 or more are used.)

python sites/kuma/research/scripts/count_per_report.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import json  # noqa: E402

SOURCES = {"akita": "秋田県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
SEASONS = [("4〜6月", (4, 5, 6)), ("7〜8月", (7, 8)), ("9月", (9,))]
MIN_RECORDS = 200


def month_of(v) -> int:
    return v.month


def main() -> None:
    data, counts = {}, {}
    for k in SOURCES:
        src = common.load_source(k)
        raw = json.loads((common.DATA / f"{k}_kuma.json").read_text(encoding="utf-8"))
        fy = [x for x in raw["sightings"] if x["observed_at"][:10] >= common.FY_START.isoformat()]
        data[k] = src
        counts[k] = [(int(x["observed_at"][5:7]), x["count"]) for x in fy if x["kind"] == "目撃" and isinstance(x.get("count"), int) and x["count"] >= 1]
    stats, rows = {}, []
    for k, label in SOURCES.items():
        c = counts[k]
        assert len(c) >= MIN_RECORDS, k
        multi = sum(1 for _, n in c if n >= 2)
        heads = sum(n for _, n in c)
        by_season = []
        for name, months in SEASONS:
            sub = [n for m, n in c if m in months]
            by_season.append((name, len(sub), sum(1 for n in sub if n >= 2)))
        stats[k] = dict(n=len(c), multi=multi, share=common.pct(multi, len(c), 1), heads=heads, per=round(heads / len(c), 2), seasons=by_season)
        rows.append([label, f"{len(c):,}", f"{multi}件({stats[k]['share']:.1f}%)", f"{stats[k]['per']}頭"] +
                    [(f"{m}/{n}件({common.pct(m, n, 1):.1f}%)" if n >= 30 else f"{n}件(件数が少なく比べない)") for _, n, m in by_season])
    order = sorted(SOURCES, key=lambda k: stats[k]["share"], reverse=True)
    hi, lo = order[0], order[-1]
    tot_n = sum(s["n"] for s in stats.values())
    tot_m = sum(s["multi"] for s in stats.values())
    as_of = max(s["as_of"] for s in data.values())
    end = min(date.fromisoformat(s["as_of"]) for s in data.values())
    three = sum(1 for k in SOURCES for _, n in counts[k] if n >= 3)

    doc = {
        "slug": "count-per-report", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃は、1件に何頭と報告されているか。5県で、2頭以上の割合を数える",
        "h1": "熊(クマ)の目撃1件に何頭と書かれているか。2頭以上の報告の割合を県ごとに数える",
        "description": f"秋田・新潟・富山・山口・山梨の令和8年度の目撃記録のうち、頭数が書かれた{tot_n:,}件を数え、2頭以上と報告された割合を県別・時期別に比べました。",
        "lead": (f"目撃の記録には、見た熊の頭数が書かれているものがあります。ほとんどは1頭ですが、2頭以上の報告はどれくらいあるのでしょうか。"
                 f"頭数の記録がある5県の目撃{tot_n:,}件を数えると、2頭以上と報告されたのは{tot_m:,}件({common.pct(tot_m, tot_n, 1):.1f}%)でした。県別と時期別に見ていきます。"),
        "findings": [
            f"目撃1件のうち、2頭以上と報告された割合は、{SOURCES[hi]}が{stats[hi]['share']:.1f}%でいちばん大きく、{SOURCES[lo]}が{stats[lo]['share']:.1f}%でいちばん小さくなりました。",
            f"5県を合わせると、頭数の書かれた目撃{tot_n:,}件のうち、2頭以上は{tot_m:,}件({common.pct(tot_m, tot_n, 1):.1f}%)です。残りは1頭と報告された件です。",
            f"3頭以上と報告された目撃は、5県で{three}件({common.pct(three, tot_n, 1):.1f}%)でした。",
        ],
        "sections": [
            {"h2": "県ごとの、2頭以上の報告の割合",
             "paragraphs": ["「頭数の書かれた目撃」は、種別が目撃で、頭数が1以上と記録されている件です。痕跡(足跡・糞・食害)と、頭数の空欄は含めていません。時期別の欄は、30件に届かない場合は割合を出していません。"],
             "table": {"head": ["県", "頭数の書かれた目撃", "2頭以上の報告", "1件あたりの平均", "4〜6月", "7〜8月", "9月"], "rows": rows,
                       "note": "令和8年度(2026年4月1日から)の記録です。時期は、目撃のあった月で分けました。"}},
            {"h2": "割合の比べ方",
             "paragraphs": ["割合が大きい県ほど、2頭以上いたという報告が、目撃のうちで多めです。"],
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [stats[k]["share"] for k in order], "title": "2頭以上と報告された目撃の割合(%)",
                       "desc": "頭数の書かれた目撃のうち、2頭以上と報告された件の割合を、秋田・新潟・富山・山口・山梨の5県で比べた棒グラフ。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の目撃の記録のうち、頭数が1以上の整数で書かれたものです。記録の最新日は県で違い、いちばん早いのは{end.month}月{end.day}日です。それぞれの県の最新の記録まで数えています。",
            "頭数の記録がない県(宮城県など)と、頭数が空欄の記録は、数えていません。頭数の記録が200件に届かない県は、割合が偶然に左右されるため対象にしていません。",
            "「平均」は、頭数を足して件数で割った値です。「2頭以上」は、1件の記録に2頭以上と書かれた件数です。",
        ],
        "caveats": [
            "頭数は、通報した人の見たままの数です。同じ熊を別の人が通報していても、1件ずつ数えています。実際の熊の頭数ではありません。",
            "県によって、頭数の書き方や、親子を何頭と数えるかが違う可能性があります。県どうしの大小は目安として見てください。",
            "2頭以上の報告が多い時期や県があっても、その理由はこの記録だけでは言えません。令和8年度の記録で、ほかの年にも同じになるとは限りません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/count_per_report.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, st in stats.items():
        print(k, st)
    print(three, end)


if __name__ == "__main__":
    main()
