"""The redesign of sale-calendar.com ("SALEカレンダー"): Muse's template kit (2026-11-12) fed with the site's own confirmed data.

Switched on by the environment variable KAIDOKI_REDESIGN=1 (hooks.py calls prepare() and apply()) or by "redesign": true in config.json; without it nothing here runs and the site is built exactly as before.
The pipeline of sokuhou/newsite.py is kept (content pages, legal pages, JSON-LD, measure tag, sitemap, SEO and thin-page checks).  apply() takes the pages it has rendered and
re-wraps each one in the kit's layout: the kit-native pages (top, calendar, malls, category, product, ...) get the kit's templates filled from sites/kaidoki/gen/facts.py; every other
page (the explanation pages, method, about, privacy, contact) keeps its confirmed text and gets the kit's header, banner and reading column.

Data: the sales are facts.EVENTS (organisers' own announcements; the checked day is gen.common.CHECKED), the unannounced ones facts.UNANNOUNCED.  No product price, no ranking of
shops.  The product pages come from sites/kaidoki/redesign/products/*.json (tracked: official campaign facts of makers and carriers only, no mall product page address; see tools/extract_product.py): no file, no page.
The hero's headline frame comes from hero.json (the picture is permanent).  Going public: site.json (demo, publication_reviewed), see the result file of 2026-11-12.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
JST = timezone(timedelta(hours=9))
WD = "月火水木金土日"


def enabled(cfg: dict | None = None) -> bool:
    """On when KAIDOKI_REDESIGN=1 (a side build for checking) or when config.json says "redesign": true (the switch of the real site).  KAIDOKI_REDESIGN=0 forces it off."""
    v = os.environ.get("KAIDOKI_REDESIGN")
    if v in ("0", "1"):
        return v == "1"
    return bool(cfg and cfg.get("redesign"))


def e(v) -> str:
    return escape(str(v), quote=True)


def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def settings() -> dict:
    """site.json.  KAIDOKI_REDESIGN_DEMO=0 builds as the public site (no noindex) WITHOUT changing the file: for the gates (sitecheck / layoutcheck / text gate) and screenshots
    before the switch.  It still wants a reviewed flag in the file when the file itself says demo=false."""
    s = _json(HERE / "site.json")
    if os.environ.get("KAIDOKI_REDESIGN_DEMO") == "0":
        s = dict(s, demo=False, publication_reviewed=True)
    if os.environ.get("KAIDOKI_REDESIGN_DEMO") == "1":
        s = dict(s, demo=True)
    return s


def now() -> datetime:
    v = os.environ.get("KAIDOKI_NOW")
    if v:
        return datetime.fromisoformat(v).replace(tzinfo=JST)
    t = os.environ.get("KAIDOKI_TODAY")
    if t:
        return datetime.fromisoformat(t + "T12:00").replace(tzinfo=JST)
    return datetime.now(JST)


# ------------------------------------------------------------------ prepare: the name
OLD_NAME = "買い時カレンダー"


def _rename(x, new: str):
    if isinstance(x, str):
        return x.replace(OLD_NAME, new)
    if isinstance(x, list):
        return [_rename(i, new) for i in x]
    if isinstance(x, dict):
        return {k: _rename(v, new) for k, v in x.items()}
    return x


def prepare(cfg: dict, spec: dict, content: list, site_dir) -> list:
    """The site name and the operator name of the redesign (config.json stays as it is for the current site)."""
    s = settings()
    cfg["site_name"] = s["name"]
    cfg["operator_name"] = s["operator_name"]
    for k in list(spec):
        spec[k] = _rename(spec[k], s["name"])
    return [_rename(p, s["name"]) for p in content]


# ------------------------------------------------------------------ sales (the kit's sales.json, from facts.py)
MALL_ID = {"楽天": "rakuten", "Amazon": "amazon", "Yahoo!ショッピング": "yahoo"}
MALL_TITLE = {"rakuten": "楽天市場", "amazon": "Amazon", "yahoo": "Yahoo!ショッピング"}
MALL_PATH = {"rakuten": "/rakuten/", "amazon": "/amazon/sale-calendar/", "yahoo": "/yahoo/"}
GROUP_PAGE = {"rsup": "/rakuten/super-sale/", "rmar": "/rakuten/marathon/", "rbf": "/rakuten/black-friday/", "rhat": "/rakuten/hatsuuri/",
              "apd": "/amazon/prime-day/", "apde": "/amazon/prime-day-early/", "akan": "/amazon/prime-appreciation/", "akane": "/amazon/prime-appreciation/",
              "abf": "/amazon/black-friday/", "abfe": "/amazon/black-friday/", "ashin": "/amazon/sale-calendar/", "ahat": "/amazon/sale-calendar/",
              "ypp": "/yahoo/", "ybaku": "/yahoo/", "ybf": "/yahoo/"}
UNANNOUNCED_PAGE = [("楽天スーパーSALE", "/rakuten/super-sale/"), ("Amazon ブラックフライデー", "/amazon/black-friday/"), ("Rakuten初売り", "/rakuten/hatsuuri/"),
                    ("楽天ブラックフライデー", "/rakuten/black-friday/"), ("Amazon 初売り", "/amazon/sale-calendar/"), ("プライムデー", "/amazon/prime-day/")]
SHOW_FROM = "2026-01-01"          # sales that ended before this are not listed (the explanation pages keep the history)


def _iso(day: str, t: str, default: str) -> str:
    return f"{day}T{(t or default)}:00+09:00"


def sales_list() -> list[dict]:
    from sites.kaidoki.gen import facts
    from sites.kaidoki.gen.common import CHECKED
    out = []
    for ev in facts.EVENTS:
        if ev["end"] < SHOW_FROM:
            continue
        mall_id = MALL_ID[ev["mall"]]
        out.append({"id": ev["id"], "mall_id": mall_id, "mall": MALL_TITLE[mall_id], "title": ev["name"],
                    "start": _iso(ev["start"], ev.get("start_t", ""), "00:00"), "end": _iso(ev["end"], ev.get("end_t", ""), "23:59"),
                    "start_t": bool(ev.get("start_t")), "end_t": bool(ev.get("end_t")), "href": GROUP_PAGE[ev["group"]],
                    "summary": ev.get("note") or ("主催者の公式ページで確認した日程です。" if ev.get("read") != "summary" else "公式ページの表示で確認した日程です。"),
                    "tags": [f"確認日 {CHECKED.replace('-', '/')}"], "categories": ["electronics"]})
    for name, mall, why in facts.UNANNOUNCED:
        mall_id = MALL_ID[mall]
        href = next(p for k, p in UNANNOUNCED_PAGE if name.startswith(k))
        out.append({"id": "un-" + hashlib.sha1(name.encode()).hexdigest()[:6], "mall_id": mall_id, "mall": MALL_TITLE[mall_id], "title": name, "start": None, "end": None,
                    "start_t": False, "end_t": False, "href": href, "summary": why, "tags": [f"確認日 {CHECKED.replace('-', '/')}"], "categories": ["electronics"]})
    return out


def state(s: dict, at: datetime) -> str:
    if not s.get("start"):
        return "日程未発表"
    if at < datetime.fromisoformat(s["start"]):
        return "開催予定"
    if at >= datetime.fromisoformat(s["end"]) + timedelta(minutes=1):          # "1:59" is until 2:00
        return "終了"
    return "開催中"


def order(sales: list[dict], at: datetime) -> list[dict]:
    rank = {"開催中": 0, "開催予定": 1, "日程未発表": 2, "終了": 3}
    def key(s):
        st = state(s, at)
        if st == "終了":
            return (rank[st], "", [-ord(c) for c in s["end"]])
        return (rank[st], s["start"] or "9999", [])
    return sorted(sales, key=key)


def fmt(iso: str, has_time: bool) -> str:
    d = datetime.fromisoformat(iso)
    base = f"{d.year}/{d.month:02d}/{d.day:02d}({WD[d.weekday()]})"
    return f"{base} {d.hour:02d}:{d.minute:02d}" if has_time else base


def sale_card(s: dict, at: datetime) -> str:
    st = state(s, at)
    period = fmt(s["start"], s["start_t"]) + " 〜 " + fmt(s["end"], s["end_t"]) if s.get("start") else "日程未発表"
    return (f'<article class="sale-tile" data-mall="{e(s["mall_id"])}" data-status="{e(st)}" data-start="{e(s.get("start") or "")}" data-end="{e(s.get("end") or "")}">'
            f'<div class="tile-top"><span class="status {"upcoming" if st != "開催中" else ""}">{e(st)}</span><span>{e(s["mall"])}</span></div>'
            f'<h3><a href="{e(s["href"])}">{e(s["title"])}</a></h3><p class="tile-date">{e(period)}</p><p>{e(s["summary"])}</p>'
            f'<div class="mini-tags">' + "".join(f"<span>{e(x)}</span>" for x in s["tags"]) + f'</div>{link(s["href"], "対象・条件を見る")}</article>')


def sales_grid(items: list[dict], at: datetime) -> str:
    if not items:
        return notice("この条件に合う掲載情報はありません。未発表の予定は推測しません。")
    return '<div class="sales-grid">' + "".join(sale_card(x, at) for x in items) + "</div>"


# ------------------------------------------------------------------ small html helpers (the kit's build.py)
def link(href: str, label: str, cls: str = "text-link") -> str:
    return f'<a class="{cls}" href="{e(href)}">{e(label)} →</a>'


def paragraphs(items) -> str:
    return "".join("<p>" + e(x) + "</p>" for x in items)


def notice(text: str) -> str:
    return '<div class="notice">' + e(text) + "</div>"


def checks(items) -> str:
    return '<ul class="checklist">' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def facts_dl(rows) -> str:
    return '<dl class="facts">' + "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in rows) + "</dl>"


def category_card(c: dict, anchor: bool = True) -> str:
    i = c["image_index"]
    inner = (f'<span class="category-photo" aria-hidden="true"><svg viewBox="0 0 512 512"><defs><clipPath id="clip-{e(c["id"])}"><rect width="512" height="512"/></clipPath></defs>'
             f'<g clip-path="url(#clip-{e(c["id"])})"><image href="assets/flyer-categories.webp" width="2048" height="1024" x="{-(i % 4) * 512}" y="{-(i // 4) * 512}"/></g></svg></span>'
             f'<span class="category-content"><h3>{e(c["title"])}</h3><p>{e(c["description"])}</p>' + ('<span class="category-go">このジャンルを見る →</span>' if anchor else "") + "</span>")
    return f'<a class="category" href="{e(c["href"])}">{inner}</a>' if anchor else f'<div class="category">{inner}</div>'


def category_cards(items: list[dict]) -> str:
    return '<div class="categories kit-categories">' + "".join(category_card(c) for c in items) + "</div>"


def article_cards(items: list[dict]) -> str:
    return '<div class="article-links">' + "".join(
        f'<article><span class="num">{e(a["label"])}</span><h3>{link(a["href"], a["title"], "")}</h3>' + (f'<p>{e(a["description"])}</p>' if a["description"] else "") + '</article>' for a in items) + "</div>"


def filters(malls: list[str]) -> str:
    return ('<form class="listing-filters" id="listing-filter"><label>開催状況<select name="status"><option value="">すべて</option>'
            + "".join(f"<option>{x}</option>" for x in ["開催中", "開催予定", "日程未発表", "終了"])
            + '</select></label><label>モール<select name="mall"><option value="">すべて</option>'
            + "".join(f'<option value="{e(m)}">{e(MALL_TITLE[m])}</option>' for m in malls)
            + '</select></label><label>買う期限<input type="date" name="deadline"></label><button class="small-btn" type="reset">リセット</button>'
              '<span id="filter-count" role="status" aria-live="polite"></span></form><p id="filter-empty" class="notice" hidden>条件に合う掲載情報はありません。</p>')


def crumbs_html(items: list[tuple[str, str | None]]) -> str:
    out = []
    for i, (label, href) in enumerate(items):
        out.append(f'<li><a href="{e(href)}">{e(label)}</a></li>' if href and i < len(items) - 1 else f'<li aria-current="page">{e(label)}</li>')
    return '<nav class="breadcrumbs" aria-label="パンくず"><ol>' + "".join(out) + "</ol></nav>"


def banner(label: str, h1_html: str, text: str) -> str:
    return f'<section class="page-banner"><div class="wrap"><span class="banner-label">{e(label)}</span><h1>{h1_html}</h1><p>{e(text)}</p></div></section>'


def template(name: str, **slots) -> str:
    text = (HERE / "tmpl" / f"{name}.html").read_text(encoding="utf-8")
    for k, v in slots.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[a-z_]+\}\}", text)
    if left:
        raise ValueError(f"{name}: unresolved slots {left}")
    return text


# ------------------------------------------------------------------ urls: the kit writes relative file names, the site uses folders
KIT_URLS = {"index.html": "/", "calendar.html": "/calendar/", "categories.html": "/buytime/", "malls.html": "/malls/", "calculator.html": "/calc/",
            "articles.html": "/articles/", "method.html": "/method/", "about.html": "/about/", "history.html": "/corrections/", "privacy.html": "/privacy/",
            "contact.html": "/contact/"}
_ATTR = re.compile(r'(href|src)="((?!https?:|/|#|mailto:)[^"]+)"')


def absolutize(html: str) -> str:
    def sub(m):
        attr, v = m.group(1), m.group(2)
        if v.startswith("assets/"):
            return f'{attr}="/assets/kit/{v}"'
        if v in KIT_URLS:
            return f'{attr}="{KIT_URLS[v]}"'
        raise ValueError(f"redesign: relative link without a place: {v}")
    return _ATTR.sub(sub, html)


NAV = [("セール日程", "/calendar/", ("/calendar/",)), ("商品別の買い時", "/buytime/", ("/buytime/", "/kaden/", "/randoseru/", "/what-to-buy/")),
       ("モール・公式ストア", "/malls/", ("/malls/", "/rakuten/", "/amazon/", "/yahoo/")), ("実質価格を計算", "/calc/", ("/calc/",)),
       ("調査・検証 ↗", "/articles/", ("/articles/", "/method/"))]


def nav_html(path: str) -> str:
    out = []
    for label, href, prefixes in NAV:
        cur = any(path.startswith(p) for p in prefixes)
        out.append(f'<a href="{href}"{" aria-current=\"page\"" if cur else ""}>{label}</a>')
    return '<nav class="nav" id="main-nav" aria-label="メイン">' + "".join(out) + "</nav>"


# ------------------------------------------------------------------ the pages
MAIN = re.compile(r'<main class="wrap">\n(.*)\n</main>', re.S)
HEAD = re.compile(r"<head>\n(.*?)</head>", re.S)
CRUMBS = re.compile(r'<nav class="crumbs"[^>]*>(.*?)</nav>\n?', re.S)
CRUMB_ITEM = re.compile(r'<a href="([^"]+)">([^<]+)</a>|<span>([^<]+)</span>')
H1 = re.compile(r"<h1>(.*?)</h1>\n?", re.S)
ANSWER = re.compile(r'<p class="answer">(.*?)</p>\n?', re.S)
OLD_CSS = re.compile(r'<link rel="stylesheet" href="/assets/style\.css[^>]*>\n?')
ICONS_OLD = re.compile(r'<link rel="icon" href="/favicon\.ico"[^>]*>\n<link rel="icon" type="image/png" sizes="32x32"[^>]*>\n<link rel="apple-touch-icon"[^>]*>\n')
ICONS_NEW = ('<link rel="icon" href="/favicon.ico" sizes="any">\n<link rel="icon" type="image/png" sizes="32x32" href="/assets/fv/d-gold-bag-32.png">\n'
             '<link rel="icon" type="image/png" sizes="16x16" href="/assets/fv/d-gold-bag-16.png">\n<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">\n')

CARD_SKIP = ("カード", "分かります", "入口", "確かめて", "確かめます", "見ます", "置きます", "載せ", "並べ", "出ます", "決まります", "ご確認")
LABELS = {"/calendar/": "日程を探す", "/buytime/": "ジャンルで探す", "/malls/": "モール別", "/rakuten/": "楽天市場", "/amazon/sale-calendar/": "Amazon", "/yahoo/": "Yahoo!ショッピング",
          "/kaden/": "家電・デジタル", "/calc/": "実質価格の計算", "/method/": "調査方法", "/about/": "運営情報", "/privacy/": "プライバシー", "/contact/": "お問い合わせ",
          "/corrections/": "訂正履歴", "/articles/": "調査・検証", "/black-friday/": "ブラックフライデー", "/randoseru/": "ランドセル", "/what-to-buy/": "買う物から探す"}
PREFIX_LABELS = (("/rakuten/", "楽天市場"), ("/amazon/", "Amazon"), ("/kaden/", "家電・デジタル"), ("/calc/", "実質価格の計算"), ("/yahoo/", "Yahoo!ショッピング"))


def label_of(path: str) -> str:
    if path in LABELS:
        return LABELS[path]
    return next((lb for pre, lb in PREFIX_LABELS if path.startswith(pre)), "ガイド")


def parse(html: str) -> dict:
    head = HEAD.search(html).group(1)
    main = MAIN.search(html).group(1)
    crumbs = []
    m = CRUMBS.search(main)
    if m:
        crumbs = [(a or c, href or None) for href, a, c in CRUMB_ITEM.findall(m.group(1))]
        main = main[:m.start()] + main[m.end():]
    h1 = H1.search(main)
    main = main[:h1.start()] + main[h1.end():]
    ans = ANSWER.search(main)
    answer = ""
    if ans:
        answer = ans.group(1)
        main = main[:ans.start()] + main[ans.end():]
    desc = re.search(r'<meta name="description" content="([^"]*)">', head)
    return {"head": head, "h1": h1.group(1), "answer": answer, "crumbs": crumbs, "rest": main.strip(), "desc": desc.group(1) if desc else ""}


def head_html(head: str, demo: bool, ld_extra: str = "") -> str:
    head = OLD_CSS.sub("", head)
    head = ICONS_OLD.sub(ICONS_NEW, head, count=1)
    if demo and 'name="robots"' not in head:
        head = head.replace('<meta name="viewport"', '<meta name="robots" content="noindex,nofollow">\n<meta name="viewport"', 1)
    return head + ld_extra


def doc(rest: str) -> str:
    return f'<div class="wrap page-content doc"><article class="reading-column">{rest}</article></div>' if rest.strip() else ""


class Ctx:
    def __init__(self, pages: dict, content: list, cfg: dict, site_dir):
        self.pages, self.cfg, self.site_dir = pages, cfg, Path(site_dir)
        self.set = settings()
        self.at = now()
        self.by_path = {p["path"]: p for p in content}
        self.content = content
        self.sales = order(sales_list(), self.at)
        cats = _json(HERE / "categories.json")
        self.categories = [dict(c, href="/kaden/") for c in cats if c["id"] == "electronics"]      # the genres whose data and product pages are ready (first: electronics)
        self.malls = _json(HERE / "malls.json")
        self.ver = hashlib.sha1(b"".join((HERE / "static" / "styles" / n).read_bytes() for n in ("site.css", "templates.css", "extra.css"))
                                + (HERE / "static" / "scripts" / "site.js").read_bytes()).hexdigest()[:8]
        self.products = load_products(self.site_dir)
        self.hero = _json(HERE / "hero.json")

    def card(self, path: str, label: str | None = None) -> dict:
        p = self.by_path[path]
        # a card shows a page's text a second time: a word the text gate counts must not be counted twice, so the first of description / first sentence of the lead answer
        # without such a word is used, and a plain line when both have one (a card is never empty: sitecheck reads an empty block as a defect)
        first = p.get("answer", "").split("。")[0] + "。" if p.get("answer") else ""
        desc = next((x for x in (p["description"], first) if x and not any(w in x for w in CARD_SKIP)), "日程と条件を、このページにまとめています。")
        return {"href": path, "title": p["h1"], "description": desc, "label": label or label_of(path)}

    def children(self, path: str) -> list[dict]:
        return [self.card(c["path"]) for c in self.content if c.get("parent") == path]

    def product_cards(self, category: str) -> list[dict]:
        return [{"href": f"/kaden/{p['slug']}/", "title": p["title"], "description": p["lead"].split("。")[0] + "。", "label": p["kicker"]} for p in self.products if p["category"] == category]


def load_products(site_dir: Path) -> list[dict]:
    d = Path(site_dir) / "redesign" / "products"
    return [_json(f) for f in sorted(d.glob("*.json"))] if d.is_dir() else []


def hero_headline(ctx: Ctx) -> str:
    at = ctx.at
    pick = ctx.hero["default"]
    for h in ctx.hero["scheduled"]:
        if ("from" not in h or at >= datetime.fromisoformat(h["from"])) and ("until" not in h or at < datetime.fromisoformat(h["until"])):
            pick = h
            break
    return (f'<div class="eyebrow">{e(pick["eyebrow"])}</div><h1>{pick["h1"]}</h1><p>{pick["lead"]}</p><div class="hero-cta">'
            + "".join(f'<a class="btn {c[2]}" href="{e(c[1])}">{e(c[0])}</a>' for c in pick["cta"]) + "</div>")


def native_body(ctx: Ctx, path: str, pg: dict) -> str | None:
    """The kit-template part of the pages that have one (None: the page keeps the plain reading column)."""
    at = ctx.at
    live = [s for s in ctx.sales if state(s, at) in ("開催中", "開催予定")]
    if path == "/":
        arts = [ctx.card("/rakuten/marathon/", "楽天"), ctx.card("/rakuten/marathon-vs-super-sale/", "楽天"), ctx.card("/calc/points/", "計算")]
        return template("home", headline=hero_headline(ctx), featured=sales_grid(live[:2], at), schedule=sales_grid(ctx.sales[:3], at),
                        categories=category_cards(ctx.categories), articles=article_cards(arts),
                        more=f'<section class="section"><div class="wrap"><article class="reading-column doc"><p class="answer">{pg["answer"]}</p>{pg["rest"]}</article></div></section>')
    if path == "/calendar/":
        stamp = f"表示時点：{fmt(at.isoformat(timespec='seconds'), True)}（日本時間）。未発表・終了を含めて確認できます。日程は、各セールの欄に書いた確認日に、主催者の発表や信頼できる報道で確かめたものです。"
        return template("calendar", notes=notice(stamp), filters=filters(["rakuten", "amazon", "yahoo"]), sales=sales_grid(ctx.sales, at))
    mall = next((m for m, pth in MALL_PATH.items() if pth == path), None)
    if mall:
        info = next(m for m in ctx.malls if m["id"] == mall)
        kids = [ctx.card(c["path"]) for c in ctx.content if c.get("parent") == path]
        return template("mall", intro="", sales=sales_grid([s for s in ctx.sales if s["mall_id"] == mall and state(s, at) != "終了"], at),
                        checks=checks(info["checks"]), links=article_cards(kids or [ctx.card("/calc/points/", "計算")]))
    if path == "/kaden/":
        c = ctx.categories[0]
        kids = ctx.children("/kaden/") + ctx.product_cards("electronics")
        return template("category", intro=paragraphs(c["intro"]), image=category_card(c, anchor=False), sales=sales_grid([s for s in ctx.sales if state(s, at) != "終了"][:6], at),
                        checks=checks(c["checks"]), articles=article_cards(kids))
    if path == "/buytime/":
        return template("category-index", intro=notice("金額や商品の価格帯で対象を限定しません。情報を用意できたジャンルから掲載します。"), categories=category_cards(ctx.categories))
    return None


def mall_index_body(ctx: Ctx) -> str:
    cards = "".join(f'<article><span class="num">モール・公式ストア</span><h2>{e(MALL_TITLE[m["id"]])}</h2>{paragraphs([ctx.by_path[MALL_PATH[m["id"]]]["answer"]])}'
                    f'{link(MALL_PATH[m["id"]], "日程と条件を見る")}</article>' for m in ctx.malls if m["id"] in MALL_PATH)
    return template("mall-index", malls=f'<div class="template-grid">{cards}</div>')


def articles_body(ctx: Ctx) -> str:
    items = [ctx.card(p["path"]) for p in ctx.content if p.get("kind") in ("analysis", "article") and p["path"] != "/corrections/"]
    return template("article-index", intro=paragraphs(["数字の大きさだけで決めないための確認メモです。"]), articles=article_cards(items))


def product_pages(ctx: Ctx, base_head: str) -> dict:
    out = {}
    for pr in ctx.products:
        path = f"/kaden/{pr['slug']}/"
        stores = ""
        for st in pr["stores"]:
            links = " ／ ".join(f'<a href="{e(u)}" target="_blank" rel="noopener noreferrer">{e(t)} ↗</a>' for t, u in st["links"])
            src = f'確認日：{e(st["checked"])} ｜ 公式ページ：{links}' if links else f'確認日：{e(st["checked"])}'   # a store without a public source link (Amazon: its page address stays out of the repository) shows the date only
            stores += (f'<article class="store-card"><h3>{e(st["name"])}<span class="tag">{e(st["tag"])}</span></h3>{facts_dl(st["rows"])}'
                       f'<p class="src">{src}</p></article>')
        body = template("product", intro=paragraphs([pr["lead"]]), meta=f'<p class="meta-line">{e(pr["meta"])}</p>',
                        stores_h2=f'<span class="store-burst">{e(pr["stores_burst"])}</span> {e(pr["stores_h2"])}', stores=stores, note=notice(pr["note"]),
                        calc_big=e(pr["calc_big"]), calc_text=e(pr["calc_text"]), howto_h2=e(pr["howto_h2"]), howto="".join(f"<p>{e(x)}</p>" for x in pr["howto"]),
                        related="<h2>関連するセール</h2>" + sales_grid([s for s in ctx.sales if state(s, ctx.at) != "終了"][:4], ctx.at))
        title = f'{pr["title"]} | {ctx.cfg["site_name"]}'
        desc = pr["lead"].split("。")[0] + "。" + pr["lead"].split("。")[1] + "。"
        head = base_head
        head = re.sub(r"<title>.*?</title>", lambda m: f"<title>{e(title)}</title>", head, flags=re.S)
        head = re.sub(r'(<meta name="description" content=")[^"]*(">)', lambda m: m.group(1) + e(desc) + m.group(2), head)
        head = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', lambda m: m.group(1) + e(title) + m.group(2), head)
        head = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', lambda m: m.group(1) + e(desc) + m.group(2), head)
        url = ctx.cfg["site_url"].rstrip("/") + path
        head = re.sub(r'(<link rel="canonical" href=")[^"]*(">)', lambda m: m.group(1) + e(url) + m.group(2), head)
        head = re.sub(r'(<meta property="og:url" content=")[^"]*(">)', lambda m: m.group(1) + e(url) + m.group(2), head)
        head = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", head, flags=re.S)
        trail = [("トップ", "/"), ("商品別の買い時", "/buytime/"), ("家電・デジタル", "/kaden/"), (pr["crumb"], None)]
        ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, **({"item": ctx.cfg["site_url"].rstrip("/") + h} if h else {})} for i, (n, h) in enumerate(trail)]}
        head += '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
        out[path.strip("/") + "/index.html"] = wrap(ctx, path, head, crumbs_html(trail), banner(pr["kicker"], pr["h1_html"], pr["sub"]), body, pr.get("checked", ""), "product")
    return out


def wrap(ctx: Ctx, path: str, head: str, breadcrumb: str, heading: str, body: str, updated: str, page_type: str) -> str:
    demo = ctx.set["demo"]
    bar = ""
    if demo:
        bar = '<div class="demo-bar"><strong>公開前の確認用ページ</strong> 検索エンジンには登録されません ／ ' + e(fmt(ctx.at.isoformat(timespec="seconds"), True)) + " 日本時間を基準に表示</div>"
    html = template("base", head=head_html(head, demo), ver=ctx.ver, nav=nav_html(path), site_name=e(ctx.cfg["site_name"]), demo_banner=bar,
                    breadcrumb=f'<div class="wrap">{breadcrumb}</div>' if breadcrumb else "", heading=heading, body=body, updated=e(updated), page_type=e(page_type))
    return absolutize(html)


def apply(pages: dict, content: list, cfg: dict, spec: dict, site_dir) -> dict:
    ctx = Ctx(pages, content, cfg, site_dir)
    s = ctx.set
    if not s["demo"]:
        if not s["base_url"].startswith("https://") or not s.get("publication_reviewed"):
            raise ValueError("redesign: demo=false needs base_url (https) and publication_reviewed=true in sites/kaidoki/redesign/site.json")
        if s["base_url"].rstrip("/") != cfg["site_url"].rstrip("/"):
            raise ValueError("redesign: base_url differs from config.json site_url")
    out = dict(pages)
    base_head = None
    path_of = {("index.html" if p["path"] == "/" else p["path"].strip("/") + "/index.html"): p["path"] for p in content}
    path_of.update({"about/index.html": "/about/", "privacy/index.html": "/privacy/", "contact/index.html": "/contact/", "404.html": "/404.html"})
    for rel, html in pages.items():       # any other page of the pipeline (the contact form's thanks page, ...) is wrapped the same way, by its address
        if rel not in path_of and isinstance(html, str) and rel.endswith(".html") and html.startswith("<!doctype") and '<main class="wrap">' in html:
            path_of[rel] = "/" + rel
    for rel, path in path_of.items():
        html = pages.get(rel)
        if html is None:
            raise ValueError(f"redesign: {rel} was not built")
        pg = parse(html)
        if path == "/kaden/":
            base_head = pg["head"]
        if path == "/404.html":
            body = template("404", links=link("/", "トップへ戻る", "btn btn-red") + link("/calendar/", "セール日程を見る", "btn btn-light"))
            out[rel] = wrap(ctx, path, pg["head"], "", banner("404", pg["h1"], "ページが移動・削除されたときの案内です。" if not pg["desc"] else pg["desc"]), body, cfg.get("updated", ""), "404")
            continue
        body = native_body(ctx, path, pg)
        if path == "/":
            full = body
            out[rel] = wrap(ctx, path, pg["head"], "", "", full, ctx.by_path["/"]["updated"], "home")
            continue
        text = pg["answer"] or pg["desc"]
        trail = [("トップ", "/")] + (pg["crumbs"][1:] if pg["crumbs"] and pg["crumbs"][0][1] == "/" else pg["crumbs"]) if pg["crumbs"] else [("トップ", "/"), (re.sub(r"<[^>]+>", "", pg["h1"]), None)]
        page_type = "doc"
        if body is None:
            full = doc(pg["rest"])
        else:
            full = body + doc(pg["rest"])
            page_type = "kit"
        upd = ctx.by_path[path]["updated"] if path in ctx.by_path else ""
        out[rel] = wrap(ctx, path, pg["head"], crumbs_html([(a, b) for a, b in trail]), banner(label_of(path), pg["h1"], html_unescape(text)), full, upd, page_type)
    # pages the kit adds
    if base_head is None:
        raise ValueError("redesign: the /kaden/ page is missing")
    for rel, body_fn, path, title, desc, label in (
            ("malls/index.html", mall_index_body, "/malls/", "モール・公式ストアから探す", "楽天・Amazon・Yahoo!ショッピングのセール日程と参加条件を、モールごとに見られます。", "モール別"),
            ("articles/index.html", articles_body, "/articles/", "買う前の確認メモ", "セールの日程の読み方と、ポイント・上限・条件の確かめ方をまとめた解説ページの一覧です。", "調査・検証")):
        head = base_head
        head = re.sub(r"<title>.*?</title>", lambda m, t=title: f"<title>{e(t)} | {e(cfg['site_name'])}</title>", head, flags=re.S)
        head = re.sub(r'(<meta name="description" content=")[^"]*(">)', lambda m, d=desc: m.group(1) + e(d) + m.group(2), head)
        head = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', lambda m, t=title: m.group(1) + e(t) + m.group(2), head)
        head = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', lambda m, d=desc: m.group(1) + e(d) + m.group(2), head)
        url = cfg["site_url"].rstrip("/") + path
        head = re.sub(r'(<link rel="canonical" href=")[^"]*(">)', lambda m, u=url: m.group(1) + e(u) + m.group(2), head)
        head = re.sub(r'(<meta property="og:url" content=")[^"]*(">)', lambda m, u=url: m.group(1) + e(u) + m.group(2), head)
        head = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", head, flags=re.S)
        trail = [("トップ", "/"), (title, None)]
        ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, **({"item": cfg["site_url"].rstrip("/") + h} if h else {})} for i, (n, h) in enumerate(trail)]}
        head += '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
        out[rel] = wrap(ctx, path, head, crumbs_html(trail), banner(label, e(title), desc), body_fn(ctx), spec.get("updated", ""), "kit")
    out.update(product_pages(ctx, base_head))
    # the kit's own files
    for sub in ("styles", "scripts", "assets"):
        for f in sorted((HERE / "static" / sub).iterdir()):
            out[f"assets/kit/{sub}/{f.name}"] = f.read_bytes() if f.suffix == ".webp" else f.read_text(encoding="utf-8")
    return out


def html_unescape(s: str) -> str:
    import html
    return html.unescape(s)
