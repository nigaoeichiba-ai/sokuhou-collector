"""Research note: do bears show up in new towns in September?  For six prefectures, the towns with a record in September 2026 against the towns with a record from 1 April to 31 August.
New towns (September only), towns that went quiet (April-August only), and the share of September records that fall in towns already on the list.
Reference: the same records with the 'September' label shuffled among them (1,000 draws, fixed seed).

python sites/kuma/research/scripts/new-towns.py
"""
from __future__ import annotations

import random
import statistics
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
SEP1, SEP30 = date(2026, 9, 1), date(2026, 9, 30)
DRAWS = 1000


def split(towns: list[str], flags: list[bool]) -> tuple[set[str], set[str]]:
    base = {c for c, f in zip(towns, flags) if not f}
    sep = {c for c, f in zip(towns, flags) if f}
    return base, sep


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rng = random.Random(20261028)
    stats, rows = {}, []
    for k, label in SOURCES.items():
        towns, flags = [], []
        for r in data[k]["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if r[2] and d <= SEP30:
                towns.append(r[2])
                flags.append(d >= SEP1)
        base, sep = split(towns, flags)
        new, gone = sep - base, base - sep
        base_count = Counter(c for c, f in zip(towns, flags) if not f)
        n_sep = sum(flags)
        in_new = sum(1 for c, f in zip(towns, flags) if f and c in new)
        sims_new, sims_gone = [], []
        for _ in range(DRAWS):
            fl = flags[:]
            rng.shuffle(fl)
            b, s = split(towns, fl)
            sims_new.append(len(s - b))
            sims_gone.append(len(b - s))
        sims_new.sort()
        sims_gone.sort()
        st = dict(n=len(towns), n_sep=n_sep, base=len(base), sep=len(sep), new=sorted(new), gone=len(gone), in_new=in_new,
                  prior_pct=common.pct(n_sep - in_new, n_sep, 1),
                  gone_med=statistics.median(base_count[c] for c in gone) if gone else None,
                  base_med=statistics.median(base_count.values()),
                  sim_new=(sims_new[0], sims_new[len(sims_new) // 2], sims_new[-1]),
                  sim_gone=(sims_gone[0], sims_gone[len(sims_gone) // 2], sims_gone[-1]))
        st['new_n'] = {c: sum(1 for cc, f in zip(towns, flags) if f and cc == c) for c in new}
        top_sep = Counter(c for c, f in zip(towns, flags) if f).most_common(3)
        st['top_sep'] = top_sep
        st['top_base'] = [c for c, _ in base_count.most_common(3)]
        st['top_overlap'] = len({c for c, _ in top_sep} & set(st['top_base']))
        stats[k] = st
        rows.append([label, f"{st['n']:,}", f"{st['base']}", f"{st['sep']}", f"{len(st['new'])}", f"{st['gone']}",
                     f"{st['sim_new'][0]}〜{st['sim_new'][2]}", f"{st['sim_gone'][0]}〜{st['sim_gone'][2]}"])
    total_sep = sum(st["n_sep"] for st in stats.values())
    total_new = sum(st["in_new"] for st in stats.values())
    new_names = [f"{SOURCES[k]}の{c}" for k, st in stats.items() for c in st["new"]]
    in_range = [k for k in SOURCES if stats[k]["sim_gone"][0] <= stats[k]["gone"] <= stats[k]["sim_gone"][2]]
    gone_rows = [[SOURCES[k], f"{stats[k]['gone']}", f"{stats[k]['gone_med']:g}件", f"{stats[k]['base_med']:g}件"] for k in SOURCES]
    prior_rows = [[SOURCES[k], f"{stats[k]['n_sep']}", f"{stats[k]['n_sep'] - stats[k]['in_new']}", f"{stats[k]['prior_pct']:.0f}%"] for k in SOURCES]
    as_of = max(s["as_of"] for s in data.values())
    total = sum(st["n"] for st in stats.values())
    order = sorted(SOURCES, key=lambda k: -stats[k]["gone"] / stats[k]["base"])
    lowk = [k for k in SOURCES if stats[k]["gone_med"] < stats[k]["base_med"] * 0.8]
    topk_rows = [[SOURCES[k], "、".join(f"{c}({n}件)" for c, n in stats[k]["top_sep"]), "、".join(stats[k]["top_base"]), f"{stats[k]['top_overlap']}"] for k in SOURCES]
    newk_rows = [[SOURCES[k], c, f"{n}件"] for k in SOURCES for c, n in stats[k]["new_n"].items()]

    doc = {
        "slug": "new-towns", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の9月の目撃は、新しい市町村に広がったか。春〜夏の記録と6県で比べる",
        "h1": "9月の熊(クマ)の目撃に、新しい市町村はどれだけ入ったか。春〜夏の記録と比べる",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の目撃記録{total:,}件で、9月の記録がある市町村を、4〜8月に記録のあった市町村と比べました。9月に初めて出た市町村は、{len(new_names)}か所です。",
        "lead": (f"秋に熊が人里に下りてくると言われます。では、9月の目撃記録は、春から夏にかけて記録のなかった市町村にも広がったのでしょうか。"
                 f"6県の記録で、4月から8月までに記録のあった市町村と、9月に記録のあった市町村を、並べて数えました。結果は、9月に初めて記録が出た市町村は6県合わせて{len(new_names)}か所だけです。"),
        "findings": [
            f"9月の記録{total_sep:,}件のうち、4〜8月にも記録のあった市町村の分は{total_sep - total_new:,}件({common.pct(total_sep - total_new, total_sep, 1)}%)でした。9月に初めて記録が出た市町村の分は{total_new}件です。",
            f"9月に初めて記録が出た市町村は、{'、'.join(new_names)}の{len(new_names)}か所です。秋田・新潟・富山は0か所でした。",
            "4〜8月に記録があって9月に記録がなかった市町村は、6県で" + "、".join(f"{SOURCES[k]}{stats[k]['gone']}か所" for k in SOURCES) + "でした。" +
            (f"9月だけの市町村の数も、4〜8月だけの市町村の数も、{'6県とも' if len(in_range) == 6 else '・'.join(SOURCES[k] for k in in_range)}、偶然に入れ替えた場合の範囲に収まっています。" if in_range else ""),
        ],
        "sections": [
            {"h2": "9月に記録がある市町村と、春〜夏に記録がある市町村",
             "paragraphs": [f"令和8年度の記録のうち、4月1日から9月30日までのものを使いました。記録を「4月1日〜8月31日」と「9月1日〜9月30日」に分け、それぞれの期間に1件でも記録のあった市町村を数えています。「9月だけ」の市町村が、9月に初めて記録が出た市町村です。「4〜8月だけ」の市町村は、春から夏には記録があって、9月には記録がなかった市町村です。",
                            f"「偶然の範囲」は、次の計算の結果です。各県の記録の市町村名はそのままにして、9月かどうかの区別だけを記録の間で入れ替えます。これを{DRAWS:,}回行い、最小値から最大値までを書きました。乱数の種は固定しています。"],
             "table": {"head": ["県", "記録件数", "4〜8月の市町村", "9月の市町村", "9月だけ", "4〜8月だけ", "9月だけ(偶然の範囲)", "4〜8月だけ(偶然の範囲)"], "rows": rows,
                       "note": "市町村の数は、記録に市町村名のあるものを数えています。記録件数は、4月1日から9月30日までの合計です。"}},
            {"h2": "9月の記録は、すでに記録のあった市町村に入っている",
             "paragraphs": [f"9月の記録を、市町村ごとに分けました。その市町村に4〜8月の記録が1件でもあれば「すでに記録のあった市町村」です。6県合わせると、9月の{total_sep:,}件のうち{total_sep - total_new:,}件が、すでに記録のあった市町村のものでした。",
                            f"9月に入って初めて熊の記録が出た町は、{len(new_names)}か所だけです。そのうち宮城県の2か所(塩竈市・涌谷町)は合わせて{stats['miyagi']['in_new']}件、山口県の光市と山梨県の甲斐市は1件ずつでした。",
                            "もうひとつ、9月に記録の多かった上位3市町村と、4〜8月に記録の多かった上位3市町村を比べました。重なっている数は、下の表の右の列です。"],
             "table": {"head": ["県", "9月の記録", "すでに記録のあった市町村の分", "割合"], "rows": prior_rows, "note": "9月の記録は、市町村名のあるものだけを数えています。"}},
            {"h2": "9月に記録が多い市町村と、春〜夏に記録が多い市町村",
             "paragraphs": ["9月の上位3市町村と、4〜8月の上位3市町村が、どれだけ重なるかを見ました。6県のうち、3つ全部が重なるのは富山県だけで、ほかの県は1〜2か所の重なりです。9月の上位は、春から夏の上位と同じ顔ぶれにはなっていません。ただし、件数の少ない県では、1件の違いで順位が入れ替わります。"],
             "table": {"head": ["県", "9月の上位3(件数)", "4〜8月の上位3", "重なる数"], "rows": topk_rows, "note": "上位3は、記録の件数が多い順です。件数が同じ市町村は、記録に先に現れた順で並べています。"}},
            {"h2": "9月に初めて記録が出た市町村",
             "paragraphs": [f"9月に初めて記録が出た{len(new_names)}か所の件数は、下の表のとおりです。{'、'.join(f'{c}は{n}件' for k in SOURCES for c, n in stats[k]['new_n'].items())}で、いずれも少ない件数です。1件の記録で「新しく出た町」になるため、数字の大きさに意味を持たせすぎないでください。"],
             "table": {"head": ["県", "市町村", "9月の記録"], "rows": newk_rows, "note": "4月1日から8月31日までに記録がなく、9月1日から30日に記録があった市町村です。"}},
            {"h2": "春〜夏だけで9月に記録がなかった市町村は、件数が少ない",
             "paragraphs": [f"逆に、4〜8月に記録があって9月にはなかった市町村は、どの県にもあります。割合では、{SOURCES[order[0]]}が{stats[order[0]]['gone']}か所({common.pct(stats[order[0]]['gone'], stats[order[0]]['base'])}%)でいちばん高く、{SOURCES[order[-1]]}が{stats[order[-1]]['gone']}か所({common.pct(stats[order[-1]]['gone'], stats[order[-1]]['base'])}%)でいちばん低くなりました。",
                            f"下の表は、9月に記録がなかった市町村の4〜8月の件数の中央値と、その県の市町村全体の中央値を比べたものです。{'・'.join(SOURCES[k] for k in lowk)}では、9月に記録がなかった市町村の件数のほうが少なくなっています。{'・'.join(SOURCES[k] for k in SOURCES if k not in lowk)}は、ほぼ同じか、むしろ多くなりました。件数の少ない町ほど9月に記録がなくなりやすい面はありますが、それだけでは説明がつかない県もあります。"],
             "table": {"head": ["県", "4〜8月だけの市町村", "その件数の中央値", "県全体の中央値"], "rows": gone_rows, "note": "件数は、4月1日から8月31日までの、その市町村の記録件数です。中央値は、市町村ごとの件数の真ん中の値です。"},
             "chart": {"kind": "bars", "labels": [SOURCES[k] for k in order], "values": [common.pct(stats[k]["gone"], stats[k]["base"]) for k in order],
                       "title": "4〜8月に記録があって9月にはなかった市町村の割合(%)",
                       "desc": "4月から8月に記録のあった市町村のうち、9月に記録がなかった市町村の割合を、6県で比べた棒グラフ。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [
                 "熊の目撃は、県の中で同じ地域に繰り返し出る傾向があります。「秋になると新しい町に出始める」という見方は、少なくとも令和8年度の9月の記録では、はっきりした形では見えません。",
                 f"ただし、これは9月だけを見た結果です。10月以降は、山の実りの具合によって行動が変わると言われますが、このページは10月以降の記録を使っていません。{SOURCES['akita']}の記録は9月30日までなので、期間を9月までにそろえました。",
                 "お住まいの市町村に4〜8月の記録がなくても、近くの市町村に記録があれば、周辺の地図で位置を確かめてください。このページの数字は、過去の記録の分け方を示すもので、これからの出没を予測するものではありません。",
             ]},
        ],
        "method": [
            "対象は、令和8年度(2026年4月1日から)の記録のうち、9月30日までのものです。6県の記録の最新日が違うため、いちばん早い秋田県の9月30日にそろえました。10月の記録は使っていません。",
            "市町村は、記録の「市町村名」の欄をそのまま使っています。市町村名のない記録は、数えていません。合併や表記の違いは、整えていません。",
            f"偶然の範囲は、各県の記録の市町村名を並べたまま、9月の記録かどうかの区別だけを入れ替える計算を{DRAWS:,}回行ったときの、最小値と最大値です。春から夏に多かった市町村が9月にも多くなる構造は、この計算に含まれています。",
            "対象の6県は、busy-days(記録の半分が入る日数)と同じです。記録が200件に届かない県は対象にしていません。",
        ],
        "caveats": [
            "これは「報告された記録の市町村」の数え方です。記録のない市町村に、熊がいないとは言えません。報告の少ない地域や、公表が遅れている地域があります。",
            "件数の少ない市町村は、1件あるかないかで「新しい」「記録がなくなった」が入れ替わります。数か所の違いを、県どうしの差として読まないでください。",
            "9月だけの比べ方です。10月以降の動きや、ほかの年にも同じ傾向になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/new-towns.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "富山県の最新の目撃情報", "href": "/live/toyama/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k, st in stats.items():
        print(k, st)
    print(total_sep, total_new, new_names, sum(len(str(p)) for s in doc["sections"] for p in s["paragraphs"]))


if __name__ == "__main__":
    main()
