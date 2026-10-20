"""Research note: deaths in bear injury statistics, year by year (H20-R07) and the Ministry's lists of fatal accidents (R07, R08): month and prefecture.  Counts only.

python sites/kuma/research/scripts/deaths_by_year.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main() -> None:
    env = common.load_env()
    I = env["injuries"]
    years = [y for y in I["years"] if y != "R08"]            # R08 is a year in progress (to the end of September)
    nat = I["national"]
    deaths = {y: nat[y][2] for y in years}
    victims = {y: nat[y][1] for y in years}
    top = sorted(years, key=lambda y: -deaths[y])
    zero = [y for y in years if deaths[y] == 0]
    avg_first = sum(deaths[y] for y in years[:10]) / 10
    avg_last = sum(deaths[y] for y in years[-10:]) / 10
    lists = {y: env["fatal"][y] for y in ("R07", "R08")}
    inc = [(y, i) for y in ("R07", "R08") for i in lists[y]["incidents"]]
    by_m = {y: Counter(int(i["date"][5:7]) for i in lists[y]["incidents"]) for y in lists}
    by_p = Counter(i["prefecture"] for _, i in inc)
    found = sum(1 for _, i in inc if i["found_date"])
    two = sum(1 for _, i in inc if i["victims"] > 1)
    cur_dead = nat["R08"][2]
    inj_as_of = I["as_of"].replace("R08年", "令和8年")
    data_as_of = max(I["updated"], lists["R07"]["as_of"], lists["R08"]["as_of"])
    rows = []
    for m in common.MONTHS:
        a, b = by_m["R07"].get(m, 0), by_m["R08"].get(m, 0)
        rows.append([f"{m}月", str(a), str(b)])
    prow = [[p, str(sum(1 for y, i in inc if i["prefecture"] == p and y == "R07")), str(sum(1 for y, i in inc if i["prefecture"] == p and y == "R08")), str(n)] for p, n in by_p.most_common()]
    yrows = [[common.fy(y), f"{nat[y][0]}", f"{nat[y][1]}", f"{nat[y][2]}"] for y in reversed(years)]
    peak_m = max(by_m["R07"], key=lambda m: by_m["R07"][m])
    cum = sum(deaths.values())

    doc = {
        "slug": "deaths-by-year", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": f"熊(クマ)による死亡は、年にどれだけか。環境省の統計({common.fy(years[0])}〜{common.fy(years[-1])})と、死亡事故の一覧を数える",
        "h1": f"クマによる死亡者数は、年度でどう動いてきたか。{common.fy(years[0])}から{common.fy(years[-1])}と、最近の死亡事故の月別・県別",
        "description": f"環境省の人身被害の統計で、クマによる死亡者数を{common.fy(years[0])}から{common.fy(years[-1])}まで年度別に数えました。最も多かったのは{common.fy(top[0])}の{deaths[top[0]]}人です。死亡事故の月別・県別も、件数だけで載せます。",
        "lead": (f"環境省は、クマによる人身被害を、件数・人数・死亡者数で、平成20年度から公表しています。死亡者数が年度でどう動いてきたのかを、{common.fy(years[0])}から{common.fy(years[-1])}の{len(years)}年度分で数えました。"
                 f"あわせて、環境省が別に公表している死亡事故の一覧(令和7年度{len(lists['R07']['incidents'])}件・令和8年度{len(lists['R08']['incidents'])}件)を、月別・都道府県別に数えます。事故の経過や被害者の状況は、扱いません。"),
        "findings": [
            f"{common.fy(years[0])}から{common.fy(years[-1])}の{len(years)}年度で、死亡者は合計{cum}人です。最も多かったのは{common.fy(top[0])}の{deaths[top[0]]}人、次いで{common.fy(top[1])}の{deaths[top[1]]}人でした。死亡者が0人の年度は{len(zero)}年度あります。",
            f"最初の10年度の平均は年{avg_first:.1f}人、最近の10年度の平均は年{avg_last:.1f}人です。{common.fy(years[-1])}は、被害者{victims[years[-1]]}人のうち死亡が{deaths[years[-1]]}人でした。令和8年度は、{inj_as_of.replace('令和8年', '')}までで死亡{cur_dead}人です。",
            f"環境省の死亡事故の一覧({len(inc)}件)を月別に数えると、令和7年度は{peak_m}月が{by_m['R07'][peak_m]}件で最も多くなりました。都道府県別では{'・'.join(f'{p}{n}件' for p, n in by_p.most_common(3))}が多くなっています。",
        ],
        "sections": [
            {"h2": "年度別の、人身被害と死亡者数",
             "paragraphs": ["環境省の人身被害の統計を、新しい年度から並べました。「件数」は被害にあった事案の数、「被害者数」は人数、「死亡」は被害者のうち亡くなった人数です。"],
             "table": {"head": ["年度", "人身被害の件数", "被害者数(人)", "うち死亡(人)"], "rows": yrows,
                       "note": f"令和8年度は{inj_as_of}までの速報値で、年度の途中のため、この表には載せていません(死亡{cur_dead}人)。"}},
            {"h2": "死亡者数の年度別の動き(グラフ)",
             "paragraphs": [f"年度ごとの死亡者数を、棒グラフにしました。{common.fy(top[0])}の{deaths[top[0]]}人が最も多く、死亡者が0人の年度は{'・'.join(common.fy(y) for y in zero)}です。"],
             "chart": {"kind": "bars", "labels": [y.replace("R0", "R").replace("H", "H") for y in years], "values": [deaths[y] for y in years], "title": "クマによる死亡者数(人)",
                       "desc": f"{common.fy(years[0])}から{common.fy(years[-1])}までの、全国のクマによる死亡者数を年度別に比べた棒グラフ。"}},
            {"h2": "死亡事故の一覧(令和7・8年度)を、月別に数える",
             "paragraphs": [f"環境省が公表している死亡事故の一覧の、日付の月で数えました。令和7年度は{common.jp(lists['R07']['as_of'])}現在、令和8年度は{common.jp(lists['R08']['as_of'])}現在の一覧です。{found}件は、事故の日ではなく被害者が見つかった日が、日付に書かれています。"],
             "table": {"head": ["月", "令和7年度(件)", "令和8年度(件)"], "rows": rows}},
            {"h2": "都道府県別の件数",
             "paragraphs": ["一覧に書かれている都道府県で数えました。人数は、1件につき1人です。" if not two else f"一覧に書かれている都道府県で数えました。1件で複数の被害者の事故が{two}件あります。"],
             "table": {"head": ["都道府県", "令和7年度(件)", "令和8年度(件)", "合計(件)"], "rows": prow}},
        ],
        "method": [
            "環境省「クマによる人身被害件数(速報値)」の、全国の件数・人数・死亡者数(平成20年度から)を使いました。年度の途中の令和8年度は、年度別の表から外しました。",
            "死亡事故の一覧は、環境省「令和7年度のクマによる死亡事故件数等」「令和8年度のクマによる死亡事故数等」の、1件ごとの日付・都道府県・市町村・人数を、月と都道府県で数えたものです。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開きました。人身被害件数と、死亡事故の資料が掲載されていることを確かめています。",
        ],
        "caveats": [
            "人身被害の統計は、環境省が都道府県から聞き取った速報値で、後から変更されることがあります。死亡者数の年度による増減が、出没の増減や、人の行動の変化によるものかは、この記録からは言えません。",
            "死亡事故の一覧は、令和7年度と令和8年度の2年度分だけで、件数が少ないため、月別・県別の偏りは、偶然でも生じます。件数の多い県が、危険な県であることを意味しません。",
            "一覧の日付には、事故の日と、被害者が見つかった日が混ざっています。このノートは、事故の状況・場所の詳細・被害者の情報を扱いません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/deaths_by_year.py",
        "related": [{"label": "人身被害ランキング", "href": "/ranking/injuries/"}, {"label": "緊急銃猟と死亡事故の一覧", "href": "/emergency/"},
                    {"label": "クマに出会ったときの行動", "href": "/guide/encounter/"}, {"label": "クマに出会わないための備え", "href": "/guide/prepare/"}],
    }
    common.write_note(doc)
    print(deaths, avg_first, avg_last, found, two, by_p.most_common(4), peak_m)


if __name__ == "__main__":
    main()
