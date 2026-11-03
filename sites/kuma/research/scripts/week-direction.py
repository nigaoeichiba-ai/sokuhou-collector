"""Research note: after a week with more bear records than the week before, is the next week more again?  Six prefectures, weekly counts from 1 April; compared with 1,000 reshuffles of the same weeks.

python sites/kuma/research/scripts/week-direction.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
CAP = date(2026, 10, 28)      # the latest day the prefectures other than Akita cover together
SHUFFLES = 1000


def weekly(src: dict) -> list[int]:
    end = min(date.fromisoformat(src["as_of"]), CAP)
    n = 0
    while common.FY_START + timedelta(7 * n + 6) <= end:
        n += 1
    c = [0] * n
    for r in src["rows"]:
        d = r[0].date() if isinstance(r[0], datetime) else r[0]
        i = (d - common.FY_START).days // 7
        if 0 <= i < n:
            c[i] += 1
    return c


def directions(c: list[int]) -> list[int]:
    return [(b > a) - (b < a) for a, b in zip(c, c[1:])]


def pairs(c: list[int]) -> tuple[int, int]:
    """(pairs of consecutive weeks that both changed, of which the same way)."""
    ch = directions(c)
    p = [(x, y) for x, y in zip(ch, ch[1:]) if x and y]
    return sum(1 for x, y in p if x == y), len(p)


def longest(ch: list[int], sign: int) -> int:
    best = run = 0
    for x in ch:
        run = run + 1 if x == sign else 0
        best = max(best, run)
    return best


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rng = random.Random(20261103)
    st = {}
    for k, src in data.items():
        c = weekly(src)
        ch = directions(c)
        cont, n = pairs(c)
        obs = cont / n
        shares = []
        for _ in range(SHUFFLES):
            d = c[:]
            rng.shuffle(d)
            a, b = pairs(d)
            shares.append(a / b if b else 0.0)
        big = [(a, b) for a, b in zip(c, c[1:]) if a >= 10]
        st[k] = dict(big_n=len(big), jump=sum(1 for a, b in big if b >= a * 1.5), drop=sum(1 for a, b in big if b <= a / 2),
                     weeks=len(c), up=ch.count(1), down=ch.count(-1), same=ch.count(0), cont=cont, n=n, obs=obs,
                     mean=sum(shares) / SHUFFLES, ge=sum(1 for s in shares if s >= obs) / SHUFFLES,
                     rise=longest(ch, 1), fall=longest(ch, -1))
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    pc = lambda x: f"{x * 100:.0f}%"
    names = list(SOURCES)
    tot_cont = sum(s["cont"] for s in st.values())
    tot_n = sum(s["n"] for s in st.values())
    over = [SOURCES[k] for k in names if st[k]["ge"] < 0.05]
    lo = min(st[k]["obs"] for k in names)
    hi = max(st[k]["obs"] for k in names)
    mlo = min(st[k]["mean"] for k in names)
    mhi = max(st[k]["mean"] for k in names)
    rows = [[SOURCES[k], f"{st[k]['weeks']}", f"{st[k]['up']}", f"{st[k]['down']}", f"{st[k]['same']}"] for k in names]
    rows2 = [[SOURCES[k], f"{st[k]['cont']}/{st[k]['n']}", pc(st[k]["obs"]), pc(st[k]["mean"]), f"{st[k]['ge'] * 100:.1f}%"] for k in names]
    rows3 = [[SOURCES[k], f"{st[k]['rise']}", f"{st[k]['fall']}"] for k in names]
    rows4 = [[SOURCES[k], f"{st[k]['big_n']}", f"{st[k]['jump']}", f"{st[k]['drop']}"] for k in names]
    tot_big = sum(st[k]["big_n"] for k in names)
    tot_jump = sum(st[k]["jump"] for k in names)
    tot_drop = sum(st[k]["drop"] for k in names)
    chart_vals = [round(st[k]["obs"] * 100) for k in names]
    over_txt = "・".join(over) if over else "なし"
    ak, mi = st["akita"], st["miyagi"]
    mr = max(st[k]["rise"] for k in names)
    mf = max(st[k]["fall"] for k in names)
    max_rise_txt = "・".join(SOURCES[k] for k in names if st[k]["rise"] == mr)
    max_fall_txt = "・".join(SOURCES[k] for k in names if st[k]["fall"] == mf)

    doc = {
        "slug": "week-direction", "date": today, "data_as_of": as_of,
        "title": "熊の記録が先週より増えた週の翌週は、また増えるのか",
        "h1": "熊(クマ)の記録が前の週より増えた週の翌週は、また増えるか",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の週別件数です。増減の向きが翌週も同じだった割合は{pc(lo)}から{pc(hi)}で、週の順番を入れ替えた平均({pc(mlo)}〜{pc(mhi)})を上回ったのは{over_txt}でした。",
        "lead": (f"熊の記録が前の週より増えた週は、翌週もさらに増えるのでしょうか。6県の週別の件数で、増減が2週続けて同じ向きだった割合を数えると、{pc(lo)}から{pc(hi)}でした。"
                 f"週の順番をばらばらに入れ替えても同じ計算をすると、平均は{pc(mlo)}〜{pc(mhi)}になります。入れ替えた範囲を超えたのは{over_txt}だけで、ほかの県は偶然でも出る範囲でした。"),
        "findings": [
            f"4月1日から7日ごとに区切った週別の件数で、前の週より増えた週と減った週は、ほぼ同じ数でした。{SOURCES['akita']}は増{ak['up']}・減{ak['down']}、{SOURCES['miyagi']}は増{mi['up']}・減{mi['down']}です。",
            f"増減が2週続けて起きた組のうち、同じ向きだった割合は、{'、'.join(f'{SOURCES[k]}{pc(st[k]['obs'])}' for k in names)}です。6県を合わせると{tot_cont}/{tot_n}組({pc(tot_cont / tot_n)})でした。",
            f"同じ週の件数を1,000回入れ替えた場合の平均は{pc(mlo)}〜{pc(mhi)}です。実際の割合がこの範囲の上位5%に入ったのは、{over_txt}でした。",
        ],
        "sections": [
            {"h2": "週ごとの増減は、増えた週と減った週がほぼ半々",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録を、4月1日を初日に7日ごとの週に分け、週ごとの件数を数えました。記録がそろっている最後の日(秋田県は{data['akita']['as_of']}、ほかの5県は{CAP.month}月{CAP.day}日)までで、7日がそろった週だけを使っています。",
                            "それぞれの週について、前の週より多ければ「増」、少なければ「減」、同じなら「同数」としました。表のとおり、どの県も増と減の数は近く、特定の向きに偏ってはいません。春から夏にかけて件数が増え、秋に減る大きな流れの中でも、週ごとに見ると上下をくり返しています。",
                            "上下のくり返しには、天気、報告の集まり方、入力の遅れなど、いくつもの理由が考えられます。このノートでは、その理由までは分けていません。"],
             "table": {"head": ["県", "使った週の数", "前の週より増えた週", "減った週", "同数の週"], "rows": rows,
                       "note": "週の数は、7日がそろった週だけです。最初の週には前の週がないため、増減は週の数より1つ少なくなります。"}},
            {"h2": "同じ向きが続いた割合を、順番の入れ替えと比べる",
             "paragraphs": [f"増(または減)の次の週も、同じ向きに変わったかどうかを見ました。連続した2回の増減がどちらも「増」か「減」で、同数を挟まない組だけを数えます。6県を合わせると{tot_n}組のうち{tot_cont}組で同じ向きが続き、割合は{pc(tot_cont / tot_n)}でした。県別では{pc(lo)}から{pc(hi)}です。",
                            f"この割合が大きいか小さいかは、そのままでは分かりません。そこで、各県の週別の件数を、順番だけ入れ替えて{SHUFFLES:,}回同じ計算をしました。入れ替えると春から秋への流れが消えるので、同じ向きが続く割合は、平均で{pc(mlo)}〜{pc(mhi)}まで下がります。",
                            f"実際の割合が入れ替えの平均を上回ったのは6県すべてです。ただ、入れ替えた{SHUFFLES:,}回のうち実際以上になった回数が5%未満だったのは、{over_txt}だけでした。{SOURCES['miyagi']}は{pc(mi['obs'])}で、入れ替えで同じかそれ以上になったのは{mi['ge'] * 100:.1f}%です。ほかの県は、週の順番が違っても出る範囲でした。"],
             "table": {"head": ["県", "同じ向きが続いた組", "割合", "入れ替えた場合の平均", "入れ替えで実際以上になった割合"], "rows": rows2,
                       "note": "分子は増減が2週続けて同じ向きだった組、分母は2週続けて増減があった組です。入れ替えは各県1,000回です。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in names], "values": chart_vals,
                       "title": "増減が2週続けて同じ向きだった割合(%)",
                       "desc": "6県の週別件数で、前の週との増減が2週続けて同じ向きだった割合を比べた棒グラフ。宮城県が最も高い。"}},
            {"h2": "増え続けた週・減り続けた週の最長",
             "paragraphs": [f"増が何週続いたか、減が何週続いたかの最長も数えました。増が最も長く続いたのは{max_rise_txt}の{mr}週、減が最も長く続いたのは{max_fall_txt}の{mf}週です。",
                            f"6県とも、増も減も最長は2〜{max(mr, mf)}週で、5週以上は続いていません。件数の多い秋田県と宮城県でも、前の週の増減を見て翌週を当てられる状態ではありません。"],
             "table": {"head": ["県", "増が続いた最長(週)", "減が続いた最長(週)"], "rows": rows3, "note": "同数の週は、続いた回数を途切れさせます。"}},
            {"h2": "前の週から大きく変わった週は、どれくらいあるか",
             "paragraphs": [f"向きだけでなく、変わり方の大きさも見ました。前の週に10件以上あった週を対象に、翌週が1.5倍以上に増えた週と、半分以下に減った週を数えます。対象は6県で{tot_big}週あり、1.5倍以上になったのは{tot_jump}週、半分以下になったのは{tot_drop}週でした。",
                            "前の週が9件以下の週は、1件の違いで倍率が大きく動くため、この数え方には入れていません。1.5倍と半分は、このノートで決めた目安で、公式の区分ではありません。"],
             "table": {"head": ["県", "前の週が10件以上の週", "翌週が1.5倍以上", "翌週が半分以下"], "rows": rows4, "note": "山口県・山梨県・富山県は10件以上の週が少ないため、週の数が少なくなっています。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": ["言えるのは、令和8年度の6県で、前の週より増えたことが翌週も増える目安にはなりにくかったことです。宮城県だけは、順番を入れ替えた場合を超えて、同じ向きが続きやすい結果でした。",
                            "言えないのは、来週の件数の予測です。週ごとの増減は偶然の揺れが大きく、1年度分(約30週)では、県ごとの傾向を確かに示すだけの組の数がありません。",
                            "最新の状況は県別のページで、週ごとの数字は「週ごとのまとめ」のページで見られます。件数が増えた週も減った週も、出会わないための備えは同じです。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録です。秋田・宮城・新潟・富山・山口・山梨の6県で、週は4月1日を初日に7日ごとに区切り、7日がそろった週だけを使いました。秋田県は記録が{data['akita']['as_of']}まで、ほかの5県は{CAP.isoformat()}までです。計算した日は{today}、使った記録の最新日は{as_of}です。",
            f"増減は、隣り合う週の件数の大小で決めました。同数の週は「同数」とし、同数を含む組は、同じ向きが続いたかの計算から除きました。入れ替えは、各県の週別の件数をランダムに並べ替えて同じ計算をする作業を、{SHUFFLES:,}回(乱数の種を固定)行いました。",
            "「上位5%に入った」は、入れ替えた場合に、実際の割合と同じかそれ以上になった回数が5%未満だったことを指します。統計の検定の結論ではなく、目安です。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や行動を直接示すものではありません。",
            "県ごとに記録の集め方が違います。記録の入力が遅れると、直近の週の件数が少なく見えて、増減の向きが変わることがあります。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
            "富山・山口・山梨は週の件数が1けたの週が多く、1件の違いで増減の向きが変わります。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/week-direction.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
