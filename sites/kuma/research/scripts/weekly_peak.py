"""Research note: when was this year's peak week of bear sightings, and how fast did the reports fall away?  (Akita, Miyagi, Niigata, Toyama: the four sources with 250+ records.)

python sites/kuma/research/scripts/weekly_peak.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県"}
MIN_RECORDS = 250          # smaller sources (Yamaguchi, Yamanashi, Sorachi, ...) have weekly counts of 0-20: a peak week would be noise, so they are not counted


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    n_weeks = min(((date.fromisoformat(s["as_of"]) - common.FY_START).days + 1) // 7 for s in data.values())    # only whole 7-day weeks that every source covers
    weeks: dict[str, list[int]] = {}
    for k, s in data.items():
        end = date.fromisoformat(s["as_of"])
        dates = [(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in s["rows"] if (r[0].date() if isinstance(r[0], datetime) else r[0]) <= end]
        assert len(dates) >= MIN_RECORDS, k
        c = Counter((d - common.FY_START).days // 7 for d in dates)
        weeks[k] = [c[i] for i in range(n_weeks)]
    week_start = lambda i: common.FY_START + timedelta(days=7 * i)       # noqa: E731
    week_end = lambda i: week_start(i) + timedelta(days=6)               # noqa: E731

    rows, stats = [], {}
    for k, label in SOURCES.items():
        w = weeks[k]
        total = sum(w)
        sums3 = [sum(w[i:i + 3]) for i in range(len(w) - 2)]
        p3 = max(range(len(sums3)), key=lambda i: sums3[i])               # first of the three weeks of the busiest 3-week stretch
        peak_avg = sums3[p3] / 3
        pw = max(range(len(w)), key=lambda i: w[i])
        after = [(sums3[i] / 3) for i in range(p3 + 3, len(sums3))]       # 3-week averages that start after the peak stretch has ended
        half_at = next((i for i in range(p3 + 3, len(sums3)) if sums3[i] / 3 <= peak_avg / 2), None)
        trough_i = min(range(p3 + 3, len(sums3)), key=lambda i: sums3[i])
        trough = sums3[trough_i] / 3
        latest = sum(w[-3:]) / 3
        stats[k] = dict(total=total, pw=pw, p3=p3, share=common.pct(sums3[p3], total), peak_avg=peak_avg, half_at=half_at, trough=trough, trough_i=trough_i, latest=latest,
                        latest_vs_peak=common.pct(latest, peak_avg), latest_vs_trough=latest / trough if trough else 0.0, wk_peak=w[pw])
        rows.append([label, f"{total:,}", f"{md(week_start(pw))}〜{md(week_end(pw))}", f"{w[pw]:,}",
                     f"{md(week_start(p3))}〜{md(week_end(p3 + 2))}", f"{stats[k]['share']:.0f}%"])

    # index lines: 3-week moving average, peak = 100
    xl = [f"{md(week_start(i))}" if i % 4 == 0 else "" for i in range(n_weeks - 2)]
    series = []
    for j, k in enumerate(SOURCES):
        w = weeks[k]
        avg = [sum(w[i:i + 3]) / 3 for i in range(len(w) - 2)]
        series.append({"label": SOURCES[k], "values": [round(a / stats[k]["peak_avg"] * 100, 1) for a in avg], "cls": f"c{j + 1}"})

    fall_tab = []
    for k, label in SOURCES.items():
        st = stats[k]
        half = f"{md(week_start(st['half_at']))}の週から" if st["half_at"] is not None else "まだ半分以下になっていない"
        fall_tab.append([label, f"{st['peak_avg']:.0f}", half, f"{st['trough']:.0f}(週の始まり {md(week_start(st['trough_i']))})", f"{st['latest']:.0f}", f"{st['latest_vs_peak']:.0f}%"])

    ends = [min(date.fromisoformat(s["as_of"]) for s in data.values())]
    last_day = week_end(n_weeks - 1)
    total = sum(st["total"] for st in stats.values())
    p3_starts = sorted(week_start(st["p3"]) for st in stats.values())
    shares = [st["share"] for st in stats.values()]
    latest_pct = [st["latest_vs_peak"] for st in stats.values()]
    rebound = [SOURCES[k] for k, st in stats.items() if st["latest_vs_trough"] >= 1.3]
    nonrebound = [SOURCES[k] for k, st in stats.items() if st["latest_vs_trough"] < 1.3]

    doc = {
        "slug": "weekly-peak", "date": common.today().isoformat(), "data_as_of": max(s["as_of"] for s in data.values()),
        "title": "熊(クマ)の目撃の「ピーク週」はいつ?秋田・宮城・新潟・富山の週別の数え方",
        "h1": "今年の熊(クマ)の目撃は、いつがピークで、どれだけ減ったか",
        "description": f"秋田・宮城・新潟・富山の令和8年度の目撃記録{total:,}件を週ごとに数え、ピークの時期とその後の減り方を県ごとに比べました。数え方と限界つき。",
        "lead": (f"秋田県・宮城県・新潟県・富山県が公表している令和8年度の熊(クマ)の目撃記録{total:,}件を、4月1日からの7日ごと(〜{md(last_day)})に数えました。"
                 "「今年の山は、いつだったのか」「そのあと、どれだけ減っているのか」を、県ごとに並べます。"),
        "findings": [
            f"件数がいちばん多かった3週間は、4県とも{md(p3_starts[0])}から{md(p3_starts[-1])}の間に始まっています(県ごとの日付は下の表)。この3週間だけで、その県の令和8年度の記録の{min(shares):.0f}〜{max(shares):.0f}%が集まっています。",
            f"ピークの3週間の平均を100とすると、直近の3週間は{min(latest_pct):.0f}〜{max(latest_pct):.0f}%です。山を過ぎても、ゼロになる動きではありません。",
            ("ピークのあと、いったん減ってから直近で持ち直している県は、記録の上では" + "・".join(rebound) + "です(最低だった3週間の平均より3割以上多い)。" if rebound
             else "ピークのあと、最低だった3週間の平均から3割以上持ち直している県は、4県にはありません。"),
        ],
        "sections": [
            {"h2": "県ごとのピーク週とピークの3週間",
             "paragraphs": ["4月1日から7日ごとに区切って件数を数え、いちばん多かった1週と、いちばん多かった連続3週を県ごとに出しました。1週だけでは偶然のばらつきが大きいため、3週間の平均も使っています。"],
             "table": {"head": ["県", "件数", "最も多かった1週", "その週の件数", "最も多かった3週間", "3週間の割合"], "rows": rows,
                       "note": "週は4月1日を1日目とする7日ごとです(月曜はじまりではありません)。割合は、その県の令和8年度の記録の合計に対するものです。"}},
            {"h2": "週ごとの動き(ピークの3週間の平均を100とした指数)",
             "paragraphs": ["県ごとに件数の水準が大きく違うため、各県の「ピークの3週間の平均」を100にそろえて、3週間の移動平均を並べました。山の位置と、減り方の形を比べるためのものです。"],
             "chart": {"kind": "lines", "x_labels": xl, "series": series, "title": "週別の目撃報告の動き(ピーク=100、3週移動平均)",
                       "desc": "秋田・宮城・新潟・富山の令和8年度の目撃記録の3週移動平均を、各県のピークを100として並べた折れ線。横軸は4月から10月まで。"}},
            {"h2": "ピークのあと、どれだけ減ったか",
             "paragraphs": ["ピークの3週間の平均、それが半分以下になった時期、その後に最も少なかった3週間の平均、直近の3週間の平均を並べました。件数は、1週間あたりの平均です。"],
             "table": {"head": ["県", "ピークの3週平均(件/週)", "半分以下になった時期", "最も少なかった3週平均(件/週)", "直近3週の平均(件/週)", "ピーク比"], "rows": fall_tab,
                       "note": "「半分以下」は、ピークの3週間が終わったあとの3週平均が、はじめてピークの半分以下になった週です。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録です。4県のうち記録が最も新しい日までの日数が短い県にそろえ、4月1日から7日ごと{n_weeks}週(〜{md(last_day)})を数えました。端の7日に満たない日の記録は、数えていません。",
            "ピークの3週間は、連続する3週の件数の合計が最大の組です。「半分以下」は、そのあとの3週平均で見ています。",
            f"件数が{MIN_RECORDS}件に届かない県(山口・山梨・北海道の空知など)は、週ごとの件数が0〜20件ほどで、ピークの週が偶然で決まるため、対象にしていません。",
            "秋田県の記録は9月末までです。8月以降の追加が続いている可能性があり、その場合は減り方の数字が変わることがあります(ピークの時期は変わりません)。",
        ],
        "caveats": [
            "これは「報告された件数」の動きです。熊の数や、実際に人里に出た回数を表すものではありません。通報の受け付け方や、公表のしかたが年や県で違うことがあります。",
            "県どうしの件数の大小は、記録の取り方が違うため比べていません。比べているのは、各県の中での動き(ピークを100とした形)です。",
            "令和8年度の1年分だけの数え方です。ほかの年にも同じ形になるかは、この記録だけでは言えません。理由(食べ物の実り・天候など)を言うものでもありません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/weekly_peak.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    del ends
    common.write_note(doc)
    for k, st in stats.items():
        print(k, st)
    print("weeks", n_weeks, "last day", last_day, "rebound", rebound, "nonrebound", nonrebound)


if __name__ == "__main__":
    main()
