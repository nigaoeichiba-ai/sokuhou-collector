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
from sites.yorokobu.picking import score  # noqa: E402
from sokuhou import rakuten  # noqa: E402
from sokuhou.sitekit import (BuildError, amazon_disclosure, asset_pages, crumbs, esc, layout, legal_pages,  # noqa: E402
                             missing_config, standard_files, write_pages)

SOURCE_HTML = ('商品の情報は<a href="https://webservice.rakuten.co.jp/" rel="noopener" target="_blank">楽天ウェブサービス</a>を利用して取得しています。'
               ' <a href="https://developers.rakuten.com/" rel="noopener" target="_blank">Supported by Rakuten Developers</a>')
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


def amazon_url(cfg: dict, query: str) -> str:
    return f"https://www.amazon.co.jp/s?k={quote(query, safe='')}&tag={quote(cfg['amazon_tracking_id'], safe='')}"


def pr_lead(cfg: dict) -> str:
    return ('<p class="pr-lead"><span class="pr-note">PR</span>このページには、広告(楽天アフィリエイト'
            + ('・Amazonアソシエイト' if cfg.get("amazon_tracking_id") else "")
            + ')のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。</p>')


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    return layout(SITE, cfg, preview, scripts=True, head_extra=FONTS, **kw)


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

def item_card(cfg: dict, it: dict, own: bool = False, rank: int | None = None) -> str:
    if own:
        href, rel = it["url"], "noopener"
    else:
        href = rakuten.affiliate_link(cfg["rakuten_affiliate_id"], cfg.get("rakuten_tracking_id"), it["url"])
        rel = "sponsored nofollow noopener"
    bits = []
    if it["reviews"]:
        bits.append(f'<span class="stars" aria-label="レビュー平均 {it["rating"]:.2f}">★{it["rating"]:.1f}</span>'
                    f'<span>({it["reviews"]:,}件)</span>')
    if it["free_shipping"]:
        bits.append('<span class="ship">送料無料</span>')
    note = '<p class="own">当サイト運営者のショップの商品です</p>' if own else ""
    label = "ショップで見る" if own else "楽天市場で見る"
    pr = "" if own else '<span class="pr-note">PR</span>'
    badge = f'<span class="rank r{rank}">おすすめ{rank}</span>' if rank and rank <= 3 and not own else ""
    return (f'<li class="item">{badge}<a class="item-img" href="{esc(href)}" rel="{rel}" target="_blank">'
            f'<img src="{esc(it["image"])}" alt="{esc(short(it["name"], 40))}" width="300" height="300" loading="lazy"></a>'
            f'<div class="item-body"><h3><a href="{esc(href)}" rel="{rel}" target="_blank">{esc(short(it["name"]))}</a></h3>'
            f'<p class="price">{yen(it["price"])}</p><p class="meta">{"".join(bits)}</p>{note}'
            f'<a class="btn" href="{esc(href)}" rel="{rel}" target="_blank">{pr}{label}</a></div></li>')


def item_grid(cfg: dict, items: list[dict], own: bool = False, ranked: bool = False) -> str:
    return '<ul class="items">' + "".join(item_card(cfg, it, own, i + 1 if ranked else None) for i, it in enumerate(items)) + "</ul>"


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
    return (f'<p class="fresh">商品の価格・在庫・レビューは、{d["fetched_label"]}に取得した情報です。'
            "実際の内容は、販売ページでご確認ください。</p>")


def portrait_block(d: dict, cfg: dict, note: str | None) -> str:
    if not note or not d["portrait"]:
        return ""
    items = d["portrait"][:PORTRAIT_SHOWN]
    return (f'<section class="keepsake rv"><h2>思い出を形に残す、もうひとつの選択肢</h2><p>{esc(note)}</p>'
            f'{item_grid(cfg, items, own=True)}</section>')


# ---------------------------------------------------------------- pages

COLORS = ["yellow", "pink", "sky", "mint"]


def tile(href: str, kind: str, slug: str, name: str, small: str = "", wide: bool = False) -> str:
    sm = f"<small>{esc(small)}</small>" if small else ""
    return (f'<li><a class="tile{" wide" if wide else ""}" href="{href}"><span class="ic-wrap">{icon_img(kind, slug, 96)}</span>'
            f'<span><b>{esc(name)}</b>{sm}</span></a></li>')


def round_chip(href: str, kind: str, slug: str, name: str) -> str:
    return f'<li><a class="chip-ic" href="{href}"><span class="ic-wrap">{icon_img(kind, slug, 80)}</span><span>{esc(name)}</span></a></li>'


def head_band(color: str, icons: str, h1: str, lead: str, single: bool = False) -> str:
    return (f'<div class="{scallop_class(color)} pagehead-band dots"><div class="in"><div class="pagehead">'
            f'<div class="pagehead-ic{" single" if single else ""}">{icons}</div><div><h1>{h1}</h1><p class="lead">{esc(lead)}</p></div></div></div>'
            f'{party("page")}</div>')


def ic_wrap(kind: str, slug: str) -> str:
    return f'<span class="ic-wrap">{icon_img(kind, slug, 96)}</span>'


def pair_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    c = d["c"]
    occ, rec = c["occ"][p["occasion"]], c["rec"][p["recipient"]]
    key = ct.pair_key(p)
    lists = d["pairs"].get(key, {})
    tiers = [t for t in p["tiers"] if lists.get(t)]
    chips = "".join(f'<a href="#t-{t}">{esc(c["tiers"][t]["label"])}</a>' for t in tiers)
    sections = "".join(
        f'<section id="t-{t}" class="tier"><div class="tier-head"><span class="tag">予算</span><h2>{esc(c["tiers"][t]["label"])}のおすすめ</h2></div>'
        f'{item_grid(cfg, lists[t], ranked=True)}</section>' for t in tiers)
    if not sections:
        sections = '<p class="notice">いま表示できる商品が、見つかりませんでした。しばらくしてから、もう一度ご覧ください。</p>'
    avoid = occ["avoid"][:1] + rec["avoid"][:1]
    related_occ = [q for q in c["pairs"] if q["occasion"] == p["occasion"] and ct.pair_key(q) != key][:8]
    related_rec = [q for q in c["pairs"] if q["recipient"] == p["recipient"] and ct.pair_key(q) != key][:8]

    def links(items):
        return "".join(f'<li><a href="/gift/{ct.pair_key(q)}/">{esc(q["title"].split(" ")[0])}</a></li>' for q in items)

    amazon = ""
    if cfg.get("amazon_tracking_id"):
        amazon = (f'<p class="more"><a class="btn btn-sub" href="{esc(amazon_url(cfg, p["queries"][0]))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'<span class="pr-note">PR</span>Amazonでも探す</a></p>{amazon_disclosure(cfg)}')
    color = COLORS[list(c["occ"]).index(p["occasion"]) % 4]
    head = head_band(color, f'{ic_wrap("occasion", occ["slug"])}<span class="x">×</span>{ic_wrap("recipient", rec["slug"])}', esc(p["title"]), p["lead"])
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (occ["name"], f"/occasion/{occ['slug']}/"), (p["title"].split(" ")[0], None)])}</div>
{pr_lead(cfg)}
<section class="why" style="margin-top:44px"><h2><span class="scribble">喜ばれやすい理由</span></h2><ol class="panel-grid">{"".join(f"<li>{esc(x)}</li>" for x in p["reasons"])}</ol></section>
<section class="how" style="margin-top:50px"><h2><span class="scribble">選び方のポイント</span></h2><ol class="panel-grid">{"".join(f"<li>{esc(x)}</li>" for x in p["how_to_choose"])}</ol></section>
<nav class="chips" aria-label="予算" style="margin-top:46px">{chips}</nav>
{sections}
{freshness(d)}
{portrait_block(d, cfg, p.get("portrait_note"))}
<section class="avoid" style="margin-top:48px"><h2><span class="scribble">気をつけたいこと</span></h2>{ul(avoid, "warn")}</section>
<p style="margin-top:40px">{amazon}</p>
<section class="related" style="margin-top:40px"><h2><span class="scribble">あわせて読みたい</span></h2>
<div class="cols"><div><h3>{esc(occ["name"])}の、ほかの相手</h3><ul class="plain">{links(related_occ)}</ul></div>
<div><h3>{esc(rec["name"])}への、ほかのイベント</h3><ul class="plain">{links(related_rec)}</ul></div></div></section>"""
    return page(cfg, preview, path=f"/gift/{key}/", title=f"{p['title']} | {cfg['site_name']}", description=p["lead"][:110], body=body)


def occasion_page(d: dict, cfg: dict, preview: bool, o: dict) -> str:
    c = d["c"]
    pairs = [p for p in c["pairs"] if p["occasion"] == o["slug"]]
    cards = "".join(tile(f'/gift/{ct.pair_key(p)}/', "recipient", p["recipient"], f'{c["rec"][p["recipient"]]["name"]}へ', p["title"].split(" ")[0]) for p in pairs)
    lists = [t for p in pairs for t in d["pairs"].get(ct.pair_key(p), {}).values()]
    featured = top_items(lists)
    shown = (f'<section style="margin-top:50px"><h2><span class="scribble">選ばれている贈り物の例</span></h2>{item_grid(cfg, featured)}{freshness(d)}</section>' if featured else "")
    color = COLORS[list(c["occ"]).index(o["slug"]) % 4]
    head = head_band(color, ic_wrap("occasion", o["slug"]), f'{esc(o["name"])}の<wbr>プレゼント', o["blurb"], single=True)
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("イベント", "/occasion/"), (o["name"], None)])}</div>
{pr_lead(cfg)}
<section style="margin-top:40px" class="cols"><div><h2><span class="scribble">贈る時期の目安</span></h2><p>{esc(o["timing"])}</p></div>
<div><h2><span class="scribble">選ぶポイント</span></h2><ol class="panel-grid" style="grid-template-columns:1fr">{"".join(f"<li>{esc(x)}</li>" for x in o["tips"])}</ol></div></section>
<section style="margin-top:50px"><h2><span class="scribble">相手を選んで、おすすめを見る</span></h2><ul class="tiles">{cards}</ul></section>
{shown}
{portrait_block(d, cfg, o.get("portrait_note"))}
<section class="avoid" style="margin-top:48px"><h2><span class="scribble">避けたほうがよいこと</span></h2>{ul(o["avoid"], "warn")}</section>"""
    return page(cfg, preview, path=f"/occasion/{o['slug']}/", title=f"{o['name']}のプレゼント 選び方と相手別のおすすめ | {cfg['site_name']}",
                description=o["blurb"][:110], body=body)


def recipient_page(d: dict, cfg: dict, preview: bool, r: dict) -> str:
    c = d["c"]
    pairs = [p for p in c["pairs"] if p["recipient"] == r["slug"]]
    cards = "".join(tile(f'/gift/{ct.pair_key(p)}/', "occasion", p["occasion"], c["occ"][p["occasion"]]["name"], p["title"].split(" ")[0]) for p in pairs)
    lists = [t for p in pairs for t in d["pairs"].get(ct.pair_key(p), {}).values()]
    featured = top_items(lists)
    shown = (f'<section style="margin-top:50px"><h2><span class="scribble">選ばれている贈り物の例</span></h2>{item_grid(cfg, featured)}{freshness(d)}</section>' if featured else "")
    color = COLORS[list(c["rec"]).index(r["slug"]) % 4]
    head = head_band(color, ic_wrap("recipient", r["slug"]), f'{esc(r["name"])}への<wbr>プレゼント', r["blurb"], single=True)
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("相手から", "/for/"), (r["name"], None)])}</div>
{pr_lead(cfg)}
<section style="margin-top:40px" class="cols"><div><h2><span class="scribble">喜ばれやすいもの</span></h2><ol class="panel-grid" style="grid-template-columns:1fr">{"".join(f"<li>{esc(x)}</li>" for x in r["likes"])}</ol></div>
<div class="avoid"><h2><span class="scribble">避けたいもの</span></h2>{ul(r["avoid"], "warn")}</div></section>
<section style="margin-top:50px"><h2><span class="scribble">イベントを選んで、おすすめを見る</span></h2><ul class="tiles">{cards}</ul></section>
{shown}"""
    return page(cfg, preview, path=f"/for/{r['slug']}/", title=f"{r['name']}へのプレゼント イベント別のおすすめ | {cfg['site_name']}",
                description=r["blurb"][:110], body=body)


def hub_page(d: dict, cfg: dict, preview: bool, kind: str) -> str:
    c = d["c"]
    if kind == "occasion":
        rows = "".join(tile(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"], o["season"]) for o in c["occasions"])
        title, h1, lead, path, color = "イベントから探す", "イベントから、<wbr>プレゼントを探す", "贈るきっかけを選ぶと、相手ごとのおすすめが見つかります。", "/occasion/", "pink"
    else:
        rows = "".join(tile(f'/for/{r["slug"]}/', "recipient", r["slug"], r["name"]) for r in c["recipients"])
        title, h1, lead, path, color = "贈る相手から探す", "贈る相手から、<wbr>プレゼントを探す", "贈る相手を選ぶと、イベントごとのおすすめが見つかります。", "/for/", "sky"
    body = f"""{head_band(color, f'<img class="pair-mini" src="/assets/img/mascot-red.webp" alt="" width="150" height="112">', h1, lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (title, None)])}</div>
<section style="margin-top:34px"><ul class="tiles">{rows}</ul></section>"""
    return page(cfg, preview, path=path, title=f"{title} | {cfg['site_name']}", description=lead, body=body)


def season_occasions(c: dict, today: date) -> list[dict]:
    months = {today.month, today.month % 12 + 1}
    out = [o for o in c["occasions"] if o["slug"] in SEASON and months & set(SEASON[o["slug"]])]
    return out or [o for o in c["occasions"] if o["slug"] not in SEASON][:4]


def finder(c: dict) -> str:
    """Event + recipient + budget picker; without JavaScript it links to the event list, with JavaScript it jumps to the page."""
    occ = "".join(f'<option value="{o["slug"]}">{esc(o["name"])}</option>' for o in c["occasions"])
    rec = "".join(f'<option value="{r["slug"]}">{esc(r["name"])}</option>' for r in c["recipients"])
    bud = "".join(f'<option value="{t["slug"]}">{esc(t["label"])}</option>' for t in c["filters"]["tiers"])
    pairs = esc(json.dumps([ct.pair_key(p) for p in c["pairs"]]))
    return (f'<form class="finder" action="/occasion/" method="get" data-pairs="{pairs}"><p class="finder-title">贈り物をさがす</p>'
            f'<div class="finder-row"><select name="o" aria-label="イベント">{occ}</select><select name="r" aria-label="贈る相手">{rec}</select>'
            f'<select name="b" aria-label="予算"><option value="">予算</option>{bud}</select><button type="submit">さがす</button></div></form>')


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
{finder(c)}
<p class="hero-cta"><a class="btn big" href="/occasion/">イベントから探す</a><a class="btn big btn-sub" href="/for/">相手から探す</a></p></div>
<div class="hero-art">{party("hero")}<img class="pair" src="/assets/img/mascot-pair.webp" alt="赤と青のマフラーをしたシマエナガのふたり" width="1674" height="628"></div>
</div></section>
<div class="marquee" aria-hidden="true"><div class="track">{ticker}</div></div>
{pr_lead(cfg)}
<section style="margin-top:56px"><div class="sec-head"><span class="sticker">NOW</span><h2>いまが<span class="scribble">贈りどき</span></h2><p>これから迎えるイベントのプレゼントを、先取りで。</p></div>
<ul class="tiles wide">{season}</ul></section>
<section class="band sky scallop" style="margin-top:70px"><div class="in"><div class="sec-head"><h2>選び方は、かんたん<span class="scribble">3ステップ</span></h2></div>
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
<div><img src="/assets/img/mascot-pair.webp" alt="" width="1674" height="628" loading="lazy" style="width:100%;max-width:460px;display:block;margin:0 auto"></div>
<div class="bubble"><h2 style="font-size:1.3rem">このサイトについて</h2>
<p>「何を贈ればいいか分からない」というときに、<strong>イベント</strong>と<strong>贈る相手</strong>から、選び方のポイントと、商品の例を探せるサイトです。</p>
<p>商品は、楽天市場の情報を、毎日、自動で更新して表示しています。シマエナガのふたりが、あなたの「贈りたい気持ち」を、応援します。</p></div></div></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} イベントと相手から、喜ばれるプレゼントを探す",
                description="誕生日・母の日・クリスマスなど、イベントと贈る相手から、喜ばれやすいプレゼントの選び方と、おすすめの商品が見つかります。", body=body)


# ---------------------------------------------------------------- site

def prepare(c: dict, items: dict | None) -> dict:
    items = items or {"pairs": {}, "portrait": [], "fetched_at": None}
    f = items.get("fetched_at")
    label = "取得日不明"
    if f:
        t = datetime.fromisoformat(f)
        label = f"{t.year}年{t.month}月{t.day}日"
    return {"c": c, "pairs": items.get("pairs", {}), "portrait": items.get("portrait", []), "fetched_label": label,
            "fetched_date": (f or date.today().isoformat())[:10]}


def render_site(c: dict, items: dict | None, cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    if release and not (items and items.get("pairs")):
        raise BuildError("release build refused: no fetched products (run sites/yorokobu/fetch.py first)")
    preview = bool(missing)
    today = today or date.today()
    d = prepare(c, items)
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
