"""あと何日、もう何日 (atomou.com): register a date and see "あと○日 / もう○日"; verified official dates can be saved in one tap.

    python sites/atomou/build.py [--release] [--out DIR] [--today YYYY-MM-DD]

Static pages plus a small browser app (assets/app.js).  Personal days never leave the visitor's browser (localStorage); the server only ships
assets/catalog.json (the verified public dates, from data/atomou/seed_*.json through catalog.py).  Counting happens in the browser from the device's
calendar date, so the pages stay correct without a daily rebuild; the static markup carries the date, source and a "as of the build day" sentence.
A build without --release is a preview (noindex, robots.txt disallows everything).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog, datecore, skins, usecases  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, asset_version, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

NAME = "あと何日、もう何日"
CATCH = "忘れたくない日を、お知らせします。"
SLUGS = ["deadline", "sale", "events", "exams", "hobby", "festival"]
GROUP_SLUG = dict(zip(catalog.GROUPS, SLUGS))
GROUP_LEAD = {
    "締切・制度": "確定申告、年金、ふるさと納税、法律の施行日など、すぎると損をする日。",
    "消費・セール": "年賀状、大型セール、ポイントの期限、サービス終了など、暮らしのお金に関わる日。",
    "大会・番組": "野球、サッカー、駅伝、相撲、音楽番組など、楽しみにしている日。",
    "試験・資格": "大学入試、高校入試、資格試験、就活、奨学金の締切。",
    "マニア・天文": "流星群、日食、鉄道、即売会、ゲーム・アニメなど、好きな人の日。",
    "地域のお祭り": "祭り、花火、イルミネーション、紅葉、初詣など、行きたい日。",
}
POPULAR = ["年賀状", "ふるさと納税", "共通テスト", "流星群", "紅白", "コミケ", "最低賃金", "確定申告", "ドラフト"]
SITE = {
    "nav": [("さがす", "/search/", "/search/"), ("カレンダー", "/calendar/", "/calendar/"), ("記録する", "/add/", "/add/"), ("マイページ", "/my/", "/my/")],
    "glyph": "",
    "assets": HERE / "assets",
    "source_html": '日付は、公式の発表などで確認しています。あなたが記録した日は、この端末の中だけに保存されます。<a href="/manual/">使い方(説明書)</a> | <a href="/use/">こんな時に</a> | <a href="/skins/">きせかえ</a>',
}
WD = "月火水木金土日"
_TODAY = date.today()   # set by build_pages: the date the static counts on the cards are worked out for (the browser recounts at once)
# the one pattern a statistics key must match: assets/app.js (STAT_RE), api/e.php (from stats_receiver.php.tpl) and tests/test_atomou_build.py all use it
STAT_KEY_RE = r"^(view|skin|big|home_order|home_hidden|act)(:[a-z0-9_,-]{1,60}){1,2}$"


# ---------- shared helpers ----------
HT_CACHE = """
# assets carry ?v=<hash> in their URLs, so they can be kept for a year; pages are always asked for again
<IfModule mod_headers.c>
<FilesMatch "\\.(css|js|json|svg|png|webp|ico)$">
Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
<FilesMatch "(sw\\.js|manifest\\.webmanifest)$">
Header set Cache-Control "no-cache"
</FilesMatch>
</IfModule>
<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/css application/javascript text/javascript application/json image/svg+xml application/manifest+json
</IfModule>
AddType application/manifest+json .webmanifest
"""


HTPASSWD_PLACEHOLDER = "__HTPASSWD__"
DEMO_AUTH = (
    "# demo: nobody gets in without the password (the deploy job writes the password file outside public_html and fills in its path)\n"
    'AuthType Basic\nAuthName "atomou demo"\n'
    f"AuthUserFile {HTPASSWD_PLACEHOLDER}\nRequire valid-user\n"
)


def stats_php() -> str:
    return (HERE / "stats_receiver.php.tpl").read_text(encoding="utf-8").replace("__RE__", "/" + STAT_KEY_RE + "/")


STATS_SECTION = '<h2 id="stats">利用状況の統計</h2>\n<p>画面の使われ方を知って、使いやすくするために、件数だけの統計を取ります。送るのは、あらかじめ決めた項目の件数です。たとえば、「どのページが開かれたか」「選ばれたきせかえ」「ホームのブロックの並び方・非表示にされたブロック」「保存やカレンダーのボタンが押された回数」「検索で見つかったか、見つからなかったか(検索した言葉は送りません)」です。</p>\n<p>名前・日付・メモ・メールアドレス・検索した言葉・端末を識別する番号は、送りません。Cookie は使いません。サーバーには、1日ごとの合計の件数だけを保存します(同じ人かどうかは、分かりません)。送りすぎを防ぐため、アドレスから作った1日だけ有効な符号を、回数の制限にだけ使い、翌日以降に削除します。</p>\n<p>マイページの「利用状況の統計に協力する」で、いつでも止められます。ブラウザの「トラッキングしない」(DNT・Global Privacy Control)の設定がオンのときは、初めから止まっています。</p>'
GOOGLE_SECTION = '<h2 id="google">Google アカウントでの引き継ぎ(任意)</h2>\n<p>マイページの「Google アカウントでつないで同期する」を押したときだけ、Google の画面が開きます。許可するのは、あなた自身の Google ドライブの中にある、このサイト専用の非表示フォルダ(アプリデータ)への保存だけです。記録した日・保存した日・設定を、そこに保存し、別の端末で読み込めます。当サイトのサーバーには送りません。当サイトは、あなたの Google アカウントの氏名やメールアドレスを取得しません。</p>\n<p>つなぐのをやめるときは、<a href="https://myaccount.google.com/permissions" rel="noopener" target="_blank">Google アカウントの権限の管理</a>から、「あと何日、もう何日」の権限を削除してください。</p>'


def fmt_date(iso: str, precision: str = "day") -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    if precision == "year":
        return f"{y}年ごろ"
    if precision == "month":
        return f"{y}年{m}月ごろ"
    return f"{y}年{m}月{d}日({WD[date(y, m, d).weekday()]})"


def host(url: str) -> str:
    h = urlparse(url).hostname or ""
    return h[4:] if h.startswith("www.") else h


def live_entries(entries: list[dict], today: date) -> list[dict]:
    """Not finished as seen from `today`, soonest first (app.js liveFrom)."""
    out = []
    for e in entries:
        if e["status"] == "ended":
            continue
        if (e.get("date_end") or e["date"]) >= today.isoformat():
            out.append(e)
    return sorted(out, key=lambda e: (e["date"], e["title"]))


def diverse(pool: list[dict], n: int) -> list[dict]:
    """The soonest of each genre first, so the first screen is not one kind of date (app.js diverse)."""
    per = -(-n // len(catalog.GROUPS))
    pick, seen = [], {}
    for e in pool:
        seen.setdefault(e["group"], 0)
        if seen[e["group"]] < per and len(pick) < n:
            seen[e["group"]] += 1
            pick.append(e)
    for e in pool:
        if len(pick) < n and e not in pick:
            pick.append(e)
    return sorted(pick, key=lambda e: e["date"])


def count_parts(iso: str, precision: str) -> tuple[str, str, str, str, str]:
    """(direction, word, number, relative word, total) as app.js fillCard works them out, for the static markup."""
    r = datecore.countdown(date.fromisoformat(iso), _TODAY, precision)
    big = r["big"]
    word = big[:2] if big[:2] in ("あと", "もう") else ""
    t = r.get("total")
    rel = {1: "(明日)", 2: "(明後日)", -1: "(昨日)", -2: "(おととい)"}.get(t, "") if precision == "day" and t is not None else ""
    return r["dir"], word, big[len(word):], rel, (f"合計 {r['sub']}" if r.get("sub") else "")


def card_html(e: dict, *, own: bool = False, actions: bool = True, big: bool = False, link: bool = True) -> str:
    """The card markup; app.js cardHtml builds the same thing (tests/test_atomou_build.py compares the class lists).
    No source line here: the source and the check date are on the detail page ("詳細")."""
    g = catalog.GROUPS.index(e["group"]) + 1 if e.get("group") in catalog.GROUPS else int(e.get("g") or 0)
    key = ("m:" if own else "c:") + e["id"]
    p = e.get("precision") or "day"
    cls = "card" + (" quiet" if e.get("quiet") else "") + (" big" if big else "")
    direction, word, num, rel, sub = count_parts(e["date"], p)
    h = [f'<article class="{cls}" data-key="{esc(key)}" data-title="{esc(e["title"])}" data-date="{esc(e["date"])}" data-p="{p}" data-dir="{direction}" data-long="{1 if len(num) > 5 else 0}"'
         + (f' data-g="{g}"' if g else "") + (f' data-cat="{esc(e["category"])}"' if e.get("category") else "") + ">"]
    subject = e.get("subject") or (e.get("category") if not own else None) or e["kind"]
    what = e.get("what") or (e.get("kind") if not own else None)
    place = e.get("place") if e.get("place") is not None else (e.get("region") if not own else None)
    h.append('<div class="c-top">' + (f'<span class="mark m{g}" data-g="{g}" aria-hidden="true"></span>' if g else "")
             + f'<span class="badge">{esc(subject if not own else e["kind"])}</span>' + (f'<span class="what">{esc(what)}</span>' if what and not own else "") + "</div>")
    h.append(f'<p class="c-count"><span class="word">{word}</span><span class="num">{esc(num)}</span><span class="rel">{rel}</span></p><p class="c-sub">{esc(sub)}</p>')
    title = esc(e["title"])
    linked = '<a href="/e/' + e["id"] + '/">' + title + "</a>" if link and not own else title
    h.append(f'<h3 class="c-title">{linked}</h3>')
    pl = f'<span class="pl"><b>場所</b>{esc(place)}</span>' if place and place != "全国" and not own else ""
    h.append(f'<p class="c-date">{esc(fmt_date(e["date"], p))}{" " + esc(e["kind"]) if not own and e.get("kind") else ""}{pl}</p>')
    if own:
        h.append('<div class="c-next"></div>')
    if actions:
        if own:
            a = f'<a class="btn small" href="/plan/?key={esc(key)}">開く</a><button type="button" class="btn small ghost" data-act="del">消す</button>'
        else:
            a = '<button type="button" class="btn small" data-act="save" aria-pressed="false">☆ 予定に入れる</button>' + ("" if big else f'<a class="btn small ghost" href="/e/{e["id"]}/">詳細</a>')
        h.append('<div class="c-act">' + a + "</div>")
        h.append('<div class="c-move"><button type="button" class="mini grip" data-act="grip" aria-label="つかんで動かす">⠿</button>'
                 '<button type="button" class="mini" data-act="up" aria-label="ひとつ前へ">↑</button><button type="button" class="mini" data-act="down" aria-label="ひとつ後ろへ">↓</button></div>')
    h.append("</article>")
    return "".join(h)


def mark_html(i: int) -> str:
    return f'<span class="mark m{i}" data-g="{i}" aria-hidden="true"></span>'


BUNDLE = ('core', 'ics', 'app', 'plan', 'quick', 'guide')   # one script instead of six requests; the sources stay separate files


# ---------- site-wide wrapping (skins, scripts, body tag) ----------
def _wordmark() -> str:
    """assets/wordmark.svg (made by atomou/design/logo/make_wordmark.py from the outlines of Noto Sans JP, SIL OFL) inlined, its colours as variables a skin may set."""
    f = HERE / "assets" / "wordmark.svg"
    svg = f.read_text(encoding="utf-8").strip() if f.exists() else ""
    for old, new in (("#1A56B8", "var(--wm-ato,#1A56B8)"), ("#C2410C", "var(--wm-mou,#C2410C)"), ("#1F2937", "var(--wm-ink,currentColor)")):
        svg = svg.replace(f'"{old}"', f'"{new}"')
    return '<span class="wm">' + svg.replace("<svg ", '<svg class="wm-svg" focusable="false" ', 1) + "</span>" if svg else "あと何日、もう何日"


WORDMARK = _wordmark()



def _icon(d: str) -> str:  # own line icons: 24 grid, 1.75 stroke, round ends, no fill, currentColor
    return f'<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'


ICONS = {
    "home": _icon('<path d="M4 11l8-7 8 7M6 10v10h12V10"/>'),
    "calendar": _icon('<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
    "plus": _icon('<path d="M12 5v14M5 12h14"/>'),
    "user": _icon('<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/>'),
    "search": _icon('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'),
    "palette": _icon('<path d="M12 4a8 8 0 1 0 0 16c1.2 0 1.8-.8 1.8-1.7 0-.9-.7-1.3-.7-2.2 0-.9.7-1.6 1.6-1.6H17a3 3 0 0 0 3-3C20 7 16.5 4 12 4z"/><circle cx="8" cy="11" r="1"/><circle cx="11" cy="7.8" r="1"/><circle cx="15" cy="8.6" r="1"/>'),
}
TABS = [("/", "ホーム", "home"), ("/calendar/", "カレンダー", "calendar"), ("/add/", "記録", "plus"), ("/my/", "マイページ", "user")]


def tabbar_html(path: str) -> str:
    def current(href: str) -> bool:
        if href == "/":
            return path == "/"
        return path.startswith(href) or (href == "/calendar/" and path.startswith("/plan/"))
    return '<nav class="tabbar" aria-label="下のメニュー">' + "".join(
        f'<a href="{h}"{" aria-current=\'page\'" if current(h) else ""}>{ICONS[i]}<span>{esc(t)}</span></a>' for h, t, i in TABS) + "</nav>\n"


HEAD_ICONS = ('<div class="hicons"><a href="/search/" aria-label="さがす">' + ICONS["search"] + '</a><a href="/skins/" aria-label="きせかえ">' + ICONS["palette"] + "</a></div>")



class Ctx:
    def __init__(self, cfg: dict, preview: bool, today: date, entries: list[dict], skins_css: str):
        self.cfg, self.preview, self.today, self.entries = cfg, preview, today, entries
        self.cat_json = json.dumps(catalog.public_json(entries), ensure_ascii=False, separators=(",", ":"))
        self.skins_css = skins_css
        self.v_cat = hashlib.sha1(self.cat_json.encode("utf-8")).hexdigest()[:8]
        self.v_skin = hashlib.sha1(skins_css.encode("utf-8")).hexdigest()[:8]
        self.ver = asset_version(SITE["assets"])
        basic_css, other_css = skins.css().split("\n", 1)   # the first line is the basic skin's :root block; the others are fetched only when one of them is chosen
        self.skins_css = other_css
        self.v_skin = hashlib.sha1(other_css.encode("utf-8")).hexdigest()[:8]
        self.v_bundle = None
        css_urls = [f"/assets/skins.css?v={self.v_skin}"] + ([f"/assets/design.css?v={self.ver}"] if (SITE["assets"] / "design.css").exists() else [])
        conf = {"v": self.v_cat, "groups": catalog.GROUPS, "slugs": SLUGS, "css": css_urls,
                "skins": {s["id"]: {"card": s["card"], "name": s["name"], "attrs": s.get("attrs", {}), **({"season": s["season"]} if s.get("season") else {})} for s in skins.SKINS}}
        if cfg.get("google_client_id"):
            conf["gclient"] = cfg["google_client_id"]
        conf_js = json.dumps(conf, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        card_map = json.dumps({s["id"]: [s["card"], s.get("attrs", {})] for s in skins.SKINS}, separators=(",", ":"))
        self.head = (f"<script>window.ATOMOU={conf_js};</script>\n"
                     "<script>(function(){try{var p=(JSON.parse(localStorage.getItem('atomou.v1')||'{}').prefs)||{},m=" + card_map +
                     ",r=document.documentElement;if(p.skin&&p.skin!=='basic'&&m[p.skin]){__LOAD__r.setAttribute('data-skin',p.skin);r.setAttribute('data-card',m[p.skin][0]);for(var k in m[p.skin][1])r.setAttribute('data-'+k,m[p.skin][1][k])}"
                     "if(p.big)r.setAttribute('data-big','1')}catch(e){}})()</script>\n"
                     f'<style>{basic_css}</style>\n<link rel="manifest" href="/manifest.webmanifest">\n<meta name="theme-color" content="#ffffff">\n')
        load = "".join(f"var l{i}=document.createElement('link');l{i}.rel='stylesheet';l{i}.href='{u}';document.head.appendChild(l{i});" for i, u in enumerate(css_urls))
        self.head = self.head.replace("__LOAD__", load)
        self.bundle = "\n".join((SITE["assets"] / f"{n}.js").read_text(encoding="utf-8") for n in BUNDLE)
        self.v_bundle = hashlib.sha1(self.bundle.encode("utf-8")).hexdigest()[:8]
        self.tail = f'<script src="/assets/atomou.js?v={self.v_bundle}" defer></script>\n'
        self.site = dict(SITE)

    def page(self, path: str, title: str, desc: str, body: str, kind: str, *, noindex: bool = False) -> str:
        html = layout(self.site, self.cfg, self.preview, path=path, title=title, description=desc, body=body)
        return self.finish(html, kind, noindex)

    def finish(self, html: str, kind: str, noindex: bool = False) -> str:
        extra = ""
        if noindex and 'name="robots"' not in html:
            extra = '<meta name="robots" content="noindex,follow">\n'
        html = html.replace("</head>", extra + self.head + "</head>", 1)
        html = html.replace("<body>", f'<body data-page="{kind}">', 1)
        m = re.search(r'rel="canonical" href="https?://[^/"]+(/[^"]*)"', html)
        path = m.group(1) if m else "/"
        html = html.replace("</nav>\n</div></header>", "</nav>\n" + HEAD_ICONS + "\n</div></header>", 1)
        html = re.sub(r'<span class="logo" aria-hidden="true"></span>[^<]*</a>', lambda _m: WORDMARK + "</a>", html, count=1)
        return html.replace("</body>", tabbar_html(path) + self.tail + "</body>", 1)


# ---------- pages ----------
def search_form(q: str = "") -> str:
    return ('<div class="sbox"><form class="searchbox" id="searchform" action="/search/" method="get" role="search">'
            '<label class="vh" for="q">日付をさがす</label>'
            f'<input type="search" id="q" name="q" value="{esc(q)}" placeholder="さがす(年賀状、共通テスト、流星群)" autocomplete="off" enterkeyhint="search">'
            f'<button type="submit" class="sbtn" aria-label="さがす">{ICONS["search"]}</button></form><div class="suggest" id="suggest" hidden></div></div>')


def popular_chips(entries: list[dict]) -> str:
    out = []
    for w in POPULAR:
        if any(w in e["title"] or w in e["tags"] for e in entries):
            out.append(f'<a class="chip" href="/search/?q={quote(w)}">{esc(w)}</a>')
    return '<div class="chips scroll" aria-label="よく探される言葉">' + "".join(out) + "</div>" if out else ""


def home_page(c: Ctx) -> str:
    live = live_entries(c.entries, c.today)
    first = diverse(live, 6)
    chips = "".join(f'<a class="chip" href="/c/{GROUP_SLUG[g]}/">{mark_html(i + 1)}{esc(g)}</a>' for i, g in enumerate(catalog.GROUPS))
    ucs = "".join(f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>'
                  for u in [usecases.by_slug(s) for s in ("couple-anniversary", "furusato-nozei", "exam-university", "oshi-live", "quit-smoking", "baby-100days")] if u)
    body = f"""<section class="hero"><h1>{esc(CATCH)}</h1></section>
<div id="season" class="season" hidden></div>
<div id="blocks">
<section id="todo" data-block="todo" data-title="今日の予定・やること" hidden>
<div class="head-row"><h2>今日の予定・やること</h2><div class="grow"><a class="btn small ghost" href="/calendar/">カレンダー</a></div></div>
<ul class="plist" id="todo-list"><li class="muted">読み込み中です。</li></ul>
</section>
<section data-block="search" data-title="さがす">
{search_form()}
</section>
<section data-block="cats" data-title="ジャンル"><nav class="chiprow" aria-label="ジャンルから探す">{chips}</nav></section>
<section data-block="daily" data-title="今日の数字"><div class="daily" id="daily" aria-label="今日の数字"><span>今日の日付と、年末・年度末までの日数が出ます。</span></div></section>
<section id="mine" data-block="mine" data-title="あなたの日" hidden>
<div class="head-row"><h2>あなたの日</h2><div class="grow"><a class="btn small ghost" href="/my/">マイページ</a></div></div>
<div class="cards" id="mine-grid" data-save-order="1"></div>
</section>
<section data-block="soon" data-title="もうすぐの日">
<div class="head-row"><h2>もうすぐの日</h2><div class="grow"><button type="button" class="btn small ghost" id="shuffle">シャッフル</button></div></div>
<div class="cards" id="grid" data-save-order="1">{"".join(card_html(e) for e in first)}</div>
<p class="more-row"><button type="button" class="btn ghost" id="more">もっと見る</button></p>
</section>
<section data-block="usecases" data-title="こんな時に">
<div class="head-row"><h2>こんな時に</h2><div class="grow"><a class="btn small ghost" href="/use/">一覧</a></div></div>
<div class="uc-grid compact">{ucs}</div>
</section>
</div>
<p class="edit-home"><button type="button" class="btn small ghost" id="edit-home" aria-pressed="false">ホームの並べかえ・表示を変える</button> <button type="button" class="btn small ghost" id="reset-home" hidden>初期の並びに戻す</button></p>"""
    return c.page("/", f"{NAME}|{CATCH}", "あの日からもう何日?あの日まであと何日?日付を選ぶだけで数えて、カレンダーに入れられます。締切・試験・大会・お祭りなど、確認ずみの日付はワンタップで保存。", body, "home")


def search_page(c: Ctx) -> str:
    chips = '<button type="button" class="chip" data-g-chip="" aria-pressed="true">すべて</button>' + "".join(
        f'<button type="button" class="chip" data-g-chip="{SLUGS[i]}" aria-pressed="false">{esc(g)}</button>' for i, g in enumerate(catalog.GROUPS))
    body = f"""{crumbs([("トップ", "/"), ("さがす", None)])}
<h1>日付をさがす</h1>
<p class="lead muted">言葉で探すか、ジャンルを選んでください。</p>
{search_form()}
<div class="chips" role="group" aria-label="ジャンル">{chips}<button type="button" class="chip" id="f-son" aria-pressed="false">損得に関わる日だけ</button></div>
<p class="small muted" id="found" aria-live="polite">&nbsp;</p>
<div class="cards" id="results"></div>
<div class="panel" id="none" hidden><p>見つかりませんでした。</p><p>言葉を短くするか、ジャンルを「すべて」にしてみてください。自分の日として、そのまま<a id="none-add" href="/add/">記録する</a>こともできます。</p></div>
<noscript><p class="notice">さがす機能には JavaScript が必要です。ジャンルから探すときは、<a href="/c/deadline/">各ジャンルのページ</a>をご覧ください。</p></noscript>"""
    return c.page("/search/", f"日付をさがす | {NAME}", "言葉やジャンルから、締切・試験・大会・お祭りなどの日付をさがせます。見つけた日はワンタップで保存。", body, "search")


def my_page(c: Ctx) -> str:
    sync_html = ""
    if c.cfg.get("google_client_id"):
        sync_html = ('<h2 id="sync">端末をまたいで引き継ぐ</h2>\n<div class="panel" id="sync-box" hidden>'
                     '<p>Google アカウントでつなぐと、記録した日を、自分の Google ドライブ(専用の非表示フォルダ)を通して、別の端末に引き継げます。当サイトのサーバーには預けません。'
                     '<a href="/privacy/#google">くわしく</a></p><p><button type="button" class="btn" id="sync-now">Google アカウントでつないで同期する</button></p></div>\n')
    body = f"""{crumbs([("トップ", "/"), ("マイページ", None)])}
<h1>マイページ</h1>
<p class="lead muted">記録した日と、予定に入れた日が並びます。この端末の中だけに保存されます。</p>
<div class="panel" id="my-empty" hidden><p>まだ、ありません。</p><p><a class="btn" href="/add/">日付を記録する</a> <a class="btn ghost" href="/search/">日付をさがす</a></p></div>
<div class="head-row" id="my-tools" hidden><div class="grow" style="margin-left:0"><button type="button" class="btn small ghost" id="reorder" aria-pressed="false">↑↓で動かす</button></div></div>
<div class="cards" id="my-grid" data-save-order="1"></div>
<h2>設定</h2>
<div class="panel">
<div class="field"><label class="lab" for="p-big"><input type="checkbox" id="p-big"> 文字を大きくする</label></div>
<div class="field"><label for="p-alarm">他のカレンダーアプリ用のファイルに入れる、お知らせの時間</label>
<select id="p-alarm"><option value="morning">当日の朝9時</option><option value="eve">前の日の夜9時</option><option value="week">1週間前の朝9時</option><option value="none">お知らせなし</option></select></div>
<div class="field"><label class="lab" for="p-stats"><input type="checkbox" id="p-stats"> 利用状況の統計に協力する(個人は特定されません。<a href="/privacy/#stats">くわしく</a>)</label></div>
<p><a href="/skins/">きせかえ(見た目を変える)</a></p>
<p><a href="/?edit=1">ホームの並べかえ・表示を変える</a></p>
</div>
{sync_html}<h2>他のカレンダーアプリを使う人へ</h2>
<div class="panel"><p>入れた予定を、iPhone の「カレンダー」や Google カレンダーにも取り込みたいときは、ファイルをつくれます。1件ずつは、予定の詳細ページからです。</p>
<p><button type="button" class="btn small ghost" id="ics-all">すべての予定のファイルをつくる</button></p></div>
<h2>バックアップ</h2>
<div class="panel">
<p>記録は、この端末の中だけにあります。機種変更のときは、書き出して、新しい端末で読み込んでください。</p>
<p><button type="button" class="btn small" id="backup">書き出す</button>
<label class="btn small ghost" for="restore">読み込む</label><input class="vh" type="file" id="restore" accept="application/json,.json">
<button type="button" class="btn small ghost" id="wipe">すべて消す</button></p>
</div>
<noscript><p class="notice">マイページには JavaScript が必要です。</p></noscript>"""
    return c.page("/my/", f"マイページ | {NAME}", "記録した日と保存した日の一覧です。この端末の中だけに保存されます。", body, "my", noindex=True)


def add_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("日付を記録する", None)])}
<h1>日付を記録する</h1>
<p class="lead muted">選ぶだけで、数えます。年月日が分からなくても、年だけで残せます。</p>
<div id="wizard" class="wizard"><noscript><p class="notice">日付の記録には JavaScript が必要です。</p></noscript></div>"""
    return c.page("/add/", f"日付を記録する | {NAME}", "記念日・誕生日・はじめた日・命日などを、選ぶだけで記録。あと何日、もう何日かをすぐに表示します。", body, "add")


def calendar_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", None)])}
<h1>カレンダー・予定帳</h1>
<p class="lead muted">予定・記念日・予定に入れた公式の日付を、ひと目で見られます。日を押すと、その日の予定が出ます。</p>
<div id="cal"></div>
<noscript><p class="notice">カレンダーには JavaScript が必要です。</p></noscript>"""
    return c.page("/calendar/", f"カレンダー・予定帳 | {NAME}", "予定・記念日・公式の日付を、月のカレンダーと一覧で見られる予定帳です。予定ごとにメモと「何日前までにやること」を書けます。", body, "calendar")


def plan_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", "/calendar/"), ("予定の詳細", None)])}
<h1>予定の詳細</h1>
<div id="plan"><p class="muted">読み込み中です。</p></div>
<noscript><p class="notice">予定の詳細には JavaScript が必要です。</p></noscript>"""
    return c.page("/plan/", f"予定の詳細 | {NAME}", "予定のメモと、何日前までにやることを書き込めます。この端末の中だけに保存されます。", body, "plan", noindex=True)


def skins_page(c: Ctx) -> str:
    def tile(s: dict) -> str:
        v = s["vars"]
        sw = "".join(f'<i style="background:{v[k]}"></i>' for k in ("bg", "surface", "accent", "ato", "mou"))
        return (f'<button type="button" class="skin" data-skin="{s["id"]}" data-name="{esc(s["name"])}" aria-pressed="false"><span class="sw">{sw}</span>'
                f'<b>{esc(s["name"])}</b><small>{esc(s["desc"])}</small></button>')
    t = c.today
    samples = [
        {"id": "s1", "title": "サンプル 申込の締切", "date": (t + timedelta(days=45)).isoformat(), "kind": "締切", "g": 1, "quiet": False},
        {"id": "s2", "title": "サンプル はじめた日", "date": (t - timedelta(days=400)).isoformat(), "kind": "はじめた日", "g": 4, "quiet": False},
        {"id": "s3", "title": "サンプル 大切な日", "date": (t - timedelta(days=800)).isoformat(), "kind": "大切な日", "g": 0, "quiet": True},
    ]
    body = f"""{crumbs([("トップ", "/"), ("きせかえ", None)])}
<h1>きせかえ</h1>
<div id="season" class="season" hidden></div>
<p class="lead muted">見た目を、好みのものに変えられます。選ぶと、すぐに変わります。いちばん上の「ベーシック」が標準です。</p>
<h2>見えかた</h2>
<p class="hint">左から、これから来る日、過ぎた日、大切な人を思う日(静かな表示)の例です。</p>
<div class="cards">{"".join(card_html(s, own=True, actions=False, link=False) for s in samples)}</div>
<h2>選ぶ</h2>
<div class="skins" id="skin-list">{"".join(tile(s) for s in skins.SKINS)}</div>
<noscript><p class="notice">きせかえには JavaScript が必要です。</p></noscript>"""
    return c.page("/skins/", f"きせかえ | {NAME}", "見た目を20種類以上から選べます。文字の大きいもの、色のやさしいもの、にぎやかなものまで。", body, "skins")


def use_index(c: Ctx) -> str:
    secs = []
    for name, items in usecases.grouped():
        secs.append(f"<h2>{esc(name)}</h2><div class=\"uc-grid\">" + "".join(
            f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>' for u in items) + "</div>")
    body = f"""{crumbs([("トップ", "/"), ("使い方", None)])}
<h1>こんな時に使えます</h1>
<p class="lead muted">使い方の例です。近い場面を見つけてください。</p>
{"".join(secs)}"""
    return c.page("/use/", f"こんな時に使えます | {NAME}", "付き合った記念日、大切な人を思う日、確定申告、受験、推し活など、使い方の例を場面ごとに紹介します。", body, "use")


def use_page(c: Ctx, u: dict) -> str:
    quiet = u["quiet"]
    steps = "".join(f"<li>{esc(s)}</li>" for s in u["steps"])
    parts = [f'<p class="lead">{esc(u["situation"])}</p>', f'<p class="small muted">こんな方に: {esc(u["who"])}</p>', f"<h2>やり方</h2><ol class=\"steps\">{steps}</ol>"]
    acts = []
    if u["own"]:
        o = u["own"]
        acts.append(f'<a class="btn" href="/add/?kind={o["kind"]}&amp;title={quote(o["label"])}">この日を記録する</a>')
        parts.append(f'<p class="hint">{esc(o["hint"])}</p>')
    cat = u["catalog"]
    if cat:
        g = cat.get("group")
        acts.append(f'<a class="btn ghost" href="/c/{GROUP_SLUG[g]}/">公式の日付を見る</a>' if g in GROUP_SLUG else "")
        tags = "".join(f'<a class="chip" href="/search/?q={quote(t)}">{esc(t)}</a>' for t in cat.get("tags", []))
        if tags:
            parts.append(f'<p class="small muted">探す言葉</p><div class="chips">{tags}</div>')
    if acts:
        parts.append("<p>" + " ".join(a for a in acts if a) + "</p>")
    if u["tips"]:
        parts.append("<h2>ポイント</h2><ul>" + "".join(f"<li>{esc(t)}</li>" for t in u["tips"]) + "</ul>")
    if u["cautions"]:
        parts.append(f'<div class="notice{" quiet" if quiet else ""}"><b>気をつけること</b><ul>' + "".join(f"<li>{esc(t)}</li>" for t in u["cautions"]) + "</ul></div>")
    rel = [r for r in usecases.related(u["slug"]) if r["quiet"] == quiet]
    if rel:
        parts.append("<h2>ほかの場面</h2><div class=\"uc-grid\">" + "".join(f'<a class="uc" href="/use/{r["slug"]}/"><b>{esc(r["title"])}</b><span>{esc(r["who"])}</span></a>' for r in rel) + "</div>")
    body = crumbs([("トップ", "/"), ("使い方", "/use/"), (u["title"], None)]) + f'<h1>{esc(u["title"])}</h1>\n' + "\n".join(parts)
    return c.page(f"/use/{u['slug']}/", f"{u['title']} | {NAME}", u["situation"], body, "use")


def event_page(c: Ctx, e: dict, indexable: bool, live: list[dict]) -> str:
    quiet = e["quiet"]
    today = c.today
    d = date.fromisoformat(e["date"])
    n = (d - today).days
    word = "です" if n == 0 else (f"あと{n}日です" if n > 0 else f"もう{-n}日たちました")
    fmt = fmt_date(e["date"], e["precision"])
    end = f"〜{fmt_date(e['date_end'])}" if e.get("date_end") else ""
    rel = [] if quiet else [r for r in live if r["group"] == e["group"] and r["id"] != e["id"] and not r["quiet"]][:4]
    sentence = (f"{e['title']}は、{fmt}{end}です。" if e["precision"] == "day" else f"{e['title']}は、{fmt}です。") + (
        f"{today.year}年{today.month}月{today.day}日の時点で、{word}。" if e["precision"] == "day" else "")
    body = crumbs([("トップ", "/"), (e["group"], f"/c/{GROUP_SLUG[e['group']]}/"), (e["title"], None)]) + f"""
<h1>{esc(e['title'])}</h1>
{card_html(e, big=True, link=False)}
<p>{esc(sentence)}<span class="small muted">(この文章は、ページを作った日の数字です。上のカードは、開いた日の数字になります。)</span></p>
{'<p class="notice quiet">この日は、静かにお知らせします。</p>' if quiet else ""}
<h2>日付の出どころ</h2>
<dl class="info"><dt>出典</dt><dd><a href="{esc(e['source_url'])}" rel="noopener nofollow" target="_blank">{esc(host(e['source_url']))}</a></dd>
<dt>確認した日</dt><dd>{esc(e['checked_on'])}</dd>{f"<dt>出典の文</dt><dd>{esc(e['source_quote'])}</dd>" if e.get('source_quote') else ""}</dl>
<p class="small muted">日付は変わることがあります。申し込みや手続きの前に、必ず出典の公式ページでご確認ください。</p>
<p><a class="btn small" href="/plan/?key=c:{e['id']}">メモ・やることを書く</a> <a class="btn small ghost" href="/add/?title={quote(e['title'])}&amp;date={e['date']}">自分の日として記録する</a></p>
{f'<details class="more"><summary>他のカレンダーアプリも使うとき</summary><p class="hint">iPhone の「カレンダー」や Google カレンダーに取り込めるファイルをつくります。</p><p><button type="button" class="btn small ghost" data-ics-for="c:{e["id"]}">ファイルをつくる</button></p></details>' if e["precision"] == "day" else ""}
{('<h2>同じジャンルの日</h2><div class="cards">' + "".join(card_html(r) for r in rel) + "</div>") if rel else ""}"""
    suffix = "から、もう何日?" if e["status"] == "ended" else "はいつ?あと何日?"
    title = f"{e['title']}{suffix} {fmt} | {NAME}"
    desc = f"{e['title']}の日付は{fmt}{end}。出典と確認日つきで、あと何日(もう何日)かを表示し、カレンダーに入れられます。"
    return c.page(f"/e/{e['id']}/", title, desc, body, "event", noindex=not indexable)


def category_page(c: Ctx, group: str, live: list[dict]) -> str:
    rows = [e for e in live if e["group"] == group][:200]
    cats: list[str] = []
    for e in rows:
        if e["category"] not in cats:
            cats.append(e["category"])
    chips = ""
    if len(cats) > 1:
        chips = ('<div class="chips" role="group" aria-label="しぼりこみ"><button type="button" class="chip" data-cat-chip="" aria-pressed="true">すべて</button>'
                 + "".join(f'<button type="button" class="chip" data-cat-chip="{esc(x)}" aria-pressed="false">{esc(x)}</button>' for x in cats) + "</div>")
    body = f"""{crumbs([("トップ", "/"), (group, None)])}
<h1>{esc(group)}の日付</h1>
<p class="lead muted">{esc(GROUP_LEAD[group])}</p>
{search_form()}
{chips}
<div class="cards" id="grid">{"".join(card_html(e) for e in rows)}</div>"""
    if not rows:
        body = body.replace('<div class="cards" id="grid"></div>', '<p class="empty">いま表示できる日付はありません。</p>')
    return c.page(f"/c/{GROUP_SLUG[group]}/", f"{group}の日付一覧 | {NAME}", f"{GROUP_LEAD[group]}あと何日かがひと目で分かり、ワンタップで保存できます。", body, "category")


def manual_page(c: Ctx) -> str:
    t = c.today
    sample = {"id": "sample", "title": "家族で行く旅行の日(例)", "date": (t + timedelta(days=45)).isoformat(), "kind": "予定", "g": 1, "quiet": False}
    past = {"id": "sample2", "title": "禁煙をはじめた日(例)", "date": (t - timedelta(days=400)).isoformat(), "kind": "はじめた日", "g": 4, "quiet": False}

    def step(n: int, head: str, text: str) -> str:
        return f'<div class="stepcard"><span class="no" aria-hidden="true">{n}</span><div><b>{head}</b><p>{text}</p></div></div>'

    def btn(label: str, ghost: bool = False) -> str:
        return f'<span class="btn small sample{" ghost" if ghost else ""}" aria-hidden="true">{label}</span>'

    qa = [
        ("料金はかかりますか?", "無料です。会員登録(ログイン)も必要ありません。"),
        ("入力した内容は、ほかの人に見えますか?", "見えません。予定・メモ・やることは、お使いのスマートフォンやパソコンの中だけに保存され、当サイトのサーバーには送りません。"),
        ("予定の前に、お知らせは来ますか?", "いまのところ、スマートフォンへの通知はありません。サイトを開いたときに、ホームの「今日の予定・やること」と、カレンダーに出ます。スマートフォンへの通知は、今後の追加を検討しています。他のカレンダーアプリの通知を使いたいときは、予定の詳細の「他のカレンダーアプリも使うとき」から、ファイルをつくって取り込めます。"),
        ("「やること」とは何ですか?", "予定の何日前までに何をするかを、書き込める欄です。たとえば「試験の1週間前:願書を出す」。期限の日が、カレンダーと、ホームの「今日の予定・やること」に出ます。チェックを入れると、済みになります。"),
        ("機種変更をしたら、記録はどうなりますか?", "新しい端末には引き継がれません。変更の前に、マイページの「書き出す」でファイルを作り、新しい端末で「読み込む」を押してください。Google アカウントでの引き継ぎが表示されている場合は、それも使えます。"),
        ("「あと」と「もう」は、どう違いますか?", "「あと」は、これから来る日までの日数です。「もう」は、過ぎた日からの日数です。"),
        ("日数の数え方を教えてください。", "今日を0日として数えます。明日は「あと1日」、昨日は「もう1日」と表示され、当日は「今日」と表示されます。"),
        ("2月29日は、どう扱われますか?", "うるう年でない年は、2月28日として数えます。"),
        ("文字が小さくて読みにくいです。", "マイページの「設定」で「文字を大きくする」にチェックを入れてください。「きせかえ」の「大きな文字」や「ハイコントラスト」も読みやすくなります。"),
        ("日付が間違っているようです。", "公式の日付は、変更されることがあります。各カードの「詳細」に、出典(元のページ)と確認した日があります。誤りを見つけたときは、<a href=\"/contact/\">お問い合わせ</a>からお知らせください。"),
        ("大切な人を思う日も、入れてよいですか?", "入れて大丈夫です。「大切な人を思う日」を選ぶと、静かな見た目で残せます。広告やおすすめは表示しません。"),
        ("入れた日を消したいです。", "マイページ、またはカレンダーから、その予定を開き、「消す」を押します。すべて消すときは、マイページの「すべて消す」を押します。"),
    ]
    qa_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in qa)
    body = f"""{crumbs([("トップ", "/"), ("説明書", None)])}
<div class="manual">
<h1>使い方(説明書)</h1>
<p class="lead">「あと何日、もう何日」の使い方を説明します。画面の上に出る案内で、実際のボタンを指しながら教えることもできます。</p>
<p><button type="button" class="btn" data-guide="start">この画面のガイドを見る</button> <span class="hint">各ページの右下の「ガイド」ボタンからも、いつでも見られます。</span></p>

<h2>このサイトでできること</h2>
<ul class="big-list">
<li><b>日付を数えます。</b>「あの日からもう何日」「あの日まであと何日」がすぐに分かります。</li>
<li><b>カレンダーと予定帳として使えます。</b>デート、会議、記念日などを入れて、月のカレンダーと一覧で見られます。予定ごとに、メモと「何日前までにやること」を書けます。</li>
<li><b>世の中の大事な日も見られます。</b>締切、試験、大会、お祭りなどの日付を、公式の情報で確認して載せています。「予定に入れる」で、カレンダーに入ります。</li>
</ul>

<h2>はじめて使うとき</h2>
{step(1, "「記録する」を押す", "画面上部の「記録する」を押します。")}
{step(2, "どんな日かを選ぶ", "「予定」「記念日」「誕生日」など、近いものを選びます。デートや会議は「予定」です。文字を入力する必要はありません。")}
{step(3, "日付(と時刻)を選ぶ", "日付の欄を押すとカレンダーが開くので、そこから選びます。「予定」のときは、時刻も入れられます。")}
{step(4, "「この日を残す」を押す", "保存されて、予定の詳細が開きます。続けて、メモや、何日前までにやることを書けます。")}
<p class="hint">年や月しか分からないときは、「年と月だけ」「年だけ」も選べます。</p>

<h2>カレンダーの使い方</h2>
<ul class="big-list">
<li>上の「カレンダー」を押すと、月のカレンダーが出ます。「一覧」に切りかえると、これから60日の予定とやることが、日ごとに並びます。</li>
<li>日を押すと、下に、その日の予定とやることが出ます。「この日に予定を追加」で、その日の予定を入れられます。</li>
<li>予定を押すと、詳細が開き、メモと「やること」を書けます。</li>
</ul>

<h2>予定のメモと「やること」</h2>
<p>予定の詳細で、「やること」に、いつまでにするかと、内容を書きます。たとえば、次のように使えます。</p>
<ul class="big-list">
<li>試験の予定に、「1週間前:願書を出す」「前の日:持ち物を確認する」</li>
<li>引っ越しの予定に、「2週間前:引っ越しの手続き」「3日前:荷造りを終える」</li>
</ul>
<p>期限の日は、カレンダーに出ます。今日が期限のものは、ホームの「今日の予定・やること」に出て、そこでチェックできます。</p>

<h2>カードの見かた</h2>
<p>日付は「カード」に表示されます。</p>
<div class="cards" style="max-width:360px">{card_html(sample, own=True, actions=False, link=False)}</div>
<ul class="big-list">
<li><b>「あと」</b> … これから来る日までの日数です。</li>
<li><b>大きな数字</b> … 日数です。100日を超えるときは「2年3か月12日」のように表示し、その下に合計の日数も表示します。</li>
<li><b>日付</b> … その日が何月何日の何曜日かを表します。</li>
</ul>
<p>過ぎた日は、次のように表示されます。「<b>もう</b>」は、その日から数えた日数です。</p>
<div class="cards" style="max-width:360px">{card_html(past, own=True, actions=False, link=False)}</div>

<h2>ボタンの働き</h2>
<dl class="info big-dl">
<dt>{btn("☆ 予定に入れる")}</dt><dd>公式の日付を、自分のカレンダーに入れます。入ると「★ 予定に入っています」に変わります。もう一度押すと、はずれます。</dd>
<dt>{btn("詳細", True)}</dt><dd>出典(元のページ)や、確認した日など、くわしい情報を開きます。</dd>
<dt>{btn("開く")}</dt><dd>自分で入れた予定の詳細を開きます。直したり、メモやることを書いたりできます。</dd>
<dt>{btn("消す", True)}</dt><dd>自分で入れた予定を消します。</dd>
<dt>{btn("シャッフル")}</dt><dd>トップページのカードを、別の日に入れ替えます。</dd>
<dt>{btn("↑↓で動かす", True)}</dt><dd>カードの並び順を、ボタンで変えます。ボタンを使わなくても、カードは、ドラッグ(スマホは長押し)で動かせます。</dd>
<dt>{btn("さがす")}</dt><dd>言葉で日付を探します。「年賀状」「流星群」など、思いついた言葉を入力してください。</dd>
<dt>{btn("きせかえ", True)}</dt><dd>色や形、文字の大きさなど、見た目を変えます。季節のきせかえもあります。</dd>
<dt>{btn("ホームの並べかえ", True)}</dt><dd>トップページの各ブロックを入れ替えたり、表示しないようにしたりできます。トップページの一番下のボタンから使えます。</dd>
</dl>

<h2>よくある質問</h2>
<div class="qa">{qa_html}</div>
<p>解決しないときは、<a href="/contact/">お問い合わせ</a>からご連絡ください。</p>
<p><a class="btn" href="/add/">予定を入れる</a> <a class="btn ghost" href="/use/">こんな時に使えます(使い方の例)</a></p>
</div>"""
    return c.page("/manual/", f"使い方(説明書) | {NAME}", "あと何日、もう何日の使い方を説明します。予定の入れ方、カレンダーとやること、カードの見かた、ボタンの働き、よくある質問をまとめています。", body, "manual")


def today_page(c: Ctx) -> str:
    def purposes(items: list[tuple[str, str, str, str]]) -> str:
        cards = "".join(
            f'<a class="uc" href="/add/?kind={kind}&amp;title={quote(label)}" data-when="{when}"><b>{esc(label)}</b><span>{esc(hint)}</span></a>'
            for label, hint, kind, when in items)
        return f'<div class="uc-grid">{cards}</div>'

    t = c.today
    doy = (t - date(t.year, 1, 1)).days + 1
    total = 366 if (t.year % 4 == 0 and t.year % 100 != 0) or t.year % 400 == 0 else 365
    fy_start = date(t.year if t.month >= 4 else t.year - 1, 4, 1)
    static = {"today": fmt_date(t.isoformat()), "y": str(t.year), "year": str(doy), "year-left": str(total - doy), "newyear-y": str(t.year + 1), "newyear": str(total - doy + 1),
              "fy-y": str(fy_start.year), "fy": str((date(fy_start.year + 1, 3, 31) - t).days)}

    def n(key: str) -> str:  # filled with the visitor's own today by app.js; the build day's value is the fallback
        return f'<span data-num="{key}">{static[key]}</span>'

    def more(links: list[tuple[str, str]]) -> str:
        return '<p class="small">くわしい使い方: ' + " / ".join(f'<a href="{h}">{esc(t)}</a>' for t, h in links) + "</p>"

    body = f"""{crumbs([("トップ", "/"), ("今日の数字", None)])}
<h1>今日の数字</h1>
<p class="lead muted">今日の日付から、これからの準備を考えられます。当てはまるものを選ぶと、その日までの日数を、自分の日として記録できます。通知の時間も選べます。</p>
<section id="today"><h2>今日は {n("today")}</h2>
<p>お使いの端末の日付をもとに、下の日数を表示しています。</p></section>

<section id="year">
<h2>{n("y")}年は、もう{n("year")}日め</h2>
<p>年末まで、あと{n("year-left")}日です。年内にしておきたいことは、ありますか。</p>
{purposes([("年賀状の準備", "年末までの予定として記録します", "until", "year-end"), ("ふるさと納税の期限", "その年の分は12月31日までが目安です", "until", "year-end"),
           ("年末の大掃除・買い出し", "年内の予定にします", "until", "year-end"), ("年内に済ませたい手続き", "自分で名前をつけて記録できます", "until", "year-end")])}
{more([("年賀状", "/use/nengajo/"), ("ふるさと納税", "/use/furusato-nozei/"), ("年末までの日数", "/use/year-end-count/")])}
</section>

<section id="newyear">
<h2>{n("newyear-y")}年まで、あと{n("newyear")}日</h2>
<p>新しい年を迎える準備を、いまから考えておけます。</p>
{purposes([("お正月の準備", "おせち・帰省・買い物など", "until", "new-year"), ("帰省・旅行の予約", "混みあう時期の予約を忘れないように", "until", "new-year"),
           ("初詣の予定", "家族や友人との予定に", "until", "new-year")])}
{more([("初詣・初日の出の日付をさがす", "/search/?q=%E5%88%9D%E8%A9%A3")])}
</section>

<section id="fy">
<h2>{n("fy-y")}年度は、あと{n("fy")}日</h2>
<p>年度は4月から翌年3月までです。年度の終わりと始まりに合わせて、準備できることがあります。</p>
{purposes([("入学の用意", "入学式に向けた準備の目安に", "until", "fy-start"), ("新学期の用意", "学用品・手続きなどの準備に", "until", "fy-start"),
           ("引っ越しの用意", "年度末は混みあうので、早めの予約を", "until", "fy-end"), ("年度末の手続き", "締切のある手続きを忘れないように", "until", "fy-end"),
           ("転職・異動の準備", "新年度に向けた準備に", "until", "fy-start")])}
{more([("年度末までの日数", "/use/fiscal-year-end/"), ("引っ越しの手続き", "/use/moving-procedure/"), ("就職活動", "/use/job-hunting/")])}
</section>

<section id="start">
<h2>今日から数える</h2>
<p>今日を「はじめた日」にして、続けた日数を数えられます。</p>
{purposes([("禁煙をはじめた日", "続けた日数が、毎日増えていきます", "since", "today"), ("習慣をはじめた日", "運動・勉強・早起きなど", "since", "today"),
           ("今日のできごと", "あとから「もう何日」と見返せます", "memo", "today")])}
{more([("禁煙", "/use/quit-smoking/"), ("習慣", "/use/habit-streak/")])}
</section>
<p>どれも当てはまらないときは、<a href="/add/">自分で日付を入力する</a>こともできます。</p>"""
    return c.page("/today/", f"今日の数字から、これからの準備を考える | {NAME}", "今年のあと何日、来年まであと何日、年度末まであと何日。今日の数字から、入学や引っ越しなどの準備を考え、自分の日として記録できます。", body, "today")


def sw_js(c: Ctx) -> str:
    """A small service worker: the pages and scripts open at once on the next visit (assets from the cache, pages from the network first), and it is the base of notifications later."""
    urls = [f"/assets/style.css?v={c.ver}", f"/assets/atomou.js?v={c.v_bundle}"]
    urls.append(f"/assets/catalog.json?v={c.v_cat}")
    return ("// generated by sites/atomou/build.py (do not edit)\n"
            f"const CACHE = 'atomou-{c.ver}-{c.v_cat}-{c.v_skin}';\nconst PRE = {json.dumps(urls)};\n"
            "self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRE)).then(() => self.skipWaiting())); });\n"
            "self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });\n"
            "self.addEventListener('fetch', (e) => {\n"
            "  const r = e.request, u = new URL(r.url);\n"
            "  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;\n"
            "  if (u.pathname.startsWith('/assets/')) { e.respondWith(caches.match(r).then((m) => m || fetch(r).then((x) => { if (x.ok) { const y = x.clone(); caches.open(CACHE).then((c) => c.put(r, y)); } return x; }))); return; }\n"
            "  if (r.mode === 'navigate') { e.respondWith(fetch(r).then((x) => { if (x.ok) { const y = x.clone(); caches.open(CACHE).then((c) => c.put(r, y)); } return x; }).catch(() => caches.match(r).then((m) => m || caches.match('/')))); }\n"
            "});\n")


def privacy_fix(c: Ctx, html: str) -> str:
    """The shared privacy page says that no analytics is used; this site counts fixed items (and may offer a Google Drive hand-over), so that part is replaced."""
    if "<title>プライバシーポリシー" not in html:
        return html
    old = "<h2>アクセス解析</h2>\n<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>"
    if old not in html:
        raise BuildError("sitekit's privacy text changed: update privacy_fix in sites/atomou/build.py")
    return html.replace(old, STATS_SECTION + ("\n" + GOOGLE_SECTION if c.cfg.get("google_client_id") else ""), 1)


def legal(c: Ctx) -> dict:
    cfg, site = c.cfg, c.site
    return legal_pages(
        site, cfg, c.preview,
        purpose="日付を登録すると、あと何日、もう何日かを数えて、カレンダーに入れられるようにすること。締切・試験・大会・お祭りなどの公式の日付を、ワンタップで保存できるようにすること。",
        sources_html="各日付のページに、出典(官公庁・主催者などの公式ページ)と、確認した日を載せています。",
        update_text="日付は、公式の発表をもとに、随時、確認・追加します。",
        disclaimer_html="<p>日付は、公式の発表などをもとに確認していますが、変更・中止されることがあります。申し込みや手続きの前に、必ず出典の公式ページでご確認ください。当サイトの情報をもとに行った行動の結果について、責任を負いかねます。</p>"
                        "<p>表示する「あと○日」「もう○日」は、お使いの端末の日付をもとに、ブラウザの中で計算しています。端末の日付が正しくないときは、数字もずれます。</p>",
        contact_notice="日付の間違いのご指摘は、該当ページの名前と、正しい日付の出典(ページのアドレス)を添えていただけると、確認が早くなります。",
        input_note=("<h2>この端末に保存する情報</h2>"
                    "<p>あなたが記録した日(名前・日付・時刻・メモ・やること・設定)と、予定に入れた日の一覧は、お使いのブラウザの中(localStorage)だけに保存します。当サイトのサーバーには送りません。"
                    "ブラウザのデータを消すと、記録も消えます。マイページの「書き出す」で、バックアップを作れます。</p>"),
        finish=lambda html: c.finish(privacy_fix(c, html), "legal"),
    )


# ---------- the site ----------
def build_pages(cfg: dict, release: bool = False, today: date | None = None) -> dict:
    global _TODAY
    today = today or date.today()
    _TODAY = today
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing) or not release
    entries, _rejects = catalog.build_catalog(today)
    c = Ctx(cfg, preview, today, entries, skins.css())
    launch = date.fromisoformat(cfg.get("launch_date") or today.isoformat())
    index_ids = catalog.indexable_ids(entries, today, launch, int(cfg.get("index_per_week", 6)))
    live = live_entries(entries, today)
    pages: dict[str, str | bytes] = {
        "index.html": home_page(c), "search/index.html": search_page(c), "my/index.html": my_page(c), "add/index.html": add_page(c),
        "skins/index.html": skins_page(c), "use/index.html": use_index(c), "manual/index.html": manual_page(c), "today/index.html": today_page(c), "calendar/index.html": calendar_page(c), "plan/index.html": plan_page(c),
    }
    for u in usecases.USECASES:
        pages[f"use/{u['slug']}/index.html"] = use_page(c, u)
    for g in catalog.GROUPS:
        pages[f"c/{GROUP_SLUG[g]}/index.html"] = category_page(c, g, live)
    for e in entries:
        pages[f"e/{e['id']}/index.html"] = event_page(c, e, e["id"] in index_ids, live)
    pages.update(legal(c))
    pages["api/e.php"] = stats_php()
    pages["manifest.webmanifest"] = json.dumps({
        "name": NAME, "short_name": "あと何日", "description": CATCH, "start_url": "/", "scope": "/", "display": "standalone", "lang": "ja",
        "background_color": "#F7F7F5", "theme_color": "#FFFFFF",
        "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, ensure_ascii=False, indent=1) + "\n"
    pages["sw.js"] = sw_js(c)
    pages["assets/catalog.json"] = c.cat_json
    pages["assets/skins.css"] = c.skins_css
    pages["assets/atomou.js"] = c.bundle
    pages.update(asset_pages(SITE["assets"]))
    # the sitemap lists indexable pages only (not /my/, not event pages that are held back)
    listed = {k: 1 for k in pages if k.endswith("index.html") and k != "my/index.html"
              and k != "plan/index.html" and not (k.startswith("e/") and k.split("/")[1] not in index_ids)}
    pages.update(standard_files(listed, cfg, preview, today.isoformat()))
    pages[".htaccess"] = pages[".htaccess"] + HT_CACHE
    if preview:
        ht = pages[".htaccess"]
        # Xserver's server cache answers repeat requests without asking Apache, which would skip the password: switch it off for the demo
        ht = ht.replace('SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=off\n', 'SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=on\n')
        ht = ht.replace('SetEnvIf Request_URI ".*" Ngx_Cache_AllCacheMode\n', "")
        if "NoCacheMode=on" not in ht or "AllCacheMode" in ht:
            raise BuildError("sitekit's .htaccess changed: update the demo's cache switch in sites/atomou/build.py")
        pages[".htaccess"] = ht + DEMO_AUTH
    return pages


def render_site(cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    pages = build_pages(cfg, release, today)
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--today", default="")
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        files = render_site(cfg, Path(a.out), release=a.release, today=date.fromisoformat(a.today) if a.today else None)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
