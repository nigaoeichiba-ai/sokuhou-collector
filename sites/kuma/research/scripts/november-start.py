"""Research note: do the bear records keep falling into November?  Five-day blocks from Oct 7 to Nov 5 in the four prefectures whose data reach November.

python sites/kuma/research/scripts/november-start.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, datetime, timedelta
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"miyagi": "宮城県", "yamaguchi": "山口県", "yamanashi": "山梨県", "toyama": "富山県"}
FIRST = date(2026, 10, 7)
N_BLOCKS = 6                                   # 6 blocks of 5 days: Oct 7-11 ... Nov 1-5
BLOCK_DAYS = 5
LAST_DAY = FIRST + timedelta(days=BLOCK_DAYS * N_BLOCKS - 1)   # 2026-11-05


def two_sided_p(a: int, b: int) -> float:
    """Exact two-sided binomial p: if the two periods had the same expected count, how often is a split at least this uneven?"""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def label(i: int) -> str:
    s = FIRST + timedelta(days=BLOCK_DAYS * i)
    e = s + timedelta(days=BLOCK_DAYS - 1)
    return f"{s.month}月{s.day}日〜{e.day}日" if s.month == e.month else f"{s.month}月{s.day}日〜{e.month}月{e.day}日"


def fp(p: float, d: int = 3) -> str:
    return "0.001未満" if p < 0.001 else f"{p:.{d}f}"


def pct(x: float) -> str:
    return f"{x:.0f}%"


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    counts = {}
    for k, s in data.items():
        c = Counter()
        for r in s["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if FIRST <= d <= LAST_DAY:
                c[(d - FIRST).days // BLOCK_DAYS] += 1
        counts[k] = [c[i] for i in range(N_BLOCKS)]
    total = [sum(counts[k][i] for k in SOURCES) for i in range(N_BLOCKS)]
    as_of = min(s["as_of"] for s in data.values())
    as_of_max = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()

    rows1 = [[label(i)] + [f"{counts[k][i]:,}" for k in SOURCES] + [f"{total[i]:,}"] for i in range(N_BLOCKS)]
    head1 = ["期間(5日ごと)"] + [SOURCES[k] for k in SOURCES] + ["4県の合計"]

    def comp(a_idx: int, b_idx: int, k: str | None = None):
        a = total[a_idx] if k is None else counts[k][a_idx]
        b = total[b_idx] if k is None else counts[k][b_idx]
        return a, b, (b / a * 100 if a else 0.0), two_sided_p(a, b)

    rows2 = []
    for k in list(SOURCES) + [None]:
        a, b, ratio, p = comp(0, 5, k)
        a2, b2, ratio2, p2 = comp(4, 5, k)
        rows2.append([SOURCES[k] if k else "4県の合計", f"{a:,}", f"{b:,}", pct(ratio), fp(p), f"{a2:,}", f"{b2:,}", fp(p2, 2)])
    head2 = ["県", "10月7〜11日", "11月1〜5日", "11月1〜5日は10月7〜11日の何%か", "偶然のずれの確率(p)", "10月27〜31日", "11月1〜5日", "偶然のずれの確率(p)"]

    t_first, t_last, t_ratio, t_p = comp(0, 5)
    _, _, _, t_p_prev = comp(4, 5)
    low_i = min(range(N_BLOCKS), key=lambda i: total[i])
    mid_i = [i for i in range(2, N_BLOCKS)]
    late = total[3:]
    late_min, late_max = min(late), max(late)
    sub = [k for k in ("miyagi", "yamaguchi")]
    sub_first = sum(counts[k][0] for k in sub)
    sub_last = sum(counts[k][5] for k in sub)
    sub_p = two_sided_p(sub_first, sub_last)
    ym = counts["yamanashi"]
    ym_min, ym_max = min(ym), max(ym)
    ym_first, ym_last = ym[0], ym[5]
    to = counts["toyama"]
    n_all = sum(total)

    # records on the days up to as_of: how many days at the end of the window have no record in the prefecture (to judge late entries)
    zero_days = {}
    for k, s in data.items():
        days = {(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in s["rows"]}
        zero_days[k] = sum(1 for i in range(BLOCK_DAYS * N_BLOCKS) if (FIRST + timedelta(days=i)) not in days)

    active = {k: [0] * N_BLOCKS for k in SOURCES}
    for k, s in data.items():
        days = {(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in s["rows"]}
        for d in days:
            if FIRST <= d <= LAST_DAY:
                active[k][(d - FIRST).days // BLOCK_DAYS] += 1
    rows3 = [[label(i)] + [f"{active[k][i]}日" for k in SOURCES] for i in range(N_BLOCKS)]
    head3 = ["期間(5日ごと)"] + [SOURCES[k] for k in SOURCES]
    mi_act, ya_act = active["miyagi"], active["yamaguchi"]

    desc = (f"宮城・山口・山梨・富山の令和8年度の熊の記録のうち、10月7〜11日は4県で{t_first}件、11月1〜5日は{t_last}件でした。"
            f"宮城と山口は{sub_first}件から{sub_last}件へ減り、山梨は{ym_first}件から{ym_last}件で減っていません。")

    doc = {
        "slug": "november-start", "date": today, "data_as_of": as_of_max,
        "title": "11月に入って、熊の記録は減り続けているか",
        "h1": "11月に入って、熊(クマ)の記録は減り続けているか",
        "description": desc,
        "lead": (f"熊の記録が秋に減っていく話は、よく聞きます。では11月に入ると、さらに減るのでしょうか。宮城・山口・山梨・富山の4県で、10月7日から11月5日までを5日ごとの6つに区切り、件数を集計しました。"
                 f"4県の合計は{' → '.join(str(v) for v in total)}件でした。10月の前半から下旬にかけて{total[0]}件から{total[3]}件まで減りました。そのあとの3つの期間は{late_min}〜{late_max}件で、ほぼ横ばいです。"
                 f"県別に見ると、宮城・山口は減り、山梨は減っていません。11月の最初の5日間に、記録が急に消えたわけではありませんでした。"),
        "findings": [
            f"4県の記録は、10月7〜11日の{t_first}件から、10月22〜26日の{total[3]}件まで減りました。そのあとの10月27〜31日は{total[4]}件、11月1〜5日は{total[5]}件で、{late_min}〜{late_max}件の間にとどまります。",
            f"宮城県は10月7〜11日の{counts['miyagi'][0]}件から11月1〜5日の{counts['miyagi'][5]}件へ、山口県は{counts['yamaguchi'][0]}件から{counts['yamaguchi'][5]}件へ減りました。2県を合わせると{sub_first}件から{sub_last}件で、偶然のずれとして説明できる確率は{fp(sub_p)}です。",
            f"山梨県は5日ごとに{ym_min}〜{ym_max}件で、10月7〜11日の{ym_first}件に対して11月1〜5日は{ym_last}件でした。減る県と減らない県が混ざっているので、4県の合計だけでは動きを読み違えます。",
        ],
        "sections": [
            {"h2": "10月7日から11月5日までを、5日ごとに数える",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、11月まで記録が届いているのは、宮城県・山口県・山梨県・富山県の4県です。使った記録の最新日は、県によって{as_of}から{as_of_max}までです。秋田県は9月末まで、新潟県は11月2日までなので、ここでは入れていません。",
                            f"最新の日は、あとから記録が足されることがあります。そこで、記録がそろっていると考えられる11月5日までを区切りにして、10月7日から11月5日までの30日間を5日ごとの6つに分けました。4県の合計は{n_all:,}件です。",
                            f"4県の合計は、{' → '.join(f'{v}件' for v in total)}です。10月前半の2つの期間({total[0]}件・{total[1]}件)から、10月の中ごろ({total[2]}件)、下旬({total[3]}件)へと減りました。10月27〜31日は{total[4]}件、11月1〜5日は{total[5]}件でした。"],
             "table": {"head": head1, "rows": rows1, "note": "各期間の日付は、記録に書かれた日付です。5日ごとに区切っています。"}},
            {"h2": "11月の最初の5日間は、10月の前半や直前と比べてどうか",
             "paragraphs": [f"11月1〜5日の4県の合計{t_last}件は、10月7〜11日の{t_first}件の{pct(t_ratio)}です。直前の10月27〜31日の{total[4]}件とは、{abs(total[5] - total[4])}件の差でした。この2つの期間の差が偶然のずれの範囲に入る確率は{t_p_prev:.2f}で、11月に入って急に増えた、あるいは急に減った、とは言えません。",
                            f"県別では、宮城県は10月7〜11日の{counts['miyagi'][0]}件に対して11月1〜5日は{counts['miyagi'][5]}件、山口県は{counts['yamaguchi'][0]}件に対して{counts['yamaguchi'][3 + 2]}件です。この2県は10月7〜11日に比べて、記録が大きく減っています。一方、山梨県は{ym_first}件に対して{ym_last}件、富山県は{to[0]}件に対して{to[5]}件でした。山梨県と富山県は、10月7〜11日と11月1〜5日の間に大きな差がありません。",
                            "「偶然のずれの確率」は、2つの期間の記録の数が本来は同じだったとして、記録の合計をどちらの期間に入れるかを偶然だけで決めたとき、これ以上に偏る確率です。小さいほど、偶然とは考えにくくなります。"],
             "table": {"head": head2, "rows": rows2, "note": "確率は、2つの期間の件数の合計を、同じ確率で2つの期間に振り分けたときの両側の確率(二項分布)です。"}},
            {"h2": "宮城・山口は減り、山梨は減らない",
             "paragraphs": [f"宮城県は{' → '.join(str(v) for v in counts['miyagi'])}件、山口県は{' → '.join(str(v) for v in counts['yamaguchi'])}件です。10月の前半から下旬にかけて減り、そのあとは小さな数字の間で動いています。2県を合わせた10月7〜11日と11月1〜5日の差は、偶然のずれの確率で{fp(sub_p)}です。",
                            f"山梨県は{' → '.join(str(v) for v in ym)}件で、10月の前半から11月の最初の5日間まで、{ym_min}〜{ym_max}件の間にあります。山梨県の記録が少ない期間は、10月7〜11日の{ym_first}件でした。同じ時期でも、県によって動きがそろわないことが、この集計からうかがえます。",
                            f"富山県は{' → '.join(str(v) for v in to)}件で、どの期間も数件です。件数が少ないので、増えたか減ったかを読み取るのは難しい状態です。"]},
            {"h2": "記録のある日は、何日あるか",
             "paragraphs": ["件数だけでなく、記録のあった日の数も、5日ごとに集計しました。件数が多い日が1日あっても、ほかの日に記録がなければ、その期間は出没の記録が散らばっていないことになります。反対に、毎日1件ずつ出ているなら、件数が少なくても、記録は途切れていません。",
                            f"宮城県は、5日のうち記録のあった日が{' → '.join(str(v) for v in mi_act)}日と動き、山口県は{' → '.join(str(v) for v in ya_act)}日と動きました。山梨県は{' → '.join(str(v) for v in active['yamanashi'])}日です。",
                            f"富山県は{' → '.join(str(v) for v in active['toyama'])}日で、もともと件数が少ない県です。5日間の件数がゼロの期間と数件の期間の差は、数字では大きく見えても、偶然のずれの範囲に入りやすくなります。"],
             "table": {"head": head3, "rows": rows3, "note": "5日のうち、記録が1件以上あった日の数です。最大は5日です。"}},
            {"h2": "減る県と、減らない県が混ざるのはなぜか",
             "paragraphs": ["記録が減る理由は、このデータからは分かりません。熊の行動が変わった可能性もありますし、報告する人・出かける人の数が変わった可能性もあります。県による記録の集め方の違いも関わる可能性があります。",
                            "ほかの研究ノートでは、記録の動きが県ごとに違うことを何度か確かめています。たとえば、10月の前半と後半を比べたノートでは、宮城県は減り、山梨県は増えていました。このノートの数字は、その結果と同じ向きです。",
                            "県の合計を作ると、記録の多い県の動きに引っ張られます。宮城県は10月7〜11日の件数が多いので、4県の合計の形は、宮城県の形に近くなります。住んでいる県の動きを知りたいときは、その県の最新の記録を見るほうが確かです。"]},
            {"h2": "この数字を、身の回りの判断にどう使うか",
             "paragraphs": ["「秋が深まれば、熊の記録は減る」という話は、4県の合計では、10月の前半から下旬にかけて当てはまります。ただし、山梨県のように、10月の初めから11月の初めまで同じ程度の件数が続く県もあります。",
                            "お住まいの県の記録が減っていても、ゼロになったわけではありません。山に近い場所に出かけるときの備えは、季節の終わりを決めずに、その県の直近の記録を見て考えるのが無難です。",
                            "県の合計や、全国の傾向は、その県のいまの状況とは別のものです。このノートの数字も、4県の10月7日から11月5日までを区切った結果で、ほかの県に当てはめることはできません。"]},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、4県の記録が10月7〜11日の{t_first}件から10月22〜26日の{total[3]}件まで減り、そのあとの11月5日まで{late_min}〜{late_max}件で動いたことです。宮城・山口は減り、山梨は減っていません。",
                            "言えないのは、11月の中旬以降にどうなるか、そして記録が減った理由です。11月5日までの数字から、これからの記録の数を予測することはできません。熊が冬眠に入った、と決めることもできません。",
                            "11月に入っても、熊の記録は続いています。お住まいの県の最新の記録は、自治体の発表で確認してください。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、11月まで記録が届いている宮城・山口・山梨・富山の4県です。計算した日は{today}、使った記録の最新日は県によって{as_of}から{as_of_max}までです。",
            f"区切りは、記録に書かれた日付です。10月7日から11月5日までの30日間を、5日ごとの6つに分けました。最新の日は記録があとから足されることがあるので、11月5日までにしています。30日のうち記録のない日は、宮城{zero_days['miyagi']}日・山口{zero_days['yamaguchi']}日・山梨{zero_days['yamanashi']}日・富山{zero_days['toyama']}日です。",
            "2つの期間の比較は、2つの期間の件数の合計が、同じ確率で2つの期間に入ると考えたときの、両側の二項確率です。ずれが偶然の範囲かどうかの目安であって、減った理由を示すものではありません。",
            "秋田県は9月末まで、新潟県は11月2日までの記録なので入れていません。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の数です。熊の数や、人里に出た熊の実際の数を示すものではありません。",
            "最新の日は、記録があとから足されることがあります。数日たつと、11月の件数が増える場合があります。",
            "4県だけで、5日ごとの件数が少ない県(富山県など)は、増減を読み取りにくくなります。ほかの県の動きは、この記録だけでは言えません。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/november-start.py",
        "related": [{"label": "10月の後半は前半より減ったか", "href": "/research/october-halves/"}, {"label": "10月にも記録があった市町村の割合", "href": "/research/october-towns/"},
                    {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
