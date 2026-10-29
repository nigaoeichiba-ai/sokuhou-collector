"""Research note: is October busier than September?  Records of 1-20 October against 1-20 September, for the five prefectures whose data reach late October.
Reference: the 40 days' counts with the 'October' label shuffled among the days (1,000 draws, fixed seed).  Yamanashi: which towns carry the October records.

python sites/kuma/research/scripts/october-vs-september.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
DAYS = 20
SEP0, OCT0 = date(2026, 9, 1), date(2026, 10, 1)
DRAWS = 1000


def day(r) -> date:
    return r[0].date() if isinstance(r[0], datetime) else r[0]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rng = random.Random(20261029)
    st, rows = {}, []
    for k, label in SOURCES.items():
        c = Counter(day(r) for r in data[k]["rows"])
        sep = [c.get(SEP0 + timedelta(i), 0) for i in range(DAYS)]
        octo = [c.get(OCT0 + timedelta(i), 0) for i in range(DAYS)]
        first, second = sum(octo[:10]), sum(octo[10:])
        allv = sep + octo
        sims = []
        for _ in range(DRAWS):
            rng.shuffle(allv)
            sims.append(sum(allv[DAYS:]) / max(sum(allv[:DAYS]), 1))
        sims.sort()
        lo, hi = sims[int(DRAWS * 0.025)], sims[int(DRAWS * 0.975) - 1]
        ratio = sum(octo) / sum(sep)
        st[k] = dict(sep=sum(sep), octo=sum(octo), ratio=ratio, lo=lo, hi=hi, first=first, second=second,
                     sep_days=sum(1 for v in sep if v), oct_days=sum(1 for v in octo if v), as_of=data[k]["as_of"])
        rows.append([label, f"{sum(sep)}", f"{sum(octo)}", f"{ratio:.2f}倍", f"{lo:.2f}〜{hi:.2f}倍", f"{first}件・{second}件"])
    above = [k for k in SOURCES if st[k]["ratio"] > st[k]["hi"]]
    below = [k for k in SOURCES if st[k]["ratio"] < st[k]["lo"]]
    inside = [k for k in SOURCES if k not in above and k not in below]
    tot_sep = sum(s["sep"] for s in st.values())
    tot_oct = sum(s["octo"] for s in st.values())

    # Yamanashi: towns of the 20 days in each month
    ym = data["yamanashi"]["rows"]
    towns = {}
    for name, lo_d in (("sep", SEP0), ("oct", OCT0)):
        sel = [r[2] for r in ym if lo_d <= day(r) <= lo_d + timedelta(days=DAYS - 1) and r[2]]
        towns[name] = Counter(sel)
    top_oct = towns["oct"].most_common(4)
    n_oct, n_sep = sum(towns["oct"].values()), sum(towns["sep"].values())
    new_in_oct = [c for c in towns["oct"] if c not in towns["sep"]]
    share3 = common.pct(sum(n for _, n in towns["oct"].most_common(3)), n_oct)
    share3_sep = common.pct(sum(n for _, n in towns["sep"].most_common(3)), n_sep)
    ots = towns["oct"]["大月市"]
    as_of = max(s["as_of"] for s in st.values())
    y = st["yamanashi"]
    total = sum(len(data[k]["rows"]) for k in SOURCES)
    names_inside = "・".join(SOURCES[k] for k in inside)
    ratio_rows = sorted(SOURCES, key=lambda k: -st[k]["ratio"])

    doc = {
        "slug": "october-vs-september", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃は10月に増えたか。9月と同じ20日で、5県の件数を比べる",
        "h1": "10月の熊(クマ)の目撃は、9月より増えたか。5県で同じ20日を比べる",
        "description": f"宮城・新潟・富山・山口・山梨の令和8年度の記録{total:,}件から、10月1〜20日の件数を9月1〜20日と比べました。5県とも倍率は偶然の範囲に収まり、山梨県は範囲の上限と同じ{y['ratio']:.2f}倍でした。",
        "lead": (f"10月に入り、熊のニュースが増えたと感じる人は多いと思います。では、記録の件数は、9月より本当に増えているのでしょうか。"
                 f"5県の記録で、9月1〜20日と10月1〜20日の件数を並べて数えました。結果は、5県合わせて{tot_sep}件が{tot_oct}件になっています。"
                 f"ただし、倍率が偶然の範囲を超えた県は、5県のなかにありません。山梨県は{y['ratio']:.2f}倍で、範囲の上限と同じ値でした。"),
        "findings": [
            f"9月1〜20日の{tot_sep}件に対し、10月1〜20日は{tot_oct}件(5県合計・{tot_oct / tot_sep:.2f}倍)でした。県で見ると、{'、'.join(f'{SOURCES[k]}{st[k]['ratio']:.2f}倍' for k in ratio_rows)}です。",
            f"日付の間で入れ替えた偶然の範囲を、実際の倍率が超えた県は{'ありません' if not above else '・'.join(SOURCES[k] for k in above)}。5県とも、日の並びが違うだけでも出る範囲に収まっています。",
            f"山梨県の10月1〜20日は{y['octo']}件で、9月の{y['sep']}件の{y['ratio']:.1f}倍です。10月の件数は前半の{y['first']}件に対して後半が{y['second']}件で、後半に偏っています。大月市が{ots}件で最も多く、上位3市町の割合は{share3:.0f}%(9月は{share3_sep:.0f}%)でした。",
        ],
        "sections": [
            {"h2": "9月と10月の同じ20日を、5県で比べる",
             "paragraphs": [f"令和8年度の記録のうち、9月1日〜20日と、10月1日〜20日を取り出し、それぞれの件数を数えました。月全体ではなく20日にそろえたのは、5県の記録の最新日が10月22日〜28日と違うためです。直近の数日は記録の追加が済んでいないことがあるので、全県で記録がそろっている10月20日までにしています。",
                            f"対象は、記録がこの年度で200件を超え、10月のデータがある宮城・新潟・富山・山口・山梨の5県です。20日間の件数は、9月が5県合計{tot_sep}件、10月が{tot_oct}件でした。",
                            "「偶然の範囲」は、次の計算です。9月の20日と10月の20日、合わせて40日の1日ごとの件数はそのままにして、どの日が10月かという区別だけを入れ替えます。これを1,000回行い、倍率の小さい側と大きい側から2.5%ずつを除いた範囲を書きました。乱数の種は固定しています。実際の倍率がこの範囲の外なら、日付の並びだけでは説明しにくい差です。"],
             "table": {"head": ["県", "9月1〜20日", "10月1〜20日", "倍率(10月÷9月)", "偶然の範囲", "10月の前半・後半"], "rows": rows,
                       "note": "件数は、各県の記録のうち、期間内の日付のものです。前半は10月1〜10日、後半は10月11〜20日の件数です。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in ratio_rows], "values": [round(st[k]["ratio"], 2) for k in ratio_rows],
                       "title": "10月1〜20日の件数は、9月1〜20日の何倍か(倍)",
                       "desc": "9月1〜20日の件数を1としたときの、10月1〜20日の件数の倍率。宮城・新潟・富山・山口・山梨の5県を比べた棒グラフ。"}},
            {"h2": "5県とも、偶然の範囲に収まった",
             "paragraphs": [f"倍率が1倍を超えたのは、5県のうち{sum(1 for s in st.values() if s['ratio'] > 1)}県です。宮城県だけが{st['miyagi']['ratio']:.2f}倍とわずかに下回りました。ただし、新潟県の{st['niigata']['ratio']:.2f}倍、富山県の{st['toyama']['ratio']:.2f}倍、山口県の{st['yamaguchi']['ratio']:.2f}倍は、20日の件数が十数件から数十件と少ないため、偶然の範囲に収まっています。件数が少ないと、数件の違いで倍率が大きく動きます。",
                            f"宮城県は、{st['miyagi']['sep']}件が{st['miyagi']['octo']}件で、ほぼ同じ水準です。宮城県は9月の件数がもともと多く、春から夏の水準に近い状態が続いています。新潟県は{st['niigata']['sep']}件が{st['niigata']['octo']}件で、ほぼ横ばいでした。",
                            f"最も倍率が高いのは山梨県の{y['ratio']:.2f}倍です。{y['sep']}件が{y['octo']}件になりましたが、偶然の範囲は{y['lo']:.2f}〜{y['hi']:.2f}倍で、実際の倍率はその上限と同じ値でした。範囲の外に出てはいないので、「偶然では説明しにくい」とまでは言えません。ほかの4県と比べると増え方は大きく、10月の末に向けて確かめる価値のある県です。"]},
            {"h2": "山梨県の10月は、後半に集まっている",
             "paragraphs": [f"山梨県の10月1〜20日の{y['octo']}件は、1〜10日が{y['first']}件、11〜20日が{y['second']}件で、後半が約{y['second'] / y['first']:.1f}倍です。同じ日数で比べても、増えた分は10月の後半に偏っています。宮城・新潟・富山は、前半のほうが後半より多くなっています。",
                            f"山梨県の10月1〜20日の{n_oct}件を市町村別に数えると、{'、'.join(f'{c}{n}件' for c, n in top_oct)}の順でした。上位3市町で{share3:.0f}%です。9月1〜20日の{n_sep}件では、上位3市町の割合は{share3_sep:.0f}%でした。",
                            f"9月の20日に記録がなく、10月の20日に記録が出た市町村は、{len(new_in_oct)}か所あります。" + (f"{'、'.join(new_in_oct)}です。" if new_in_oct else "") +
                            "市町村名のない記録は、この集計に入れていません。"],
             "table": {"head": ["順位", "10月1〜20日の市町村", "件数", "9月1〜20日の同じ市町村の件数"],
                       "rows": [[f"{i + 1}", c, f"{n}", f"{towns['sep'].get(c, 0)}"] for i, (c, n) in enumerate(top_oct)],
                       "note": "山梨県の記録のうち、市町村名のあるものを数えています。件数が同じ市町村は、記録に先に現れた順で並べています。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の記録で、10月の20日間が9月の20日間より多かった県は、5県のうち4県だということです。増え方が最も大きいのは山梨県(2.00倍)でした。ただし、どの県の倍率も偶然の範囲に収まっています。「10月に増えた」と断定できる県は、この記録にはありません。",
                            "言えないのは、増えた理由です。山の食べ物の状況や、見回りの回数、報告のしやすさなど、記録の件数を動かす要因は多くあり、このページの計算はどれも調べていません。「10月は危ない」「10月は安全」と読むための数字でもありません。",
                            "お住まいの県の最新の記録は、県別のページで確かめてください。このページは10月20日までの記録で数えていて、10月21日以降の動きはまだ含まれていません。山梨県の後半の偏りが続くかは、記録が増えてから改めて確かめます。"]},
        ],
        "method": [
            "対象は、令和8年度(2026年4月1日から)の記録のうち、9月1〜20日と10月1〜20日のものです。5県の記録の最新日は10月22日〜28日で、そろって記録がある10月20日までにそろえました。",
            f"倍率は、10月1〜20日の件数を9月1〜20日の件数で割ったものです。偶然の範囲は、この40日の1日ごとの件数を保ち、10月の日の区別だけを入れ替える計算を{DRAWS:,}回行った結果です。2.5%〜97.5%の範囲を書いています。",
            "市町村は、記録の市町村名の欄をそのまま使っています。市町村名のない記録は、市町村別の集計に入れていません。",
            "秋田県は記録が9月30日までのため、対象にしていません。記録が200件に届かない県も対象にしていません。",
        ],
        "caveats": [
            "これは「報告された記録」の数え方です。熊の実際の数や、人里への出没の多さそのものではありません。報告のしやすさや、記録のまとめ方の違いも、件数に影響します。",
            "20日間の件数が少ない県は、数件の違いで倍率が大きく動きます。県どうしの倍率の差を、県の違いとして読まないでください。",
            "同じ20日の比べ方で、令和8年度だけの結果です。ほかの年にも同じ傾向になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/october-vs-september.py",
        "related": [{"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, s in st.items():
        print(k, s)
    print(above, below, inside, top_oct, share3, share3_sep, new_in_oct)
    print(sum(len(str(p)) for s in doc["sections"] for p in s["paragraphs"]))


if __name__ == "__main__":
    main()
