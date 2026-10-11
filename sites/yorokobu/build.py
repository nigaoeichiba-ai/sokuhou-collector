"""よろこぶプレゼント (yorokobu-present.com): a static gift-recommendation site.

    python sites/yorokobu/build.py [--release] [--out DIR] [--items out/yorokobu_items.json]

The editorial text is in sites/yorokobu/content/*.json; the products come from the Rakuten API (sites/yorokobu/fetch.py)
and are rebuilt every day.  A page never shows a product that was not in the fetched data.
"""
from __future__ import annotations

import argparse
import json
from html import unescape as _html_unescape
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.modules.setdefault("sites.yorokobu.build", sys.modules[__name__])   # tools.py and dataroom.py import this module lazily: they must get THIS one (its nav flags), not a second copy

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import dataroom  # noqa: E402
from sites.yorokobu import picksite  # noqa: E402
from sites.yorokobu import giftcal  # noqa: E402
from sites.yorokobu import icons  # noqa: E402
from sites.yorokobu import relevance  # noqa: E402
from sites.yorokobu import ogimage  # noqa: E402
from sites.yorokobu import numberlists as nm  # noqa: E402
from sites.yorokobu import ranking as rk  # noqa: E402
from sites.yorokobu.picking import in_tier, score, usable  # noqa: E402
from sites.yorokobu.tools import (calc_page, gacha_data, gacha_page, gacha_pool, gift_map, persona_page, quiz_page, taboo_page, tools_hub_page)  # noqa: E402
from sokuhou import rakuten  # noqa: E402
from sokuhou.sitekit import (BuildError, amazon_disclosure, asset_pages, crumbs, esc, layout, legal_pages,  # noqa: E402
                             missing_config, standard_files, write_pages)

SOURCE_HTML = ('商品の情報は楽天ウェブサービスを利用して取得しています。 '
               '<a href="https://webservice.rakuten.co.jp/" target="_blank">Supported by Rakuten Developers</a>')  # the credit HTML is prescribed: use as is
NAV = [("イベントから", "/occasion/", "/occasion/"), ("相手から", "/for/", "/for/"), ("季節の贈り物", "/#season", "/season-none/")]
# the logo mark: a gift box in the site's pink (the bird mascots were taken out on 2026-10-09: "as long as the mascot is there, the childishness stays")
LOGO_MARK = ('<svg width="36" height="36" viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect width="36" height="36" rx="9" fill="#e8503f"/>'
             '<rect x="8" y="16" width="20" height="12" rx="1.5" fill="#fff"/><rect x="6.5" y="12" width="23" height="5" rx="1.5" fill="#fff"/>'
             '<rect x="16.5" y="12" width="3" height="16" fill="#e8503f"/><path d="M18 12c-3-5-8-4-6.5-1.5 1 1.6 4 1.5 6.5 1.5zm0 0c3-5 8-4 6.5-1.5-1 1.6-4 1.5-6.5 1.5z" fill="#fff"/></svg>')
SITE = {"nav": NAV[:2] + [("気持ちから", "/theme/", "/theme/"), ("診断・ツール", "/tool/", "/tool/")], "glyph": LOGO_MARK, "assets": HERE / "assets",
        "source_html": SOURCE_HTML, "legal_extra": (("編集方針", "/policy/"),)}
# months (1-12) in which an occasion is worth showing as "いまが贈りどき"; the rest are evergreen
SEASON = {
    "mothers-day": (4, 5), "fathers-day": (5, 6), "respect-for-aged-day": (8, 9), "christmas": (11, 12),
    "valentine": (1, 2), "white-day": (2, 3), "school-entrance": (3, 4), "graduation": (2, 3), "coming-of-age": (12, 1),
    "new-job": (3, 4), "promotion": (3, 4), "retirement": (2, 3), "farewell": (3, 4), "oseibo": (11, 12),
    "ochugen": (6, 7), "year-end-gathering": (11, 12), "homecoming": (7, 8, 12),
}
NAME_LIMIT = 44
PORTRAIT_SHOWN = 2


def yen(v: int) -> str:
    return f"¥{v:,}"


KEEP_OCCASIONS: set[str] = set()   # the occasion words that belong on the page being built (set by the page functions)
DECOR = re.compile(r"[＼／\\/♪★☆◆■●▼▲♡♥]+")
EXTRA_OCCASIONS = ("卒業記念品", "卒業", "卒園", "入園祝い", "昇進祝い", "転職祝い", "成人祝い", "七五三", "古希", "喜寿", "米寿", "傘寿", "開店祝い", "開業祝い")
PROMO = re.compile(r"楽天ランキング\d*位(?:獲得)?[!！]?|楽天1位(?!ギフト)|ランキング\d+位(?:獲得)?[!！]?|ジャンル祭対象|マラソン期間中|\S*で紹介[!！]?|最強配送")


def set_keep(*words: str) -> None:
    KEEP_OCCASIONS.clear()
    KEEP_OCCASIONS.update(w for w in words if w)


def strip_occasions(name: str) -> str:
    """Product titles are stuffed with every occasion ("敬老の日 父の日 ハロウィン"); show only the page's own occasion, never an unrelated one.
    The title is kept as it is when stripping would leave too little."""
    out = PROMO.sub(" ", DECOR.sub(" ", name))
    kept = sorted(KEEP_OCCASIONS, key=len, reverse=True)
    for i, w in enumerate(kept):          # the page's own words are masked first, so a shorter word inside one ("卒業" in "卒業祝い") cannot cut it
        out = out.replace(w, f"¤{i}¤")
    for w in sorted(set(relevance.OCCASION_WORDS) | set(EXTRA_OCCASIONS), key=len, reverse=True):
        out = out.replace(w, " ")
    for i, w in enumerate(kept):
        out = out.replace(f"¤{i}¤", w)
    out = " ".join(out.split())
    return out if len(out) >= 10 else " ".join(name.split())


SPEC_ONLY = re.compile(r"[0-9０-９%％.\-+×x]+")


def short(name: str, limit: int = NAME_LIMIT) -> str:
    """A title for a card: the shop's keyword string without its repeats ("折りたたみ" then "折りたたみ傘"), cut at a word boundary, never in the middle of a word."""
    name = strip_occasions(name)
    kept: list[str] = []
    for t in name.split():
        if SPEC_ONLY.fullmatch(t) or any(t in k for k in kept):
            continue
        kept = [k for k in kept if k not in t] + [t]                  # a later, more specific word replaces the plainer one before it
    text = " ".join(kept) or name
    if len(text) <= limit:
        return text
    out = ""
    for t in text.split(" "):
        nxt = f"{out} {t}".strip()
        if len(nxt) > limit - 1:
            break
        out = nxt
    return (out or text[: limit - 1].rstrip()) + "…"


def amazon_url(cfg: dict, query: str, low: int | None = None, high: int | None = None) -> str:
    """Amazon.co.jp search results for a keyword (optionally within a price range), with the Associates tracking ID."""
    price = (f"&low-price={low}" if low else "") + (f"&high-price={high}" if high else "")
    return f"https://www.amazon.co.jp/s?k={quote(query, safe='')}{price}&tag={quote(cfg['amazon_tracking_id'], safe='')}"


def amazon_more(cfg: dict, query: str, label: str) -> str:
    """The "Amazonで探す" button (an Amazon search for `query`) with the Associates notice; empty when no tracking ID is set.  Used on the pages that list no single product."""
    if not cfg.get("amazon_tracking_id"):
        return ""
    return (f'<section style="margin-top:40px"><p class="more"><a class="btn" href="{esc(amazon_url(cfg, query))}" rel="sponsored nofollow noopener" target="_blank">'
            f'{esc(label)}</a></p></section>')


def amazon_query(name: str, limit: int = 30) -> str:
    """The words to search Amazon for a product known by its Rakuten title: the product name at the front of the title, without the shop's brackets and
    sales words (a title of 60 characters finds nothing there, because every word has to match)."""
    s = re.sub(r"[【\[\(（〔《][^】\]\)）〕》]*[】\]\)）〕》]", " ", name)
    out = ""
    for w in s.split():
        if out and len(out) + 1 + len(w) > limit:
            break
        out = f"{out} {w}".strip()
    return out or name[:limit]


def pr_lead(cfg: dict) -> str:
    return ('<p class="pr-lead"><span class="pr-note">PR</span>このページには、広告(楽天アフィリエイト'
            + ('・Amazonアソシエイト' if cfg.get("amazon_tracking_id") else "")
            + ')のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。</p>')


RANKING_ON = False   # set by render_site: the nav and the home page link to /ranking/ only when that page is built
DATA_ON = False      # the same for /data/ (the data room)
PICKS_ON = False     # and for /picks/ (the daily picks)


CRUMB_ITEM = re.compile(r'<a href="([^"]+)">([^<]+)</a>|<span>([^<]+)</span>')


def breadcrumb_ld(cfg: dict, body: str) -> str:
    """schema.org BreadcrumbList made from the page's own breadcrumb navigation (empty when the page has none)."""
    m = re.search(r'<nav class="crumbs"[^>]*>(.*?)</nav>', body, re.S)
    if not m:
        return ""
    base = cfg["site_url"].rstrip("/")
    rows = []
    for href, label, last in CRUMB_ITEM.findall(m.group(1)):
        name = _html_unescape(label or last)
        rows.append({"@type": "ListItem", "position": len(rows) + 1, "name": name, **({"item": base + href} if href else {})})
    if len(rows) < 2:
        return ""
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": rows}, ensure_ascii=False) + "</script>"


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    amazon_links = kw.pop("amazon_links", False)                     # a page whose Amazon buttons are made by its script
    if "pr-quiet" in kw.get("body", ""):
        kw["body"] += pr_foot(cfg, amazon_links or "amazon.co.jp/" in kw["body"], "rakuten.co.jp/" in kw["body"] or amazon_links)
    kw["body"] = kw.get("body", "") + icons.sprite(kw.get("body", "")) + breadcrumb_ld(cfg, kw.get("body", ""))   # the pictures the page uses (only those), the breadcrumb data
    site = {**SITE, "nav": ([("今日のおすすめ", "/picks/", "/picks/")] if PICKS_ON else []) + SITE["nav"] + ([("いま売れている", "/ranking/", "/ranking/")] if RANKING_ON else [])
                              + ([("データ室", "/data/", "/data/")] if DATA_ON else [])}
    return layout(site, cfg, preview, scripts=True, head_extra=FONTS, **kw)


SEEN: dict = {}   # every product a page showed (code -> name, price, image, links): the data file of the shared-list page
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
            f'<button type="button" class="share-btn native" hidden data-url="{esc(url)}" data-text="{esc(text)}">共有する</button>'
            f'<button type="button" class="share-btn copy" data-url="{esc(url)}">リンクをコピー</button></div>')


def icon_img(kind: str, slug: str, size: int = 64) -> str:
    return icons.icon(kind, slug, size)


def ul(items: list[str], cls: str = "") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


# ---------------------------------------------------------------- decoration (inline SVG, drawn here)

INK = "#2b1b14"
PALETTE = {"pink": "#ff4d6d", "yellow": "#ffc93c", "sky": "#38bdf8", "mint": "#2fd09b", "lilac": "#a78bfa", "orange": "#ff8a3d", "white": "#ffffff"}
MANIFEST = {
    "name": "よろこぶプレゼント", "short_name": "よろこぶ", "description": "イベントと贈る相手から、喜ばれるプレゼントを選べるサイト。大切な日のメモ・カレンダーつき。",
    "start_url": "/?from=home", "scope": "/", "display": "standalone", "lang": "ja", "background_color": "#fbf6ee", "theme_color": "#fbf6ee",
    "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
              {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    "shortcuts": [{"name": "たいせつな日メモ", "url": "/memo/"}, {"name": "イベントから探す", "url": "/occasion/"}, {"name": "相手から探す", "url": "/for/"}],
}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@500;700'
         '&family=Shippori+Mincho+B1:wght@500;700;800&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap">\n'
         '<link rel="manifest" href="/manifest.webmanifest">\n<meta name="theme-color" content="#fbf6ee">\n'
         '<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-title" content="よろこぶ">\n')
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
    """The balloons and confetti that used to be scattered around the heroes: none now (an adult gift site)."""
    return ""


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
        note += f'<p class="pick-note"><b>{it.get("note_label") or ("選んだ理由" if it.get("curated") else "数字から見ると")}</b>{esc(it["note"])}</p>'
    if not own:
        SEEN[it["code"]] = {"n": short(name, 60), "p": it["price"], "i": it["image"], "u": href,
                            "a": amazon_url(cfg, amazon_query(name)) if cfg.get("amazon_tracking_id") else ""}
    label = "ショップで見る" if own else "楽天市場で見る"
    buttons = f'<a class="btn" href="{esc(href)}" rel="{rel}" target="_blank">{label}</a>'
    if not own and cfg.get("amazon_tracking_id"):          # the same product, looked for on Amazon: one button each, the same size and colour
        buttons += (f'<a class="btn" href="{esc(amazon_url(cfg, amazon_query(name)))}" rel="sponsored nofollow noopener" target="_blank" '
                    f'aria-label="Amazonで同じ商品を探す">Amazonで探す</a>')
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
            f'<div class="item-btns">{buttons}</div></div></li>')


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


def pr_with_amazon(cfg: dict) -> str:
    """The PR label for a page whose only affiliate link is the Amazon search button (the other pages carry it already)."""
    return pr_quiet(cfg) if cfg.get("amazon_tracking_id") else ""


def pr_quiet(cfg: dict) -> str:
    """A one-line label at the top of the page (the full text sits in the footer of every page)."""
    return '<p class="pr-quiet"><span class="pr-chip" title="広告を含みます" aria-label="広告を含みます">PR</span></p>'


def pr_foot(cfg: dict, amazon: bool = False, rakuten: bool = True) -> str:
    """The full notice at the bottom of a page; it names each programme only when the page really has a link to it."""
    amazon = amazon and bool(cfg.get("amazon_tracking_id"))
    names = "・".join((["楽天アフィリエイト"] if rakuten or not amazon else []) + (["Amazonアソシエイト"] if amazon else []))
    prices = '掲載している価格・レビューは、楽天市場の情報です。Amazonの価格は、リンク先でご確認ください。' if amazon and rakuten else ""
    return ('<aside class="pr-foot"><b>広告について</b>このページには、広告(' + names + ')のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。商品の選び方は、<a href="/policy/">編集方針</a>に書いています。' + prices
            + (amazon_disclosure(cfg) if amazon else "") + '</aside>')


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
    return (f'<div class="band {color} pagehead-band"><div class="in"><div class="pagehead">'
            f'<div class="pagehead-ic{" single" if single else ""}">{icons}</div><div><h1>{h1}</h1><p class="lead">{esc(lead)}</p></div></div>'
            f'</div></div>')


def ic_wrap(kind: str, slug: str) -> str:
    return f'<span class="ic-wrap">{icon_img(kind, slug, 96)}</span>'


def bird_say(img: str, text: str, cls: str = "") -> str:
    """A short note in the page's voice (it used to be a bird's speech bubble; `img` is ignored)."""
    return f'<div class="bird-say plain {cls}"><p>{text}</p></div>'


def idea_card(cfg: dict, idea: dict, i: int, tiers: list[dict]) -> str:
    cards = "".join(item_card(cfg, it, tier=tier_of(it["price"], tiers), kind=idea["type"]) for it in idea["items"][:4])
    body = f'<ul class="items mini">{cards}</ul>' if cards else '<p class="notice">この種類の商品は、いま見つかりませんでした。下のリンクから楽天市場で探せます。</p>'
    return (f'<article class="idea" id="idea-{i}"><header><span class="type">{esc(idea["type"])}</span><h3>{esc(idea["label"])}</h3></header>'
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


def concierge(cfg: dict, d: dict, p: dict | None, heading: str = "ひとこと入れて探す") -> str:
    kws = (p or {}).get("keywords", [])[:8]
    chips = "".join(f'<li><a href="{esc(search_link(cfg, k))}" rel="sponsored nofollow noopener" target="_blank">{esc(k)}</a></li>' for k in kws)
    ctx = esc(" ".join(x for x in [(p or {}).get("recipient_keyword", "")] if x))
    return f"""<section class="concierge band-soft" id="concierge"><div class="concierge-in">
<div class="concierge-body"><h2>{heading}</h2>
<p>その人について、ひとこと教えてください(好きなもの、趣味、年齢など)。近い商品を楽天市場で探します。</p>
<form class="kw-form" data-aff="{esc(cfg['rakuten_affiliate_id'])}" data-trk="{esc(cfg.get('rakuten_tracking_id') or '')}" data-ctx="{ctx}">
<input type="search" name="q" placeholder="例: ガーデニングが好きな60代" aria-label="その人のこと、ほしいもの">
<button type="submit" class="btn">楽天市場で探す</button></form>
<ul class="kw-chips">{chips}</ul></div></div></section>"""


def listing(d: dict, cfg: dict, p: dict, heading: str) -> tuple[str, str, dict | None]:
    """The product part shared by every page that has ideas: (sommelier proposals, filterable navigator, the operator's own listing or None)."""
    c = d["c"]
    key = ct.pair_key(p)
    ideas, tiers_map, union = pair_items(d, key)
    tier_defs = [c["tiers"][t] for t in p["tiers"]]
    own = own_item(d, p["occasion"]) if p.get("portrait_note") else None

    def noted(it: dict) -> dict:           # a one-line reason is shown only where an editor wrote one (a sentence made from the numbers, repeated on every card, reads as machine-made)
        return {**it, "curated": True} if it.get("note") else it
    union = [noted(i) for i in union]
    ideas = [{**idea, "items": [noted(i) for i in idea["items"]]} for idea in ideas]
    grid_items = list(union)
    # the proposals (sommelier)
    proposals = "".join(idea_card(cfg, idea, i, c["filters"]["tiers"]) for i, idea in enumerate(ideas) if idea["items"])
    if proposals:
        proposals = (f'<section class="proposals"><div class="sec-title"><span class="tag">おすすめの贈り方</span><h2>{esc(heading)}</h2></div>'
                     f'<div class="idea-grid">{proposals}</div></section>')
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
        browse = f"""<section class="browse" id="browse"><div class="sec-title"><span class="tag">絞り込み</span><h2>条件で絞って比べる</h2></div>
{bird_say("navi-map", "予算や種類を選ぶと、ぴったりのものだけを表示します。並べかえもできます。", "navigator")}
<div class="controls">
<div class="ctl"><b>予算</b><div class="chipset" data-filter="tier"><button type="button" class="chipbtn on" data-v="">すべて</button>{tier_btns}</div></div>
{f'<div class="ctl"><b>種類</b><div class="chipset" data-filter="type"><button type="button" class="chipbtn on" data-v="">すべて</button>{type_btns}</div></div>' if type_btns else ''}
<div class="ctl row"><label>並べかえ <select data-sort><option value="rank">おすすめ順</option><option value="reviews">レビュー件数が多い順</option>
<option value="rating">評価が高い順</option><option value="price-asc">価格が安い順</option><option value="price-desc">価格が高い順</option></select></label>
<label class="chk"><input type="checkbox" data-ship> 送料無料</label><label class="chk"><input type="checkbox" data-gift> ギフト対応</label></div></div>
<p class="count" aria-live="polite"></p>
<ul class="items grid-all">{li}</ul>
<p class="empty" hidden>この条件に合う商品は見つかりませんでした。条件をゆるめるか、下の入力欄から楽天市場で探してください。</p>
{freshness(d)}</section>"""
    else:
        browse = '<section class="browse"><p class="notice">いま表示できる商品がありません。下の入力欄から、楽天市場で探してください。</p></section>'
    gm = gift_map(key, ideas, d["c"]["map_tags"], {i for i, idea in enumerate(ideas) if idea["items"]})
    return proposals + gm, browse, own


def top_picks(cfg: dict, d: dict, key: str, n: int = 4) -> str:
    """The first thing under a gift page's head: the products people look at first, before any explanation (a visitor came for the gifts)."""
    union = pair_items(d, key)[2]
    if len(union) < 3:
        return ""
    cards = "".join(item_card(cfg, it, rank=i + 1) for i, it in enumerate(union[:n]))
    return (f'<section class="top-picks"><div class="sec-title"><span class="tag">まず見たい</span><h2>評価と売れ行きから、{min(n, len(union))}点</h2></div>'
            f'<ul class="items">{cards}</ul>{freshness(d)}</section>')


def related_section(cols: list[tuple[str, str]]) -> str:
    """The 'read together' block; a column with no links, and the whole block when no column has any, is left out (never a bare heading)."""
    inner = "".join(f'<div><h3>{esc(h)}</h3><ul class="plain">{lis}</ul></div>' for h, lis in cols if lis)
    return f'<section class="related" style="margin-top:40px"><h2><span class="scribble">あわせて読みたい</span></h2><div class="cols">{inner}</div></section>' if inner else ""


# ---------------------------------------------------------------- 贈る前の早見表 (amounts, timing, noshi and cautions per occasion; from etiquette.json, with its sources)

REL_WORDS = {"boyfriend": ("恋人", "パートナー"), "girlfriend": ("恋人", "パートナー"), "husband": ("夫婦", "配偶者", "パートナー"), "wife": ("夫婦", "配偶者", "パートナー"),
             "father": ("両親", "親"), "mother": ("両親", "親"), "grandfather": ("祖父母", "祖父", "親族"), "grandmother": ("祖父母", "祖母", "親族"),
             "friend-female": ("友人", "友達"), "friend-male": ("友人", "友達"), "colleague": ("同僚", "職場"), "boss": ("上司", "目上"), "teacher": ("先生",),
             "baby": ("赤ちゃん", "子ども", "本人"), "toddler": ("子ども", "幼児"), "child": ("子ども", "小学生"), "teen": ("子ども", "中高生"), "in-laws": ("義父母", "義")}


def budget_for(e: dict, recipient: str) -> dict | None:
    """The amount row that fits a recipient (by words in its 'to'), or None."""
    for w in REL_WORDS.get(recipient, ()):
        for r in e.get("budget") or []:
            if w in r["to"]:
                return r
    return None


def quick_section(c: dict, slug: str) -> str:
    e = c.get("etiquette", {}).get(slug)
    if not e:
        return ""
    name = c["occ"][slug]["name"]
    if e.get("budget"):
        rows = "".join(f'<tr><th scope="row">{esc(r["to"])}</th><td>{esc(r["range"])}</td><td>{esc(r.get("note", ""))}</td></tr>' for r in e["budget"])
        money = f'<div class="tablewrap"><table class="quick-table"><thead><tr><th>贈る相手</th><th>金額の目安</th><th>ひとこと</th></tr></thead><tbody>{rows}</tbody></table></div>'
    else:
        money = f'<p>{esc(e["budget_note"])}</p>'
    n = e["noshi"]
    if n.get("applicable"):
        noshi = f'<p><b>表書き</b> {esc(n["omote"])}<br><b>水引</b> {esc(n["mizuhiki"])}</p>' + (f'<p>{esc(n["note"])}</p>' if n.get("note") else "")
    else:
        noshi = '<p>のしは、付けなくてもかまいません。</p>' + (f'<p>{esc(n["note"])}</p>' if n.get("note") else "")
    back = f'<div class="qcard"><h3>お返しの目安</h3><p>{esc(e["return_gift"])}</p></div>' if e.get("return_gift") else ""
    src = "、".join(f'<a href="{esc(s["url"])}" rel="nofollow noopener" target="_blank">{esc(s["name"])}</a>' + (f'({s["year"]}年)' if s.get("year") else "") for s in e["sources"])
    return (f'<section class="quick" id="quick"><h2><span class="scribble">{esc(name)}の、贈る前の早見表</span></h2>'
            f'<div class="quick-grid"><div class="qcard wide"><h3>金額の目安</h3>{money}</div>'
            f'<div class="qcard"><h3>贈る時期</h3><p>{esc(e["timing"])}</p></div>'
            f'<div class="qcard"><h3>のし(表書き・水引)</h3>{noshi}</div>'
            f'<div class="qcard"><h3>気をつけたいこと</h3>{ul(e["cautions"], "warn")}</div>{back}</div>'
            f'<p class="quick-src">金額や習慣は目安です。地域や家庭、相手との関係で変わります。参考にした出典: {src}</p></section>')


def quick_pair_note(c: dict, p: dict) -> str:
    e = c.get("etiquette", {}).get(p["occasion"])
    row = budget_for(e, p["recipient"]) if e else None
    if not row:
        return ""
    occ, rec = c["occ"][p["occasion"]], c["rec"][p["recipient"]]
    return (f'<p class="quick-pair"><b>金額の目安</b>{esc(rec["name"])}への{esc(occ["name"])}は、{esc(row["range"])}ほど。'
            f'<a href="/occasion/{occ["slug"]}/#quick">のし・時期・注意をまとめて見る</a></p>')


# ---------------------------------------------------------------- Amazonで見つけた贈り物 (hand-picked from Amazon's own best-seller lists; text and a link, no price, no picture)

def amazon_dp(cfg: dict, asin: str) -> str:
    return f"https://www.amazon.co.jp/dp/{asin}?tag={quote(cfg['amazon_tracking_id'], safe='')}"


def amazon_pick_card(cfg: dict, p: dict) -> str:
    return (f'<li class="apick"><div class="apick-body"><span class="type">{esc(p["kind"])}</span><h3>{esc(p["name"])}</h3>'
            f'<p class="apick-maker">{esc(p["maker"])}</p><p>{esc(p["why"])}</p></div>'
            f'<a class="btn" href="{esc(amazon_dp(cfg, p["asin"]))}" rel="sponsored nofollow noopener" target="_blank" aria-label="{esc(p["name"])}をAmazonで見る">Amazonで見る</a></li>')


def amazon_picks_for(c: dict, occasion: str, recipient: str | None = None, limit: int = 4) -> list[dict]:
    out = [p for p in c.get("amazon", []) if occasion in p["occasions"] and (not p.get("recipients") or recipient is None or recipient in p["recipients"])]
    return out[:limit]


def amazon_picks_section(cfg: dict, c: dict, occasion: str, recipient: str | None = None, limit: int = 4) -> str:
    if not cfg.get("amazon_tracking_id"):
        return ""
    picks = amazon_picks_for(c, occasion, recipient, limit)
    if not picks:
        return ""
    cards = "".join(amazon_pick_card(cfg, p) for p in picks)
    return (f'<section class="amazon-picks" style="margin-top:50px"><h2><span class="scribble">Amazonで見つけた贈り物</span></h2>'
            f'<p class="sec-lead">Amazonの売れ筋ランキングから、この場面に合うものを選びました。価格や在庫は変わるため、購入前にAmazonのページでご確認ください。</p>'
            f'<ul class="apicks">{cards}</ul>'
            f'<p class="more"><a class="btn btn-sub" href="/amazon/">Amazonで選ぶ贈り物を、すべて見る</a></p></section>')


def amazon_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    c = d["c"]
    kinds: dict[str, list[dict]] = {}
    for p in c["amazon"]:
        kinds.setdefault(p["kind"], []).append(p)
    blocks = "".join(f'<section style="margin-top:40px"><h2><span class="scribble">{esc(k)}</span></h2><ul class="apicks">{"".join(amazon_pick_card(cfg, p) for p in ps)}</ul></section>'
                     for k, ps in kinds.items())
    lead = "Amazonの売れ筋ランキングから、贈り物に選びやすい商品を、人の手で選びました。楽天市場の商品と並べて、見比べてください。"
    body = f"""{head_band("sky", "", "Amazonで選ぶ、<wbr>贈り物", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("Amazonで選ぶ贈り物", None)])}</div>
{pr_quiet(cfg)}
<p class="sec-lead">ここに載せているのは、Amazonの「グルメギフト」「Amazonデバイス」「ギフトカード」の売れ筋ランキングで確かめた商品です(確認日: {esc(c["amazon_checked"])})。価格や在庫は変わるため、購入前にAmazonのページでご確認ください。</p>
{blocks}
<p class="memo-note" style="margin-top:36px">イベントや相手から探すなら、<a href="/occasion/">イベントから探す</a>、<a href="/for/">相手から探す</a>へ。</p>"""
    return page(cfg, preview, path="/amazon/", title=f"Amazonで選ぶ、贈り物 | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- 共有リスト (/list/?c=code,code: what a friend sent; the data is list/items.json)

def list_page(d: dict, cfg: dict, preview: bool) -> str:
    lead = "友人や家族から届いた、贈り物の候補です。気に入ったものを教えてあげてください。"
    body = f"""{head_band("sky", "", "贈り物の候補", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("贈り物の候補", None)])}</div>
{pr_quiet(cfg)}
<section id="sharedlist" class="sharedlist" data-src="/list/items.json">
<p class="list-msg" role="status" aria-live="polite">候補を読み込んでいます。</p>
<ul class="items" id="list-items" aria-live="polite"></ul>
<noscript><p class="notice">このページは、JavaScript が使える環境でお使いください。</p></noscript>
<p class="more"><a class="btn" href="/">自分でも、プレゼントを探す</a></p>
</section>
<p class="notice">商品の価格・在庫・レビューは、取得した時点の情報です。購入前に、販売ページでご確認ください。</p>"""
    html = page(cfg, preview, path="/list/", title=f"贈り物の候補 | {cfg['site_name']}", description=lead, body=body, amazon_links=bool(cfg.get("amazon_tracking_id")))
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow">', 1)


def pair_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    set_keep(d["c"]["occ"][p["occasion"]]["name"])
    c = d["c"]
    occ, rec = c["occ"][p["occasion"]], c["rec"][p["recipient"]]
    key = ct.pair_key(p)
    proposals, browse, own = listing(d, cfg, p, f'{rec["name"]}への{occ["name"]}、こんな贈り方はどうでしょう')
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
        amazon = (f'<p class="more"><a class="btn" href="{esc(amazon_url(cfg, p["queries"][0]))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'Amazonで探す</a></p>')
    color = COLORS[list(c["occ"]).index(p["occasion"]) % 4]
    head = head_band(color, f'{ic_wrap("occasion", occ["slug"])}<span class="x">×</span>{ic_wrap("recipient", rec["slug"])}', esc(p["title"]), p["lead"],
                     mascot=OCC_MASCOT.get(p["occasion"], ("r-joy", "b-sparkle", "r-wink", "b-joy")[list(c["occ"]).index(p["occasion"]) % 4]))
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (occ["name"], f"/occasion/{occ['slug']}/"), (p["title"].split(" ")[0], None)])}</div>
{pr_quiet(cfg)}
{share_bar(cfg, f"/gift/{key}/", f"{p['title'].split(' ')[0]}の候補です。どれが合うか、意見をください。")}
{top_picks(cfg, d, key)}
<p class="memo-link"><a href="/memo/?o={p['occasion']}&amp;r={p['recipient']}">この日を忘れない(たいせつな日メモに登録)</a></p>
{quick_pair_note(c, p)}
<section class="why-how"><div class="cols"><div><h2><span class="scribble">喜ばれやすい理由</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["reasons"])}</ol></div>
<div class="how"><h2><span class="scribble">選び方のポイント</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["how_to_choose"])}</ol></div></div></section>
{proposals}
{own_note}
{browse}
{amazon_picks_section(cfg, c, p["occasion"], p["recipient"])}
{concierge(cfg, d, p)}
<section class="avoid" style="margin-top:48px"><h2><span class="scribble">気をつけたいこと</span></h2>{ul(avoid, "warn")}</section>
{guide_link(c, p["occasion"])}
<p style="margin-top:40px">{amazon}</p>
{related_section([(f"{occ['name']}の、ほかの相手", links(related_occ)), (f"{rec['name']}への、ほかのイベント", links(related_rec))])}"""
    return page(cfg, preview, path=f"/gift/{key}/", title=f"{p['title']} | {cfg['site_name']}", description=p["lead"][:110], body=body,
                og_image=og_for(f"gift/{key}"))


# ---------------------------------------------------------------- theme pages (start from a feeling or an interest, not from an occasion)

GROUP_STYLE = {"feeling": ("pink", "r-joy", "dot"), "giver": ("sky", "b-wink", "star"), "interest": ("mint", "b-sparkle", "sparkle")}
_EXTRA_STYLES = [("yellow", "r-wink", "bar"), ("lilac", "b-joy", "tri"), ("orange", "r-sparkle", "dot")]
MIN_THEME_ITEMS = 3   # a theme page with fewer products than this is not published (a bad search query must never produce an empty page)


def group_style(slug: str) -> tuple[str, str, str]:
    """A group the content factory added later gets one of the spare styles, stable by its name."""
    return GROUP_STYLE.get(slug) or _EXTRA_STYLES[sum(map(ord, slug)) % len(_EXTRA_STYLES)]


THEME_GLYPH = {"feeling": "heart", "giver": "hand-heart", "interest": "sparkle"}


def theme_mark(t: dict, size: int = 64) -> str:
    """A round mark for a theme: the Phosphor picture of its group (themes have no photo icons)."""
    return f'<span class="theme-mark" aria-hidden="true">{icons.glyph(THEME_GLYPH.get(t["group"], "gift"), 30)}</span>'


def theme_tile(t: dict) -> str:
    return (f'<li><a class="tile theme-tile" href="/theme/{t["slug"]}/">{theme_mark(t)}'
            f'<span><b>{esc(t["name"])}</b><small>{esc(t["title"])}</small></span></a></li>')


def theme_page(d: dict, cfg: dict, preview: bool, t: dict) -> str:
    set_keep()
    c = d["c"]
    color, mascot, _ = group_style(t["group"])
    group = next(g for g in c["theme_groups"] if g["slug"] == t["group"])
    proposals, browse, _ = listing(d, cfg, t, f'{t["name"]}、こんな贈り方はどうでしょう')
    same = [x for x in d["live_themes"] if x["group"] == t["group"] and x["slug"] != t["slug"]][:10]
    other = "".join(f'<li><a href="/theme/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in same)
    avoid = f'<section class="avoid" style="margin-top:48px"><h2><span class="scribble">気をつけたいこと</span></h2>{ul(t["avoid"], "warn")}</section>' if t["avoid"] else ""
    amazon = ""
    if cfg.get("amazon_tracking_id"):
        amazon = (f'<p class="more"><a class="btn" href="{esc(amazon_url(cfg, t["ideas"][0]["query"]))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'Amazonで探す</a></p>')
    head = head_band(color, theme_mark(t, 96), esc(t["title"]), t["lead"], single=True, mascot=mascot)
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("気持ち・興味から探す", "/theme/"), (t["name"], None)])}</div>
{pr_quiet(cfg)}
{top_picks(cfg, d, t["key"])}
{share_bar(cfg, f"/theme/{t['slug']}/", f"{t['title']}の候補をまとめました。どれが合うか、意見をください。")}
<section class="why-how"><div class="cols"><div><h2><span class="scribble">喜ばれやすい理由</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in t["reasons"])}</ol></div>
<div class="how"><h2><span class="scribble">選び方のポイント</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in t["how_to_choose"])}</ol></div></div></section>
{proposals}
{browse}
{concierge(cfg, d, t)}
{avoid}
<p style="margin-top:40px">{amazon}</p>
{f'<section class="related" style="margin-top:40px"><h2><span class="scribble">{esc(group["name"])}、ほかのテーマ</span></h2><ul class="plain cols2 chips">{other}</ul></section>' if other else ""}"""
    return page(cfg, preview, path=f"/theme/{t['slug']}/", title=f"{t['title']} | {cfg['site_name']}", description=t["lead"][:110], body=body,
                og_image=og_for(f"theme/{t['slug']}"))


def theme_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    c = d["c"]
    sections = ""
    for g in c["theme_groups"]:
        ts = [t for t in d["live_themes"] if t["group"] == g["slug"]]
        if ts:
            sections += (f'<section style="margin-top:44px"><h2><span class="scribble">{esc(g["name"])}</span></h2><p class="sec-lead">{esc(g["blurb"])}</p>'
                         f'<ul class="tiles">{"".join(theme_tile(t) for t in ts)}</ul></section>')
    lead = "贈りたい気持ちや、相手の好きなことから、プレゼントを探します。イベントや相手が決まっていなくても、ここから始められます。"
    body = f"""{head_band("lilac", '', "気持ち・興味から、<wbr>プレゼントを探す", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("気持ち・興味から探す", None)])}</div>
{pr_quiet(cfg)}{sections}"""
    return page(cfg, preview, path="/theme/", title=f"気持ち・興味から、プレゼントを探す | {cfg['site_name']}", description=lead, body=body)


def msg_link(c: dict, occasion: str) -> str:
    if occasion not in c["messages"]:
        return ""
    return (f'<section style="margin-top:44px"><h2><span class="scribble">添えるメッセージに、迷ったら</span></h2>'
            f'<p><a class="btn btn-sub" href="/message/{occasion}/">{esc(c["occ"][occasion]["name"])}のメッセージ例文を見る</a></p></section>')


def occasion_page(d: dict, cfg: dict, preview: bool, o: dict) -> str:
    set_keep(o["name"])
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
{quick_section(c, o["slug"])}
<section style="margin-top:40px" class="cols">{"" if c.get("etiquette", {}).get(o["slug"]) else f'<div><h2><span class="scribble">贈る時期の目安</span></h2><p>{esc(o["timing"])}</p></div>'}
<div><h2><span class="scribble">選ぶポイント</span></h2><ol class="panel-grid" style="grid-template-columns:1fr">{"".join(f"<li>{esc(x)}</li>" for x in o["tips"])}</ol></div></section>
<section style="margin-top:50px"><h2><span class="scribble">相手を選んで、おすすめを見る</span></h2><ul class="tiles">{cards}</ul></section>
{shown}
{msg_link(c, o["slug"])}<section class="avoid" style="margin-top:48px"><h2><span class="scribble">避けたほうがよいこと</span></h2>{ul(o["avoid"], "warn")}</section>
{guide_link(c, o["slug"])}
{amazon_picks_section(cfg, c, o["slug"])}
{amazon_more(cfg, o["name"] + " プレゼント", o["name"] + "のプレゼントを、Amazonで探す")}"""
    return page(cfg, preview, path=f"/occasion/{o['slug']}/", title=f"{o['name']}のプレゼント 選び方と相手別のおすすめ | {cfg['site_name']}",
                description=o["blurb"][:110], body=body, og_image=og_for(f"occasion/{o['slug']}"))


def recipient_page(d: dict, cfg: dict, preview: bool, r: dict) -> str:
    set_keep()
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
{shown}
{amazon_more(cfg, r["name"] + " プレゼント", r["name"] + "へのプレゼントを、Amazonで探す")}"""
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
    body = f"""{head_band(color, f'', h1, lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (title, None)])}</div>
<section style="margin-top:34px"><ul class="tiles">{rows}</ul></section>"""
    return page(cfg, preview, path=path, title=f"{title} | {cfg['site_name']}", description=lead, body=body)



# ---------------------------------------------------------------- 贈りどきカレンダー and たいせつな日メモ (reminders kept in the browser)

def fixed_dates(today: date) -> dict:
    """{occasion: [ISO dates of its next three years]} for the occasions whose day is the same for everybody."""
    out: dict = {}
    for y in (today.year, today.year + 1, today.year + 2):
        for g in giftcal.gift_days(y):
            out.setdefault(g["slug"], []).append(g["date"].isoformat())
    return out


def countdown(target: date, today: date) -> str:
    """「あと12日」 for a day that has not passed yet (the build runs every day, so the number is always today's); empty for a past day."""
    n = (target - today).days
    return "" if n < 0 else ("今日" if n == 0 else f"あと{n}日")


def next_fixed(slug: str, today: date) -> date | None:
    """The next date of an occasion whose day is the same for everybody (母の日, 父の日, 敬老の日, クリスマス ...), or None."""
    days = sorted(date.fromisoformat(x) for x in fixed_dates(today).get(slug, []))
    return next((x for x in days if x >= today), None)


def season_tile(o: dict, today: date) -> str:
    when = next_fixed(o["slug"], today)
    lead = f"{countdown(when, today)}({when.month}月{when.day}日)・" if when else ""
    return tile(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"], lead + o["timing"][:30] + "…", wide=True)


def memo_data(d: dict, cfg: dict, today: date) -> dict:
    c = d["c"]
    return {"fixed": fixed_dates(today), "names": {"occ": {o["slug"]: o["name"] for o in c["occasions"]}, "rec": {r["slug"]: r["name"] for r in c["recipients"]}},
            "pairs": [ct.pair_key(p) for p in c["pairs"]], "base": cfg["site_url"].rstrip("/")}


def memo_page(d: dict, cfg: dict, preview: bool, today: date) -> str:
    c = d["c"]
    occ_opts = "".join(f'<option value="{o["slug"]}">{esc(o["name"])}</option>' for o in c["occasions"])
    rec_opts = "".join(f'<option value="{r["slug"]}">{esc(r["name"])}</option>' for r in c["recipients"])
    data = memo_data(d, cfg, today)
    head = head_band("mint", f'{ic_wrap("occasion", "thanks")}', "たいせつな日メモ", "大切な人の誕生日や記念日を登録しておくと、3週間前と1週間前にお知らせします(カレンダーの通知)。", single=True, mascot="r-wink")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("たいせつな日メモ", None)])}</div>
<section id="memo-app" class="memo" data-json="{esc(json.dumps(data, ensure_ascii=False, separators=(",", ":")))}">
<div class="memo-form"><h2><span class="scribble">日を登録する</span></h2>
<form class="memo-add">
<label>だれの<select name="rec" required><option value="">贈る相手</option>{rec_opts}</select></label>
<label>名前(自由・なくてもOK)<input type="text" name="name" maxlength="12" placeholder="例: ハナコ"></label>
<label>どの日<select name="occ" required><option value="">イベント</option>{occ_opts}</select></label>
<label class="when">日にち<input type="date" name="date"></label>
<p class="memo-fixed" hidden></p>
<button type="submit" class="btn">この日を登録</button>
</form>
<p class="memo-note">入力した内容は、<b>この端末のブラウザだけに保存され、送信されません</b>。端末やブラウザを変えると、見られなくなります。</p>
</div>
<div class="memo-list-wrap"><h2><span class="scribble">登録した日</span></h2>
<ul class="memo-list" aria-live="polite"></ul>
<p class="memo-empty">まだ登録がありません。左のフォームから、大切な日を、登録してみましょう。</p>
<p class="memo-all" hidden><button type="button" class="btn btn-sub" data-all-ics>すべてカレンダーに追加(.ics)</button></p>
</div>
</section>
<section class="calendar-teaser" style="margin-top:50px"><h2><span class="scribble">みんなの贈りどき</span></h2>
<p>母の日、父の日、クリスマスなど日付が決まっている贈りどきは、<a href="/calendar/">贈りどきカレンダー</a>からまとめてカレンダーに入れられます。</p></section>"""
    return page(cfg, preview, path="/memo/", title=f"たいせつな日メモ 贈り忘れを防ぐリマインダー | {cfg['site_name']}",
                description="大切な人の誕生日や記念日を登録して、3週間前と1週間前に、カレンダーの通知で、贈り物の準備をお知らせ。登録は不要、入力した内容は端末の中だけに保存されます。",
                body=body, og_image=og_for("default"))


def calendar_page(d: dict, cfg: dict, preview: bool, today: date) -> str:
    c = d["c"]
    blocks = ""
    for y in (today.year, today.year + 1):
        rows = ""
        for g in giftcal.gift_days(y):
            if g["date"] < today:
                continue
            link = f'<a href="/occasion/{g["slug"]}/">{esc(g["label"])}</a>' if g["slug"] in c["occ"] else esc(g["label"])
            rows += (f'<tr><td>{g["date"].month}月{g["date"].day}日</td><td>{link}<small>({esc(g["when"])})</small></td>'
                     f'<td>{g["start"].month}月{g["start"].day}日</td></tr>')
        if rows:
            blocks += (f'<h3>{y}年</h3><div class="tablewrap"><table class="gift-days"><thead><tr><th>日にち</th><th>贈りどき</th><th>選びはじめ(3週間前)</th></tr></thead>'
                       f'<tbody>{rows}</tbody></table></div>')
    feed = cfg["site_url"].rstrip("/") + "/calendar/yorokobu-gift-days.ics"
    webcal = "webcal://" + feed.split("://", 1)[1]
    google = "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe="")
    head = head_band("pink", f'{ic_wrap("occasion", "oseibo")}', "贈りどきカレンダー", "母の日、父の日、クリスマスなど日付が決まっている贈りどきを、カレンダーに入れておけます。3週間前には、選びはじめの予定も入ります。", single=True, mascot="b-sparkle")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("贈りどきカレンダー", None)])}</div>
<section><h2><span class="scribble">カレンダーに入れる</span></h2>
<p class="cal-actions"><a class="btn" href="{esc(google)}" target="_blank" rel="noopener">Googleカレンダーに追加</a>
<a class="btn btn-sub" href="{esc(webcal)}">iPhone・Macに追加</a>
<a class="btn btn-sub" href="/calendar/yorokobu-gift-days.ics" download>.icsを保存</a></p>
<p class="memo-note">どれも無料で、登録は不要です。カレンダーの更新の反映には、時間がかかる場合があります。</p></section>
<section style="margin-top:36px"><h2><span class="scribble">日にちの一覧</span></h2>{blocks}
<p class="memo-note">誕生日や結婚記念日など、人によって違う日は、<a href="/memo/">たいせつな日メモ</a>に登録できます。月ごとに見るなら<a href="/month/">月ごとの贈りどき</a>へ。</p></section>"""
    return page(cfg, preview, path="/calendar/", title=f"贈りどきカレンダー {today.year}・{today.year + 1} 母の日・父の日・クリスマスの日にち | {cfg['site_name']}",
                description="母の日・父の日・敬老の日・クリスマス・お歳暮などの贈りどきの日にちと、選びはじめの目安(3週間前)の一覧。GoogleカレンダーやiPhoneに、まとめて追加できます。",
                body=body, og_image=og_for("default"))


def guide_link(c: dict, occasion: str, cls: str = "guide-link") -> str:
    g = c["guides"].get(occasion)
    if not g:
        return ""
    return (f'<aside class="{cls}">'
            f'<div><b>読みもの</b><a href="/guide/{occasion}/">{esc(g["title"])}</a></div></aside>')


def guide_page(d: dict, cfg: dict, preview: bool, slug: str) -> str:
    c = d["c"]
    g, o = c["guides"][slug], c["occ"][slug]
    secs = "".join(f'<section class="g-sec"><h2><span class="scribble">{esc(s["h"])}</span></h2><p>{esc(s["body"])}</p></section>' for s in g["sections"])
    checks = "".join(f'<li><label><input type="checkbox"> {esc(x)}</label></li>' for x in g["checklist"])
    faq = "".join(f'<details class="faq"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>' for f in g["faq"])
    pairs = [p for p in c["pairs"] if p["occasion"] == slug][:8]
    links = "".join(f'<li><a href="/gift/{ct.pair_key(p)}/">{esc(p["title"].split(" ")[0])}</a></li>' for p in pairs)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                     "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in g["faq"]]},
                    ensure_ascii=False)
    head = head_band("sky", ic_wrap("occasion", slug), esc(g["title"]), g["intro"], single=True, mascot=OCC_MASCOT.get(slug, "r-wink"))
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), (o["name"], f"/occasion/{slug}/"), ("読みもの", None)])}</div>
{pr_with_amazon(cfg)}
<article class="guide">{secs}
<section class="g-sec"><h2><span class="scribble">贈る前の、チェックリスト</span></h2><ul class="checklist">{checks}</ul></section>
<section class="g-sec"><h2><span class="scribble">よくある質問</span></h2>{faq}</section></article>
{share_bar(cfg, f"/guide/{slug}/", f"{g['title']}", "この記事を、だれかに送る")}
<section class="related" style="margin-top:44px"><h2><span class="scribble">{esc(o["name"])}の贈り物を、選ぶ</span></h2>
<ul class="plain">{links}</ul><p style="margin-top:14px"><a class="btn btn-sub" href="/occasion/{slug}/">{esc(o["name"])}のおすすめを見る</a></p></section>
{amazon_more(cfg, o["name"] + " プレゼント", o["name"] + "の贈り物を、Amazonで探す")}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/guide/{slug}/", title=f"{g['title']} | {cfg['site_name']}", description=g["intro"][:110], body=body, og_image=og_for(f"occasion/{slug}"))


# ---------------------------------------------------------------- reading articles (free-form, added by the content factory)

def article_page(d: dict, cfg: dict, preview: bool, a: dict) -> str:
    c = d["c"]
    secs = "".join(f'<section class="g-sec"><h2><span class="scribble">{esc(s["h"])}</span></h2><p>{esc(s["body"])}</p></section>' for s in a["sections"])
    checks = ""
    if a["checklist"]:
        checks = ('<section class="g-sec"><h2><span class="scribble">チェックリスト</span></h2><ul class="checklist">'
                  + "".join(f'<li><label><input type="checkbox"> {esc(x)}</label></li>' for x in a["checklist"]) + "</ul></section>")
    faq = "".join(f'<details class="faq"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>' for f in a["faq"])
    live = {t["slug"] for t in d["live_themes"]}
    rel = "".join(f'<li><a href="/theme/{s}/">{esc(c["theme"][s]["title"])}</a></li>' for s in a["themes"] if s in live)
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": a["title"], "datePublished": a["date"],
                     "inLanguage": "ja", "author": {"@type": "Organization", "name": cfg["operator_name"]}}, ensure_ascii=False)
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                         "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in a["faq"]]}, ensure_ascii=False)
    head = head_band("lilac", '', esc(a["title"]), a["lead"], single=True, mascot="r-wink")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("読みもの", "/read/"), (a["title"], None)])}</div>
<p class="meta-date">{esc(a["date"])} 公開</p>
<article class="guide">{secs}{checks}<section class="g-sec"><h2><span class="scribble">よくある質問</span></h2>{faq}</section></article>
{share_bar(cfg, f"/read/{a['slug']}/", a["title"], "この記事を、だれかに送る")}
{f'<section class="related" style="margin-top:44px"><h2><span class="scribble">贈り物を、探してみる</span></h2><ul class="plain cols2 chips">{rel}</ul></section>' if rel else ""}
<script type="application/ld+json">{ld}</script><script type="application/ld+json">{faq_ld}</script>"""
    return page(cfg, preview, path=f"/read/{a['slug']}/", title=f"{a['title']} | {cfg['site_name']}", description=a["lead"][:110], body=body, og_image=og_for(f"read/{a['slug']}"))


def read_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    arts = d["c"]["articles"]
    lead = "プレゼント選びの前に読んでおくと役立つ、読みものです。新しい記事を順次追加しています。"
    rows = "".join(f'<li><a class="tile wide read-tile" href="/read/{a["slug"]}/"><span><b>{esc(a["title"])}</b><small>{esc(a["date"])} ・ {esc(a["lead"][:60])}…</small></span></a></li>' for a in arts)
    body = f"""{head_band("lilac", '', "プレゼントの読みもの", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("読みもの", None)])}</div>
<section style="margin-top:34px"><ul class="tiles wide">{rows}</ul></section>"""
    return page(cfg, preview, path="/read/", title=f"プレゼントの読みもの | {cfg['site_name']}", description=lead, body=body)


def feed_xml(d: dict, cfg: dict) -> str:
    """Atom feed of the newest articles and themes (so readers, aggregators and search engines see that the site keeps growing)."""
    base = cfg["site_url"].rstrip("/")
    items = [(a["date"], a["title"], f"{base}/read/{a['slug']}/", a["lead"]) for a in d["c"]["articles"]]
    items += [(t.get("added") or d["fetched_date"], t["title"], f"{base}/theme/{t['slug']}/", t["lead"]) for t in d["live_themes"] if t.get("added")]
    items += picksite.feed_entries(d, cfg)
    items = sorted(items, reverse=True)[:40]
    entries = "".join(f"<entry><title>{esc(t)}</title><link href=\"{esc(u)}\"/><id>{esc(u)}</id><updated>{day}T00:00:00+09:00</updated><summary>{esc(s[:140])}</summary></entry>\n"
                      for day, t, u, s in items)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"><title>' + esc(cfg["site_name"]) + '</title>'
            f'<link href="{base}/"/><id>{base}/</id><updated>{d["fetched_date"]}T00:00:00+09:00</updated>\n' + entries + "</feed>\n")


def whats_new(d: dict, n: int = 6) -> str:
    """The home page strip with the newest pages (articles and themes the factory added), newest first; empty until there are some."""
    c = d["c"]
    rows = [(a["date"], f'/read/{a["slug"]}/', a["title"], "読みもの") for a in c["articles"]]
    rows += [(t["added"], f'/theme/{t["slug"]}/', t["title"], "テーマ") for t in d["live_themes"] if t.get("added")]
    rows = sorted(rows, reverse=True)[:n]
    if not rows:
        return ""
    lis = "".join(f'<li><a href="{u}"><span class="new-kind">{k}</span><b>{esc(t)}</b><small>{esc(day)}</small></a></li>' for day, u, t, k in rows)
    return f'<section class="whatsnew block"><div class="sec-head"><span class="eyebrow">New</span><h2>新しく追加した、ページ</h2></div><ul class="newlist">{lis}</ul><p class="more"><a class="btn btn-sub" href="/read/">読みものを、ぜんぶ見る</a></p></section>'


def season_occasions(c: dict, today: date) -> list[dict]:
    months = {today.month, today.month % 12 + 1}
    out = [o for o in c["occasions"] if o["slug"] in SEASON and months & set(SEASON[o["slug"]])]
    return out or [o for o in c["occasions"] if o["slug"] not in SEASON][:4]


def finder(d: dict) -> str:
    """A sentence with three blanks: 「[母]に、[母の日]の贈り物を、[5,000円以内]で」.  Nothing is pre-selected; the options that cannot lead to a page are
    disabled by the script (data-map: event -> recipient -> budgets that have products)."""
    c = d["c"]
    occ = "".join(f'<option value="{o["slug"]}">{esc(o["name"])}</option>' for o in c["occasions"])
    rec = "".join(f'<option value="{r["slug"]}">{esc(r["name"])}</option>' for r in c["recipients"])
    bud = "".join(f'<option value="{t["slug"]}">{esc(t["label"])}</option>' for t in c["filters"]["tiers"])
    fmap = esc(json.dumps(finder_map(d), separators=(",", ":")))
    return (f'<form class="finder" action="/occasion/" method="get" data-map="{fmap}">'
            f'<p class="finder-title">いますぐ、探す</p>'
            f'<div class="finder-row"><select name="r" aria-label="贈る相手"><option value="">だれ</option>{rec}</select><span>に、</span>'
            f'<select name="o" aria-label="イベント"><option value="">どんな日</option>{occ}</select><span>の贈り物を、</span>'
            f'<select name="b" aria-label="予算"><option value="">予算は決めない</option>{bud}</select><span>で</span>'
            f'<button type="submit">さがす</button></div>'
            f'<p class="finder-msg" role="status" hidden></p></form>')


def ranking_band(d: dict) -> str:
    """Home block for the data-driven pages: the ranking by age and sex, and the lists made by review numbers (each only when it exists)."""
    rv, nv = d.get("ranking"), d.get("numbers")
    if not (rv or nv):
        return ""
    btns = ('<a class="btn" href="/ranking/">いま売れている商品</a>' if rv else "") + ('<a class="btn btn-sub" href="/numbers/">数字で選ぶ</a>' if nv else "")
    return ('<section class="block"><div class="sec-head"><span class="eyebrow">Ranking</span><h2>数字から、選ぶ</h2>'
            '<p>楽天市場で、ジャンル別・世代別に、いま売れている商品(毎日更新)。レビュー件数や評価など、数字の条件で集めた商品の一覧も、あります。</p></div>'
            f'<p class="more">{btns}</p></section>')


def data_band(d: dict) -> str:
    """Home block for the data room: today's finding of each chart page."""
    rows = dataroom.home_teaser(d)
    if not rows:
        return ""
    cards = "".join(f'<li><a class="finding" href="{p}"><b>{esc(t)}</b><span>{esc(f)}</span></a></li>' for p, t, f in rows)
    return ('<section class="block"><div class="sec-head"><span class="eyebrow">Data</span><h2>数字で見る、贈り物</h2>'
            '<p>プレゼントの価格や予算を、商品のデータと国の統計で、グラフにしました。毎日、更新しています。</p></div>'
            f'<ul class="findings">{cards}</ul><p class="more"><a class="btn btn-sub" href="/data/">データ室を見る</a></p></section>')


def budget_block(d: dict) -> str:
    tiers = budget_tiers(d)
    if not tiers:
        return ""
    chips = "".join(f'<li><a href="/budget/{x["slug"]}/">{esc(budget_title(x))}</a></li>' for x, _ in tiers)
    return ('<section class="block"><div class="sec-head"><span class="eyebrow">Budget</span><h2>予算から、探す</h2><p>いくらまでかけるかが決まっていれば、ここから。</p></div>'
            f'<ul class="plain cols2 chips budget-chips">{chips}</ul></section>')


def daily_mix(d: dict, today: date, n: int, skip: set[str] = frozenset(), salt: int = 0) -> list[dict]:
    """n products spread over the kinds of gift (food, goods, experiences ...), different every day: the picture of the top page.
    Only products with a few good reviews and a real price are taken, so that the first thing a visitor sees is a gift, not a bargain bin."""
    import random
    pool: dict[str, dict[str, dict]] = {}
    for k in sorted(d["pairs"]):
        for idea in pair_items(d, k)[0]:
            for it in idea["items"][:3]:
                if it.get("image") and it["reviews"] >= 5 and it["rating"] >= 4.0 and it["price"] >= 1500 and it["code"] not in skip:
                    pool.setdefault(idea["type"], {})[it["code"]] = it
    types = [t for t in TYPE_ORDER if pool.get(t)]
    if not types:
        return []
    rnd = random.Random(today.toordinal() * 7 + salt)
    ranked = {t: sorted(pool[t].values(), key=lambda i: (-score(i), i["code"]))[:12] for t in types}
    order, out, seen = types[:], [], set()
    rnd.shuffle(order)
    for _ in range(n * 3):
        if len(out) >= n:
            break
        for t in order:
            if len(out) >= n:
                break
            cand = [i for i in ranked[t] if i["code"] not in seen]
            if cand:
                it = rnd.choice(cand[:6])
                seen.add(it["code"])
                out.append(it)
    return out


def mood_collage(today: date) -> str:
    """The hero picture: six mood photographs (assets/mood, made by Codex), a different set each day.  Shop photographs carry the shops' own banners
    (point rates, sale stickers) and would make the first screen look like a flyer; the products themselves are right below, in 今日のおすすめ and the rail."""
    from sites.yorokobu import dailypicks as dp
    kinds = [k for k in TYPE_ORDER if k in dp.KIND_KEY]
    off = today.toordinal() % len(kinds)
    cells = ""
    for i in range(6):
        kind = kinds[(off + i * 2) % len(kinds)] if len(kinds) > 6 else kinds[i % len(kinds)]
        variant = (today.toordinal() + i) % dp.MOOD_VARIANTS + 1
        cells += (f'<span class="cg"><img src="/assets/mood/{dp.KIND_KEY[kind]}-{variant}.webp" alt="" width="480" height="320" loading="eager">'
                  f'<span class="cg-kind">{esc(kind)}</span></span>')
    return f'<div class="collage" aria-hidden="true">{cells}</div>'


def countdown_chips(c: dict, today: date) -> str:
    days = sorted((g for y in (today.year, today.year + 1) for g in giftcal.gift_days(y) if g["date"] >= today and g["slug"] in c["occ"]), key=lambda g: g["date"])
    chips = ""
    for g in days[:3]:
        n = (g["date"] - today).days
        num = "きょう" if n == 0 else f"{n}<small>日後</small>"
        label = g["label"].replace("の時期のはじまり", "")
        chips += (f'<li><a class="cd-chip" href="/occasion/{g["slug"]}/"><span class="cd-n">{num}</span><span class="cd-t"><b>{esc(label)}</b>'
                  f'<span>{g["date"].month}月{g["date"].day}日</span></span></a></li>')
    chips += ('<li><a class="cd-chip add" href="/memo/"><span class="cd-n" aria-hidden="true">＋</span><span class="cd-t"><b>大切な日を登録</b>'
              '<span>記念日を忘れない</span></span></a></li>')
    return f'<ul class="countdowns">{chips}</ul>'


def tool_tile(href: str, glyph: str, name: str, small: str) -> str:
    return f'<li><a class="tile tool-tile" href="{href}"><span class="ic-wrap">{icons.glyph(glyph, 30)}</span><span><b>{esc(name)}</b><small>{esc(small)}</small></span></a></li>'


def home_tools(d: dict) -> str:
    c = d["c"]
    rows = []
    if d["gacha"]:
        rows.append(tool_tile("/tool/gacha/", "dice-five", "おまかせ提案", "条件を選ぶと、1点だけ提案します"))
    rows.append(tool_tile("/memo/", "calendar-heart", "たいせつな日メモ", "誕生日や記念日を、3週間前にお知らせ"))
    if c["persona"]:
        rows.append(tool_tile("/diagnosis/", "sparkle", "プレゼント診断", "相手のタイプから、合う贈り物を"))
    if c["taboo"]:
        rows.append(tool_tile("/tool/taboo/", "shield-check", "縁起・マナーチェック", "贈る前に、避けたい品を確かめる"))
    rows.append(tool_tile("/tool/calc/", "currency-jpy", "お返し・割り勘の計算", "お返しの目安と、人数での割り勘"))
    rows.append(tool_tile("/calendar/", "calendar-check", "贈りどきカレンダー", "母の日やクリスマスを、カレンダーに"))
    return (f'<section class="block"><div class="sec-head"><span class="eyebrow">Tools</span><h2>迷ったときの、道具</h2>'
            f'<p>決めきれないときは、ここから。気になった商品に♡を付けると、友人や家族に、1つのリンクで送れます。</p></div>'
            f'<ul class="tiles wide">{"".join(rows)}</ul></section>')


def index_page(d: dict, cfg: dict, preview: bool, today: date) -> str:
    set_keep()
    c = d["c"]
    rail_items = daily_mix(d, today, 10, salt=1)
    season = "".join(season_tile(o, today) for o in season_occasions(c, today)[:6])
    month_more = (f'<p class="more"><a class="btn btn-sub" href="/month/{today.month}/">{today.month}月の贈りどきを、すべて見る</a></p>'
                  if today.month in month_pages(c, today) else "")
    occ = "".join(round_chip(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"]) for o in c["occasions"])
    rec = "".join(round_chip(f'/for/{r["slug"]}/', "recipient", r["slug"], r["name"]) for r in c["recipients"])
    popular = [p for p in c["pairs"] if p["occasion"] in ("birthday", "year-end-gathering", "mothers-day", "christmas")][:12]
    pop = "".join(f'<li><a href="/gift/{ct.pair_key(p)}/">{esc(p["title"].split(" ")[0])}</a></li>' for p in popular)
    theme_band = ""
    if d["live_themes"]:
        picks = [x for g in c["theme_groups"] for x in [t for t in d["live_themes"] if t["group"] == g["slug"]][:4]]
        theme_band = (f'<section class="block"><div class="sec-head"><span class="eyebrow">Themes</span><h2>気持ち・興味から、探す</h2>'
                      f'<p>イベントが決まっていなくても大丈夫。贈りたい気持ちや、相手の好きなことから。</p></div>'
                      f'<ul class="tiles">{"".join(theme_tile(x) for x in picks)}</ul><p class="more"><a class="btn btn-sub" href="/theme/">テーマを、すべて見る</a></p></section>')
    rail = ""
    if rail_items:
        cards = "".join(item_card(cfg, it, rank=None) for it in rail_items)
        rail = (f'<section class="block"><div class="sec-head"><div><span class="eyebrow">Today</span><h2>今日の、贈り物の候補</h2>'
                f'<p>毎日、入れ替わります。ジャンルがかたよらないように、評価の高い商品を選んでいます。</p></div></div>'
                f'<ul class="rail">{cards}</ul>{freshness(d)}</section>')
    hero_cls = "hero"
    body = f"""<section class="{hero_cls}">
<div class="hero-text">
<h1><span class="nb">よろこばれるプレゼント、</span><br><span class="nb"><em>見つかります。</em></span></h1>
<p class="lead">イベントと贈る相手から、喜ばれやすい選び方と、おすすめの商品が見つかります。</p>
{finder(d)}
</div>
{mood_collage(today)}
</section>
{pr_quiet(cfg)}
{picksite.home_block(d, cfg)}
<section id="memo-strip" class="memo-strip block" data-json="{esc(json.dumps(memo_data(d, cfg, today), ensure_ascii=False, separators=(",", ":")))}"><div class="memo-strip-in">
<div><span class="eyebrow">Countdown</span><h2>贈りどきまで、あと何日?</h2>{countdown_chips(c, today)}<p class="more"><a class="btn btn-sub" href="/calendar/">贈りどきカレンダー</a></p></div></div></section>
<section class="block"><div class="sec-head"><span class="eyebrow">Now</span><h2>いま、準備したいイベント</h2><p>これから迎えるイベントのプレゼントを、先取りで。</p></div>
<ul class="tiles wide">{season}</ul>{month_more}</section>
<section class="block"><div class="sec-head"><span class="eyebrow">For whom</span><h2>だれに、贈りますか?</h2></div>
<ul class="chip-grid round">{rec}</ul></section>
{budget_block(d)}
<section class="block"><div class="sec-head"><span class="eyebrow">Occasions</span><h2>どんな日に、贈りますか?</h2></div>
<ul class="chip-grid">{occ}</ul></section>
{rail}
{home_tools(d)}
<section class="block"><div class="sec-head"><span class="eyebrow">Popular</span><h2>まず見たい、おすすめページ</h2></div>
<ul class="plain cols2 chips">{pop}</ul></section>
{whats_new(d)}
{data_band(d)}
{ranking_band(d)}
{message_band(d)}
{theme_band}
<section class="about-home"><h2>このサイトについて</h2>
<p>「何を贈ればいいか分からない」というときに、<strong>イベント</strong>と<strong>贈る相手</strong>から、選び方のポイントと商品の例を探せるサイトです。</p>
<p>商品の価格・在庫は、毎日、楽天市場の情報にあわせて更新しています。選び方や文章の作り方は、<a href="/policy/">編集方針</a>に書いています。</p></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} イベントと相手から、喜ばれるプレゼントを探す",
                description="誕生日・母の日・クリスマスなど、イベントと贈る相手から、喜ばれやすいプレゼントの選び方と、おすすめの商品が見つかります。", body=body,
                og_image=og_for("default"))


# ---------------------------------------------------------------- いま売れている (Rakuten sales ranking by age and sex; data from ranking.py, no network here)

def ranked_card(cfg: dict, it: dict, note: str, label: str) -> str:
    return item_card(cfg, {**it, "note": note, "note_label": label, "curated": False}, rank=it["rank"] if it["rank"] <= 3 else None)


def ranking_grid(cfg: dict, rows: list[tuple[dict, str, str]]) -> str:
    return '<ul class="items">' + "".join(ranked_card(cfg, it, note, label) for it, note, label in rows) + "</ul>"


def ranking_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    rv = d["ranking"]
    day = rk.date_label(rv["date"])
    def tiles_of(kind: str) -> str:
        out = ""
        for slug in rv["order"]:
            sg = rv["segments"][slug]
            if sg["kind"] != kind:
                continue
            first = sg["items"][0]
            out += (f'<li><a class="tile wide" href="/ranking/{slug}/"><span><b>{esc(sg["label"])}</b>'
                    f'<small>{first["rank"]}位: {esc(short(first.get("display") or first["name"], 24))}</small></span></a></li>')
        return out
    genre_tiles, people_tiles = tiles_of("genre"), tiles_of("people")
    genre_block = (f'<section style="margin-top:34px"><h2><span class="scribble">ジャンルから選ぶ</span></h2>'
                   f'<p class="sec-lead">贈り物の定番ジャンルごとに、いま売れている商品です。</p><ul class="tiles wide">{genre_tiles}</ul></section>') if genre_tiles else ""
    people_block = (f'<section style="margin-top:34px"><h2><span class="scribble">世代と性別から選ぶ</span></h2>'
                    f'<p class="sec-lead">その世代・性別でよく売れている商品です(日用品や贈り物に向かない商品は除いています)。</p><ul class="tiles wide">{people_tiles}</ul></section>') if people_tiles else ""
    rise = ""
    if rv["risers"]:
        rows = [(it, f'{lab}で、前日より{g}つ順位アップ', "急上昇") for lab, slug, it, g in rv["risers"]]
        rise = (f'<section style="margin-top:44px"><h2><span class="scribble">きのうより、順位を上げた商品</span></h2>'
                f'<p class="sec-lead">年代・性別ごとのランキングで、前日より順位が上がった商品のなかから、上がり幅の大きい順に並べています。</p>'
                f'{ranking_grid(cfg, rows)}</section>')
    else:
        rise = ('<section style="margin-top:44px"><h2><span class="scribble">きのうより、順位を上げた商品</span></h2>'
                '<p class="sec-lead">順位の変化は、毎日のランキングが2日分たまってから表示します。</p></section>')
    lead = "楽天市場のランキングをもとに、ジャンル別・年代別・性別ごとに、いま売れている商品を紹介します。前日より順位が上がった商品や、はじめてランクインした商品も、毎日更新します。"
    body = f"""{head_band("yellow", '', "いま売れている、<wbr>ランキング", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("いま売れている", None)])}</div>
{pr_quiet(cfg)}
<p class="sec-lead">{esc(day)}のランキングです。ランキングは、楽天市場の売れ行きにもとづく数字で、贈り物として選ばれた順位ではありません。
トイレットペーパーや飲料など、ふだんの買い物の商品と、このサイトの基準に合わない商品は、除いています。</p>
{genre_block}
{people_block}
{rise}
{freshness({**d, "fetched_label": day})}"""
    return page(cfg, preview, path="/ranking/", title=f"いま売れている、世代別ランキング | {cfg['site_name']}", description=lead, body=body)


def ranking_page(d: dict, cfg: dict, preview: bool, slug: str) -> str:
    rv = d["ranking"]
    sg = rv["segments"][slug]
    part = "に" if sg["kind"] == "people" else "の"       # 「20代女性に、いま売れている商品」 / 「スイーツ・お菓子の、いま売れている商品」
    day = rk.date_label(sg["date"])
    f = sg["facts"]
    facts = ""
    if f:
        facts = (f'<p class="sec-lead">{esc(day)}のランキング上位から、条件に合う{f["n"]}点の、価格の中央値は{yen(f["median"])}です。'
                 f'3,000円以下が{f["le3000"]}点、10,000円以上が{f["ge10000"]}点、いちばん安いのは{yen(f["min"])}、いちばん高いのは{yen(f["max"])}です。</p>')
    blocks = ""
    if sg["risers"]:
        blocks += (f'<section style="margin-top:40px"><h2><span class="scribble">きのうより、順位を上げた</span></h2>'
                   f'{ranking_grid(cfg, [(it, f"前日より{g}つ順位アップ(現在{it["rank"]}位)", "急上昇") for it, g in sg["risers"]])}</section>')
    if sg["entered"]:
        blocks += (f'<section style="margin-top:40px"><h2><span class="scribble">はじめてのランクイン</span></h2>'
                   f'<p class="sec-lead">前日のランキング上位{sg["depth"]}位にある、贈り物向きの商品には入っていなかった商品です。</p>'
                   f'{ranking_grid(cfg, [(it, f"前日は圏外。現在{it["rank"]}位", "新顔") for it in sg["entered"]])}</section>')
    if sg["stay"]:
        blocks += (f'<section style="margin-top:40px"><h2><span class="scribble">ランクインし続けている</span></h2>'
                   f'<p class="sec-lead">毎日のランキング上位{sg["depth"]}位に、3日以上続けて入っている商品です(記録は{sg["days"]}日分)。</p>'
                   f'{ranking_grid(cfg, [(it, f"{n}日連続でランクイン(現在{it["rank"]}位)", "ロングヒット") for it, n in sg["stay"]])}</section>')
    others = "".join(f'<li><a href="/ranking/{o}/">{esc(rv["segments"][o]["label"])}</a></li>' for o in rv["order"] if o != slug)
    body = f"""{head_band("yellow", '', f"{esc(sg['label'])}{part}、<wbr>いま売れている商品", f"楽天市場で、{sg['label']}{'に' if part == 'に' else 'で'}売れている商品の上位です({day}のランキング)。", single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("いま売れている", "/ranking/"), (sg["label"], None)])}</div>
{pr_quiet(cfg)}
{facts}
{blocks}
<section style="margin-top:40px"><h2><span class="scribble">ランキング(上位)</span></h2>
<p class="sec-lead">順位は、楽天市場のランキングの順位です(上位{sg["depth"]}位のなかから、商品名で贈り物向きと分かるものだけを、載せています。ふだんの買い物の商品などは、除いているため、順位に欠けがあります)。</p>
{ranking_grid(cfg, [(it, f"現在{it['rank']}位", "順位") for it in sg["items"]])}</section>
{amazon_more(cfg, sg["label"] + (" プレゼント" if sg["kind"] == "people" else " ギフト"), sg["label"] + ("への" if sg["kind"] == "people" else "の") + "贈り物を、Amazonで探す")}
{f'<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかの世代・性別</span></h2><ul class="plain cols2 chips">{others}</ul></section>' if others else ""}
{freshness({**d, "fetched_label": day})}"""
    return page(cfg, preview, path=f"/ranking/{slug}/", title=f"{sg['label']}{part}、いま売れている商品 | {cfg['site_name']}",
                description=f"楽天市場で{sg['label']}{'に' if part == 'に' else 'で'}売れている商品の上位。きのうより順位を上げた商品、はじめてランクインした商品も。{day}のランキングです。", body=body)




# ---------------------------------------------------------------- メッセージ例文集 (ready-to-copy card messages per occasion; from messages.json)

STYLE_LABEL = {"丁寧": "ていねい", "やわらかい": "やわらかく", "ひとこと": "ひとこと"}


def message_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    c = d["c"]
    tiles = "".join(tile(f'/message/{o["slug"]}/', "occasion", o["slug"], f'{o["name"]}のメッセージ', f'{len(c["messages"][o["slug"]]["sets"])}人分の例文')
                    for o in c["occasions"] if o["slug"] in c["messages"])
    lead = "プレゼントに添える一言や、カードに書くメッセージを、イベントと贈る相手ごとに集めました。気に入った文を、そのままコピーして使えます。"
    body = f"""{head_band("pink", '', "プレゼントに添える、<wbr>メッセージ例文集", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("メッセージ例文集", None)])}</div>
<section style="margin-top:34px"><h2><span class="scribble">イベントをえらぶ</span></h2><ul class="tiles">{tiles}</ul></section>"""
    return page(cfg, preview, path="/message/", title=f"プレゼントに添える、メッセージ例文集 | {cfg['site_name']}", description=lead, body=body)


def message_page(d: dict, cfg: dict, preview: bool, slug: str) -> str:
    c = d["c"]
    o, m = c["occ"][slug], c["messages"][slug]
    sets = ""
    for s in m["sets"]:
        lines = "".join(f'<li><p class="msg-text">{esc(ln)}</p><button type="button" class="copy" data-copy hidden>コピー</button></li>' for ln in s["lines"])
        sets += (f'<section style="margin-top:34px"><h2><span class="scribble">{esc(s["to"])}</span> <span class="tagx">{esc(STYLE_LABEL.get(s["style"], s["style"]))}</span></h2>'
                 f'<ul class="msg-list">{lines}</ul></section>')
    closing = "".join(f'<li><p class="msg-text">{esc(x)}</p><button type="button" class="copy" data-copy hidden>コピー</button></li>' for x in m["closing"])
    others = "".join(f'<li><a href="/message/{x["slug"]}/">{esc(x["name"])}のメッセージ</a></li>' for x in c["occasions"] if x["slug"] in c["messages"] and x["slug"] != slug)
    related = (f'<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかのイベントのメッセージ</span></h2>'
               f'<ul class="plain cols2 chips">{others}</ul></section>') if others else ""
    lead = m["intro"]
    body = f"""{head_band("pink", ic_wrap("occasion", slug), f'{esc(o["name"])}の<wbr>メッセージ例文集', lead, single=True, mascot=OCC_MASCOT.get(slug, "b-wink"))}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("メッセージ例文集", "/message/"), (o["name"], None)])}</div>
{pr_with_amazon(cfg)}
<p class="sec-lead">気に入った文の「コピー」を押すと、そのまま貼りつけられます。相手との関係に合わせて、言葉を少し変えると、さらに気持ちが伝わります。</p>
{sets}
<section style="margin-top:44px"><h2><span class="scribble">最後に添える、ひとこと</span></h2><ul class="msg-list">{closing}</ul></section>
<section class="avoid" style="margin-top:44px"><h2><span class="scribble">言葉を選ぶときの、気をつけたいこと</span></h2>{ul(m["manners"], "warn")}</section>
<section style="margin-top:44px"><h2><span class="scribble">贈るものを、探す</span></h2>
<p><a class="btn" href="/occasion/{slug}/">{esc(o["name"])}のプレゼントを探す</a></p>{guide_link(c, slug)}</section>
{amazon_more(cfg, o["name"] + " プレゼント", o["name"] + "に贈るものを、Amazonで探す")}
{related}"""
    return page(cfg, preview, path=f"/message/{slug}/", title=f"{o['name']}のメッセージ例文集 | {cfg['site_name']}", description=lead[:110], body=body,
                og_image=og_for(f"occasion/{slug}"))


def message_band(d: dict) -> str:
    if not d["c"]["messages"]:
        return ""
    return ('<section class="block"><div class="sec-head"><span class="eyebrow">Messages</span><h2>添える言葉に、迷ったら</h2>'
            '<p>誕生日、母の日、クリスマスなど、プレゼントに添えるメッセージの例文を、相手ごとにまとめました。コピーしてそのまま使えます。</p></div>'
            '<p class="more"><a class="btn btn-sub" href="/message/">メッセージ例文集を見る</a></p></section>')


# ---------------------------------------------------------------- 数字で選ぶ (lists made by rules on review count, rating and price)

def numbers_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    nv = d["numbers"]
    tiles = "".join(f'<li><a class="tile wide" href="/numbers/{L["slug"]}/"><span><b>{esc(L["title"])}</b><small>{esc(L["short"])}({L["total"]}点)</small></span></a></li>'
                    for L in nv["lists"])
    lead = "レビューの件数・評価・価格などの数字を条件に、プレゼントの候補を並べました。迷ったときの目安にしてください。"
    to_ranking = '<p class="more"><a class="btn btn-sub" href="/ranking/">いま売れている商品も見る</a></p>' if d.get("ranking") else ""
    body = f"""{head_band("sky", '', "数字で選ぶ、<wbr>プレゼント", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("数字で選ぶ", None)])}</div>
{pr_quiet(cfg)}
<p class="sec-lead">このサイトで紹介している商品{nv["pool"]}点のなかから、数字の条件に合うものを集めています。レビューは購入した人の感想です。商品の品質や、贈った相手が喜ぶことを保証するものではありません。</p>
<section style="margin-top:34px"><h2><span class="scribble">条件をえらぶ</span></h2><ul class="tiles wide">{tiles}</ul></section>
{to_ranking}
{freshness(d)}"""
    return page(cfg, preview, path="/numbers/", title=f"数字で選ぶ、プレゼント | {cfg['site_name']}", description=lead, body=body)


def numbers_page(d: dict, cfg: dict, preview: bool, slug: str) -> str:
    nv = d["numbers"]
    L = next(x for x in nv["lists"] if x["slug"] == slug)
    others = "".join(f'<li><a href="/numbers/{o["slug"]}/">{esc(o["title"])}</a></li>' for o in nv["lists"] if o["slug"] != slug)
    shown = len(L["items"])
    more = f"(条件に合う{L['total']}点のうち、上位{shown}点)" if L["total"] > shown else f"({L['total']}点)"
    set_keep()
    body = f"""{head_band("sky", '', esc(L["title"]), L["says"], single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("数字で選ぶ", "/numbers/"), (L["title"], None)])}</div>
{pr_quiet(cfg)}
<p class="sec-lead">条件に合う商品の、いまの数字です{more}。レビューは購入した人の感想で、品質を保証するものではありません。</p>
<section style="margin-top:30px">{item_grid(cfg, L["items"])}</section>
{amazon_more(cfg, "プレゼント ギフト 人気", "プレゼントを、Amazonで探す")}
{f'<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかの条件</span></h2><ul class="plain cols2 chips">{others}</ul></section>' if others else ""}
{freshness(d)}"""
    return page(cfg, preview, path=f"/numbers/{slug}/", title=f"{L['title']} | {cfg['site_name']}", description=L["says"][:110], body=body)


# ---------------------------------------------------------------- 今月の贈りどき (one page per calendar month, from SEASON and giftcal)

def month_year(m: int, today: date) -> int:
    """The year in which month m is next (or currently) coming up."""
    return today.year if m >= today.month else today.year + 1


def month_content(c: dict, m: int, today: date) -> dict:
    y = month_year(m, today)
    days = [g for g in giftcal.gift_days(y) if g["date"].month == m]
    starts = [g for g in giftcal.gift_days(y) if g["start"].month == m and g["date"].month != m]
    occ = [o for o in c["occasions"] if m in SEASON.get(o["slug"], ())]
    return {"m": m, "y": y, "days": days, "starts": starts, "occ": occ}


def month_pages(c: dict, today: date) -> list[int]:
    return [m for m in range(1, 13) if (lambda x: x["days"] or x["starts"] or x["occ"])(month_content(c, m, today))]


def month_page(d: dict, cfg: dict, preview: bool, m: int, today: date, months: list[int]) -> str:
    set_keep()
    c = d["c"]
    mc = month_content(c, m, today)
    tiles = "".join(tile(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"], o["timing"][:30] + "…", wide=True) for o in mc["occ"])
    def left(g: dict) -> str:
        t = countdown(g["date"], today)
        return f"<small>({t})</small>" if t else ""
    rows = "".join(f'<tr><td>{g["date"].month}月{g["date"].day}日{left(g)}</td><td>{esc(g["label"])}<small>({esc(g["when"])})</small></td>'
                   f'<td>{g["start"].month}月{g["start"].day}日</td></tr>' for g in mc["days"])
    srows = "".join(f'<tr><td>{g["date"].month}月{g["date"].day}日</td><td>{esc(g["label"])}<small>({esc(g["when"])})</small></td>'
                    f'<td>{g["start"].month}月{g["start"].day}日</td></tr>' for g in mc["starts"])
    head_row = "<thead><tr><th>日にち</th><th>贈りどき</th><th>選びはじめ(3週間前)</th></tr></thead>"
    sec = ""
    if tiles:
        sec += f'<section style="margin-top:40px"><h2><span class="scribble">{m}月に、準備したいイベント</span></h2><ul class="tiles wide">{tiles}</ul></section>'
    if rows:
        sec += f'<section style="margin-top:40px"><h2><span class="scribble">{m}月にある、日にちの決まった贈りどき</span></h2><div class="tablewrap"><table class="gift-days">{head_row}<tbody>{rows}</tbody></table></div></section>'
    if srows:
        sec += f'<section style="margin-top:40px"><h2><span class="scribble">{m}月に、選びはじめたい贈りどき</span></h2><p>翌月以降の贈りどきのうち、選びはじめの目安(3週間前)が{m}月に入るものです。</p><div class="tablewrap"><table class="gift-days">{head_row}<tbody>{srows}</tbody></table></div></section>'
    i = months.index(m)
    prev_m, next_m = months[i - 1], months[(i + 1) % len(months)]
    nav = (f'<p class="more"><a class="btn btn-sub" href="/month/{prev_m}/">{prev_m}月</a> <a class="btn btn-sub" href="/month/">月ごとの一覧</a> '
           f'<a class="btn btn-sub" href="/month/{next_m}/">{next_m}月</a></p>')
    lead = f"{m}月に準備したいプレゼントのイベントと、日付が決まっている贈りどき、選びはじめの目安をまとめています。"
    head = head_band(COLORS[m % 4], ic_wrap("occasion", mc["occ"][0]["slug"]) if mc["occ"] else "", f"{m}月の<wbr>贈りどき", lead, single=True, mascot="b-sparkle")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("月ごとの贈りどき", "/month/"), (f"{m}月", None)])}</div>
{pr_with_amazon(cfg)}
{sec}
{amazon_more(cfg, (mc["occ"][0]["name"] + " プレゼント") if mc["occ"] else "プレゼント ギフト", ((mc["occ"][0]["name"] + "の") if mc["occ"] else "") + "プレゼントを、Amazonで探す")}
<p class="memo-note" style="margin-top:36px">日付は{mc["y"]}年のものです(毎年、新しい年の日付に更新します)。誕生日や記念日など、人によって違う日は、<a href="/memo/">たいせつな日メモ</a>に登録できます。カレンダーに入れるなら<a href="/calendar/">贈りどきカレンダー</a>へ。</p>
{nav}"""
    return page(cfg, preview, path=f"/month/{m}/", title=f"{m}月の贈りどき 準備したいプレゼントのイベント | {cfg['site_name']}", description=lead, body=body,
                og_image=og_for("default"))


def month_hub_page(d: dict, cfg: dict, preview: bool, today: date, months: list[int]) -> str:
    c = d["c"]
    tiles = ""
    for m in months:
        mc = month_content(c, m, today)
        names = "・".join([o["name"] for o in mc["occ"]][:3] or [g["label"] for g in mc["days"]][:3])
        tiles += (f'<li><a class="tile wide" href="/month/{m}/"><span><b>{m}月{"(いま)" if m == today.month else ""}</b>'
                  f'<small>{esc(names)}</small></span></a></li>')
    now_link = (f'<p><a href="/month/{today.month}/">{today.month}月の贈りどきを見る</a></p>'
                if today.month in months else "")   # a month with nothing to show has no page
    lead = "1年を月ごとに見て、いつ、何のプレゼントを準備すればよいかが分かります。"
    head = head_band("yellow", "", "月ごとの<wbr>贈りどき", lead, single=True, mascot="b-wink")
    body = f"""{head}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("月ごとの贈りどき", None)])}</div>
<section style="margin-top:40px"><h2><span class="scribble">いまは{today.month}月</span></h2>{now_link}
<ul class="tiles wide">{tiles}</ul></section>"""
    return page(cfg, preview, path="/month/", title=f"月ごとの贈りどき 1年のプレゼントの準備カレンダー | {cfg['site_name']}", description=lead, body=body,
                og_image=og_for("default"))


# ---------------------------------------------------------------- 予算から探す (/budget/<tier>/: the products of one price range, from every page of the site)

MIN_BUDGET_ITEMS = 12


def budget_pool(d: dict, tier: dict) -> list[tuple[dict, str]]:
    """The best products of one price range with their kind of gift, spread over the kinds (round by round), at most three from one shop."""
    kinds: dict[str, dict[str, dict]] = {}
    for key in sorted(d["pairs"]):
        for idea in pair_items(d, key)[0]:
            for it in idea["items"]:
                if in_tier(it["price"], tier) and it["code"] not in kinds.get(idea["type"], {}):
                    kinds.setdefault(idea["type"], {})[it["code"]] = it
    order = [k for k in TYPE_ORDER if k in kinds]
    ranked = {k: sorted(kinds[k].values(), key=lambda i: (-score(i), i["code"])) for k in order}
    out, seen, shops = [], set(), {}
    for rnd in range(12):
        for k in order:
            if rnd >= len(ranked[k]):
                continue
            it = ranked[k][rnd]
            if it["code"] in seen or shops.get(it["shop_code"], 0) >= 3:
                continue
            seen.add(it["code"])
            shops[it["shop_code"]] = shops.get(it["shop_code"], 0) + 1
            out.append((it, k))
            if len(out) >= 24:
                return out
    return out


def budget_tiers(d: dict) -> list[tuple[dict, list[tuple[dict, str]]]]:
    """(tier, products) for each price range that has enough products to be worth a page."""
    out = []
    for tier in d["c"]["filters"]["tiers"]:
        pool = budget_pool(d, tier)
        if len(pool) >= MIN_BUDGET_ITEMS:
            out.append((tier, pool))
    return out


def budget_title(tier: dict) -> str:
    return tier["label"]


def budget_page(d: dict, cfg: dict, preview: bool, tier: dict, pool: list, tiers: list) -> str:
    set_keep()
    c = d["c"]
    name = budget_title(tier)
    counts: dict[str, int] = {}
    for _, k in pool:
        counts[k] = counts.get(k, 0) + 1
    top = sorted(counts, key=lambda k: -counts[k])[:3]
    prices = sorted(it["price"] for it, _ in pool)
    note = (f"当サイトで取り上げている商品のうち、{tier['label']}の価格帯から、種類がかたよらないように{len(pool)}点を選びました。"
            f"いちばん多い種類は、{ ' と '.join(top[:2]) }です。価格の中央値は{yen(prices[len(prices) // 2])}です。")
    cards = "".join(item_card(cfg, it, kind=k) for it, k in pool)
    others = "".join(f'<li><a href="/budget/{x["slug"]}/">{esc(budget_title(x))}</a></li>' for x, _ in tiers if x["slug"] != tier["slug"])
    occ = "".join(round_chip(f'/occasion/{o["slug"]}/', "occasion", o["slug"], o["name"]) for o in c["occasions"][:12])
    amazon = ""
    if cfg.get("amazon_tracking_id"):
        amazon = (f'<p class="more"><a class="btn" href="{esc(amazon_url(cfg, "プレゼント ギフト", tier.get("min") or None, tier.get("max")))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'{esc(name)}の贈り物を、Amazonで探す</a></p>')
    lead = f"{name}で贈れる、プレゼントの候補です。贈る相手やイベントが決まっていなくても、この予算から選べます。"
    body = f"""{head_band("yellow", "", f"{esc(name)}で贈る、<wbr>プレゼント", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("予算から探す", "/budget/"), (name, None)])}</div>
{pr_quiet(cfg)}
<p class="sec-lead" style="margin-top:18px">{esc(note)}</p>
<section style="margin-top:26px"><ul class="items">{cards}</ul>{freshness(d)}</section>
{amazon}
<section class="block"><div class="sec-head"><h2>ほかの予算から探す</h2></div><ul class="plain cols2 chips">{others}</ul></section>
<section class="block"><div class="sec-head"><h2>イベントから、{esc(tier['label'])}で探す</h2><p>イベントのページでは、予算で絞り込めます。</p></div><ul class="chip-grid">{occ}</ul></section>"""
    return page(cfg, preview, path=f"/budget/{tier['slug']}/", title=f"{name}で贈る、プレゼントのおすすめ | {cfg['site_name']}", description=lead, body=body)


def budget_hub_page(d: dict, cfg: dict, preview: bool, tiers: list) -> str:
    rows = "".join(f'<li><a class="tile wide" href="/budget/{x["slug"]}/"><span><b>{esc(budget_title(x))}</b><small>{len(pool)}点から選べます</small></span></a></li>' for x, pool in tiers)
    lead = "予算から、プレゼントを探します。贈る相手やイベントが決まっていなくても、いくらまでかけるかが決まっていれば、ここから始められます。"
    body = f"""{head_band("sky", "", "予算から、<wbr>プレゼントを探す", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("予算から探す", None)])}</div>
<section style="margin-top:34px"><ul class="tiles wide">{rows}</ul></section>"""
    return page(cfg, preview, path="/budget/", title=f"予算から、プレゼントを探す | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- 編集方針 (how products are chosen, how the text is made, how numbers are used: written down, and true)

def policy_page(d: dict, cfg: dict, preview: bool) -> str:
    op = esc(cfg.get("operator_name") or "運営者")
    lead = "よろこぶプレゼントが、どのように商品を選び、文章を書き、数字を扱っているかを、まとめています。"
    secs = [
        ("運営", f'<p>運営は{op}です(<a href="/about/">運営者情報</a>)。ご意見や、内容の誤りのご指摘は、<a href="/contact/">お問い合わせ</a>から受け付けています。</p>'),
        ("載せる商品の選び方", "<ul><li>贈り物として渡しやすい品であること(日用品や、相手の年齢に合わない品は除きます)。</li>"
         "<li>商品ページで、仕様と注意事項が確かめられること。</li><li>購入者の評価が、一定の水準を満たしていること。</li>"
         "<li>同じ店の商品に、かたよらないこと。</li></ul><p>広告の報酬の有無や大小で、載せる商品や順番を決めることはしません。</p>"),
        ("文章の作り方", "<p>商品の説明は、商品ページの仕様、メーカーなどの公開情報、購入者の声の傾向を読んで、自分たちの言葉でまとめています。"
         "商品ページやレビューの文章を、そのまま載せることはしません。確かめられないことは、書かないようにしています。</p>"
         "<p>当サイトで商品を実際に使って試した感想ではありません。そのことは、商品を紹介するページにも書いています。</p>"),
        ("毎日のおすすめ", '<p><a href="/picks/">毎日のおすすめ</a>では、楽天市場とAmazonから10点ずつを選び、渡す場面と、贈る前に確かめたい点まで書いています。'
         "公開前に、数字や言い回しを、別の目でも確かめています。</p>"),
        ("価格と画像", "<p>楽天市場の商品の価格・在庫・画像・評価は、楽天ウェブサービスから、毎日、取得し直しています。"
         "Amazonの商品は、規約により、価格・評価・商品の写真を載せていません。写真の代わりに、贈る場面を表したイメージ画像を使い、その旨を明記しています。</p>"),
        ("数字と統計", '<p><a href="/data/">データ室</a>の数字は、出典を明記しています。「当サイトの商品」と書いてあるものは、当サイトで取り上げた商品の集計で、市場全体ではありません。</p>'),
        ("広告について", "<p>当サイトは、楽天アフィリエイトとAmazonアソシエイトに参加しています。リンク先で購入されると、運営者に報酬が支払われることがあります。広告のあるページには、「PR」と表示しています。</p>"),
        ("訂正", "<p>誤りが分かったときは、速やかに直します。お気づきの点は、お問い合わせからお知らせください。</p>"),
        ("アイコン", '<p>アイコンには、<a href="https://phosphoricons.com/" rel="noopener" target="_blank">Phosphor Icons</a>(MITライセンス)を使っています。</p>'),
    ]
    if not PICKS_ON:
        secs = [x for x in secs if x[0] != "毎日のおすすめ"]
    if not DATA_ON:
        secs = [x for x in secs if x[0] != "数字と統計"]
    body = "".join(f'<section class="g-sec"><h2>{h}</h2>{x}</section>' for h, x in secs)
    html = f"""{head_band("lilac", "", "編集方針", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("編集方針", None)])}</div>
<article class="guide">{body}</article>"""
    return page(cfg, preview, path="/policy/", title=f"編集方針 | {cfg['site_name']}", description=lead, body=html)


# ---------------------------------------------------------------- site

def prepare(c: dict, items: dict | None, cfg: dict) -> dict:
    items = items or {"pairs": {}, "portrait": [], "fetched_at": None}
    f = items.get("fetched_at")
    label = "取得日時不明"
    if f:
        t = datetime.fromisoformat(f)
        label = f"{t.year}年{t.month}月{t.day}日 {t.hour}:{t.minute:02d}"
    # the stored lists were chosen at fetch time; apply today's rules again (relaxed superset) so a rule change shows without refetching
    owner = {ct.pair_key(p): p.get("recipient") for p in ct.pages(c)}
    pairs = {}
    for k, v in items.get("pairs", {}).items():
        def ok(i, k=k):
            return usable(i, c["filters"], owner.get(k), relaxed=True)
        if "ideas" in v:
            pairs[k] = {"ideas": [{**idea, "items": [i for i in idea["items"] if ok(i)]} for idea in v["ideas"]],
                        "tiers": {t: [i for i in lst if ok(i)] for t, lst in v["tiers"].items()}}
        else:  # data fetched before ideas existed: budget lists only
            pairs[k] = {t: [i for i in lst if ok(i)] for t, lst in v.items() if isinstance(lst, list)}
    d = {"c": c, "pairs": pairs, "portrait": items.get("portrait", []), "fetched_label": label, "site_name": cfg["site_name"],
         "fetched_date": (f or date.today().isoformat())[:10], "daily_items": items.get("daily", {})}
    if items.get("pairs"):
        d["live_themes"] = [t for t in c["themes"] if len(pair_items(d, t["key"])[2]) >= MIN_THEME_ITEMS]
    else:                       # a preview build without any product data shows every theme
        d["live_themes"] = list(c["themes"])
    return d


def mood_photo(key: str) -> str:
    """The mood photograph (assets/mood) for a share card: one of the eighteen, chosen by the page's name, so every page has its own and a rebuild keeps it."""
    from zlib import crc32
    from sites.yorokobu import dailypicks as dp
    kinds = list(dp.KIND_KEY.values())
    h = crc32(key.encode("utf-8"))
    return f"{kinds[h % len(kinds)]}-{(h // 7) % dp.MOOD_VARIANTS + 1}"


def render_site(c: dict, items: dict | None, cfg: dict, out: Path, release: bool = False, today: date | None = None, ranking: dict | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    if release and not (items and items.get("pairs")):
        raise BuildError("release build refused: no fetched products (run sites/yorokobu/fetch.py first)")
    preview = bool(missing)
    today = today or date.today()
    d = prepare(c, items, cfg)
    d["ranking"] = rk.view(ranking, c["filters"])
    global RANKING_ON, DATA_ON, PICKS_ON
    RANKING_ON = bool(d["ranking"])
    DATA_ON = bool(dataroom.results(d))
    PICKS_ON = bool(c.get("daily"))
    d["numbers"] = nm.view(d["pairs"], c["filters"])
    d["gacha"] = gacha_data(d, cfg)
    cards: dict[str, bytes] = {}
    OG.clear()
    SEEN.clear()
    if ogimage.available():
        site = cfg["site_name"]
        cards["og/default.png"] = ogimage.card(title="よろこばれるプレゼント、見つかります。", tag="イベントと相手から", site=site, photo=mood_photo("default"))
        for o in c["occasions"]:
            cards[f"og/occasion/{o['slug']}.png"] = ogimage.card(title=f"{o['name']}のプレゼント", tag="選び方と相手別", site=site, photo=mood_photo(o["slug"]))
        for r in c["recipients"]:
            cards[f"og/for/{r['slug']}.png"] = ogimage.card(title=f"{r['name']}へのプレゼント", tag="イベント別", site=site, photo=mood_photo(r["slug"]))
        for p in c["pairs"]:
            cards[f"og/gift/{ct.pair_key(p)}.png"] = ogimage.card(
                title=p["title"].split(" ")[0], tag=f"{c['rec'][p['recipient']]['name']} × {c['occ'][p['occasion']]['name']}", site=site, photo=mood_photo(ct.pair_key(p)))
        for ps in (c["persona"] or {}).get("personas", []):
            cards[f"og/diagnosis/{ps['slug']}.png"] = ogimage.card(title=ps["name"], tag="プレゼント診断", site=site, photo=mood_photo(ps["slug"]))
        for a in c["articles"]:
            cards[f"og/read/{a['slug']}.png"] = ogimage.card(title=a["title"], tag="読みもの", site=site, photo=mood_photo(a["slug"]))
        for day in c.get("daily") or []:
            m, dd = int(day["date"][5:7]), int(day["date"][8:10])
            cards[f"og/picks/{day['date']}.png"] = ogimage.card(title="今日のおすすめギフト", tag=f"{m}月{dd}日 {day['theme']}", site=site, photo=day["amazon"][0]["mood"])
        for th in c["themes"]:
            cards[f"og/theme/{th['slug']}.png"] = ogimage.card(title=th["title"], tag=next(g["name"] for g in c["theme_groups"] if g["slug"] == th["group"]), site=site, photo=mood_photo(th["slug"]))
        OG.update(k[len("og/"):-len(".png")] for k in cards)
    pages: dict[str, str | bytes] = {"index.html": index_page(d, cfg, preview, today),
                                     "occasion/index.html": hub_page(d, cfg, preview, "occasion"),
                                     "for/index.html": hub_page(d, cfg, preview, "for")}
    pages["policy/index.html"] = policy_page(d, cfg, preview)
    bt = budget_tiers(d)
    if bt:
        pages["budget/index.html"] = budget_hub_page(d, cfg, preview, bt)
        for tier, pool in bt:
            pages[f"budget/{tier['slug']}/index.html"] = budget_page(d, cfg, preview, tier, pool, bt)
    pages["memo/index.html"] = memo_page(d, cfg, preview, today)
    pages["calendar/index.html"] = calendar_page(d, cfg, preview, today)
    months = month_pages(c, today)
    if months:
        pages["month/index.html"] = month_hub_page(d, cfg, preview, today, months)
        for m in months:
            pages[f"month/{m}/index.html"] = month_page(d, cfg, preview, m, today, months)
    pages["calendar/yorokobu-gift-days.ics"] = giftcal.ics(cfg["site_url"], [today.year, today.year + 1, today.year + 2],
                                                             f"{today:%Y%m%d}T000000Z")
    for o in c["occasions"]:
        pages[f"occasion/{o['slug']}/index.html"] = occasion_page(d, cfg, preview, o)
    for r in c["recipients"]:
        pages[f"for/{r['slug']}/index.html"] = recipient_page(d, cfg, preview, r)
    pages["tool/index.html"] = tools_hub_page(d, cfg, preview)
    pages["tool/calc/index.html"] = calc_page(d, cfg, preview)
    if d["gacha"]:
        gp = json.loads(d["gacha"])
        pages["tool/gacha/index.html"] = gacha_page(d, cfg, preview, gp["rec"], gp["tiers"])
        pages["tool/gacha/items.json"] = d["gacha"]
    if c["taboo"]:
        pages["tool/taboo/index.html"] = taboo_page(d, cfg, preview)
    if c["persona"]:
        pages["diagnosis/index.html"] = quiz_page(d, cfg, preview)
        for ps in c["persona"]["personas"]:
            pages[f"diagnosis/{ps['slug']}/index.html"] = persona_page(d, cfg, preview, ps)
    if c["articles"]:
        pages["read/index.html"] = read_hub_page(d, cfg, preview)
        for a in c["articles"]:
            pages[f"read/{a['slug']}/index.html"] = article_page(d, cfg, preview, a)
    pages["feed.xml"] = feed_xml(d, cfg)
    if c["messages"]:
        pages["message/index.html"] = message_hub_page(d, cfg, preview)
        for slug in c["messages"]:
            pages[f"message/{slug}/index.html"] = message_page(d, cfg, preview, slug)
    if c.get("amazon") and cfg.get("amazon_tracking_id"):
        pages["amazon/index.html"] = amazon_hub_page(d, cfg, preview)
    if d["numbers"]:
        pages["numbers/index.html"] = numbers_hub_page(d, cfg, preview)
        for L in d["numbers"]["lists"]:
            pages[f"numbers/{L['slug']}/index.html"] = numbers_page(d, cfg, preview, L["slug"])
    if d["ranking"]:
        pages["ranking/index.html"] = ranking_hub_page(d, cfg, preview)
        for slug in d["ranking"]["order"]:
            pages[f"ranking/{slug}/index.html"] = ranking_page(d, cfg, preview, slug)
    pages.update(dataroom.build_pages(d, cfg, preview))
    pages.update(picksite.build_pages(d, cfg, preview))
    if d["live_themes"]:
        pages["theme/index.html"] = theme_hub_page(d, cfg, preview)
        for th in d["live_themes"]:
            pages[f"theme/{th['slug']}/index.html"] = theme_page(d, cfg, preview, th)
    for slug in c["guides"]:
        pages[f"guide/{slug}/index.html"] = guide_page(d, cfg, preview, slug)
    for p in c["pairs"]:
        pages[f"gift/{ct.pair_key(p)}/index.html"] = pair_page(d, cfg, preview, p)
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="イベントと贈る相手から、プレゼントの選び方と、商品の例を、探しやすく整理して、贈り物選びに役立てていただくこと。",
        sources_html='商品の名前・価格・画像・レビュー・販売ページのリンクは、<a href="https://webservice.rakuten.co.jp/" rel="noopener" target="_blank">楽天ウェブサービス</a>(楽天市場)の情報を使っています。選び方などの文章は、当サイトの編集方針にもとづいて作成しています。',
        update_text="商品の価格・在庫は、毎日、楽天市場の情報にあわせて更新します。各ページに取得した日付を表示します。",
        disclaimer_html=("<p>商品の価格・在庫・送料・レビューは、取得した時点の情報で、販売ページと異なる場合があります。購入前に、必ず、販売ページでご確認ください。"
                         "当サイトは、商品の品質や、贈った相手が喜ぶことを保証するものではありません。</p>"
                         "<p>当サイトの運営者は、楽天市場で、似顔絵のショップも運営しています。そのショップの商品を紹介するときは、そのことを、ページ上に明示します。</p>"
                         "<p>当サイトは、楽天グループ株式会社が運営するものではありません。</p>"),
        contact_notice="商品の購入・配送・返品などのお問い合わせは、各販売店へお願いします。当サイトでは、商品の販売を行っていません。",
        input_note="", finish=lambda s: s))
    pages["manifest.webmanifest"] = json.dumps(MANIFEST, ensure_ascii=False, indent=1)
    pages.update(cards)
    listed = dict(pages)                                   # the sitemap lists the pages that can be found by searching, not the shared-list page (noindex, built from a link)
    if SEEN:
        pages["list/index.html"] = list_page(d, cfg, preview)
        pages["list/items.json"] = json.dumps(SEEN, ensure_ascii=False, separators=(",", ":"))
    pages.update(standard_files(listed, cfg, preview, d["fetched_date"]))
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
        files = render_site(ct.load(), items, cfg, Path(a.out), release=a.release, ranking=rk.load())
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
