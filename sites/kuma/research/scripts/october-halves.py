"""Research note: did the bear records fall off in the second half of October?  Five prefectures, 1-14 October against 15-28 October (28 days common to all five), with 1-14 / 15-28 September beside them.
A shuffle test moves the dates of the October records among the days 1-28 at random and counts how often the second-half share is as far from 50% as the real one.

python sites/kuma/research/scripts/october-halves.py
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
TRIALS = 5000


def halves(days: list[date], month: int) -> tuple[int, int]:
    first = sum(1 for d in days if d.month == month and d.day <= 14)
    second = sum(1 for d in days if d.month == month and 15 <= d.day <= 28)
    return first, second


def shuffle_extreme(n1: int, n2: int, rng: random.Random) -> float:
    """Share of shuffles in which the second-half count is at least as far from half as the real one (two-sided)."""
    n = n1 + n2
    gap = abs(n2 - n / 2)
    hit = 0
    for _ in range(TRIALS):
        # each record lands on one of the 28 days with equal chance; days 15-28 are the second half
        s = sum(1 for _ in range(n) if rng.randrange(28) >= 14)
        if abs(s - n / 2) >= gap:
            hit += 1
    return hit / TRIALS


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rng = random.Random(20261101)
    st = {}
    for k, src in data.items():
        days = [r[0].date() if isinstance(r[0], datetime) else r[0] for r in src["rows"]]
        o1, o2 = halves(days, 10)
        s1, s2 = halves(days, 9)
        st[k] = dict(o1=o1, o2=o2, s1=s1, s2=s2, o=o1 + o2, share=o2 / (o1 + o2), sshare=s2 / (s1 + s2),
                     p=shuffle_extreme(o1, o2, rng), after=sum(1 for d in days if d >= date(2026, 10, 29)),
                     ratio=o2 / o1 if o1 else 0)
    as_of = max(s["as_of"] for s in data.values())
    total = sum(s["o"] for s in st.values())
    fell = [k for k in SOURCES if st[k]["o2"] < st[k]["o1"]]
    rose = [k for k in SOURCES if st[k]["o2"] > st[k]["o1"]]
    sig = [k for k in SOURCES if st[k]["p"] < 0.05]
    order = sorted(SOURCES, key=lambda k: st[k]["share"])
    low, high = order[0], order[-1]
    pc = lambda x: f"{x * 100:.0f}%"
    rows = [[SOURCES[k], f"{st[k]['o1']:,}", f"{st[k]['o2']:,}", f"{st[k]['o']:,}", pc(st[k]["share"]), f"{st[k]['p'] * 100:.1f}%"] for k in SOURCES]
    srows = [[SOURCES[k], f"{st[k]['s1']:,}", f"{st[k]['s2']:,}", pc(st[k]["sshare"]), pc(st[k]["share"])] for k in SOURCES]
    sig_names = "・".join(SOURCES[k] for k in sig)
    notsig = [k for k in SOURCES if k not in sig]
    notsig_names = "・".join(SOURCES[k] for k in notsig)
    both_same = [k for k in SOURCES if (st[k]["sshare"] > 0.5) == (st[k]["share"] > 0.5)]

    doc = {
        "slug": "october-halves", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃は10月の後半に減ったか。5県で前半と後半を比べる",
        "h1": "熊(クマ)の目撃は、10月の後半に減ったか。10月1〜14日と15〜28日を5県で比べる",
        "description": f"宮城・新潟・富山・山口・山梨の令和8年度の記録で、10月1〜14日と15〜28日の件数を比べました。後半の割合は{SOURCES[low]}{pc(st[low]['share'])}、{SOURCES[high]}{pc(st[high]['share'])}で、県によって逆でした。",
        "lead": (f"秋が深まると熊の出没は落ち着く、と考える人は多いと思います。10月を前半(1〜14日)と後半(15〜28日)に分けて数えると、後半が前半より少なかったのは5県のうち{len(fell)}県、多かったのは{len(rose)}県でした。"
                 f"5県の10月1〜28日の記録{total:,}件を、日付を入れ替えた偶然のずれと比べて確かめます。"),
        "findings": [
            f"10月1〜14日と15〜28日の件数は、{'、'.join(f'{SOURCES[k]}{st[k]['o1']}件→{st[k]['o2']}件' for k in SOURCES)}です。後半が減ったのは{'・'.join(SOURCES[k] for k in fell)}、増えたのは{'・'.join(SOURCES[k] for k in rose)}でした。",
            f"後半の割合が最も低いのは{SOURCES[low]}の{pc(st[low]['share'])}、最も高いのは{SOURCES[high]}の{pc(st[high]['share'])}です。{SOURCES[low]}は前半の{st[low]['o1']}件が後半は{st[low]['o2']}件に、{SOURCES[high]}は{st[high]['o1']}件が{st[high]['o2']}件になっています。",
            f"件数を日付に入れ替えて{TRIALS:,}回ためした偶然の範囲を超えたのは{sig_names if sig else 'なし'}です。" + (f"{notsig_names}は、前半と後半の差が偶然のずれの範囲に入りました。" if sig and notsig else ""),
        ],
        "sections": [
            {"h2": "10月の前半と後半の件数",
             "paragraphs": [f"令和8年度の記録のうち、10月1日から28日までを、1〜14日(前半)と15〜28日(後半)に分けて数えました。どちらも14日間です。28日で区切ったのは、5県のうち記録の最新日がいちばん早い宮城県が10月28日だったためです。29日以降の記録は、{'、'.join(f'{SOURCES[k]}{st[k]['after']}件' for k in SOURCES if st[k]['after'])}ありますが、この表には入れていません。",
                            f"合計は5県で{total:,}件です。宮城県が{st['miyagi']['o']}件と最も多く、前半が{st['miyagi']['o1']}件、後半が{st['miyagi']['o2']}件でした。山梨県は逆に、前半の{st['yamanashi']['o1']}件に対して後半が{st['yamanashi']['o2']}件です。",
                            f"1日あたりに直すと、宮城県は前半が{st['miyagi']['o1'] / 14:.1f}件、後半が{st['miyagi']['o2'] / 14:.1f}件、山梨県は前半が{st['yamanashi']['o1'] / 14:.1f}件、後半が{st['yamanashi']['o2'] / 14:.1f}件です。後半の件数が前半の何倍かを見ると、宮城県は{st['miyagi']['ratio']:.2f}倍、山口県は{st['yamaguchi']['ratio']:.2f}倍、新潟県は{st['niigata']['ratio']:.2f}倍、富山県は{st['toyama']['ratio']:.2f}倍、山梨県は{st['yamanashi']['ratio']:.2f}倍です。1倍を下回れば後半が少なく、上回れば後半が多いことになります。"],
             "table": {"head": ["県", "10/1〜14", "10/15〜28", "10月1〜28日の合計", "後半の割合", "偶然でもこの差になる割合"], "rows": rows,
                       "note": "「偶然でもこの差になる割合」は、記録の日付を1〜28日の中でランダムに入れ替えて、後半の件数が半分から同じだけ離れた回の割合です(5,000回)。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [round(st[k]["share"] * 100) for k in order],
                       "title": "10月の記録のうち、15〜28日に出た割合(%)",
                       "desc": "10月1〜28日の記録のうち後半の15〜28日に入る割合を、5県で比べた棒グラフ。50%より低ければ後半が少ない。"}},
            {"h2": "9月の前半と後半との比べ方",
             "paragraphs": ["同じ区切りで9月も数えました。9月1〜14日と15〜28日です。10月の動きが、9月から続いているのか、10月に入って変わったのかを見る目安になります。",
                            f"9月と10月で後半の割合が半分より上か下かが同じ県は、5県のうち{len(both_same)}県({'・'.join(SOURCES[k] for k in both_same)})です。宮城県は9月に後半が増え({pc(st['miyagi']['sshare'])})、10月は後半が減りました({pc(st['miyagi']['share'])})。9月の後半に増えた記録が、10月の前半まで続いてから減った形です。"],
             "table": {"head": ["県", "9/1〜14", "9/15〜28", "9月の後半の割合", "10月の後半の割合"], "rows": srows, "note": "9月の区切りも、10月と同じ前半14日・後半14日です。"}},
            {"h2": "偶然のずれとの比べ方",
             "paragraphs": [f"件数が少ない県は、数件の違いで割合が大きく動きます。たとえば富山県は、前半が{st['toyama']['o1']}件、後半が{st['toyama']['o2']}件で、後半の割合は{pc(st['toyama']['share'])}ですが、記録が{st['toyama']['o']}件と少ないため、偶然のずれの範囲に入ります。",
                            f"記録の日付を28日の中でランダムに入れ替えると、{st['miyagi']['o']}件ある宮城県でも、後半の割合が半分から大きくずれることがあります。それでも、実際の{pc(st['miyagi']['share'])}ほど離れる回は、{TRIALS:,}回のうち{round(st['miyagi']['p'] * TRIALS)}回でした。" if st["miyagi"]["p"] < 0.05 else
                            f"宮城県の後半の割合は{pc(st['miyagi']['share'])}ですが、偶然のずれの範囲に入ります。"],
             },
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の10月は、県によって前半と後半の動きが違ったことです。{'・'.join(SOURCES[k] for k in fell)}では後半が少なく、{'・'.join(SOURCES[k] for k in rose)}では後半が多くなりました。「秋は、後半になるほど減る」とは、この5県では言えません。",
                            f"偶然のずれを超えたのは{sig_names if sig else 'なし'}です。" + (f"{notsig_names}は、差があっても、日付を入れ替えた場合に出る範囲に入っています。" if sig and notsig else "") + "差が偶然の範囲を超えたことは、その差の理由が分かったことではありません。",
                            "ただし、記録が減ったことは、熊が減ったことを意味しません。報告する人の行動、自治体の記録の入力時期、天候、エサの量などが、日付ごとの件数に影響している可能性があります。また、住んでいる地域の出没を予測するものでもありません。",
                            "11月に入ると冬眠に向かうと言われますが、このページは11月の記録を使っていません。11月の記録がそろってから、別の形で数えます。お住まいの県の最新の目撃情報は、県別のページで見られます。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、9月1日から10月28日までのものです。記録の最新日が最も早い宮城県が10月28日だったため、5県とも10月28日までで区切りました。計算した日は{common.today().isoformat()}、使った記録の最新日は{as_of}です。",
            "前半は各月の1〜14日、後半は15〜28日です。月末の29日以降は、日数が月によって違うため、この比べ方では使っていません。",
            f"日付は、記録の観測日をそのまま使っています。偶然のずれは、その県の10月1〜28日の記録の件数を、28日のうちのどの日にも同じ確率で割りふる計算を{TRIALS:,}回くり返して出しました。乱数の種は固定です。",
            "対象の5県は、october-vs-september(10月1〜20日と9月1〜20日の件数)と同じ県です。秋田県は記録が9月30日までのため入れていません。計算のスクリプトは、公開しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や行動の変化を直接示すものではありません。",
            "県ごとに記録の集め方が違います。記録を入力するまでの遅れがあると、後半の件数が少なく見えます。最新日に近い日ほど、入力が済んでいない分が含まれる可能性があります。",
            "1年度分(令和8年度)の10月だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
            "富山県・新潟県のように記録が少ない県は、数件の違いで割合が変わります。県どうしの割合の差を、そのまま比べないでください。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/october-halves.py",
        "related": [{"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"}, {"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, s in st.items():
        print(k, s)
    print("chars", sum(len(p) for s in doc["sections"] for p in s["paragraphs"]) + sum(len(x) for x in doc["method"] + doc["caveats"] + doc["findings"]))
    print(doc["lead"])
    for f in doc["findings"]:
        print(f)


if __name__ == "__main__":
    main()
