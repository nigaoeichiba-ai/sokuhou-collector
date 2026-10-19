"""Analyses of the data room that come only from the site's own data (no outside source): what moves in the sales ranking, and what each kind of gift costs.

Only counts and prices are published, never a product's name, picture or link (the mall data stays out of public places); the pages say how the numbers were counted and what they
cannot tell.  Registered in dataroom.BUILDERS.
"""
from __future__ import annotations

from sokuhou.sitekit import esc
from sites.yorokobu import dataroom as dr

MIN_RANK_DAYS = 3        # the share of products that stayed three days needs three days of records


def _share(n: int, total: int) -> float:
    return n / total * 100 if total else 0.0


def _notes(items: list[str]) -> str:
    return f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in items)}</ul></section>'


def _how(text: str) -> str:
    return f'<section class="data-notes"><h2>どうやって数えたか</h2><p>{text}</p></section>'


def _care(text: str) -> str:
    return f'<section class="data-notes"><h2>見かたの注意</h2><p>{text}</p></section>'


def ranking_turnover(d: dict) -> tuple | None:
    """How much of each sales list is new and how much stays, counted from the stored ranking history."""
    rv = d.get("ranking")
    if not rv:
        return None
    segs = [sg for sg in rv["segments"].values() if not sg.get("thin") and sg.get("days", 0) >= MIN_RANK_DAYS and len(sg["items"]) >= dr.MIN_PER_ROW and "n_entered" in sg]
    people = sorted((sg for sg in segs if sg["kind"] == "people"), key=lambda sg: -_share(sg["n_entered"], len(sg["items"])))
    genres = sorted((sg for sg in segs if sg["kind"] == "genre"), key=lambda sg: -_share(sg["n_stay"], len(sg["items"])))
    if len(people) < dr.MIN_ROWS or len(genres) < dr.MIN_ROWS:
        return None
    day = dr._b().rk.date_label(rv["date"])
    days = min(sg["days"] for sg in segs)

    def row(sg: dict, key: str) -> tuple[str, float, str]:
        v = _share(sg[key], len(sg["items"]))
        return sg["label"], v, f"{v:.0f}%"
    c1 = dr.figure(d, "世代・性別ごとの、はじめてランクインした商品の割合", dr.hbars([row(sg, "n_entered") for sg in people], top=100, series_class="s2"),
                   f"前日の上位になかった商品の割合(贈り物向きの商品だけ)。出典: 楽天市場のランキング({day})の記録から当サイトが集計。",
                   dr.table(["世代・性別", "商品の数", "新しく入った商品", "割合"], [[sg["label"], str(len(sg["items"])), str(sg["n_entered"]), row(sg, "n_entered")[2]] for sg in people]))
    c2 = dr.figure(d, "ジャンルごとの、3日以上ランクインし続けている商品の割合(上位10ジャンル)", dr.hbars([row(sg, "n_stay") for sg in genres[:10]], top=100),
                   f"ジャンルごとに、毎日の上位に3日以上続けて入っている商品の割合。出典: 楽天市場のランキング({day})の記録から当サイトが集計。",
                   dr.table(["ジャンル", "商品の数", "3日以上続けて入っている商品", "割合"], [[sg["label"], str(len(sg["items"])), str(sg["n_stay"]), row(sg, "n_stay")[2]] for sg in genres]))
    most, least, steady, moving = people[0], people[-1], genres[0], genres[-1]
    notes = [f"前日の上位になかった商品の割合は、「{most['label']}」が{row(most, 'n_entered')[2]}でいちばん高く、「{least['label']}」が{row(least, 'n_entered')[2]}でいちばん低くなっています。",
             f"3日以上続けて入っている商品の割合は、ジャンルでは「{steady['label']}」が{row(steady, 'n_stay')[2]}でいちばん高く、「{moving['label']}」が{row(moving, 'n_stay')[2]}でいちばん低くなっています。"]
    body = (_notes(notes) + c1 + c2
            + _how("楽天市場のランキングの上位から、贈り物向きと分かる商品だけを残し、毎日の記録を残しています。前日の記録になかった商品を「新しく入った商品」、"
                   f"前日から続けて入っている日数が3日以上の商品を「続けて入っている商品」と数えました。記録は{days}日分です。")
            + _care("記録の日数が少ないうちは、1日の動きが大きく出ます。贈り物向きの商品に絞っているため、ランキングの順位そのものとは違います。"
                    '商品の名前は載せていません。商品は<a href="/ranking/">いま売れている商品</a>で見られます。'))
    lead = f"楽天市場の売れ筋は、毎日どのくらい入れ替わっているのか。世代・性別とジャンルごとに、新しく入った商品と続けて入っている商品の割合を数えました({day}まで)。"
    return ("/data/ranking-turnover/", "売れ筋の入れ替わり", lead, body, "売れ筋の入れ替わり",
            f"新しく入った商品の割合がいちばん高いのは「{most['label']}」({row(most, 'n_entered')[2]})")


def kind_prices(d: dict) -> tuple | None:
    """The price of each of the nine kinds of gift (食べもの・飲みもの, ファッション小物 ...) among the products the site shows."""
    B = dr._b()
    by: dict[str, dict[str, dict]] = {}
    for key in sorted(d["pairs"]):
        for idea in B.pair_items(d, key)[0]:
            for it in idea["items"]:
                by.setdefault(idea["type"], {}).setdefault(it["code"], it)
    rows = []
    for kind, items in by.items():
        xs = [i["price"] for i in items.values()]
        if len(xs) >= dr.MIN_PER_ROW:
            a, m, b = dr.quartiles(xs)
            rows.append({"kind": kind, "n": len(xs), "q1": a, "median": m, "q3": b, "le3000": _share(sum(1 for x in xs if x <= 3000), len(xs))})
    if len(rows) < dr.MIN_ROWS:
        return None
    rows.sort(key=lambda r: r["median"])
    total = sum(r["n"] for r in rows)
    c1 = dr.figure(d, "贈り物の種類ごとの価格の中央値", dr.hbars([(r["kind"], r["median"], dr.yen(r["median"])) for r in rows]), "当サイトが取り上げている商品の価格の中央値。" + dr.own_source(d, total),
                   dr.table(["種類", "商品の数", "下から25%", "中央値", "下から75%"], [[r["kind"], str(r["n"]), dr.yen(r["q1"]), dr.yen(r["median"]), dr.yen(r["q3"])] for r in rows]))
    cheap = sorted(rows, key=lambda r: -r["le3000"])
    c2 = dr.figure(d, "3,000円以下の商品の割合", dr.hbars([(r["kind"], r["le3000"], f"{r['le3000']:.0f}%") for r in cheap], top=100, series_class="s2"),
                   "種類ごとに、3,000円以下の商品が占める割合。" + dr.own_source(d, total), dr.table(["種類", "3,000円以下の割合"], [[r["kind"], f"{r['le3000']:.0f}%"] for r in cheap]))
    hi, lo = rows[-1], rows[0]
    notes = [f"価格の中央値がいちばん高い種類は「{hi['kind']}」の{dr.yen(hi['median'])}、いちばん低い種類は「{lo['kind']}」の{dr.yen(lo['median'])}です。",
             f"3,000円以下の商品の割合がいちばん高い種類は「{cheap[0]['kind']}」で{cheap[0]['le3000']:.0f}%です。"]
    body = (_notes(notes) + c1 + c2
            + _how(f"各ページの案に載せている商品を、案の種類ごとに集めて、同じ商品は1回だけ数えました。種類ごとの商品が{dr.MIN_PER_ROW}点に満たないものは、除いています。")
            + _care('ここにあるのは、当サイトが取り上げた商品の価格です。楽天市場の全体の価格ではなく、贈るときの予算とも違います。同じ種類でも、ブランドや量で価格は大きく変わります。'
                    '予算から探すときは<a href="/budget/">予算から探す</a>が使えます。'))
    lead = "食べもの、ファッション小物など、贈り物の種類ごとに、どのくらいの価格の商品が多いのか。当サイトが取り上げている商品の価格を、種類ごとに比べました。毎日、更新しています。"
    return "/data/kind-prices/", "贈り物の種類ごとの価格", lead, body, "種類ごとの価格", f"価格の中央値がいちばん高い種類は「{hi['kind']}」({dr.yen(hi['median'])})"
