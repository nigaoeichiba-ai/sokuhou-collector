"""Research note: do bear records differ by moon phase?  Six prefectures, April-September 2026; daily counts relative to a 15-day moving average, compared with 1,000 random shifts of the lunar calendar.

python sites/kuma/research/scripts/moon-phase.py
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
SYN = 29.530588853
REF = date(2000, 1, 6)     # a new moon (18:14 UTC on 6 January 2000 = 03:14 JST on 7 January)
SHIFTS = 1000
BIN_NAMES = ["新月から上弦", "上弦から満月", "満月から下弦", "下弦から新月"]
BINS = [(0, SYN / 4), (SYN / 4, SYN / 2), (SYN / 2, SYN * 3 / 4), (SYN * 3 / 4, SYN)]
BIN_LABELS = ["月齢0〜7.4(新月から上弦)", "月齢7.4〜14.8(上弦から満月)", "月齢14.8〜22.1(満月から下弦)", "月齢22.1〜29.5(下弦から新月)"]


def age(d: date, shift: float = 0.0) -> float:
    """Moon age at midday of the day (days since the new moon)."""
    return ((d - REF).days + 0.5 - 1.13 + shift) % SYN      # new moon was 1.13 days after 0:00 of 6 Jan 2000 JST... midday of d, minus the 03:14 JST offset


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


def stats(days: list, norm: list, shift: float):
    sums = [[] for _ in BINS]
    for d, v in zip(days, norm):
        if v is None:
            continue
        a = age(d, shift)
        for i, (lo, hi) in enumerate(BINS):
            if lo <= a < hi:
                sums[i].append(v)
    return [float(np.mean(s)) for s in sums], [len(s) for s in sums]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    days = [START + timedelta(i) for i in range((END - START).days + 1)]
    st, per_day = {}, [[] for _ in days]
    for k, src in data.items():
        c = Counter((r[0].date() if isinstance(r[0], datetime) else r[0]) for r in src["rows"])
        counts = [c[d] for d in days]
        norm = normalized(counts)
        for i, v in enumerate(norm):
            per_day[i].append(v)
        st[k] = dict(n=sum(counts), norm=norm)
    pn = [float(np.mean(v)) if all(x is not None for x in v) else None for v in per_day]
    rng = random.Random(20261105)
    shifts = [rng.uniform(0, SYN) for _ in range(SHIFTS)]

    def spread(means):
        return max(means) - min(means)

    res = {}
    for k in list(SOURCES) + ["all"]:
        norm = pn if k == "all" else st[k]["norm"]
        means, ns = stats(days, norm, 0.0)
        obs = spread(means)
        nulls = [spread(stats(days, norm, s)[0]) for s in shifts]
        p = sum(1 for x in nulls if x >= obs) / SHIFTS
        res[k] = dict(means=means, ns=ns, spread=obs, null=float(np.mean(nulls)), hi=float(np.percentile(nulls, 95)), p=p)

    def near(target):
        v = []
        for d, x in zip(days, pn):
            if x is None:
                continue
            a = age(d)
            dist = min(abs(a - target), SYN - abs(a - target))
            if dist <= 2:
                v.append(x)
        return float(np.mean(v)), len(v)

    full, nf = near(SYN / 2)
    new, nn = near(0.0)
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    total = sum(st[k]["n"] for k in SOURCES)
    f2 = lambda x: f"{x:.2f}"
    A = res["all"]
    sig = [SOURCES[k] for k in SOURCES if res[k]["p"] < 0.05]
    sig_txt = "・".join(sig)
    ranges = [res[k]["spread"] for k in SOURCES]
    rows1 = [[BIN_LABELS[i], f"{A['ns'][i]}", f2(A["means"][i])] for i in range(4)]
    rows2 = [[SOURCES[k]] + [f2(x) for x in res[k]["means"]] for k in SOURCES]
    rows3 = [[SOURCES[k], f"{st[k]['n']:,}", f2(res[k]["spread"]), f2(res[k]["null"]), f2(res[k]["hi"]), f"{res[k]['p'] * 100:.1f}%"] for k in SOURCES]
    rows3.append(["6県を合わせた値", f"{total:,}", f2(A["spread"]), f2(A["null"]), f2(A["hi"]), f"{A['p'] * 100:.1f}%"])
    best = max(range(4), key=lambda i: A["means"][i])
    worst = min(range(4), key=lambda i: A["means"][i])
    if sig:
        sig_line = f"月齢をずらした場合の上位5%を超えたのは、{sig_txt}です。ただし、県を6つ並べて見ているので、偶然でも1つか2つは超えることがあります。"
    else:
        sig_line = "月齢をずらした場合の上位5%を超えた県は、ありませんでした。"
    if A["p"] < 0.05:
        all_line = f"6県を合わせた値は、ずらした場合の上位5%を超えました(ずらした場合に実際以上になった割合は{A['p'] * 100:.1f}%)。"
    else:
        all_line = f"6県を合わせた値も、ずらした場合の範囲に収まりました(ずらした場合に実際以上になった割合は{A['p'] * 100:.1f}%)。"
    bins_txt = "、".join(f"{BIN_NAMES[i]}は{f2(A['means'][i])}" for i in range(4))
    ratio = full / new if new else 0.0
    doc = {
        "slug": "moon-phase", "date": today, "data_as_of": as_of,
        "title": "満月の日は熊の記録が増えるか。月齢別に6県の記録を数えた",
        "h1": "熊(クマ)の記録は満月の前後で変わるか。月齢別の件数",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度4〜9月、{total:,}件を月齢4区分に分けました。満月の前後2日は新月の前後2日の{f2(ratio)}倍。月齢をずらした場合の範囲との比較つきです。",
        "lead": (f"満月の夜は熊が動くのか、と気になる人は多いはずです。6県の令和8年度の記録{total:,}件を、日ごとの件数に直して月齢ごとに平均しました。季節で件数が大きく変わるので、各日の件数は前後7日の平均で割って比べています。"
                 f"満月の前後2日の値は{f2(full)}、新月の前後2日は{f2(new)}でした(1.00が前後7日の平均と同じ)。月齢との関係が偶然の範囲かどうかは、月齢のずれを変えた1,000通りと比べて確かめています。"),
        "findings": [
            f"日ごとの件数を前後7日の平均で割ると、6県の平均は区分ごとに次のとおりです(1.00で平均並み)。{bins_txt}。",
            f"満月の前後2日(のべ{nf}日)は{f2(full)}、新月の前後2日(のべ{nn}日)は{f2(new)}でした。",
            f"区分どうしの差(最大−最小)は、6県を合わせて{f2(A['spread'])}。月齢のずれを1,000通りに変えた場合の平均は{f2(A['null'])}、上位5%の境目は{f2(A['hi'])}です。{all_line}",
        ],
        "sections": [
            {"h2": "月齢の4区分で、記録の件数は変わるか",
             "paragraphs": [f"令和8年度の記録のうち、4月1日から9月30日の{total:,}件を使いました。県ごとに1日あたりの件数を数え、その日の前後7日(15日間)の平均で割りました。熊の記録は春から夏へ季節で増減するため、割らずに月齢で比べると、たまたま件数の多い時期に当たった月齢が高く出てしまうからです。",
                            f"各日の月齢は、新月から数えた日数(0〜29.5)です。これを4つに分け、区分ごとに6県の値を平均しました。最も高いのは「{BIN_NAMES[best]}」の{f2(A['means'][best])}、最も低いのは「{BIN_NAMES[worst]}」の{f2(A['means'][worst])}でした。1.00は、前後7日の平均と同じ件数という意味です。",
                            "表の日数は、前後7日がそろう日だけを集計しています。"],
             "table": {"head": ["月齢の区分", "のべ日数", "件数÷前後7日の平均(6県平均)"], "rows": rows1, "note": "月齢は新月を0とした日数。計算で出した目安で、実際の月の位置と半日ほどずれることがあります。"}},
            {"h2": "県ごとに見ても同じか",
             "paragraphs": ["県別に同じ計算をすると、区分の値は次のとおりです。記録の少ない県では、1日の件数が0や1になるため、値が大きく揺れます。",
                            f"区分の差(最大−最小)は、県ごとに{f2(min(ranges))}から{f2(max(ranges))}でした。"],
             "table": {"head": ["県"] + BIN_NAMES, "rows": rows2, "note": "各区分の「件数÷前後7日の平均」の平均。"}},
            {"h2": "月齢をずらしても出る差か",
             "paragraphs": ["区分の差は、月齢と関係がなくても、日々の件数のばらつきで出ます。どこまでが偶然の範囲かを見るため、各日の月齢を同じ日数だけずらす計算を1,000回しました。ずらす日数は0〜29.5日からランダムに選びます。記録の日付は変えません。ずらした場合の区分の差の平均と、上位5%の境目を出しました。",
                            sig_line + all_line,
                            "この比べ方で分かるのは、月齢と記録の件数に、偶然では説明しにくい関係があるかどうかまでです。あったとしても、熊の動きが変わったのか、人の出歩きや見つけやすさが変わったのかは、記録からは分かりません。"],
             "table": {"head": ["県", "記録(件)", "区分の差", "ずらした場合の平均", "ずらした場合の上位5%の境目", "ずらして実際以上になった割合"], "rows": rows3, "note": "割合が5%未満のときは、月齢をずらした場合より差が大きいことになります。6県を並べているので、1県は偶然でも出ることがあります。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の4〜9月の記録では、満月の前後2日が{f2(full)}、新月の前後2日が{f2(new)}で、その差は{f2(abs(full - new))}だったことです。{all_line}",
                            "言えないのは、月齢が熊の行動を変えるか、変えないかです。記録は人が見つけて報告した件数で、昼の目撃が中心です。月明かりの影響を直接見ることはできません。1年度の半年分だけなので、ほかの年に同じ形になるかも分かりません。",
                            "月齢に関わらず、熊の出没情報は毎日変わります。お住まいの県の最新の目撃情報は県別のページで、出会わないための対処は「クマに出会わないために」のページで見られます。"]},
        ],
        "method": [
            f"対象は、令和8年度の記録のうち、4月1日から9月30日の{total:,}件です(秋田・宮城・新潟・富山・山口・山梨。日付のある記録すべて)。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "日ごとの件数は、その日の前後7日の15日間の平均で割りました。前後7日がそろわない最初と最後の7日、平均が0の日は除きます。6県の値は、日ごとに6県の値を平均してから区分ごとに平均しました。",
            f"月齢は、2000年1月7日(日本時間)の新月から、平均朔望月29.53059日で数えた計算値です(半日ほどのずれがあります)。月齢のずらしは0〜29.53日から{SHIFTS:,}回ランダムに選びました(乱数の種は固定)。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の動きや数を直接示すものではありません。",
            "記録の多くは昼間の目撃で、月明かりの直接の影響は見られません。",
            "月齢は計算した目安で、天文台の暦の値とは半日ほどずれることがあります。",
            "1年度の4〜9月だけです。県によって記録の集め方も違います。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/moon-phase.py",
        "related": [{"label": "時間帯ごとの報告(何時ごろ多いか)", "href": "/research/hour-of-day/"}, {"label": "日没後に報告された記録の割合", "href": "/research/after-sunset/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(rows1, f2(full), f2(new), nf, nn, [(k, round(res[k]['p'], 3)) for k in res], total, sig)


main()
