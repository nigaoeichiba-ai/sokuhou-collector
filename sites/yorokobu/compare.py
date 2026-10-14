"""商品比較 (/compare/): the same kind of gift in several Rakuten shops side by side, with a score.

The data is data/yorokobu_compare.json (compare_fetch.py: Rakuten's own search results of each kind, price, the shop's point multiplier, shipping, reviews).  The build only
reads it.  Every number on a page comes from that file; the score is a plain formula that the page itself prints, so nobody has to take it on trust:

    総合点 (0-100) = 実質価格 40 + レビュー 40 + 送料 10 + ギフト対応 10

  実質価格  the price less the points the shop's multiplier gives (the multiplier is the shop's own, shown on its item page; a member's other point campaigns are not counted),
            as a place among the products of the table: the cheapest gets 40, the dearest 0.
  レビュー  the review average pulled toward the table's median by REVIEW_PRIOR reviews (a 5.0 from two reviews does not beat a 4.6 from a thousand), then 3.5 → 0 and 4.9 → 40.
  送料      free shipping 10.   ギフト対応  the shop offers gift wrapping 10.

What this does not say: that a product is good or that it is the cheapest anywhere.  The products of one table differ in size and contents, which the page says too.
Amazon is not in the tables: its price may be shown only from Amazon's own API (Amazon's programme policy), which this site does not have, and a comparison that leaves
out Amazon's price must not claim to be one of all shops.  The page says so and gives Amazon's search as a link.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path

from sites.yorokobu import amazonrank, relevance
from sites.yorokobu.picking import usable
from sokuhou.sitekit import crumbs, esc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "yorokobu_compare.json"
MIN_ITEMS = 8                  # products in a table (fewer says nothing)
MIN_SHOPS = 3                  # shops in a table (one shop's catalogue is not a comparison)
MAX_ROWS = 20
PER_SHOP = 3
REVIEW_PRIOR = 30
W_PRICE, W_REVIEW, W_SHIP, W_GIFT = 40, 40, 10, 10
RATING_LO, RATING_HI = 3.5, 4.9
SORTS = (("score", "総合点が高い順"), ("price", "実質価格が安い順"), ("rating", "レビューが高い順"), ("points", "ポイントが多い順"))


def _b():
    from sites.yorokobu import build
    return build


def load(path: Path | None = None) -> dict | None:
    p = path or DATA
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def groups() -> list[dict]:
    return json.loads((HERE / "content" / "compare.json").read_text(encoding="utf-8"))["groups"]


# ---------------------------------------------------------------- the numbers

def points_of(it: dict, now: datetime | None = None) -> int:
    """The points the shop's multiplier gives on this price (1 point = 1 yen; N times = N % of the price), 0 when the item has no running multiplier."""
    B = _b()
    if not B.point_end(it):
        return 0
    return int(it["price"] * float(it["point_rate"]) / 100)


def effective(it: dict) -> int:
    return it["price"] - points_of(it)


def bayes(rating: float, reviews: int, prior: float) -> float:
    return (rating * reviews + prior * REVIEW_PRIOR) / (reviews + REVIEW_PRIOR)


def score_table(items: list[dict]) -> list[dict]:
    """Each item with its parts and its total; the list is sorted by the total (then by price)."""
    eff = [effective(i) for i in items]
    lo, hi = min(eff), max(eff)
    rated = [i["rating"] for i in items if i["reviews"]]
    prior = statistics.median(rated) if rated else 4.0
    out = []
    for it, e in zip(items, eff):
        price_part = W_PRICE * ((hi - e) / (hi - lo) if hi > lo else 1.0)
        b = bayes(it["rating"], it["reviews"], prior)
        review_part = W_REVIEW * min(1.0, max(0.0, (b - RATING_LO) / (RATING_HI - RATING_LO)))
        ship_part = W_SHIP if it["free_shipping"] else 0
        gift_part = W_GIFT if it.get("gift") else 0
        total = price_part + review_part + ship_part + gift_part
        out.append({**it, "points": points_of(it), "effective": e, "bayes": round(b, 2), "parts": (round(price_part), round(review_part), ship_part, gift_part), "total": round(total)})
    out.sort(key=lambda r: (-r["total"], r["effective"], r["code"]))
    return out


def view(raw: dict | None, filters: dict, cfg_groups: list[dict] | None = None) -> dict | None:
    """The tables to publish: per kind the products that fit the kind and the site's rules, at most PER_SHOP of a shop, scored; a kind with too few products or shops is left out."""
    if not raw:
        return None
    gs = cfg_groups if cfg_groups is not None else groups()
    out = []
    for g in gs:
        items, seen, per = [], set(), {}
        for it in raw.get("groups", {}).get(g["slug"], []):
            if it["code"] in seen or not usable(it, filters, None, relaxed=True) or not relevance.fits_head(it["name"], g["words"]):
                continue
            if per.get(it["shop_code"], 0) >= PER_SHOP:
                continue
            seen.add(it["code"])
            per[it["shop_code"]] = per.get(it["shop_code"], 0) + 1
            items.append(it)
        if len(items) < MIN_ITEMS or len({i["shop_code"] for i in items}) < MIN_SHOPS:
            continue
        keep = {r["code"] for r in score_table(items)[:MAX_ROWS]}               # the best of everything found ...
        rows = score_table([it for it in items if it["code"] in keep])         # ... scored again among themselves: the table's numbers are places within the table, as the page says
        prices = sorted(r["price"] for r in rows)
        out.append({**g, "rows": rows, "n": len(rows), "shops": len({r["shop_code"] for r in rows}), "min": prices[0], "max": prices[-1],
                    "median_price": int(statistics.median(prices)), "campaign": sum(1 for r in rows if r["points"])})
    if not out:
        return None
    t = datetime.fromisoformat(raw["fetched_at"])
    return {"groups": out, "fetched_at": raw["fetched_at"], "fetched_label": f"{t.year}年{t.month}月{t.day}日 {t.hour}:{t.minute:02d}", "by_slug": {g["slug"]: g for g in out}}


# ---------------------------------------------------------------- pages

def shaddy_url(cfg: dict) -> str:
    """The affiliate link (A8.net) of シャディギフトモール; empty when the site has no id for it."""
    m = cfg.get("shaddy_a8mat")
    return f"https://px.a8.net/svt/ejp?a8mat={m}" if m else ""


def shaddy_a(cfg: dict, text: str = "シャディギフトモール") -> str:
    return f'<a href="{esc(shaddy_url(cfg))}" rel="sponsored nofollow noopener" target="_blank">{esc(text)}</a>'


def path(slug: str | None = None) -> str:
    return "/compare/" if slug is None else f"/compare/{slug}/"


def formula_html() -> str:
    return ('<details class="cmp-formula"><summary>総合点のつけ方</summary>'
            '<p>総合点は次の4つの合計です(100点満点)。当サイトの計算で商品の品質を評価した点数ではありません。</p>'
            '<ul class="cmp-parts">'
            f'<li><b>実質価格 {W_PRICE}点</b>価格からショップのポイント倍率で付くポイントを引いた額が、この表の中で安いほど高くなります(いちばん安い商品が{W_PRICE}点、いちばん高い商品が0点)。会員ランクなどのほかのポイントは入れていません。</li>'
            f'<li><b>レビュー {W_REVIEW}点</b>レビューの平均をこの表の中央値に{REVIEW_PRIOR}件分だけ寄せて見ます(件数の少ない満点が、件数の多い高評価を上回らないようにするためです)。平均{RATING_LO}で0点、{RATING_HI}で{W_REVIEW}点です。</li>'
            f'<li><b>送料 {W_SHIP}点</b>送料無料なら{W_SHIP}点です。</li>'
            f'<li><b>ギフト対応 {W_GIFT}点</b>ギフト包装などに対応しているショップなら{W_GIFT}点です。</li></ul>'
            '<p>各商品の下の「ひとこと」と4本のバーは、この点数の元になった数字から書いています。商品を使った感想ではありません。バーは、それぞれの満点に対する割合です。</p>'
            '<p>同じ表の商品でも、大きさや内容量、セットの中身は違います。価格は中身をそろえた比較ではありません。商品ページで中身と届く日を確かめてください。</p></details>')


def say(r: dict, rank: int, n: int, median_eff: int) -> str:
    """The row's one-line reading, written from its own numbers (rank by real price among the n rows, the review count, shipping, gift wrapping).  It says what the score rests on; it is not an opinion of the product."""
    gap = median_eff - r["effective"]
    if rank == 1:
        price = "実質価格はこの表でいちばん安い水準です。"
    elif rank <= max(3, n // 3):
        price = f"実質価格は安い方から{rank}番目です。"
    elif rank > n - max(3, n // 3) and n >= 8:
        price = "実質価格は表の中では高い方です。"
    else:
        price = "実質価格は表の中ほどです。"
    if rank > 1 and abs(gap) >= 100:
        price += f"中央値より{abs(gap):,}円{'安く' if gap > 0 else '高く'}なっています。"
    rv, rt = r["reviews"], r["rating"]
    if not rv:
        review = "レビューはまだありません。"
    elif rv < 10:
        review = f"レビューは{rv}件と少なく評価は参考程度です。"
    elif rv >= 100 and rt >= 4.5:
        review = f"レビューは★{rt:.2f}で{rv:,}件と多く、評価が固まっています。"
    elif rv >= 100 and rt < 4.0:
        review = f"レビューは{rv:,}件あり、平均は★{rt:.2f}と低めです。"
    elif rt >= 4.5:
        review = f"レビューは★{rt:.2f}と高く、件数は{rv}件です。"
    else:
        review = f"レビューは★{rt:.2f}({rv}件)です。"
    notes = []
    if not r["free_shipping"]:
        notes.append("送料は別にかかります")
    if not r.get("gift"):
        notes.append("ショップのギフト対応の表示はありません")
    tail = ("。".join(notes) + "。") if notes else "送料無料でギフト対応の表示もあります。"
    return price + review + tail


def places(rows: list[dict]) -> dict[str, int]:
    """The place of each row by real price (1 = cheapest); rows of the same price share a place."""
    return {r["code"]: 1 + sum(1 for o in rows if o["effective"] < r["effective"]) for r in rows}


def stat_html(r: dict) -> str:
    """Four bars, one per part of the score, each as a share of its own maximum with the points written out (so the page does not rest on colour)."""
    p, rv, sh, gf = r["parts"]
    rows = (("実質価格", p, W_PRICE), ("レビュー", rv, W_REVIEW), ("送料", sh, W_SHIP), ("ギフト対応", gf, W_GIFT))
    return '<ul class="cmp-stat" aria-label="総合点の内訳">' + "".join(
        f'<li><span class="cmp-sl">{k}</span><span class="cmp-st"><i style="width:{round(v * 100 / m)}%"></i></span><span class="cmp-sv">{v}<small>/{m}</small></span></li>'
        for k, v, m in rows) + "</ul>"


def _row(cfg: dict, r: dict, n: int, rank: int = 0, total: int = 0, median_eff: int = 0) -> str:
    B = _b()
    href = B.rakuten_link(cfg, B.rakuten.clean_item_url(r["url"]))
    B.SEEN[r["code"]] = {"n": B.short(r["name"], 60), "p": r["price"], "i": r["image"], "u": href,
                         "a": B.amazon_url(cfg, B.amazon_query(r["name"])) if cfg.get("amazon_tracking_id") else ""}
    tags = ""
    if r["free_shipping"]:
        tags += '<span class="tagx">送料無料</span>'
    if r.get("gift"):
        tags += '<span class="tagx">ギフト対応</span>'
    tags += B.point_badge(r)
    price = f'<p class="cmp-price"><b>{B.yen(r["price"])}</b></p>'
    if r["points"]:
        price += f'<p class="cmp-pt">ポイント約{r["points"]:,}pt<br>実質 {B.yen(r["effective"])}</p>'
    stars = f'<span class="stars">★{r["rating"]:.2f}</span>({r["reviews"]:,}件)' if r["reviews"] else "レビューなし"
    attrs = (f'data-code="{esc(r["code"])}" data-price="{r["effective"]}" data-rating="{r["bayes"]}" data-points="{r["points"]}" data-score="{r["total"]}" data-order="{n}"')
    fav = B.fav_button(r["code"], B.short(r["name"], 40), r["price"], B.rakuten.clean_item_url(r["url"]))
    p, rv, sh, gf = r["parts"]
    return (f'<li class="cmp-row" {attrs}><span class="cmp-no">{n}</span>'
            f'<div class="imgbox cmp-img"><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank"><img src="{esc(B.thumb(r["image"], 128))}" alt="{esc(B.short(r["name"], 40))}" width="84" height="84" {B.LAZY}></a>{fav}</div>'
            f'<div class="cmp-main"><p class="cmp-shop">{esc(r["shop"])}</p><h3><a href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(B.short(r["name"], 52))}</a></h3><p class="cmp-tags">{tags}</p></div>'
            f'<div class="cmp-num">{price}</div>'
            f'<div class="cmp-num cmp-rev"><p>{stars}</p></div>'
            f'<div class="cmp-score" title="実質価格{p}・レビュー{rv}・送料{sh}・ギフト対応{gf}"><b>{r["total"]}</b><small>総合点</small><i style="width:{r["total"]}%"></i></div>'
            f'<div class="cmp-go"><a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">楽天市場で見る</a></div>'
            f'<div class="cmp-why"><p class="cmp-say"><span class="cmp-cap">ひとこと</span>{esc(say(r, rank, total, median_eff))}</p>{stat_html(r)}</div></li>')


def group_page(d: dict, cfg: dict, preview: bool, g: dict) -> str:
    B = _b()
    cv = d["compare"]
    by_price = places(g["rows"])
    med = int(statistics.median(r["effective"] for r in g["rows"]))
    rows = "".join(_row(cfg, r, i, by_price[r["code"]], len(g["rows"]), med) for i, r in enumerate(g["rows"], 1))
    sort = "".join(f'<button type="button" class="cmp-sort" data-sort="{k}" aria-pressed="{"true" if k == "score" else "false"}">{esc(t)}</button>' for k, t in SORTS)
    lead = f"{g['label']}を楽天市場の{g['shops']}店・{g['n']}点で価格・ポイント・送料・レビューを並べて比べます。総合点の高い順に並べています。"
    az = ""
    if cfg.get("amazon_tracking_id"):
        az = (f'<p class="cmp-az">Amazonの価格はこの表には入っていません(Amazonの規約で価格を表示できるのは、Amazon自身が提供する方法に限られるためです)。'
              f'同じ種類は<a href="{esc(B.amazon_url(cfg, g["label"] + " ギフト"))}" rel="sponsored nofollow noopener" target="_blank">Amazonで{esc(g["label"])}を探す</a>から確かめられます。'
              f'Amazonの商品は、価格のない<a href="{amazonrank.PATH}">編集部の採点ページ</a>に分けています。</p>')
    if "shaddy" in g.get("mall", []) and shaddy_url(cfg):
        az += f'<p class="cmp-az">ギフト専門店の{shaddy_a(cfg)}は、この表に入っていません。内祝いやお返しの品は、こちらからも探せます。</p>'
    camp = f"ポイント倍率が付いている商品は{g['campaign']}点です。" if g["campaign"] else ""
    summary = (f'<p class="cmp-sum">価格は{B.yen(g["min"])}〜{B.yen(g["max"])}(中央値{B.yen(g["median_price"])})です。{camp}</p>')
    others = "".join(f'<li><a href="{path(o["slug"])}">{esc(o["label"])}</a></li>' for o in cv["groups"] if o["slug"] != g["slug"])
    body = f"""{B.head_band("sky", "", f"{esc(g['label'])}を比べる", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("商品比較", path()), (g["label"], None)])}</div>
{B.pr_quiet(cfg)}
<section class="block cmp" id="cmp" data-fetched="{esc(cv['fetched_at'])}">
{summary}
<div class="cmp-bar" role="group" aria-label="並べ替え" hidden>{sort}</div>
<ol class="cmp-list" id="cmp-list" aria-live="polite">{rows}</ol>
{B.freshness({**d, "fetched_label": cv["fetched_label"]})}
{formula_html()}
<p class="cmp-note">この表は楽天市場の商品だけです。ほかのモールの商品やほかのショップの価格は入っていません。「最安」とは言えません。</p>
{az}
</section>
<section class="block"><div class="sec-head"><h2>ほかの種類を比べる</h2></div><ul class="plain cols2 chips">{others}</ul></section>
<script src="/assets/compare.js" defer></script>"""
    return B.page(cfg, preview, path=path(g["slug"]), title=f"{g['label']}を楽天市場で比べる(価格・ポイント・レビュー) | {cfg['site_name']}",
                  description=lead, body=body, amazon_links=bool(cfg.get("amazon_tracking_id")))


def hub_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    cv = d["compare"]
    tiles = "".join(f'<li><a class="tile wide" href="{path(g["slug"])}"><span><b>{esc(g["label"])}</b><small>{g["n"]}点・{B.yen(g["min"])}〜{B.yen(g["max"])}</small></span></a></li>' for g in cv["groups"])
    lead = "同じ種類の贈り物を楽天市場のいくつものショップで、価格・ポイント・送料・レビューを並べて比べます。"
    mall_items = ""
    if cfg.get("amazon_tracking_id"):
        mall_items += f'<li><a href="{amazonrank.PATH}">Amazonで選ぶ贈り物</a> 価格とレビューは載せられないため、当サイトの4項目の採点順に並べています。</li>'
    if shaddy_url(cfg):
        mall_items += f'<li>{shaddy_a(cfg)} 内祝いやお返しの品も探せるギフト専門店です。価格はこの比較に入っていません。</li>'
    malls = f'<section class="block"><div class="sec-head"><h2>ほかのモールで探す</h2></div><ul class="plain">{mall_items}</ul></section>' if mall_items else ""
    body = f"""{B.head_band("sky", "", "商品比較", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("商品比較", None)])}</div>
{B.pr_quiet(cfg)}
<section class="block"><div class="sec-head"><h2>種類を選ぶ</h2><p class="sec-lead">楽天市場で{esc(cv['fetched_label'])}に調べた結果です。毎日更新しています。</p></div><ul class="tiles wide">{tiles}</ul></section>
{malls}
<section class="block"><div class="sec-head"><h2>この比較について</h2></div>
<ul class="plain">
<li>価格、ポイント倍率、送料、レビューは楽天市場が公開している情報です。調べた日時を各ページに載せています。</li>
<li>総合点は実質価格・レビュー・送料・ギフト対応を足した、当サイトの計算です。式は各ページで確かめられます。商品の品質を評価した点数ではありません。</li>
<li>いまは楽天市場の商品だけを比べています。Amazonは価格を表示できる条件が当サイトに合わないため、表には入れず、価格のない採点ページに分けています。</li>
<li>同じ表の商品でも、大きさや内容量は違います。商品ページで中身と届く日を確かめてください。</li></ul></section>"""
    return B.page(cfg, preview, path=path(), title=f"商品比較(楽天市場の価格・ポイント・レビューを並べる) | {cfg['site_name']}", description=lead, body=body)


def build_pages(d: dict, cfg: dict, preview: bool) -> dict[str, str]:
    cv = d.get("compare")
    if not cv:
        return {}
    pages = {"compare/index.html": hub_page(d, cfg, preview)}
    for g in cv["groups"]:
        pages[f"compare/{g['slug']}/index.html"] = group_page(d, cfg, preview, g)
    return pages
