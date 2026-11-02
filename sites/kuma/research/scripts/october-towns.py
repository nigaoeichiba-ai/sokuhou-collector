"""Research note: which towns that had bear records in April-September still had a record in October?  Five prefectures, towns grouped by how many records they had in April-September (1-2, 3-9, 10 or more).

python sites/kuma/research/scripts/october-towns.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
GROUPS = [("1〜2件", 1, 2), ("3〜9件", 3, 9), ("10件以上", 10, 10**6)]
END = date(2026, 10, 28)     # the latest day every one of the five prefectures covers


def day(r) -> date:
    return r[0].date() if isinstance(r[0], datetime) else r[0]


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    st = {}
    pooled = {g[0]: [0, 0] for g in GROUPS}
    oct_in = {g[0]: 0 for g in GROUPS}
    oct_new = 0
    oct_records = 0
    for k, src in data.items():
        early = Counter(r[2] for r in src["rows"] if r[2] and date(2026, 4, 1) <= day(r) <= date(2026, 9, 30))
        octo_rows = [r for r in src["rows"] if r[2] and date(2026, 10, 1) <= day(r) <= END]
        octo = Counter(r[2] for r in octo_rows)
        row = {}
        for name, lo, hi in GROUPS:
            towns = [c for c, n in early.items() if lo <= n <= hi]
            hit = sum(1 for c in towns if c in octo)
            row[name] = (len(towns), hit)
            pooled[name][0] += len(towns)
            pooled[name][1] += hit
            oct_in[name] += sum(octo[c] for c in towns)
        new = [c for c in octo if c not in early]
        oct_new += len(new)
        oct_records += len(octo_rows)
        st[k] = dict(towns=len(early), hit=sum(1 for c in early if c in octo), row=row, new=len(new), octo=len(octo_rows),
                     big=[c for c, n in early.items() if n >= 10 and c not in octo])
    as_of = max(s["as_of"] for s in data.values())
    tot_t = sum(s["towns"] for s in st.values())
    tot_h = sum(s["hit"] for s in st.values())
    pc = lambda a, b: f"{a / b * 100:.0f}%" if b else "-"
    gshare = {n: pc(h, t) for n, (t, h) in pooled.items()}
    big_t, big_h = pooled["10件以上"]
    small_t, small_h = pooled["1〜2件"]
    mid_t, mid_h = pooled["3〜9件"]
    rows = [[SOURCES[k], f"{st[k]['towns']}", f"{st[k]['hit']}", pc(st[k]["hit"], st[k]["towns"]), f"{st[k]['octo']}"] for k in SOURCES]
    rows.append(["5県の合計", f"{tot_t}", f"{tot_h}", pc(tot_h, tot_t), f"{oct_records}"])
    grows = [[n, f"{t}", f"{h}", pc(h, t), f"{oct_in[n]}"] for n, (t, h) in pooled.items()]
    prow = [[SOURCES[k]] + [f"{st[k]['row'][g[0]][1]}/{st[k]['row'][g[0]][0]}" for g in GROUPS] for k in SOURCES]
    silent_big = sum(len(s["big"]) for s in st.values())
    share_big = oct_in["10件以上"] / oct_records
    names_big = "・".join(f"{SOURCES[k]}{len(st[k]['big'])}" for k in SOURCES if st[k]["big"])
    by_pref = "、".join(f"{SOURCES[k]}{pc(st[k]['hit'], st[k]['towns'])}" for k in SOURCES)
    lo_share = min(st[k]["hit"] / st[k]["towns"] for k in SOURCES)
    hi_share = max(st[k]["hit"] / st[k]["towns"] for k in SOURCES)
    r = lambda k, g: f"{st[k]['row'][g][1]}/{st[k]['row'][g][0]}"
    today = common.today().isoformat()

    doc = {
        "slug": "october-towns", "date": today, "data_as_of": as_of,
        "title": "春から夏に熊の記録があった市町村の何割に、10月も記録があるか",
        "h1": "4〜9月に熊(クマ)の記録があった市町村の、何割で10月にも記録があったか",
        "description": f"宮城・新潟・富山・山口・山梨の令和8年度の記録です。4〜9月に記録があった{tot_t}市町村のうち、10月1〜28日にも記録があったのは{tot_h}市町村({pc(tot_h, tot_t)})でした。4〜9月に10件以上あった市町村では{pc(big_h, big_t)}、1〜2件では{pc(small_h, small_t)}です。",
        "lead": (f"夏のあいだに熊の記録が出た市町村では、秋になっても記録が続くのでしょうか。5県で、4〜9月に記録のあった{tot_t}市町村を数えると、10月1〜28日にも記録があったのは{tot_h}市町村で、{pc(tot_h, tot_t)}でした。"
                 f"ただし、夏の記録が10件以上あった市町村では{pc(big_h, big_t)}、1〜2件だった市町村では{pc(small_h, small_t)}と、割合が大きく違います。この差を、県ごとにも確かめます。"),
        "findings": [
            f"4〜9月に記録のあった市町村は5県で{tot_t}。うち10月1〜28日にも記録があったのは{tot_h}で、{pc(tot_h, tot_t)}です。県別では、{by_pref}です。",
            f"4〜9月の件数で市町村を分け、10月にも記録があった割合を見ます。1〜2件の市町村は{small_h}/{small_t}({pc(small_h, small_t)})、3〜9件は{mid_h}/{mid_t}({pc(mid_h, mid_t)})、10件以上は{big_h}/{big_t}({pc(big_h, big_t)})です。夏に件数の多かった市町村ほど、10月にも記録が出ています。",
            f"4〜9月に記録がなく、10月に初めて記録が出た市町村は、5県を合わせて{oct_new}です。10月の記録{oct_records}件のうち、夏に10件以上あった市町村の記録は{oct_in['10件以上']}件({share_big * 100:.0f}%)でした。",
        ],
        "sections": [
            {"h2": "県別に見た、10月にも記録があった市町村の数",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、市町村名のある記録を使いました。4月1日から9月30日までに1件以上あった市町村を「夏までに記録のあった市町村」とし、そのうち10月1日から28日までにも1件以上あった市町村を数えました。28日で区切ったのは、5県の記録がそろっている範囲が10月28日までだからです。",
                            f"5県を合わせると{tot_t}市町村のうち{tot_h}市町村(約{pc(tot_h, tot_t)})で、10月にも記録がありました。県別では{lo_share * 100:.0f}%から{hi_share * 100:.0f}%までの幅があります。宮城県は夏までに記録のあった市町村が{st['miyagi']['towns']}と最も多く、そのうち{st['miyagi']['hit']}市町村に10月の記録がありました。",
                            f"10月に記録が出た市町村のうち、4〜9月には1件も記録がなかった市町村は、5県を合わせて{oct_new}です。10月の記録は、すべて夏までに記録のあった市町村の中で出ています。9月に初めて記録が出た市町村を数えたnew-townsのノートと、同じ向きの結果です。"],
             "table": {"head": ["県", "4〜9月に記録のあった市町村", "うち10月1〜28日にも記録あり", "割合", "10月1〜28日の記録(件)"], "rows": rows,
                       "note": "市町村名のない記録は数えていません。10月の件数は、市町村名のある記録だけの合計です。"}},
            {"h2": "夏の件数が多い市町村ほど、10月にも記録がある",
             "paragraphs": [f"市町村を、4〜9月の記録の件数で3つに分けました。1〜2件、3〜9件、10件以上です。5県を合わせると、10月にも記録があった割合は{gshare['1〜2件']}、{gshare['3〜9件']}、{gshare['10件以上']}と、件数の多いグループほど高くなっています。",
                            f"夏に10件以上あった市町村は{big_t}あり、そのうち{big_h}で10月にも記録がありました。10月に記録がなかった{silent_big}市町村は、県別に{names_big}です。一方、夏の記録が1〜2件だった{small_t}市町村では、10月にも記録があったのは{small_h}市町村でした。",
                            "ただし、これは当たり前の面もあります。夏に記録の多い市町村は、熊が出やすい場所か、報告が集まりやすい場所です。件数の少ない市町村は、10月の28日間に1件も出ないことが、もともと多いからです。このノートでは、その理由までは分けられません。"],
             "table": {"head": ["4〜9月の件数", "市町村の数(5県の合計)", "うち10月にも記録あり", "割合", "10月1〜28日の記録(件)"], "rows": grows,
                       "note": "市町村の数と記録の件数は、5県を足し合わせた値です。"},
             "chart": {"kind": "bars", "labels": [g[0] for g in GROUPS], "values": [round(pooled[g[0]][1] / pooled[g[0]][0] * 100) for g in GROUPS],
                       "title": "4〜9月の件数別に見た、10月にも記録があった市町村の割合(%)",
                       "desc": "4〜9月に記録のあった市町村を件数で3つに分け、10月1〜28日にも記録があった割合を比べた棒グラフ。件数の多いグループほど高い。"}},
            {"h2": "県ごとに、同じ向きになっているか",
             "paragraphs": ["5県を足し合わせた割合は、一つの県の動きに引っぱられることがあります。そこで、県ごとの分母と分子を、グループ別に並べました。表の「3/7」は、7市町村のうち3市町村に10月の記録があったことを表します。",
                            f"10件以上のグループで見ると、宮城県は{r('miyagi', '10件以上')}、新潟県は{r('niigata', '10件以上')}、富山県は{r('toyama', '10件以上')}、山口県は{r('yamaguchi', '10件以上')}、山梨県は{r('yamanashi', '10件以上')}です。1〜2件のグループは、山梨県が{r('yamanashi', '1〜2件')}、山口県が{r('yamaguchi', '1〜2件')}、宮城県が{r('miyagi', '1〜2件')}など、市町村の数が少ないため、1市町村の違いで割合が大きく変わります。",
                            "市町村の数が少ない県とグループの割合は、数値そのままを県どうしで比べないでください。"],
             "table": {"head": ["県", "1〜2件", "3〜9件", "10件以上"], "rows": prow, "note": "分子は10月1〜28日にも記録があった市町村、分母は4〜9月にその件数だった市町村です。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、令和8年度の5県では、夏までに記録のあった市町村のうち{pc(tot_h, tot_t)}で10月にも記録があり、夏の件数が多い市町村ほどその割合が高かったことです。10月に初めて記録が出た市町村はありませんでした。",
                            "言えないのは、記録のない市町村が安全だということです。記録のない市町村は、熊が出ていないとは限らず、報告されていないか、この記録の集め方に入っていない場合があります。また、10月に記録がなかった市町村で、11月以降に記録が出ないとも言えません。",
                            "お住まいの市町村に夏の記録が少なくても、それを理由に備えを省かないでください。最新の目撃情報は県別のページで、対処法は「クマに出会わないために」のページで見られます。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、市町村名のあるものです。4〜9月と、10月1〜28日に分けました。宮城・新潟・富山・山口・山梨の5県で、秋田県は記録が9月30日までのため入れていません。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "市町村名は、各県の記録にある表記のままです。同じ市町村が表記ゆれで別々に数えられていないかは、県ごとの一覧で確かめていません。",
            "夏の件数は、4月1日から9月30日までの、その市町村の記録の件数です。グループの区切り(1〜2件・3〜9件・10件以上)は、このノートで決めた目安で、公式の区分ではありません。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や行動を直接示すものではありません。",
            "県ごとに記録の集め方が違います。記録の入力が遅れると、10月の後半の件数が少なく見えます。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
            "市町村の数が少ない県とグループでは、1市町村の違いで割合が大きく変わります。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/october-towns.py",
        "related": [{"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"}, {"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
