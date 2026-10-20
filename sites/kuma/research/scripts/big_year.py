"""Research note: in the years when sightings jumped (R05 and R07), where and by how much?  Ministry of the Environment's yearly totals, R04-R07, by prefecture and by region,
and this year's April-to-latest-month against the same months of the last year.

python sites/kuma/research/scripts/big_year.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from sokuhou import prefectures as pf  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07"]
MIN_BASE = 100         # the earlier year of a pair must have this many sightings for a multiple to be shown


def main() -> None:
    env = common.load_env()
    S = env["sightings"]
    li = S["months"].index(S["latest_month"])
    latest_m = S["latest_month"]
    nat = S["national"]["total"]
    jump = {"R05": nat["R05"] / nat["R04"], "R07": nat["R07"] / nat["R06"]}
    rows, mult = [], {}
    regions = defaultdict(lambda: {y: 0 for y in YEARS})
    ytd = {}
    for p in S["prefectures"]:
        t, m = p["total"], p["monthly"]
        if any(t[y] is None for y in YEARS):
            continue
        region = pf.region_of(p["name"])[1]
        for y in YEARS:
            regions[region][y] += t[y]
        a = t["R05"] / t["R04"] if t["R04"] >= MIN_BASE else None
        b = t["R07"] / t["R06"] if t["R06"] >= MIN_BASE else None
        cur, prev = sum(v or 0 for v in m["R08"][: li + 1]), sum(m["R07"][: li + 1])
        ytd[p["name"]] = (cur, prev)
        mult[p["name"]] = (a, b)
        if max(t[y] for y in YEARS) >= 300:
            rows.append((p["name"], t, a, b))
    rows.sort(key=lambda r: -(r[1]["R07"]))
    table = [[common.full_name(n), f"{t['R04']:,}", f"{t['R05']:,}", f"{a:.1f}倍" if a else "-", f"{t['R06']:,}", f"{t['R07']:,}", f"{b:.1f}倍" if b else "-"] for n, t, a, b in rows]
    reg_rows = []
    for rg, v in sorted(regions.items(), key=lambda kv: -kv[1]["R07"]):
        if v["R07"] < 100:
            continue
        reg_rows.append([rg] + [f"{v[y]:,}" for y in YEARS] + [f"{v['R05'] / v['R04']:.1f}倍" if v["R04"] >= MIN_BASE else "-", f"{v['R07'] / v['R06']:.1f}倍" if v["R06"] >= MIN_BASE else "-"])
    both = [(n, a, b) for n, (a, b) in mult.items() if a and b]
    up5 = sum(1 for n, (a, b) in mult.items() if a and a > 1)
    n5 = sum(1 for n, (a, b) in mult.items() if a)
    up7 = sum(1 for n, (a, b) in mult.items() if b and b > 1)
    n7 = sum(1 for n, (a, b) in mult.items() if b)
    top7 = max(((n, b) for n, (a, b) in mult.items() if b), key=lambda t: t[1])
    top5 = max(((n, a) for n, (a, b) in mult.items() if a), key=lambda t: t[1])
    full = common.full_name
    nat_cur = sum(c for c, _ in ytd.values())
    nat_prev = sum(p for _, p in ytd.values())
    ytd_rows = sorted(((n, c, p) for n, (c, p) in ytd.items() if p >= MIN_BASE), key=lambda t: -t[1] / t[2])
    ytd_up = sum(1 for _, c, p in ytd_rows if c > p)
    data_as_of = S["updated"]
    reg7 = max((r for r in reg_rows if r[6] != "-"), key=lambda r: float(r[6].rstrip("倍")))
    reg5 = max((r for r in reg_rows if r[5] != "-"), key=lambda r: float(r[5].rstrip("倍")))

    doc = {
        "slug": "big-year", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": "熊(クマ)の出没が急に増えた年は、どの県で何倍になったか。令和5年度と令和7年度を環境省の表で数える",
        "h1": "出没が急に増えた年。令和5年度と令和7年度に、どの県で何倍になったか",
        "description": f"環境省の出没件数で、令和5年度(前年度の{jump['R05']:.1f}倍)と令和7年度({jump['R07']:.1f}倍)に、どの県で何倍になったかを数えました。令和8年度の{latest_m}月までは、前年度の同じ期間と比べます。",
        "lead": (f"熊の出没は、年によって大きく増えることがあります。環境省の表で、令和4年度から令和7年度の全国の件数を見ると、令和5年度は前年度の{jump['R05']:.1f}倍、令和7年度は前年度の{jump['R07']:.1f}倍でした。"
                 "この増え方は、全国で同じだったのか、県や地方でどれだけ違ったのか。県別・地方別に、年度の件数と倍率を数えました。"),
        "findings": [
            f"令和5年度は、前年度の件数が{MIN_BASE}件以上あった{n5}道府県のうち{up5}道府県で増え、最も増えたのは{full(top5[0])}の{top5[1]:.1f}倍です。令和7年度は{n7}道府県のうち{up7}道府県で増え、最も増えたのは{full(top7[0])}の{top7[1]:.1f}倍でした。",
            f"地方別では、令和5年度の増え方が最も大きかったのは{reg5[0]}の{reg5[5]}、令和7年度は{reg7[0]}の{reg7[6]}です。",
            f"令和8年度の4〜{latest_m}月は、全国(出没件数の表がある道府県の合計)で{nat_cur:,}件で、前年度の同じ期間({nat_prev:,}件)の{nat_cur / nat_prev:.2f}倍です。前年度が{MIN_BASE}件以上の{len(ytd_rows)}道府県のうち、{ytd_up}道府県で前年度の同じ期間より多くなっています。",
        ],
        "sections": [
            {"h2": "道府県別の、年度の件数と倍率",
             "paragraphs": ["4年度の件数が300件以上ある道府県を、令和7年度の件数が多い順に並べました。倍率は、令和5年度は令和4年度に対する倍、令和7年度は令和6年度に対する倍です。前の年度が" + f"{MIN_BASE}件に満たない場合は、倍率を「-」にしています。"],
             "table": {"head": ["道府県", "令和4年度", "令和5年度", "5年度の倍率", "令和6年度", "令和7年度", "7年度の倍率"], "rows": table,
                       "note": "件数は、環境省が都道府県から聞き取った速報値です。都道府県ごとに数え方が違うため、県どうしの件数の大小は比べられません。同じ県の年度どうしの倍率を見てください。"}},
            {"h2": "地方別の、年度の件数と倍率",
             "paragraphs": ["環境省の表にある道府県の件数を、地方ごとに合計しました。北海道は、環境省の出没件数の表に数値がないため、含まれていません。"],
             "table": {"head": ["地方", "令和4年度", "令和5年度", "令和6年度", "令和7年度", "5年度の倍率", "7年度の倍率"], "rows": reg_rows}},
            {"h2": f"令和8年度の4〜{latest_m}月は、前年度の同じ期間と比べてどうか",
             "paragraphs": [f"令和8年度は、{latest_m}月分までが公表されています。令和7年度の4〜{latest_m}月と比べました(前年度の同じ期間が{MIN_BASE}件以上の道府県)。倍率が大きい順の上位8道府県です。"],
             "table": {"head": ["道府県", f"令和8年度(4〜{latest_m}月)", f"令和7年度(4〜{latest_m}月)", "倍率"], "rows": [[full(n), f"{c:,}", f"{p:,}", f"{c / p:.2f}倍"] for n, c, p in ytd_rows[:8]],
                       "note": f"4〜{latest_m}月だけの比べです。令和7年度は、秋(9〜11月)に件数が大きく増えた年度なので、年度全体の件数とは分けて見てください。"}},
        ],
        "method": [
            "環境省「クマの出没情報(速報値)」の、都道府県別の年度ごとの合計と、月別の件数を使いました。令和4〜7年度は、4月から翌年3月まで公表済みの年度です。令和8年度は、公表済みの月まで(4〜" + f"{latest_m}月)を、令和7年度の同じ月と比べました。",
            f"倍率は、後の年度の件数を前の年度の件数で割り、小数第1位で示しました。前の年度が{MIN_BASE}件に満たない道府県は、数件の違いで倍率が大きく動くため、倍率を出していません。地方の区分は、このサイトの地方別の区分です。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開きました。出没情報の表が掲載されていることを確かめています。",
        ],
        "caveats": [
            "出没件数の数え方は、都道府県ごとに違います。倍率が大きい県が、実際の個体の増え方が大きい県とは言えません。報告の件数は、通報のしやすさや受け付けの体制にも左右されます。",
            "増えた理由は、この表からは言えません。ここで数えたのは、件数の変わり方だけです。令和8年度の公表は途中で、年度全体がどうなるかは、まだ分かりません。",
            "4年度のうちの2回の増加を見ただけです。ほかの年にも同じ県で大きく増えるかは、言えません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/big_year.py",
        "related": [{"label": "前年度の同じ期間との比較(ランキング)", "href": "/ranking/change/"}, {"label": "全国の推移", "href": "/trend/"},
                    {"label": "何月に多いか(都道府県別)", "href": "/season/"}, {"label": "出没件数ランキング", "href": "/ranking/sightings/"}],
    }
    common.write_note(doc)
    print(jump, n5, up5, top5, n7, up7, top7, reg5[:1], reg7[:1], nat_cur, nat_prev, ytd_up, len(ytd_rows))


if __name__ == "__main__":
    main()
