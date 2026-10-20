"""Research note: how many bears were captured (permitted captures, in heads) against the number of sightings?  Ministry of the Environment, R04-R07.

Captures are a separate statistic counted in heads under a prefecture's plan; sightings are counted by each prefecture its own way.  The ratio (captures per 100 sightings) is read
for one prefecture across the years; the note says that it is not a rate of anything and that captures are not a subset of sightings.

python sites/kuma/research/scripts/capture_vs_sightings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07"]
MIN_POOLED = 1000          # sightings over the four years


def main() -> None:
    env, cap = common.load_env(), common.load_capture()
    S = env["sightings"]
    by_cap = {p["name"]: p["by_year"] for p in cap["prefectures"]}
    nat_c, nat_s = cap["national"], S["national"]["total"]
    sp = cap["species"]
    full = common.full_name
    stats, rows = {}, []
    for p in S["prefectures"]:
        t = p["total"]
        if any(t[y] is None for y in YEARS) or p["name"] not in by_cap:
            continue
        pooled = sum(t[y] for y in YEARS)
        if pooled < MIN_POOLED:
            continue
        caps = sum(by_cap[p["name"]][y][0] for y in YEARS)
        per_year = [by_cap[p["name"]][y][0] / t[y] * 100 for y in YEARS]
        stats[p["name"]] = dict(pooled=pooled, caps=caps, ratio=caps / pooled * 100, per_year=per_year)
    order = sorted(stats, key=lambda k: -stats[k]["pooled"])
    for k in order:
        st = stats[k]
        rows.append([full(k), f"{st['pooled']:,}", f"{st['caps']:,}", f"{st['ratio']:.0f}", " / ".join(f"{v:.0f}" for v in st["per_year"])])
    lo = min(stats, key=lambda k: stats[k]["ratio"])
    hi = max(stats, key=lambda k: stats[k]["ratio"])
    over = [k for k in stats if any(v > 100 for v in stats[k]["per_year"])]
    hok_cap = {y: by_cap['北海道'][y][0] for y in YEARS}
    ratio = {y: (nat_c[y][0] - hok_cap[y]) / nat_s[y] * 100 for y in YEARS}      # the Ministry's sightings table has no Hokkaido figure, so Hokkaido's captures are left out of the ratio
    hok = {y: sp["ヒグマ"][y][0] for y in YEARS}
    tsuki = {y: sp["ツキノワグマ"][y][0] for y in YEARS}
    data_as_of = max(S["updated"], cap["updated"])
    kill = {y: nat_c[y][1] / nat_c[y][0] * 100 for y in YEARS}
    big = max(YEARS, key=lambda y: nat_s[y])
    sm = min(YEARS, key=lambda y: nat_s[y])
    cap_as_of = cap["as_of"].replace("R08年", "令和8年")

    doc = {
        "slug": "capture-vs-sightings", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": "熊(クマ)の出没100件に対して、何頭が捕獲されたか。環境省の許可捕獲数と出没件数を重ねる",
        "h1": "出没件数と許可捕獲数を重ねる。出没100件あたり、何頭が捕獲されたか",
        "description": f"環境省の出没件数と許可捕獲数(令和4〜7年度)を重ね、出没100件あたりの捕獲頭数を全国と{len(stats)}道府県で数えました。全国は{min(ratio.values()):.0f}〜{max(ratio.values()):.0f}頭で、県と年度で大きく違います。",
        "lead": ("環境省は、クマの出没件数と、許可を得て捕獲した頭数を、別の表で公表しています。出没が増えた年に、捕獲の頭数は、どれだけ増えているのか。"
                 f"令和4年度から令和7年度の4年度分を重ねて、出没100件あたりの許可捕獲数を、全国と、出没の多い{len(stats)}道府県で数えました。"),
        "findings": [
            f"北海道を除く全国の出没100件あたりの許可捕獲数は、{'、'.join(f'{common.fy(y)}が{ratio[y]:.0f}頭' for y in YEARS)}でした。出没件数が最も多かった{common.fy(big)}({nat_s[big]:,}件)に、全国で許可捕獲されたのは{nat_c[big][0]:,}頭(北海道のヒグマを含む)です。",
            f"{len(stats)}道府県の4年度合計では、出没100件あたりの捕獲頭数がいちばん少ないのは{full(lo)}({stats[lo]['ratio']:.0f}頭)、いちばん多いのは{full(hi)}({stats[hi]['ratio']:.0f}頭)でした。{'・'.join(full(k) for k in over)}には、捕獲数が出没件数を上回った年度があります。" if over else
            f"{len(stats)}道府県の4年度合計では、出没100件あたりの捕獲頭数がいちばん少ないのは{full(lo)}({stats[lo]['ratio']:.0f}頭)、いちばん多いのは{full(hi)}({stats[hi]['ratio']:.0f}頭)でした。",
            f"捕獲のうち、捕殺(殺処理)の割合は、全国で{min(kill.values()):.0f}〜{max(kill.values()):.0f}%です。北海道のヒグマは{hok['R04']:,}頭から{hok['R07']:,}頭(令和4→7年度)、本州以南のツキノワグマは{tsuki['R04']:,}頭から{tsuki['R07']:,}頭でした。",
        ],
        "sections": [
            {"h2": "全国の、許可捕獲数と出没件数",
             "paragraphs": ["許可捕獲数は、被害防止のための捕獲と、特定計画による数の調整のための捕獲を合わせた頭数です。「捕殺」は殺処理した頭数、「非捕殺」は放獣などをした頭数です。出没件数は、件数で数えているため、頭数とは単位が違います。"],
             "table": {"head": ["年度", "出没件数(北海道を除く全国)", "許可捕獲数(全国・頭)", "うち捕殺(頭)", "出没100件あたりの捕獲(北海道を除く・頭)", "ツキノワグマ(頭)", "ヒグマ(頭)"],
                       "rows": [[common.fy(y), f"{nat_s[y]:,}", f"{nat_c[y][0]:,}", f"{nat_c[y][1]:,}", f"{ratio[y]:.0f}", f"{tsuki[y]:,}", f"{hok[y]:,}"] for y in YEARS],
                       "note": "許可捕獲数は北海道(ヒグマ)を含む全国の頭数です。環境省の出没件数の表には北海道の数値がないため、「100件あたり」は、北海道の捕獲数を除いた頭数を、出没件数で割っています。"}},
            {"h2": "道府県別(4年度の合計)",
             "paragraphs": [f"4年度の出没件数の合計が{MIN_POOLED:,}件以上の道府県を、出没件数の多い順に並べました。右端の列は、令和4・5・6・7年度それぞれの、出没100件あたりの捕獲頭数です。"],
             "table": {"head": ["道府県", "出没件数(4年度)", "許可捕獲数(頭)", "100件あたり(頭)", "年度別(R4/R5/R6/R7)"], "rows": rows,
                       "note": "出没件数の数え方も、許可捕獲の運用も、都道府県で違います。同じ県の年度どうしを比べるときの目安として見てください。"}},
            {"h2": "出没が増えた年度の、捕獲の増え方",
             "paragraphs": [f"出没件数が最も多かった{common.fy(big)}は、最も少なかった{common.fy(min(YEARS, key=lambda y: nat_s[y]))}の{nat_s[big] / min(nat_s.values()) if False else nat_s[big] / nat_s[min(YEARS, key=lambda y: nat_s[y])]:.1f}倍の出没件数でした。北海道を除く許可捕獲数は{(nat_c[big][0] - hok_cap[big]) / (nat_c[sm][0] - hok_cap[sm]):.1f}倍です。",
                            "出没件数と許可捕獲数は、年度ごとに同じ方向に動いています(出没が多い年度は、捕獲も多い)。ただし、どちらが先に増えたのか、捕獲が出没を減らしたのかは、この年ごとの合計からは言えません。"]},
        ],
        "method": [
            "環境省「クマの許可捕獲数(速報値)」の都道府県別・年度別の頭数(捕獲数・捕殺・非捕殺)と、「クマの出没情報(速報値)」の年度ごとの合計を使いました。対象は、公表が済んだ令和4〜7年度の4年度です。令和8年度は" + f"{cap_as_of}までの暫定値のため含めていません。",
            f"出没100件あたりの捕獲数は、許可捕獲数を出没件数で割って100倍し、整数に丸めました。道府県は、4年度の出没件数の合計が{MIN_POOLED:,}件以上のものです。北海道は、環境省の出没件数の表に数値がないため、道府県別の表には入れていません。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開き、出没情報と許可捕獲数が掲載されていることを確かめました。",
        ],
        "caveats": [
            "許可捕獲数は頭数、出没件数は件数で、単位が違います。捕獲された頭数が、出没として報告された件数の一部であるとは限りません(捕獲は、報告のない場所でも行われます)。「100件あたり」は、割合ではなく、2つの数字の比です。",
            "捕獲数は、環境省が都道府県などから聞き取った速報値で、後から変更されることがあります。許可の出し方や、捕獲の体制は、県によって違います。",
            "この比の大小で、捕獲が適切かどうか、出没を減らす効果があるかどうかは言えません。個々の捕獲の理由(被害防止か数の調整か)の内訳も、この分析では見ていません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/capture_vs_sightings.py",
        "related": [{"label": "許可捕獲数のランキング", "href": "/ranking/captures/"}, {"label": "出没件数ランキング", "href": "/ranking/sightings/"},
                    {"label": "全国の推移", "href": "/trend/"}, {"label": "緊急銃猟と死亡事故", "href": "/emergency/"}],
    }
    common.write_note(doc)
    print(ratio, lo, hi, over, kill)


if __name__ == "__main__":
    main()
