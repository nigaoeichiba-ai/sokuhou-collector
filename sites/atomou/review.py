"""The review build: a small, finished-looking content site for the ad and affiliate reviews, reachable but not findable by the public.

    python sites/atomou/build.py --review --out <dir>        (the deploy job uses it while the repository variable ATOMOU_REVIEW is "true")

What it is: the home page, the six genre pages, one explanation page per event (the pages that will rank in search), and the legal pages (operator
information, privacy, contact).  What it is not: nothing of the application.  No saving of days, no calendar, no notices, no members, no skins, no
manual, no scripts but the one that recounts the days on the cards.  The wording says nothing about what is coming.
Not findable: every page carries noindex,nofollow, robots.txt shuts out every crawler except Google's AdSense one (Mediapartners-Google), there is no
sitemap, and nothing links to the site.  Not behind a password, because a review crawler cannot log in.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from sites.atomou import articles, build as B, catalog, skins
from sokuhou.sitekit import asset_pages, crumbs, esc, layout, legal_pages, standard_files

NAME = B.NAME
TAGLINE = "公式の日付まで、あと何日"
LEAD = ("試験、締切、制度の変更、大会、天文、お祭りなど、公式に決まっている日付を、出典と確認した日をつけて集めています。"
        "それぞれの日まで、あと何日かが一目で分かります。")
ALLOWED_ASSETS = {"assets/style.css", "assets/core.js", "assets/review.js", "assets/wordmark.svg", "assets/og.png", "assets/favicon.ico", "assets/favicon-32.png",
                  "assets/apple-touch-icon.png", "assets/icon-192.png", "assets/icon-512.png", "favicon.ico", "apple-touch-icon.png"}
ROBOTS = ("# a review copy: not for search engines.  Google's AdSense crawler may read it.\n"
          "User-agent: Mediapartners-Google\nDisallow:\n\nUser-agent: *\nDisallow: /\n")


class ReviewCtx(B.Ctx):
    def __init__(self, cfg: dict, today: date, entries: list[dict]):
        super().__init__(cfg, False, today, entries, skins.css())
        basic_css = skins.css().split("\n", 1)[0]
        self.head = (f'<style>{basic_css}</style>\n<style>.hero{{padding:1.4rem 0 .4rem}}.hero h1{{font-size:1.7rem;font-weight:800;color:var(--text);line-height:1.4}}</style>\n'
                     '<meta name="theme-color" content="#ffffff">\n')
        self.tail = '<script src="/assets/core.js" defer></script>\n<script src="/assets/review.js" defer></script>\n'
        genres = [(g, f"/c/{B.GROUP_SLUG[g]}/") for g in catalog.GROUPS]
        self.site = dict(B.SITE)
        self.site["nav"] = [(g, u, u) for g, u in genres]
        self.site["source_html"] = ("公式の日付は、出典と確認した日つきで載せています。 "
                                    + " | ".join(f'<a href="{u}">{esc(g)}</a>' for g, u in genres))

    def finish(self, html: str, kind: str, noindex: bool = False) -> str:
        html = html.replace("</head>", '<meta name="robots" content="noindex,nofollow">\n' + self.head + "</head>", 1)
        html = html.replace("<body>", f'<body data-page="{kind}">', 1)
        html = re.sub(r'<span class="logo" aria-hidden="true"></span>[^<]*</a>', lambda _m: B.WORDMARK + "</a>", html, count=1)
        return html.replace("</body>", self.tail + "</body>", 1)


def home_page(c: ReviewCtx, live: list[dict]) -> str:
    soon = B.diverse([e for e in live if not e["quiet"]], 12)
    genres = "".join(
        f'<a class="uc" href="/c/{B.GROUP_SLUG[g]}/"><b>{esc(g)}</b><span>{esc(B.GROUP_LEAD[g])}</span></a>' for g in catalog.GROUPS)
    body = f"""<section class="hero"><h1>{esc(NAME)}</h1><p class="lead">{esc(LEAD)}</p></section>
<h2>もうすぐの日</h2>
<div class="cards">{"".join(B.card_html(e) for e in soon)}</div>
<h2>ジャンルから探す</h2>
<div class="uc-grid">{genres}</div>
<h2>このサイトについて</h2>
<p>「あと何日」を知りたい日付は、人によって違います。受験や資格試験の日、年末の手続きの締切、好きな大会や番組、観たい天体、行きたいお祭り。
その日付を、官公庁や主催者などの公式な発表から集めて、日ごとに「どんな日か」「いつ、どこで」「何を確かめておくとよいか」を、一つずつ解説しています。</p>
<p>日付は変更や中止になることがあります。どの日付にも、出典のページと、確認した日を載せています。申し込みや手続きの前には、出典の公式ページで最新の情報をご確認ください。
誤りを見つけた場合は、<a href="/contact/">お問い合わせ</a>からお知らせください。</p>"""
    return c.page("/", f"{NAME}|{TAGLINE}", f"{LEAD}", body, "home")


def category_page(c: ReviewCtx, group: str, live: list[dict]) -> str:
    rows = [e for e in live if e["group"] == group][:200]
    body = f"""{crumbs([("トップ", "/"), (group, None)])}
<h1>{esc(group)}の日付</h1>
<p class="lead muted">{esc(B.GROUP_LEAD[group])}</p>
<div class="cards">{"".join(B.card_html(e) for e in rows)}</div>"""
    if not rows:
        body = body.replace('<div class="cards"></div>', '<p class="empty">いまは日付がありません。</p>')
    return c.page(f"/c/{B.GROUP_SLUG[group]}/", f"{group}の日付一覧 | {NAME}", f"{B.GROUP_LEAD[group]}あと何日かが一目で分かります。", body, "category")


def event_page(c: ReviewCtx, e: dict, live: list[dict], guides: dict[str, dict]) -> str:
    today = c.today
    d = date.fromisoformat(e["date"])
    n = (d - today).days
    word = "今日です" if n == 0 else (f"あと{n}日です" if n > 0 else f"もう{-n}日です")
    fmt = B.fmt_date(e["date"], e["precision"])
    end = f"〜{B.fmt_date(e['date_end'])}" if e.get("date_end") else ""
    guide = guides.get(e["subject"])
    art = articles.article_html(e, B.fmt_date, B.host(e["source_url"]), today, guide)
    if not art:
        art = f"<p>{esc(e['title'])}は、{esc(fmt)}{esc(end)}です。{today.year}年{today.month}月{today.day}日の時点で、{word}。</p>"
    others = [r for r in live if r["id"] != e["id"] and not r["quiet"]]
    same = sorted((r for r in others if r["subject"] == e["subject"]), key=lambda r: (r["date"], r["id"]))[:6]
    kin = [r for r in others if r["group"] == e["group"] and r not in same][:4]
    near = sorted((r for r in others if r["precision"] == "day" and e["precision"] == "day" and r not in same and r not in kin
                   and abs((date.fromisoformat(r["date"]) - d).days) <= 10), key=lambda r: (abs((date.fromisoformat(r["date"]) - d).days), r["date"], r["id"]))[:4]
    quote = f"<dt>出典の文</dt><dd>{esc(e['source_quote'])}</dd>" if e.get("source_quote") else ""

    def block(head: str, rows: list[dict], hint: str = "") -> str:
        return f'<h2>{head}</h2>{hint}<div class="cards">' + "".join(B.card_html(r) for r in rows) + "</div>" if rows else ""

    body = crumbs([("トップ", "/"), (e["group"], f"/c/{B.GROUP_SLUG[e['group']]}/"), (e["title"], None)]) + f"""
<h1>{esc(e['title'])}</h1>
{B.card_html(e, big=True, link=False)}
<p class="small muted">上のカードは、今日の日付で数えた数字です。</p>
{art}
<h2>出典と確認した日</h2>
<dl class="info"><dt>出典</dt><dd><a href="{esc(e['source_url'])}" rel="noopener nofollow" target="_blank">{esc(B.host(e['source_url']))}</a></dd>
<dt>確認した日</dt><dd>{esc(e['checked_on'])}</dd>{quote}</dl>
<p class="small muted">日付は変わることがあります。申し込みや手続きの前に、出典の公式ページでご確認ください。</p>
{block(f'同じ「{esc(e["subject"])}」の日', same)}
{block('同じジャンルの日', kin)}
{block('同じ頃の日', near, '<p class="hint">この日の前後10日にある日です。</p>')}"""
    place = (e.get("place") or "").strip()
    desc = (f"{e['title']}は{fmt}{end}" + (f"、{place}" if place and place not in ("全国", "地域") else "") + "。"
            + (f"{guide['about'].split('。')[0]}。" if guide else "") + "出典と確認した日つき。")
    suffix = "からもう何日？" if e["status"] == "ended" else "はいつ？あと何日？"
    return c.page(f"/e/{e['id']}/", f"{e['title']}{suffix} {fmt} | {NAME}", desc, body, "event")


def legal(c: ReviewCtx) -> dict:
    return legal_pages(
        c.site, c.cfg, False,
        purpose="試験・締切・大会・天文・お祭りなど、公式に決まっている日付を、出典と確認した日をつけてまとめ、あと何日かをわかりやすく示すこと。",
        sources_html="各日付のページに、出典(官公庁・主催者の公式ページ)と確認した日を載せています。",
        update_text="公式の発表をもとに、随時確認・追加します。",
        disclaimer_html="<p>日付は公式の発表をもとに確認していますが、変更・中止されることがあります。申し込みや手続きの前に、出典の公式ページでご確認ください。当サイトの情報にもとづく行動の結果について、責任を負いかねます。</p>"
                        "<p>「あと○日」「もう○日」は、お使いの端末の日付をもとにブラウザの中で数えています。端末の日付がずれていれば、数字もずれます。</p>",
        contact_notice="日付の誤りのご指摘は、ページの名前と、正しい日付の出典(アドレス)を添えていただけると早く確認できます。",
        finish=lambda html: c.finish(html, "legal"),
    )


def build_pages(cfg: dict, today: date | None = None) -> dict:
    today = today or date.today()
    B._TODAY = today
    entries, _rejects = catalog.build_catalog(today)
    c = ReviewCtx(cfg, today, entries)
    live = B.live_entries(entries, today)
    guides = articles.load_guides()
    old = B._ACTIONS
    B._ACTIONS = False      # cards without "add to my days": there is no application here
    try:
        pages: dict[str, str | bytes] = {"index.html": home_page(c, live)}
        for g in catalog.GROUPS:
            pages[f"c/{B.GROUP_SLUG[g]}/index.html"] = category_page(c, g, live)
        for e in entries:
            pages[f"e/{e['id']}/index.html"] = event_page(c, e, live, guides)
        pages.update(legal(c))
    finally:
        B._ACTIONS = old
    pages.update({k: v for k, v in asset_pages(B.SITE["assets"]).items() if k in ALLOWED_ASSETS})
    files = standard_files({k: 1 for k in pages if k.endswith("index.html")}, cfg, False, today.isoformat())
    pages["robots.txt"] = ROBOTS     # not the shared one: it does not mention the sitemap, and shuts out everything but the AdSense crawler
    for k in (".htaccess", "ads.txt", "sitemap.xml") + tuple(k for k in files if k.startswith("google")):   # the sitemap is only for the deploy checks; no crawler is pointed at it
        if k in files:
            pages[k] = files[k]
    pages[".htaccess"] = pages[".htaccess"] + B.HT_CACHE
    # the "preview" robots rules inside the shared .htaccess are not used here: no password, so a review crawler can read the pages
    return pages
