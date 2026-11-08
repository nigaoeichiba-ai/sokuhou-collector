"""Research note: after a municipality had no bear record for 14 days, does the next record come within 14 days?  Six prefectures, one unit = one municipality-day.

python sites/kuma/research/scripts/quiet-then-again.py
"""
from __future__ import annotations

import bisect
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
WINDOW = 14
CLASSES = [("0日", lambda n: n == 0), ("1〜3日", lambda n: 1 <= n <= 3), ("4〜8日", lambda n: 4 <= n <= 8), ("9日以上", lambda n: n >= 9)]


def day(r):
    return r[0].date() if isinstance(r[0], datetime) else r[0]


def klass(n: int) -> int:
    for i, (_, f) in enumerate(CLASSES):
        if f(n):
            return i
    return 3


def new_acc():
    return {"n": 0, "hit": 0, "gaps": []}


def add(acc, hit, gap):
    acc["n"] += 1
    acc["hit"] += hit
    if gap is not None:
        acc["gaps"].append(gap)


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    by_class = [new_acc() for _ in CLASSES]
    start_pref = {k: new_acc() for k in SOURCES}
    start_month = {m: new_acc() for m in range(4, 11)}
    early, late = new_acc(), new_acc()
    first_day = common.FY_START + timedelta(days=WINDOW)
    for k, src in data.items():
        cut = date.fromisoformat(src["as_of"]) - timedelta(days=WINDOW)
        towns = defaultdict(set)
        for r in src["rows"]:
            if r[2]:
                towns[r[2]].add(day(r))
        for v in map(sorted, towns.values()):
            for i, d in enumerate(v):
                if d < first_day or d > cut:
                    continue
                lo = bisect.bisect_left(v, d - timedelta(days=WINDOW))
                c = klass(i - lo)
                nxt = v[i + 1] if i + 1 < len(v) else None
                gap = (nxt - d).days if nxt else None
                hit = 1 if gap is not None and gap <= WINDOW else 0
                add(by_class[c], hit, gap)
                if c == 0:
                    add(start_pref[k], hit, gap)
                    add(start_month[d.month], hit, gap)
                    add(early if d.month <= 6 else late, hit, gap)
    pc = lambda a: ("全件" if a["hit"] == a["n"] else f"{a['hit'] / a['n'] * 100:.0f}%") if a["n"] else "-"
    med = lambda a: f"{statistics.median(a['gaps']):.0f}日" if a["gaps"] else "-"
    ratio = lambda a: a["hit"] / a["n"] * 100 if a["n"] else 0.0
    base = by_class[0]
    total_units = sum(a["n"] for a in by_class)
    names = list(SOURCES)
    ok = [k for k in names if start_pref[k]["n"] >= 30]
    hi = max(ok, key=lambda k: ratio(start_pref[k]))
    lo = min(ok, key=lambda k: ratio(start_pref[k]))
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    months = [m for m in range(4, 11) if start_month[m]["n"] > 0]
    rows1 = [[lab, f"{a['n']:,}", f"{a['hit']:,}", pc(a), med(a)] for (lab, _), a in zip(CLASSES, by_class)]
    rows2 = [[SOURCES[k], f"{start_pref[k]['n']}", f"{start_pref[k]['hit']}", pc(start_pref[k]), med(start_pref[k])] for k in names]
    rows3 = [[f"{m}月", f"{start_month[m]['n']}", f"{start_month[m]['hit']}", pc(start_month[m])] for m in months]
    long_after = sum(1 for g in base["gaps"] if g > 30)
    no_next = base["n"] - len(base["gaps"])
    cuts = [(0, 3), (4, 7), (8, 14), (15, 30)]
    g = base["gaps"]
    rows5 = [[f"{a}〜{b}日" if a else f"{b}日以内", f"{sum(1 for x in g if a <= x <= b)}", f"{sum(1 for x in g if a <= x <= b) / base['n'] * 100:.0f}%"] for a, b in cuts]
    rows5[0][0] = "3日以内"
    rows5 += [["31日以降", f"{long_after}", f"{long_after / base['n'] * 100:.0f}%"], ["年度内に次の記録なし", f"{base['n'] - len(g)}", f"{(base['n'] - len(g)) / base['n'] * 100:.0f}%"]]
    cum = [sum(1 for x in g if x <= w) for w in (3, 7, 14)]
    rows4 = [["4〜6月", f"{early['n']}", f"{early['hit']}", pc(early), med(early)], ["7〜10月", f"{late['n']}", f"{late['hit']}", pc(late), med(late)]]
    desc = (f"6県の令和8年度で、14日間記録のなかった市町村に熊の記録が出た{base['n']}件のうち、その後14日以内にまた記録が出たのは{ratio(base):.0f}%でした。"
            f"4〜6月は{ratio(early):.0f}%、7〜10月は{ratio(late):.0f}%です。")
    doc = {
        "slug": "quiet-then-again", "date": today, "data_as_of": as_of,
        "title": "熊の記録が久しぶりに出た市町村では、2週間以内にまた出たか",
        "h1": "久しぶりに熊(クマ)の記録が出た市町村で、2週間以内にまた出たか",
        "description": desc,
        "lead": (f"その市町村で2週間ぶりに熊の記録が出たとき、続けてまた出るのでしょうか。6県の令和8年度の記録で、直前の14日間に記録がなかった日を{base['n']}件数えると、"
                 f"その後14日以内に同じ市町村でまた記録が出たのは{base['hit']}件、{ratio(base):.0f}%でした。県別では{SOURCES[lo]}の{ratio(start_pref[lo]):.0f}%から{SOURCES[hi]}の{ratio(start_pref[hi]):.0f}%まで開きがあり、"
                 f"4〜6月は{ratio(early):.0f}%、7〜10月は{ratio(late):.0f}%と、夏の終わりに向かって下がっています。"),
        "findings": [
            f"直前14日間に記録のなかった市町村の日(以下「久しぶりの日」)は6県で{base['n']}件ありました。そのうち{base['hit']}件({ratio(base):.0f}%)は、その後14日以内に同じ市町村でまた記録が出ています。次の記録までの日数の中央値は{med(base)}です。",
            f"直前14日間に記録のあった日が1〜3日の市町村では{pc(by_class[1])}、4〜8日では{pc(by_class[2])}、9日以上では{pc(by_class[3])}でした。記録が続いている市町村ほど、その後14日以内にも記録が出ています。",
            f"「久しぶりの日」の後にまた記録が出た割合は、{SOURCES[hi]}が{pc(start_pref[hi])}、{SOURCES[lo]}が{pc(start_pref[lo])}でした(30件以上の県のみ)。月別では4月{pc(start_month[4])}、5月{pc(start_month[5])}、6月{pc(start_month[6])}、7月{pc(start_month[7])}、8月{pc(start_month[8])}です。",
        ],
        "sections": [
            {"h2": "直前の2週間に記録がなかった日を探す",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録を、市町村ごと、日ごとにまとめました。同じ日に同じ市町村で何件あっても1日として数えています。その上で、ある市町村のある日について、その日より前の14日間に同じ市町村の記録がなかった日を「久しぶりの日」と呼びました。",
                            f"6県で{total_units:,}の市町村の日が数えられ、「久しぶりの日」は{base['n']}件でした。4月1日から13日までの日は、直前の14日間の記録が手元にないので入れていません。記録の最新日から14日以内の日も、その後の14日間が終わっていないので入れていません。",
                            f"それぞれの日について、その後14日以内に同じ市町村でまた記録があったかを調べました。「久しぶりの日」{base['n']}件のうち、あったのは{base['hit']}件で、{ratio(base):.0f}%です。なかったのは{base['n'] - base['hit']}件で、その内訳は、15日以降に次の記録が出た日が{len(base['gaps']) - base['hit']}件、年度の最後の記録まで出なかった日が{no_next}件です。"],
             "table": {"head": ["直前14日間に記録のあった日", "市町村の日の数", "その後14日以内にまた記録", "割合", "次の記録までの日数(中央値)"], "rows": rows1,
                       "note": "「0日」が「久しぶりの日」です。次の記録までの日数は、年度内に次の記録が出た日だけの中央値です。"}},
            {"h2": "記録が続いている市町村ほど、その後も続く",
             "paragraphs": [f"直前14日間に記録のあった日が多いほど、その後14日以内にまた記録が出る割合は上がります。1〜3日の市町村では{pc(by_class[1])}、4〜8日では{pc(by_class[2])}、9日以上では{pc(by_class[3])}でした。",
                            f"2週間ぶりに出た市町村の{ratio(base):.0f}%という数字は、すでに記録が続いている市町村(直前14日間に4日以上)の{ratio(by_class[2]):.0f}%以上より、はっきり低くなっています。残りの{100 - ratio(base):.0f}%は、その後の2週間、同じ市町村で記録が出ませんでした。",
                            "記録が続いている市町村の割合が高いのは、ほぼ当然でもあります。直前の2週間のうち9日以上に記録があれば、翌日以降にも記録が出る可能性が高いからです。このノートで知りたいのは、数字の高い側ではなく、「久しぶりの日」の58%が、どの程度の目安になるかです。",
                            "ただし、静かな時期が続いた後の1件が、そのまま次の流れの始まりになるとは限りません。この数え方では、1件だけで終わる場合と、続く場合を、前もって見分けることはできません。"]},
            {"h2": "県によって、久しぶりの記録の後の続き方は違う",
             "paragraphs": [f"「久しぶりの日」を県別に分けると、その後14日以内にまた記録が出た割合は、{SOURCES[hi]}が{pc(start_pref[hi])}({start_pref[hi]['hit']}/{start_pref[hi]['n']}件)で最も高くなりました。最も低かったのは{SOURCES[lo]}で、{pc(start_pref[lo])}({start_pref[lo]['hit']}/{start_pref[lo]['n']}件)でした。",
                            f"県の中の市町村の数や、1市町村あたりの記録の数も違います。「久しぶりの日」は、{'、'.join(f'{SOURCES[k]}{start_pref[k]['n']}件' for k in names)}でした。",
                            "県によって、記録を集める範囲や、市町村の数、報告の出し方が違います。割合の差が熊の動き方の違いなのか、記録の集め方の違いなのかは、このデータでは分けられません。件数の少ない県は、1件の違いで割合が大きく動きます。"],
             "table": {"head": ["県", "久しぶりの日", "その後14日以内にまた記録", "割合", "次の記録までの日数(中央値)"], "rows": rows2,
                       "note": "「久しぶりの日」は、直前14日間に同じ市町村の記録がなかった日です。"}},
            {"h2": "月別では、春は続きやすく、夏の終わりは続きにくい",
             "paragraphs": [f"「久しぶりの日」を月別に見ると、4月は{pc(start_month[4])}、5月は{pc(start_month[5])}、6月は{pc(start_month[6])}で、7月は{pc(start_month[7])}、8月は{pc(start_month[8])}と下がります。4〜6月をまとめると{pc(early)}({early['hit']}/{early['n']}件)、7〜10月は{pc(late)}({late['hit']}/{late['n']}件)です。",
                            f"6月までは7割前後だった割合が、7月以降は{pc(start_month[8])}から{pc(start_month[7])}の間に下がりました。夏の後半は、2週間ぶりに記録が出た後、そのまま静かになる市町村が増えています。記録の最新日に近い日は数えないようにしてあるので、年度末に近いことの影響は受けていません。",
            f"次の記録までの日数は、4〜6月は中央値{med(early)}、7〜10月は{med(late)}と、後半のほうが長くなっています。",
                            f"10月は{start_month[10]['n']}件と少ないため、ほかの月との比較には使えません。月別の割合の差が、熊の動きによるものか、記録の入力の時期によるものかは、ここからは言えません。"],
             "table": {"head": ["月", "久しぶりの日", "その後14日以内にまた記録", "割合"], "rows": rows3,
                       "note": "4月は15日以降の日のみです。月は「久しぶりの日」の月です。"}},
            {"h2": "4〜6月と7〜10月でまとめて比べる",
             "paragraphs": [f"4〜6月と7〜10月でまとめると、その後14日以内にまた記録が出た割合は{pc(early)}と{pc(late)}です。次の記録までの日数の中央値は、4〜6月が{med(early)}、7〜10月が{med(late)}でした。",
                            f"春は、{early['n']}件のうち{sum(1 for g in early['gaps'] if g <= 7)}件({sum(1 for g in early['gaps'] if g <= 7) / early['n'] * 100:.0f}%)が1週間以内に次の記録を出しています。夏の後半から秋は、{late['n']}件のうち{sum(1 for g in late['gaps'] if g <= 7)}件({sum(1 for g in late['gaps'] if g <= 7) / late['n'] * 100:.0f}%)です。"],
             "table": {"head": ["時期", "久しぶりの日", "その後14日以内にまた記録", "割合", "次の記録までの日数(中央値)"], "rows": rows4,
                       "note": "4〜6月は4月15日から、7〜10月は記録の最新日の14日前までです。"}},
            {"h2": "次の記録までの日数の内訳",
             "paragraphs": [f"「久しぶりの日」{base['n']}件を、次の記録までの日数で分けました。{rows5[0][1]}件が3日以内、1週間以内までで{cum[1]}件({cum[1] / base['n'] * 100:.0f}%)、2週間以内までで{cum[2]}件({cum[2] / base['n'] * 100:.0f}%)です。1か月を超えてから次の記録が出た日は{long_after}件、年度内に次の記録が出なかった日は{no_next}件でした。",
                            f"{100 - cum[2] / base['n'] * 100:.0f}%の日は、2週間たっても次の記録がありません。2週間ぶりに記録が出たからといって、出没が続くと見込むのは、数字の上では早すぎます。一方で、{cum[2] / base['n'] * 100:.0f}%の日は2週間以内に続報が出ているため、1件だけで終わると決めてしまうのも、数字とは合いません。"],
             "table": {"head": ["次の記録まで", "「久しぶりの日」の数", "全体に対する割合"], "rows": rows5,
                       "note": "日数は、「久しぶりの日」から、同じ市町村で次に記録のあった日までの差です。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、記録が出た市町村では、その前の2週間の記録の多さが、その後2週間の記録の出やすさと並んでいることです。久しぶりに出た場合でも、{pc(base)}は2週間以内にまた記録が出ています。",
                            "言えないのは、2週間ぶりの記録が出た市町村で、その後も熊が居続けているかどうかです。記録は報告された件数で、熊の数や行動を直接測ったものではありません。また、記録のない期間が、本当に出没のない期間だったかどうかも、このデータからは分かりません。",
                            "お住まいの市町村で久しぶりに出没情報があったときは、その後2週間のうちに続報が出るかどうかを、自治体の発表で確かめてください。このノートの割合は、目安の一つです。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録です。秋田・宮城・新潟・富山・山口・山梨の6県で、記録の最新日は秋田県が{data['akita']['as_of']}、宮城県が{data['miyagi']['as_of']}などです。計算した日は{today}、使った記録の最新日は{as_of}です。",
            f"同じ日に同じ市町村で何件あっても、1つの「市町村の日」として数えました。直前{WINDOW}日間(その日を含まない)に同じ市町村の記録のあった日の数で、4つに分けています。「久しぶりの日」は、これが0日の日です。",
            f"4月1日から{WINDOW - 1}日までの日は、直前の{WINDOW}日間が年度の前にかかるため、入れていません。各県の記録の最新日から{WINDOW}日以内の日も、その後の{WINDOW}日間が終わっていないため、入れていません。",
            "次の記録までの日数は、年度内に次の記録が出た日だけの中央値です。市町村の名前は、記録に付いている名称そのままです。県によって、市町村の区切り方・記録の集め方が違います。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や、市町村に熊が居続けているかを直接示すものではありません。",
            "「記録がなかった期間」は、熊が出なかった期間とは限りません。報告されなかった、まだ記録に入っていない、ということもあります。",
            "県ごとに記録の集め方・市町村の区切り方が違うため、県どうしの割合の大小は、そのまま比べられません。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/quiet-then-again.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
