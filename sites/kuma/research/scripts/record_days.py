"""Research note: on how many days did a prefecture have a bear record at all?  Share of days with at least one record, longest run of days with records, longest run of days without.
(Akita, Miyagi, Niigata, Toyama, Yamaguchi, Yamanashi: the sources with 200+ records in the window; the window is 1 April to the earliest 'as of' date of the six, so every prefecture is counted over the same days.)

python sites/kuma/research/scripts/record_days.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MIN_RECORDS = 200


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def runs(days: set[date], start: date, end: date) -> tuple[tuple[int, date, date], tuple[int, date, date]]:
    """(longest run with records, longest run without), each as (length, first day, last day)."""
    best = {True: (0, start, start), False: (0, start, start)}
    cur_state, cur_start = None, start
    d = start
    while d <= end + timedelta(days=1):
        state = (d in days) if d <= end else None
        if state != cur_state:
            if cur_state is not None:
                n = (d - cur_start).days
                if n > best[cur_state][0]:
                    best[cur_state] = (n, cur_start, d - timedelta(days=1))
            cur_state, cur_start = state, d
        d += timedelta(days=1)
    return best[True], best[False]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    end = min(date.fromisoformat(s["as_of"]) for s in data.values())
    n_days = (end - common.FY_START).days + 1
    stats, rows = {}, []
    for k, label in SOURCES.items():
        dates = [(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in data[k]["rows"]]
        dates = [d for d in dates if d <= end]
        assert len(dates) >= MIN_RECORDS, k
        days = set(dates)
        with_rec, without = runs(days, common.FY_START, end)
        st = dict(records=len(dates), days=len(days), share=common.pct(len(days), n_days), run=with_rec, gap=without, per_day=round(len(dates) / len(days), 1))
        stats[k] = st
        rows.append([label, f"{st['records']:,}", f"{st['days']}日({st['share']:.0f}%)", f"{st['per_day']}件",
                     f"{with_rec[0]}日({md(with_rec[1])}〜{md(with_rec[2])})", f"{without[0]}日({md(without[1])}〜{md(without[2])})" if without[0] else "なし"])
    order = sorted(SOURCES, key=lambda k: stats[k]["share"], reverse=True)
    hi, lo = order[0], order[-1]
    total = sum(st["records"] for st in stats.values())
    as_of = max(s["as_of"] for s in data.values())
    full = [SOURCES[k] for k in SOURCES if stats[k]["days"] == n_days]
    full_text = ("、".join(full) + "は、期間のすべての日に記録がありました。") if full else "期間のすべての日に記録があった県はありません。"
    gap_k = max(SOURCES, key=lambda k: stats[k]["gap"][0])

    doc = {
        "slug": "record-days", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": f"熊(クマ)の目撃は、何日に1日の割合で記録されているか。6県の「記録のあった日」を数える",
        "h1": "熊(クマ)の目撃記録が、ある日とない日。4月から9月の「記録のあった日」を県ごとに数える",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の目撃記録{total:,}件から、4月1日〜{md(end)}のうち記録のあった日の割合と、記録が続いた日数・途切れた日数の最長を県ごとに比べました。",
        "lead": (f"件数ではなく、「日」で数えました。4月1日から{md(end)}までの{n_days}日のうち、熊(クマ)の目撃記録が1件でもあった日は、何日あるのか。"
                 "秋田県・宮城県・新潟県・富山県・山口県・山梨県の記録で、記録のあった日の割合を出します。あわせて、記録が毎日続いた最長の日数と、記録のない日が続いた最長の日数も見ます。"),
        "findings": [
            f"{n_days}日のうち記録のあった日の割合は、{SOURCES[hi]}が{stats[hi]['share']:.0f}%でいちばん大きく、{SOURCES[lo]}が{stats[lo]['share']:.0f}%でいちばん小さくなりました。",
            full_text,
            f"記録のない日が続いた最長は、{SOURCES[gap_k]}の{stats[gap_k]['gap'][0]}日間({md(stats[gap_k]['gap'][1])}〜{md(stats[gap_k]['gap'][2])})です。" if stats[gap_k]["gap"][0] else "記録のない日が続いた期間は、どの県にもありませんでした。",
        ],
        "sections": [
            {"h2": "県ごとの、記録のあった日の割合と、続いた日数",
             "paragraphs": [f"4月1日から{md(end)}までの{n_days}日を、1日ずつ見ました。その日に1件でも記録があれば「記録のあった日」です。「記録のあった日の1日あたり件数」は、記録のあった日だけで平均した件数です。"],
             "table": {"head": ["県", "件数", "記録のあった日", "記録のあった日の1日あたり件数", "記録が毎日続いた最長", "記録のない日が続いた最長"], "rows": rows,
                       "note": f"期間は6県そろえて、4月1日〜{md(end)}({n_days}日)です。それより後の記録は数えていません。"}},
            {"h2": "記録のあった日の割合の比べ方",
             "paragraphs": ["割合が大きい県ほど、期間のうち多くの日に、どこかで目撃が報告されています。"],
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [stats[k]["share"] for k in order], "title": "記録のあった日の割合(%)",
                       "desc": f"4月1日から{md(end)}までのうち、目撃記録が1件でもあった日の割合を、秋田・宮城・新潟・富山・山口・山梨の6県で比べた棒グラフ。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、{md(end)}までのものです。6県の記録の最新日が違うため、いちばん早い日にそろえました。記録が{MIN_RECORDS}件に届かない県は、日ごとの有無が偶然に左右されるため対象にしていません。",
            "日付は、公表されている記録の、目撃などがあった日の日付です。時刻は使っていません。県内のどの市町村でも、1件あればその日を「記録のあった日」と数えました。",
            "「続いた最長」は、連続する日のうち、記録のあった日(またはなかった日)がいちばん長く続いた日数です。",
        ],
        "caveats": [
            "これは「報告された記録の有無」です。記録のない日に、熊がいなかったとは言えません。通報の受け付けや公表の更新が、曜日や休日で偏ることもあります。",
            "県の広さと記録の取り方は違います。広い県ほど、どこかで記録のある日が多くなりやすく、県どうしの割合の大小は目安として見てください。",
            "令和8年度の4月から9月までの数え方です。10月以降や、ほかの年にも同じ傾向になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/record_days.py",
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
