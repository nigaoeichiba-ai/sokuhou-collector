"""Research note: how far apart are the records of the same day?  For each record with coordinates, the distance to the nearest other record of the same day;
the share within 5 km.  Reference: the day labels shuffled among the records of the same week (300 draws, fixed seed), which keeps each week's records and each day's count.
Akita is also split by month.

python sites/kuma/research/scripts/same-day-distance.py
"""
from __future__ import annotations

import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import json  # noqa: E402

SOURCES = {"akita": "秋田県", "niigata": "新潟県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
NEAR_KM = 5
DRAWS = 300
BANDS = (1, 5, 10, 20)


def hv(a, b) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl, dp = math.radians(b[1] - a[1]), p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def load(key: str):
    raw = json.loads((common.DATA / f"{key}_kuma.json").read_text(encoding="utf-8"))
    recs = [(x["observed_at"][:10], (x["lat"], x["lon"])) for x in raw["sightings"]
            if x["observed_at"][:10] >= common.FY_START.isoformat() and x.get("lat") and x.get("lon")]
    return raw, recs


def nearest(recs):
    """[(day, nearest km)] of the records that have another record on the same day."""
    days = defaultdict(list)
    for d, p in recs:
        days[d].append(p)
    out = []
    for d, v in days.items():
        if len(v) < 2:
            continue
        for i, p in enumerate(v):
            out.append((d, min(hv(p, q) for j, q in enumerate(v) if j != i)))
    return out


def main() -> None:
    rng = random.Random(20261030)
    st, rows, raws = {}, [], {}
    for k, label in SOURCES.items():
        raw, recs = load(k)
        raws[k] = raw
        real = nearest(recs)
        n = len(real)
        share = sum(1 for _, x in real if x <= NEAR_KM) / n
        med = statistics.median(x for _, x in real)
        weeks = defaultdict(list)
        for i, (d, _) in enumerate(recs):
            weeks[date.fromisoformat(d).isocalendar()[:2]].append(i)
        sims, sim_med, sim_month = [], [], defaultdict(list)
        for _ in range(DRAWS):
            new = list(recs)
            for idx in weeks.values():
                ds = [recs[i][0] for i in idx]
                rng.shuffle(ds)
                for i, d in zip(idx, ds):
                    new[i] = (d, recs[i][1])
            r = nearest(new)
            sims.append(sum(1 for _, x in r if x <= NEAR_KM) / len(r))
            sim_med.append(statistics.median(x for _, x in r))
            if k == "akita":
                by = defaultdict(list)
                for d, x in r:
                    by[int(d[5:7])].append(x <= NEAR_KM)
                for m, v in by.items():
                    sim_month[m].append(sum(v) / len(v))
        sims.sort()
        sim_med.sort()
        lo, hi = sims[int(DRAWS * 0.025)], sims[int(DRAWS * 0.975) - 1]
        mlo, mhi = sim_med[int(DRAWS * 0.025)], sim_med[int(DRAWS * 0.975) - 1]
        bands = [sum(1 for _, x in real if x <= b) / n for b in BANDS]
        st[k] = dict(bands=bands, total=len(recs), n=n, share=share, med=med, lo=lo, hi=hi, mlo=mlo, mhi=mhi, as_of=raw["as_of"],
                     last=max(d for d, _ in recs))
        if k == "akita":
            month = {}
            for m in range(4, 10):
                xs = [x for d, x in real if int(d[5:7]) == m]
                if len(xs) < 30:
                    continue
                s = sorted(sim_month[m])
                month[m] = dict(n=len(xs), share=sum(1 for x in xs if x <= NEAR_KM) / len(xs),
                                lo=s[int(len(s) * 0.025)], hi=s[int(len(s) * 0.975) - 1], med=statistics.median(xs))
            st[k]["month"] = month
        rows.append([label, f"{len(recs):,}件", f"{n:,}件", f"{share * 100:.0f}%", f"{lo * 100:.0f}〜{hi * 100:.0f}%", f"{med:.1f}km"])
    above = [k for k in SOURCES if st[k]["share"] > st[k]["hi"]]
    inside = [k for k in SOURCES if st[k]["lo"] <= st[k]["share"] <= st[k]["hi"]]
    below = [k for k in SOURCES if st[k]["share"] < st[k]["lo"]]
    a, nv, yg, ym = st["akita"], st["niigata"], st["yamaguchi"], st["yamanashi"]
    month = a["month"]
    total = sum(s["total"] for s in st.values())
    as_of = max(s["as_of"] for s in st.values())
    mrows = [[f"{m}月", f"{v['n']:,}件", f"{v['share'] * 100:.0f}%", f"{v['lo'] * 100:.0f}〜{v['hi'] * 100:.0f}%", f"{v['med']:.1f}km"] for m, v in month.items()]
    mtop = max(month, key=lambda m: month[m]["share"])
    mlow = min(month, key=lambda m: month[m]["share"])
    m_above = [m for m, v in month.items() if v["share"] > v["hi"]]
    order = sorted(SOURCES, key=lambda k: -st[k]["share"])
    names_above = "・".join(SOURCES[k] for k in above)
    names_inside = "・".join(SOURCES[k] for k in inside)
    brows = [[SOURCES[k]] + [f"{v * 100:.0f}%" for v in st[k]["bands"]] for k in order]
    print({k: {kk: vv for kk, vv in v.items() if kk != "month"} for k, v in st.items()})
    print(month)
    print(above, inside, below, m_above, mtop, mlow)

    doc = {
        "slug": "same-day-distance", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "同じ日の熊(クマ)の目撃は、何km以内に集まるか。4県の座標つき記録で調べた",
        "h1": "同じ日の熊(クマ)の目撃は、何km以内に集まるか。4県の座標を比べる",
        "description": f"秋田・新潟・山口・山梨の令和8年度の座標つき記録{total:,}件で、同じ日の別の記録までの距離を測りました。5km以内に別の記録がある割合は、秋田県{a['share'] * 100:.0f}%、新潟県{nv['share'] * 100:.0f}%、山口県{yg['share'] * 100:.0f}%、山梨県{ym['share'] * 100:.0f}%です。",
        "lead": (f"同じ日に何件も報告が出たとき、それは1か所のまわりに集まっているのでしょうか。それとも、県のあちこちに散らばっているのでしょうか。"
                 f"4県の記録で、1件ごとに「同じ日の、いちばん近い別の記録」までの距離を測りました。5km以内に別の記録がある割合は、秋田県で{a['share'] * 100:.0f}%、新潟県で{nv['share'] * 100:.0f}%でした。"
                 f"同じ週の記録の日付を入れ替えた場合の範囲と比べると、この2県は範囲の外にあります。山口県と山梨県は、範囲の中に収まっていました。"),
        "findings": [
            f"同じ日に別の記録がある記録のうち、5km以内にもう1件ある割合は、{'、'.join(f'{SOURCES[k]}{st[k]["share"] * 100:.0f}%' for k in order)}です。いちばん近い記録までの距離の中央値は、秋田県{a['med']:.1f}km、新潟県{nv['med']:.1f}km、山口県{yg['med']:.1f}km、山梨県{ym['med']:.1f}kmでした。",
            f"同じ週の記録で日付を入れ替えた{DRAWS}回の範囲を、実際の割合が上回ったのは{names_above}です。{names_inside}は範囲の中でした。",
            f"秋田県を月別に見ると、5km以内の割合は{mlow}月の{month[mlow]['share'] * 100:.0f}%から{mtop}月の{month[mtop]['share'] * 100:.0f}%まで動いています。日付を入れ替えた範囲を上回った月は、{'・'.join(f'{m}月' for m in m_above) if m_above else 'ありません'}。",
        ],
        "sections": [
            {"h2": "1件ごとに、同じ日のいちばん近い記録までを測る",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、緯度と経度が付いているものを使いました。対象は、秋田・新潟・山口・山梨の4県で、合わせて{total:,}件です。記録の座標は、県が公表している位置の値をそのまま使い、動かしていません。",
                            f"測り方は次のとおりです。ある記録と同じ日付の記録が、ほかに1件以上あれば、その中でいちばん近いものまでの距離(直線のkm)を求めます。同じ日に記録が1件しかない日は、比べる相手がいないので数えません。この「いちばん近い記録まで」が{NEAR_KM}km以内に収まる記録の割合を、県ごとに出しました。",
                            f"比べる基準として、同じ週の記録の間で日付を入れ替える計算をしました。1週間のうち、どの記録が何日のものかだけを入れ替えるので、週ごとの件数も、日ごとの件数も変わりません。これを{DRAWS}回行い、割合の小さい側と大きい側から2.5%ずつを除いた範囲を「入れ替えた範囲」として書きます。乱数の種は固定してあります。"],
             "table": {"head": ["県", "座標つきの記録", "同じ日に別の記録がある件数", f"{NEAR_KM}km以内の割合", "入れ替えた範囲", "距離の中央値"], "rows": rows,
                       "note": f"距離は、各記録から同じ日の別の記録までの最短の直線距離です。入れ替えた範囲は、同じ週の中で日付を入れ替えた{DRAWS}回の、2.5%〜97.5%の範囲です。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [round(st[k]["share"] * 100, 1) for k in order],
                       "title": f"同じ日の別の記録が{NEAR_KM}km以内にある記録の割合(%)",
                       "desc": f"秋田・新潟・山口・山梨の4県で、同じ日にいちばん近い別の記録が{NEAR_KM}km以内にある記録の割合を比べた棒グラフ。"}},
            {"h2": "秋田県と新潟県は、日付の入れ替えより集まっている",
             "paragraphs": [f"秋田県は、同じ日に別の記録がある{a['n']:,}件のうち、{a['share'] * 100:.0f}%が5km以内にもう1件ありました。日付を入れ替えた範囲は{a['lo'] * 100:.0f}〜{a['hi'] * 100:.0f}%で、実際の割合はその上にあります。中央値は{a['med']:.1f}kmで、入れ替えた場合の{a['mlo']:.1f}〜{a['mhi']:.1f}kmより短くなっています。",
                            f"新潟県は、{nv['n']:,}件のうち{nv['share'] * 100:.0f}%でした。入れ替えた範囲は{nv['lo'] * 100:.0f}〜{nv['hi'] * 100:.0f}%で、こちらも上回っています。ただし、割合そのものは秋田県よりずっと低く、同じ日の記録の多くは5kmより離れています。新潟県は1日の件数が秋田県より少なく、同じ日に別の記録がある相手が、そもそも遠くなりやすい面もあります。",
                            "日付を入れ替えても同じ週の記録の場所は変わらないので、「その週にどこで出ていたか」の偏りは、基準の側に含まれています。それでも実際が上回ったということは、週のなかの同じ日に、近い場所で重なって報告される傾向が、この2県にはあると読めます。理由まではわかりません。同じ個体が動いたのか、同じ地区で複数の人が報告したのかは、記録からは区別できないためです。"]},
            {"h2": "山口県と山梨県は、範囲に収まった",
             "paragraphs": [f"山口県は{yg['n']}件のうち{yg['share'] * 100:.0f}%で、入れ替えた範囲は{yg['lo'] * 100:.0f}〜{yg['hi'] * 100:.0f}%でした。山梨県は{ym['n']}件のうち{ym['share'] * 100:.0f}%で、範囲は{ym['lo'] * 100:.0f}〜{ym['hi'] * 100:.0f}%です。どちらも実際の割合は範囲の中にあり、日付を入れ替えただけでも出る水準です。",
                            "この2県は、同じ日に記録がある件数が少なく、範囲が広くなっています。「集まっていない」と言い切れるわけではなく、集まっているかどうかを判断できるだけの件数がない、というのが正確です。"]},
            {"h2": "1km・5km・10km・20kmで区切ると",
             "paragraphs": [f"5kmという区切りは、この記事で決めたものです。区切りを変えても読み方が変わらないか、1km・10km・20kmの割合も並べました。1km以内でも、秋田県は{st['akita']['bands'][0] * 100:.0f}%の記録に、同じ日の別の記録があります。20km以内まで広げると、秋田県は{st['akita']['bands'][3] * 100:.0f}%、新潟県は{st['niigata']['bands'][3] * 100:.0f}%、山口県は{st['yamaguchi']['bands'][3] * 100:.0f}%、山梨県は{st['yamanashi']['bands'][3] * 100:.0f}%です。",
                            f"秋田県は、どの区切りでも4県のなかでいちばん高く、県内の同じ日の記録がまとまって出る傾向は、区切りの選び方によりません。山口県と山梨県は、20km以内でも半分前後にとどまり、同じ日の記録は県内の離れた場所に出ています。"],
             "table": {"head": ["県"] + [f"{b}km以内" for b in BANDS], "rows": brows,
                       "note": "同じ日に別の記録がある記録のうち、いちばん近い別の記録がその距離以内にある割合です。"}},
            {"h2": "秋田県を月別に見る",
             "paragraphs": [f"秋田県は件数が多いので、月別にも同じ計算ができます。{'、'.join(f'{m}月は{v["n"]:,}件で{v["share"] * 100:.0f}%' for m, v in month.items())}でした。",
                            f"日付を入れ替えた範囲を上回った月は{'、'.join(f'{m}月' for m in m_above) if m_above else 'ありません'}。入れ替えた範囲も月ごとに違います。その月の1日あたりの件数が変わると、同じ日に近い記録が重なる確率も変わるためです。そのため、月どうしの割合は並べて比べず、同じ月の範囲と比べて読んでください。9月は記録が9月30日までで、95件と少なく、割合は範囲の上限と同じ値でした。"],
             "table": {"head": ["月", "同じ日に別の記録がある件数", f"{NEAR_KM}km以内の割合", "入れ替えた範囲", "距離の中央値"], "rows": mrows,
                       "note": "秋田県の記録のうち、30件以上ある月だけを示しています。入れ替えた範囲は、日付を入れ替えたあとの、その月の割合の2.5%〜97.5%です。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、秋田県と新潟県では、同じ日の記録が、日付を入れ替えた場合より近い場所に集まっていることです。山口県と山梨県は、範囲の中でした。距離は、記録に付いた座標をそのまま測った直線距離です。",
                            "言えないのは、1頭の熊が動いた距離や、出没の広がりそのものです。同じ日の近い2件が同じ個体かどうかは、記録からはわかりません。近いからといって「同じ場所に居続けている」ことも、離れているからといって「別の個体がいる」ことも、示せません。「安全」や「危険」を判断する数字でもありません。",
                            "お住まいの地域の最新の記録は、県別のページの地図で確かめてください。このページの計算は令和8年度の記録で、記録の追加が済んでいない直近の日は、実際より記録が少ない可能性があります。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、緯度・経度のあるものです。秋田・新潟・山口・山梨の4県で、記録の最新日はそれぞれ{st['akita']['last']}・{st['niigata']['last']}・{st['yamaguchi']['last']}・{st['yamanashi']['last']}です。",
            "距離は、2つの座標の間の直線距離(球面上の大円距離)です。各記録について、同じ日付の別の記録までの最短の距離を求めました。同じ日の記録が1件だけの日は、その記録を数えていません。",
            f"入れ替えた範囲は、同じ週(月曜始まり)の記録の間で日付を入れ替える計算を{DRAWS}回行った結果です。2.5%〜97.5%の範囲を書いています。乱数の種は固定しています。",
            "宮城・富山など、座標のない県は対象にしていません。座標のない記録は、距離の計算に入れていません。",
        ],
        "caveats": [
            "これは「報告された記録」の数え方です。熊の実際の動きや数ではありません。報告のしやすさや、地区ごとの報告の仕方の違いも、距離に影響します。",
            "座標は、県が公表した位置の値です。公表の段階で、地区の代表点に丸められている記録が含まれる可能性があります。5kmより細かい違いは読まないでください。",
            "件数が少ない県は、範囲が広く、差があっても範囲に収まります。県どうしの割合の差を、県の違いとして読まないでください。",
            "令和8年度だけの結果です。ほかの年にも同じ傾向になるかは、この記録だけでは言えません。",
        ],
        "credits": [raws[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/same-day-distance.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "山口県の最新の目撃情報", "href": "/live/yamaguchi/"}, {"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(sum(len(p) for s in doc["sections"] for p in s["paragraphs"]))


if __name__ == "__main__":
    main()
