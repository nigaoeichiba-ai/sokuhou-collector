"""よろこぶプレゼント (yorokobu-present.com): a static gift-recommendation site.

    python sites/yorokobu/build.py [--release] [--out DIR] [--items out/yorokobu_items.json]

The editorial text is in sites/yorokobu/content/*.json; the products come from the Rakuten API (sites/yorokobu/fetch.py)
and are rebuilt every day.  A page never shows a product that was not in the fetched data.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import ogimage  # noqa: E402
from sites.yorokobu.picking import in_tier, score, usable  # noqa: E402
from sokuhou import rakuten  # noqa: E402
from sokuhou.sitekit import (BuildError, amazon_disclosure, asset_pages, crumbs, esc, layout, legal_pages,  # noqa: E402
                             missing_config, standard_files, write_pages)

SOURCE_HTML = ('商品の情報は楽天ウェブサービスを利用して取得しています。 '
               '<a href="https://webservice.rakuten.co.jp/" target="_blank">Supported by Rakuten Developers</a>')  # the credit HTML is prescribed: use as is
NAV = [("イベントから", "/occasion/", "/occasion/"), ("相手から", "/for/", "/for/"), ("季節の贈り物", "/#season", "/season-none/")]
SITE = {"nav": NAV[:2], "glyph": '<img src="/assets/img/logo-mark.webp" alt="" width="36" height="36">', "assets": HERE / "assets",
        "source_html": SOURCE_HTML}
# months (1-12) in which an occasion is worth showing as "いまが贈りどき"; the rest are evergreen
SEASON = {
    "mothers-day": (4, 5), "fathers-day": (5, 6), "respect-for-aged-day": (8, 9), "christmas": (11, 12),
    "valentine": (1, 2), "white-day": (2, 3), "school-entrance": (3, 4), "graduation": (2, 3), "coming-of-age": (12, 1),
    "new-job": (3, 4), "promotion": (3, 4), "retirement": (2, 3), "farewell": (3, 4), "oseibo": (11, 12),
    "ochugen": (6, 7), "year-end-gathering": (11, 12), "homecoming": (7, 8, 12),
}
NAME_LIMIT = 56
PORTRAIT_SHOWN = 2


def yen(v: int) -> str:
    return f"¥{v:,}"


def short(name: str, limit: int = NAME_LIMIT) -> str:
    name = " ".join(name.split())
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"


def amazon_url(cfg: dict, query: str, low: int | None = None, high: int | None = None) -> str:
    """Amazon.co.jp search results for a keyword (optionally within a price range), with the Associates tracking ID."""
    price = (f"&low-price={low}" if low else "") + (f"&high-price={high}" if high else "")
    return f"https://www.amazon.co.jp/s?k={quote(query, safe='')}{price}&tag={quote(cfg['amazon_tracking_id'], safe='')}"


def pr_lead(cfg: dict) -> str:
    return ('<p class="pr-lead"><span class="pr-note">PR</span>このページには、広告(楽天アフィリエイト'
            + ('・Amazonアソシエイト' if cfg.get("amazon_tracking_id") else "")
            + ')のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。</p>')


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    return layout(SITE, cfg, preview, scripts=True, head_extra=FONTS, **kw)


OG: set = set()   # the share-card images drawn in this build ("gift/<key>", "occasion/<slug>", "for/<slug>", "default")


def og_for(name: str) -> str:
    return f"/og/{name}.png" if name in OG else "/assets/img/og.webp"


def share_bar(cfg: dict, path: str, text: str, label: str = "この候補、誰かに相談する") -> str:
    """LINE / X / copy-link buttons.  The shared text carries our page URL only, never an affiliate link."""
    url = cfg["site_url"].rstrip("/") + path
    line = "https://line.me/R/share?text=" + quote(f"{text}\n{url}", safe="")
    x = "https://twitter.com/intent/tweet?text=" + quote(text, safe="") + "&url=" + quote(url, safe="")
    return (f'<div class="share"><span class="share-label">{esc(label)}</span>'
            f'<a class="share-btn line" href="{esc(line)}" target="_blank" rel="noopener">LINEで送る</a>'
            f'<a class="share-btn x" href="{esc(x)}" target="_blank" rel="noopener">Xで共有</a>'
            f'<button type="button" class="share-btn copy" data-url="{esc(url)}">リンクをコピー</button></div>')


def icon_img(kind: str, slug: str, size: int = 64) -> str:
    return f'<img class="ic" src="/assets/img/{kind}/{slug}.webp" alt="" width="{size}" height="{size}" loading="lazy">'


def ul(items: list[str], cls: str = "") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


# ---------------------------------------------------------------- decoration (inline SVG, drawn here)

INK = "#2b1b14"
PALETTE = {"pink": "#ff4d6d", "yellow": "#ffc93c", "sky": "#38bdf8", "mint": "#2fd09b", "lilac": "#a78bfa", "orange": "#ff8a3d", "white": "#ffffff"}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Mochiy+Pop+One'
         '&family=Zen+Maru+Gothic:wght@500;700;900&display=swap">\n')
SHAPES = {
    "balloon": ('<svg viewBox="0 0 60 96"><path d="M30 64c-8 12 6 18-2 30" fill="none" stroke="{ink}" stroke-width="2.5" stroke-linecap="round"/>'
                '<path d="M30 4C14 4 5 17 5 32c0 17 13 29 25 29s25-12 25-29C55 17 46 4 30 4z" fill="{c}" stroke="{ink}" stroke-width="3"/>'
                '<path d="M25 62h10l-5 8z" fill="{c}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/>'
                '<ellipse cx="19" cy="22" rx="4.5" ry="9" fill="#fff" opacity=".65" transform="rotate(22 19 22)"/></svg>'),
    "star": ('<svg viewBox="0 0 60 60"><path d="M30 4l7.6 16.2 17.7 2.2-13 12.2 3.4 17.6L30 43.4 14.3 52.2l3.4-17.6-13-12.2 17.7-2.2z" '
             'fill="{c}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/></svg>'),
    "sparkle": ('<svg viewBox="0 0 60 60"><path d="M30 2c2 14 5 22 28 28-23 6-26 14-28 28-2-14-5-22-28-28C25 24 28 16 30 2z" '
                'fill="{c}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/></svg>'),
    "dot": '<svg viewBox="0 0 30 30"><circle cx="15" cy="15" r="11" fill="{c}" stroke="{ink}" stroke-width="3"/></svg>',
    "bar": '<svg viewBox="0 0 60 30"><rect x="5" y="9" width="50" height="13" rx="6.5" fill="{c}" stroke="{ink}" stroke-width="3"/></svg>',
    "tri": '<svg viewBox="0 0 50 50"><path d="M25 7l19 34H6z" fill="{c}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/></svg>',
    "box": ('<svg viewBox="0 0 80 80"><rect x="8" y="30" width="64" height="44" rx="6" fill="{c}" stroke="{ink}" stroke-width="3"/>'
            '<rect x="4" y="20" width="72" height="16" rx="5" fill="{c}" stroke="{ink}" stroke-width="3"/>'
            '<path d="M40 20v54" stroke="{ink}" stroke-width="3"/><rect x="34" y="20" width="12" height="54" fill="#fff" stroke="{ink}" stroke-width="3"/>'
            '<path d="M40 20c-10-16-26-10-18-2 6 6 18 2 18 2zM40 20c10-16 26-10 18-2-6 6-18 2-18 2z" fill="#fff" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/></svg>'),
}


def deco(kind: str, color: str, x: str, y: str, size: int, rot: int = 0, delay: float = 0.0, motion: str = "float") -> str:
    svg = SHAPES[kind].format(c=PALETTE[color], ink=INK)
    return (f'<span class="deco {motion}" aria-hidden="true" style="left:{x};top:{y};width:{size}px;--r:{rot}deg;transform:rotate({rot}deg);'
            f'animation-delay:{delay}s">{svg}</span>')


def party(kind: str = "hero") -> str:
    """The scattered balloons, stars and confetti around a hero."""
    if kind == "hero":
        items = [("balloon", "pink", "2%", "-6%", 54, -8, 0), ("balloon", "sky", "88%", "2%", 58, 10, 1.2), ("star", "white", "46%", "-4%", 40, 12, .6),
                 ("sparkle", "white", "92%", "46%", 42, 0, 2), ("dot", "pink", "6%", "46%", 22, 0, .3), ("bar", "mint", "52%", "86%", 46, -24, .9),
                 ("tri", "lilac", "40%", "30%", 30, 18, 1.6), ("box", "pink", "-1%", "72%", 84, -10, 1.1), ("sparkle", "yellow", "64%", "6%", 34, 0, .4)]
    else:
        items = [("star", "white", "1%", "8%", 34, 12, 0), ("dot", "pink", "44%", "12%", 20, 0, .8), ("sparkle", "white", "90%", "14%", 36, 0, 1.4),
                 ("bar", "mint", "70%", "74%", 40, -20, .5), ("balloon", "pink", "94%", "52%", 40, 10, 1)]
    return "".join(deco(k, c, x, y, sz, r, d) for k, c, x, y, sz, r, d in items)


def scallop_class(color: str) -> str:
    return f"band {color} scallop"


# ---------------------------------------------------------------- products

TYPE_ORDER = ["実用品", "食べもの・飲みもの", "ファッション小物", "癒し・リラックス", "思い出・名入れ", "体験・お出かけ", "趣味・ホビー", "おもしろ・サプライズ", "子ども向け"]
SOMMELIER_IMGS = ["sommelier-gift", "sommelier-taste", "sommelier-tray", "sommelier-spin"]
# words in the operator's own caricature-shop listings that tie a listing to an occasion (the shop is shown only where it truly fits)
PORTRAIT_KEYS = {
    "retirement": ("退職", "定年"), "longevity": ("還暦", "古希", "喜寿", "傘寿", "米寿", "長寿"), "wedding-gift": ("結婚祝", "結婚式", "ウェルカム"),
    "wedding-anniversary": ("結婚記念", "金婚", "銀婚"), "birth-gift": ("出産", "命名"), "birthday": ("誕生日",), "mothers-day": ("母の日", "お母さん"),
    "fathers-day": ("父の日", "お父さん"), "respect-for-aged-day": ("敬老",), "farewell": ("送別", "異動"), "thanks": ("感謝",),
    "year-end-gathering": ("両親", "祖父母", "家族"),
}


def rakuten_link(cfg: dict, target: str) -> str:
    return rakuten.affiliate_link(cfg["rakuten_affiliate_id"], cfg.get("rakuten_tracking_id"), target)


def search_link(cfg: dict, keyword: str) -> str:
    return rakuten_link(cfg, rakuten.search_url(keyword))


def item_card(cfg: dict, it: dict, own: bool = False, rank: int | None = None, tier: str = "", kind: str = "") -> str:
    url = rakuten.clean_item_url(it["url"])  # also unwraps data fetched before the API's redirect links were handled
    name = it.get("display") or rakuten.clean_title(it["name"])
    if own:
        href, rel = url, "noopener"
    else:
        href, rel = rakuten_link(cfg, url), "sponsored nofollow noopener"
    bits = []
    if it["reviews"]:
        bits.append(f'<span class="stars" aria-label="レビュー平均 {it["rating"]:.2f}">★{it["rating"]:.1f}</span><span>({it["reviews"]:,}件)</span>')
    if it["free_shipping"]:
        bits.append('<span class="ship">送料無料</span>')
    if it.get("gift"):
        bits.append('<span class="tagx">ギフト対応</span>')
    if it.get("appoint"):
        bits.append('<span class="tagx">日付指定可</span>')
    note = '<p class="own">運営者のショップ</p>' if own else ""
    if it.get("note"):  # the editors' one-line reason for picking this product
        note += f'<p class="pick-note">{esc(it["note"])}</p>'
    label = "ショップで見る" if own else "楽天市場で見る"
    badge = f'<span class="rank r{rank}">{rank}</span>' if rank and rank <= 3 and not own else ""
    attrs = (f'data-code="{esc(it["code"])}" data-price="{it["price"]}" data-reviews="{it["reviews"]}" data-rating="{it["rating"]}" '
             f'data-ship="{1 if it["free_shipping"] else 0}" data-gift="{1 if it.get("gift") else 0}" data-tier="{esc(tier)}" data-type="{esc(kind)}" '
             f'data-rank="{rank or 0}"')
    fav = (f'<button type="button" class="fav" aria-label="気になるリストに入れる" aria-pressed="false" data-name="{esc(short(name, 40))}" '
           f'data-price="{it["price"]}" data-url="{esc(url)}">♡</button>')
    return (f'<li class="item" {attrs}>{badge}{fav}<a class="item-img" href="{esc(href)}" rel="{rel}" target="_blank">'
            f'<img src="{esc(it["image"])}" alt="{esc(short(name, 40))}" width="300" height="300" loading="lazy"></a>'
            f'<div class="item-body"><h3><a href="{esc(href)}" rel="{rel}" target="_blank">{esc(short(name))}</a></h3>'
            f'<p class="price">{yen(it["price"])}</p><p class="meta">{"".join(bits)}</p>{note}'
            f'<a class="btn" href="{esc(href)}" rel="{rel}" target="_blank">{label}</a></div></li>')


def item_grid(cfg: dict, items: list[dict], cls: str = "items") -> str:
    return f'<ul class="{cls}">' + "".join(item_card(cfg, it, rank=i + 1 if i < 3 else None) for i, it in enumerate(items)) + "</ul>"


def top_items(lists: list[list[dict]], n: int = 6) -> list[dict]:
    seen, out = set(), []
    for it in sorted((i for lst in lists for i in lst), key=lambda i: -score(i)):
        if it["code"] in seen:
            continue
        seen.add(it["code"])
        out.append(it)
        if len(out) >= n:
            break
    return out


def freshness(d: dict) -> str:
    """Rakuten's rule: if data is not refreshed hourly, show the fetch time next to the prices and its prescribed disclaimer."""
    name = esc(d["site_name"])
    return (f'<p class="fresh">価格・在庫は{d["fetched_label"]}時点の情報です。このサイトで掲載されている情報は、{name}の作成者により運営されています。'
            "価格、販売可能情報は、変更される場合があります。購入時に楽天市場店舗(www.rakuten.co.jp)に表示されている価格が、その商品の販売に適用されます。</p>")


def pr_quiet(cfg: dict) -> str:
    return '<p class="pr-quiet">PR:本ページには広告(アフィリエイトリンク)が含まれます。掲載する商品は、編集方針にもとづいて選んでいます。</p>'


def pair_items(d: dict, key: str) -> tuple[list[dict], dict, list[dict]]:
    """(ideas, tiers, union of every product on the page, best first) for one page; copes with data fetched before ideas existed."""
    v = d["pairs"].get(key) or {}
    ideas = v.get("ideas", []) if "ideas" in v else []
    tiers = v.get("tiers", {}) if "tiers" in v else {t: lst for t, lst in v.items() if isinstance(lst, list)}
    seen, union = set(), []
    for it in [i for idea in ideas for i in idea["items"]] + [i for lst in tiers.values() for i in lst]:
        if it["code"] not in seen:
            seen.add(it["code"])
            union.append(it)
    union.sort(key=lambda i: -score(i))
    return ideas, tiers, union


def own_item(d: dict, occasion: str) -> dict | None:
    """The operator's own caricature listing that matches this occasion by its title words, shown as a plain card; None when none fits."""
    keys = PORTRAIT_KEYS.get(occasion, ())
    for it in d["portrait"]:
        hit = next((k for k in keys if k in it["name"]), None)
        if hit:
            return {**it, "display": f"手描きの似顔絵ギフト({hit}に)"}
    return None


def tier_of(price: int, tiers: list[dict]) -> str:
    for t in tiers:
        if in_tier(price, t):
            return t["slug"]
    return ""


# ---------------------------------------------------------------- pages

COLORS = ["yellow", "pink", "sky", "mint"]
# the costume that fits an occasion (head of its pages); the others use the expression set
OCC_MASCOT = {"christmas": "season-christmas", "year-end-gathering": "season-party", "birthday": "season-birthday",
              "valentine": "season-valentine", "mothers-day": "season-mothers", "fathers-day": "season-fathers", "ochugen": "season-summer"}


def tile(href: str, kind: str, slug: str, name: str, small: str = "", wide: bool = False) -> str:
    sm = f"<small>{esc(small)}</small>" if small else ""
    return (f'<li><a class="tile{" wide" if wide else ""}" href="{href}"><span class="ic-wrap">{icon_img(kind, slug, 96)}</span>'
            f'<span><b>{esc(name)}</b>{sm}</span></a></li>')


def round_chip(href: str, kind: str, slug: str, name: str) -> str:
    return f'<li><a class="chip-ic" href="{href}"><span class="ic-wrap">{icon_img(kind, slug, 80)}</span><span>{esc(name)}</span></a></li>'


def head_band(color: str, icons: str, h1: str, lead: str, single: bool = False, mascot: str = "b-wink") -> str:
    return (f'<div class="{scallop_class(color)} pagehead-band dots"><div class="in"><div class="pagehead">'
            f'<div class="pagehead-ic{" single" if single else ""}">{icons}</div><div><h1>{h1}</h1><p class="lead">{esc(lead)}</p></div></div>'
            f'<img class="head-mascot" src="/assets/img/{mascot}.webp" alt="" width="190" height="150" loading="lazy"></div>'
            f'{party("page")}</div>')


def ic_wrap(kind: str, slug: str) -> str:
    return f'<span class="ic-wrap">{icon_img(kind, slug, 96)}</span>'


def bird_say(img: str, text: str, cls: str = "") -> str:
    """A bird speaking: the avatar and a speech bubble."""
    return f'<div class="bird-say {cls}"><img src="/assets/img/{img}.webp" alt="" width="120" height="90" loading="lazy"><p>{text}</p></div>'


def idea_card(cfg: dict, idea: dict, i: int, tiers: list[dict]) -> str:
    cards = "".join(item_card(cfg, it, tier=tier_of(it["price"], tiers), kind=idea["type"]) for it in idea["items"][:4])
    body = f'<ul class="items mini">{cards}</ul>' if cards else '<p class="notice">この種類の商品は、いま、見つかりませんでした。下のリンクから、楽天市場で、探せます。</p>'
    return (f'<article class="idea"><header><span class="type">{esc(idea["type"])}</span><h3>{esc(idea["label"])}</h3></header>'
            f'{bird_say(SOMMELIER_IMGS[i % 4], esc(idea["why"]), "sommelier")}{body}'
            f'<p class="idea-more"><a href="{esc(search_link(cfg, idea["query"]))}" rel="sponsored nofollow noopener" target="_blank">'
            f'楽天市場で「{esc(idea["query"])}」をもっと見る</a></p></article>')


def finder_map(d: dict) -> dict:
    """{occasion: {recipient: [budget tiers that have products]}} for the picker on the top page."""
    out: dict = {}
    for p in d["c"]["pairs"]:
        _, tiers, union = pair_items(d, ct.pair_key(p))
        have = [t["slug"] for t in d["c"]["filters"]["tiers"] if any(in_tier(i["price"], t) for i in union)]
        out.setdefault(p["occasion"], {})[p["recipient"]] = have if d["pairs"] else [t["slug"] for t in d["c"]["filters"]["tiers"]]
    return out


def concierge(cfg: dict, d: dict, p: dict | None, heading: str = "コンシェルジュに相談する") -> str:
    kws = (p or {}).get("keywords", [])[:8]
    chips = "".join(f'<li><a href="{esc(search_link(cfg, k))}" rel="sponsored nofollow noopener" target="_blank">{esc(k)}</a></li>' for k in kws)
    ctx = esc(" ".join(x for x in [(p or {}).get("recipient_keyword", "")] if x))
    return f"""<section class="concierge band-soft" id="concierge"><div class="concierge-in">
<img class="concierge-bird hop" src="/assets/img/concierge-note.webp" alt="" width="190" height="150" loading="lazy">
<div class="concierge-body"><h2>{heading}</h2>
<p>その人のことを、ひとこと教えてください(好きなもの、趣味、年齢など)。楽天市場で、近い商品を探すお手伝いをします。</p>
<form class="kw-form" data-aff="{esc(cfg['rakuten_affiliate_id'])}" data-trk="{esc(cfg.get('rakuten_tracking_id') or '')}" data-ctx="{ctx}">
<input type="search" name="q" placeholder="例: ガーデニングが好きな60代" aria-label="その人のこと、ほしいもの">
<button type="submit" class="btn">楽天市場でさがす</button></form>
<ul class="kw-chips">{chips}</ul></div></div></section>"""


def pair_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    c = d["c"]
    occ, rec = c["occ"][p["occasion"]], c["rec"][p["recipient"]]
    key = ct.pair_key(p)
    ideas, tiers_map, union = pair_items(d, key)
    tier_defs = [c["tiers"][t] for t in p["tiers"]]
    own = own_item(d, p["occasion"]) if p.get("portrait_note") else None
    grid_items = list(union)
    # the proposals (sommelier)
    proposals = "".join(idea_card(cfg, idea, i, c["filters"]["tiers"]) for i, idea in enumerate(ideas) if idea["items"])
    if proposals:
        proposals = (f'<section class="proposals"><div class="sec-title"><span class="tag">ソムリエの提案</span><h2>{esc(rec["name"])}への{esc(occ["name"])}、'
                     f'こんな贈り方はどうでしょう</h2></div><div class="idea-grid">{proposals}</div></section>')
    # the filterable list
    all_types = [t for t in TYPE_ORDER if any(idea["type"] == t and idea["items"] for idea in ideas)]
    idea_type = {it["code"]: idea["type"] for idea in ideas for it in idea["items"]}
    li = "".join(item_card(cfg, it, rank=None, tier=tier_of(it["price"], c["filters"]["tiers"]), kind=idea_type.get(it["code"], "")) for it in grid_items)
    if own:
        li += item_card(cfg, own, own=True, tier=tier_of(own["price"], c["filters"]["tiers"]), kind="思い出・名入れ")
    tier_btns = "".join(f'<button type="button" class="chipbtn" data-v="{t["slug"]}">{esc(t["label"])}</button>'
                        for t in c["filters"]["tiers"] if any(in_tier(i["price"], t) for i in grid_items))
    type_btns = "".join(f'<button type="button" class="chipbtn" data-v="{esc(t)}">{esc(t)}</button>' for t in all_types)
    browse = ""
    if grid_items:
        browse = f"""<section class="browse" id="browse"><div class="sec-title"><span class="tag">ナビゲーター</span><h2>条件でしぼって、くらべる</h2></div>
{bird_say("navi-map", "予算や種類を選ぶと、ぴったりのものだけを表示します。並べかえもできます。", "navigator")}
<div class="controls">
<div class="ctl"><b>予算</b><div class="chipset" data-filter="tier"><button type="button" class="chipbtn on" data-v="">すべて</button>{tier_btns}</div></div>
{f'<div class="ctl"><b>種類</b><div class="chipset" data-filter="type"><button type="button" class="chipbtn on" data-v="">すべて</button>{type_btns}</div></div>' if type_btns else ''}
<div class="ctl row"><label>並べかえ <select data-sort><option value="rank">おすすめ順</option><option value="reviews">レビュー件数が多い順</option>
<option value="rating">評価が高い順</option><option value="price-asc">価格が安い順</option><option value="price-desc">価格が高い順</option></select></label>
<label class="chk"><input type="checkbox" data-ship> 送料無料</label><label class="chk"><input type="checkbox" data-gift> ギフト対応</label></div></div>
<p class="count" aria-live="polite"></p>
<ul class="items grid-all">{li}</ul>
<p class="empty" hidden>この条件に合う商品は、見つかりませんでした。条件をゆるめるか、下の「コンシェルジュ」で、楽天市場を直接さがしてみましょう。</p>
{freshness(d)}</section>"""
    else:
        browse = '<section class="browse"><p class="notice">いま表示できる商品が、見つかりませんでした。下のコンシェルジュから、楽天市場で、探してみてください。</p></section>'
    own_note = ""
    if own:
        own_note = (f'<aside class="own-slim"><b>長く残る贈りものなら</b><span>手描きの似顔絵という選び方もあります。店主が制作しています(一覧のなかの「運営者のショップ」の商品です)。</span></aside>')
    avoid = occ["avoid"][:1] + rec["avoid"][:1]
    related_occ = [q for q in c["pairs"] if q["occasion"] == p["occasion"] and ct.pair_key(q) != key][:8]
    related_rec = [q for q in c["pairs"] if q["recipient"] == p["recipient"] and ct.pair_key(q) != key][:8]

    def links(items):
        return "".join(f'<li><a href="/gift/{ct.pair_key(q)}/">{esc(q["title"].split(" ")[0])}</a></li>' for q in items)

    amazon = ""
    if cfg.get("amazon_tracking_id"):
        amazon = (f'<p class="more"><a class="btn btn-sub" href="{esc(amazon_url(cfg, p["queries"][0]))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'Amazonでも探す</a></p>{amazon_disclosure(cfg)}')
    color = COLORS[list(c["occ"]).index(p["occasion"]) % 4]
    head = head_band(color, f'{ic_wrap("occasion", occ["slug"])}<span class="x">×</span>{ic_wrap("recipient", rec["slug"])}', esc(p["title"]), p["lead"],
                     mascot=OCC_MASCOT.get(p["occasion"], ("r-joy", "b-sparkle", "r-wink", "b-joy")[list(c["occ"]).index(p["occasion"]) % 4]))
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (occ["name"], f"/occasion/{occ['slug']}/"), (p["title"].split(" ")[0], None)])}</div>
{pr_quiet(cfg)}
{share_bar(cfg, f"/gift/{key}/", f"{p['title'].split(' ')[0]}の候補を見つけたよ。どれがよさそう?")}
<section class="why-how"><div class="cols"><div><h2><span class="scribble">喜ばれやすい理由</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["reasons"])}</ol></div>
<div class="how"><h2><span class="scribble">選び方のポイント</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["how_to_choose"])}</ol></div></div></section>
{proposals}
{own_note}
{browse}
{concierge(cfg, d, p)}
<section class="avoid" style="margin-top:48px"><h2><span class="scribble">気をつけたいこと</span></h2>{ul(avoid, "warn")}</section>
<p style="margin-top:40px">{amazon}</p>
<section class="related" style="margin-top:40px"><h2><span class="scribble">あわせて読みたい</span></h2>
<div class="cols"><div><h3>{esc(occ["name"])}の、ほかの相手</h3><ul class="plain">{links(related_occ)}</ul></div>
<div><h3>{esc(rec["name"])}への、ほかのイベント</h3><ul class="plain">{links(related_rec)}</ul></div></div></section>"""
    return page(cfg, preview, path=f"/gift/{key}/", title=f"{p['title']} | {cfg['site_name']}", description=p["lead"][:110], body=body,
                og_image=og_for(f"gift/{key}"))


def occasion_page(d: dict, cfg: dict, preview: bool, o: dict) -> str:
    c = d["c"]
    pairs = [p for p in c["pairs"] if p["occasion"] == o["slug"]]
    cards = "".join(tile(f'/gift/{ct.pair_key(p)}/', "recipient", p["recipient"], f'{c["rec"][p["recipient"]]["name"]}へ', p["title"].split(" ")[0]) for p in pairs)
    featured = top_items([pair_items(d, ct.pair_key(p))[2] for p in pairs])
    shown = (f'<section style="margin-top:50px"><h2><span class="scribble">選ばれている贈り物の例</span></h2>{item_grid(cfg, featured)}{freshness(d)}</section>' if featured else "")
    color = COLORS[list(c["occ"]).index(o["slug"]) % 4]
    head = head_band(color, ic_wrap("occasion", o["slug"]), f'{esc(o["name"])}の<wbr>プレゼント', o["blurb"], single=True, mascot=OCC_MASCOT.get(o["slug"], "b-wink"))
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("イベント", "/occasion/"), (o["name"], None)])}</div>
{pr_quiet(cfg)}
<section style="margin-top:40px" class="cols"><div><h2><span class="scribble">贈る時期の目安</span></h2><p>{esc(o["timing"])}</p></div>
<div><h2><span class="scribble">選ぶポイント</span></h2><ol class="panel-grid" style="grid-template-columns:1fr">{"".join(f"<li>{esc(x)}</li>" for x in o["tips"])}</ol></div></section>
<section style="margin-top:50px"><h2><span class="scribble">相手を選んで、おすすめを見る</span></h2><ul class="tiles">{cards}</ul></section>
{shown}
<section class="avoid" style="margin-top:48px"><h2><span class="scribble">避けたほうがよいこと</span></h2>{ul(o["avoid"], "warn")}</section>"""
    return page(cfg, preview, path=f"/occasion/{o['slug']}/", title=f"{o['name']}のプレゼント 選び方と相手別のおすすめ | {cfg['site_name']}",
                description=o["blurb"][:110], body=body, og_image=og_for(f"occasion/{o['slug']}"))


def recipient_page(d: dict, cfg: dict, preview: bool, r: dict) -> str:
    c = d["c"]
    pairs = [p for p in c["pairs"] if p["recipient"] == r["slug"]]
    cards = "".join(tile(f'/gift/{ct.pair_key(p)}/', "occasion", p["occasion"], c["occ"][p["occasion"]]["name"], p["title"].split(" ")[0]) for p in pairs)
    featured = top_items([pair_items(d, ct.pair_key(p))[2] for p in pairs])
    shown = (f'<section style="margin-top:50px"><h2><span class="scribble">選ばれている贈り物の例</span></h2>{item_grid(cfg, featured)}{freshness(d)}</section>' if featured else "")
    color = COLORS[list(c["rec"]).index(r["slug"]) % 4]
    head = head_band(color, ic_wrap("recipient", r["slug"]), f'{esc(r["name"])}への<wbr>プレゼント', r["blurb"], single=True, mascot="r-sparkle")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("相手から", "/for/"), (r["name"], None)])}</div>
{pr_quiet(cfg)}
<section style="margin-top:40px" class="cols"><div><h2><span class="scribble">喜ばれやすいもの</span></h2><ol class="panel-grid" style="grid-template-columns:1fr">{"".join(f"<li>{esc(x)}</li>" for x in r["likes"])}</ol></div>
<div class="avoid"><h2><span class="scribble">避けたいもの</span></h2>{ul(r["avoid"], "warn")}</div></section>
<section style="margin-top:50px"><h2><span class="scribble">イベントを選んで、おすすめを見る</span></h2><ul class="tiles">{cards}</ul></section>
{shown}"""
    return page(cfg, preview, path=f"/for/{r['slug']}/", title=f"{r['name']}へのプレゼント イベント別のおすすめ | {cfg['site_name']}",
                description=r["blurb"][:110], body=body, og_image=og_for(f"for/{r['slug']}"))


def hub_page(d: dict, cfg: dict, preview: bool, kind: str) -> str:
    c = d["c"]
    if kind == "occasion":
        rows = "".join(tile(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"], o["season"]) for o in c["occasions"])
        title, h1, lead, path, color = "イベントから探す", "イベントから、<wbr>プレゼントを探す", "贈るきっかけを選ぶと、相手ごとのおすすめが見つかります。", "/occasion/", "pink"
    else:
        rows = "".join(tile(f'/for/{r["slug"]}/', "recipient", r["slug"], r["name"]) for r in c["recipients"])
        title, h1, lead, path, color = "贈る相手から探す", "贈る相手から、<wbr>プレゼントを探す", "贈る相手を選ぶと、イベントごとのおすすめが見つかります。", "/for/", "sky"
    body = f"""{head_band(color, f'<img class="pair-mini" src="/assets/img/r-joy.webp" alt="" width="170" height="155">', h1, lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (title, None)])}</div>
<section style="margin-top:34px"><ul class="tiles">{rows}</ul></section>"""
    return page(cfg, preview, path=path, title=f"{title} | {cfg['site_name']}", description=lead, body=body)


def season_occasions(c: dict, today: date) -> list[dict]:
    months = {today.month, today.month % 12 + 1}
    out = [o for o in c["occasions"] if o["slug"] in SEASON and months & set(SEASON[o["slug"]])]
    return out or [o for o in c["occasions"] if o["slug"] not in SEASON][:4]


def finder(d: dict) -> str:
    """Event + recipient + budget picker. Nothing is pre-selected; the options that cannot lead to a page are disabled by the script
    (data-map: event -> recipient -> budgets that have products)."""
    c = d["c"]
    occ = "".join(f'<option value="{o["slug"]}">{esc(o["name"])}</option>' for o in c["occasions"])
    rec = "".join(f'<option value="{r["slug"]}">{esc(r["name"])}</option>' for r in c["recipients"])
    bud = "".join(f'<option value="{t["slug"]}">{esc(t["label"])}</option>' for t in c["filters"]["tiers"])
    fmap = esc(json.dumps(finder_map(d), separators=(",", ":")))
    return (f'<form class="finder" action="/occasion/" method="get" data-map="{fmap}"><img class="peek hop" src="/assets/img/concierge-bell.webp" alt="" width="96" height="73">'
            f'<p class="finder-title">贈り物をさがす</p>'
            f'<div class="finder-row"><select name="o" aria-label="イベント"><option value="">イベント</option>{occ}</select>'
            f'<select name="r" aria-label="贈る相手"><option value="">贈る相手</option>{rec}</select>'
            f'<select name="b" aria-label="予算"><option value="">予算(指定なし)</option>{bud}</select><button type="submit">さがす</button></div>'
            f'<p class="finder-msg" role="status" hidden></p></form>')


def index_page(d: dict, cfg: dict, preview: bool, today: date) -> str:
    c = d["c"]
    season = "".join(tile(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"], o["timing"][:30] + "…", wide=True) for o in season_occasions(c, today)[:6])
    occ = "".join(round_chip(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"]) for o in c["occasions"])
    rec = "".join(round_chip(f'/for/{r["slug"]}/', "recipient", r["slug"], r["name"]) for r in c["recipients"])
    popular = [p for p in c["pairs"] if p["occasion"] in ("birthday", "year-end-gathering", "mothers-day", "christmas")][:12]
    pop = "".join(f'<li><a href="/gift/{ct.pair_key(p)}/">{esc(p["title"].split(" ")[0])}</a></li>' for p in popular)
    ticker = "".join(f"<span>{esc(o['name'])}</span>" for o in c["occasions"])
    ticker = ticker + ticker
    body = f"""<section class="band yellow dots hero scallop-b"><div class="in">
<div class="hero-text"><span class="sticker">プレゼント選びを、わくわくに!</span>
<h1><span class="nb">相手が<em>よろこぶ</em></span><br><span class="nb">プレゼント、</span><br><span class="nb">いっしょに見つけよう</span></h1>
<p class="lead">イベントと贈る相手から、喜ばれやすい選び方と、おすすめの商品が見つかります。</p>
{finder(d)}
<p class="hero-cta"><a class="btn big" href="/occasion/">イベントから探す</a><a class="btn big btn-sub" href="/for/">相手から探す</a></p></div>
<div class="hero-art">{party("hero")}<img class="pair" src="/assets/img/mascot-pair.webp" alt="赤と青のマフラーをしたシマエナガのふたりが、プレゼントを持って喜んでいる" width="1400" height="579"></div>
</div></section>
<div class="marquee" aria-hidden="true"><div class="track">{ticker}</div></div>
{pr_quiet(cfg)}
<section style="margin-top:56px"><div class="sec-head"><span class="sticker">NOW</span><h2>いまが<span class="scribble">贈りどき</span></h2><p>これから迎えるイベントのプレゼントを、先取りで。</p></div>
<ul class="tiles wide">{season}</ul></section>
<section class="band sky scallop" style="margin-top:70px"><div class="in"><div class="sec-head"><img class="step-mascot hop" src="/assets/img/navi-scope.webp" alt="望遠鏡をのぞくシマエナガと、道を指さすシマエナガ" width="380" height="193" loading="lazy"><h2>選び方は、かんたん<span class="scribble">3ステップ</span></h2></div>
<ol class="steps"><li><img src="/assets/img/occasion/birthday.webp" alt="" width="84" height="84" loading="lazy"><b>イベントを選ぶ</b><p>誕生日、母の日、クリスマスなど、贈るきっかけを選びます。</p></li>
<li><img src="/assets/img/recipient/mother.webp" alt="" width="84" height="84" loading="lazy"><b>相手を選ぶ</b><p>彼氏、母、同僚など、贈る相手に合わせた選び方が見つかります。</p></li>
<li><img src="/assets/img/occasion/thanks.webp" alt="" width="84" height="84" loading="lazy"><b>予算でえらぶ</b><p>3,000円以内から、2万円以上まで。予算に合う商品を比べられます。</p></li></ol></div></section>
<section class="band pink scallop"><div class="in"><div class="sec-head"><h2>イベントから<span class="scribble">探す</span></h2><p>贈るきっかけを選んでね。</p></div>
<ul class="chip-grid">{occ}</ul></div></section>
<section class="band cream flat"><div class="in"><div class="sec-head"><h2>贈る相手から<span class="scribble">探す</span></h2><p>だれに贈る?</p></div>
<ul class="chip-grid round">{rec}</ul></div></section>
<section class="band mint flat"><div class="in"><div class="sec-head"><h2>よく読まれている、<span class="scribble">おすすめページ</span></h2></div>
<ul class="plain cols2 chips">{pop}</ul></div></section>
<section class="band yellow dots scallop about-home"><div class="in">
<div><img src="/assets/img/pair-gift.webp" alt="" width="600" height="239" loading="lazy" style="width:100%;max-width:460px;display:block;margin:0 auto"></div>
<div class="bubble"><h2 style="font-size:1.3rem">このサイトについて</h2>
<p>「何を贈ればいいか分からない」というときに、<strong>イベント</strong>と<strong>贈る相手</strong>から、選び方のポイントと、商品の例を探せるサイトです。</p>
<p>商品は、楽天市場の情報を、毎日、自動で更新して表示しています。シマエナガのふたりが、あなたの「贈りたい気持ち」を、応援します。</p></div></div></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} イベントと相手から、喜ばれるプレゼントを探す",
                description="誕生日・母の日・クリスマスなど、イベントと贈る相手から、喜ばれやすいプレゼントの選び方と、おすすめの商品が見つかります。", body=body,
                og_image=og_for("default"))


# ---------------------------------------------------------------- site

def prepare(c: dict, items: dict | None, cfg: dict) -> dict:
    items = items or {"pairs": {}, "portrait": [], "fetched_at": None}
    f = items.get("fetched_at")
    label = "取得日時不明"
    if f:
        t = datetime.fromisoformat(f)
        label = f"{t.year}年{t.month}月{t.day}日 {t.hour}:{t.minute:02d}"
    # the stored lists were chosen at fetch time; apply today's rules again (relaxed superset) so a rule change shows without refetching
    owner = {ct.pair_key(p): p["recipient"] for p in c["pairs"]}
    pairs = {}
    for k, v in items.get("pairs", {}).items():
        def ok(i, k=k):
            return usable(i, c["filters"], owner.get(k), relaxed=True)
        if "ideas" in v:
            pairs[k] = {"ideas": [{**idea, "items": [i for i in idea["items"] if ok(i)]} for idea in v["ideas"]],
                        "tiers": {t: [i for i in lst if ok(i)] for t, lst in v["tiers"].items()}}
        else:  # data fetched before ideas existed: budget lists only
            pairs[k] = {t: [i for i in lst if ok(i)] for t, lst in v.items() if isinstance(lst, list)}
    return {"c": c, "pairs": pairs, "portrait": items.get("portrait", []), "fetched_label": label, "site_name": cfg["site_name"],
            "fetched_date": (f or date.today().isoformat())[:10]}


def render_site(c: dict, items: dict | None, cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    if release and not (items and items.get("pairs")):
        raise BuildError("release build refused: no fetched products (run sites/yorokobu/fetch.py first)")
    preview = bool(missing)
    today = today or date.today()
    d = prepare(c, items, cfg)
    cards: dict[str, bytes] = {}
    OG.clear()
    if ogimage.available():
        site = cfg["site_name"]
        birds = ("r-joy", "b-sparkle", "r-wink", "b-joy")
        cards["og/default.png"] = ogimage.card(title="プレゼント選びを、わくわくに!", tag="イベントと相手から", bird="mascot-pair", site=site)
        for o in c["occasions"]:
            cards[f"og/occasion/{o['slug']}.png"] = ogimage.card(title=f"{o['name']}のプレゼント", tag="選び方と相手別", bird=OCC_MASCOT.get(o["slug"], "b-wink"), site=site)
        for r in c["recipients"]:
            cards[f"og/for/{r['slug']}.png"] = ogimage.card(title=f"{r['name']}へのプレゼント", tag="イベント別", bird="r-sparkle", site=site)
        for p in c["pairs"]:
            cards[f"og/gift/{ct.pair_key(p)}.png"] = ogimage.card(
                title=p["title"].split(" ")[0], tag=f"{c['rec'][p['recipient']]['name']} × {c['occ'][p['occasion']]['name']}",
                bird=OCC_MASCOT.get(p["occasion"], birds[list(c["occ"]).index(p["occasion"]) % 4]), site=site)
        OG.update(k[len("og/"):-len(".png")] for k in cards)
    pages: dict[str, str | bytes] = {"index.html": index_page(d, cfg, preview, today),
                                     "occasion/index.html": hub_page(d, cfg, preview, "occasion"),
                                     "for/index.html": hub_page(d, cfg, preview, "for")}
    for o in c["occasions"]:
        pages[f"occasion/{o['slug']}/index.html"] = occasion_page(d, cfg, preview, o)
    for r in c["recipients"]:
        pages[f"for/{r['slug']}/index.html"] = recipient_page(d, cfg, preview, r)
    for p in c["pairs"]:
        pages[f"gift/{ct.pair_key(p)}/index.html"] = pair_page(d, cfg, preview, p)
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="イベントと贈る相手から、プレゼントの選び方と、商品の例を、探しやすく整理して、贈り物選びに役立てていただくこと。",
        sources_html='商品の名前・価格・画像・レビュー・販売ページのリンクは、<a href="https://webservice.rakuten.co.jp/" rel="noopener" target="_blank">楽天ウェブサービス</a>(楽天市場)から、自動で取得しています。選び方の文章は、当サイトの運営者が作成しています。',
        update_text="商品の情報は、毎日、自動で更新します。各ページに、取得した日付を表示します。",
        disclaimer_html=("<p>商品の価格・在庫・送料・レビューは、取得した時点の情報で、販売ページと異なる場合があります。購入前に、必ず、販売ページでご確認ください。"
                         "当サイトは、商品の品質や、贈った相手が喜ぶことを、保証するものではありません。</p>"
                         "<p>当サイトの運営者は、楽天市場で、似顔絵のショップも運営しています。そのショップの商品を紹介するときは、そのことを、ページ上に明示します。</p>"
                         "<p>当サイトは、楽天グループ株式会社が運営するものではありません。</p>"),
        contact_notice="商品の購入・配送・返品などのお問い合わせは、各販売店へお願いします。当サイトでは、商品の販売を行っていません。",
        input_note="", finish=lambda s: s))
    pages.update(cards)
    pages.update(standard_files(pages, cfg, preview, d["fetched_date"]))
    pages.update(asset_pages(HERE / "assets"))
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--items", default=str(ROOT / "out" / "yorokobu_items.json"))
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    items_path = Path(a.items)
    items = json.loads(items_path.read_text(encoding="utf-8")) if items_path.exists() else None
    try:
        files = render_site(ct.load(), items, cfg, Path(a.out), release=a.release)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
