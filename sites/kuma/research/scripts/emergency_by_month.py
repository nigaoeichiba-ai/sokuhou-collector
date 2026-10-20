"""Research note: when and where was an emergency shooting (緊急銃猟) carried out?  Ministry of the Environment's list of emergency shootings, R07 and R08 (to the day of the list).

python sites/kuma/research/scripts/emergency_by_month.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R07", "R08"]


def main() -> None:
    env = common.load_env()
    cases = {y: env["emergency"][y]["cases"] for y in YEARS}
    upd = {y: env["emergency"][y]["updated"] for y in YEARS}
    span = {y: (min(c["date"] for c in cases[y]), max(c["date"] for c in cases[y])) for y in YEARS}
    by_m = {y: Counter(int(c["date"][5:7]) for c in cases[y]) for y in YEARS}
    by_p = {y: Counter(c["prefecture"] for c in cases[y]) for y in YEARS}
    by_s = {y: Counter(c["species"] for c in cases[y]) for y in YEARS}
    total = {y: len(cases[y]) for y in YEARS}
    allp = by_p["R07"] + by_p["R08"]
    peak = {y: max(by_m[y], key=lambda m: by_m[y][m]) for y in YEARS}
    bears = {y: sum(v for k, v in by_s[y].items() if k.endswith(("グマ", "クマ"))) for y in YEARS}
    cities = Counter((c["prefecture"], c["place"]) for y in YEARS for c in cases[y])
    again = [(k, v) for k, v in cities.most_common() if v >= 2]
    # by calendar month, both years side by side (the R07 list starts in October, the R08 list runs from April)
    rows = []
    for m in common.MONTHS:
        a, b = by_m["R07"].get(m, 0), by_m["R08"].get(m, 0)
        rows.append([f"{m}月", "-" if (m in (4, 5, 6, 7, 8, 9) and a == 0) else str(a), str(b) if b or m in (4, 5, 6, 7, 8, 9, 10) else "-"])
    prow = [[common.full_name(p.removesuffix("県").removesuffix("府").removesuffix("都")) if False else p, str(by_p["R07"].get(p, 0)), str(by_p["R08"].get(p, 0)), str(allp[p])] for p, _ in allp.most_common()]
    srow = []
    for sp in sorted(set(by_s["R07"]) | set(by_s["R08"]), key=lambda k: -(by_s["R07"].get(k, 0) + by_s["R08"].get(k, 0))):
        srow.append([sp, str(by_s["R07"].get(sp, 0)), str(by_s["R08"].get(sp, 0))])
    top3 = [p for p, _ in allp.most_common(3)]
    data_as_of = max(upd.values())
    nov = by_m["R07"].get(11, 0)

    def jp_md(d):
        return f"{int(d[5:7])}月{int(d[8:10])}日"

    doc = {
        "slug": "emergency-by-month", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": f"熊(クマ)の緊急銃猟は、いつ、どの県で行われたか。環境省の一覧{total['R07'] + total['R08']}件を数える",
        "h1": "緊急銃猟の実施は、何月に、どの都道府県に多いか。環境省の一覧を月別・県別・対象別に数える",
        "description": f"環境省が公表している緊急銃猟の実施状況(令和7年度{total['R07']}件・令和8年度{total['R08']}件)を、月別・都道府県別・対象別に数えました。令和7年度は{peak['R07']}月が最多の{by_m['R07'][peak['R07']]}件です。",
        "lead": ("緊急銃猟は、クマなどが市街地に出て、人の命や身体に危害が及ぶおそれがあるときに、市町村長の判断で行う銃猟です。環境省は、実施状況を一覧で公表しています。"
                 f"令和7年度は{jp_md(span['R07'][0])}〜{jp_md(span['R07'][1])}の{total['R07']}件、令和8年度は{jp_md(span['R08'][0])}〜{jp_md(span['R08'][1])}の{total['R08']}件です。この一覧を、月ごと・都道府県ごと・対象の動物ごとに数えました。"),
        "findings": [
            f"令和7年度は{total['R07']}件で、{peak['R07']}月が{by_m['R07'][peak['R07']]}件と最も多く、11月だけで年度の{nov / total['R07'] * 100:.0f}%を占めます。令和8年度は{jp_md(span['R08'][1])}までで{total['R08']}件、月別では{peak['R08']}月が{by_m['R08'][peak['R08']]}件で最も多くなっています。",
            f"2年度の合計{total['R07'] + total['R08']}件を都道府県別に数えると、多いのは{'・'.join(f'{p}{allp[p]}件' for p in top3)}です。{len(allp)}都道府県で実施されました。",
            f"対象は、クマ類が令和7年度{bears['R07']}件・令和8年度{bears['R08']}件で、ほかにイノシシがあります。同じ市町村で2回以上実施された例は{len(again)}市町村です。",
        ],
        "sections": [
            {"h2": "月別の件数",
             "paragraphs": ["実施の日付で、月ごとに数えました。令和7年度の一覧に載っている最初の実施は10月15日で、4〜9月の欄の「-」は、一覧に実施の記載がないことを示します。令和8年度は、4月から一覧の日までの件数です。"],
             "table": {"head": ["月", "令和7年度(件)", "令和8年度(件)"], "rows": rows, "note": f"令和7年度は{common.jp(upd['R07'])}、令和8年度は{common.jp(upd['R08'])}に更新された一覧です。令和8年度の10月は、{jp_md(span['R08'][1])}までの件数です。"},
             },
            {"h2": "令和7年度の月別の件数(グラフ)",
             "paragraphs": [f"令和7年度の件数を月別に並べました。10月から12月に{sum(by_m['R07'].get(m, 0) for m in (10, 11, 12))}件が集中し、1〜3月は{sum(by_m['R07'].get(m, 0) for m in (1, 2, 3))}件です。"],
             "chart": {"kind": "bars", "labels": [f"{m}月" for m in (10, 11, 12, 1, 2, 3)], "values": [by_m["R07"].get(m, 0) for m in (10, 11, 12, 1, 2, 3)], "title": "令和7年度の緊急銃猟の月別の件数",
                       "desc": "令和7年度の緊急銃猟の実施件数を、10月から翌年3月まで月別に比べた棒グラフ。"}},
            {"h2": "都道府県別の件数",
             "paragraphs": ["実施した市町村がある都道府県を、2年度の合計が多い順に並べました。"],
             "table": {"head": ["都道府県", "令和7年度(件)", "令和8年度(件)", "合計(件)"], "rows": prow}},
            {"h2": "同じ市町村での、くり返し",
             "paragraphs": [f"都道府県と市町村の名前が同じ行を数えると、2回以上実施された市町村が{len(again)}あります。最も多いのは{'・'.join(f'{p}{c}({n}件)' for (p, c), n in again[:3])}です。" if again else "同じ市町村で2回以上実施された例は、一覧にありません。",
                            "同じ市町村で複数回あっても、同じ個体への対応かどうかは、一覧からは分かりません。一覧の1行は、1回の実施です。"],
             "table": {"head": ["都道府県", "市町村", "実施(件)"], "rows": [[p, c, str(n)] for (p, c), n in again]}} if again else None,
            {"h2": "対象の動物",
             "paragraphs": [f"一覧に書かれている対象の動物ごとに数えました。クマ類(ツキノワグマ・ヒグマ)は2年度で{bears['R07'] + bears['R08']}件、ほかの動物は{total['R07'] + total['R08'] - bears['R07'] - bears['R08']}件です。一覧には、イノシシの例も入っています。"],
             "table": {"head": ["対象", "令和7年度(件)", "令和8年度(件)"], "rows": srow}},
        ],
        "method": [
            "環境省「令和7年度の緊急銃猟実施状況」「令和8年度の緊急銃猟実施状況」の一覧(1件ごとの日付・都道府県・市町村・対象)を、日付・都道府県・対象で数えました。1件は、一覧の1行です。",
            f"月は、実施日の月です。同じ日に同じ場所で複数の行があれば、そのまま複数件と数えています。同じ市町村に2件以上ある例は、都道府県と市町村名が同じ行を数えました。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開き、令和7年度と令和8年度の一覧が掲載されていることを確かめました。一覧の更新日は、{common.jp(upd['R07'])}と{common.jp(upd['R08'])}です。",
        ],
        "caveats": [
            "この一覧は、環境省が把握した緊急銃猟の実施です。出没があっても、実施しなかった例は含まれません。件数の多い県が、出没の多い県とは限りません。",
            "実施の件数が月で偏る理由は、この一覧からは言えません。市街地に出る頻度や、実施の判断の運用が、年度によって違うことも考えられますが、確かめられません。",
            "令和8年度は年度の途中です。令和8年度の10月は月の途中までの件数なので、令和7年度の10月とは、期間が同じではありません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/emergency_by_month.py",
        "related": [{"label": "緊急銃猟と死亡事故の一覧", "href": "/emergency/"}, {"label": "環境省のお知らせ", "href": "/news/"},
                    {"label": "クマに出会ったときの行動", "href": "/guide/encounter/"}, {"label": "出没件数ランキング", "href": "/ranking/sightings/"}],
    }
    doc["sections"] = [x for x in doc["sections"] if x]
    common.write_note(doc)
    print(total, peak, nov, again, top3, len(allp))


if __name__ == "__main__":
    main()
