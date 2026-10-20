"""Research note: how large is the share of traces (footprints, droppings, feeding damage) among the bear records, and does it rise in autumn?
(Akita, Miyagi, Niigata, Toyama, Yamaguchi: the sources that tell sightings and traces apart; Yamanashi lists sightings only.)

python sites/kuma/research/scripts/trace-ratio.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県"}
MIN_MONTH = 20           # a month with fewer records is shown as a dash
MIN_PERIOD = 30          # a period with fewer records is not compared
EARLY = (4, 5, 6, 7, 8)  # April-August
LATE = (9, 10)           # September-October


def is_trace(kind: str) -> bool:
    return kind.startswith("痕跡")


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    stats, rows = {}, []
    monthly = {}
    for k, label in SOURCES.items():
        s = data[k]
        end = date.fromisoformat(s["as_of"])
        recs = []
        for r in s["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if d <= end:
                recs.append((d.month, is_trace(r[1])))
        monthly[k] = recs
        total, trace = len(recs), sum(1 for _, t in recs if t)
        e = [t for m, t in recs if m in EARLY]
        l = [t for m, t in recs if m in LATE]
        st = dict(total=total, trace=trace, share=common.pct(trace, total, 1), e_n=len(e), e_t=sum(e), l_n=len(l), l_t=sum(l),
                  e_share=common.pct(sum(e), len(e), 1), l_share=common.pct(sum(l), len(l), 1), comparable=len(e) >= MIN_PERIOD and len(l) >= MIN_PERIOD)
        stats[k] = st
        rows.append([label, f"{total:,}", f"{trace:,}", f"{st['share']:.1f}%",
                     f"{st['e_share']:.1f}%({st['e_t']}/{st['e_n']})", f"{st['l_share']:.1f}%({st['l_t']}/{st['l_n']})" if len(l) else "—"])
    month_rows = []
    month_hi = {}
    for m in (4, 5, 6, 7, 8, 9, 10):
        cells = []
        for k in SOURCES:
            recs = [t for mm, t in monthly[k] if mm == m]
            cells.append(f"{common.pct(sum(recs), len(recs), 0):.0f}%({sum(recs)}/{len(recs)})" if len(recs) >= MIN_MONTH else "-")
            if len(recs) >= MIN_MONTH:
                month_hi[(k, m)] = sum(recs) / len(recs)
        month_rows.append([f"{m}月"] + cells)
    top_month = max(month_hi, key=month_hi.get)
    low_month = min(month_hi, key=month_hi.get)
    comp = [k for k in SOURCES if stats[k]["comparable"]]
    up = [k for k in comp if stats[k]["l_share"] > stats[k]["e_share"]]
    order = sorted(SOURCES, key=lambda k: stats[k]["share"], reverse=True)
    hi, lo = order[0], order[-1]
    total = sum(st["total"] for st in stats.values())
    all_trace = sum(st["trace"] for st in stats.values())
    as_of = max(s["as_of"] for s in data.values())
    comp_names = "・".join(SOURCES[k] for k in comp)
    excl = [SOURCES[k] for k in SOURCES if k not in comp]
    big = max(comp, key=lambda k: stats[k]["l_share"] - stats[k]["e_share"])
    diff_big = f"増え方がいちばん大きい{SOURCES[big]}は、{stats[big]['e_share']:.1f}%から{stats[big]['l_share']:.1f}%でした。"

    doc = {
        "slug": "trace-ratio", "date": "2026-10-18", "data_as_of": as_of,
        "title": "熊(クマ)の記録のうち、足跡・糞などの痕跡は何割?5県の割合と、4〜8月と9〜10月の違い",
        "h1": "熊(クマ)の記録のうち、目撃ではなく痕跡の報告は何割か",
        "description": f"秋田・宮城・新潟・富山・山口の令和8年度の記録{total:,}件のうち、足跡・糞・食害などの痕跡が占める割合を県ごとに数え、4〜8月と9〜10月で比べました。数え方と限界つき。",
        "lead": (f"熊の記録には、姿を見た「目撃」のほかに、足跡・糞・食害などの「痕跡」の報告が混じっています。秋田県・宮城県・新潟県・富山県・山口県の令和8年度の記録{total:,}件のうち、痕跡は{all_trace:,}件でした。"
                 "県ごとの割合と、4〜8月・9〜10月での違いを数えます。"),
        "findings": [
            f"痕跡の割合がいちばん大きいのは{SOURCES[hi]}で{stats[hi]['share']:.1f}%、いちばん小さいのは{SOURCES[lo]}で{stats[lo]['share']:.1f}%です。",
            f"4〜8月と9〜10月を比べられる{comp_names}では、9〜10月の割合が高い県が{len(comp)}県中{len(up)}県でした。{diff_big}",
            "痕跡の割合は、県の記録の取り方に左右されます。県どうしの差は、熊の行動の差とは言えません。",
        ],
        "sections": [
            {"h2": "県ごとの痕跡の件数と割合",
             "paragraphs": ["記録の「種別」の欄が、痕跡(足跡・糞・食害などの「その他」を含む)になっているものを数えました。右の2つの欄は、4〜8月と9〜10月に分けた割合です。かっこの中は、痕跡の件数 / その期間の記録の件数です。"],
             "table": {"head": ["県", "記録", "痕跡", "痕跡の割合", "4〜8月の痕跡の割合", "9〜10月の痕跡の割合"], "rows": rows,
                       "note": "9〜10月の記録が少ない県は、割合を比べていません。秋田県の記録は9月30日まで、ほかの県は10月15・16日までです。"}},
            {"h2": "月ごとの痕跡の割合",
             "paragraphs": [f"期間を月に分けて、痕跡の割合を数えました。記録が{MIN_MONTH}件に満たない月は「-」です。月の割合のうち、いちばん高いのは{SOURCES[top_month[0]]}の{top_month[1]}月({month_hi[top_month] * 100:.0f}%)、いちばん低いのは{SOURCES[low_month[0]]}の{low_month[1]}月({month_hi[low_month] * 100:.0f}%)でした。",
                            "同じ県の中でも、月によって割合は大きく動きます。月ごとの記録の件数が少ない県と月では、数件の違いで割合が変わるため、1か月の数字だけで傾向を決めることはできません。"],
             "table": {"head": ["月"] + [SOURCES[k] for k in SOURCES], "rows": month_rows,
                       "note": "かっこの中は、痕跡の件数 / その月の記録の件数です。数えた期間は、各県の記録が最も新しい日までです。"}},
            {"h2": "痕跡の割合の比べ方",
             "paragraphs": ["県ごとの痕跡の割合を並べました。山梨県は目撃だけを公表しているため、入れていません。"],
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [stats[k]["share"] for k in order], "title": "記録のうち痕跡が占める割合(%)",
                       "desc": "令和8年度の記録のうち、足跡・糞・食害などの痕跡が占める割合を、秋田・宮城・新潟・富山・山口の5県で比べた棒グラフ。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録で、各県の記録が最も新しい日までです。種別が「痕跡」で始まるもの(痕跡・痕跡(食害)・痕跡(その他))を痕跡として数え、宮城県の「その他」は痕跡に入れていません。",
            f"4〜8月と9〜10月に分け、どちらかの記録が{MIN_PERIOD}件に満たない県は、割合を比べていません" + (f"({'・'.join(excl)})。" if excl else "。"),
            "山梨県は目撃だけを公表しているため、対象にしていません。",
        ],
        "caveats": [
            "県によって、痕跡を記録に入れるかどうかが違います。痕跡の割合の差は、記録の取り方の差を含みます。",
            "9〜10月の記録は、4〜8月より少なく、割合は件数の少ない中での値です。1件の増減で数ポイント動きます。",
            "痕跡が多いことは、熊の数や危険の大きさを表しません。令和8年度の1年分だけの数え方で、ほかの年にも同じになるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/trace-ratio.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, st in stats.items():
        print(k, st)


if __name__ == "__main__":
    main()
