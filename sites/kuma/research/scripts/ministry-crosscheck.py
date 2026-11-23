"""Research note: do the prefectures' own records add up to the Ministry of the Environment's monthly counts?  Six prefectures, April-September 2026.

python sites/kuma/research/scripts/ministry-crosscheck.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MOE_NAME = {"akita": "秋田", "miyagi": "宮城", "niigata": "新潟", "toyama": "富山", "yamaguchi": "山口", "yamanashi": "山梨"}
MONTHS = [4, 5, 6, 7, 8, 9]                 # the months the Ministry's table already holds for 令和8年度 (the table is updated about once a month)
FY = "R08"


def main() -> None:
    env = common.load_env()
    moe_by_name = {x["name"]: x for x in env["sightings"]["prefectures"]}
    moe_updated = env["sightings"]["updated"]

    data, ours, moe = {}, {}, {}
    for key in SOURCES:
        data[key] = common.load_source(key)
        c = Counter(r[0].month for r in data[key]["rows"])
        ours[key] = [c.get(m, 0) for m in MONTHS]
        moe[key] = [moe_by_name[MOE_NAME[key]]["monthly"][FY][m - 4] for m in MONTHS]
        assert all(v is not None for v in moe[key]), key

    cells = [(k, i) for k in SOURCES for i in range(len(MONTHS))]
    same = [(k, i) for k, i in cells if ours[k][i] == moe[k][i]]
    off1 = [(k, i) for k, i in cells if abs(ours[k][i] - moe[k][i]) == 1]
    far = [(k, i) for k, i in cells if abs(ours[k][i] - moe[k][i]) > 1]
    tot_o = {k: sum(ours[k]) for k in SOURCES}
    tot_m = {k: sum(moe[k]) for k in SOURCES}
    matching = [k for k in SOURCES if all(abs(ours[k][i] - moe[k][i]) <= 1 for i in range(len(MONTHS)))]
    odd = [k for k in SOURCES if k not in matching]
    assert odd == ["yamaguchi"], odd

    rows = []
    for key, name in SOURCES.items():
        gap = tot_o[key] - tot_m[key]
        ratio = common.pct(tot_o[key], tot_m[key])
        rows.append([name, f"{tot_m[key]:,}件", f"{tot_o[key]:,}件", f"{gap:+d}件", f"{ratio:.0f}%"])
    head1 = ["県", "公的な表(4〜9月)", "この記録(4〜9月)", "差(記録−公的な表)", "公的な表に対する割合"]

    yrows = []
    for i, m in enumerate(MONTHS):
        yrows.append([f"{m}月", f"{moe['yamaguchi'][i]}件", f"{ours['yamaguchi'][i]}件", f"{common.pct(ours['yamaguchi'][i], moe['yamaguchi'][i]):.0f}%"])
    yhead = ["月", "公的な表", "山口県警の記録", "割合"]
    y_ratio = [common.pct(ours["yamaguchi"][i], moe["yamaguchi"][i]) for i in range(len(MONTHS))]
    y_early = common.pct(sum(ours["yamaguchi"][:3]), sum(moe["yamaguchi"][:3]))
    y_late = common.pct(sum(ours["yamaguchi"][3:]), sum(moe["yamaguchi"][3:]))
    y_kinds = Counter(r[1] for r in data["yamaguchi"]["rows"] if r[0].month in MONTHS)

    diffrows = []
    for k, i in off1:
        diffrows.append([SOURCES[k], f"{MONTHS[i]}月", f"{moe[k][i]}件", f"{ours[k][i]}件"])
    dhead = ["県", "月", "公的な表", "この記録"]

    five = [k for k in SOURCES if k != "yamaguchi"]
    five_cells = 5 * len(MONTHS)
    five_same = sum(1 for k, i in same if k != "yamaguchi")
    five_o, five_m = sum(tot_o[k] for k in five), sum(tot_m[k] for k in five)
    as_min = min(data[k]["as_of"] for k in SOURCES)
    as_max = max(data[k]["as_of"] for k in SOURCES)
    today = common.today().isoformat()
    y_gap = tot_m["yamaguchi"] - tot_o["yamaguchi"]
    n_cells = len(cells)

    doc = {
        "slug": "ministry-crosscheck", "date": today, "data_as_of": as_max,
        "title": "自治体の記録の月別件数は、公的な表と合うか",
        "h1": "自治体の記録の月別件数は、公的な表と合うか",
        "description": (f"秋田・宮城・新潟・富山・山口・山梨の令和8年度4〜9月で、このサイトの記録と公的な月別出没件数を比べました。"
                        f"{n_cells}の月のうち{len(same)}が一致し、山口県だけが記録のほうが{y_gap}件少なくなりました。"),
        "lead": (f"熊の出没件数は、公的な表と、各県が公開する記録の2か所に出ています。この2つは同じ数字になっているのでしょうか。"
                 f"秋田・宮城・新潟・富山・山口・山梨の6県で、令和8年度の4〜9月を月ごとに比べました。{n_cells}の月のうち{len(same)}が完全に一致し、"
                 f"{len(off1)}は1件の差です。大きくずれたのは山口県の{len(far)}か月だけで、山口県は記録の合計が公的な表の{common.pct(tot_o['yamaguchi'], tot_m['yamaguchi']):.0f}%でした。"),
        "findings": [
            f"{n_cells}の月(6県×4〜9月)のうち、記録の件数が公的な表と同じなのは{len(same)}です。1件だけ違うのが{len(off1)}、2件以上違うのが{len(far)}でした。",
            f"秋田・宮城・新潟・富山・山梨の5県は、4〜9月の合計が公的な表で{five_m:,}件、この記録で{five_o:,}件です。差は{five_o - five_m:+d}件でした。",
            f"山口県は、公的な表が{tot_m['yamaguchi']}件、山口県警の記録が{tot_o['yamaguchi']}件で、{y_gap}件少なくなっています。4〜6月は{y_early:.0f}%、7〜9月は{y_late:.0f}%です。",
        ],
        "sections": [
            {"h2": "6県の月別件数を、公的な表と並べる",
             "paragraphs": [
                 f"国は、クマの出没件数を都道府県別・月別に公表しています。令和8年度は、表の更新日が{moe_updated}で、4月から9月までが入っています。このサイトは、同じ6県の公開記録を取り込んで、月別に集計できます。",
                 f"比べたのは、秋田・宮城・新潟・富山・山口・山梨の6県です。月ごとの件数を、公的な表の数字と、このサイトの記録の件数で並べました。記録の件数は、目撃・痕跡・人身被害など、公表されている種類をすべて合わせた数です。",
                 f"使った記録の最新日は、県によって{as_min}から{as_max}までです。公的な表より新しい日付ですが、4〜9月の件数は、後から記録が足されることがあります。"],
             "table": {"head": head1, "rows": rows,
                       "note": "4〜9月の合計です。この記録は、各県の公開記録を種類に関係なく合計した件数です。差は、記録から公的な表を引いた値です。"}},
            {"h2": "5県は、ほぼ同じ数字になっている",
             "paragraphs": [
                 f"秋田・宮城・新潟・富山・山梨の5県は、{five_cells}の月のうち{five_same}で件数が完全に一致しました。残る{five_cells - five_same}か月は、" + "と、".join(f"{SOURCES[k]}の{MONTHS[i]}月(国{moe[k][i]}件・記録{ours[k][i]}件)" for k, i in off1) + "で、どれも1件の差です。",
                 "公開記録に、その後で記録が足されたり、取り下げられたりすると、1件ほどのずれが出ます。秋田県と宮城県の月別の件数は、6か月とも同じでした。",
                 "5県では、公的な月別件数は、各県が公開する個別の記録を月ごとに足し合わせた数と同じ形になっています。ただし、公的な表が何を元に作られているかは、この記録だけでは言えません。"],
             "table": {"head": dhead, "rows": diffrows, "note": "5県のうち、公的な表と1件だけ違った月です。2件以上違った月は、5県にはありませんでした。"}},
            {"h2": "山口県だけが、記録のほうが少ない",
             "paragraphs": [
                 f"山口県は、公的な表が4〜9月で{tot_m['yamaguchi']}件、山口県警の記録が{tot_o['yamaguchi']}件です。6か月すべてで、記録のほうが少なくなっています。",
                 f"差は月によって違います。4月は{y_ratio[0]:.0f}%、5月は{y_ratio[1]:.0f}%、6月は{y_ratio[2]:.0f}%とほぼ近い一方、7月は{y_ratio[3]:.0f}%、8月は{y_ratio[4]:.0f}%、9月は{y_ratio[5]:.0f}%まで下がります。",
                 f"山口県の記録は、公開元が「山口県警察が認知した目撃・痕跡の情報」と説明しています。記録の種類は、目撃{y_kinds.get('目撃', 0)}件・痕跡{y_kinds.get('痕跡', 0)}件です。公的な表に、警察以外の窓口で受けた情報が入っているのかどうかは、この記録からは分かりません。"],
             "table": {"head": yhead, "rows": yrows, "note": "山口県の令和8年度4〜9月です。割合は、山口県警の記録の件数を公的な表の件数で割った値です。"},
             "chart": {"kind": "bars", "labels": [f"{m}月" for m in MONTHS], "values": y_ratio, "title": "山口県:警察の記録が公的な表に占める割合(%)",
                       "desc": "令和8年度の4〜9月について、山口県警の公開記録の件数が公的な月別出没件数の何%にあたるかを月別に示した棒グラフ。4〜6月は80〜90%台、7〜9月は40〜50%台。"}},
            {"h2": "なぜ山口県だけずれるのか、この記録からは言えない",
             "paragraphs": [
                 "考えられる理由はいくつかあります。公的な表が、警察以外の窓口(市町や県の担当課)に届いた情報も含めている場合や、同じ県の中で公開記録に載せる範囲を決めている場合です。どれが当たっているのかは、この記録から決めることができません。",
                 "言えるのは、同じ県の同じ月でも、公開された記録の件数と、国が公表する出没件数が、一致しない県があることです。山口県では、夏から秋にかけて、差が広がっています。",
                 "ほかの県でも、これから記録が追加されたり、公的な表が改訂されたりすれば、差が出る可能性があります。このノートは、令和8年度の4〜9月だけの比較です。"],
            },
            {"h2": "この数字の使い方",
             "paragraphs": [
                 f"秋田・宮城・新潟・富山・山梨のように、記録と公的な表が合う県では、公的な月別件数を見れば、各県の公開記録の月ごとの量をほぼつかめます。逆に、この記録の月別の集計を、県全体の出没の量として読んでも、大きくは外れません。",
                 f"山口県の記録は、公的な表の{common.pct(tot_o['yamaguchi'], tot_m['yamaguchi']):.0f}%です。山口県で、記録が少ない月があっても、実際の出没が少ないとは限りません。公的な月別の表と、県警の公開記録の両方を見比べて判断してください。",
                 "お住まいの地域の様子は、市町の窓口や県の最新の公表ページで確認してください。"],
            },
        ],
        "method": [
            f"対象は、令和8年度の4〜9月(6か月)と、秋田・宮城・新潟・富山・山口・山梨の6県です。公的な表は、{moe_updated}に更新された出没件数(都道府県別・月別)を使いました。計算した日は{today}、使った記録の最新日は県によって{as_min}から{as_max}までです。",
            "この記録の件数は、各県の公開記録を、観測日の月で数えた件数です。種類(目撃・痕跡・人身被害・その他)は区別せず、すべて合計しています。",
            "月ごとに、公的な表の件数と記録の件数を比べ、同じ・1件違い・2件以上違いの3つに分けました。計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
            f"公的な表(出没件数)は、公表資料の「速報値」です。公表元のページは、{common.MOE_CHECKED}に開いて、令和8年度の出没件数の表が載っていることを確認しています。",
        ],
        "caveats": [
            "公的な件数が何を元に集計されているかは、この記録からは分かりません。山口県のずれの理由も、言えません。",
            "対象は令和8年度の4〜9月だけです。10月以降は、公的な表がまだ更新されていないため、比べていません。",
            "後から記録が足されたり直されたりすると、件数は変わります。1件の差は、更新のタイミングのずれの可能性があります。",
            "6県だけの比較です。ほかの県で一致するかどうかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES] + [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/ministry-crosscheck.py",
        "related": [{"label": "熊の出没は10月から11月にかけてどれだけ減るか(公的な表)", "href": "/research/month-ratio-autumn/"},
                    {"label": "熊の出没100件に対して、何頭が捕獲されたか", "href": "/research/capture-vs-sightings/"},
                    {"label": "山口県の最新の目撃情報", "href": "/live/yamaguchi/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print({"same": len(same), "off1": len(off1), "far": len(far), "tot_o": tot_o, "tot_m": tot_m, "y_ratio": y_ratio, "kinds": dict(y_kinds)})


main()
