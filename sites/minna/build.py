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
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.minna import model, printables  # noqa: E402
from sites.minna.catalog import CATEGORIES, build_catalog  # noqa: E402
from sites.minna.specials import MIN_ITEMS, SPECIALS  # noqa: E402
from sites.minna.taxonomy import GENRE_BY_SLUG, GENRES, TOUCH_BY_SLUG, TOUCHES  # noqa: E402
from sites.yorokobu import content as gift_content  # noqa: E402
from sokuhou import contactform, rakuten  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

PER_PAGE = 60
MIN_CROSS = 12          # a genre x touch page exists only with at least this many items
BASE_NAV = [("イラスト", "/illust/", "/illust/"), ("特集", "/special/", "/special/"), ("読みもの", "/guide/", "/guide/"), ("印刷", "/printables/", "/printables/"), ("カードをつくる", "/tool/card/", "/tool/"), ("リクエスト", "/request/", "/request/")]
SITE = {
    "nav": list(BASE_NAV),
    "glyph": '<img src="/assets/img/logo-mark.webp" alt="" width="36" height="36">',
    "assets": HERE / "assets",
    "source_html": "イラストは、AIで生成し、人が選んで、整えています。",
}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Mochiy+Pop+One'
         '&family=Zen+Maru+Gothic:wght@500;700;900&display=swap">\n<meta name="theme-color" content="#2fd09b">\n')
USES = {
    "animals": ["LINEやSNSの返信に", "スライドの、ひとこと解説に", "ブログの、吹き出しの横に", "保育園・学校の、おたよりに"],
    "eto": ["年賀状・ごあいさつ状に", "LINEの「あけおめ」画像に", "お店や会社の、新年のお知らせに", "保育園・学校の、1月のおたよりに"],
    "season": ["季節のお知らせに", "カード・招待状に", "店頭のポップに", "学校・園の、おたよりに"],
    "food": ["メニューやレシピに", "給食だよりに", "お店のポップに", "ブログやSNSの画像に"],
    "nature": ["季節のあいさつ状に", "メッセージカードに", "天気や行事のお知らせに", "ブログの見出しに"],
    "life": ["暮らしのお知らせに", "チェックリストや説明資料に", "引っ越し・住まいの案内に", "子ども向けの資料に"],
    "school": ["学級通信・園だよりに", "掲示物やプリントに", "学習カードやワークシートに", "新学期のお知らせに"],
    "work": ["プレゼン資料に", "チラシやサイトに", "社内だよりやマニュアルに", "提案書の図解に"],
    "people": ["自己紹介スライドに", "チームの、役割の紹介に", "アンケートや、診断の、選択肢に", "家族の、お知らせに"],
    "deco": ["写真や文字を囲むフレームに", "おたよりの見出しに", "SNS画像の飾りに", "プレゼントのカードに"],
    "icon": ["資料の、目印や強調に", "チラシ・ポスターの飾りに", "SNS画像のワンポイントに", "ウェブサイトのボタンや見出しに"],
    "shimaenaga": ["LINEやSNSの返信に", "スライドの、ひとこと解説に", "ブログの、吹き出しの横に", "動画のサムネイルに"],
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
    illust = (f'<section style="margin-top:36px"><h2><span class="scribble">この記事で使える、イラスト</span></h2>{grid(its)}'
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
<h1>読みもの</h1><p class="lead">年賀状、寒中見舞い、ぬりえ、おたより…イラストを使うときに役立つ、やさしい解説です。</p><ul class="readlist big">{cards}</ul>"""
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
SEARCH_FORM = ('<form class="hsearch" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="さがす(例: ひつじ、年賀状)" '
               'aria-label="イラストをさがす" autocomplete="off"><button type="submit" aria-label="検索">さがす</button></form>')


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    html = layout(SITE, cfg, preview, scripts=True, head_extra=FONTS, **kw)
    html = html.replace('<nav aria-label="メイン">', SEARCH_FORM + '<nav aria-label="メイン">', 1)
    return html


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
    return (f'<div class="share"><span class="share-label">このページを、教える</span>'
            f'<a class="share-btn line" href="{esc("https://line.me/R/share?text=" + quote(text + chr(10) + url, safe=""))}" target="_blank" rel="noopener">LINEで送る</a>'
            f'<a class="share-btn x" href="{esc("https://twitter.com/intent/tweet?text=" + quote(text, safe="") + "&url=" + quote(url, safe=""))}" target="_blank" rel="noopener">Xで共有</a></div>')


def licence_box() -> str:
    return ('<aside class="licence-box"><b>ずっと無料・商用OK・クレジット不要・登録不要</b><span>個人でも、会社でも、点数の制限なく使えます。'
            '加工(色や大きさを変える)もできます。くわしくは<a href="/license/">利用について</a>。</span></aside>')


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
    ("hitsuji", "ひつじ", "ふわふわのひつじと、1年を。2027年の干支(未年)にちなんだ、ひつじのカレンダー。",
     ["eto-sheep-kawaii-kagami", "sheep-pose-heart", "sheep-pose-thanks", "sheep-pose-wave", "sheep-pose-eat", "sheep-pose-sad", "sheep-pose-cheer", "sheep-pose-run",
      "sheep-pose-surprised", "sheep-pose-wink", "sheep-pose-sleep", "christmas-animals-kawaii-sheep"]),
    ("dobutsu", "どうぶつ", "毎月ちがう、かわいいどうぶつが出てくる、12か月のカレンダー。",
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
    "shojo": ("賞状テンプレート かわいい動物 無料・A4印刷", "どうぶつの賞状", "子どもに渡す賞状を、A4に印刷して使えるテンプレートです。名前・日づけ・おくる人を、手で書き入れます。",
              [("文字を入れられますか?", "手書きで書き入れる形です。名前の線、日づけ、「より」の線が空いています。"), ("どの大きさで印刷しますか?", "A4(横)です。プリンターの設定は「実際のサイズ」で、厚めの紙だと立派に仕上がります。")]),
    "nafuda": ("名札テンプレート かわいい動物 無料・A4印刷", "どうぶつの名札", "切りとって使える名札です。1ページに10枚。名前を手書きして、ラミネートしたり、安全ピンやクリップをつけたりして使えます。",
               [("何枚つくれますか?", "1ページに10枚です。同じ絵が10枚並びます。"), ("名前は書けますか?", "各名札に、名前を書く線があります。ペンで書き入れてください。")]),
    "jikanwari": ("時間割テンプレート かわいい動物 無料・A4印刷", "どうぶつの時間割", "月曜から金曜、1〜6時間目の時間割表です。教科を手書きして、机にはったり、ファイルに入れたりして使えます。",
                  [("6時間目までですか?", "はい。1〜6時間目の表です。使わない時間は空らんのままで使えます。"), ("どの大きさで印刷しますか?", "A4(横)です。プリンターの設定で「実際のサイズ」を選んでください。")]),
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
<section style="margin-top:44px"><h2><span class="scribble">よくある、しつもん</span></h2><div class="faq">{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)}</div></section>
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
    faq = [("祝日は入っていますか?", f"はい。{year}年の祝日(振替休日を含む)を、赤い字で名前つきで入れています。"),
           ("どの大きさで印刷しますか?", "A4(縦)で作っています。プリンターの設定で「実際のサイズ」または「拡大縮小なし」を選ぶと、きれいに印刷できます。"),
           ("商用で使えますか?", "はい。無料・商用OKです。お店や会社で配るカレンダーにもお使いいただけます(PDFそのものの再配布や販売はご遠慮ください)。")]
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), ("印刷", "/printables/"), (f"{year}年カレンダー", None)])}
<h1>{year}年(令和{year - 2018}年)イラストカレンダー 無料・A4で印刷できるPDF</h1>
<p class="lead">かわいいイラストつきの、{year}年のカレンダーです。1か月ずつ、または12か月まとめて、無料でダウンロードできます。祝日つき・A4縦・登録不要。</p>{licence_box()}
{secs}
<section style="margin-top:44px"><h2><span class="scribble">よくある、しつもん</span></h2><div class="faq">{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)}</div></section>
{pr_box(cfg, *PRINTABLE_PR["calendar"])}
{share(cfg, f"/printables/calendar-{year}/", f"{year}年イラストカレンダー(無料・印刷用PDF)")}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/printables/calendar-{year}/", title=f"{year}年 イラストカレンダー 無料・印刷用PDF(A4・祝日つき) | {cfg['site_name']}",
                description=f"{year}年(令和{year - 2018}年)のかわいいイラストカレンダー。A4・祝日つき・登録不要で無料ダウンロード。ひつじ、どうぶつの2種類。商用OK。", body=body,
                og_image=f"/files/calendar/{year}-{themes[0]['slug']}-01.webp")


def printables_hub(cfg, preview, year: int, themes: list[dict], items: list[dict], kinds: dict | None = None) -> str:
    nurie = [i for i in items if i["touch"] == "lineart"]
    cards = (f'<li><a class="special-card" href="/printables/calendar-{year}/"><span class="set-thumbs checker">'
             + "".join(f'<img src="{m["img"]}" alt="" width="120" height="170" loading="lazy">' for m in themes[0]["months"][:3])
             + f'</span><b>{year}年 イラストカレンダー</b><small>A4・祝日つき・{len(themes)}種類</small></a></li>')
    if nurie:
        cards += (f'<li><a class="special-card" href="/special/nurie/"><span class="set-thumbs checker">'
                  + "".join(f'<img src="/thumbs/{i["id"]}.webp" alt="" width="120" height="{round(i["h"] * 120 / i["w"])}" loading="lazy">' for i in nurie[:3])
                  + f'</span><b>ぬりえ(A4で印刷)</b><small>{len(nurie)}点・どうぶつ・お正月</small></a></li>')
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
    "nenga-tsukurikata": ("年賀状づくりに、あると便利なもの", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("年賀状向けのプリンター用紙", "年賀状 プリンター用紙"), ("プリンターのインク", "プリンター インク 純正")]),
    "nenga-2027-schedule": ("年賀状の準備に", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("宛名ラベル", "年賀状 宛名 ラベル"), ("スタンプ・はんこ", "年賀状 スタンプ 干支")]),
    "nenga-bunrei": ("年賀状に、ひとこと添えるなら", [("年賀状用のペン", "年賀状 ペン 筆ペン"), ("スタンプ・はんこ", "年賀状 スタンプ 干支")]),
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
    "nenga-2027": ("年賀状づくりに、あると便利なもの", [("年賀状の印刷サービス", "年賀状 印刷 2027"), ("プリンターのインク", "プリンター インク 純正"), ("年賀状向けのプリンター用紙", "年賀状 プリンター用紙")]),
    "nurie": ("ぬりえを楽しむ道具", [("色えんぴつ", "色えんぴつ 24色"), ("クレヨン", "クレヨン 幼児 安全"), ("ぬりえの本", "ぬりえ 本")]),
    "christmas": ("クリスマスの準備に", [("クリスマスカード用紙", "メッセージカード 用紙 A4"), ("ラッピング用品", "ラッピング 袋 クリスマス")]),
}
PRINTABLE_PR = {
    "calendar": ("カレンダーを、きれいに使うために", [("A4の厚手用紙", "A4 用紙 厚手 カラー"), ("ラミネートフィルム", "ラミネートフィルム A4"), ("カレンダー用フレーム", "A4 フォトフレーム 壁掛け")]),
    "shojo": ("賞状を、きれいに仕上げるために", [("賞状用紙", "賞状用紙 A4"), ("賞状ホルダー・額", "賞状 額縁 A4"), ("A4の厚手用紙", "A4 用紙 厚手 カラー")]),
    "nafuda": ("名札を、じょうぶにするために", [("名札ケース", "名札ケース 安全ピン"), ("ラミネートフィルム", "ラミネートフィルム 名刺サイズ"), ("ストラップ", "ネームホルダー ストラップ")]),
    "jikanwari": ("時間割を、長く使うために", [("ラミネートフィルム", "ラミネートフィルム A4"), ("下じき", "下敷き 学習"), ("クリアファイル", "クリアファイル A4")]),
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
    want = ["sheep-pose-wave", "fox-pose-proud", "eto-sheep-kawaii-kagami", "cat-pose-wave", "dog-pose-jump", "christmas-animals-kawaii-bear", "bear-pose-heart", "rabbit-pose-thanks",
            "eto-sheep-kawaii-kite", "panda-pose-eat", "penguin-pose-wave", "season-christmas", "r-joy"]
    by = {i["id"]: i for i in items}
    chosen = [by[w] for w in want if w in by][:5]
    if len(chosen) < 5:
        chosen += [i for i in items if i not in chosen][: 5 - len(chosen)]
    pos = ["a", "b", "c", "d", "e"]
    return "".join(f'<img class="hc {pos[n]}" src="/thumbs/{c["id"]}.webp" alt="{esc(c["title"])}" width="{min(c["w"], 360)}" height="{round(c["h"] * min(c["w"], 360) / c["w"])}">'
                   for n, c in enumerate(chosen))


def index_page(cfg: dict, preview: bool, items: list[dict], series: list[dict], today: date, printable_thumbs: list[str] | None = None) -> str:
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
        season_html = f'<section style="margin-top:44px"><div class="sec-head"><h2>いま使える<span class="scribble">特集</span></h2><p>季節の行事に、すぐ使えるイラストです。</p></div><ul class="special-grid">{cards}</ul></section>'
    newest = sorted(series, key=lambda s: (s["added"], s["slug"]), reverse=True)
    newest = [s for s in newest if not s["legacy"]][:8] or newest[:8]
    print_html = ""
    if printable_thumbs:
        thumbs = "".join(f'<img src="{t}" alt="" width="110" height="156" loading="lazy">' for t in printable_thumbs[:4])
        print_html = (f'<section style="margin-top:50px"><div class="sec-head"><h2>印刷して<span class="scribble">つかう</span></h2><p>カレンダー、ぬりえ、賞状、名札、時間割。A4で印刷できます。</p></div>'
                      f'<a class="print-banner" href="/printables/"><span class="print-thumbs">{thumbs}</span><b>印刷できるもの(無料・A4)</b><small>{calendar_year(today)}年のカレンダー(祝日つき)・ぬりえ・賞状・名札・時間割</small></a></section>')
    body = f"""<section class="band mint dots hero"><div class="in"><div class="hero-text"><span class="sticker">ずっと無料・商用OK・登録不要</span>
<h1><span class="nb">そのまま使える、</span><br><span class="nb"><em>かわいい</em>イラスト素材</span></h1>
<p class="lead">どうぶつ・年賀状・行事・たべもの・フレームまで、{len(items)}点。ダウンロードして、すぐに使えます。クレジット表示も、点数の制限も、ありません。</p>
<form class="hero-search" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="ひつじ、年賀状、クリスマス、ぬりえ…" aria-label="イラストをさがす" autocomplete="off"><button class="btn" type="submit">さがす</button></form>
<p class="hero-cta"><a class="btn big" href="/illust/">イラストを見る</a><a class="btn big btn-sub" href="/tool/card/">カードをつくる</a></p></div>
<div class="hero-art collage">{hero_collage(items)}</div></div></section>
{licence_box()}
{season_html}
<section style="margin-top:44px"><div class="sec-head"><h2>ジャンルから<span class="scribble">さがす</span></h2></div><ul class="genre-grid">{gtiles}</ul></section>
{print_html}
<section style="margin-top:50px"><div class="sec-head"><h2>あたらしい<span class="scribble">セット</span></h2><p>同じキャラクター・同じタッチで、そろっています。</p></div>{set_grid(newest)}
<p style="text-align:center"><a class="btn" href="/new/">新着をもっと見る</a></p></section>
<section style="margin-top:50px"><div class="sec-head"><h2>タッチから<span class="scribble">えらぶ</span></h2><p>同じ絵でも、タッチがちがうと、雰囲気が変わります。</p></div><ul class="touch-grid">{ttiles}</ul></section>
<section class="band yellow dots scallop" style="margin-top:56px"><div class="in"><div class="sec-head"><h2>名前や、ひとことを入れて、<span class="scribble">カードにする</span></h2><p>誕生日、ありがとう、お祝いのカードを、その場でつくって、画像で保存できます。</p></div>
<p style="text-align:center"><a class="btn big" href="/tool/card/">カードをつくる</a></p></div></section>
<section style="margin-top:50px"><div class="sec-head"><h2>みんなのイラストの、<span class="scribble">やくそく</span></h2></div>
<ul class="promise"><li><b>登録なし</b><span>ログインも会員登録も、いりません。</span></li><li><b>制限なし</b><span>ダウンロードの回数も、使う点数も、自由です。</span></li><li><b>商用OK</b><span>会社のチラシやお店のポップにも、使えます。</span></li><li><b>AIで生成・人が確認</b><span>AIで生成し、人が選んで、整えています。</span></li></ul></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} 商用OK・クレジット不要・登録不要の、かわいいイラスト素材",
                description="どうぶつ、年賀状(2027年・未年)、季節の行事、たべもの、フレームまで。無料・商用OK・登録不要の、かわいい透明PNGのイラスト素材。名前入りのカードも、つくれます。", body=body)


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
    head = (f'<h1>イラスト一覧</h1><p class="lead">すべて無料、商用OK、クレジット不要です。全{len(items)}点。ジャンルやタッチで、しぼりこめます。</p>'
            f'<p class="chip-label">ジャンル</p><nav class="chips">{chips}</nav><p class="chip-label">タッチ</p><nav class="chips">{tchips}</nav>')
    ordered = sorted(items, key=lambda i: (i["added"], i["id"]), reverse=True)
    return paged(cfg, preview, "/illust/", ordered, head, f"イラスト一覧 | {cfg['site_name']}",
                 "どうぶつ、年賀状、季節の行事、たべもの、フレームなど、すべてのイラストの一覧です。無料・商用OK・登録不要。", [("トップ", "/"), ("イラスト", None)])


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
        top = f'<section><h2><span class="scribble">セットでさがす</span></h2>{set_grid(sers)}</section><h2 style="margin-top:36px"><span class="scribble">すべてのイラスト</span></h2>'
        out.update(paged(cfg, preview, f"/genre/{slug}/", sorted(its, key=lambda i: (i["added"], i["id"]), reverse=True), head, f"{name}のイラスト 無料・商用OK | {cfg['site_name']}",
                         f"{desc}無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, None)], extra_top=top))
        for t, ts in touches:
            if len(ts) < MIN_CROSS:
                continue
            h = (f'<h1>{esc(name)}の{esc(t[1])}イラスト</h1><p class="lead">{esc(t[2])}{esc(name)}のイラストを、{esc(t[1])}のタッチで、{len(ts)}点そろえました。</p>{licence_box()}')
            out.update(paged(cfg, preview, f"/genre/{slug}/{t[0]}/", sorted(ts, key=lambda i: (i["added"], i["id"]), reverse=True), h, f"{name}の{t[1]}イラスト 無料・商用OK | {cfg['site_name']}",
                             f"{t[2]}{name}のイラスト{len(ts)}点。無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, f"/genre/{slug}/"), (t[1], None)]))
    return out


def touch_pages(cfg, preview, items, series) -> dict:
    out = {}
    for slug, name, desc, _ in TOUCHES:
        its = [i for i in items if i["touch"] == slug]
        if not its:
            continue
        sers = [s for s in series if s["touch"] == slug]
        head = f'<h1>{esc(name)}のイラスト</h1><p class="lead">{esc(desc)}全{len(its)}点。無料・商用OK・クレジット不要。</p>{licence_box()}'
        top = f'<section><h2><span class="scribble">セットでさがす</span></h2>{set_grid(sers)}</section><h2 style="margin-top:36px"><span class="scribble">すべてのイラスト</span></h2>'
        out.update(paged(cfg, preview, f"/touch/{slug}/", sorted(its, key=lambda i: (i["added"], i["id"]), reverse=True), head, f"{name}のイラスト 無料・商用OK | {cfg['site_name']}",
                         f"{desc}無料・商用OK・登録不要の透明PNG。", [("トップ", "/"), (name, None)], extra_top=top))
    return out


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
<p class="dl"><button type="button" class="btn big" data-zip data-name="{s['slug']}" data-files='{esc(files)}'>セットをまとめて保存(ZIP)</button> <span class="memo-note">ブラウザの中でまとめます。ログインはいりません。</span></p>
{licence_box()}{grid(s['items'])}
<section style="margin-top:44px"><h2><span class="scribble">こんなふうに、使えます</span></h2><ul class="check">{''.join(f'<li>{esc(u)}</li>' for u in USES[s['genre']])}</ul></section>
{share(cfg, s['url'], s['title'] + '(無料・商用OKのイラスト)')}
{('<section style="margin-top:44px"><h2><span class="scribble">ほかの、' + esc(g) + 'のセット</span></h2>' + set_grid(same_genre) + '</section>') if same_genre else ''}
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
    uses = "".join(f"<li>{esc(u)}</li>" for u in USES[it["genre"]])
    tags = "".join(f'<li>{esc(x)}</li>' for x in it["tags"])
    ld = json.dumps({"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": f"{base}/files/{it['id']}.png", "name": it["title"],
                     "description": it["desc"], "license": f"{base}/license/", "acquireLicensePage": f"{base}/license/",
                     "creditText": cfg["site_name"], "creator": {"@type": "Organization", "name": cfg["operator_name"]}, "width": it["w"], "height": it["h"],
                     "encodingFormat": "image/png", "keywords": ", ".join(it["tags"])}, ensure_ascii=False)
    prev_next = ""
    if len(s["items"]) > 1:
        pv, nx = s["items"][idx - 1], s["items"][(idx + 1) % len(s["items"])]
        prev_next = f'<nav class="prevnext" aria-label="同じセットの前後"><a href="/illust/{pv["id"]}/" rel="prev">← {esc(pv["title"])}</a><a href="/illust/{nx["id"]}/" rel="next">{esc(nx["title"])} →</a></nav>'
    body = f"""{crumbs([("トップ", "/"), (g, f"/genre/{it['genre']}/"), (s["title"], s["url"]), (it["title"], None)])}
<div class="detail"><div class="preview"><div class="checker big" id="bgbox"><img id="mainimg" src="/files/{it['id']}.png" alt="{esc(it['title'])}" width="{it['w']}" height="{it['h']}"></div>
<div class="bgsw" aria-label="背景の色を変えて見る"><button type="button" data-bg="" class="on">すかし</button><button type="button" data-bg="#ffffff">白</button><button type="button" data-bg="#ffc93c">黄</button><button type="button" data-bg="#ffd6e0">桃</button><button type="button" data-bg="#d9f1ff">空</button><button type="button" data-bg="#2b1b14">黒</button></div></div>
<div class="info"><h1>{esc(it['title'])}</h1><p class="lead">{esc(it['desc'])}</p>
<p class="dl"><a class="btn big" href="/files/{it['id']}.png" download="{it['id']}.png">PNG(透明)をダウンロード</a>
<a class="btn btn-sub" href="/files/{it['id']}.webp" download="{it['id']}.webp">WebP</a>
{''.join(f'<a class="btn btn-sub" href="/files/{it["id"]}-{k}.pdf" download="{it["id"]}-{k}.pdf">{"A4で印刷(PDF)" if k == "a4" else "はがきサイズで印刷(PDF)"}</a>' for k in pdf_kinds(it))}
<button class="btn btn-sub fav-big" type="button" data-fav="{it['id']}" aria-pressed="false">♡ お気に入り</button></p>
<p class="meta">サイズ: {it['w']}×{it['h']}px(透明な背景) ・ セット: <a href="{s['url']}">{esc(s['title'])}</a> ・ タッチ: <a href="/touch/{it['touch']}/">{esc(t)}</a> ・ ジャンル: <a href="/genre/{it['genre']}/">{esc(g)}</a></p>
<details class="export" data-src="/files/{it['id']}.png" data-name="{it['id']}"><summary>背景や大きさを変えて保存する</summary>
<div class="export-row"><label>形式<select name="fmt"><option value="png">PNG</option><option value="jpg">JPG(背景つき)</option></select></label>
<label>背景<select name="bg"><option value="">透明</option><option value="#ffffff">白</option><option value="#ffc93c">黄</option><option value="#ffd6e0">桃</option><option value="#d9f1ff">空</option><option value="#d7f7ea">ミント</option></select></label>
<label>大きさ<select name="size"><option value="orig">そのまま</option><option value="sq1080">正方形 1080px(SNS・アイコン)</option><option value="wide">ヨコ 1280×720(サムネイル)</option><option value="hagaki">はがき(縦)300dpi</option></select></label></div>
<p><button type="button" class="btn" data-export>この設定で保存</button> <button type="button" class="btn btn-sub" data-copy>画像をコピー</button> <span class="memo-note" role="status" aria-live="polite" data-export-msg></span></p></details>
{licence_box()}
<p class="ai-note">このイラストは、AIで生成し、人が選んで、整えたものです。</p></div></div>
{prev_next}
<section><h2><span class="scribble">こんなふうに、使えます</span></h2><ul class="check">{uses}</ul></section>
<section><h2><span class="scribble">キーワード</span></h2><ul class="tagcloud">{tags}</ul></section>
{share(cfg, f"/illust/{it['id']}/", f"{it['title']}(無料・商用OKのイラスト)")}
<section style="margin-top:44px"><h2><span class="scribble">おなじセットの、イラスト</span></h2>{grid(mates)}</section>
{('<section style="margin-top:44px"><h2><span class="scribble">ほかの、' + esc(g) + 'のイラスト</span></h2>' + grid(others) + '</section>') if others else ''}
{guide_box(guides_for(it['genre'], it['touch'], list(guides)))}
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/illust/{it['id']}/", title=f"{it['title']} 無料・商用OKのイラスト | {cfg['site_name']}",
                description=f"{it['desc']}{t}のタッチ。無料・商用OK・クレジット不要の透明PNG。"[:150], body=body, og_image=f"/thumbs/{it['id']}.webp")


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
<section><h2><span class="scribble">つかいかた</span></h2><ol class="howto">{steps}</ol></section>
{sections}
{guide_box(guides_for('eto' if sp['slug'] == 'nenga-2027' else 'season', 'kawaii', list(guides), 3))}
<section style="margin-top:44px"><h2><span class="scribble">よくある、しつもん</span></h2><div class="faq">{faq}</div></section>
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
<h1>新着のセット</h1><p class="lead">あたらしく追加したイラストのセットです。</p>{set_grid(newest[:60])}"""
    return page(cfg, preview, path="/new/", title=f"新着のイラスト | {cfg['site_name']}", description="あたらしく追加したイラストのセットです。無料・商用OK・登録不要。", body=body)


def search_page(cfg, preview) -> str:
    gopts = '<option value="">ジャンル: すべて</option>' + "".join(f'<option value="{g[0]}">{esc(g[1])}</option>' for g in GENRES)
    topts = '<option value="">タッチ: すべて</option>' + "".join(f'<option value="{t[0]}">{esc(t[1])}</option>' for t in TOUCHES)
    body = f"""{crumbs([("トップ", "/"), ("さがす", None)])}
<h1>イラストをさがす</h1>
<form class="search-app" id="search-app" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="ひつじ、年賀状、クリスマス、ぬりえ…" aria-label="キーワード" autocomplete="off">
<select name="g" aria-label="ジャンル">{gopts}</select><select name="t" aria-label="タッチ">{topts}</select><button class="btn" type="submit">さがす</button></form>
<p class="memo-note" id="search-status" role="status" aria-live="polite">キーワードを入れてください。ひらがな・カタカナは、どちらでも見つかります。</p>
<ul class="illust-grid" id="search-results" aria-live="polite"></ul>
<p style="text-align:center"><button class="btn" type="button" id="search-more" hidden>もっと見る</button></p>
<noscript><p class="notice">さがす機能には、JavaScript が必要です。<a href="/illust/">イラスト一覧</a>からも、探せます。</p></noscript>"""
    return page(cfg, preview, path="/search/", title=f"イラストをさがす | {cfg['site_name']}", description="キーワードで、イラストをさがせます。ジャンルやタッチでも、しぼりこめます。", body=body)


def favorites_page(cfg, preview) -> str:
    body = f"""{crumbs([("トップ", "/"), ("お気に入り", None)])}
<h1>お気に入り</h1><p class="lead">♡を押したイラストが、ここに並びます。この端末のブラウザの中だけに保存され、送信はされません。</p>
<p class="memo-note" id="fav-status" role="status" aria-live="polite"></p>
<ul class="illust-grid" id="fav-results" aria-live="polite"></ul>"""
    return page(cfg, preview, path="/favorites/", title=f"お気に入り | {cfg['site_name']}", description="お気に入りに入れたイラストの一覧です。この端末の中だけに保存されます。", body=body)


def license_page(cfg: dict, preview: bool) -> str:
    body = f"""{crumbs([("トップ", "/"), ("利用について", None)])}
<h1>利用について(ライセンス)</h1>
<p class="lead">{esc(cfg['site_name'])}のイラストは、<b>個人でも、会社でも、無料で、ご利用いただけます</b>。使う前の連絡や、クレジット表示は、いりません。会員登録も、ダウンロード回数の制限も、ありません。</p>
<h2><span class="scribble">できること</span></h2><ul class="check"><li>商用利用(チラシ、商品の説明、広告、動画、書籍、アプリ、年賀状、お店のポップなど)</li><li>点数の制限なしで、何点でも使うこと</li>
<li>大きさ、色、向きを変えたり、文字や、ほかの画像と、組み合わせたりすること</li><li>SNSやLINEで、画像として、共有すること</li><li>印刷して配ること(年賀状、おたより、掲示物など)</li></ul>
<h2><span class="scribble">お願い</span></h2><ul class="warn"><li>イラストそのものを、素材集として、配布・販売することは、できません(加工して、ほかの作品に使うのは、問題ありません)。</li>
<li>イラストを、商標として登録したり、「自分のキャラクター」として、権利を主張したりすることは、ご遠慮ください。</li>
<li>LINEスタンプなど、イラストが主役の商品として、そのまま販売することは、ご遠慮ください。</li>
<li>人を、傷つける内容、法律や公序良俗に反する内容に、使うことは、できません。</li></ul>
<h2><span class="scribble">AIで作ったイラストについて</span></h2>
<p>このサイトのイラストは、<b>AIで生成し、人が選んで、整えたもの</b>です。AIで生成したものは、法律上、著作物として扱われない場合があるため、ここでは、「著作権が、当サイトに帰属する」とは、書かず、<b>利用の許諾</b>として、上の内容をお約束します。</p>
<p>既存のキャラクターや、実在の人物、特定の作家の画風を、まねる指示では、作っていません。万一、似ているというご指摘があれば、<a href="/contact/">お問い合わせ</a>ください。速やかに、確認して、必要な場合は、取り下げます。</p>
<h2><span class="scribble">保証について</span></h2>
<p>イラストの利用によって生じた問題について、当サイトは、責任を負いません。第三者の権利を、侵害しないことの、保証もできません。ご自身の判断で、ご利用ください。</p>"""
    return page(cfg, preview, path="/license/", title=f"利用について(ライセンス) 商用OK・クレジット不要 | {cfg['site_name']}",
                description="個人も商用も無料、クレジット表示も、登録も、点数の制限も、ありません。できること、お願い、AIで作ったイラストの扱いを、説明します。", body=body)


def request_page(cfg: dict, preview: bool) -> str:
    form = contactform.form_html(cfg, default_kind="イラストのリクエスト", message_hint="例: ひつじが、お正月に、こたつでみかんを食べているイラスト。年賀状に使いたいです。", page_hint=False)
    body = f"""{crumbs([("トップ", "/"), ("リクエスト", None)])}
<h1>こんなイラストが、ほしい</h1>
<p class="lead">「こんな動物の、こんなポーズが、ほしい」「こんな場面の、イラストが、ほしい」というご希望を、お聞かせください。</p>
<p>いただいたご希望は、ほかの方にも、役に立つものを、選んで、順番に、イラストにして、公開します(個別のお返事や、納期のお約束は、できません)。</p>
<ul class="check"><li>どんなモチーフか(動物・食べ物・行事など)</li><li>どんなポーズ・場面か</li><li>何に使いたいか(年賀状・スライド・LINE・チラシなど)</li></ul>
{form}
<p class="notice">既存のキャラクターや、実在の人物、特定の作家の画風を、まねるご希望は、お受けできません。</p>"""
    return page(cfg, preview, path="/request/", title=f"イラストのリクエスト | {cfg['site_name']}", description="こんなイラストがほしい、というご希望を送れます。", body=body)


def tool_page(cfg: dict, preview: bool, items: list[dict], series: list[dict]) -> str:
    chars = [{"id": i["id"], "title": i["title"], "src": f"/files/{i['id']}.png", "g": series_of(i, series)["title"]}
             for i in items if i["genre"] in ("animals", "shimaenaga", "eto") and i["touch"] in ("kawaii", "wa") and not i["id"].startswith(("event-", "person-"))]
    data = esc(json.dumps({"chars": chars}, ensure_ascii=False, separators=(",", ":")))
    groups: dict[str, list[dict]] = {}
    for c in chars:
        groups.setdefault(c["g"], []).append(c)
    opts = "".join(f'<optgroup label="{esc(g)}">' + "".join(f'<option value="{c["id"]}">{esc(c["title"])}</option>' for c in cs) + "</optgroup>" for g, cs in groups.items())
    body = f"""{crumbs([("トップ", "/"), ("カードをつくる", None)])}
<h1>名前入りの、カードをつくる</h1><p class="lead">名前とひとことを入れて、かわいいどうぶつのカードを、画像で保存できます。入力した内容は、この端末の中だけで、使われます(送信されません)。</p>
<section id="card-app" class="card-app" data-json="{data}">
<div class="card-form"><label>カードの種類<select name="tpl"><option value="birthday">誕生日</option><option value="thanks">ありがとう</option><option value="congrats">おめでとう</option><option value="cheer">おうえん</option><option value="newyear">あけましておめでとう</option></select></label>
<label>あて名(だれに)<input type="text" name="to" maxlength="14" placeholder="例: ハナコさん"></label>
<label>ひとこと<textarea name="msg" maxlength="60" rows="3" placeholder="例: いつも ありがとう。今日は ゆっくり してね。"></textarea></label>
<label>名前(だれから)<input type="text" name="from" maxlength="14" placeholder="例: タロウ"></label>
<label>キャラクター<select name="char">{opts}</select></label>
<label>いろ<select name="color"><option value="#ffc93c">たまご色</option><option value="#ffd6e0">さくら色</option><option value="#d9f1ff">空色</option><option value="#d7f7ea">ミント色</option></select></label>
<p class="dl"><button type="button" class="btn big" data-save>画像として保存</button></p><p class="memo-note">スマホで、保存できないときは、下の画像を、長押ししてください。</p></div>
<div class="card-preview"><canvas width="1080" height="1350" aria-label="カードのプレビュー"></canvas><img class="card-img" alt="できあがったカード" hidden></div></section>
{licence_box()}"""
    return page(cfg, preview, path="/tool/card/", title=f"名前入りカードをつくる 無料・保存OK | {cfg['site_name']}",
                description="名前とひとことを入れて、どうぶつのカードを画像で保存。誕生日・ありがとう・おめでとう・あけおめ。無料で、すぐにつくれます。", body=body)


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
    pages: dict[str, str | bytes] = {"index.html": index_page(cfg, preview, items, series, today, [m["img"] for m in cal_themes[0]["months"][:4]] if cal_themes else None)}
    pages.update(illust_hub(cfg, preview, items, series))
    pages.update(genre_pages(cfg, preview, items, series))
    pages.update(touch_pages(cfg, preview, items, series))
    pages["license/index.html"] = license_page(cfg, preview)
    pages["request/index.html"] = request_page(cfg, preview)
    pages["tool/card/index.html"] = tool_page(cfg, preview, items, series)
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
    pages["feed.xml"] = feed_xml(cfg, series, today)
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="個人でも商用でも、無料で、使えるイラストを、公開し、名前入りのカードを、かんたんにつくれるようにすること。",
        sources_html="イラストは、AIで生成し、人が選んで、整えたものです。キャラクターは、当サイトのオリジナルです。",
        update_text="イラストは、順次、追加します。",
        disclaimer_html=("<p>イラストの利用によって生じた問題について、当サイトは責任を負いません。ご利用条件は、<a href=\"/license/\">利用について</a>をご覧ください。</p>"
                         "<p>既存のキャラクター・実在の人物・特定の作家の画風を、まねる指示では、作っていません。似ているというご指摘があれば、お問い合わせください。</p>"),
        contact_notice="リクエストは、お約束のお返事や、納期を、お約束するものではありません。",
        input_note="<p>カードをつくる機能や、お気に入りに入力・保存した内容は、この端末のブラウザの中だけで使われ、当サイトには、送信されません。</p>"))
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
