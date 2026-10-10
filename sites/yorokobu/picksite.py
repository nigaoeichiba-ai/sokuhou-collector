"""The pages of 今日のおすすめギフト: /picks/ (the recent days) and /picks/YYYY-MM-DD/ (one day: 10 Rakuten and 10 Amazon products, each with its own text).

The text comes from content/daily/*.json (validated by dailypicks.problems at load time).  A Rakuten product's price, rating and picture are looked up again
at every refresh (refresh.py writes them to items["daily"]); when that is missing (an old day, a failed lookup) the card shows the picture saved with the text
and no price.  A product that Rakuten reports as no longer available is left out of the day's page.  Amazon products carry no price and no picture of the product.
"""
from __future__ import annotations

import json
from datetime import date

from sites.yorokobu import dailypicks as dp
from sokuhou.sitekit import crumbs, esc

STORE_NAME = {"rakuten": "楽天市場", "amazon": "Amazon"}
POLICY = ("掲載する商品は、贈り物として渡しやすいこと、商品ページで仕様と注意事項が確認できること、購入者の声に大きな不満が目立たないことを基準に、毎日選んでいます。"
          "文章は、商品ページの仕様、メーカーなどの公開情報、購入者の声の傾向を読んで、自分たちの言葉でまとめたものです。当サイトで実際に使って試した感想ではありません。"
          "商品ページの文章やレビューは、そのまま載せていません。")


def _b():
    from sites.yorokobu import build
    return build


def date_label(iso: str, year: bool = False) -> str:
    d = date.fromisoformat(iso)
    return f"{d.year}年{d.month}月{d.day}日" if year else f"{d.month}月{d.day}日"


def day_path(iso: str) -> str:
    return f"/picks/{iso}/"


def _chips(items: list[str]) -> str:
    return '<ul class="pick-for">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def _facts(e: dict) -> str:
    return ('<div class="pick-pc"><div><h4>いいところ</h4><p>' + esc(e["good"]) + '</p></div><div><h4>気になるところ</h4><p>' + esc(e["care"]) + '</p></div></div>'
            '<ul class="pick-check">' + "".join(f"<li>{esc(x)}</li>" for x in e["check"]) + "</ul>")


def rakuten_card(cfg: dict, d: dict, e: dict, eid: str, n: int) -> str | None:
    B = _b()
    live = d.get("daily_items", {}).get(e["code"])
    if live is not None and not live.get("available", True):
        return None                                                      # sold out or gone: not shown (nobody can buy it)
    url = B.rakuten.clean_item_url(live["url"] if live else e["url"])
    href = B.rakuten_link(cfg, url)
    img = live["image"] if live else e["img"]
    price = ""
    if live:
        stars = f'<span class="stars">★{live["rating"]:.1f}</span>({live["reviews"]:,}件)' if live["reviews"] else ""
        price = (f'<p class="pick-price">{B.yen(live["price"])}<small>{stars}{"・送料無料" if live["free_shipping"] else ""}'
                 f'<br>楽天市場の{esc(d["fetched_label"])}時点の情報</small></p>')
        B.SEEN[e["code"]] = {"n": B.short(e["name"], 60), "p": live["price"], "i": live["image"], "u": href,
                             "a": B.amazon_url(cfg, B.amazon_query(e["name"])) if cfg.get("amazon_tracking_id") else ""}
    else:
        price = '<p class="pick-price"><small>価格・在庫は、販売ページでご確認ください。</small></p>'
    other = (f'<a class="btn" href="{esc(B.amazon_url(cfg, B.amazon_query(e["name"])))}" rel="sponsored nofollow noopener" target="_blank" '
             f'aria-label="Amazonで同じ商品を探す">Amazonで探す</a>') if cfg.get("amazon_tracking_id") else ""
    return (f'<article class="pick" id="{eid}"><a class="pick-img" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">'
            f'<img src="{esc(img)}" alt="{esc(e["name"])}" width="300" height="300" loading="lazy"></a>'
            f'<div class="pick-body"><p class="pick-meta"><span class="pick-no">{n}</span><span class="tag">{esc(e["kind"])}</span><span class="pick-scene">{esc(e["scene"])}</span></p>'
            f'<h3>{esc(e["headline"])}</h3><p class="pick-name">{esc(e["name"])}</p><p class="pick-sum">{esc(e["summary"])}</p>{_chips(e["for"])}{_facts(e)}{price}'
            f'<div class="item-btns"><a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">楽天市場で見る</a>{other}</div></div></article>')


def amazon_card(cfg: dict, d: dict, e: dict, eid: str, n: int) -> str:
    B = _b()
    href = B.amazon_dp(cfg, e["asin"])
    rk = B.search_link(cfg, B.amazon_query(e["name"]))
    return (f'<article class="pick" id="{eid}"><a class="pick-img mood" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">'
            f'<img src="{dp.mood_path(e)}" alt="{esc(e["name"])}の商品写真ではなく、贈る場面を表したイメージ" width="480" height="320" loading="lazy"><span class="img-note">イメージ画像</span></a>'
            f'<div class="pick-body"><p class="pick-meta"><span class="pick-no">{n}</span><span class="tag">{esc(e["kind"])}</span><span class="pick-scene">{esc(e["scene"])}</span></p>'
            f'<h3>{esc(e["headline"])}</h3><p class="pick-name">{esc(e["name"])}</p><p class="pick-sum">{esc(e["summary"])}</p>{_chips(e["for"])}{_facts(e)}'
            f'<p class="pick-price"><small>価格・在庫は、Amazonのページでご確認ください。</small></p>'
            f'<div class="item-btns"><a class="btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">Amazonで見る</a>'
            f'<a class="btn" href="{esc(rk)}" rel="sponsored nofollow noopener" target="_blank" aria-label="楽天市場で同じ商品を探す">楽天市場で探す</a></div></div></article>')


def _entries(day: dict) -> dict[str, tuple[str, dict]]:
    out = {f"r{i}": ("rakuten", e) for i, e in enumerate(day["rakuten"], 1)}
    out.update({f"a{i}": ("amazon", e) for i, e in enumerate(day["amazon"], 1)})
    return out


def highlight_tiles(day: dict, d: dict, cfg: dict) -> str:
    ents = _entries(day)
    tiles = ""
    for h in day["highlights"]:
        store, e = ents[h["ref"]]
        if store == "amazon" and not cfg.get("amazon_tracking_id"):
            continue                                                       # no Associates ID, no Amazon link: such a product is not shown
        live = d.get("daily_items", {}).get(e.get("code", ""))
        img = (live["image"] if live else e.get("img")) if store == "rakuten" else dp.mood_path(e)
        tiles += (f'<li><a class="pick-hl" href="{day_path(day["date"])}#{h["ref"]}"><img src="{esc(img)}" alt="" width="120" height="120" loading="lazy">'
                  f'<span><b class="hl-tag">{esc(h["tag"])}</b><strong>{esc(e["headline"])}</strong><small>{esc(e["name"][:34])}</small></span></a></li>')
    return f'<ul class="pick-hls">{tiles}</ul>'


def day_page(d: dict, cfg: dict, preview: bool, day: dict, newest: bool, prev_day: str | None, next_day: str | None) -> str:
    B = _b()
    iso = day["date"]
    r_cards, a_cards, shown = [], [], []
    for i, e in enumerate(day["rakuten"], 1):
        c = rakuten_card(cfg, d, e, f"r{i}", len(r_cards) + 1)
        if c:
            r_cards.append(c)
            shown.append((f"r{i}", e))
    for i, e in enumerate(day["amazon"], 1):
        if cfg.get("amazon_tracking_id"):
            a_cards.append(amazon_card(cfg, d, e, f"a{i}", i))
            shown.append((f"a{i}", e))
    total = len(r_cards) + len(a_cards)
    h1 = f"今日のおすすめギフト{total}選 {date_label(iso)}" if newest else f"{date_label(iso, True)}のおすすめギフト{total}選"
    live_any = any(d.get("daily_items", {}).get(e["code"]) for e in day["rakuten"])
    az_note = ('<p class="sec-lead">Amazonの商品は、規約により、価格と商品の写真を載せていません。写真は、贈る場面を表したイメージです。'
               '価格・在庫・購入者の評価は、Amazonのページでご確認ください。</p>') if cfg.get("amazon_tracking_id") else ""
    nav = ""
    if prev_day or next_day:
        nav = ('<p class="more">' + (f'<a class="btn btn-sub" href="{day_path(prev_day)}">{date_label(prev_day)}のおすすめ</a>' if prev_day else "")
               + (f'<a class="btn btn-sub" href="{day_path(next_day)}">{date_label(next_day)}のおすすめ</a>' if next_day else "") + '<a class="btn btn-sub" href="/picks/">過去のおすすめ</a></p>')
    else:
        nav = '<p class="more"><a class="btn btn-sub" href="/picks/">過去のおすすめ</a></p>'
    ld = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "name": h1, "numberOfItems": total,
                     "itemListElement": [{"@type": "ListItem", "position": i, "name": e["headline"], "url": f'{cfg["site_url"].rstrip("/")}{day_path(iso)}#{eid}'}
                                         for i, (eid, e) in enumerate(shown, 1)]}, ensure_ascii=False)
    ld2 = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": h1, "datePublished": iso, "dateModified": iso, "inLanguage": "ja",
                      "author": {"@type": "Organization", "name": cfg["operator_name"]}}, ensure_ascii=False)
    body = f"""{B.head_band("yellow", "", esc(h1), day["lede"], single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("毎日のおすすめ", "/picks/"), (date_label(iso), None)])}</div>
{B.pr_quiet(cfg)}
<p class="pick-theme"><span class="eyebrow">Today's theme</span>{esc(day["theme"])}</p>
<section class="block pick-top"><div class="sec-head"><h2>今日の注目3点</h2></div>{highlight_tiles(day, d, cfg)}</section>
<nav class="chips pick-toc" aria-label="このページの内容"><a href="#rakuten">楽天市場の{len(r_cards)}点</a>{f'<a href="#amazon">Amazonの{len(a_cards)}点</a>' if a_cards else ""}<a href="#policy">選び方</a></nav>
<section class="block" id="rakuten"><div class="sec-head"><span class="eyebrow">Rakuten</span><h2>楽天市場で選ぶ{len(r_cards)}点</h2></div><div class="pick-list">{"".join(r_cards)}</div>
{B.freshness(d) if live_any else ""}</section>
{f'<section class="block" id="amazon"><div class="sec-head"><span class="eyebrow">Amazon</span><h2>Amazonで選ぶ{len(a_cards)}点</h2>{az_note}</div><div class="pick-list">{"".join(a_cards)}</div></section>' if a_cards else ""}
<section class="block" id="policy"><div class="sec-head"><h2>このページの選び方</h2></div><p class="notice">{esc(POLICY)}</p></section>
{B.share_bar(cfg, day_path(iso), f"{h1}: {day['theme']}", "このページを、だれかに送る")}
{nav}
<script type="application/ld+json">{ld}</script><script type="application/ld+json">{ld2}</script>"""
    return B.page(cfg, preview, path=day_path(iso), title=f"{h1}|{day['theme']} | {cfg['site_name']}", description=day["lede"][:110], body=body, og_image=B.og_for(f"picks/{iso}"))


def hub_page(d: dict, cfg: dict, preview: bool, days: list[dict]) -> str:
    B = _b()
    latest = days[0]
    rows = "".join(f'<li><a class="tile wide" href="{day_path(x["date"])}"><span><b>{esc(date_label(x["date"], True))}</b><small>{esc(x["theme"])}</small></span></a></li>' for x in days[:60])
    lead = "楽天市場とAmazonから、毎日10点ずつ。商品ページと購入者の声の傾向を読んで、渡す場面と、確かめたい点まで、自分たちの言葉でまとめています。"
    body = f"""{B.head_band("yellow", "", "毎日の、おすすめギフト", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("毎日のおすすめ", None)])}</div>
{B.pr_quiet(cfg)}
<section class="block"><div class="sec-head"><span class="eyebrow">Latest</span><h2>{esc(date_label(latest["date"]))}のおすすめ: {esc(latest["theme"])}</h2></div>
{highlight_tiles(latest, d, cfg)}<p class="more"><a class="btn" href="{day_path(latest["date"])}">すべて見る</a></p></section>
<section class="block"><div class="sec-head"><h2>これまでのおすすめ</h2></div><ul class="tiles wide">{rows}</ul></section>
<section class="block"><div class="sec-head"><h2>選び方</h2></div><p class="notice">{esc(POLICY)}</p></section>"""
    return B.page(cfg, preview, path="/picks/", title=f"毎日の、おすすめギフト | {cfg['site_name']}", description=lead, body=body)


def build_pages(d: dict, cfg: dict, preview: bool) -> dict[str, str]:
    days = d["c"].get("daily") or []
    if not days:
        return {}
    out = {"picks/index.html": hub_page(d, cfg, preview, days)}
    for i, day in enumerate(days):
        newer = days[i - 1]["date"] if i > 0 else None
        older = days[i + 1]["date"] if i + 1 < len(days) else None
        out[f"picks/{day['date']}/index.html"] = day_page(d, cfg, preview, day, i == 0, older, newer)
    return out


def home_block(d: dict, cfg: dict) -> str:
    """The top page's block with the newest day's three highlights."""
    days = d["c"].get("daily") or []
    if not days:
        return ""
    day = days[0]
    return (f'<section class="block"><div class="sec-head"><span class="eyebrow">Today\'s picks</span><h2>今日のおすすめ: {esc(day["theme"])}</h2>'
            f'<p>{"楽天市場とAmazonから10点ずつ。" if cfg.get("amazon_tracking_id") else "楽天市場から10点。"}{esc(date_label(day["date"]))}の商品を、1点ずつ調べて、まとめました。</p></div>'
            f'{highlight_tiles(day, d, cfg)}<p class="more"><a class="btn" href="{day_path(day["date"])}">すべて見る</a><a class="btn btn-sub" href="/picks/">過去のおすすめ</a></p></section>')


def feed_entries(d: dict, cfg: dict) -> list[tuple[str, str, str, str]]:
    base = cfg["site_url"].rstrip("/")
    return [(x["date"], f'今日のおすすめギフト {date_label(x["date"])}: {x["theme"]}', f"{base}{day_path(x['date'])}", x["lede"]) for x in (d["c"].get("daily") or [])]
