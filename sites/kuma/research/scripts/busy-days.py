"""Research note: how unevenly do the records fall on the days?  Share of the busiest day, share of the ten busiest days, and how many days hold half of all records
(Akita, Miyagi, Niigata, Toyama, Yamaguchi, Yamanashi, the same six as record-days; 1 April to the earliest 'as of' date).
Reference: the same number of records placed on random days with equal chance (1,000 draws, fixed seed).

python sites/kuma/research/scripts/busy-days.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
DRAWS = 1000


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def days_to_half(counts: list[int]) -> int:
    """How many of the busiest days it takes to reach half of all records."""
    total, acc = sum(counts), 0
    for i, c in enumerate(sorted(counts, reverse=True), 1):
        acc += c
        if acc * 2 >= total:
            return i
    return len(counts)


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    end = min(date.fromisoformat(s["as_of"]) for s in data.values())
    n_days = (end - common.FY_START).days + 1
    rng = random.Random(20261027)
    stats, rows = {}, []
    for k, label in SOURCES.items():
        dates = [(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in data[k]["rows"]]
        dates = [d for d in dates if d <= end]
        n = len(dates)
        c = Counter(dates)
        top = sorted(c.items(), key=lambda x: (-x[1], x[0]))
        top10 = top[:10]
        top10_days = sorted(d for d, _ in top10)
        half = days_to_half(list(c.values()))
        sims = []
        for _ in range(DRAWS):
            cc = Counter(rng.randrange(n_days) for _ in range(n))
            sims.append(days_to_half(list(cc.values())))
        sims.sort()
        st = dict(n=n, top=top[0], share1=common.pct(top[0][1], n, 1), share10=common.pct(sum(v for _, v in top10), n), half=half,
                  half_pct=common.pct(half, n_days), sim=sims[len(sims) // 2], sim_min=sims[0], span=(top10_days[0], top10_days[-1]), top3=top[:3],
                  ratio=round(half / sims[len(sims) // 2], 2), inside=half >= sims[0], top10_weeks=len({(d - common.FY_START).days // 7 for d in top10_days}))
        stats[k] = st
        rows.append([label, f"{n:,}", f"{md(st['top'][0])}の{st['top'][1]}件({st['share1']}%)", f"{st['share10']:.0f}%",
                     f"{half}日({st['half_pct']:.0f}%)", f"約{st['sim']}日", f"{md(st['span'][0])}〜{md(st['span'][1])}"])
    order = sorted(SOURCES, key=lambda k: stats[k]["half_pct"])
    lo, hi = order[0], order[-1]
    as_of = max(s["as_of"] for s in data.values())
    total = sum(st["n"] for st in stats.values())
    below = [k for k in SOURCES if stats[k]["half"] < stats[k]["sim_min"]]
    near = [k for k in SOURCES if k not in below]
    rorder = sorted(SOURCES, key=lambda k: stats[k]["ratio"])
    rows3 = [[SOURCES[k], *[f"{md(d)}({v}件)" for d, v in stats[k]["top3"]]] for k in SOURCES]

    doc = {
        "slug": "busy-days", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃記録の半分は、全体の何日に集まっているか。6県の「記録が多い日」を数える",
        "h1": "熊(クマ)の目撃記録は、一部の日に集まる。記録の半分が入る日数を、県ごとに数える",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の目撃記録{total:,}件を、日ごとに数えました。上位10日の割合と、記録の半分が入る日数を県ごとに比べます。",
        "lead": (f"記録は、4月1日から{md(end)}までの{n_days}日に、同じ数ずつ入っているわけではありません。件数の多い日から順に足していくと、何日で全体の半分に届くのか。"
                 "秋田県・宮城県・新潟県・富山県・山口県・山梨県の記録で数えました。同じ件数の記録を、ランダムな日に入れた場合の日数とも比べます。"),
        "findings": [
            f"記録の半分が入る日数は、{SOURCES[lo]}が{stats[lo]['half']}日({stats[lo]['half_pct']:.0f}%)でいちばん短く、{SOURCES[hi]}が{stats[hi]['half']}日({stats[hi]['half_pct']:.0f}%)でいちばん長くなりました。",
            "いちばん多い1日でも、その県の記録全体に占める割合は" + "、".join(f"{SOURCES[k]}{stats[k]['share1']}%" for k in SOURCES) + "でした。1日だけが飛び抜けて多い県はありません。",
            (f"同じ件数をランダムな日に入れた場合の日数と比べると、{'・'.join(SOURCES[k] for k in below)}は、1,000回の最小値よりも短い日数で半分に届いています。"
             + (f"{'・'.join(SOURCES[k] for k in near)}は、1,000回の範囲に入っていて、ランダムな場合との差がはっきりしません。" if near else "")),
        ],
        "sections": [
            {"h2": "県ごとの、記録が多い日の割合",
             "paragraphs": [f"4月1日から{md(end)}までの{n_days}日を、1日ずつ見ました。件数の多い日から順に足し、全体の半分に届くまでの日数を「半分が入る日数」としています。「ランダムな場合」は、同じ件数の記録を、{n_days}日のどの日にも同じ確率で入れる計算を{DRAWS:,}回くり返したときの、日数の中央値です。"],
             "table": {"head": ["県", "件数", "いちばん多い日", "上位10日の割合", "半分が入る日数", "ランダムな場合", "上位10日の期間"], "rows": rows,
                       "note": f"期間は6県そろえて、4月1日〜{md(end)}({n_days}日)です。ランダムな場合は乱数の種を固定しており、スクリプトを再実行すると同じ値になります。"}},
            {"h2": "半分が入る日数が、期間の何%か",
             "paragraphs": ["割合が小さい県ほど、少ない日数に記録が集まっています。まったく均等なら50%です。"],
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [stats[k]["half_pct"] for k in order], "title": "記録の半分が入る日数が、期間に占める割合(%)",
                       "desc": f"4月1日から{md(end)}までのうち、件数の多い日から順に足して記録の半分に届くまでの日数の割合を、6県で比べた棒グラフ。"}},
            {"h2": "ランダムに置いた場合との比べ方",
             "paragraphs": [f"実際の「半分が入る日数」を、ランダムな場合の中央値で割りました。1より小さいほど、ランダムな場合より少ない日数に記録が集まっています。{SOURCES[rorder[0]]}が{stats[rorder[0]]['ratio']}でいちばん小さく、{SOURCES[rorder[-1]]}が{stats[rorder[-1]]['ratio']}でいちばん1に近くなりました。",
                            "件数が多い県ほど、ランダムな場合との差が出やすい点に注意してください。件数が200件台の県では、日ごとの件数が1〜2件になり、多い日と少ない日の差そのものが小さくなります。"],
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in rorder], "values": [stats[k]["ratio"] for k in rorder], "title": "実際の日数÷ランダムな場合の日数",
                       "desc": "記録の半分が入る日数を、同じ件数をランダムな日に入れた場合の中央値で割った値を、6県で比べた棒グラフ。1より小さいほど、少ない日数に記録が集まっている。"}},
            {"h2": "いちばん件数の多かった3日",
             "paragraphs": [f"件数の多い日が、期間のどこにあるのかも見ました。上位10日は、{'、'.join(f'{SOURCES[k]}が{stats[k]['top10_weeks']}週' for k in SOURCES)}にまたがっています(4月1日からの7日ごとの週で数えた、上位10日が入る週の数)。"],
             "table": {"head": ["県", "1位", "2位", "3位"], "rows": rows3, "note": "件数は、その日付の記録の合計です。同じ件数の日は、日付の早い順に並べています。"}},
            {"h2": "この数え方は、何の役に立つか",
             "paragraphs": [
                 "目撃記録の数は、月ごとや週ごとにまとめて語られることが多く、1日ずつの偏りは見えにくくなります。日ごとに数えると、記録がどれだけ特定の日に寄っているかが、1つの数字で分かります。",
                 f"たとえば秋田県は、{stats['akita']['n']:,}件の半分が{stats['akita']['half']}日に入っています。期間は{n_days}日あるので、期間の約4分の1の日数です。いっぽう、いちばん多い6月3日でも{stats['akita']['top'][1]}件で、全体の{stats['akita']['share1']}%です。つまり、記録は1日に集中するというより、数十日にゆるやかに広がって、その中に多い日が混じる形です。",
                 f"山口県と山梨県は、半分が入る日数が{stats['yamaguchi']['half']}日と{stats['yamanashi']['half']}日で、ランダムな場合の{stats['yamaguchi']['sim']}日・{stats['yamanashi']['sim']}日に近い値です。この2県は件数が200件台で、日ごとの件数が1〜2件にとどまるため、多い日が目立ちにくくなります。県どうしの違いとして読むより、件数が少ないことの影響が混じっていると考えてください。",
                 "お住まいの県で「今日は記録が多い日か」を見るときは、その県の1日あたりの件数と、直近の週の件数を比べるのが目安になります。このページの数字は、過去の期間の偏りを示すもので、これからの日を予測するものではありません。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、{md(end)}までのものです。6県の記録の最新日が違うため、いちばん早い日にそろえました。記録が200件に届かない県は、日ごとの件数が偶然に左右されるため対象にしていません。",
            "日付は、公表されている記録の、目撃などがあった日の日付です。時刻は使っていません。県内のどの市町村の記録も、同じ日なら足しています。",
            f"ランダムな場合は、実際の件数の記録を、{n_days}日のどの日にも同じ確率で入れる計算を{DRAWS:,}回行い、半分に届く日数の中央値を出しました。季節による増減は入れていないので、実際より日数が多く出ます。実際との差は、季節の山を含んでいます。",
            "対象の6県は、record-days(記録のあった日の割合)と同じです。",
        ],
        "caveats": [
            "これは「報告された記録が入った日」の数え方です。記録の多い日に、熊が実際に多く出たとは言い切れません。通報のまとめて公表される日や、更新の日にずれることがあります。",
            "ランダムな場合との差は、季節の山(初夏や秋に増える)で大半が説明できます。この差から、特定の日に特別なことが起きたとは言えません。",
            "令和8年度の4月から9月までの数え方です。10月以降や、ほかの年にも同じ傾向になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/busy-days.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(n_days, end)
    for k, st in stats.items():
        print(k, st)


if __name__ == "__main__":
    main()
