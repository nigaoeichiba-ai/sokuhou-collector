"""Amazonで選ぶ贈り物 (/compare/amazon/): the Amazon products of the daily picks, ordered by a score the page prints.

Amazon's programme policy lets a site show a price or a customer review only from Amazon's own API (which needs sales this account does not have yet), so this page has neither.
The ranking therefore rests on what the site itself has written down about each product (content/daily/*.json): four marks of 1-5 each, kept in content/amazon_rank.json, one list
per ASIN.  The total is the sum times 5 (0-100).  It is the site's judgement, said so on the page; it does not say a product is good, cheap or well reviewed.

    贈りやすさ   a box, single wrapping, how it looks when handed over
    外しにくさ   how little a difference of taste, allergy or belongings can spoil it
    使いやすさ   how little work it takes, whether it gets used up, how long it lasts
    注意点の少なさ  how little the buyer has to check first, how few people it cannot be given to

A product without marks is not listed (the daily routine adds the marks of its ten new Amazon products).  Nothing here is an Amazon image, price, star or review.
"""
from __future__ import annotations

import json
from pathlib import Path

from sokuhou.sitekit import crumbs, esc

HERE = Path(__file__).resolve().parent
PATH = "/compare/amazon/"
MAXMARK = 5


def _b():
    from sites.yorokobu import build
    return build


def load() -> dict:
    return json.loads((HERE / "content" / "amazon_rank.json").read_text(encoding="utf-8"))


def ranked(days: list[dict], data: dict) -> list[dict]:
    """Every Amazon product of the daily picks (newest entry of an ASIN wins) that has marks, best total first; ties go to 注意点の少なさ, then 使いやすさ, then the newer day."""
    scores, n_axes = data["scores"], len(data["axes"])
    seen: dict[str, dict] = {}
    for day in sorted(days, key=lambda x: x["date"], reverse=True):
        for e in day.get("amazon", []):
            if e["asin"] not in seen and e["asin"] in scores and len(scores[e["asin"]]) == n_axes:
                seen[e["asin"]] = {**e, "date": day["date"], "marks": scores[e["asin"]]}
    out = []
    for e in seen.values():
        e["total"] = round(sum(e["marks"]) * 100 / (MAXMARK * n_axes))
        out.append(e)
    out.sort(key=lambda e: e["date"], reverse=True)                                 # newer first among equals (sort is stable) ...
    out.sort(key=lambda e: (-e["total"], -e["marks"][3], -e["marks"][2]))           # ... after the total, then 注意点の少なさ, then 使いやすさ
    return out


def _bars(axes: list[dict], marks: list[int]) -> str:
    return '<ul class="cmp-stat" aria-label="編集点の内訳">' + "".join(
        f'<li><span class="cmp-sl">{esc(a["label"])}</span><span class="cmp-st"><i style="width:{round(m * 100 / MAXMARK)}%"></i></span><span class="cmp-sv">{m}<small>/{MAXMARK}</small></span></li>'
        for a, m in zip(axes, marks)) + "</ul>"


def _row(cfg: dict, axes: list[dict], e: dict, n: int) -> str:
    B = _b()
    href = B.amazon_dp(cfg, e["asin"])
    fav = B.fav_button("a:" + e["asin"], B.short(e["name"], 40), None, href)
    img = B.mood_img(e["mood"], e["name"] + "の商品写真ではなく、贈る場面を表したイメージ", "84px")
    return (f'<li class="cmp-row az-row" data-asin="{esc(e["asin"])}"><span class="cmp-no">{n}</span>'
            f'<div class="imgbox cmp-img"><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{img}</a>{fav}</div>'
            f'<div class="cmp-main"><p class="cmp-shop">{esc(e["kind"])}</p><h3><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(e["headline"])}</a></h3>'
            f'<p class="cmp-shop">{esc(B.short(e["name"], 56))}</p></div>'
            f'<div class="cmp-score" title="編集点 {e["total"]}点"><b>{e["total"]}</b><small>編集点</small><i style="width:{e["total"]}%"></i></div>'
            f'<div class="cmp-go"><a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">Amazonで見る</a></div>'
            f'<div class="cmp-why"><div class="az-say"><p><span class="cmp-cap">いいところ</span>{esc(e["good"])}</p><p><span class="cmp-cap">気になるところ</span>{esc(e["care"])}</p></div>'
            f'{_bars(axes, e["marks"])}</div></li>')


def formula_html(axes: list[dict]) -> str:
    items = "".join(f'<li><b>{esc(a["label"])} {MAXMARK}点満点</b>{esc(a["note"])}。</li>' for a in axes)
    return ('<details class="cmp-formula" open><summary>編集点のつけ方</summary>'
            f'<p>編集点は、次の{len(axes)}項目を{MAXMARK}点満点でつけた合計です(100点満点に直しています)。</p>'
            f'<ul class="cmp-parts">{items}</ul>'
            '<p>点は、当サイトが商品ページやメーカーの説明から書き出した事実(各商品の「いいところ」「気になるところ」)をもとにした判断です。商品の品質や効果を保証するものではなく、購入者のレビューも入っていません。</p></details>')


def page(d: dict, cfg: dict, preview: bool) -> str | None:
    if not cfg.get("amazon_tracking_id"):
        return None
    B = _b()
    data = load()
    rows = ranked(d["c"].get("daily") or [], data)
    if len(rows) < 8:
        return None
    axes = data["axes"]
    lead = f"Amazonで買える贈り物{len(rows)}点を、商品ページの事実から{len(axes)}項目で採点した順に並べます。価格とレビューはAmazonの規約で載せられないため、点数に入っていません。"
    lis = "".join(_row(cfg, axes, e, i) for i, e in enumerate(rows, 1))
    rakuten = "楽天市場の商品は、価格・ポイント・送料・レビューを並べた<a href=\"/compare/\">商品比較</a>で比べられます。" if d.get("compare") else ""
    body = f"""{B.head_band("sky", "", "Amazonで選ぶ贈り物", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/")] + ([("商品比較", "/compare/")] if d.get("compare") else []) + [("Amazonで選ぶ", None)])}</div>
{B.pr_quiet(cfg)}
<section class="block cmp" id="cmp">
<p class="cmp-sum">毎日のおすすめギフトで紹介したAmazonの商品が対象です。点数は{esc(data["updated"][:4])}年{int(data["updated"][5:7])}月{int(data["updated"][8:10])}日までに採点した分で、新しい商品が増えるたびに並べ直します。画像は商品の写真ではなく、贈る場面を表したイメージです。</p>
<ol class="cmp-list" id="cmp-list">{lis}</ol>
{formula_html(axes)}
<p class="cmp-note">価格・在庫・購入者の評価は、Amazonのページでご確認ください。{rakuten}</p>
</section>"""
    return B.page(cfg, preview, path=PATH, title=f"Amazonで選ぶ贈り物(編集部の採点順) | {cfg['site_name']}", description=lead, body=body, amazon_links=True)


def build_pages(d: dict, cfg: dict, preview: bool) -> dict[str, str]:
    html = page(d, cfg, preview)
    return {"compare/amazon/index.html": html} if html else {}
