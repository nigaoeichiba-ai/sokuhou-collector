"""Research note: do bear records differ on long holidays and weekends?  Six prefectures, April-September 2026; daily counts relative to a 15-day moving average, compared with 1,000 random shifts of the calendar mask.

python sites/kuma/research/scripts/holiday-weeks.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
START, END = date(2026, 4, 1), date(2026, 9, 30)
SHIFTS = 1000
# Long holiday spells of 2026 (Saturday-Sunday plus national holidays; the Obon days are the usual leave period, not a legal holiday).
SPELLS = [
    ("ゴールデンウィーク", date(2026, 4, 29), date(2026, 5, 6)),
    ("海の日の3連休", date(2026, 7, 18), date(2026, 7, 20)),
    ("お盆(8月13〜16日)", date(2026, 8, 13), date(2026, 8, 16)),
    ("9月の連休(19〜23日)", date(2026, 9, 19), date(2026, 9, 23)),
]
GROUPS = ["連休の日", "連休以外の土日", "連休以外の平日"]


def normalized(counts: list[int]) -> list:
    """count / centred 15-day mean (first and last 7 days and days with mean 0 are None)."""
    n, out = len(counts), []
    for i in range(n):
        if i < 7 or i >= n - 7:
            out.append(None)
            continue
        m = sum(counts[i - 7:i + 8]) / 15
        out.append(counts[i] / m if m > 0 else None)
    return out


def labels(days: list[date]) -> list[int]:
    """0 = long-holiday day, 1 = other Saturday/Sunday, 2 = other weekday."""
    out = []
    for d in days:
        if any(a <= d <= b for _, a, b in SPELLS):
            out.append(0)
        elif d.weekday() >= 5:
            out.append(1)
        else:
            out.append(2)
    return out


def group_means(norm: list, lab: list[int]) -> list[float]:
    sums = [[], [], []]
    for v, g in zip(norm, lab):
        if v is not None:
            sums[g].append(v)
    return [float(np.mean(s)) if s else float("nan") for s in sums]


def contrasts(norm: list, lab: list[int]) -> tuple[float, float]:
    m = group_means(norm, lab)
    off = [v for v, g in zip(norm, lab) if v is not None and g != 0]
    return m[0] - float(np.mean(off)), m[1] - m[2]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    days = [START + timedelta(i) for i in range((END - START).days + 1)]
    n = len(days)
    lab = labels(days)
    counts_days0 = [sum(1 for g in lab if g == i) for i in range(3)]
    st, per_day = {}, [[] for _ in days]
    for k, src in data.items():
        c = Counter((r[0].date() if isinstance(r[0], datetime) else r[0]) for r in src["rows"])
        counts = [c[d] for d in days]
        norm = normalized(counts)
        for i, v in enumerate(norm):
            per_day[i].append(v)
        st[k] = dict(n=sum(counts), norm=norm, counts=counts)
    pn = [float(np.mean(v)) if all(x is not None for x in v) else None for v in per_day]
    rng = random.Random(20261106)
    offsets = [rng.randrange(1, n) for _ in range(SHIFTS)]

    res = {}
    for k in list(SOURCES) + ["all"]:
        norm = pn if k == "all" else st[k]["norm"]
        means = group_means(norm, lab)
        c1, c2 = contrasts(norm, lab)
        n1, n2 = [], []
        for o in offsets:
            shifted = lab[o:] + lab[:o]
            a, b = contrasts(norm, shifted)
            n1.append(a)
            n2.append(b)
        p1 = sum(1 for x in n1 if abs(x) >= abs(c1)) / SHIFTS
        p2 = sum(1 for x in n2 if abs(x) >= abs(c2)) / SHIFTS
        res[k] = dict(means=means, c1=c1, c2=c2, p1=p1, p2=p2, lo1=float(np.percentile(n1, 2.5)), hi1=float(np.percentile(n1, 97.5)),
                      lo2=float(np.percentile(n2, 2.5)), hi2=float(np.percentile(n2, 97.5)))

    # per spell (6 prefectures pooled)
    spell_rows = []
    for name, a, b in SPELLS:
        vals = [pn[i] for i, d in enumerate(days) if a <= d <= b and pn[i] is not None]
        spell_rows.append([name, f"{a.month}月{a.day}日〜{b.month}月{b.day}日", f"{len(vals)}", f"{np.mean(vals):.2f}" if vals else "—"])

    raw = {}
    for k in SOURCES:
        cs = st[k]["counts"]
        raw[k] = [sum(c for c, g in zip(cs, lab) if g == i) / counts_days0[i] for i in range(3)]
    rows_raw = [[SOURCES[k]] + [f"{x:.1f}" for x in raw[k]] + [f"{(1 - raw[k][1] / raw[k][2]) * 100:.0f}%"] for k in SOURCES]
    wk_cut = [1 - raw[k][1] / raw[k][2] for k in SOURCES]
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    total = sum(st[k]["n"] for k in SOURCES)
    f2 = lambda x: f"{x:.2f}"
    A = res["all"]
    counts_days = [sum(1 for g in lab if g == i) for i in range(3)]
    valid_days = [sum(1 for v, g in zip(pn, lab) if v is not None and g == i) for i in range(3)]
    sig1 = [SOURCES[k] for k in SOURCES if res[k]["p1"] < 0.05]
    sig2 = [SOURCES[k] for k in SOURCES if res[k]["p2"] < 0.05]
    rows1 = [[GROUPS[i], f"{counts_days[i]}", f"{valid_days[i]}", f2(A["means"][i])] for i in range(3)]
    rows2 = [[SOURCES[k]] + [f2(x) for x in res[k]["means"]] for k in SOURCES]
    rows3 = []
    for k in list(SOURCES) + ["all"]:
        r = res[k]
        rows3.append([SOURCES[k] if k != "all" else "6県を合わせた値", f"{r['c1']:+.2f}", f"{r['lo1']:+.2f}〜{r['hi1']:+.2f}", f"{r['p1'] * 100:.1f}%",
                      f"{r['c2']:+.2f}", f"{r['lo2']:+.2f}〜{r['hi2']:+.2f}", f"{r['p2'] * 100:.1f}%"])

    def verdict(p, sig, what):
        s = f"{what}、カレンダーをずらした1,000通りの範囲" + ("を超えました" if p < 0.05 else "に収まりました")
        s += f"(ずらして実際以上に差が出た割合は{p * 100:.1f}%)。"
        if sig:
            s += f"県別では{'・'.join(sig)}が範囲を超えました。ただし6県を並べているので、偶然でも1県は超えることがあります。"
        else:
            s += "県別で範囲を超えた県は、ありませんでした。"
        return s

    v1 = verdict(A["p1"], sig1, "6県を合わせた連休の日とそれ以外の日の差は")
    v2 = verdict(A["p2"], sig2, "6県を合わせた連休以外の土日と平日の差は")
    doc = {
        "slug": "holiday-weeks", "date": today, "data_as_of": as_of,
        "title": "連休やお盆に熊の記録は増えるか。ゴールデンウィークなど4つの連休で数えた",
        "h1": "熊(クマ)の記録は連休や土日に変わるか。6県の4〜9月",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度4〜9月、{total:,}件を、連休・土日・平日に分けて数えました。連休の日は前後7日の平均の{f2(A['means'][0])}倍。カレンダーをずらした範囲との比較つきです。",
        "lead": (f"山に入る人が増える連休は、熊の記録も増えるのでしょうか。6県の令和8年度の記録{total:,}件(4月1日〜9月30日)を、ゴールデンウィークなど4つの連休、それ以外の土日、それ以外の平日に分けて比べました。"
                 f"季節で件数が大きく変わるため、各日の件数は前後7日の平均で割っています。連休の日は{f2(A['means'][0])}、連休以外の土日は{f2(A['means'][1])}、連休以外の平日は{f2(A['means'][2])}でした(1.00が前後7日の平均と同じ)。"
                 "差が偶然の範囲かどうかは、カレンダーの位置をずらした1,000通りと比べて確かめています。"),
        "findings": [
            f"日ごとの件数を前後7日の平均で割ると、6県の平均は、連休の日が{f2(A['means'][0])}、連休以外の土日が{f2(A['means'][1])}、連休以外の平日が{f2(A['means'][2])}です(1.00で平均並み)。",
            f"連休の日とそれ以外の日の差は{A['c1']:+.2f}。カレンダーをずらした1,000通りの95%は{A['lo1']:+.2f}〜{A['hi1']:+.2f}に入ります。{v1}",
            f"連休以外の土日と平日の差は{A['c2']:+.2f}。ずらした1,000通りの95%は{A['lo2']:+.2f}〜{A['hi2']:+.2f}に入ります。{v2}",
        ],
        "sections": [
            {"h2": "連休・土日・平日で、記録の件数は変わるか",
             "paragraphs": [f"令和8年度の記録のうち、4月1日から9月30日の{total:,}件を使いました。県ごとに1日あたりの件数を数え、その日の前後7日(15日間)の平均で割りました。熊の記録は春から夏へ季節で増減するため、割らずに比べると、たまたま件数の多い時期にあった連休が高く出てしまうからです。",
                            "連休は、2026年のカレンダーで次の4つを選びました。4月29日〜5月6日のゴールデンウィーク、7月18〜20日の海の日の3連休、お盆の8月13〜16日、9月19〜23日の連休です。お盆は法律上の休日ではなく、休みを取る人が多い期間として入れています。",
                            f"それ以外の日を、土日と平日に分けます。日数は、連休の日{counts_days[0]}日、連休以外の土日{counts_days[1]}日、連休以外の平日{counts_days[2]}日です。1.00は、前後7日の平均と同じ件数という意味です。"],
             "table": {"head": ["区分", "日数", "前後7日がそろう日数", "件数÷前後7日の平均(6県平均)"], "rows": rows1, "note": "4月1〜7日と9月24〜30日は、前後7日がそろわないため平均に入れていません。"}},
            {"h2": "連休ごとに見ると、どうか",
             "paragraphs": ["連休を1つずつ見ると、日数が3〜8日と短く、1日の件数も県ごとに0〜数件のため、値は大きく揺れます。次の表は、6県の値を日ごとに平均してから、連休ごとに平均したものです。",
                            "連休の日数が少ないほど、1回の連休の値は偶然で上下しやすくなります。そのため、表の1行だけを取り出して「この連休は増えた」とは言いにくいです。"],
             "table": {"head": ["連休", "期間", "前後7日がそろう日数", "件数÷前後7日の平均(6県平均)"], "rows": spell_rows, "note": "9月24日以降は前後7日がそろわないため、9月の連休は一部の日だけを含みます。"}},
            {"h2": "県ごとに見ても同じか",
             "paragraphs": ["県別に同じ計算をすると、次のとおりです。記録の少ない県では、1日の件数が0や1になるため、値が大きく揺れます。"],
             "table": {"head": ["県"] + GROUPS, "rows": rows2, "note": "各区分の「件数÷前後7日の平均」の平均。"}},
            {"h2": "割らない件数で見ると、土日は何件少ないか",
             "paragraphs": ["ここまでの値は前後7日の平均で割った比です。割る前の、1日あたりの件数も示します。県ごとに、連休の日、連休以外の土日、連休以外の平日の1日あたりの件数を平均しました。",
                            f"連休以外の土日の件数が平日より少ない割合は、県ごとに{min(wk_cut) * 100:.0f}%から{max(wk_cut) * 100:.0f}%でした。平日の比が1.00を少し超えるのは、土日と連休が1.00を下回る分、平均が平日側にかたよるためで、平日に増えているという意味ではありません。",
                            f"土日のほうが少ない県は、6県中{sum(1 for x in wk_cut if x > 0)}県でした。{'6県とも同じ向きですが、' if all(x > 0 for x in wk_cut) else ''}差の大きさは県によって大きく違い、記録の多い秋田県では1日あたり{raw['akita'][2] - raw['akita'][1]:.1f}件、宮城県では{raw['miyagi'][2] - raw['miyagi'][1]:.1f}件の差です。",
                            "土日に件数が少ないのは、情報を受け付ける窓口の動きが平日と違うためかもしれません。ただ、記録からその理由までは分かりません。"],
             "table": {"head": ["県", "連休の日(件/日)", "連休以外の土日(件/日)", "連休以外の平日(件/日)", "土日が平日より少ない割合"], "rows": rows_raw, "note": "4月1日〜9月30日の記録を、区分ごとの日数で割った値。前後7日の平均では割っていません。"}},
            {"h2": "カレンダーをずらしても出る差か",
             "paragraphs": ["連休や土日の差は、カレンダーと関係がなくても、日々の件数のばらつきで出ます。どこまでが偶然の範囲かを見るため、連休・土日・平日の並び全体を、1〜182日の範囲でランダムにずらす計算を1,000回しました。記録の日付は変えません。ずらした場合の差の95%が入る範囲を出しています。",
                            v1 + v2,
                            "この比べ方で分かるのは、カレンダーと記録の件数に、偶然では説明しにくい関係があるかどうかまでです。あったとしても、熊の動きが変わったのか、人の出歩きや報告のしかたが変わったのかは、記録からは分かりません。"],
             "table": {"head": ["県", "連休−それ以外の差", "ずらした場合の95%の範囲", "ずらして実際以上になった割合", "土日−平日の差", "ずらした場合の95%の範囲", "ずらして実際以上になった割合"], "rows": rows3, "note": "割合が5%未満のときは、カレンダーをずらした場合より差が大きいことになります。6県を並べているので、1県は偶然でも出ることがあります。差が0より大きいと、連休(土日)のほうが多い側です。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の4〜9月の記録では、連休の日が{f2(A['means'][0])}、連休以外の土日が{f2(A['means'][1])}、連休以外の平日が{f2(A['means'][2])}だったことです。{v1}{v2}",
                            "言えないのは、連休に山へ入る人が増えるから記録が増える(あるいは減る)、といった理由です。記録は人が見つけて自治体に届けた件数なので、休日は役所の受け付け方が変わることもあります。1年度の半年分で、連休も4つだけです。ほかの年に同じ形になるかは分かりません。",
                            "連休や土日に記録の件数が少なく見えても、その日に熊がいないという意味にはなりません。山や川沿いに出かける日は、記録の件数に関わらず、鈴やラジオなどで人がいることを知らせ、最新の情報を確かめてください。",
                            "連休かどうかに関わらず、熊の出没情報は毎日変わります。お住まいの県の最新の目撃情報は県別のページで、出会わないための対処は「クマに出会わないために」のページで見られます。"]},
        ],
        "method": [
            f"対象は、令和8年度の記録のうち、4月1日から9月30日の{total:,}件です(秋田・宮城・新潟・富山・山口・山梨。日付のある記録すべて)。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "日ごとの件数は、その日の前後7日の15日間の平均で割りました。前後7日がそろわない最初と最後の7日、平均が0の日は除きます。6県の値は、日ごとに6県の値を平均してから区分ごとに平均しました。",
            "連休の日は、ゴールデンウィーク(4月29日〜5月6日)、海の日の3連休(7月18〜20日)、お盆(8月13〜16日)、9月の連休(19〜23日)です。この選び方は筆者が決めたもので、役所の定義ではありません。土日は、連休に入らない土曜と日曜です。",
            f"カレンダーのずらしは、区分の並び全体を1〜{n - 1}日のうちランダムに選んだ日数だけずらす計算を{SHIFTS:,}回しました(乱数の種は固定)。「差」は区分の平均値の差で、連休は連休以外の全日と、土日は平日と比べています。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の動きや数を直接示すものではありません。",
            "休日は、人の出歩きや役所の受け付けが平日と違います。記録の件数の差が、熊の側の変化かどうかは分かりません。",
            "連休は4つだけで、日数も短いため、1回ごとの値は偶然で上下します。",
            "1年度の4〜9月だけです。県によって記録の集め方も違います。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/holiday-weeks.py",
        "related": [{"label": "時間帯ごとの報告(何時ごろ多いか)", "href": "/research/hour-of-day/"}, {"label": "満月の前後で記録は変わるか", "href": "/research/moon-phase/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(rows1, spell_rows, [(k, round(res[k]['p1'], 3), round(res[k]['p2'], 3)) for k in res], total, sig1, sig2, f2(A['c1']), f2(A['c2']))


main()
