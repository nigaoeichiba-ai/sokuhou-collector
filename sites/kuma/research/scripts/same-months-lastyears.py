"""Research note: is April-September of 令和8年度 high or low against the same months of the past four years, and did it come early?  Ministry of the Environment table.

python sites/kuma/research/scripts/same-months-lastyears.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07", "R08"]
MOE_OPENED = "2026-11-23"          # the day the Ministry's page was opened: 出没情報 listed as 速報値 up to September, updated 2026-11-10
MIN_TOTAL = 200                     # prefectures that reached 200 in April-September in at least one year


def main() -> None:
    env = common.load_env()
    s = env["sightings"]
    updated = s["updated"]
    nat = s["national"]["monthly"]
    n_tot = {y: sum(nat[y][:6]) for y in YEARS}
    n_early = {y: sum(nat[y][:3]) for y in YEARS}
    n_late = {y: sum(nat[y][3:6]) for y in YEARS}
    n_share = {y: common.pct(n_early[y], n_tot[y], 1) for y in YEARS}
    n_peak = {y: nat[y][:6].index(max(nat[y][:6])) + 4 for y in YEARS}
    assert n_peak["R07"] == 7 and all(n_peak[y] == 6 for y in ("R04","R05","R06","R08")) and nat["R08"][2] == max(nat["R08"][:6])
    assert max(n_tot, key=n_tot.get) == "R08" and n_tot["R08"] > n_tot["R07"]

    prefs = []
    for p in s["prefectures"]:
        m = p["monthly"]
        if any(x is None for y in YEARS for x in m[y][:6]):
            continue
        t = {y: sum(m[y][:6]) for y in YEARS}
        if max(t.values()) < MIN_TOTAL:
            continue
        a = {y: sum(m[y][:3]) for y in YEARS}
        b = {y: sum(m[y][3:6]) for y in YEARS}
        rank = sorted(YEARS, key=lambda y: -t[y]).index("R08") + 1
        prefs.append({"name": p["name"], "t": t, "a": a, "b": b, "rank": rank,
                      "sh7": a["R07"] / t["R07"] * 100, "sh8": a["R08"] / t["R08"] * 100})
    prefs.sort(key=lambda q: -q["t"]["R08"])
    n = len(prefs)
    early_up = sum(1 for q in prefs if q["a"]["R08"] > q["a"]["R07"])
    late_down = sum(1 for q in prefs if q["b"]["R08"] < q["b"]["R07"])
    late_up = n - late_down
    first = [q["name"] for q in prefs if q["rank"] == 1]
    share_up = sum(1 for q in prefs if q["sh8"] > q["sh7"])
    both_pat = [q["name"] for q in prefs if q["a"]["R08"] > q["a"]["R07"] and q["b"]["R08"] < q["b"]["R07"]]
    both_up = [q["name"] for q in prefs if q["a"]["R08"] > q["a"]["R07"] and q["b"]["R08"] >= q["b"]["R07"]]
    total_pref_n = len([p for p in s["prefectures"] if all(x is not None for y in YEARS for x in p["monthly"][y][:6])])

    rows = []
    for q in prefs:
        rows.append([q["name"], f"{q['t']['R07']:,}件", f"{q['t']['R08']:,}件", f"{q['t']['R08'] / q['t']['R07']:.2f}倍",
                     f"{q['a']['R08'] / q['a']['R07']:.2f}倍", f"{q['b']['R08'] / q['b']['R07']:.2f}倍", f"{q['rank']}位"])
    head = ["都道府県", "令和7年度4〜9月", "令和8年度4〜9月", "全体の比", "4〜6月の比", "7〜9月の比", "5年度での順位"]

    yrows = [[common.fy(y), f"{n_tot[y]:,}件", f"{n_early[y]:,}件", f"{n_late[y]:,}件", f"{n_share[y]:.1f}%", f"{n_peak[y]}月"] for y in YEARS]
    yhead = ["年度", "4〜9月の合計", "4〜6月", "7〜9月", "4〜6月の割合", "月別の最多"]

    r8_late_ratio = n_late["R08"] / n_late["R07"]
    r8_early_ratio = n_early["R08"] / n_early["R07"]
    today = common.today().isoformat()
    f = lambda x: f"{x:,}"

    doc = {
        "slug": "same-months-lastyears", "date": today, "data_as_of": updated,
        "title": "今年度の4〜9月は、過去4年度の同じ期間と比べて多いのか",
        "h1": "今年度の4〜9月は、過去4年度の同じ期間と比べて多いのか",
        "description": (f"環境省の月別の表で、令和4〜8年度の4〜9月の出没件数を比べました。令和8年度は{f(n_tot['R08'])}件で5年度のなかで最多、"
                        f"ただし4〜6月に{n_share['R08']:.0f}%が集中し、7〜9月は前の年度の{r8_late_ratio:.2f}倍でした。"),
        "lead": (f"今年は熊が多いと聞きます。環境省の表で、令和4年度から令和8年度までの4〜9月を並べます。令和8年度の{f(n_tot['R08'])}件は5年度のなかで最も多く、"
                 f"令和7年度の{f(n_tot['R07'])}件とほぼ同じ水準です。違うのは出方です。令和8年度は4〜6月に全体の{n_share['R08']:.0f}%が集まり、7〜9月は令和7年度の{r8_late_ratio:.2f}倍にとどまりました。"
                 f"これは9月までの話で、令和7年度に件数が跳ね上がった10月以降は、まだ表にありません。"),
        "findings": [
            f"4〜9月の全国の合計は、令和4年度{f(n_tot['R04'])}件、5年度{f(n_tot['R05'])}件、6年度{f(n_tot['R06'])}件、7年度{f(n_tot['R07'])}件、8年度{f(n_tot['R08'])}件です。令和8年度が最多で、令和7年度との差は{n_tot['R08'] - n_tot['R07']:+d}件でした。",
            f"4〜6月が4〜9月に占める割合は、令和8年度が{n_share['R08']:.1f}%で、ほかの4年度の{min(n_share[y] for y in YEARS[:4]):.1f}〜{max(n_share[y] for y in YEARS[:4]):.1f}%を上回りました。4〜6月は令和7年度の{r8_early_ratio:.2f}倍、7〜9月は{r8_late_ratio:.2f}倍です。",
            f"4〜9月に200件以上を記録した年度のある{n}道府県のうち、4〜6月が令和7年度より多いのは{early_up}、7〜9月が令和7年度より少ないのは{late_down}です。令和8年度が5年度のなかで最多なのは、{'・'.join(first)}の{len(first)}県でした。",
        ],
        "sections": [
            {"h2": "全国の4〜9月を、5年度で並べる",
             "paragraphs": [
                 f"環境省は、クマの出没件数を都道府県別・月別に公表しています。令和8年度の表は、{updated}に更新され、9月までの数字があります。比べるため、どの年度も4月から9月までの6か月だけを取り出しました。令和7年度や5年度は10月に件数が大きく増えているので、年間の合計で比べると、今年度の途中経過と並べられません。",
                 f"全国の4〜9月の合計は、令和4年度の{f(n_tot['R04'])}件から、令和8年度の{f(n_tot['R08'])}件まで、年度ごとに増えてきました。令和8年度は令和7年度より{n_tot['R08'] - n_tot['R07']}件多いだけで、ほぼ同じです。",
                 f"月別の最多は、令和7年度だけが{n_peak['R07']}月で、ほかの4年度は{n_peak['R04']}月でした。"],
             "table": {"head": yhead, "rows": yrows, "note": "環境省の表(速報値)の全国の合計です。4〜6月の割合は、4〜9月の合計に対する4〜6月の件数の割合です。"},
             "chart": {"kind": "bars", "labels": [common.fy(y) for y in YEARS], "values": [n_share[y] for y in YEARS], "title": "4〜9月のうち4〜6月が占める割合(%)",
                       "desc": f"令和4〜8年度の全国の出没件数で、4〜9月の合計に対する4〜6月の割合を示した棒グラフ。令和4〜6年度は40%台、令和7年度は35%、令和8年度は{n_share['R08']:.0f}%で最も高い。"}},
            {"h2": "今年は4〜6月に集まり、7〜9月は少ない",
             "paragraphs": [
                 f"令和8年度の4〜6月は{f(n_early['R08'])}件で、令和7年度の同じ3か月({f(n_early['R07'])}件)の{r8_early_ratio:.2f}倍です。一方、7〜9月は{f(n_late['R08'])}件で、令和7年度の{f(n_late['R07'])}件の{r8_late_ratio:.2f}倍でした。",
                 f"4〜6月が全体に占める割合は、令和8年度が{n_share['R08']:.1f}%です。令和4年度から令和7年度までは{min(n_share[y] for y in YEARS[:4]):.1f}〜{max(n_share[y] for y in YEARS[:4]):.1f}%で、令和7年度は{n_share['R07']:.1f}%と夏から秋に寄っていました。令和8年度は、これと逆の形になっています。",
                 f"月別では、令和8年度は6月が{f(nat['R08'][2])}件で最多でした。7月は{f(nat['R08'][3])}件、8月は{f(nat['R08'][4])}件、9月は{f(nat['R08'][5])}件と、夏が深まるほど減っています。"],
            },
            {"h2": "道府県で見ても、同じ形が多い",
             "paragraphs": [
                 f"4〜9月に200件以上を記録した年度のある{n}道府県に絞ります。表に月別の数字がそろうのは{total_pref_n}道府県で、その一部です。4〜6月が令和7年度より多いのは{early_up}で、すべてです。7〜9月が令和7年度より少ないのは{late_down}、多いか同じなのは{late_up}でした。",
                 f"4〜6月が4〜9月に占める割合が令和7年度より高いのは、{n}道府県のうち{share_up}です。4〜6月が増えて7〜9月が減ったのは、" + "・".join(both_pat) + "でした。",
                 "4〜6月も7〜9月も増えたのは、" + "・".join(both_up) + "です。西日本と近畿では、夏にも件数が多い道府県が目立ちます。",
                 f"令和8年度の4〜9月が、5年度のなかで最多なのは、{'・'.join(first)}の{len(first)}県です。"],
             "table": {"head": head, "rows": rows, "note": "環境省の表(速報値)で、4〜9月の件数に月別の数字がそろい、5年度のどこかで200件以上あった道府県です。比は令和8年度を令和7年度で割った値です。順位は、令和4〜8年度の4〜9月の件数が、令和8年度で何番目に多いかです。"}},
            {"h2": "この数字だけでは言えないこと",
             "paragraphs": [
                 f"この表は、9月までです。令和7年度は10月に{f(nat['R07'][6])}件、11月に{f(nat['R07'][7])}件と、秋に件数が大きく増えました。令和8年度の10月以降がどうなるかは、まだ表にありません。4〜9月が多かったことは、年度全体が多くなることを意味しません。",
                 "4〜6月に件数が集まった理由も、この表からは分かりません。環境省の表は件数だけで、山での餌の量や人の動き、記録の取り方が変わったかどうかは含まれていません。",
                 "件数は、通報や記録のされ方にも左右されます。報告が増えれば、同じ出没でも件数は増えます。出没の数そのものが増えたのかどうかは、言えません。"],
            },
            {"h2": "この数字の使い方",
             "paragraphs": [
                 f"夏の件数が前の年度より少なくても、山や里に出ていないとは限りません。秋は、令和5年度の10月({f(nat['R05'][6])}件)や令和7年度の10月のように、件数が急に増える年があります。",
                 "お住まいの県の月ごとの動きは、このサイトの月別の記録と、市町や県の最新の公表で確認してください。"],
            },
        ],
        "method": [
            f"環境省の「クマの出没情報(速報値)」の都道府県別・月別の表を使いました。表の更新日は{updated}で、令和8年度は9月までの数字があります。環境省の公表ページは、{MOE_OPENED}に開いて、出没情報が9月までの速報値として{updated}更新で載っていることを確認しています。計算した日は{today}です。",
            "令和4〜8年度のそれぞれで、4〜9月の6か月分を足しました。4〜6月と7〜9月に分け、令和8年度を令和7年度で割った比を出しています。",
            f"道府県の表は、4〜9月の6か月とも数字がある道府県のうち、5年度のどこかで4〜9月が{MIN_TOTAL}件以上だった{n}道府県です。件数が少ない県は、1件の増減で比が大きく動くため、除きました。",
            "環境省の表の数字は速報値で、後から改訂されることがあります。計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "9月までの比較です。10月以降の件数は、令和8年度の表にまだありません。令和7年度は10月に大きく増えています。",
            "件数が増えた・減った理由は、この表からは言えません。記録や通報のされ方の違いも含みます。",
            "環境省の表は速報値で、後から改訂されることがあります。",
            f"件数の少ない県は除いた{n}道府県です。北海道は、この表に月別の数字がないため対象外です。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/same-months-lastyears.py",
        "related": [{"label": "熊の出没は10月から11月にかけてどれだけ減るか(環境省の表)", "href": "/research/month-ratio-autumn/"},
                    {"label": "熊の出没が急に増えた年は、どの県で何倍になったか", "href": "/research/big-year/"},
                    {"label": "熊の出没のピークは、夏か秋か", "href": "/research/peak-month-type/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print({"tot": n_tot, "share": n_share, "early_up": early_up, "late_down": late_down, "n": n, "first": first, "both_pat": both_pat, "both_up": both_up, "share_up": share_up, "total_pref_n": total_pref_n})


main()
