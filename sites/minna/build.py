"""みんなのイラスト (minna-no-illust.com): a free illustration site (commercial use allowed, no credit, no sign-up) with sets, genres, art touches, search and a card maker.

    python sites/minna/build.py [--release] [--out DIR]

Illustrations are AI-generated, picked and tidied by people; the site says so on every page.  Every illustration has a detail page with PNG (transparent) and
WebP downloads, an in-browser export (background colour, size presets, JPG), a licence summary, usage ideas and ImageObject markup.  Items are grouped in sets
(series), genres and touches; curated landing pages (/special/) cover the seasonal topics; search and favourites run in the browser.
The factory (factory.py) draws new sets from specs; this file only reads the finished library (model.py).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.minna import model, printables, wishes  # noqa: E402
from sites.minna.catalog import CATEGORIES, build_catalog  # noqa: E402
from sites.minna.specials import MIN_ITEMS, SPECIALS  # noqa: E402
from sites.minna.taxonomy import GENRE_BY_SLUG, GENRES, TOUCH_BY_SLUG, TOUCHES  # noqa: E402
from sites.yorokobu import content as gift_content  # noqa: E402
from sokuhou import contactform, rakuten  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

PER_PAGE = 60
MIN_TAG = 12            # a keyword page exists only with at least this many items from at least two sets
MAX_TAG_PAGES = 150
MIN_CROSS = 12          # a genre x touch page exists only with at least this many items
BASE_NAV = [("イラスト", "/illust/", "/illust/"), ("特集", "/special/", "/special/"), ("用途", "/use/", "/use/"), ("読みもの", "/guide/", "/guide/"), ("印刷", "/printables/", "/printables/"), ("つくる", "/tool/", "/tool/"), ("リクエスト", "/request/", "/request/")]
SITE = {
    "nav": list(BASE_NAV),
    "glyph": '<img src="/assets/img/logo-mark.webp" alt="" width="36" height="36">',
    "assets": HERE / "assets",
    "source_html": "個人でも商用でも無料でお使いいただけます。",
}
FONTS = '<meta name="theme-color" content="#2fd09b">\n'      # no Web fonts: the system's Japanese fonts (the Google ones were 122 files, about 1.5 MB, on every page)
USES = {
    "animals": ["LINEやSNSの返信に", "スライドのひとこと解説に", "ブログの吹き出しの横に", "保育園・学校のおたよりに"],
    "eto": ["年賀状・あいさつ状に", "新年のあいさつ画像に", "お店や会社の新年のお知らせに", "保育園・学校の1月のおたよりに"],
    "season": ["季節のお知らせに", "カード・招待状に", "店頭のポップに", "学校・園のおたよりに"],
    "food": ["メニューやレシピに", "給食だよりに", "お店のポップに", "ブログやSNSの画像に"],
    "nature": ["季節のあいさつ状に", "メッセージカードに", "天気や行事のお知らせに", "ブログの見出しに"],
    "life": ["暮らしのお知らせに", "チェックリストや説明資料に", "引っ越し・住まいの案内に", "子ども向けの資料に"],
    "school": ["学級通信・園だよりに", "掲示物やプリントに", "学習カードやワークシートに", "新学期のお知らせに"],
    "work": ["プレゼン資料に", "チラシやサイトに", "社内だよりやマニュアルに", "提案書の図解に"],
    "people": ["自己紹介スライドに", "チームの役割紹介に", "アンケートや診断の選択肢に", "家族のお知らせに"],
    "deco": ["写真や文字を囲むフレームに", "おたよりの見出しに", "SNS画像の飾りに", "プレゼントのカードに"],
    "icon": ["資料の目印や強調に", "チラシ・ポスターの飾りに", "SNS画像のワンポイントに", "ウェブサイトのボタンや見出しに"],
    "shimaenaga": ["LINEやSNSの返信に", "スライドのひとこと解説に", "ブログの吹き出しの横に", "動画のサムネイルに"],
}
GUIDE_BY_GENRE = {"eto": ["nenga-tsukurikata", "nenga-2027-schedule", "kantyu-mimai"], "season": ["christmas-card", "hoiku-otayori"], "school": ["hoiku-otayori", "nurie-insatsu"],
                  "animals": ["line-reply-illust", "tomei-png"], "deco": ["tomei-png", "hoiku-otayori"], "icon": ["tomei-png"], "work": ["shoyo-license", "tomei-png"]}
GUIDE_DEFAULT = ["tomei-png", "shoyo-license"]


def load_guides() -> list[dict]:
    f = HERE / "content" / "guides.json"
    if not f.exists():
        return []
    out = []
    for g in json.loads(f.read_text(encoding="utf-8"))["guides"]:
        for k in ("slug", "title", "description", "lead", "sections"):
            if not g.get(k):
                raise BuildError(f"guides.json: {g.get('slug')} lacks {k}")
        out.append(g)
    return out


def guides_for(genre: str, touch: str, guides: list[dict], n: int = 2) -> list[dict]:
    by = {g["slug"]: g for g in guides}
    want = list(GUIDE_BY_GENRE.get(genre, [])) + (["nurie-insatsu"] if touch == "lineart" else []) + GUIDE_DEFAULT
    out = []
    for slug in want:
        if slug in by and by[slug] not in out:
            out.append(by[slug])
    return out[:n]


def guide_box(guides: list[dict]) -> str:
    if not guides:
        return ""
    return ('<section style="margin-top:44px"><h2><span class="scribble">あわせて読みたい</span></h2><ul class="readlist">'
            + "".join(f'<li><a href="/guide/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["description"])}</span></a></li>' for g in guides) + "</ul></section>")


def guide_page(cfg, preview, g: dict, series: list[dict]) -> str:
    base = cfg["site_url"].rstrip("/")
    secs = ""
    for sec in g["sections"]:
        secs += f'<section class="art"><h2>{esc(sec["h2"])}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in sec.get("paras", []))
        if sec.get("list"):
            secs += "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in sec["list"]) + "</ul>"
        if sec.get("table"):
            t = sec["table"]
            secs += ('<div class="tablewrap"><table><thead><tr>' + "".join(f"<th>{esc(h)}</th>" for h in t["head"]) + "</tr></thead><tbody>"
                     + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in t["rows"]) + "</tbody></table></div>")
        secs += "</section>"
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in g.get("faq", []))
    src = ""
    if g.get("sources"):
        src = ('<section class="art"><h2>参考にした情報</h2><ul>' + "".join(f'<li><a href="{esc(x["url"])}" rel="noopener nofollow" target="_blank">{esc(x["title"])}</a></li>' for x in g["sources"]) + "</ul></section>")
    rel = [s_ for slug in g.get("related_series", []) for s_ in series if s_["slug"] == slug]
    its = [i for s_ in rel for i in s_["items"]][:12]
    illust = (f'<section style="margin-top:36px"><h2><span class="scribble">この記事で使えるイラスト</span></h2>{grid(its)}'
              + "".join(f'<p><a href="{s_["url"]}">「{esc(s_["title"])}」をすべて見る</a></p>' for s_ in rel) + "</section>") if its else ""
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": g["title"], "description": g["description"], "inLanguage": "ja",
                     "datePublished": g.get("date", "2026-10-07"), "dateModified": g.get("date", "2026-10-07"),
                     "author": {"@type": "Organization", "name": cfg["operator_name"]}, "publisher": {"@type": "Organization", "name": cfg["operator_name"]},
                     "mainEntityOfPage": f"{base}/guide/{g['slug']}/"}, ensure_ascii=False)
    faq_ld = ""
    if g.get("faq"):
        faq_json = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in g["faq"]]}, ensure_ascii=False)
        faq_ld = f'<script type="application/ld+json">{faq_json}</script>'
    faq_html = ('<section class="art"><h2>よくある質問</h2><div class="faq">' + faq + '</div></section>') if faq else ""
    body = f"""{crumbs([("トップ", "/"), ("読みもの", "/guide/"), (g["title"], None)])}
<h1>{esc(g['title'])}</h1><p class="lead">{esc(g['lead'])}</p>{licence_box()}
{secs}{illust}
{faq_html}
{src}{pr_box(cfg, *GUIDE_PR[g['slug']]) if g['slug'] in GUIDE_PR else ""}{share(cfg, f"/guide/{g['slug']}/", g['title'])}
<script type="application/ld+json">{ld}</script>{faq_ld}"""
    return page(cfg, preview, path=f"/guide/{g['slug']}/", title=f"{g['title']} | {cfg['site_name']}", description=g["description"][:150], body=body)


def guides_hub(cfg, preview, guides: list[dict]) -> str:
    cards = "".join(f'<li><a href="/guide/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["description"])}</span></a></li>' for g in guides)
    body = f"""{crumbs([("トップ", "/"), ("読みもの", None)])}
<h1>読みもの</h1><p class="lead">年賀状、寒中見舞い、ぬりえ、おたよりなど、イラストを使うときに役立つ解説です。</p><ul class="readlist big">{cards}</ul>"""
    return page(cfg, preview, path="/guide/", title=f"読みもの | {cfg['site_name']}", description="年賀状、寒中見舞い、ぬりえの印刷、保育園のおたより、透明PNGの使い方など、イラストを使うときに役立つ解説。", body=body)




# ------------------------------------------------------------------ derived files (cached by content hash: a rebuild only converts new images)
def cache_dir() -> Path:
    d = Path(os.environ.get("MINNA_CACHE") or ROOT / "out" / "minna_cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cached(path: Path, kind: str, make) -> bytes:
    key = hashlib.sha1(path.read_bytes()).hexdigest()
    f = cache_dir() / f"{key}.{kind}"
    if f.exists():
        return f.read_bytes()
    data = make()
    tmp = f.with_suffix(f.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(f)
    return data


def png_bytes(webp: Path) -> bytes:
    from PIL import Image

    def make():
        buf = io.BytesIO()
        Image.open(webp).convert("RGBA").save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    return _cached(webp, "png", make)


def thumb_bytes(webp: Path, width: int = 360) -> bytes:
    from PIL import Image

    def make():
        im = Image.open(webp).convert("RGBA")
        if im.width > width:
            im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=86, method=4)
        return buf.getvalue()
    return _cached(webp, f"t{width}.webp", make)


PDF_SIZES = {"a4": (1654, 2339, 200.0), "hagaki": (1181, 1748, 300.0)}     # pixels and dpi: A4 and a postcard (100 x 148 mm)


def pdf_kinds(it: dict) -> list[str]:
    """Print versions offered for an item: coloring pages on A4, New Year / frame items on a postcard."""
    kinds = []
    if it["touch"] == "lineart":
        kinds.append("a4")
    if it["genre"] in ("eto", "deco") and it["touch"] != "lineart":
        kinds.append("hagaki")
    return kinds


def pdf_bytes(webp: Path, kind: str) -> bytes:
    """A white page with the picture centred (no text, so no font is needed)."""
    from PIL import Image
    w, h, dpi = PDF_SIZES[kind]

    def make():
        im = Image.open(webp).convert("RGBA")
        page = Image.new("RGB", (w, h), "white")
        sc = min(w * 0.86 / im.width, h * 0.86 / im.height)
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
        page.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
        buf = io.BytesIO()
        page.save(buf, format="PDF", resolution=dpi, quality=88)
        return buf.getvalue()
    return _cached(webp, f"{kind}.pdf", make)


def og_bytes(items: list[dict], bg: tuple[int, int, int]) -> bytes:
    """1200x630 share image: up to four illustrations on a colour."""
    from PIL import Image
    im = Image.new("RGB", (1200, 630), bg)
    pick = items[:4]
    cell = 1200 // max(1, len(pick))
    for i, it in enumerate(pick):
        a = Image.open(it["path"]).convert("RGBA")
        s = min((cell - 40) / a.width, 520 / a.height)
        a = a.resize((max(1, int(a.width * s)), max(1, int(a.height * s))), Image.LANCZOS)
        im.paste(a, (i * cell + (cell - a.width) // 2, 60 + (520 - a.height) // 2), a)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=88)
    return buf.getvalue()


# ------------------------------------------------------------------ data
def load_data(today: date | None = None):
    items, series = model.load_all(gift_content, build_catalog, CATEGORIES)
    by_id = {i["id"]: i for i in items}
    for s in series:
        s["items"] = [by_id[i] for i in s["ids"]]
    return items, series


def load_catalog() -> list[dict]:
    return load_data()[0]


def series_of(item: dict, series: list[dict]) -> dict:
    return next(s for s in series if s["slug"] == item["series"])


def series_use(s: dict) -> str:
    """The sentence of the set's lead that says what it is for ("…に使えます。"), or "" when the lead has none."""
    sents = re.findall(r"[^。]+。", s.get("lead", ""))
    return sents[-1] if len(sents) >= 2 and "使え" in sents[-1] else ""


def is_pose_set(s: dict) -> bool:
    return not s["legacy"] and "ポーズ" in s["title"]


def genre_name(slug: str) -> str:
    return GENRE_BY_SLUG[slug][1]


def touch_name(slug: str) -> str:
    return TOUCH_BY_SLUG[slug][1]


def match_series(patterns: list[str], series: list[dict]) -> list[dict]:
    out = []
    for s in series:
        for p in patterns:
            if (p.endswith("*") and s["slug"].startswith(p[:-1])) or s["slug"] == p:
                out.append(s)
                break
    return out


# ------------------------------------------------------------------ small html helpers
SEARCH_FORM = ('<form class="hsearch" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="探す(例: ひつじ、年賀状)" '
               'aria-label="イラストを探す" autocomplete="off"><button type="submit" aria-label="検索">探す</button></form>')


def tune_images(html: str, eager: int = 5) -> str:
    """Only the first few pictures of a page are fetched at once (the logo and the first cards); every other picture waits until it is near the screen, and none blocks the page while it decodes.
    A special page used to start 8 pictures per heading: 63 pictures, 1.5 MB, before anyone scrolled."""
    n = 0

    def one(m: re.Match) -> str:
        nonlocal n
        tag = m.group(0)
        n += 1
        if "decoding=" not in tag:
            tag = tag[:-1].rstrip("/ ") + ' decoding="async">'
        if n > eager:
            tag = re.sub(r"\sloading=(\"?)eager\1", "", tag)
            if "loading=" not in tag:
                tag = tag[:-1] + ' loading="lazy">'
        return tag
    return re.sub(r"<img\b[^>]*>", one, html)


ASSIST_BUTTON = ('<div id="assist-nudge" class="assist-nudge" hidden><button type="button" class="n-go" data-assist-open>探しているイラストを、案内がお手伝いします</button>'
                 '<button type="button" class="n-x" aria-label="閉じる">×</button></div>'
                 '<button id="assist-open" class="assist-open" type="button" aria-haspopup="dialog" aria-expanded="false" aria-controls="assist-panel" data-src="/assets/assist.js">'
                 '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-8l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>'
                 '<path d="M7 9h10M7 12.5h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg><span class="t">探しものの案内</span></button>')
ASSIST_CHIPS = ["年賀状に使いたい", "印刷したい", "商用で使えますか", "ぬりえを使いたい", "リクエストしたい"]
ASSIST_FAQ = [
    {"k": ["商用", "会社", "広告", "お金をもらう", "仕事で"], "a": "はい。個人でも会社でも、無料で商用利用できます。使う前の連絡も点数制限もありません。", "u": "/license/", "l": "利用について"},
    {"k": ["クレジット", "表記", "著作権表示", "出典"], "a": "クレジット表示は不要です。付ける場合は任意です。", "u": "/license/", "l": "利用について"},
    {"k": ["登録", "ログイン", "会員", "アカウント"], "a": "登録もログインも不要です。ダウンロード回数の制限もありません。", "u": "/license/", "l": "利用について"},
    {"k": ["加工", "色を変", "色変え", "大きさ", "サイズ", "編集", "トリミング"], "a": "色や大きさ、向きを変えたり、文字や他の画像と組み合わせたりできます。各イラストのページでは背景色と大きさを選んで保存できます。", "u": "/guide/tomei-png/", "l": "透明PNGの使い方"},
    {"k": ["ダウンロード", "保存", "やり方", "使い方"], "a": "イラストのページで「PNGでダウンロード」を押すと保存できます。スマホで保存できないときは画像を長押ししてください。", "u": "/guide/tomei-png/", "l": "透明PNGの使い方"},
    {"k": ["透明", "背景", "白い"], "a": "イラストは背景が透明のPNGです。ページの背景ボタンで、色の上に重ねたときの見え方を確認できます。", "u": "/guide/tomei-png/", "l": "透明PNGの使い方"},
    {"k": ["印刷", "プリント", "a4", "はがき", "ハガキ", "pdf"], "a": "各イラストのページに、A4やはがきで印刷できるPDFがあります。ぬりえ、カレンダー、賞状、名札、時間割も印刷できます。", "u": "/printables/", "l": "印刷できるもの"},
    {"k": ["ai", "人工知能", "生成", "エーアイ"], "a": "イラストは生成AIが制作しています。", "u": "/license/", "l": "利用について"},
    {"k": ["スタンプ", "転売", "販売", "売", "商標", "素材集", "再配布"], "a": "イラストそのものを素材集として配布・販売すること、商標登録すること、LINEスタンプなどでそのまま販売することはご遠慮ください。加工して他の作品に使うことは問題ありません。", "u": "/license/", "l": "利用について"},
    {"k": ["無料", "料金", "お金がかかる", "有料"], "a": "ずっと無料です。", "u": "/license/", "l": "利用について"},
    {"k": ["似て", "取り下げ", "削除して", "著作権侵害", "問題がある"], "a": "似ているというご指摘は、お問い合わせからお知らせください。確認し、必要な場合は取り下げます。", "u": "/contact/", "l": "お問い合わせ"},
    {"k": ["ぬりえをし", "塗り絵をし", "色をぬ", "色を塗", "ぬってみ", "オンラインぬりえ"], "a": "ブラウザ上で色を塗れます。絵と色を選び、塗りたい場所をタップします。塗った絵は保存も印刷もできます。", "u": "/tool/nurie/", "l": "オンラインぬりえ"},
    {"k": ["カード", "名前入り", "名入れ", "名前を入れ"], "a": "名前とひとことを入れて、動物のカードを画像で保存できます。入力した内容はこの端末の中だけで使われます。", "u": "/tool/card/", "l": "名前入りカードをつくる"},
    {"k": ["カレンダーを作", "カレンダー作", "カレンダーメーカー", "カレンダーをつく", "月間カレンダー", "祝日つき"], "a": "好きなイラストで、年と月を選んだカレンダーを作れます。祝日入りで、画像として保存でき、そのまま印刷もできます。", "u": "/tool/calendar/", "l": "カレンダーをつくる"},
    {"k": ["名札", "席札", "賞状", "名前入り印刷", "ネームプレート", "ネームタグ"], "a": "名前を入れた名札(A4に8枚)、二つ折りの席札、賞状を作れます。入力した内容はこの端末の中だけで使われます。", "u": "/tool/nametag/", "l": "名前入りの名札・賞状をつくる"},
]


def synonym_groups() -> list[list[str]]:
    """content/synonyms.json (hand-made groups) plus content/demand_synonyms.json (pairs the weekly routine adds): what the search page and the helper treat as one word."""
    groups = [list(g) for g in json.loads((HERE / "content" / "synonyms.json").read_text(encoding="utf-8"))["groups"]]
    extra = HERE / "content" / "demand_synonyms.json"
    if extra.exists():
        groups += [[k, v] for k, v in json.loads(extra.read_text(encoding="utf-8")).items() if not k.startswith("_") and isinstance(v, str)]
    return groups


def assist_data(built, guides, year: int, kinds: dict, use_hubs: list | None = None, has_pose: bool = False) -> dict:
    """data/assist.json: the pages the helper can point to, its short answers and the first buttons."""
    pages = []
    for sp, _sers, _its in built:
        pages.append({"u": f"/special/{sp['slug']}/", "n": sp["name"], "k": [sp["title"]], "t": "特集"})
    for g in guides:
        pages.append({"u": f"/guide/{g['slug']}/", "n": g["title"], "k": [g.get("description", "")[:60]], "t": "読みもの"})
    pages.append({"u": "/printables/", "n": "印刷できるもの(ぬりえ・カレンダー・賞状・名札・時間割)", "k": ["印刷", "プリント", "a4", "ぬりえ", "カレンダー", "賞状", "名札", "時間割"], "t": "印刷"})
    pages.append({"u": f"/printables/calendar-{year}/", "n": f"{year}年のイラストカレンダー", "k": ["カレンダー", "月間", "年間", "印刷"], "t": "印刷"})
    for kind in kinds:
        pages.append({"u": f"/printables/{kind}/", "n": PRINT_COPY[kind][1], "k": [PRINT_COPY[kind][0]], "t": "印刷"})
    pages.append({"u": "/tool/nurie/", "n": "オンラインぬりえ(ブラウザで色を塗る)", "k": ["ぬりえ", "塗り絵", "色を塗る", "オンライン", "保存", "印刷"], "t": "ツール"})
    for h in use_hubs or []:
        pages.append({"u": f"/use/{h['slug']}/", "n": f"{h['name']}に使えるイラスト", "k": h["words"][:8], "t": "用途"})
    if has_pose:
        pages.append({"u": "/pose/", "n": "ポーズ集(動物・人物のポーズ違いのイラスト)", "k": ["ポーズ", "表情", "差分", "動物", "いろいろ", "立つ", "座る"], "t": "ポーズ"})
    pages.append({"u": "/tool/", "n": "つくる(カード・カレンダー・名札・賞状・ぬりえ)", "k": ["つくる", "作る", "ツール", "メーカー", "カレンダー", "名札", "席札", "賞状", "カード", "ぬりえ"], "t": "ツール"})
    pages.append({"u": "/tool/calendar/", "n": "カレンダーをつくる(イラスト入り・祝日つき)", "k": ["カレンダー", "月間", "祝日", "印刷", "壁掛け", "メーカー"], "t": "ツール"})
    pages.append({"u": "/tool/nametag/", "n": "名前入りの名札・席札・賞状をつくる", "k": ["名札", "ネームプレート", "席札", "賞状", "名前入り", "印刷", "ネームタグ"], "t": "ツール"})
    pages.append({"u": "/tool/card/", "n": "名前入りカードをつくる", "k": ["カード", "名前入り", "誕生日", "ありがとう", "おめでとう", "あけおめ"], "t": "ツール"})
    pages.append({"u": "/request/", "n": "イラストのリクエスト", "k": ["リクエスト", "欲しい", "描いて", "ない"], "t": "リクエスト"})
    pages.append({"u": "/new/", "n": "新着のセット", "k": ["新着", "新しい", "最近"], "t": "新着"})
    return {"v": 1, "pages": pages, "faq": ASSIST_FAQ, "chips": ASSIST_CHIPS, "touches": {t[0]: t[1] for t in TOUCHES}}


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    html = layout(SITE, cfg, preview, scripts=True, head_extra=FONTS, **kw)
    html = html.replace('<nav aria-label="メイン">', SEARCH_FORM + '<nav aria-label="メイン">', 1)
    return tune_images(html.replace("</body>", ASSIST_BUTTON + "</body>", 1))


def card(it: dict, lazy: bool = True) -> str:
    tw = min(it["w"], 360)
    return (f'<li class="ic"><a class="illust-card" href="/illust/{it["id"]}/"><span class="checker"><img src="/thumbs/{it["id"]}.webp" alt="{esc(it["title"])}" '
            f'width="{tw}" height="{round(it["h"] * tw / it["w"])}"{" loading=lazy" if lazy else ""}></span><b>{esc(it["title"])}</b></a>'
            f'<button class="fav" type="button" data-fav="{it["id"]}" aria-pressed="false" aria-label="お気に入りに入れる">♡</button></li>')


def grid(items: list[dict], live: bool = False) -> str:
    return '<ul class="illust-grid">' + "".join(card(i, lazy=n > 7) for n, i in enumerate(items)) + "</ul>"


def series_card(s: dict) -> str:
    thumbs = "".join(f'<img src="/thumbs/{i["id"]}.webp" alt="" width="120" height="{round(i["h"] * 120 / i["w"])}" loading="lazy">' for i in s["items"][:3])
    return (f'<li><a class="set-card" href="{s["url"]}"><span class="set-thumbs checker">{thumbs}</span><b>{esc(s["title"])}</b>'
            f'<small>{len(s["items"])}点 ・ {esc(touch_name(s["touch"]))}</small></a></li>')


def set_grid(series: list[dict]) -> str:
    return '<ul class="set-grid">' + "".join(series_card(s) for s in series) + "</ul>"


def share(cfg: dict, path: str, text: str) -> str:
    url = cfg["site_url"].rstrip("/") + path
    return (f'<div class="share"><span class="share-label">このページを共有する</span>'
            f'<a class="share-btn line" href="{esc("https://line.me/R/share?text=" + quote(text + chr(10) + url, safe=""))}" target="_blank" rel="noopener">LINEで送る</a>'
            f'<a class="share-btn x" href="{esc("https://twitter.com/intent/tweet?text=" + quote(text, safe="") + "&url=" + quote(url, safe=""))}" target="_blank" rel="noopener">Xで共有</a></div>')


def licence_box() -> str:
    return ('<aside class="licence-box"><b>ずっと無料・商用OK・クレジット不要・登録不要</b><span>個人でも会社でも、点数の制限なく使えます。'
            '加工(色や大きさを変える)もできます。詳しくは<a href="/license/">利用について</a>。</span></aside>')


def pager_html(base: str, page_no: int, pages: int) -> str:
    if pages <= 1:
        return ""

    def href(n):
        return base if n == 1 else f"{base}page/{n}/"
    parts = []
    if page_no > 1:
        parts.append(f'<a rel="prev" href="{href(page_no - 1)}">前へ</a>')
    for n in range(1, pages + 1):
        if n == page_no:
            parts.append(f'<span aria-current="page">{n}</span>')
        elif n in (1, pages) or abs(n - page_no) <= 2:
            parts.append(f'<a href="{href(n)}">{n}</a>')
        elif abs(n - page_no) == 3:
            parts.append("<span>…</span>")
    if page_no < pages:
        parts.append(f'<a rel="next" href="{href(page_no + 1)}">次へ</a>')
    return '<nav class="pager" aria-label="ページ送り">' + "".join(parts) + "</nav>"


def paged(cfg, preview, base: str, items: list[dict], head_html: str, title: str, description: str, crumb_items, extra_top: str = "", extra_bottom: str = "",
          og_image: str | None = None) -> dict[str, str]:
    """A listing split into pages of PER_PAGE: {relative file: html}."""
    pages = max(1, -(-len(items) // PER_PAGE))
    out = {}
    for n in range(1, pages + 1):
        chunk = items[(n - 1) * PER_PAGE:n * PER_PAGE]
        path = base if n == 1 else f"{base}page/{n}/"
        t = title if n == 1 else f"{title}(ページ{n})"
        top = extra_top if n == 1 else ""
        body = (f'{crumbs(crumb_items if n == 1 else crumb_items[:-1] + [(crumb_items[-1][0], base)] + [(f"ページ{n}", None)])}\n{head_html if n == 1 else f"<h1>{esc(crumb_items[-1][0])}(ページ{n})</h1>"}'
                f'{top}{grid(chunk)}{pager_html(base, n, pages)}{extra_bottom if n == pages else ""}')
        kw = {"og_image": og_image} if og_image else {}
        out[f"{path.strip('/')}/index.html" if path != "/" else "index.html"] = page(cfg, preview, path=path, title=t, description=description, body=body, **kw)
    return out


# ------------------------------------------------------------------ printable calendars
CAL_THEMES = [
    ("hitsuji", "ひつじ", "2027年の干支(未年)にちなんだ、ひつじのカレンダーです。",
     ["eto-sheep-kawaii-kagami", "sheep-pose-heart", "sheep-pose-thanks", "sheep-pose-wave", "sheep-pose-eat", "sheep-pose-sad", "sheep-pose-cheer", "sheep-pose-run",
      "sheep-pose-surprised", "sheep-pose-wink", "sheep-pose-sleep", "christmas-animals-kawaii-sheep"]),
    ("dobutsu", "動物", "毎月異なる動物を使った、12か月のカレンダーです。",
     ["eto-lineup-kawaii-sheep", "cat-pose-heart", "rabbit-pose-wave", "bear-pose-wave", "dog-pose-jump", "frog-pose-wave", "penguin-pose-wave", "hamster-pose-eat",
      "panda-pose-wave", "fox-pose-proud", "koala-pose-wave", "christmas-animals-kawaii-bear"]),
]


def fill_with_animals(picks: list[dict], items: list[dict], n: int = 12) -> list[dict]:
    """Animals not drawn yet: other animal sets fill the gaps, one picture per set."""
    picks = list(picks)
    used = {i["series"] for i in picks}
    for it in items:
        if len(picks) >= n:
            break
        if it["series"].endswith("-pose") and it["series"] not in used and it["id"].rsplit("-", 1)[-1] in ("wave", "heart", "jump", "thanks"):
            picks.append(it)
            used.add(it["series"])
    return picks


PRINT_COPY = {
    "shojo": ("賞状テンプレート かわいい動物 無料・A4印刷", "動物の賞状", "子どもに渡す賞状を、A4に印刷して使えるテンプレートです。名前・日付・贈る人を手で書き入れます。",
              [("文字を入れられますか?", "手書きで書き入れる形です。名前の線、日付、「より」の線が空いています。"), ("どの大きさで印刷しますか?", "A4(横)です。プリンターの設定は「実際のサイズ」で、厚めの紙だと立派に仕上がります。")]),
    "nafuda": ("名札テンプレート かわいい動物 無料・A4印刷", "動物の名札", "切り取って使える名札です。1ページに10枚。名前を手書きして、ラミネートしたり、安全ピンやクリップを付けたりして使えます。",
               [("何枚つくれますか?", "1ページに10枚です。同じ絵が10枚並びます。"), ("名前は書けますか?", "各名札に、名前を書く線があります。ペンで書き入れてください。")]),
    "jikanwari": ("時間割テンプレート かわいい動物 無料・A4印刷", "動物の時間割", "月曜から金曜、1〜6時間目の時間割表です。教科を手書きして、机に貼ったり、ファイルに入れたりして使えます。",
                  [("6時間目までですか?", "はい。1〜6時間目の表です。使わない時間は空欄のまま使えます。"), ("どの大きさで印刷しますか?", "A4(横)です。プリンターの設定で「実際のサイズ」を選んでください。")]),
}


def build_printables(items: list[dict]) -> tuple[dict, dict]:
    """({file: bytes}, {kind: [{slug, name, pdf, img}]}) for certificates, name tags and timetables; empty without a Japanese font."""
    font = printables.find_font()
    if not font:
        return {}, {}
    by = {i["id"]: i for i in items}
    ids = next(t[3] for t in CAL_THEMES if t[0] == "dobutsu")
    picks = fill_with_animals([by[i] for i in ids if i in by], items)
    if len(picks) < 6:
        return {}, {}
    fkey = hashlib.sha1(Path(font).name.encode()).hexdigest()[:6]
    files, kinds = {}, {}
    for kind in printables.PRINTABLE_KINDS:
        rows = []
        for it in picks:
            slug = it["series"].replace("-pose", "")
            rel = f"printables/{kind}-{slug}"
            files[f"files/{rel}.pdf"] = _cached(it["path"], f"{kind}-{fkey}.pdf", lambda it=it, kind=kind: printables.printable_pdf(kind, it["path"], font))
            files[f"files/{rel}.webp"] = _cached(it["path"], f"{kind}-{fkey}.webp", lambda it=it, kind=kind: printables.printable_preview(kind, it["path"], font))
            rows.append({"slug": slug, "name": it["title"].replace("(", " ").split(" ")[0] if False else it["series"], "title": it["title"], "pdf": f"/files/{rel}.pdf", "img": f"/files/{rel}.webp", "item": it})
        kinds[kind] = rows
    return files, kinds


def printable_page(cfg, preview, kind: str, rows: list[dict]) -> str:
    title, h1, intro, faq = PRINT_COPY[kind]
    landscape = kind != "nafuda"
    w, h = (480, 340) if landscape else (480, 679)
    cards = "".join(f'<li><a class="cal-card" href="{r["pdf"]}" download><img src="{r["img"]}" alt="{esc(h1)}({esc(r["title"])})" width="{w}" height="{h}" loading="lazy"><b>{esc(r["title"])}</b><small>A4・PDF</small></a></li>' for r in rows)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("印刷", "/printables/"), (h1, None)])}
<h1>{esc(title)}</h1><p class="lead">{esc(intro)}</p>{licence_box()}
<ul class="cal-grid wide">{cards}</ul>
<section style="margin-top:44px"><h2><span class="scribble">よくある質問</span></h2><div class="faq">{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)}</div></section>
{pr_box(cfg, *PRINTABLE_PR[kind])}
{share(cfg, f"/printables/{kind}/", title)}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/printables/{kind}/", title=f"{title} | {cfg['site_name']}", description=intro[:120] + "無料・商用OK・登録不要。", body=body, og_image=rows[0]["img"])


def calendar_year(today: date) -> int:
    """The year people are looking for: next year from September on, this year before."""
    return today.year + 1 if today.month >= 9 else today.year


def build_calendars(items: list[dict], today: date) -> tuple[dict, list[dict]]:
    """({file: bytes}, [theme dict]) - empty when no Japanese font is installed (the page is then not built, nothing half-made is shipped)."""
    font = printables.find_font()
    if not font:
        return {}, []
    by = {i["id"]: i for i in items}
    year = calendar_year(today)
    files: dict = {}
    themes = []
    fkey = hashlib.sha1(Path(font).name.encode()).hexdigest()[:6]
    for slug, name, desc, ids in CAL_THEMES:
        picks = [by[i] for i in ids if i in by]
        if slug == "dobutsu":
            picks = fill_with_animals(picks, items)
        if len(picks) < 12:
            continue
        months = []
        pdfs = []
        for m, it in enumerate(picks, 1):
            rel = f"calendar/{year}-{slug}-{m:02d}"
            pdf = _cached(it["path"], f"cal{year}-{m:02d}-{fkey}.pdf", lambda it=it, m=m: printables.month_pdf(it["path"], year, m, font))
            prev = _cached(it["path"], f"cal{year}-{m:02d}-{fkey}.webp", lambda it=it, m=m: _small_webp(printables.month_page(it["path"], year, m, font)))
            files[f"files/{rel}.pdf"] = pdf
            files[f"files/{rel}.webp"] = prev
            months.append({"m": m, "pdf": f"/files/{rel}.pdf", "img": f"/files/{rel}.webp", "title": it["title"]})
            pdfs.append(it["path"])
        allkey = hashlib.sha1(("".join(hashlib.sha1(x.read_bytes()).hexdigest() for x in pdfs) + f"{year}{fkey}").encode()).hexdigest()
        allf = cache_dir() / f"{allkey}.calpack.pdf"
        if not allf.exists():
            allf.write_bytes(printables.year_pdf(pdfs, year, font))
        files[f"files/calendar/{year}-{slug}-all.pdf"] = allf.read_bytes()
        themes.append({"slug": slug, "name": name, "desc": desc, "months": months, "all": f"/files/calendar/{year}-{slug}-all.pdf"})
    return files, themes


def _small_webp(page) -> bytes:
    im = page.resize((360, round(page.height * 360 / page.width)))
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=82)
    return buf.getvalue()


def calendar_page(cfg, preview, themes: list[dict], year: int, guides) -> str:
    base = cfg["site_url"].rstrip("/")
    secs = ""
    for t in themes:
        cards = "".join(f'<li><a class="cal-card" href="{m["pdf"]}" download><img src="{m["img"]}" alt="{year}年{m["m"]}月のカレンダー({esc(t["name"])})" width="360" height="509" loading="lazy">'
                        f'<b>{m["m"]}月</b><small>A4・PDF</small></a></li>' for m in t["months"])
        secs += (f'<section style="margin-top:36px"><h2><span class="scribble">{esc(t["name"])}のカレンダー</span></h2><p class="lead">{esc(t["desc"])}</p>'
                 f'<p class="dl"><a class="btn big" href="{t["all"]}" download>12か月まとめてPDF</a></p><ul class="cal-grid">{cards}</ul></section>')
    faq = [("祝日は入っていますか?", f"はい。{year}年の祝日(振替休日を含む)を赤い字で入れています。"),
           ("どの大きさで印刷しますか?", "A4(縦)で作っています。プリンターの設定で「実際のサイズ」または「拡大縮小なし」を選ぶと、きれいに印刷できます。"),
           ("商用で使えますか?", "はい。無料・商用OKです。お店や会社で配るカレンダーにもお使いいただけます(PDFそのものの再配布や販売はご遠慮ください)。")]
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("印刷", "/printables/"), (f"{year}年カレンダー", None)])}
<h1>{year}年(令和{year - 2018}年)イラストカレンダー 無料・A4で印刷できるPDF</h1>
<p class="lead">かわいいイラスト付きの{year}年カレンダーです。1か月ずつ、または12か月まとめて無料でダウンロードできます。祝日付き・A4縦・登録不要。</p>{licence_box()}
{secs}
<section style="margin-top:44px"><h2><span class="scribble">よくある質問</span></h2><div class="faq">{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)}</div></section>
{pr_box(cfg, *PRINTABLE_PR["calendar"])}
{share(cfg, f"/printables/calendar-{year}/", f"{year}年イラストカレンダー(無料・印刷用PDF)")}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/printables/calendar-{year}/", title=f"{year}年 イラストカレンダー 無料・印刷用PDF(A4・祝日つき) | {cfg['site_name']}",
                description=f"{year}年(令和{year - 2018}年)のかわいいイラストカレンダー。A4・祝日付き・登録不要で無料ダウンロード。ひつじ、動物の2種類。商用OK。", body=body,
                og_image=f"/files/calendar/{year}-{themes[0]['slug']}-01.webp")


def printables_hub(cfg, preview, year: int, themes: list[dict], items: list[dict], kinds: dict | None = None) -> str:
    nurie = [i for i in items if i["touch"] == "lineart"]
    cards = (f'<li><a class="special-card" href="/printables/calendar-{year}/"><span class="set-thumbs checker">'
             + "".join(f'<img src="{m["img"]}" alt="" width="120" height="170" loading="lazy">' for m in themes[0]["months"][:3])
             + f'</span><b>{year}年 イラストカレンダー</b><small>A4・祝日付き・{len(themes)}種類</small></a></li>')
    if nurie:
        cards += (f'<li><a class="special-card" href="/special/nurie/"><span class="set-thumbs checker">'
                  + "".join(f'<img src="/thumbs/{i["id"]}.webp" alt="" width="120" height="{round(i["h"] * 120 / i["w"])}" loading="lazy">' for i in nurie[:3])
                  + f'</span><b>ぬりえ(A4で印刷)</b><small>{len(nurie)}点・動物・お正月</small></a></li>')
    for kind, rows in (kinds or {}).items():
        cards += (f'<li><a class="special-card" href="/printables/{kind}/"><span class="set-thumbs checker">'
                  + "".join(f'<img src="{r["img"]}" alt="" width="120" height="85" loading="lazy">' for r in rows[:3])
                  + f'</span><b>{esc(PRINT_COPY[kind][1])}</b><small>A4・{len(rows)}種類</small></a></li>')
    body = f"""{crumbs([("トップ", "/"), ("印刷", None)])}
<h1>印刷できるもの</h1><p class="lead">カレンダー、ぬりえ、はがきサイズの年賀状イラストなど、印刷して使えるものを集めました。すべて無料・商用OK・登録不要です。</p>
<ul class="special-grid">{cards}</ul>
<p>イラストのページには、「A4で印刷(PDF)」「はがきサイズで印刷(PDF)」のボタンがあるものもあります。</p>"""
    return page(cfg, preview, path="/printables/", title=f"印刷できる素材(カレンダー・ぬりえ・はがき) | {cfg['site_name']}",
                description="2027年イラストカレンダー、ぬりえ、はがきサイズの年賀状イラストなど、印刷して使える素材。無料・商用OK・登録不要。", body=body)


# ------------------------------------------------------------------ affiliate boxes (only when the owner's ids are in config.json; always marked as advertising)
GUIDE_PR = {
    "nenga-tsukurikata": ("年賀状作りにあると便利なもの", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("年賀状向けのプリンター用紙", "年賀状 プリンター用紙"), ("プリンターのインク", "プリンター インク 純正")]),
    "nenga-2027-schedule": ("年賀状の準備に", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("宛名ラベル", "年賀状 宛名 ラベル"), ("スタンプ・はんこ", "年賀状 スタンプ 干支")]),
    "nenga-bunrei": ("年賀状にひとこと添えるなら", [("年賀状用のペン", "年賀状 ペン 筆ペン"), ("スタンプ・はんこ", "年賀状 スタンプ 干支")]),
    "kantyu-mimai": ("寒中見舞いの準備に", [("寒中見舞いはがき", "寒中見舞い はがき 印刷"), ("筆ペン", "筆ペン 薄墨")]),
    "nenga-jimai": ("あいさつ状の準備に", [("あいさつ状の印刷", "年賀状じまい 印刷"), ("ペン・万年筆", "万年筆 はがき")]),
    "nurie-insatsu": ("ぬりえを楽しむ道具", [("色えんぴつ", "色えんぴつ 24色"), ("クレヨン", "クレヨン 幼児 安全"), ("ぬりえの本", "ぬりえ 本")]),
    "hoiku-otayori": ("おたよりづくりに", [("ラミネートフィルム", "ラミネートフィルム A4"), ("カラーペン", "カラーペン 水性 12色"), ("A4の厚手用紙", "A4 用紙 厚手 カラー")]),
    "tomei-png": ("イラストを印刷して使うなら", [("A4の厚手用紙", "A4 用紙 厚手"), ("ラミネートフィルム", "ラミネートフィルム A4"), ("写真用紙", "写真用紙 A4 光沢")]),
    "christmas-card": ("クリスマスカードづくりに", [("カード用の厚紙", "メッセージカード 用紙 A4"), ("封筒", "封筒 カード用"), ("シール・スタンプ", "クリスマス シール")]),
    "oseibo-orei-jo": ("お礼状の準備に", [("便せん・封筒", "便せん 封筒 縦書き"), ("筆ペン", "筆ペン 黒"), ("はがき用の切手", "切手 シート")]),
    "shichigosan-guide": ("七五三の準備に", [("千歳飴の袋", "千歳飴 袋"), ("写真用紙", "写真用紙 A4 光沢"), ("フォトフレーム", "フォトフレーム A4")]),
    "eto-ichiran": ("干支のグッズ", [("干支の置物", "干支 置物 2027 未"), ("来年の手帳", "手帳 2027")]),
}
SPECIAL_PR = {
    "nenga-2027": ("年賀状作りにあると便利なもの", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("プリンターのインク", "プリンター インク 純正"), ("年賀状向けのプリンター用紙", "年賀状 プリンター用紙")]),
    "nurie": ("ぬりえを楽しむ道具", [("色えんぴつ", "色えんぴつ 24色"), ("クレヨン", "クレヨン 幼児 安全"), ("ぬりえの本", "ぬりえ 本")]),
    "christmas": ("クリスマスの準備に", [("クリスマスカード用紙", "メッセージカード 用紙 A4"), ("ラッピング用品", "ラッピング 袋 クリスマス")]),
}
PRINTABLE_PR = {
    "calendar": ("カレンダーをきれいに使うために", [("A4の厚手用紙", "A4 用紙 厚手 カラー"), ("ラミネートフィルム", "ラミネートフィルム A4"), ("カレンダー用フレーム", "A4 フォトフレーム 壁掛け")]),
    "shojo": ("賞状をきれいに仕上げるために", [("賞状用紙", "賞状用紙 A4"), ("賞状ホルダー・額", "賞状 額縁 A4"), ("A4の厚手用紙", "A4 用紙 厚手 カラー")]),
    "nafuda": ("名札を丈夫にするために", [("名札ケース", "名札ケース 安全ピン"), ("ラミネートフィルム", "ラミネートフィルム 名刺サイズ"), ("ストラップ", "ネームホルダー ストラップ")]),
    "jikanwari": ("時間割を長く使うために", [("ラミネートフィルム", "ラミネートフィルム A4"), ("下敷き", "下敷き 学習"), ("クリアファイル", "クリアファイル A4")]),
}


def affiliates_on(cfg: dict) -> bool:
    return bool(cfg.get("rakuten_affiliate_id") or cfg.get("amazon_tracking_id"))


def pr_box(cfg: dict, heading: str, rows: list[tuple[str, str]]) -> str:
    """A small 'things that help' box with search links to Rakuten Ichiba and Amazon; empty when no affiliate id is configured."""
    if not affiliates_on(cfg) or not rows:
        return ""
    items = ""
    for label, kw in rows:
        links = ""
        if cfg.get("rakuten_affiliate_id"):
            url = rakuten.affiliate_link(cfg["rakuten_affiliate_id"], cfg.get("rakuten_tracking_id"), rakuten.search_url(kw))
            links += f'<a class="btn btn-sub" href="{esc(url)}" rel="sponsored noopener nofollow" target="_blank">楽天市場で見る</a>'
        if cfg.get("amazon_tracking_id"):
            url = f"https://www.amazon.co.jp/s?k={quote(kw, safe='')}&tag={quote(cfg['amazon_tracking_id'], safe='')}"
            links += f'<a class="btn btn-sub" href="{esc(url)}" rel="sponsored noopener nofollow" target="_blank">Amazonで見る</a>'
        items += f'<li><b>{esc(label)}</b><span>{links}</span></li>'
    note = ("このボックスには、広告(" + "・".join(x for x in ("楽天アフィリエイト" if cfg.get("rakuten_affiliate_id") else "", "Amazonアソシエイト" if cfg.get("amazon_tracking_id") else "") if x)
            + ")のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。")
    amazon = f"<br>Amazonのアソシエイトとして、{esc(cfg['site_name'])}は適格販売により収入を得ています。" if cfg.get("amazon_tracking_id") else ""
    return (f'<aside class="pr-box"><h2><span class="pr-note">PR</span>{esc(heading)}</h2><ul>{items}</ul><p class="pr-small">{esc(note)}{amazon}</p></aside>')


# ------------------------------------------------------------------ pages
def hero_collage(items: list[dict]) -> str:
    # one picture per touch (watercolour, Japanese, realistic, duotone, flat line, picture book): shows the range of the library, not one cute character
    want = ["cafe-drinks-watercolor-coffee", "japan-sights-wa-fuji", "realistic-animals-pets-dog", "telework-duotone-01-sitting-cross-legged",
            "gender-free-workers-civil-engineer", "camping-picturebook-tent"]
    by = {i["id"]: i for i in items}
    chosen = [by[w] for w in want if w in by][:6]
    if len(chosen) < 6:
        chosen += [i for i in items if i not in chosen][: 6 - len(chosen)]
    return "".join(f'<img class="hc" src="/thumbs/{c["id"]}.webp" alt="{esc(c["title"])}" width="{min(c["w"], 360)}" height="{round(c["h"] * min(c["w"], 360) / c["w"])}">'
                   for c in chosen)


def index_page(cfg: dict, preview: bool, items: list[dict], series: list[dict], today: date, printable_thumbs: list[str] | None = None, use_hubs: list[dict] | None = None, has_pose: bool = False) -> str:
    genres_present = [g for g in GENRES if any(i["genre"] == g[0] for i in items)]
    gtiles = ""
    for slug, name, desc, _ in genres_present:
        its = [i for i in items if i["genre"] == slug]
        rep = its[0]
        gtiles += (f'<li><a class="genre-tile" href="/genre/{slug}/"><span class="checker small"><img src="/thumbs/{rep["id"]}.webp" alt="" width="140" height="{round(rep["h"] * 140 / rep["w"])}" loading="lazy"></span>'
                   f'<span><b>{esc(name)}</b><small>{len(its)}点</small></span></a></li>')
    touches_present = [t for t in TOUCHES if any(i["touch"] == t[0] for i in items)]
    ttiles = "".join(f'<li><a class="touch-pill" href="/touch/{t[0]}/"><b>{esc(t[1])}</b><small>{esc(t[2])}</small></a></li>' for t in touches_present)
    seasonal = [sp for sp in specials_in_season(items, series, today)]
    season_html = ""
    if seasonal:
        cards = ""
        for sp, sers, its in seasonal[:3]:
            cards += (f'<li><a class="special-card" href="/special/{sp["slug"]}/"><span class="set-thumbs checker">'
                      + "".join(f'<img src="/thumbs/{i["id"]}.webp" alt="" width="120" height="{round(i["h"] * 120 / i["w"])}" loading="lazy">' for i in its[:3])
                      + f'</span><b>{esc(sp["name"])}</b><small>{len(its)}点そろっています</small></a></li>')
        season_html = f'<section style="margin-top:44px"><div class="sec-head"><h2>今使える<span class="scribble">特集</span></h2><p>季節の行事にすぐ使えるイラストです。</p></div><ul class="special-grid">{cards}</ul></section>'
    newest = sorted(series, key=lambda s: (s["added"], s["slug"]), reverse=True)
    newest = [s for s in newest if not s["legacy"]][:8] or newest[:8]
    use_html = ""
    if use_hubs:
        use_html = ('<section style="margin-top:44px"><div class="sec-head"><h2>用途から<span class="scribble">探す</span></h2><p>使う場面ごとに、イラストをまとめました。</p></div><nav class="chips">'
                    + "".join(f'<a href="/use/{h["slug"]}/">{esc(h["name"])}</a>' for h in use_hubs) + ('<a href="/pose/">ポーズ集</a>' if has_pose else "") + "</nav></section>")
    print_html = ""
    if printable_thumbs:
        thumbs = "".join(f'<img src="{t}" alt="" width="110" height="156" loading="lazy">' for t in printable_thumbs[:4])
        print_html = (f'<section style="margin-top:50px"><div class="sec-head"><h2>印刷して<span class="scribble">使う</span></h2><p>カレンダー、ぬりえ、賞状、名札、時間割。A4で印刷できます。</p></div>'
                      f'<a class="print-banner" href="/printables/"><span class="print-thumbs">{thumbs}</span><b>印刷できるもの(無料・A4)</b><small>{calendar_year(today)}年のカレンダー(祝日つき)・ぬりえ・賞状・名札・時間割</small></a></section>')
    body = f"""<section class="band mint dots hero"><div class="in"><div class="hero-text"><span class="sticker">ずっと無料・商用OK・登録不要</span>
<h1><span class="nb">すぐに使える</span><br><span class="nb"><em>商用OK</em>のイラスト素材</span></h1>
<p class="lead">動物・年賀状・行事・食べ物・フレームまで、{len(items)}点。ダウンロードしてすぐに使えます。クレジット表示も点数制限もありません。</p>
<form class="hero-search" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="ひつじ、年賀状、クリスマス、ぬりえ…" aria-label="イラストを探す" autocomplete="off"><button class="btn" type="submit">探す</button></form>
<p class="hero-cta"><a class="btn big" href="/illust/">イラストを見る</a><a class="btn big btn-sub" href="/tool/card/">カードをつくる</a></p>
<p class="hero-help">探しているものが決まっていない場合は <button type="button" class="linkbtn" data-assist-open>案内に相談する</button></p></div>
<div class="hero-art collage">{hero_collage(items)}</div></div></section>
{licence_box()}
{season_html}
{use_html}
<section style="margin-top:44px"><div class="sec-head"><h2>ジャンルから<span class="scribble">探す</span></h2></div><ul class="genre-grid">{gtiles}</ul></section>
{print_html}
<section style="margin-top:50px"><div class="sec-head"><h2>新しい<span class="scribble">セット</span></h2><p>同じキャラクター・同じタッチで揃っています。</p></div>{set_grid(newest)}
<p style="text-align:center"><a class="btn" href="/new/">新着をもっと見る</a></p></section>
<section style="margin-top:50px"><div class="sec-head"><h2>タッチから<span class="scribble">選ぶ</span></h2><p>同じ絵でもタッチが違うと、雰囲気が変わります。</p></div><ul class="touch-grid">{ttiles}</ul></section>
<section class="band yellow dots scallop" style="margin-top:56px"><div class="in"><div class="sec-head"><h2>名前やひとことを入れて<span class="scribble">カードにする</span></h2><p>お祝いのカードを作って画像で保存できます。</p></div>
<p style="text-align:center"><a class="btn big" href="/tool/card/">カードをつくる</a></p></div></section>
<section style="margin-top:50px"><div class="sec-head"><h2>みんなのイラストの<span class="scribble">特徴</span></h2></div>
<ul class="promise"><li><b>登録なし</b><span>ログインも会員登録も不要です。</span></li><li><b>制限なし</b><span>ダウンロード回数も利用点数も自由です。</span></li><li><b>商用OK</b><span>会社のチラシやお店のポップにも使えます。</span></li><li><b>加工OK</b><span>色や大きさを変えて使えます。</span></li></ul></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} 商用OK・クレジット不要・登録不要の、かわいいイラスト素材",
                description="動物、年賀状(2027年・未年)、季節の行事、食べ物、フレームまで。無料・商用OK・登録不要のかわいい透明PNGイラスト素材。名前入りのカードも作れます。", body=body)


def specials_in_season(items, series, today):
    out = []
    for sp in SPECIALS:
        sers = match_series(sp["match_series"], series)
        its = [i for s in sers for i in s["items"]]
        if len(its) >= MIN_ITEMS and model.in_season(sp["season"], today):
            out.append((sp, sers, its))
    return out


def illust_hub(cfg, preview, items, series) -> dict:
    chips = "".join(f'<a href="/genre/{g[0]}/">{esc(g[1])}</a>' for g in GENRES if any(i["genre"] == g[0] for i in items))
    tchips = "".join(f'<a href="/touch/{t[0]}/">{esc(t[1])}</a>' for t in TOUCHES if any(i["touch"] == t[0] for i in items))
    head = (f'<h1>イラスト一覧</h1><p class="lead">すべて無料、商用OK、クレジット不要です。全{len(items)}点。ジャンルやタッチで絞り込めます。</p>'
            f'<p class="chip-label">ジャンル</p><nav class="chips">{chips}</nav><p class="chip-label">タッチ</p><nav class="chips">{tchips}</nav>')
    ordered = sorted(items, key=lambda i: (i["added"], i["id"]), reverse=True)
    return paged(cfg, preview, "/illust/", ordered, head, f"イラスト一覧 | {cfg['site_name']}",
                 "動物、年賀状、季節の行事、食べ物、フレームなど、すべてのイラストの一覧です。無料・商用OK・登録不要。", [("トップ", "/"), ("イラスト", None)])


def genre_pages(cfg, preview, items, series) -> dict:
    out = {}
    for slug, name, desc, kw in GENRES:
        its = [i for i in items if i["genre"] == slug]
        if not its:
            continue
        sers = [s for s in series if s["genre"] == slug]
        touches = [(t, [i for i in its if i["touch"] == t[0]]) for t in TOUCHES]
        touches = [(t, ts) for t, ts in touches if ts]
        chips = "".join((f'<a href="/genre/{slug}/{t[0]}/">{esc(t[1])}({len(ts)})</a>' if len(ts) >= MIN_CROSS else f'<span>{esc(t[1])}({len(ts)})</span>') for t, ts in touches)
        head = (f'<h1>{esc(name)}のイラスト</h1><p class="lead">{esc(desc)}無料・商用OK・クレジット不要。全{len(its)}点。</p>{licence_box()}'
                f'<p class="chip-label">タッチ</p><nav class="chips">{chips}</nav>')
        top = f'<section><h2><span class="scribble">セットで探す</span></h2>{set_grid(sers)}</section><h2 style="margin-top:36px"><span class="scribble">すべてのイラスト</span></h2>'
        out.update(paged(cfg, preview, f"/genre/{slug}/", sorted(its, key=lambda i: (i["added"], i["id"]), reverse=True), head, f"{name}のイラスト 無料・商用OK | {cfg['site_name']}",
                         f"{desc}無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, None)], extra_top=top))
        for t, ts in touches:
            if len(ts) < MIN_CROSS:
                continue
            h = (f'<h1>{esc(name)}の{esc(t[1])}イラスト</h1><p class="lead">{esc(t[2])}{esc(name)}のイラストを{esc(t[1])}のタッチで{len(ts)}点揃えました。</p>{licence_box()}')
            out.update(paged(cfg, preview, f"/genre/{slug}/{t[0]}/", sorted(ts, key=lambda i: (i["added"], i["id"]), reverse=True), h, f"{name}の{t[1]}イラスト 無料・商用OK | {cfg['site_name']}",
                             f"{t[2]}{name}のイラスト{len(ts)}点。無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, f"/genre/{slug}/"), (t[1], None)]))
    return out


def tagged(items: list[dict], tag: str) -> list[dict]:
    """Items a keyword page lists.  A guide set (12 animals) carries every animal's name as a set-wide tag, so the 犬 page led with a sparrow;
    an item whose set has a sibling titled exactly like the tag, and which is not that sibling, is left out (weekly review 2026-10-12)."""
    subject_of = {(i["series"], i["title"]) for i in items}
    return [i for i in items if tag in i["tags"] and (i["title"] == tag or (i["series"], tag) not in subject_of)]


def tag_list(items: list[dict]) -> list[str]:
    """Keywords that get their own page: plain words used by >= MIN_TAG items from >= 2 sets, most used first.

    Skipped: genre/touch names (they have pages already), set-name tags with a space, months, years, and the two words every item carries."""
    found: dict[str, list[dict]] = {}
    for t in {t for it in items for t in it["tags"]}:
        found[t] = tagged(items, t)
    skip = {g[1] for g in GENRES} | {t[1] for t in TOUCHES} | {"イラスト", "かわいい"}
    ok = [t for t, v in found.items() if len(v) >= MIN_TAG and t not in skip and " " not in t and not re.fullmatch(r"\d+月?|令和\d+年|\d+", t)
          and len({i["series"] for i in v}) >= 2]
    return sorted(ok, key=lambda t: (-len(found[t]), t))[:MAX_TAG_PAGES]


def tag_url(tag: str) -> str:
    """ASCII and stable (a hash of the word): sitemaps and static hosting want escaped URLs, and Japanese folder names would need two spellings."""
    return f"/tag/{hashlib.sha1(tag.encode('utf-8')).hexdigest()[:10]}/"


def tag_pages(cfg, preview, items, tags: list[str]) -> dict:
    out = {}
    for tag in tags:
        its = sorted(tagged(items, tag), key=lambda i: (i["added"], i["id"]), reverse=True)
        nseries = len({i["series"] for i in its})
        head = (f'<h1>「{esc(tag)}」のイラスト</h1><p class="lead">「{esc(tag)}」のキーワードが付いたイラストを、{nseries}つのセットから{len(its)}点集めました。'
                f'無料・商用OK・クレジット不要。</p>{licence_box()}')
        pages = paged(cfg, preview, tag_url(tag), its, head, f"{tag}のイラスト 無料・商用OK | {cfg['site_name']}",
                      f"{tag}のイラスト{len(its)}点。無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (tag, None)])
        out.update(pages)
    return out


def touch_pages(cfg, preview, items, series) -> dict:
    out = {}
    for slug, name, desc, _ in TOUCHES:
        its = [i for i in items if i["touch"] == slug]
        if not its:
            continue
        sers = [s for s in series if s["touch"] == slug]
        head = f'<h1>{esc(name)}のイラスト</h1><p class="lead">{esc(desc)}全{len(its)}点。無料・商用OK・クレジット不要。</p>{licence_box()}'
        top = f'<section><h2><span class="scribble">セットで探す</span></h2>{set_grid(sers)}</section><h2 style="margin-top:36px"><span class="scribble">すべてのイラスト</span></h2>'
        out.update(paged(cfg, preview, f"/touch/{slug}/", sorted(its, key=lambda i: (i["added"], i["id"]), reverse=True), head, f"{name}のイラスト 無料・商用OK | {cfg['site_name']}",
                         f"{desc}無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, None)], extra_top=top))
    return out


def uses_html(s: dict, generic: list[str]) -> str:
    """<li>s of the 用途例: what this set is for first, then the usual ones of its genre."""
    first = series_use(s)
    head = f"<li><b>このセット:</b> {esc(first)}</li>" if first else ""
    return head + "".join(f"<li>{esc(u)}</li>" for u in generic)


def pose_note(s: dict) -> str:
    return '<p class="meta" style="margin-top:32px">ほかの動物や人物のポーズは、<a href="/pose/">ポーズ集の一覧</a>から探せます。</p>' if is_pose_set(s) else ""


def series_page(cfg, preview, s: dict, items, series, og: bool, guides=()) -> str:
    base = cfg["site_url"].rstrip("/")
    g, t = genre_name(s["genre"]), touch_name(s["touch"])
    same_genre = [x for x in series if x["genre"] == s["genre"] and x["slug"] != s["slug"]][:8]
    files = json.dumps([f"/files/{i['id']}.png" for i in s["items"]], separators=(",", ":"))
    ld = json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": s["title"], "description": s["lead"], "url": base + s["url"], "inLanguage": "ja",
                     "hasPart": [{"@type": "ImageObject", "contentUrl": f"{base}/files/{i['id']}.png", "name": i["title"], "license": f"{base}/license/", "acquireLicensePage": f"{base}/license/"} for i in s["items"][:20]]},
                    ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), (g, f"/genre/{s['genre']}/"), (s["title"], None)])}
<h1>{esc(s['title'])}</h1><p class="lead">{esc(s['lead'])}</p>
<p class="meta">{len(s['items'])}点 ・ タッチ: <a href="/touch/{s['touch']}/">{esc(t)}</a> ・ ジャンル: <a href="/genre/{s['genre']}/">{esc(g)}</a></p>
<p class="dl"><button type="button" class="btn big" data-zip data-name="{s['slug']}" data-files='{esc(files)}'>セットをまとめて保存(ZIP)</button> <span class="memo-note">ブラウザの中でまとめます。ログインは不要です。</span></p>
{licence_box()}{grid(s['items'])}
<section style="margin-top:44px"><h2><span class="scribble">用途例</span></h2><ul class="check">{uses_html(s, USES[s['genre']])}</ul></section>
{pose_note(s)}{share(cfg, s['url'], s['title'] + '(無料・商用OKのイラスト)')}
{('<section style="margin-top:44px"><h2><span class="scribble">他の' + esc(g) + 'のセット</span></h2>' + set_grid(same_genre) + '</section>') if same_genre else ''}
{guide_box(guides_for(s['genre'], s['touch'], list(guides)))}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=s["url"], title=f"{s['title']} 無料・商用OKのイラスト{len(s['items'])}点 | {cfg['site_name']}", description=(s["lead"][:90] + "無料・商用OK・登録不要。")[:140],
                body=body, og_image=f"/og/{s['slug']}.webp" if og else None)


def category_page(cfg, preview, s: dict, items, series) -> str:
    """Legacy category URL of an original series."""
    body = f"""{crumbs([("トップ", "/"), (s["title"], None)])}
<h1>{esc(s['title'])}</h1><p class="lead">{esc(s['lead'])}</p>
<p class="dl"><button type="button" class="btn" data-zip data-name="{s['slug']}" data-files='{esc(json.dumps([f"/files/{i['id']}.png" for i in s["items"]], separators=(",", ":")))}'>セットをまとめて保存(ZIP)</button></p>
{licence_box()}{grid(s['items'])}"""
    return page(cfg, preview, path=s["url"], title=f"{s['title']}のイラスト | {cfg['site_name']}", description=s["lead"][:110], body=body)


def illust_page(cfg, preview, it: dict, items, series, guides=()) -> str:
    base = cfg["site_url"].rstrip("/")
    s = series_of(it, series)
    g, t = genre_name(it["genre"]), touch_name(it["touch"])
    idx = s["ids"].index(it["id"])
    mates = [x for x in s["items"] if x["id"] != it["id"]]
    mates = (s["items"][idx + 1:] + s["items"][:idx])[:8]
    others = [x for x in items if x["genre"] == it["genre"] and x["series"] != it["series"]][:4]
    uses = uses_html(s, USES[it["genre"]])
    use_line = series_use(s)
    tags = "".join(f'<li><a href="{tag_url(x)}">{esc(x)}</a></li>' if x in SITE.get("tags", ()) else f'<li>{esc(x)}</li>' for x in it["tags"])
    ld = json.dumps({"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": f"{base}/files/{it['id']}.png", "name": it["title"],
                     "description": it["desc"], "license": f"{base}/license/", "acquireLicensePage": f"{base}/license/",
                     "creditText": cfg["site_name"], "creator": {"@type": "Organization", "name": cfg["operator_name"]}, "width": it["w"], "height": it["h"],
                     "encodingFormat": "image/png", "keywords": ", ".join(it["tags"])}, ensure_ascii=False)
    prev_next = ""
    if len(s["items"]) > 1:
        pv, nx = s["items"][idx - 1], s["items"][(idx + 1) % len(s["items"])]
        prev_next = f'<nav class="prevnext" aria-label="同じセットの前後"><a href="/illust/{pv["id"]}/" rel="prev">← {esc(pv["title"])}</a><a href="/illust/{nx["id"]}/" rel="next">{esc(nx["title"])} →</a></nav>'
    body = f"""{crumbs([("トップ", "/"), (g, f"/genre/{it['genre']}/"), (s["title"], s["url"]), (it["title"], None)])}
<div class="detail"><div class="preview"><div class="checker big" id="bgbox"><img id="mainimg" src="/files/{it['id']}.webp" alt="{esc(it['title'])}" width="{it['w']}" height="{it['h']}" fetchpriority="high"></div>
<div class="bgsw" aria-label="背景色を確認する"><button type="button" data-bg="" class="on">透明</button><button type="button" data-bg="#ffffff">白</button><button type="button" data-bg="#ffc93c">黄</button><button type="button" data-bg="#ffd6e0">桃</button><button type="button" data-bg="#d9f1ff">空</button><button type="button" data-bg="#2b1b14">黒</button></div></div>
<div class="info"><h1>{esc(it['title'])}</h1><p class="lead">{esc(it['desc'])}</p>
<p class="meta">「<a href="{s['url']}">{esc(s['title'])}</a>」{len(s['items'])}点のうちの1点です。{esc(use_line)}</p>
<p class="dl"><a class="btn big" href="/files/{it['id']}.png" download="{it['id']}.png">PNG(透明)をダウンロード</a>
<a class="btn btn-sub" href="/files/{it['id']}.webp" download="{it['id']}.webp">WebP</a>
{''.join(f'<a class="btn btn-sub" href="/files/{it["id"]}-{k}.pdf" download="{it["id"]}-{k}.pdf">{"A4で印刷(PDF)" if k == "a4" else "はがきサイズで印刷(PDF)"}</a>' for k in pdf_kinds(it))}
{f'<a class="btn btn-sub" href="/tool/nurie/?id={it["id"]}">オンラインで塗る</a>' if it["touch"] == "lineart" else ""}
<button class="btn btn-sub fav-big" type="button" data-fav="{it['id']}" aria-pressed="false">♡ お気に入り</button></p>
<p class="meta">サイズ: {it['w']}×{it['h']}px(透明な背景) ・ セット: <a href="{s['url']}">{esc(s['title'])}</a> ・ タッチ: <a href="/touch/{it['touch']}/">{esc(t)}</a> ・ ジャンル: <a href="/genre/{it['genre']}/">{esc(g)}</a></p>
<details class="export" data-src="/files/{it['id']}.png" data-name="{it['id']}"><summary>背景や大きさを変えて保存する</summary>
<div class="export-row"><label>形式<select name="fmt"><option value="png">PNG</option><option value="jpg">JPG(背景つき)</option></select></label>
<label>背景<select name="bg"><option value="">透明</option><option value="#ffffff">白</option><option value="#ffc93c">黄</option><option value="#ffd6e0">桃</option><option value="#d9f1ff">空</option><option value="#d7f7ea">ミント</option></select></label>
<label>大きさ<select name="size"><option value="orig">そのまま</option><option value="sq1080">正方形 1080px(SNS・アイコン)</option><option value="wide">横 1280×720(サムネイル)</option><option value="hagaki">はがき(縦)300dpi</option></select></label></div>
<p><button type="button" class="btn" data-export>この設定で保存</button> <button type="button" class="btn btn-sub" data-copy>画像をコピー</button> <span class="memo-note" role="status" aria-live="polite" data-export-msg></span></p></details>
{licence_box()}
</div></div>
{prev_next}
<section><h2><span class="scribble">用途例</span></h2><ul class="check">{uses}</ul></section>
<section><h2><span class="scribble">キーワード</span></h2><ul class="tagcloud">{tags}</ul></section>
{share(cfg, f"/illust/{it['id']}/", f"{it['title']}(無料・商用OKのイラスト)")}
<section style="margin-top:44px"><h2><span class="scribble">同じセットのイラスト</span></h2>{grid(mates)}</section>
{('<section style="margin-top:44px"><h2><span class="scribble">他の' + esc(g) + 'のイラスト</span></h2>' + grid(others) + '</section>') if others else ''}
{guide_box(guides_for(it['genre'], it['touch'], list(guides)))}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/illust/{it['id']}/", title=f"{it['title']} 無料・商用OKのイラスト | {cfg['site_name']}",
                description=(f"{it['title']}のイラスト。{s['title']}の1点です。{use_line}無料・商用OK・クレジット不要の透明PNG。" if use_line
                             else f"{it['desc']}{t}のタッチ。無料・商用OK・クレジット不要の透明PNG。")[:150], body=body, og_image=f"/thumbs/{it['id']}.webp")


def special_page(cfg, preview, sp: dict, sers: list[dict], its: list[dict], today: date, guides=()) -> str:
    intro = "".join(f"<p>{esc(p)}</p>" for p in sp["intro"])
    steps = "".join(f"<li><b>{esc(a)}</b><span>{esc(b)}</span></li>" for a, b in sp["steps"])
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in sp["faq"])
    sections = ""
    for s in sers:
        sections += f'<section style="margin-top:36px"><h2><a href="{s["url"]}" class="plainlink"><span class="scribble">{esc(s["title"])}</span></a></h2><p class="lead">{esc(s["lead"])}</p>{grid(s["items"])}</section>'
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in sp["faq"]]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("特集", "/special/"), (sp["name"], None)])}
<h1>{esc(sp['title'])}</h1>{intro}<p class="meta">全{len(its)}点 ・ {len(sers)}セット</p>{licence_box()}
<section><h2><span class="scribble">使い方</span></h2><ol class="howto">{steps}</ol></section>
{sections}
{guide_box([g for g in guides if g['slug'] in sp['guides']] if sp.get('guides') else guides_for('eto' if sp['slug'] == 'nenga-2027' else 'season', 'kawaii', list(guides), 3))}
<section style="margin-top:44px"><h2><span class="scribble">よくある質問</span></h2><div class="faq">{faq}</div></section>
{pr_box(cfg, *SPECIAL_PR[sp['slug']]) if sp['slug'] in SPECIAL_PR else ""}{share(cfg, f"/special/{sp['slug']}/", sp['title'])}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/special/{sp['slug']}/", title=f"{sp['title']} | {cfg['site_name']}", description=sp["description"][:150], body=body, og_image=f"/og/special-{sp['slug']}.webp")


def specials_hub(cfg, preview, built) -> str:
    cards = ""
    for sp, sers, its in built:
        cards += (f'<li><a class="special-card" href="/special/{sp["slug"]}/"><span class="set-thumbs checker">'
                  + "".join(f'<img src="/thumbs/{i["id"]}.webp" alt="" width="120" height="{round(i["h"] * 120 / i["w"])}" loading="lazy">' for i in its[:3])
                  + f'</span><b>{esc(sp["name"])}</b><small>{len(its)}点</small></a></li>')
    body = f"""{crumbs([("トップ", "/"), ("特集", None)])}
<h1>特集</h1><p class="lead">季節の行事や、探されることの多いテーマごとに、イラストをまとめました。</p><ul class="special-grid">{cards}</ul>"""
    return page(cfg, preview, path="/special/", title=f"特集 | {cfg['site_name']}", description="年賀状、クリスマス、冬、ハロウィン、ぬりえなど、テーマごとのイラスト特集。無料・商用OK。", body=body)


def new_page(cfg, preview, series) -> str:
    newest = sorted(series, key=lambda s: (s["added"], s["slug"]), reverse=True)
    body = f"""{crumbs([("トップ", "/"), ("新着", None)])}
<h1>新着のセット</h1><p class="lead">新しく追加したイラストのセットです。</p>{set_grid(newest[:60])}"""
    return page(cfg, preview, path="/new/", title=f"新着のイラスト | {cfg['site_name']}", description="新しく追加したイラストのセットです。無料・商用OK・登録不要。", body=body)


SEARCH_STARTS = ["年賀状", "お正月", "クリスマス", "ハロウィン", "ぬりえ", "フレーム", "飾り罫(ライン)", "おたより", "保育園", "運動会", "かわいい動物", "人物", "アイコン", "吹き出し", "リアル", "かっこいい"]


def search_page(cfg, preview) -> str:
    chip_links = "".join(f'<a class="chip" href="/search/?q={quote(w.split("(")[0], safe="")}">{esc(w)}</a>' for w in SEARCH_STARTS)
    gopts = '<option value="">ジャンル: すべて</option>' + "".join(f'<option value="{g[0]}">{esc(g[1])}</option>' for g in GENRES)
    topts = '<option value="">タッチ: すべて</option>' + "".join(f'<option value="{t[0]}">{esc(t[1])}</option>' for t in TOUCHES)
    body = f"""{crumbs([("トップ", "/"), ("探す", None)])}
<h1>イラストを探す</h1>
<form class="search-app" id="search-app" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="ひつじ、年賀状、クリスマス、ぬりえ…" aria-label="キーワード" autocomplete="off">
<select name="g" aria-label="ジャンル">{gopts}</select><select name="t" aria-label="タッチ">{topts}</select><button class="btn" type="submit">探す</button></form>
<p class="memo-note" id="search-status" role="status" aria-live="polite">キーワードを入れてください。ひらがな・カタカナ・似た言い方(塗り絵とぬりえ など)はどちらでも見つかります。</p>
<div id="search-chips" class="chips">{chip_links}</div>
<ul class="illust-grid" id="search-results" aria-live="polite"></ul>
<p style="text-align:center"><button class="btn" type="button" id="search-more" hidden>もっと見る</button></p>
<noscript><p class="notice">検索機能にはJavaScriptが必要です。<a href="/illust/">イラスト一覧</a>からも探せます。</p></noscript>"""
    return page(cfg, preview, path="/search/", title=f"イラストを探す | {cfg['site_name']}", description="キーワードでイラストを探せます。ジャンルやタッチでも絞り込めます。", body=body)


def favorites_page(cfg, preview) -> str:
    body = f"""{crumbs([("トップ", "/"), ("お気に入り", None)])}
<h1>お気に入り</h1><p class="lead">♡を押したイラストがここに並びます。この端末のブラウザの中だけに保存され、送信はされません。</p>
<p class="memo-note" id="fav-status" role="status" aria-live="polite"></p>
<ul class="illust-grid" id="fav-results" aria-live="polite"></ul>"""
    return page(cfg, preview, path="/favorites/", title=f"お気に入り | {cfg['site_name']}", description="お気に入りに入れたイラストの一覧です。この端末の中だけに保存されます。", body=body)


def license_page(cfg: dict, preview: bool) -> str:
    body = f"""{crumbs([("トップ", "/"), ("利用について", None)])}
<h1>利用について(ライセンス)</h1>
<p class="lead">{esc(cfg['site_name'])}のイラストは、<b>個人でも会社でも無料でご利用いただけます</b>。使う前の連絡やクレジット表示は不要です。会員登録もダウンロード回数の制限もありません。</p>
<h2><span class="scribble">できること</span></h2><ul class="check"><li>商用利用(チラシ、商品の説明、広告、動画、書籍、アプリ、年賀状、お店のポップなど)</li><li>点数の制限なしで、何点でも使うこと</li>
<li>大きさ、色、向きを変えたり、文字や他の画像と組み合わせたりすること</li><li>SNSやLINEで画像として共有すること</li><li>印刷して配ること(年賀状、おたより、掲示物など)</li></ul>
<h2><span class="scribble">お願い</span></h2><ul class="warn"><li>イラストそのものを素材集として配布・販売することはできません(加工して他の作品に使うのは問題ありません)。</li>
<li>イラストを商標として登録したり、「自分のキャラクター」として権利を主張したりすることはご遠慮ください。</li>
<li>LINEスタンプなど、イラストが主役の商品としてそのまま販売することはご遠慮ください。</li>
<li>人を傷つける内容、法律や公序良俗に反する内容には使えません。</li></ul>
<h2><span class="scribble">生成AIで制作したイラストについて</span></h2>
<p>このサイトのイラストは、<b>生成AIで制作し、人が選別・調整したもの</b>です。生成AIで制作したものは法律上、著作物として扱われない場合があります。そのため「著作権が当サイトに帰属する」とは書かず、<b>利用の許諾</b>として上の内容をお約束します。</p>
<p>既存のキャラクター、実在の人物、特定の作家の画風をまねる指示では制作していません。万一似ているというご指摘があれば、<a href="/contact/">お問い合わせ</a>ください。速やかに確認し、必要な場合は取り下げます。</p>
<h2><span class="scribble">保証について</span></h2>
<p>イラストの利用によって生じた問題について、当サイトは責任を負いません。第三者の権利を侵害しないことの保証もできません。ご自身の判断でご利用ください。</p>"""
    return page(cfg, preview, path="/license/", title=f"利用について(ライセンス) 商用OK・クレジット不要 | {cfg['site_name']}",
                description="個人も商用も無料。クレジット表示、登録、点数制限はありません。できることとお願いを説明します。", body=body)


def php_single(text: str) -> str:
    """Text as the inside of a PHP single-quoted string (only the backslash and the quote need care there)."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


def request_php(cfg: dict) -> str:
    """api/q.php: the receiver of illustration requests (see request_receiver.php.tpl); the rules are the page's own (content/request_rules.json)."""
    url = str(cfg["site_url"]).rstrip("/")
    rules = json.dumps(wishes.client_rules(), ensure_ascii=False, separators=(",", ":"))
    j = lambda x: json.dumps(x, ensure_ascii=False)   # noqa: E731
    php = (HERE / "request_receiver.php.tpl").read_text(encoding="utf-8")
    return (php.replace("__SITE_URL__", php_single(url)).replace("__RULES__", php_single(rules)).replace("__USES__", j(wishes.USES)).replace("__TOUCHES__", j([t[0] for t in TOUCHES])))


def request_board() -> dict:
    f = HERE / "content" / "request_board.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"v": 1, "updated": "", "rows": []}


def request_data_files() -> dict:
    """data/request-rules.json (the request box and the search page use it) and data/request-board.json (what is being made / published, for the 'your request' note)."""
    rules = wishes.client_rules()
    rules["uses"] = wishes.USES
    return {"data/request-rules.json": json.dumps(rules, ensure_ascii=False, separators=(",", ":")),
            "data/request-board.json": json.dumps(request_board(), ensure_ascii=False, separators=(",", ":"))}


def request_page(cfg: dict, preview: bool) -> str:
    form = contactform.form_html(cfg, default_kind="イラストのリクエスト", message_hint="例: ひつじが、お正月に、こたつでみかんを食べているイラスト。年賀状に使いたいです。", page_hint=False)
    board = request_board()["rows"]
    uopts = '<option value="">使い道: 選ばない</option>' + "".join(f'<option value="{esc(u)}">{esc(u)}</option>' for u in wishes.USES)
    topts = '<option value="">タッチ: お任せ</option>' + "".join(f'<option value="{t[0]}">{esc(t[1])}</option>' for t in TOUCHES)
    examples = ["こたつでみかんを食べるひつじ", "運動会のフレーム", "おじいちゃんとおばあちゃんのお出かけ", "リアルなカエル", "ハロウィンのかぼちゃのライン", "お歳暮のお礼状に添える絵"]
    chips = "".join(f'<button type="button" class="chip" data-example="{esc(e)}">{esc(e)}</button>' for e in examples)

    def row(r):
        link = f'<a href="/series/{esc(r["series"])}/">{esc(r["title"])}</a>' if r.get("series") and r["status"] == "公開しました" else esc(r["title"])
        asked = f'<small>{r["asked"]}人が欲しいと言いました</small>' if r.get("asked", 0) > 1 else ""
        want = f' <button type="button" class="chip" data-plus="{esc(r["title"])}">私も欲しい</button>' if r["status"] != "公開しました" else ""
        return f'<li><span class="req-state {"done" if r["status"] == "公開しました" else "wip"}">{esc(r["status"])}</span> <b>{link}</b>{asked}{want}</li>'
    # the board is shown only once something has really been answered: no empty promise
    board_section = (f'''<section><h2><span class="scribble">リクエストへの回答</span></h2>
<p>いただいたリクエストから、他の方にも役立つものを選んで制作しています。制作中のもの、公開したものをここに並べます。</p><ul class="req-board">{"".join(row(r) for r in board)}</ul></section>''' if board else "")
    body = f"""{crumbs([("トップ", "/"), ("リクエスト", None)])}
<h1>イラストのリクエスト</h1>
<p class="lead">欲しいイラストの場面を、ひとことで送ってください。対応できるものは順番に制作し、このサイトに公開します。早ければ翌日です。</p>
<section id="req-app" class="req-app" aria-labelledby="req-h">
<h2 id="req-h"><span class="scribble">ひとことでリクエスト</span></h2>
<form id="req-form" novalidate>
<label>希望するイラスト<input type="text" name="w" maxlength="60" placeholder="例: こたつでみかんを食べるひつじ" autocomplete="off" required></label>
<div class="req-row"><label>使い道<select name="u">{uopts}</select></label><label>タッチ<select name="t">{topts}</select></label></div>
<p><button class="btn big" type="submit">リクエストする</button></p>
<p class="req-msg" id="req-msg" role="status" aria-live="polite"></p>
</form>
<p class="memo-note">例から選ぶ:</p><div class="chips">{chips}</div>
<p class="req-small">送った言葉はイラストを選ぶために集計して使います。住所・メールアドレス・名前は聞きません。送った内容はこの端末にも記録されます(「あなたのリクエスト」に出ます)。<a href="/privacy/">プライバシーポリシー</a></p>
</section>
<section id="req-mine" class="req-mine" hidden><h2><span class="scribble">あなたのリクエスト</span></h2><p class="memo-note">この端末から送ったリクエストと、その後の状況です(この端末の中だけに記録されています)。</p><div id="req-mine-list"></div></section>
{board_section}
<section><h2><span class="scribble">お受けできないもの</span></h2>
<ul class="warn"><li>既存のキャラクター・商品名・会社のロゴ(「ポケモン」「ミッキー」など)。代わりに、<b>オリジナルの</b>似た雰囲気のキャラクターならお受けできます。</li>
<li>実在の人物、似顔絵、特定の作家の絵をまねるもの。</li><li>暴力・性的な内容、法律や公序良俗に反するもの、個人を特定できる情報。</li></ul>
<p class="memo-note">個別のお返事や納期のお約束はできません。対応できないこともあります。思い通りの絵にならない場合があります。</p></section>
<details class="req-long"><summary>詳しく伝えたい方へ(長い文章のフォーム)</summary>{form}</details>"""
    return page(cfg, preview, path="/request/", title=f"イラストのリクエスト | {cfg['site_name']}", description="欲しいイラストをひとことで送れます。対応できるものは順番に制作して公開します。", body=body)


def tool_page(cfg: dict, preview: bool, items: list[dict], series: list[dict]) -> str:
    chars = [{"id": i["id"], "title": i["title"], "src": f"/files/{i['id']}.png", "g": series_of(i, series)["title"]}
             for i in items if i["genre"] in ("animals", "shimaenaga", "eto") and i["touch"] in ("kawaii", "wa") and not i["id"].startswith(("event-", "person-"))]
    data = esc(json.dumps({"chars": chars}, ensure_ascii=False, separators=(",", ":")))
    groups: dict[str, list[dict]] = {}
    for c in chars:
        groups.setdefault(c["g"], []).append(c)
    opts = "".join(f'<optgroup label="{esc(g)}">' + "".join(f'<option value="{c["id"]}">{esc(c["title"])}</option>' for c in cs) + "</optgroup>" for g, cs in groups.items())
    body = f"""{crumbs([("トップ", "/"), ("カードをつくる", None)])}
<h1>名前入りカードをつくる</h1><p class="lead">名前とひとことを入れて、かわいい動物のカードを画像で保存できます。入力した内容はこの端末の中だけで使われます(送信されません)。</p>
<section id="card-app" class="card-app" data-json="{data}">
<div class="card-form"><label>カードの種類<select name="tpl"><option value="birthday">誕生日</option><option value="thanks">ありがとう</option><option value="congrats">おめでとう</option><option value="cheer">応援</option><option value="newyear">あけましておめでとう</option></select></label>
<label>宛名(相手)<input type="text" name="to" maxlength="14" placeholder="例: ハナコさん"></label>
<label>ひとこと<textarea name="msg" maxlength="60" rows="3" placeholder="例: いつもありがとうございます。今日はゆっくり過ごしてください。"></textarea></label>
<div class="ai-box" hidden><button type="button" class="btn btn-sub" data-ai-msg>ひとことの案を出す</button><span class="ai-note" role="status" aria-live="polite">Chromeに内蔵のAIで、この端末の中で作ります(無料)。</span><div class="ai-opts"></div></div>
<label>名前(差出人)<input type="text" name="from" maxlength="14" placeholder="例: タロウ"></label>
<label>キャラクター<select name="char">{opts}</select></label>
<label>色<select name="color"><option value="#ffc93c">たまご色</option><option value="#ffd6e0">さくら色</option><option value="#d9f1ff">空色</option><option value="#d7f7ea">ミント色</option></select></label>
<p class="dl"><button type="button" class="btn big" data-save>画像として保存</button></p><p class="memo-note">スマホで保存できないときは、下の画像を長押ししてください。</p></div>
<div class="card-preview"><canvas width="1080" height="1350" aria-label="カードのプレビュー"></canvas><img class="card-img" alt="完成したカード" hidden></div></section>
{licence_box()}"""
    return page(cfg, preview, path="/tool/card/", title=f"名前入りカードをつくる 無料・保存OK | {cfg['site_name']}",
                description="名前とひとことを入れて、動物のカードを画像で保存。誕生日・ありがとう・おめでとう・新年のあいさつ。無料ですぐに作れます。", body=body)


def use_pages(cfg: dict, preview: bool, series: list[dict], built: list, guides: list) -> tuple[dict, list[dict]]:
    """/use/ and /use/<slug>/: the hubs of usehubs.HUBS that have at least three sets; also returns those hubs (with their sets) for the home page and the helper."""
    from sites.minna import usehubs
    sp_by = {sp["slug"]: sp for sp, _s, _i in built}
    g_by = {g["slug"]: g for g in guides}
    tool_by = {u: (n, d) for u, n, d in TOOLS}
    pages: dict = {}
    live = []
    for h in usehubs.HUBS:
        sers = usehubs.rank_series(h["words"], series, 12)
        if len(sers) < 3:
            continue
        n_items = sum(len(s["items"]) for s in sers)
        intro = "".join(f"<p>{esc(t)}</p>" for t in h["intro"])
        points = "".join(f"<li><b>{esc(a)}</b><span>{esc(b)}</span></li>" for a, b in h["points"])
        links = "".join(f'<li><a href="/special/{s}/">{esc(sp_by[s]["name"])}の特集</a></li>' for s in h["specials"] if s in sp_by)
        links += "".join(f'<li><a href="/guide/{g}/">{esc(g_by[g]["title"])}</a></li>' for g in h["guides"] if g in g_by)
        links += "".join(f'<li><a href="{t}">{esc(tool_by[t][0])}</a></li>' for t in h["tools"] if t in tool_by)
        related = f'<section style="margin-top:44px"><h2><span class="scribble">あわせて見る</span></h2><ul class="plain use-links">{links}</ul></section>' if links else ""
        q = h["words"][0]
        body = f"""{crumbs([("トップ", "/"), ("用途から探す", "/use/"), (h["name"], None)])}
<h1>{esc(h["name"])}に使えるイラスト</h1>{intro}{licence_box()}
<section><h2><span class="scribble">使うときのポイント</span></h2><ul class="promise">{points}</ul></section>
<section style="margin-top:44px"><h2><span class="scribble">おすすめのセット</span></h2><p class="meta">{len(sers)}セット・{n_items}点。ほかのイラストは<a href="/search/?q={esc(q)}">「{esc(q)}」で検索</a>できます。</p>{set_grid(sers)}</section>
{related}"""
        pages[f"use/{h['slug']}/index.html"] = page(cfg, preview, path=f"/use/{h['slug']}/", title=f"{h['name']}に使える無料イラスト 商用OK | {cfg['site_name']}",
                                                       description=f"{h['short']}に使える、無料・商用OK・登録不要のイラスト素材。{len(sers)}セット{n_items}点から選べます。", body=body)
        live.append({**h, "sets": sers, "n": n_items})
    cards = "".join(f'<li><a class="tool-card" href="/use/{h["slug"]}/"><b>{esc(h["name"])}</b><span>{esc(h["short"])}({len(h["sets"])}セット)</span></a></li>' for h in live)
    body = f"""{crumbs([("トップ", "/"), ("用途から探す", None)])}
<h1>用途から探す</h1><p class="lead">チラシ、おたより、資料、SNSなど、使う場面ごとにイラストをまとめました。すべて無料・商用OK・クレジット不要です。</p>
<ul class="tool-grid">{cards}</ul>{licence_box()}"""
    pages["use/index.html"] = page(cfg, preview, path="/use/", title=f"用途から探す チラシ・おたより・資料・SNS | {cfg['site_name']}",
                                   description="チラシ、年賀状、園や学校のおたより、社内資料、SNS、医療・介護、教材、名前入りの印刷物など、使う場面ごとに無料・商用OKのイラストを探せます。", body=body)
    return pages, live


def pose_page(cfg: dict, preview: bool, series: list[dict]) -> tuple[str, list[dict]]:
    """/pose/: every set of poses (animals, workers, family and so on) in one place, grouped by genre; returns the page and the sets."""
    sets = sorted((s for s in series if is_pose_set(s) and s["items"]), key=lambda s: (s["genre"], s["slug"]))
    groups: dict[str, list[dict]] = {}
    for s in sets:
        groups.setdefault(s["genre"], []).append(s)
    order = sorted(groups, key=lambda g: (-len(groups[g]), g))
    n_items = sum(len(s["items"]) for s in sets)
    secs = "".join(f'<section style="margin-top:44px" id="pose-{g}"><h2><span class="scribble">{esc(genre_name(g))}のポーズ</span></h2>'
                   f'<p class="meta">{len(groups[g])}セット・{sum(len(s["items"]) for s in groups[g])}点</p>{set_grid(groups[g])}</section>' for g in order)
    jump = "".join(f'<a href="#pose-{g}">{esc(genre_name(g))}</a>' for g in order)
    body = f"""{crumbs([("トップ", "/"), ("ポーズ集", None)])}
<h1>ポーズ集のイラスト</h1>
<p class="lead">同じキャラクターが、立つ、座る、笑う、驚く、歩くなど、さまざまなポーズをとったイラストを集めました。{len(sets)}セット・{n_items}点。無料・商用OK・クレジット不要です。</p>
<p>1つのセットは同じキャラクターでそろっているので、スライドや資料、おたよりの中で、場面に合わせて表情やポーズを使い分けられます。背景は透明なPNGです。</p>
{licence_box()}
<nav class="chips" aria-label="ジャンル">{jump}</nav>
{secs}"""
    html = page(cfg, preview, path="/pose/", title=f"ポーズ集のイラスト 動物・人物のポーズいろいろ 無料・商用OK | {cfg['site_name']}",
                description=f"動物や人物のポーズ違いのイラスト{n_items}点({len(sets)}セット)。無料・商用OK・登録不要の透明PNGで、スライドやSNS、おたよりの表情差分に使えます。", body=body)
    return html, sets


MAKER_FAQ = {
    "calendar": [
        ("祝日は入っていますか?", "入っています。法律で定められた祝日と振替休日、国民の休日を、年ごとに計算して表示します。年によって祝日が変わることがあるため、大切な予定の確認には公式の暦も参照してください。"),
        ("印刷はどうすればいいですか?", "「印刷」を押すと、A4縦のページとして印刷できます。プリンターの設定で用紙をA4、倍率を100%にしてください。画像として保存して、別のソフトで使うこともできます。"),
        ("商用で使えますか?", "このサイトのイラストと同じく、個人でも商用でも無料で使えます。作ったカレンダーを配布・販売する場合の条件は、利用について のページをご覧ください。"),
    ],
    "nametag": [
        ("入力した名前は送信されますか?", "送信されません。名前も文面も、この端末のブラウザの中だけで使われます。"),
        ("席札はどのように使いますか?", "A4に1枚印刷し、中央の線で山型に折ると、向かい合う両側から名前が読めます。"),
        ("名札のサイズはどのくらいですか?", "A4に8枚の面付けで、1枚はおよそ95×66mmです。点線に沿って切ってください。"),
    ],
}


def maker_page(cfg: dict, preview: bool, kind: str) -> str:
    chips = "".join(f'<button type="button" class="chip" data-q="{esc(q)}">{esc(q)}</button>' for q in ("ひつじ", "ねこ", "いぬ", "花", "季節", "仕事", "シンプル"))
    if kind == "calendar":
        title, path = "カレンダーをつくる", "/tool/calendar/"
        h1, lead = "カレンダーをつくる", "好きなイラストで、年と月を選んだA4のカレンダーを作れます。祝日入りで、画像として保存でき、そのまま印刷もできます。無料・登録不要です。"
        opts = ('<label>年<select name="year"></select></label><label>月<select name="month"></select></label>'
                '<label>週の始まり<select name="start"><option value="sun">日曜日</option><option value="mon">月曜日</option></select></label>'
                '<label class="chk"><input type="checkbox" name="adj" checked> 前後の月の日付を薄く表示する</label>')
        desc = "好きなイラストで、祝日入りのA4カレンダーを作れます。年と月を選び、画像として保存・印刷できます。無料・登録不要・商用OK。"
    else:
        title, path = "名前入りの名札・席札・賞状をつくる", "/tool/nametag/"
        h1, lead = "名前入りの名札・席札・賞状をつくる", "名前を入れて、A4に印刷できる名札(8枚)・二つ折りの席札・賞状を作れます。入力した内容はこの端末の中だけで使われます。無料・登録不要です。"
        opts = ('<label>種類<select name="tpl"><option value="tag8">名札(A4に8枚)</option><option value="seat">席札(二つ折り)</option><option value="cert">賞状</option></select></label>'
                '<label>名前<input type="text" name="name" maxlength="16" placeholder="例: 山田 太郎"></label>'
                '<label data-for="tag8 seat">所属など(任意)<input type="text" name="sub" maxlength="20" placeholder="例: 営業部"></label>'
                '<label>書体<select name="face"><option value="sans">ゴシック体</option><option value="serif">明朝体</option></select></label>'
                '<label data-for="cert">文面<textarea name="body" maxlength="120" rows="3" placeholder="例: あなたは優れた成績を収めました。ここにその功績をたたえ、賞状を贈ります。"></textarea></label>'
                '<label data-for="cert">日付<input type="text" name="date" maxlength="24"></label>'
                '<label data-for="cert">贈る人・団体<input type="text" name="from" maxlength="30" placeholder="例: ○○委員会"></label>')
        desc = "名前を入れた名札(A4に8枚)・二つ折りの席札・賞状を、イラスト入りで作れます。画像として保存・印刷できます。無料・登録不要・商用OK。"
    faq = MAKER_FAQ[kind]
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("つくる", "/tool/"), (title, None)])}
<h1>{h1}</h1>
<p class="lead">{lead}</p>
{licence_box()}
<section id="maker-app" class="mk-app" data-kind="{kind}">
<div class="mk-cols"><div class="mk-side">
<form id="mk-opts" class="mk-opts" onsubmit="return false"><h2 class="mk-h">1. 内容を決める</h2>{opts}</form>
<h2 class="mk-h">2. イラストを選ぶ</h2>
<form id="mk-search" class="mk-search" role="search"><input type="search" name="q" placeholder="例: ひつじ、花、仕事" aria-label="イラストを探す" autocomplete="off"><button class="btn" type="submit">探す</button></form>
<p class="mk-chips">{chips}</p><p class="memo-note" id="mk-count" role="status" aria-live="polite"></p><div id="mk-list" class="mk-list"></div>
</div><div class="mk-main"><canvas id="mk-canvas" width="10" height="10" role="img" aria-label="できあがりのプレビュー"></canvas>
<p class="nu-btns"><button type="button" class="btn big" id="mk-save">画像で保存</button><button type="button" class="btn btn-sub" id="mk-print">印刷</button></p>
<p class="req-msg" id="mk-msg" role="status" aria-live="polite">イラストを選ぶと、プレビューに入ります。</p></div></div>
</section>
<div id="mk-printbox" class="nu-printbox" hidden aria-hidden="true"></div>
<noscript><p class="notice">この機能にはJavaScriptが必要です。印刷だけなら、<a href="/printables/">印刷できるもの</a>から選べます。</p></noscript>
<section style="margin-top:44px"><h2><span class="scribble">よくある質問</span></h2><div class="faq">{faq_html}</div></section>
<p><a href="/tool/">ほかのつくる機能</a> ・ <a href="/printables/">印刷できるもの(PDF)</a></p>
<script type="application/ld+json">{ld}</script>
<script src="/assets/maker.js" defer></script>"""
    return page(cfg, preview, path=path, title=f"{title} 無料・印刷OK・登録不要 | {cfg['site_name']}", description=desc, body=body)


TOOLS = [
    ("/tool/calendar/", "カレンダーをつくる", "好きなイラストで、祝日入りのA4カレンダー。年と月を選んで保存・印刷できます。"),
    ("/tool/nametag/", "名札・席札・賞状をつくる", "名前を入れて、A4に印刷できる名札(8枚)、二つ折りの席札、賞状を作れます。"),
    ("/tool/card/", "名前入りカードをつくる", "名前とひとことを入れて、お祝いのカードを画像で保存できます。"),
    ("/tool/nurie/", "オンラインぬりえ", "線画を選んで、ブラウザ上で色を塗れます。保存も印刷もできます。"),
    ("/printables/", "印刷できるもの(PDF)", "カレンダー、ぬりえ、賞状、名札、時間割をA4のPDFで印刷できます。"),
    ("/request/", "イラストをリクエストする", "サイトにないイラストを希望できます。選んで制作し、公開します。"),
]


def tools_page(cfg: dict, preview: bool) -> str:
    cards = "".join(f'<li><a class="tool-card" href="{u}"><b>{esc(n)}</b><span>{esc(d)}</span></a></li>' for u, n, d in TOOLS)
    body = f"""{crumbs([("トップ", "/"), ("つくる", None)])}
<h1>つくる</h1><p class="lead">サイトのイラストで、カレンダー・名札・賞状・カードを作れます。入力した内容はこの端末の中だけで使われ、送信されません。すべて無料・登録不要です。</p>
<ul class="tool-grid">{cards}</ul>
{licence_box()}"""
    return page(cfg, preview, path="/tool/", title=f"イラストでつくる カレンダー・名札・賞状・カード | {cfg['site_name']}",
                description="サイトのイラストで、カレンダー、名札、席札、賞状、名前入りカード、ぬりえを作れます。無料・登録不要・商用OK。", body=body)


NURIE_FAQ = [
    ("色を塗った絵は保存できますか?", "「保存」を押すとPNG画像として保存できます。スマホでは保存後、写真(ダウンロード)に入ります。"),
    ("印刷できますか?", "「印刷」を押すと、塗った絵をそのまま印刷できます。紙の大きさはプリンターの設定でA4などを選んでください。"),
    ("色がはみ出します。", "線が切れている所があると、色が外へ広がることがあります。「戻す」で1つ前に戻れます。"),
    ("塗った絵は商用で使えますか?", "はい。元のイラストと同じく、無料で商用利用できます。詳しくは「利用について」をご覧ください。"),
    ("塗った内容は送信されますか?", "いいえ。色を塗る作業はお使いのブラウザの中だけで行い、当サイトには送信されません。"),
]


def nurie_page(cfg: dict, preview: bool, series: list[dict]) -> str:
    lines = [s for s in series if s["touch"] == "lineart" and s["items"]]
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in NURIE_FAQ)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in NURIE_FAQ]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("オンラインぬりえ", None)])}
<h1>オンラインぬりえ</h1>
<p class="lead">ブラウザ上で色を塗れます。絵と色を選び、塗りたい場所をタップします。塗った絵は保存も印刷もできます。無料・登録不要です。</p>
{licence_box()}
<section id="nurie-app" class="nu-app">
<section id="nu-stage" class="nu-stage" hidden aria-labelledby="nu-title">
<h2 id="nu-title"><span class="scribble">ぬりえ</span></h2>
<div class="nu-wrap"><canvas id="nu-canvas" width="10" height="10" role="img" aria-label="ぬりえ"></canvas>
<div class="nu-side"><p class="memo-note">1. 色を選ぶ</p><div id="nu-palette" class="nu-palette"></div>
<p class="memo-note">2. 塗りたい場所をタップ</p>
<p class="nu-btns"><button type="button" class="btn btn-sub" id="nu-undo">1つ戻す</button><button type="button" class="btn btn-sub" id="nu-reset">白紙に戻す</button></p>
<p class="nu-btns"><button type="button" class="btn big" id="nu-save">画像で保存</button><button type="button" class="btn btn-sub" id="nu-print">印刷</button><button type="button" class="btn btn-sub" id="nu-other">他の絵</button></p>
<p class="req-msg" id="nu-msg" role="status" aria-live="polite">絵を選んでください。</p></div></div>
</section>
<section id="nu-pick"><h2><span class="scribble">塗りたい絵を選ぶ</span> <small id="nu-count"></small></h2>
<p class="memo-note">線だけで描いた絵です。選ぶと上で塗れます。</p><div id="nu-list"></div></section>
</section>
<div id="nu-printbox" class="nu-printbox" hidden aria-hidden="true"></div>
<noscript><p class="notice">オンラインぬりえにはJavaScriptが必要です。印刷して塗りたいときは、<a href="/printables/">印刷できるもの</a>から選べます。</p></noscript>
<section><h2><span class="scribble">ぬりえの絵(セットから探す)</span></h2>{set_grid(lines)}</section>
<section style="margin-top:44px"><h2><span class="scribble">よくある質問</span></h2><div class="faq">{faq}</div></section>
<p>紙に印刷して塗る、A4の<a href="/special/nurie/">ぬりえの特集</a>や、<a href="/guide/nurie-insatsu/">ぬりえの印刷方法</a>もあります。</p>
<script type="application/ld+json">{ld}</script>
<script src="/assets/nurie.js" defer></script>"""
    return page(cfg, preview, path="/tool/nurie/", title=f"オンラインぬりえ 無料・登録不要・保存と印刷OK | {cfg['site_name']}",
                description="ブラウザ上で色を塗れるぬりえ。絵と色を選んでタップするだけ。塗った絵は画像で保存も印刷もできます。無料・登録不要・商用OK。", body=body)


def sitemap_images(cfg: dict, items: list[dict]) -> str:
    base = cfg["site_url"].rstrip("/")
    rows = "".join(f"<url><loc>{esc(base)}/illust/{i['id']}/</loc><image:image><image:loc>{esc(base)}/files/{i['id']}.png</image:loc><image:title>{esc(i['title'])}</image:title></image:image></url>\n" for i in items)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
            + rows + "</urlset>\n")


def feed_xml(cfg: dict, series: list[dict], today: date) -> str:
    base = cfg["site_url"].rstrip("/")
    newest = sorted(series, key=lambda s: (s["added"], s["slug"]), reverse=True)[:30]
    ents = "".join(f"<entry><title>{esc(s['title'])}</title><link href=\"{esc(base + s['url'])}\"/><id>{esc(base + s['url'])}</id><updated>{s['added']}T00:00:00+09:00</updated>"
                   f"<summary>{esc(s['lead'])}</summary></entry>\n" for s in newest)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"><title>{esc(cfg["site_name"])} 新着</title><link href="{esc(base)}/feed.xml" rel="self"/>'
            f'<link href="{esc(base)}/"/><id>{esc(base)}/</id><updated>{today.isoformat()}T00:00:00+09:00</updated>\n{ents}</feed>\n')


def search_index(items: list[dict], series: list[dict]) -> str:
    sname = {s["slug"]: s["title"] for s in series}
    rows = [[i["id"], i["title"], " ".join(i["tags"]), i["genre"], i["touch"], sname[i["series"]], i["w"], i["h"]] for i in items]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def render_site(cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    today = today or date.today()
    items, series = load_data()
    built = []
    for sp in SPECIALS:
        sers = [s for s in match_series(sp["match_series"], series) if s["items"]]
        its = [i for s in sers for i in s["items"]]
        if len(its) >= MIN_ITEMS:
            built.append((sp, sers, its))
    guides = load_guides()
    cal_files, cal_themes = build_calendars(items, today)
    pr_files, pr_kinds = build_printables(items)
    SITE["nav"] = [n for n in BASE_NAV if (built or n[1] != "/special/") and (guides or n[1] != "/guide/") and (cal_themes or n[1] != "/printables/")]
    use_files, use_live = use_pages(cfg, preview, series, built, guides)
    pose_html, pose_sets = pose_page(cfg, preview, series)
    pages: dict[str, str | bytes] = {"index.html": index_page(cfg, preview, items, series, today, [m["img"] for m in cal_themes[0]["months"][:4]] if cal_themes else None, use_live, len(pose_sets) >= 3)}
    pages.update(use_files)
    if len(pose_sets) >= 3:
        pages["pose/index.html"] = pose_html
    pages.update(illust_hub(cfg, preview, items, series))
    pages.update(genre_pages(cfg, preview, items, series))
    pages.update(touch_pages(cfg, preview, items, series))
    tags = tag_list(items)
    SITE["tags"] = set(tags)
    pages.update(tag_pages(cfg, preview, items, tags))
    pages["license/index.html"] = license_page(cfg, preview)
    pages["request/index.html"] = request_page(cfg, preview)
    pages["api/q.php"] = request_php(cfg)
    pages.update(request_data_files())
    pages["tool/card/index.html"] = tool_page(cfg, preview, items, series)
    pages["tool/nurie/index.html"] = nurie_page(cfg, preview, series)
    pages["tool/index.html"] = tools_page(cfg, preview)
    pages["tool/calendar/index.html"] = maker_page(cfg, preview, "calendar")
    pages["tool/nametag/index.html"] = maker_page(cfg, preview, "nametag")
    pages["search/index.html"] = search_page(cfg, preview)
    pages["favorites/index.html"] = favorites_page(cfg, preview)
    pages["new/index.html"] = new_page(cfg, preview, series)
    for s in series:
        if s["legacy"]:
            pages[f"category/{s['slug']}/index.html"] = category_page(cfg, preview, s, items, series)
        else:
            pages[f"series/{s['slug']}/index.html"] = series_page(cfg, preview, s, items, series, og=True, guides=guides)
            pages[f"og/{s['slug']}.webp"] = og_bytes(s["items"], (47, 208, 155))
    for sp, sers, its in built:
        pages[f"special/{sp['slug']}/index.html"] = special_page(cfg, preview, sp, sers, its, today, guides)
        pages[f"og/special-{sp['slug']}.webp"] = og_bytes(its[::max(1, len(its) // 4)], (255, 201, 60))
    if built:
        pages["special/index.html"] = specials_hub(cfg, preview, built)
    if cal_themes:
        pages.update(cal_files)
        pages.update(pr_files)
        pages["printables/index.html"] = printables_hub(cfg, preview, calendar_year(today), cal_themes, items, pr_kinds)
        for kind, rows in pr_kinds.items():
            pages[f"printables/{kind}/index.html"] = printable_page(cfg, preview, kind, rows)
        pages[f"printables/calendar-{calendar_year(today)}/index.html"] = calendar_page(cfg, preview, cal_themes, calendar_year(today), guides)
    if guides:
        pages["guide/index.html"] = guides_hub(cfg, preview, guides)
        for g in guides:
            pages[f"guide/{g['slug']}/index.html"] = guide_page(cfg, preview, g, series)
    for it in items:
        pages[f"illust/{it['id']}/index.html"] = illust_page(cfg, preview, it, items, series, guides)
        pages[f"files/{it['id']}.png"] = png_bytes(it["path"])
        pages[f"files/{it['id']}.webp"] = it["path"].read_bytes()
        for k in pdf_kinds(it):
            pages[f"files/{it['id']}-{k}.pdf"] = pdf_bytes(it["path"], k)
        pages[f"thumbs/{it['id']}.webp"] = thumb_bytes(it["path"])
    pages["data/items.json"] = search_index(items, series)
    pages["data/synonyms.json"] = json.dumps({"v": 1, "groups": synonym_groups()}, ensure_ascii=False, separators=(",", ":"))
    pages["data/assist.json"] = json.dumps(assist_data(built, guides, calendar_year(today), pr_kinds, use_live, len(pose_sets) >= 3), ensure_ascii=False, separators=(",", ":"))
    pages["feed.xml"] = feed_xml(cfg, series, today)
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="個人でも商用でも無料で使えるイラストを公開し、名前入りのカードを簡単に作れるようにすること。",
        sources_html="イラストは生成AIが制作しています。キャラクターは当サイトのオリジナルです。",
        update_text="イラストは順次追加します。",
        disclaimer_html=("<p>イラストの利用によって生じた問題について、当サイトは責任を負いません。ご利用条件は、<a href=\"/license/\">利用について</a>をご覧ください。</p>"
                         "<p>既存のキャラクター・実在の人物・特定の作家の画風をまねる指示では作っていません。似ているというご指摘があればお問い合わせください。</p>"),
        contact_notice="リクエストは、個別のお返事や納期をお約束するものではありません。",
        input_note=("<p>カードをつくる機能や、お気に入りに入力・保存した内容は、この端末のブラウザの中だけで使われ、当サイトには送信されません。</p>"
                    "<p>「リクエスト」欄に書いて送った言葉(と、選んだ使い道・タッチ)は、イラストを企画するために当サイトのサーバーに保存し、集計して使います。"
                    "住所・メールアドレス・名前は聞きません。送った人の端末や回線を特定できる情報(IPアドレスなど)は保存しません。"
                    "1日の送信回数を数えるためだけに、日ごとに変わる元に戻せない値をその日のあいだ使い、翌日に消します。"
                    "検索で見つからなかったときの「この絵をリクエストする」ボタンも同じで、ボタンを押したときだけ検索した言葉を送ります。"
                    "送った言葉は、この端末のブラウザにも「あなたのリクエスト」の表示のために記録されます(ブラウザのデータを消すとなくなります)。"
                    "個人を特定できる内容や、お受けできない内容は保存せずにお断りします。</p>")))
    pages.update(standard_files(pages, cfg, preview, today.isoformat()))
    pages["sitemap-images.xml"] = sitemap_images(cfg, items)
    if cfg.get("indexnow_key"):
        pages[f"{cfg['indexnow_key']}.txt"] = cfg["indexnow_key"]     # IndexNow (Bing and others): proves we own the site, see indexnow.py
    if not preview:
        pages["robots.txt"] = pages["robots.txt"] + f"Sitemap: {cfg['site_url'].rstrip('/')}/sitemap-images.xml\n"
    pages.update(asset_pages(HERE / "assets"))
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        files = render_site(cfg, Path(a.out), release=a.release)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
