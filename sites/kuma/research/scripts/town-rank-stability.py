"""Research note: do the towns with the most bear records in April-June also lead in July-September?  Six prefectures; rank correlation of town counts, compared with 1,000 reshuffles of which records fall in which period.

python sites/kuma/research/scripts/town-rank-stability.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
SPLIT = date(2026, 6, 30)
END = date(2026, 9, 30)      # Akita's records end here; the others are cut at the same day
SHUFFLES = 1000


def ranks(v: list[int]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a: list[int], b: list[int]) -> float:
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def top3(c: Counter) -> set:
    return {t for t, _ in c.most_common(3)}


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    st = {}
    for k, src in data.items():
        rows = [(r[0].date() if isinstance(r[0], datetime) else r[0], r[2]) for r in src["rows"] if r[2]]
        rows = [r for r in rows if r[0] <= END]
        towns = sorted({c for _, c in rows})
        lab = [d <= SPLIT for d, _ in rows]

        def counts(lb):
            e = Counter(c for (d, c), l in zip(rows, lb) if l)
            la = Counter(c for (d, c), l in zip(rows, lb) if not l)
            return e, la

        e, la = counts(lab)
        obs = spearman([e[t] for t in towns], [la[t] for t in towns])
        rng = random.Random(20261104)
        nulls = []
        for _ in range(SHUFFLES):
            x = lab[:]
            rng.shuffle(x)
            ee, ll = counts(x)
            nulls.append(spearman([ee[t] for t in towns], [ll[t] for t in towns]))
        lowest = sum(1 for n in nulls if n <= obs) / SHUFFLES
        st[k] = dict(n=len(rows), towns=len(towns), early=sum(lab), late=len(rows) - sum(lab), rho=obs, null=float(np.mean(nulls)),
                     lo=float(np.percentile(nulls, 2.5)), hi=float(np.percentile(nulls, 97.5)), p=lowest,
                     same=len(top3(e) & top3(la)), top_e=e.most_common(3), top_l=la.most_common(3))
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    names = SOURCES
    below = [k for k in SOURCES if st[k]["p"] < 0.05]
    inside = [k for k in SOURCES if k not in below]
    lo_rho = min(st[k]["rho"] for k in SOURCES)
    hi_rho = max(st[k]["rho"] for k in SOURCES)
    f2 = lambda x: f"{x:.2f}"
    by_pref = "、".join(f"{names[k]}{f2(st[k]['rho'])}" for k in SOURCES)
    below_txt = "・".join(names[k] for k in below) if below else "なし"
    inside_txt = "・".join(names[k] for k in inside) if inside else "なし"
    same_txt = "、".join(f"{names[k]}{st[k]['same']}" for k in SOURCES)
    rows1 = [[names[k], f"{st[k]['towns']}", f"{st[k]['early']}", f"{st[k]['late']}", f2(st[k]["rho"])] for k in SOURCES]
    rows2 = [[names[k], f2(st[k]["rho"]), f2(st[k]["null"]), f"{f2(st[k]['lo'])}〜{f2(st[k]['hi'])}", f"{st[k]['p'] * 100:.1f}%"] for k in SOURCES]
    rows3 = [[names[k], "・".join(t for t, _ in st[k]["top_e"]), "・".join(t for t, _ in st[k]["top_l"]), f"{st[k]['same']}/3"] for k in SOURCES]
    ak, mi = st["akita"], st["miyagi"]
    if below:
        shift_line = f"実際の相関が入れ替えの下位5%に入った県は、{below_txt}です。入れ替えた場合より順位が動いている、ということで、時期によって記録の出る場所が少し変わっているように読めます。一方、{inside_txt}は、入れ替えた場合の範囲に収まりました。"
        lead_tail = f"ただし、記録が属する時期をばらばらに入れ替えた場合の値と比べると、{below_txt}では、実際の順位のほうが入れ替わっていました。"
        ok_tail = f"{below_txt}は入れ替えた場合よりも順位が動いていたことです"
    else:
        shift_line = "実際の相関が入れ替えの下位5%に入った県はありません。6県とも、入れ替えた場合の範囲に収まりました。"
        lead_tail = "記録が属する時期をばらばらに入れ替えた場合の値と比べても、6県とも範囲に収まりました。"
        ok_tail = "入れ替えた場合の範囲を外れた県はなかったことです"

    doc = {
        "slug": "town-rank-stability", "date": today, "data_as_of": as_of,
        "title": "4〜6月に熊の記録が多かった市町村は、7〜9月も上位にいるか",
        "h1": "熊(クマ)の記録が多い市町村の顔ぶれは、4〜6月と7〜9月で入れ替わるか",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の記録です。市町村ごとの件数の順位を4〜6月と7〜9月で比べた相関は{f2(lo_rho)}〜{f2(hi_rho)}。順位の入れ替わりが偶然より大きかったのは{below_txt}でした。",
        "lead": (f"春に熊の記録が多かった市町村は、夏の終わりにも多いのでしょうか。6県の令和8年度の記録を、4〜6月と7〜9月に分け、市町村ごとの件数の順位がどれだけ似ているかを集計しました(順位相関)。値は{f2(lo_rho)}から{f2(hi_rho)}で、どの県でも、春に多い市町村は夏の終わりにも多めでした。"
                 + lead_tail),
        "findings": [
            f"市町村ごとの件数の順位が、4〜6月と7〜9月でどれだけ似ているか(スピアマンの順位相関、1に近いほど同じ並び)は、{by_pref}です。",
            f"件数の上位3市町村のうち、4〜6月と7〜9月の両方に入った市町村の数は、{same_txt}です(最大3)。",
            f"記録の時期を{SHUFFLES:,}回入れ替えた場合と比べます。実際の相関が下位5%に入ったのは、{below_txt}です。",
        ],
        "sections": [
            {"h2": "市町村の件数の順位は、4〜6月と7〜9月でどれだけ似ているか",
             "paragraphs": ["令和8年度(2026年4月1日から)の記録のうち、市町村名のある記録を使いました。記録の最新日がそろう9月30日までを、4〜6月と7〜9月の2つに分け、市町村ごとの件数を数えて、順位の似かたを見ました。見る指標は、順位相関(スピアマン)です。1なら並びがまったく同じ、0なら関係なし、という値です。",
                            f"6県の値は{f2(lo_rho)}から{f2(hi_rho)}でした。どの県も、春に件数が多い市町村は、夏の終わりにも多めです。最も高い秋田県は{f2(ak['rho'])}、宮城県は{f2(mi['rho'])}でした。",
                            "春に多く夏の終わりに少ない市町村や、その逆の市町村が、順位が動いた市町村です。どの市町村がどう動いたかは、この表だけでは分かりません。"],
             "table": {"head": ["県", "市町村の数", "4〜6月の記録(件)", "7〜9月の記録(件)", "順位の相関"], "rows": rows1,
                       "note": "市町村名のない記録は数えていません。どちらかの期間に記録がない市町村は、0件として順位に入れています。"}},
            {"h2": "入れ替えても出る値か",
             "paragraphs": ["相関が高いのは、当たり前の面もあります。年間を通して件数の多い市町村は、どちらの期間でも多くなりやすいからです。そこで、記録の日付だけを入れ替えて同じ計算をしました。各市町村の合計件数は変えず、どの記録が4〜6月か7〜9月かだけをランダムに入れ替えます。これを1,000回くり返し、平均と、中央の95%の範囲を出しました。",
                            shift_line,
                            "なぜ動いたかは、このノートでは分けていません。熊の動き、報告の集まり方、入力の時期など、いくつか理由が考えられます。"],
             "table": {"head": ["県", "実際の相関", "入れ替えの平均", "入れ替えの中央95%", "入れ替えで実際以下になった割合"], "rows": rows2,
                       "note": f"入れ替えは{SHUFFLES:,}回。実際以下になった割合が5%未満の県は、入れ替えた場合よりも順位が動いています。"}},
            {"h2": "上位3市町村は、2つの期間でどれくらい重なるか",
             "paragraphs": [f"順位全体ではなく、上位だけを比べます。4〜6月の上位3市町村と、7〜9月の上位3市町村で、両方に入った市町村の数は、{same_txt}でした。",
                            "市町村名は、各県の記録にある表記のままです。件数が同数のときは、記録に先に出てきた市町村を上位としています。"],
             "table": {"head": ["県", "4〜6月の上位3", "7〜9月の上位3", "両方に入った数"], "rows": rows3, "note": "件数の多い順に並べています。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の6県で、4〜6月に記録の多い市町村は7〜9月にも多めだったことです(相関{f2(lo_rho)}〜{f2(hi_rho)})。さらに、{ok_tail}。",
                            "言えないのは、順位が動いた市町村で熊の数や行動が変わったということです。報告されやすい場所、人の出入りが多い時期、入力の時期の違いも、順位を動かします。また、記録のない市町村が安全ということも言えません。",
                            "お住まいの市町村が上位にないときも、備えを省かないでください。最新の目撃情報は県別のページで、対処法は「クマに出会わないために」のページで見られます。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、市町村名のあるものです。4月1日から6月30日と、7月1日から9月30日に分けました。秋田・宮城・新潟・富山・山口・山梨の6県で、各県とも9月30日までを使っています。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "順位相関はスピアマンの順位相関係数で、同じ件数は平均の順位にしました。どちらかの期間に記録がない市町村は0件として入れています。",
            f"入れ替えは、各県で、記録の時期(4〜6月か7〜9月か)の組み合わせを{SHUFFLES:,}回ランダムに入れ替え、同じ計算をしたものです(乱数の種は固定)。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や行動を直接示すものではありません。",
            "県ごとに記録の集め方が違います。市町村の数が少ない県(富山県・山口県など)では、1市町村の違いで相関が大きく動きます。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
            "4〜6月と7〜9月という区切りは、このノートで決めた目安で、熊の行動の区分ではありません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/town-rank-stability.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
