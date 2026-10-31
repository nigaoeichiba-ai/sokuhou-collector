"""Research note: by what date had half of the April-September bear records been reported?  Six prefectures, the day the running total passed 25 / 50 / 75 / 90 percent of the 1 April - 30 September records.
Reference: the calendar midpoint of the period (1 July).  October records are shown next to the total, not mixed into it.

python sites/kuma/research/scripts/half-by-date.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
START, END, OCT1 = date(2026, 4, 1), date(2026, 9, 30), date(2026, 10, 1)
MID, JUN15 = date(2026, 7, 1), date(2026, 6, 16)
LEVELS = (25, 50, 75, 90)


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def reach(days: list[date], pct: int) -> date:
    need = -(-len(days) * pct // 100)          # ceil
    return days[need - 1]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    st = {}
    for k, src in data.items():
        every = sorted(r[0].date() if isinstance(r[0], datetime) else r[0] for r in src["rows"])
        days = [d for d in every if START <= d <= END]
        st[k] = dict(n=len(days), oct=sum(1 for d in every if d >= OCT1), at={p: reach(days, p) for p in LEVELS},
                     first_half=sum(1 for d in days if d < MID), jun=sum(1 for d in days if d < JUN15))
        st[k]["half_day"] = (st[k]["at"][50] - START).days + 1
    total = sum(s["n"] for s in st.values())
    before_mid = [k for k in SOURCES if st[k]["at"][50] < MID]
    order = sorted(SOURCES, key=lambda k: st[k]["half_day"])
    early, late = order[0], order[-1]
    as_of = max(s["as_of"] for s in data.values())
    oct_keys = [k for k in SOURCES if data[k]["as_of"] >= "2026-10-28"]
    rows = [[SOURCES[k], f"{st[k]['n']:,}"] + [md(st[k]["at"][p]) for p in LEVELS] for k in SOURCES]
    first_rows = [[SOURCES[k], f"{st[k]['first_half']:,}", f"{common.pct(st[k]['first_half'], st[k]['n']):.0f}%", f"{common.pct(st[k]['jun'], st[k]['n']):.0f}%"] for k in SOURCES]
    oct_rows = [[SOURCES[k], f"{st[k]['n']:,}", f"{st[k]['oct']:,}", f"{common.pct(st[k]['oct'], st[k]['n']):.0f}%", md(date.fromisoformat(data[k]["as_of"]))] for k in oct_keys]
    spread = (st[late]["at"][50] - st[early]["at"][50]).days
    by90 = sorted(SOURCES, key=lambda k: st[k]["at"][90])
    fh = {k: st[k]["first_half"] / st[k]["n"] for k in SOURCES}
    hi, lo = max(fh, key=fh.get), min(fh, key=fh.get)
    gap = lambda k, a, b: (st[k]["at"][b] - st[k]["at"][a]).days
    span = {k: gap(k, 25, 75) for k in SOURCES}
    mshort, mlong = min(span, key=span.get), max(span, key=span.get)
    span_rows = [[SOURCES[k], f"{gap(k, 25, 50)}日", f"{gap(k, 50, 75)}日", f"{span[k]}日"] for k in SOURCES]
    over20 = [k for k in oct_keys if st[k]["oct"] / st[k]["n"] > 0.2]

    doc = {
        "slug": "half-by-date", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃記録は、4〜9月の半分がいつまでに出たか。6県で日付を比べる",
        "h1": "熊(クマ)の目撃記録の半分は、いつまでに報告されたか。4〜9月の累計で6県を比べる",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の記録{total:,}件で、4〜9月の累計が半分に達した日を比べました。{SOURCES[early]}は{md(st[early]['at'][50])}、{SOURCES[late]}は{md(st[late]['at'][50])}です。",
        "lead": (f"熊の目撃は、夏から秋にかけて多いというイメージがあります。ところが、4月1日から9月30日までの記録を日付順に積み上げると、累計が半分に達するのは{md(st[early]['at'][50])}から{md(st[late]['at'][50])}の間でした。"
                 f"期間の真ん中の7月1日より前に半分に達した県は、6県のうち{len(before_mid)}県です。6県の記録{total:,}件で、累計が25%、50%、75%、90%に達した日を数えました。"),
        "findings": [
            f"4〜9月の累計が半分に達した日は、{'、'.join(f'{SOURCES[k]}{md(st[k]['at'][50])}' for k in order)}の順でした。{SOURCES[early]}と{SOURCES[late]}で{spread}日の差があります。",
            f"期間の真ん中は7月1日です。この日より前に半分に達したのは{'・'.join(SOURCES[k] for k in before_mid)}の{len(before_mid)}県で、記録が前半に寄っています。"
            + (f"{'・'.join(SOURCES[k] for k in SOURCES if k not in before_mid)}は7月に入ってから半分に達しました。" if len(before_mid) < 6 else ""),
            f"90%に達した日は、早い順に{'、'.join(f'{SOURCES[k]}{md(st[k]['at'][90])}' for k in by90)}です。県によって、後半の記録の積み上がり方が違います。",
        ],
        "sections": [
            {"h2": "累計が25%・50%・75%・90%に達した日",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、4月1日から9月30日までの{total:,}件を、報告された日の順に並べました。県ごとに、全体の25%、50%、75%、90%に届く件が出た日を調べています。記録が9月30日までの秋田県にそろえて、6県とも9月30日で区切りました。",
                            f"半分に達した日が最も早いのは{SOURCES[early]}の{md(st[early]['at'][50])}(4月1日から数えて{st[early]['half_day']}日目)、最も遅いのは{SOURCES[late]}の{md(st[late]['at'][50])}({st[late]['half_day']}日目)です。期間の真ん中にあたる7月1日は{(MID - START).days + 1}日目です。"],
             "table": {"head": ["県", "記録件数", "25%に達した日", "50%に達した日", "75%に達した日", "90%に達した日"], "rows": rows,
                       "note": "記録件数は、4月1日から9月30日までの合計です。「達した日」は、日付の順に記録を数えて、その割合に届いた記録の日付です。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [st[k]["half_day"] for k in order],
                       "title": "累計が半分に達するまでの日数(4月1日から数えた日目)",
                       "desc": "4月1日から9月30日の記録の累計が半分に達した日を、4月1日から数えた日数で6県比べた棒グラフ。"}},
            {"h2": "前半(4〜6月)と後半(7〜9月)の記録",
             "paragraphs": ["期間を7月1日で前後に分けて、前半に入る記録の割合を出しました。4〜6月は91日、7〜9月は92日で、日数はほぼ同じです。日数が同じなのに記録が前半に寄っているかどうかを見る目安になります。",
                            f"前半の割合が最も高いのは{SOURCES[hi]}で{common.pct(st[hi]['first_half'], st[hi]['n']):.0f}%、最も低いのは{SOURCES[lo]}で{common.pct(st[lo]['first_half'], st[lo]['n']):.0f}%でした。右の列は、6月15日までの割合です。春から初夏の2.5か月で、4〜9月の記録のどれだけが出ているかを示します。"],
             "table": {"head": ["県", "4〜6月の記録", "4〜9月に占める割合", "6月15日までの割合"], "rows": first_rows, "note": "4〜6月は4月1日から6月30日、6月15日までは4月1日から6月15日の記録です。"}},
            {"h2": "記録の中ほどの半分は、何日に集まったか",
             "paragraphs": [f"累計が25%に達した日から75%に達した日までの間に、記録の半分が入ります。この期間の長さは、記録が短い間にまとまって出たのか、長く続いたのかの目安になります。短い県は{SOURCES[mshort]}の{span[mshort]}日、長い県は{SOURCES[mlong]}の{span[mlong]}日でした。",
                            f"{SOURCES[mshort]}は{md(st[mshort]['at'][25])}から{md(st[mshort]['at'][75])}まで、{SOURCES[mlong]}は{md(st[mlong]['at'][25])}から{md(st[mlong]['at'][75])}までです。件数が最も多い秋田県は{span['akita']}日、宮城県は{span['miyagi']}日でした。"],
             "table": {"head": ["県", "25%から50%まで", "50%から75%まで", "25%から75%まで"], "rows": span_rows, "note": "日数は、達した日と達した日の間の日数です。"}},
            {"h2": "10月の記録は、4〜9月の累計にどれだけ足されているか",
             "paragraphs": ["ここまでの数字は9月30日で区切っています。10月の記録は、別に数えました。対象は、最新の記録の日が10月28日以降の5県です。秋田県は記録が9月30日までのため入れていません。10月1日から最新日までの件数を、4〜9月の件数と並べました。",
                            "最新の日が県ごとに数日ずれているので、割合の差には、その日数の違いと、記録の入力が済んでいない分が含まれます。"],
             "table": {"head": ["県", "4〜9月の記録", "10月の記録", "4〜9月に対する割合", "最新の記録の日"], "rows": oct_rows, "note": "10月の記録は、10月1日から最新の記録の日までの件数です。まだ記録の追加が続いている県があります。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"6県とも、記録は春から初夏にかけて積み上がり、半分に達する日が7月上旬までにあります。「熊の目撃は秋に集中する」という見方は、令和8年度の4〜9月の、この6県の記録では当てはまりません。6県のうち{len(before_mid)}県では、4〜9月の記録の半分が6月末までに出ています。" + (f"10月の記録は別にあり、{'・'.join(SOURCES[k] for k in over20)}では4〜9月の記録の2割を超えています。" if over20 else ""),
                            f"{SOURCES[late]}は半分に達した日が{md(st[late]['at'][50])}で、次に遅い{SOURCES[order[-2]]}({md(st[order[-2]]['at'][50])})より{(st[late]['at'][50] - st[order[-2]]['at'][50]).days}日あとです。90%に達した日が最も遅いのは{SOURCES[by90[-1]]}の{md(st[by90[-1]]['at'][90])}で、この県は夏から秋まで記録の積み上がりが続きました。",
                            "ただし、半分に達した日が早いことは、その県で熊が多いことも、これから減ることも意味しません。報告の仕組み(目撃した人が通報するか、自治体が集めるか)や、記録を公表する時期の違いが、日付の積み上がり方に出ている可能性があります。",
                            "月ごとの動きは、研究ノートの「月別」「週別」のページでも見られます。お住まいの県の記録がいつ増える傾向にあるかを知りたいときは、県別の最新の目撃情報と、週ごとのまとめを合わせて見てください。このページは過去の記録の数え方を示すもので、これからの出没を予測するものではありません。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、9月30日までのものです。秋田県の記録が9月30日までのため、6県とも9月30日で区切りました。計算した日は{common.today().isoformat()}、使った記録の最新日は{as_of}です。",
            "日付は、記録の観測日をそのまま使っています。時刻のある記録も、日付だけを使っています。同じ日の記録は同じ日として数え、「達した日」はその割合に届いた件の日付です。",
            "累計の割合は、件数を日付順に並べて、全体の25%、50%、75%、90%に届く件を探しました。端数は切り上げです。",
            "対象の6県は、busy-days(記録の半分が入る日数)・new-towns(9月に初めて記録が出た市町村)と同じです。計算のスクリプトは、公開しています。",
        ],
        "caveats": [
            "これは報告された記録の累計です。熊の実際の数や行動の変化を直接示すものではありません。",
            "県ごとに記録の集め方が違います。記録が公表されるまでの遅れや、記録の入力が済んでいない分は、日付の積み上がり方にも影響します。",
            "1年度分(令和8年度)の記録だけです。ほかの年度に同じ形になるかは、この記録だけでは言えません。",
            "富山県・山口県・山梨県のように記録が少ない県は、数件の違いで「達した日」が数日ずれます。県どうしの数日の差を、そのまま比べないでください。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/half-by-date.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, s in st.items():
        print(k, s)
    print("chars", sum(len(p) for s in doc["sections"] for p in s["paragraphs"]) + sum(len(x) for x in doc["method"] + doc["caveats"] + doc["findings"]))
    print(doc["lead"])
    print(doc["findings"])
    print(oct_rows)


if __name__ == "__main__":
    main()
