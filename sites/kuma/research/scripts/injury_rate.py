"""Research note: how many people were injured per 1,000 sightings?  Ministry of the Environment: sightings (monthly table, yearly totals) and injuries (件数・人数・死亡), R04-R07.

The injury statistic is counted on one national standard; the sightings are counted by each prefecture its own way, so a ratio is read within a prefecture over the years,
not between prefectures (the note says so).

python sites/kuma/research/scripts/injury_rate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07"]
MIN_POOLED = 2000          # sightings over the four years: below this a ratio moves with one or two people


def main() -> None:
    env = common.load_env()
    S, I = env["sightings"], env["injuries"]
    by_inj = {p["name"]: p["by_year"] for p in I["prefectures"]}
    nat_s, nat_i = S["national"]["total"], I["national"]
    rate = {y: nat_i[y][1] / nat_s[y] * 1000 for y in YEARS}
    rows, stats = [], {}
    for p in S["prefectures"]:
        t = p["total"]
        if any(t[y] is None for y in YEARS):
            continue
        pooled = sum(t[y] for y in YEARS)
        if pooled < MIN_POOLED:
            continue
        inj = sum(by_inj[p["name"]][y][1] for y in YEARS)
        dead = sum(by_inj[p["name"]][y][2] for y in YEARS)
        per_year = [by_inj[p["name"]][y][1] / t[y] * 1000 for y in YEARS]
        stats[p["name"]] = dict(pooled=pooled, inj=inj, dead=dead, rate=inj / pooled * 1000, per_year=per_year)
        rows.append([common.full_name(p["name"]), f"{pooled:,}", f"{inj}", f"{inj / pooled * 1000:.1f}", f"{dead}",
                     " / ".join(f"{v:.1f}" for v in per_year)])
    rows_sorted = sorted(zip(rows, stats), key=lambda t: -stats[t[1]]["pooled"])
    rows = [r for r, _ in rows_sorted]
    order = sorted(stats, key=lambda k: stats[k]["rate"])
    lo, hi = order[0], order[-1]
    pooled_nat = sum(nat_s[y] for y in YEARS)
    inj_nat = sum(nat_i[y][1] for y in YEARS)
    big, small = max(YEARS, key=lambda y: nat_s[y]), min(YEARS, key=lambda y: nat_s[y])
    sec = sorted(YEARS, key=lambda y: -nat_s[y])[1]
    full = common.full_name
    data_as_of = max(S["updated"], I["updated"])
    inj_as_of = I["as_of"].replace("R08年", "令和8年")
    yr_text = "、".join(f"{common.fy(y)}が{rate[y]:.1f}人" for y in YEARS)

    doc = {
        "slug": "injury-rate", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": "熊(クマ)の出没1,000件あたり、何人が被害に遭ったか。環境省の統計で、4年度分を数える",
        "h1": "出没が増えると、被害も増えるのか。出没1,000件あたりの人身被害を数える",
        "description": f"環境省の出没件数と人身被害の人数(令和4〜7年度)から、出没1,000件あたりの被害者数を全国と{len(stats)}道府県で数えました。全国は{min(rate.values()):.1f}〜{max(rate.values()):.1f}人で、年度で{max(rate.values()) / min(rate.values()):.1f}倍違います。",
        "lead": ("出没の件数が増えた年は、人身被害も増えるのでしょうか。環境省は、出没件数と人身被害の人数を、別の表で公表しています。"
                 f"令和4年度から令和7年度の4年度分を重ねて、出没1,000件あたりの被害者数を、全国と、出没件数の多い{len(stats)}道府県で数えました。"),
        "findings": [
            f"全国の出没1,000件あたりの被害者数は、{yr_text}でした。出没が最も多かった{common.fy(big)}({nat_s[big]:,}件)の比率は{rate[big]:.1f}人、最も少なかった{common.fy(small)}({nat_s[small]:,}件)は{rate[small]:.1f}人です。",
            f"出没が2番目に多かった{common.fy(sec)}({nat_s[sec]:,}件、被害者{nat_i[sec][1]}人)と{common.fy(big)}を比べると、出没件数は{nat_s[big] / nat_s[sec]:.1f}倍、被害者数は{nat_i[big][1] / nat_i[sec][1]:.1f}倍です。1,000件あたりは{rate[sec]:.1f}人から{rate[big]:.1f}人に変わりました。"
            f"4年度合計では、出没{pooled_nat:,}件に対して被害者は{inj_nat:,}人(1,000件あたり{inj_nat / pooled_nat * 1000:.1f}人)です。",
            f"{len(stats)}道府県を4年度合計で比べると、1,000件あたりの被害者数がいちばん少ないのは{full(lo)}({stats[lo]['rate']:.1f}人)、いちばん多いのは{full(hi)}({stats[hi]['rate']:.1f}人)でした。ただし、出没件数の数え方が県で違うため、この大小は県どうしの危険の違いを表しません。",
        ],
        "sections": [
            {"h2": "全国の、出没件数と被害者数",
             "paragraphs": ["年度ごとに、全国の出没件数と、人身被害の件数・人数・死亡者数を並べました。人身被害は、環境省が全国で同じ基準(件数・人数・死亡者数)で数えています。出没件数は、都道府県が聞き取った速報値です。"],
             "table": {"head": ["年度", "出没件数", "人身被害の件数", "被害者数(人)", "うち死亡(人)", "出没1,000件あたりの被害者数"],
                       "rows": [[common.fy(y), f"{nat_s[y]:,}", f"{nat_i[y][0]}", f"{nat_i[y][1]}", f"{nat_i[y][2]}", f"{rate[y]:.1f}"] for y in YEARS],
                       "note": f"人身被害は{inj_as_of}の速報値のうち、令和4〜7年度の確定した年度です。"}},
            {"h2": "出没1,000件あたりの被害者数(全国)",
             "paragraphs": [f"出没件数は年度で{max(nat_s[y] for y in YEARS) / min(nat_s[y] for y in YEARS):.1f}倍の差がありますが、被害者数の差は{max(nat_i[y][1] for y in YEARS) / min(nat_i[y][1] for y in YEARS):.1f}倍です。"
                            "出没が大きく増えた年度に、被害者数が同じ割合で増えているわけではありません。"],
             "chart": {"kind": "bars", "labels": [common.fy(y) for y in YEARS], "values": [round(rate[y], 1) for y in YEARS], "title": "出没1,000件あたりの被害者数(人)",
                       "desc": "令和4〜7年度の全国について、出没1,000件あたりの人身被害の被害者数を比べた棒グラフ。"}},
            {"h2": "道府県別(4年度の合計)",
             "paragraphs": [f"4年度の出没件数の合計が{MIN_POOLED:,}件以上の道府県を、出没件数の多い順に並べました。右端の列は、令和4・5・6・7年度それぞれの、出没1,000件あたりの被害者数です。件数が少ない年度は、被害者が1人増えるだけで比率が大きく動きます。"],
             "table": {"head": ["道府県", "出没件数(4年度)", "被害者数(人)", "1,000件あたり", "うち死亡(人)", "年度別(R4/R5/R6/R7)"], "rows": rows,
                       "note": "出没件数の数え方は、都道府県ごとに違います。この表の「1,000件あたり」は、同じ県の中で年度を比べるときの目安です。"}},
        ],
        "method": [
            "環境省「クマの出没情報(速報値)」の年度ごとの合計(都道府県別・全国)と、「クマによる人身被害件数(速報値)」の被害者数・死亡者数を使いました。対象は、どちらも公表が済んだ令和4〜7年度です。令和8年度は、年度の途中のため含めていません。",
            "出没1,000件あたりの被害者数は、被害者数を出没件数で割って1,000倍し、小数第1位まで示しました。道府県は、4年度の出没件数の合計が2,000件以上のものだけです。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開き、出没情報と人身被害件数が掲載されていることを確かめました。",
        ],
        "caveats": [
            "出没件数の数え方は、都道府県で違います(目撃のみ・痕跡を含む・通報の受け付けなど)。比率が低い県は、危険が小さいと言えるわけではなく、件数を多めに数える県ほど比率は低く出ます。",
            "人身被害は、環境省が把握した件数です。被害の状況(山や農地・住宅の周りなど)や原因は、この表には含まれていません。",
            "4年度の数字です。比率の違いが、出没の増減に伴う変化なのか、年度ごとの偶然なのかは、この記録だけでは言えません。個人の行動の目安にもなりません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/injury_rate.py",
        "related": [{"label": "人身被害ランキング", "href": "/ranking/injuries/"}, {"label": "出没件数ランキング", "href": "/ranking/sightings/"},
                    {"label": "全国の推移", "href": "/trend/"}, {"label": "クマに出会ったときの行動", "href": "/guide/encounter/"}],
    }
    common.write_note(doc)
    print({y: round(rate[y], 2) for y in YEARS}, sec, lo, hi)


if __name__ == "__main__":
    main()
