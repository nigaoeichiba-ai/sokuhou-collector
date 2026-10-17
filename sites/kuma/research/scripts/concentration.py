"""Research note: how concentrated are bear reports within a prefecture?  Share of the top 1 / top 3 municipalities, and how many municipalities make up half of the records.
(Akita, Miyagi, Niigata, Toyama, Yamaguchi, Yamanashi: the sources with 240+ records.)

python sites/kuma/research/scripts/concentration.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MIN_RECORDS = 240
FIX = {"富士河口湖": "富士河口湖町"}


def municipality(city: str) -> str:
    city = FIX.get(city, city)
    return re.sub(r"^(仙台市)[^市]+区$", r"\1", city)      # Sendai's wards are one city; the other sources are already by city


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    stats, rows = {}, []
    for k, label in SOURCES.items():
        s = data[k]
        end = date.fromisoformat(s["as_of"])
        cities = [municipality(r[2]) for r in s["rows"] if (r[0].date() if isinstance(r[0], datetime) else r[0]) <= end]
        assert len(cities) >= MIN_RECORDS and all(cities), k
        c = Counter(cities)
        ranked = c.most_common()
        total = len(cities)
        cum, half_n = 0, None
        for i, (_, n) in enumerate(ranked, 1):
            cum += n
            if cum * 2 >= total:
                half_n = i
                break
        few = sum(1 for _, n in ranked if n < 10)
        stats[k] = dict(total=total, n=len(ranked), top1=ranked[0], top3=sum(n for _, n in ranked[:3]), top3_names=[a for a, _ in ranked[:3]], half_n=half_n, few=few,
                        top1_share=common.pct(ranked[0][1], total), top3_share=common.pct(sum(n for _, n in ranked[:3]), total), half_share=common.pct(half_n, len(ranked)))
        st = stats[k]
        rows.append([label, f"{total:,}", f"{st['n']}", f"{st['top1'][0]}({st['top1_share']:.0f}%)", "・".join(st["top3_names"]), f"{st['top3_share']:.0f}%",
                     f"{half_n}(記録のあった市町村の{st['half_share']:.0f}%)", f"{few}"])
    order = sorted(SOURCES, key=lambda k: stats[k]["top3_share"], reverse=True)
    labels = [SOURCES[k] for k in order]
    top3_vals = [stats[k]["top3_share"] for k in order]
    total = sum(st["total"] for st in stats.values())
    hi, lo = order[0], order[-1]
    half_min = min(st["half_share"] for st in stats.values())
    half_max = max(st["half_share"] for st in stats.values())
    as_of = max(s["as_of"] for s in data.values())
    top1_cities = [stats[k]["top1"][0] for k in SOURCES]

    doc = {
        "slug": "concentration", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃は、県のどの市町村に集まっている?上位3市町の割合を6県で比べる",
        "h1": "熊(クマ)の目撃は、県の中でどれくらい特定の市町村に集まっているか",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の目撃記録{total:,}件を市町村ごとに数え、上位3市町の割合と、記録の半分を占める市町村の数を比べました。数え方と限界つき。",
        "lead": (f"秋田県・宮城県・新潟県・富山県・山口県・山梨県が公表している令和8年度の熊(クマ)の目撃記録{total:,}件を、市町村ごとに数えました。"
                 "県の記録は、いくつかの市町村に偏っているのか、広く散らばっているのか。県ごとに、上位3市町の割合と、記録の半分に達するまでに必要な市町村の数で見ます。"),
        "findings": [
            f"上位3市町の割合がいちばん大きいのは{SOURCES[hi]}で{stats[hi]['top3_share']:.0f}%、いちばん小さいのは{SOURCES[lo]}で{stats[lo]['top3_share']:.0f}%です。",
            f"記録の半分に達するまでに必要な市町村は、記録のあった市町村の{half_min:.0f}〜{half_max:.0f}%でした。県によって、集まり方の形が違います。",
            f"最も件数の多い市町村は、秋田県が{stats['akita']['top1'][0]}、宮城県が{stats['miyagi']['top1'][0]}、新潟県が{stats['niigata']['top1'][0]}、富山県が{stats['toyama']['top1'][0]}、山口県が{stats['yamaguchi']['top1'][0]}、山梨県が{stats['yamanashi']['top1'][0]}です。",
        ],
        "sections": [
            {"h2": "県ごとの上位3市町と、記録の半分に達する市町村の数",
             "paragraphs": ["市町村ごとに件数を数え、多い順に並べました。上位3市町の割合と、多い順に足していって記録の半分に達するまでの市町村の数を、県ごとに出しています。最後の欄は、記録が10件に満たなかった市町村の数です。"],
             "table": {"head": ["県", "件数", "記録のあった市町村", "最も多い市町村(割合)", "上位3市町", "上位3市町の割合", "半分に達するまでの市町村数", "10件未満の市町村"], "rows": rows,
                       "note": "宮城県の仙台市は、区ごとの記録を1つの市にまとめています。割合は、その県の令和8年度の記録の合計に対するものです。"}},
            {"h2": "上位3市町の割合の比べ方",
             "paragraphs": ["県の中での偏りを、上位3市町の割合で並べました。割合が大きい県ほど、少数の市町村に記録が集まっています。"],
             "chart": {"kind": "bars", "labels": labels, "values": top3_vals, "title": "上位3市町が占める記録の割合(%)",
                       "desc": "令和8年度の目撃記録のうち、件数の多い上位3市町が占める割合を、秋田・宮城・新潟・富山・山口・山梨の6県で比べた棒グラフ。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録で、各県の記録が最も新しい日までです(最新の日付は県によって9月30日から10月16日まで)。記録が{MIN_RECORDS}件に届かない県は、市町村ごとの件数が少なすぎるため対象にしていません。",
            "市町村は、公表されている記録の「市町村」の欄のとおりに数えました。宮城県の仙台市の4つの区は1つの市にまとめ、山梨県の1件の「富士河口湖」は富士河口湖町として数えています。",
            "「半分に達するまでの市町村数」は、件数の多い順に足していって、県の記録の半分以上になった時点の市町村の数です。",
        ],
        "caveats": [
            "これは「報告された件数」の分布です。熊が多くいる場所を表すものではありません。人が多く住む市や、通報がしやすい市町村ほど、記録が多くなることがあります。",
            "市町村の面積や人口、山に接する長さは違います。件数の多さは、市町村どうしの優劣や安全性を表しません。",
            "県どうしでは、記録の取り方や公表の範囲が違います(通報だけを数える県、痕跡を含める県など)。そのため、県どうしの割合の大小は、目安として見てください。",
            "令和8年度の1年分だけの数え方です。ほかの年にも同じ集まり方になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/concentration.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    del top1_cities
    common.write_note(doc)
    for k, st in stats.items():
        print(k, st)


if __name__ == "__main__":
    main()
