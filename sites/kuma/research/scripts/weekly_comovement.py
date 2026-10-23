"""Research note: do the prefectures' weekly bear-report counts rise and fall together?  Same-week rank correlation of 26 weekly counts, compared with
the same series shifted around the calendar, and the week shift at which two prefectures line up best.
(Akita, Miyagi, Niigata, Toyama, Yamaguchi, Yamanashi: the six sources with 200+ records from 1 April to 30 September 2026.)

python sites/kuma/research/scripts/weekly_comovement.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
END = date(2026, 9, 30)      # Akita's records stop here; every source is cut to the same 26 whole weeks (1 April to 30 September)
N_WEEKS = ((END - common.FY_START).days + 1) // 7
LAGS = (-3, -2, -1, 0, 1, 2, 3)


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float:
    a, b = ranks(x), ranks(y)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return sum((p - ma) * (q - mb) for p, q in zip(a, b)) / math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))


def lagged(x: list[int], y: list[int], lag: int) -> float:
    """Correlation of x in week t with y in week t+lag (lag > 0: y follows x)."""
    if lag >= 0:
        return spearman(x[:N_WEEKS - lag], y[lag:])
    return spearman(x[-lag:], y[:N_WEEKS + lag])


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    weeks: dict[str, list[int]] = {}
    for k, s in data.items():
        c = Counter()
        for r in s["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if d <= END:
                c[(d - common.FY_START).days // 7] += 1
        weeks[k] = [c[i] for i in range(N_WEEKS)]
        assert sum(weeks[k]) >= 200, k

    res = []
    for a, b in combinations(SOURCES, 2):
        rho = spearman(weeks[a], weeks[b])
        shifts = [spearman(weeks[a], weeks[b][s:] + weeks[b][:s]) for s in range(1, N_WEEKS)]
        rank = 1 + sum(1 for v in shifts if v >= rho)                    # 1 = no shifted alignment matches the real one
        by_lag = {lg: lagged(weeks[a], weeks[b], lg) for lg in LAGS}
        best = max(by_lag, key=lambda lg: by_lag[lg])
        res.append(dict(a=a, b=b, rho=rho, rank=rank, best=best, best_rho=by_lag[best], by_lag=by_lag))
    res.sort(key=lambda r: -r["rho"])
    pr = {(r["a"], r["b"]): r for r in res}

    for r in res:
        print(r["a"], r["b"], round(r["rho"], 2), r["rank"], r["best"], round(r["best_rho"], 2), {k: round(v, 2) for k, v in r["by_lag"].items()})

    north = ("akita", "miyagi", "niigata")
    north_pairs = [pr[p] for p in combinations(north, 2)]
    assert all(r["rho"] >= 0.75 and r["rank"] == 1 for r in north_pairs)
    ym = [r for r in res if "yamanashi" in (r["a"], r["b"]) and (r["a"] in north or r["b"] in north)]
    assert all(pr[(a, "toyama")]["best"] in (2, 3) and pr[(a, "toyama")]["best_rho"] > pr[(a, "toyama")]["rho"] + 0.1 for a in ("akita", "miyagi", "niigata"))
    assert len(ym) == 3 and all(r["rho"] < 0.45 and r["rank"] >= 5 for r in ym)
    yg = [r for r in res if "yamaguchi" in (r["a"], r["b"])]
    tot = {k: sum(v) for k, v in weeks.items()}

    def L(k):
        return SOURCES[k]

    def pair_name(r):
        return f"{L(r['a'])}と{L(r['b'])}"

    def lag_text(r):
        if r["best"] == 0:
            return "ずれなし"
        if r["best"] > 0:
            return f"{L(r['b'])}が{r['best']}週後"
        return f"{L(r['b'])}が{-r['best']}週先"

    rows = [[pair_name(r), f"{r['rho']:.2f}", f"{r['rank']} / {N_WEEKS - 1 + 1}", lag_text(r), f"{r['best_rho']:.2f}"] for r in res]
    lo_n = min(r["rho"] for r in north_pairs)
    hi_n = max(r["rho"] for r in north_pairs)
    ym_lo, ym_hi = min(r["rho"] for r in ym), max(r["rho"] for r in ym)
    n_top = sum(1 for r in res if r["rank"] == 1)
    n_all = len(res)
    ty = pr[("toyama", "yamanashi")]
    at = pr[("akita", "toyama")]
    mt = pr[("miyagi", "toyama")]

    # chart: 3-week moving average, each source's busiest value = 100
    pts = N_WEEKS - 2
    series = []
    for j, k in enumerate(("akita", "miyagi", "niigata", "yamanashi")):
        w = weeks[k]
        avg = [sum(w[i:i + 3]) / 3 for i in range(pts)]
        series.append({"label": L(k), "values": [round(v / max(avg) * 100, 1) for v in avg], "cls": f"c{j + 1}"})
    xl = [md(common.FY_START + timedelta(days=7 * i)) if i % 4 == 0 else "" for i in range(pts)]
    chart = {"kind": "lines", "x_labels": xl, "series": series, "title": "週別の目撃報告の動き(各県の最大=100、3週移動平均)",
             "desc": "秋田県・宮城県・新潟県・山梨県の令和8年度、4月から9月までの週別の報告件数を、3週の移動平均にして、各県の最大を100にそろえた折れ線グラフ。秋田・宮城・新潟は似た形で動き、山梨県は形が違う。"}

    count_rows = [[L(k), f"{tot[k]:,}", f"{max(weeks[k]):,}", md(common.FY_START + timedelta(days=7 * max(range(N_WEEKS), key=lambda i: weeks[k][i])))] for k in SOURCES]
    as_of = max(s["as_of"] for s in data.values())
    total_n = sum(tot.values())

    doc = {
        "slug": "weekly-comovement", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃報告は、県どうしで同じ週に増減するか。6県の週別",
        "h1": f"熊(クマ)の目撃報告は、県どうしで同じ週に増えるか。秋田・宮城・新潟は相関{lo_n:.2f}〜{hi_n:.2f}",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の4〜9月{total_n:,}件を週ごとに数え、県どうしの増減がそろうかを測りました。東北と新潟は近く、山梨県は別の動きでした。",
        "lead": (f"熊の目撃が増える週は、県が違っても同じなのでしょうか。6県の記録{total_n:,}件を、4月1日から9月30日までの26週に数え、2県ずつ、週ごとの件数の増減がそろうかを測りました。"
                 f"秋田・宮城・新潟の3県は、3組とも順位相関が{lo_n:.2f}〜{hi_n:.2f}で、週をずらした場合のどれよりも強くそろいます。山梨県はこの3県との相関が{ym_lo:.2f}〜{ym_hi:.2f}で、別の動きでした。"),
        "findings": [
            f"秋田・宮城・新潟の3県は、同じ週の件数の順位相関が{lo_n:.2f}〜{hi_n:.2f}でした。同じ県の系列を暦の上で{N_WEEKS - 1}通りにずらして測り直しても、実際の並びより強くそろうずらし方は1つもありません。",
            f"山梨県は、この3県との相関が{ym_lo:.2f}〜{ym_hi:.2f}にとどまります。週をずらして測り直すと、実際の並びと同じくらいそろうずらし方が複数あり、同じ週に増減しているとは言えません。",
            f"富山県は、秋田・宮城・新潟の3県より2〜3週あとにずらすと相関が{min(at['best_rho'], mt['best_rho'], pr[('niigata','toyama')]['best_rho']):.2f}〜{max(at['best_rho'], mt['best_rho'], pr[('niigata','toyama')]['best_rho']):.2f}まで上がります(同じ週では{min(at['rho'], mt['rho'], pr[('niigata','toyama')]['rho']):.2f}〜{max(at['rho'], mt['rho'], pr[('niigata','toyama')]['rho']):.2f})。富山県の件数の山は、3県より遅れて来ているように見えます。",
            f"15組のうち、ずらした場合のどれよりも強い組は{n_top}組です。県の記録が少ないほど、週ごとの件数が小さな数になるため、相関は不安定になります({L('yamaguchi')}は4〜9月で{tot['yamaguchi']}件)。",
        ],
        "sections": [
            {"h2": "6県の件数と、ピークの週",
             "paragraphs": [f"4月1日から9月30日までを7日ずつ26週に区切り、県ごとに週の件数を数えました。秋田県の記録は9月30日まででとまっているため、ほかの県もそこで切っています。最大の週の件数は、秋田県の{max(weeks['akita']):,}件から山梨県の{max(weeks['yamanashi']):,}件まで開きます。"],
             "table": {"head": ["県", "4〜9月の記録", "1週の最大", "最大の週の始まり"], "rows": count_rows,
                       "note": "週は4月1日から7日ずつです。最後の26週目は9月23日〜29日で、9月30日は端数のため数えていません。"}},
            {"h2": "週ごとの増減の動き",
             "paragraphs": ["県ごとに件数の大きさが違うので、3週の移動平均を出し、その県の最大を100にそろえて重ねました。秋田・宮城・新潟は、6月ごろに高くなってから下がる形が似ています。山梨県は、この3県とは違う形です。"],
             "chart": chart},
            {"h2": "県どうしの相関と、週のずれ",
             "paragraphs": [f"2県ずつ、26週の件数の順位相関(スピアマン)を出しました。1に近いほど、一方が多い週にもう一方も多いことを表します。春から夏に増えて秋に減るという、どの県にもある季節の形だけでも、ある程度の相関は出ます。そのため、一方の系列を暦の上でぐるりとずらして測り直し、実際の並びの相関がその中で何番目に高いかを「順位」に書きました。1位は、ずらしたどの並びよりも実際の並びがそろっているということです。",
                            f"「最も合う週ずれ」は、一方を最大3週前後させたときに最も相関が高くなるずれです。{pair_name(at)}は{lag_text(at)}で{at['best_rho']:.2f}、{pair_name(mt)}は{lag_text(mt)}で{mt['best_rho']:.2f}でした。ただし、ずらすと重なる週が減り、26週のうち23週以上で測るため、差が小さいときは意味を持たせません。"],
             "table": {"head": ["組み合わせ", "同じ週の相関", "ずらした並びとの順位", "最も合う週ずれ", "そのときの相関"], "rows": rows,
                       "note": "順位は、実際の並びと、暦の上で1〜25週ずらした25通りを合わせた26通りの中での順位です。1位は、ずらしたどの並びより強くそろっていることを示します。"}},
            {"h2": "富山県と山梨県は、3県のあとに合う",
             "paragraphs": [f"一方を1週ずつずらして測ると、富山県は秋田・宮城・新潟のどの県に対しても、2〜3週あとにずらしたときに相関が最も高くなります(0.77〜0.84)。山梨県も、同じ3県に対して2〜3週あとにずらすと0.63〜0.68まで上がります。ただし、山梨県の週ごとの件数は1〜16件と小さく、{L('yamanashi')}が3県の動きを追っていると言えるほどの根拠にはなりません。",
                            "目撃の記録は、熊の動きだけでなく、人が見つける機会や、役所に届けて記録に入る時期にも左右されます。標高や雪の残り方、山の実りの時期が県で違うことも、時期のずれの背景として考えられますが、この記録だけでは確かめられません。県を超えて同じ週に増減がそろうかは、注意を呼びかける時期を考える材料の1つです。県ごとの最新の件数は、各県の「最新の目撃情報」のページで確かめてください。"],
             "table": {"head": ["組み合わせ(一方をずらす)"] + [f"{lg:+d}週" for lg in LAGS],
                       "rows": [[f"{L(a)}と{L(b)}"] + [f"{pr[(a, b)]['by_lag'][lg]:.2f}" for lg in LAGS] for a, b in (("akita", "toyama"), ("miyagi", "toyama"), ("niigata", "toyama"), ("akita", "yamanashi"), ("miyagi", "yamanashi"), ("niigata", "yamanashi"))],
                       "note": "プラスの週ずれは、あとの県(右側の県)が、前の県より何週あとの件数と合わせたかを表します。"}},
            {"h2": "記録が少ない県を読むときの注意",
             "paragraphs": [f"{L('yamaguchi')}は4〜9月で{tot['yamaguchi']}件、{L('yamanashi')}は{tot['yamanashi']}件、{L('toyama')}は{tot['toyama']}件です。1週の件数が1〜30件ほどなので、1週のぶれが相関を大きく動かします。{L('toyama')}と{L('yamanashi')}の相関が{ty['rho']:.2f}と高く見えるのも、両県の少ない件数の増減が、たまたま重なったためかもしれません。県の面積や森林の状況、記録の集め方の違いは、この分析には入っていません。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、4月1日から9月30日の分です。秋田県{tot['akita']:,}件、宮城県{tot['miyagi']:,}件、新潟県{tot['niigata']:,}件、富山県{tot['toyama']:,}件、山口県{tot['yamaguchi']:,}件、山梨県{tot['yamanashi']:,}件です。記録の最新日は県で違い、秋田県が9月30日で止まっているため、全県をそこで切りました。10月の分は入れていません。",
            f"4月1日を起点に7日ずつ区切って{N_WEEKS}週とし、週ごとの記録の件数を数えました。件数は、目撃も痕跡も区別せず、1件を1と数えています。相関は、週ごとの件数の順位から出したスピアマンの値です。順位は、一方の系列を暦の上で1〜{N_WEEKS - 1}週ずらして(端はもう一方の端につなげて)測り直した値と比べて出しました。週ずれは、最大±3週で測っています。計算に使ったスクリプトは公開しています。",
        ],
        "caveats": [
            "相関が高いことは、同じ原因で増減していることを意味しません。季節による山が似ているだけかもしれませんし、各県が記録を公表する日や、まとめて入力する日が重なっているだけかもしれません。この分析では、原因は分かりません。",
            "「週ずれ」の差が小さいとき、どちらの県が先かは決められません。26週という短い期間の、令和8年度の4〜9月だけの結果です。ほかの年度や、10月以降には当てはまらないことがあります。",
            "県の記録は、それぞれ集め方も公表の仕方も違います。件数の多さは、熊の多さを表すとは限りません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/weekly_comovement.py",
        "related": [{"label": "今年のピークはいつか(週ごとの件数)", "href": "/research/weekly-peak/"},
                    {"label": "今季の初出没日", "href": "/research/first-sighting/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "熊に出会わないための対処法", "href": "/guide/"}],
    }
    common.write_note(doc)


if __name__ == "__main__":
    main()
