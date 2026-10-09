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

from sites.atomou import articles, catalog, datecore, skins, usecases  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, asset_version, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

NAME = "あと何日、もう何日"
CATCH = "忘れたくない日を、お知らせします。"   # decided by the owner (2026-10-08); the copy pass may not change it
SLUGS = ["deadline", "sale", "events", "exams", "hobby", "festival"]
GROUP_SLUG = dict(zip(catalog.GROUPS, SLUGS))
GROUP_LEAD = {
    "締切・制度": "確定申告、年金、制度の施行日。過ぎると損をする日。",
    "消費・セール": "年賀状、大型セール、ポイントの期限、サービス終了。暮らしのお金の日。",
    "大会・番組": "野球、サッカー、駅伝、相撲、音楽番組。待っている日。",
    "試験・資格": "大学入試、高校入試、資格試験、就活、奨学金の締切。",
    "マニア・天文": "流星群、日食、鉄道、即売会、ゲーム・アニメ。好きな人の日。",
    "地域のお祭り": "祭り、花火、イルミネーション、紅葉、初詣。行きたい日。",
}
POPULAR = ["年賀状", "ふるさと納税", "共通テスト", "流星群", "紅白", "コミケ", "最低賃金", "確定申告", "ドラフト"]
SITE = {
    "nav": [("さがす", "/search/", "/search/"), ("カレンダー", "/calendar/", "/calendar/"), ("記録する", "/add/", "/add/"), ("マイページ", "/my/", "/my/")],
    "glyph": "",
    "assets": HERE / "assets",
    "source_html": '公式の日付は、出典と確認した日つき。記録した日は、この端末の中だけに残ります。<a href="/manual/">説明書</a> | <a href="/use/">こんな時に</a> | <a href="/skins/">きせかえ</a>',
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


PUSH_BOX = '''<h2 id="push">この端末への通知</h2>
<div class="panel" id="push-box" hidden>
<p>予定の日とやることの期限に、この端末へ通知します。届く時間は「お知らせの時間」で選べます(当日の朝7時ごろ、または前日の夜21時ごろ)。サーバーに送るのは日付だけです。予定の内容は端末に残ります。<a href="/privacy/#push">詳しく</a></p>
<p id="push-status" class="muted"></p>
<p id="push-ios" class="hint" hidden>iPhone・iPad は、共有ボタンから「ホーム画面に追加」し、そのアイコンから開くと通知を使えます。</p>
<p><button type="button" class="btn" id="push-on">この端末に通知を届ける</button> <button type="button" class="btn ghost" id="push-off" hidden>通知を止める</button></p>
</div>
'''

MEMBER_BOX = '''<h2 id="member">会員(無料)</h2>
<div class="panel" id="member-box" hidden><div class="m-body"><p class="muted">読み込み中…</p></div></div>
'''

HTPASSWD_PLACEHOLDER = "__HTPASSWD__"
DEMO_AUTH = (
    "# demo: nobody gets in without the password (the deploy job writes the password file outside public_html and fills in its path)\n"
    'AuthType Basic\nAuthName "atomou demo"\n'
    f"AuthUserFile {HTPASSWD_PLACEHOLDER}\nRequire valid-user\n"
)


def stats_php() -> str:
    return (HERE / "stats_receiver.php.tpl").read_text(encoding="utf-8").replace("__RE__", "/" + STAT_KEY_RE + "/")


def push_php(cfg: dict | None = None) -> str:
    url = str((cfg or json.loads((HERE / "config.json").read_text(encoding="utf-8")))["site_url"]).rstrip("/")
    return (HERE / "push_receiver.php.tpl").read_text(encoding="utf-8").replace("__SITE_URL__", url)


def members_on(cfg: dict) -> bool:
    return bool(cfg.get("member_mail_from"))


def member_php(cfg: dict) -> str:
    tiers = cfg.get("member_tiers") or []
    for t in tiers:
        if not (isinstance(t, dict) and re.fullmatch(r"[a-z0-9_-]{1,20}", str(t.get("id", ""))) and int(t.get("size", 0)) >= 0 and int(t.get("months", 0)) >= 0):
            raise BuildError(f"member_tiers: bad tier {t!r}")
    php = (HERE / "member_receiver.php.tpl").read_text(encoding="utf-8")
    for k, v in (("__TIERS__", json.dumps([{"id": t["id"], "size": int(t["size"]), "months": int(t["months"]), "tester": bool(t.get("tester"))} for t in tiers])),
                 ("__REF_MONTHS__", str(int(cfg.get("member_ref_months", 6)))), ("__REF_GIVE__", str(int(cfg.get("member_ref_give_months", 1)))),
                 ("__REF_CAP__", str(int(cfg.get("member_ref_cap", 12)))),
                 ("__MAIL_FROM__", str(cfg["member_mail_from"]).replace("'", "")), ("__SITE_NAME__", NAME.replace("'", "")), ("__SITE_URL__", str(cfg["site_url"]).rstrip("/"))):
        php = php.replace(k, v)
    return php


STATS_SECTION = '<h2 id="stats">利用状況の統計</h2>\n<p>使いやすくするために、件数だけの統計を取ります。送るのは、あらかじめ決めた項目の件数です。「どのページが開かれたか」「選ばれたきせかえ」「ホームのブロックの並びと非表示」「予定に入れる・ファイルを作るが押された回数」「検索で見つかったか(検索した言葉は送りません)」。</p>\n<p>名前・日付・メモ・メールアドレス・検索した言葉・端末を識別する番号は送りません。Cookie は使いません。サーバーに残るのは1日ごとの合計の件数だけで、同じ人かどうかは分かりません。送りすぎを防ぐため、アドレスから作った1日限りの符号を回数の制限にだけ使い、翌日に削除します。</p>\n<p>マイページの「利用状況の統計に協力する」でいつでも止められます。ブラウザの「トラッキングしない」(DNT・Global Privacy Control)がオンのときは、初めから止まっています。</p>'
PUSH_SECTION = '<h2 id="push">通知(任意)</h2>\n<p>マイページの「この端末に通知を届ける」を押し、ブラウザで許可したときだけ通知を使えます。当サイトのサーバーに保存するのは、ブラウザが作った通知の宛先(購読情報)と、知らせる日(日付と、朝か夜か)だけです。予定の名前・時刻・メモ・やることの内容は保存しません。通知の文は、お使いの端末の中で作ります。</p>\n<p>通知は、当サイトが GitHub Actions(GitHub, Inc.)で動かす送信プログラムから、お使いのブラウザのプッシュ配信サービス(Google、Apple、Mozilla など)を通して届きます。「通知を止める」を押すか、ブラウザの設定で通知を止めると、購読情報はサーバーから削除します。配信サービスから「宛先がない」と返されたものも削除します。</p>'
MEMBERS_SECTION = '<h2 id="members">会員登録(任意)</h2>\n<p>会員登録は無料で、パスワードはありません。メールアドレスに送る確認コードでログインします。サーバーに保存するのは、メールアドレス、登録日、プランと無料期間、紹介コード、ログイン中の端末の印(ランダムな値の要約)です。「メールでもお知らせする」をオンにした人に限り、知らせる日(日付と、朝か夜か)と予定の名前(短く)も保存します。オフにすると、その部分はすぐ消します。</p>\n<p>これらは、サーバーの公開されない場所に暗号化して保存します。記録した日・メモ・やることの内容そのものは、会員でも端末の中だけにあります。ペンネームを入れて公開に同意した人は、そのペンネームを協力者のページに載せます。紹介の確認のため、サイトを使った日(直近20日分)を保存します。モニターのアンケートの答えは、サイトの改善のためだけに使い、運営者だけが読みます。確認コードのメールは、ログインのためだけに送ります。広告のメールは、別に同意した人にしか送りません。マイページの「退会する」で、会員の記録はすぐ消えます。</p>'
GOOGLE_SECTION = '<h2 id="google">Google アカウントでの引き継ぎ(任意)</h2>\n<p>マイページの「Google アカウントで同期する」を押したときだけ、Google の画面が開きます。許可するのは、あなたの Google ドライブの中にあるこのサイト専用の非表示フォルダ(アプリデータ)への保存だけです。記録した日・予定に入れた日・設定をそこに保存し、別の端末で読み込めます。当サイトのサーバーには送りません。Google アカウントの氏名やメールアドレスは取得しません。</p>\n<p>やめるときは、<a href="https://myaccount.google.com/permissions" rel="noopener" target="_blank">Google アカウントの権限の管理</a>で「あと何日、もう何日」の権限を削除してください。</p>'


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


_ACTIONS = True   # the review build (review.py) switches the card buttons off: it has no application behind them


def card_html(e: dict, *, own: bool = False, actions: bool | None = None, big: bool = False, link: bool = True) -> str:
    """The card markup; app.js cardHtml builds the same thing (tests/test_atomou_build.py compares the class lists).
    No source line here: the source and the check date are on the detail page ("詳細")."""
    if actions is None:
        actions = _ACTIONS
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


BUNDLE = ('core', 'ics', 'app', 'plan', 'quick', 'guide', 'push', 'member')   # one script instead of six requests; the sources stay separate files


# ---------- site-wide wrapping (skins, scripts, body tag) ----------
def _wordmark() -> str:
    """assets/wordmark.svg (made by atomou/design/logo/make_wordmark.py from the outlines of Noto Sans JP, SIL OFL) inlined, its colours as variables a skin may set."""
    f = HERE / "assets" / "wordmark.svg"
    svg = f.read_text(encoding="utf-8").strip() if f.exists() else ""
    for old, new in (("#1A56B8", "var(--wm-ato,#1A56B8)"), ("#C2410C", "var(--wm-mou,#C2410C)"), ("#1F2937", "var(--wm-ink,currentColor)")):
        svg = svg.replace(f'"{old}"', f'"{new}"')
    return '<span class="wm">' + svg.replace("<svg ", '<svg class="wm-svg" focusable="false" ', 1) + "</span>" if svg else "あと何日、もう何日"


WORDMARK = _wordmark()
GUIDES = articles.load_guides()   # data/atomou/guides.json: what each subject is (written once per subject)



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



# the AdSense code (sitekit puts it in every page's head) stays only on the pages that are content: never on the app (record, calendar, my page, plan, search, skins, thanks),
# and never on a quiet day or an item with ad_ok false (see event_page)
ADS_KINDS = {"home", "category", "event", "use", "today", "manual"}
_ADS_TAG = re.compile(r'<script async src="https://pagead2\.googlesyndication\.com/[^"]*"[^>]*></script>\n?')


def strip_ads(html: str) -> str:
    return _ADS_TAG.sub("", html)


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
                "skins": {s["id"]: {"card": s["card"], "name": s["name"], "attrs": s.get("attrs", {}), **({"dark": True} if s.get("dark") else {}), **({"season": s["season"]} if s.get("season") else {})} for s in skins.SKINS}}
        if cfg.get("google_client_id"):
            conf["gclient"] = cfg["google_client_id"]
        if cfg.get("vapid_public"):
            conf["vapid"] = cfg["vapid_public"]
        if members_on(cfg):
            conf["members"] = {"tiers": {t["id"]: t.get("label", t["id"]) for t in cfg.get("member_tiers") or []},
                               "ref": int(cfg.get("member_ref_months", 6)), "give": int(cfg.get("member_ref_give_months", 1)), "cap": int(cfg.get("member_ref_cap", 12))}
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
        html = layout(self.site, self.cfg, self.preview, path=path, title=title, description=desc, body=body, og_image="/assets/og.png")   # the share picture (make_og.py)
        return self.finish(html, kind, noindex)

    def finish(self, html: str, kind: str, noindex: bool = False) -> str:
        extra = ""
        if kind not in ADS_KINDS:
            html = strip_ads(html)
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
            f'<input type="search" id="q" name="q" value="{esc(q)}" placeholder="年賀状、共通テスト、流星群…" autocomplete="off" enterkeyhint="search">'
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
    body = f"""<section class="hero"><h1>{esc(CATCH)}</h1>
<div class="hero-cta" id="hero-cta" hidden>
<p class="hero-note">登録なしで、無料で使えます。名前も日付も、この端末の中だけに残ります。</p>
<p class="hero-btns"><a class="btn" href="/add/">自分の日を残す</a></p>
<nav class="chiprow" aria-label="残せる日の例"><a class="chip" href="/add/?kind=anniversary">記念日</a><a class="chip" href="/add/?kind=birthday">誕生日</a><a class="chip" href="/add/?kind=until">楽しみな日・期限</a><a class="chip" href="/add/?kind=memorial">大切な人を思う日</a></nav>
</div></section>
<div id="season" class="season" hidden></div>
<div id="blocks">
<section id="todo" data-block="todo" data-title="今日の予定・やること" hidden>
<div class="head-row"><h2>今日の予定・やること</h2><div class="grow"><a class="btn small ghost" href="/calendar/">カレンダー</a></div></div>
<ul class="plist" id="todo-list"><li class="muted">読み込み中…</li></ul>
</section>
<section data-block="search" data-title="さがす">
{search_form()}
</section>
<section data-block="cats" data-title="ジャンル"><nav class="chiprow" aria-label="ジャンルから探す">{chips}</nav></section>
<section data-block="daily" data-title="今日の数字"><div class="daily" id="daily" aria-label="今日の数字"><span>今日の日付と、年末・年度末までの日数。</span></div></section>
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
<p class="edit-home"><button type="button" class="btn small ghost" id="edit-home" aria-pressed="false">ホームを編集</button> <button type="button" class="btn small ghost" id="reset-home" hidden>元に戻す</button></p>"""
    return c.page("/", f"{NAME}|{CATCH}", "あの日からもう何日、あの日まであと何日。日付を選ぶだけで数えて、カレンダーに残せます。締切・試験・大会・お祭りの確認済みの日付は、ワンタップで予定に。", body, "home")


def search_page(c: Ctx) -> str:
    chips = '<button type="button" class="chip" data-g-chip="" aria-pressed="true">すべて</button>' + "".join(
        f'<button type="button" class="chip" data-g-chip="{SLUGS[i]}" aria-pressed="false">{esc(g)}</button>' for i, g in enumerate(catalog.GROUPS))
    body = f"""{crumbs([("トップ", "/"), ("さがす", None)])}
<h1>日付をさがす</h1>
<p class="lead muted">言葉を入れるか、ジャンルを選びます。</p>
{search_form()}
<div class="chips" role="group" aria-label="ジャンル">{chips}<button type="button" class="chip" id="f-son" aria-pressed="false">お金や手続きの日だけ</button></div>
<p class="small muted" id="found" aria-live="polite">&nbsp;</p>
<div class="cards" id="results"></div>
<div class="panel" id="none" hidden><p>見つかりませんでした。</p><p>言葉を短くするか、ジャンルを「すべて」にしてみてください。この言葉のまま<a id="none-add" href="/add/">自分の日として残す</a>こともできます。</p><p class="muted">載せてほしい日があれば、<a id="none-ask" href="/contact/?kind=request">載せてほしい日として送る</a>こともできます。</p></div>
<noscript><p class="notice">検索には JavaScript が必要です。<a href="/c/deadline/">ジャンルのページ</a>からも探せます。</p></noscript>"""
    return c.page("/search/", f"日付をさがす | {NAME}", "言葉やジャンルから、締切・試験・大会・お祭りの日付を探せます。見つけた日は、ワンタップで予定に。", body, "search")


def my_page(c: Ctx) -> str:
    sync_html = ""
    push_html = PUSH_BOX if c.cfg.get("vapid_public") else ""
    member_html = MEMBER_BOX if members_on(c.cfg) else ""
    if c.cfg.get("google_client_id"):
        sync_html = ('<h2 id="sync">別の端末に引き継ぐ</h2>\n<div class="panel" id="sync-box" hidden>'
                     '<p>Google アカウントでつなぐと、記録した日を自分の Google ドライブに保存して、別の端末に引き継げます。当サイトのサーバーには預けません。'
                     '<a href="/privacy/#google">詳しく</a></p><p><button type="button" class="btn" id="sync-now">Google アカウントで同期する</button></p></div>\n')
    body = f"""{crumbs([("トップ", "/"), ("マイページ", None)])}
<h1>マイページ</h1>
<p class="lead muted">記録した日と予定に入れた日が並びます。この端末の中だけに保存します。</p>
<div class="panel" id="my-empty" hidden><p>まだ記録はありません。まず1つ、忘れたくない日を残せます。</p><p class="muted">名前も日付も、この端末の中だけに保存されます。</p><p><a class="btn" href="/add/">日を残す</a> <a class="btn ghost" href="/search/">公式の日付をさがす</a></p></div>
<div class="head-row" id="my-tools" hidden><div class="grow" style="margin-left:0"><button type="button" class="btn small ghost" id="reorder" aria-pressed="false">並べ替え</button></div></div>
<div class="cards" id="my-grid" data-save-order="1"></div>
<h2>設定</h2>
<div class="panel">
<div class="field"><label class="lab" for="p-big"><input type="checkbox" id="p-big"> 文字を大きくする</label></div>
<div class="field"><label for="p-alarm">お知らせの時間</label>
<select id="p-alarm"><option value="morning">当日の朝</option><option value="eve">前日の夜</option><option value="week">1週間前の朝</option><option value="none">なし</option></select></div>
<div class="field"><label class="lab" for="p-stats"><input type="checkbox" id="p-stats"> 利用状況の統計に協力する(個人は特定されません。<a href="/privacy/#stats">詳しく</a>)</label></div>
<p><a href="/skins/">きせかえ</a></p>
<p><a href="/?edit=1">ホームを編集</a></p>
</div>
{member_html}{push_html}{sync_html}<h2>他のカレンダーアプリに入れる</h2>
<div class="panel"><p>iPhone の「カレンダー」や Google カレンダーに取り込めるファイルを作れます。1件ずつ作るときは、予定の詳細から。</p>
<p><button type="button" class="btn small ghost" id="ics-all">すべての予定をファイルにする</button></p></div>
<h2 id="backup-h">バックアップ</h2>
<div class="panel">
<p>記録はこの端末の中だけにあります。機種変更の前に書き出し、新しい端末で読み込んでください。</p>
<p><button type="button" class="btn small" id="backup">書き出す</button>
<label class="btn small ghost" for="restore">読み込む</label><input class="vh" type="file" id="restore" accept="application/json,.json">
<button type="button" class="btn small ghost" id="wipe">すべて消す</button></p>
</div>
<noscript><p class="notice">マイページには JavaScript が必要です。</p></noscript>"""
    return c.page("/my/", f"マイページ | {NAME}", "記録した日と、予定に入れた日の一覧。この端末の中だけに保存します。", body, "my", noindex=True)


def add_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("記録する", None)])}
<h1>日付を記録する</h1>
<p class="lead muted">日付を選ぶだけで数えます。年だけでも残せます。</p>
<div id="wizard" class="wizard"><noscript><p class="notice">日付の記録には JavaScript が必要です。</p></noscript></div>"""
    return c.page("/add/", f"日付を記録する | {NAME}", "記念日・誕生日・はじめた日・命日を、選ぶだけで記録。あと何日、もう何日かをその場で数えます。", body, "add")


def calendar_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", None)])}
<h1>カレンダー</h1>
<p class="lead muted">記録した日と予定に入れた日が並びます。日を押すと、その日の予定とやることが出ます。</p>
<div id="cal"></div>
<noscript><p class="notice">カレンダーには JavaScript が必要です。</p></noscript>"""
    return c.page("/calendar/", f"カレンダー | {NAME}", "記録した日と公式の日付を、月のカレンダーと一覧で。予定ごとにメモと「何日前までにやること」を書けます。", body, "calendar")


def plan_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", "/calendar/"), ("予定の詳細", None)])}
<h1>予定の詳細</h1>
<div id="plan"><p class="muted">読み込み中…</p></div>
<noscript><p class="notice">予定の詳細には JavaScript が必要です。</p></noscript>"""
    return c.page("/plan/", f"予定の詳細 | {NAME}", "予定のメモと、何日前までにやること。この端末の中だけに保存します。", body, "plan", noindex=True)


def skins_page(c: Ctx) -> str:
    def tile(s: dict) -> str:
        v = s["vars"]
        sw = "".join(f'<i style="background:{v[k]}"></i>' for k in ("bg", "surface", "accent", "ato", "mou"))
        return (f'<button type="button" class="skin" data-skin="{s["id"]}" data-name="{esc(s["name"])}" aria-pressed="false"><span class="sw">{sw}</span>'
                f'<b>{esc(s["name"])}</b><small>{esc(s["desc"])}</small></button>')
    t = c.today
    samples = [
        {"id": "s1", "title": "申込の締切(例)", "date": (t + timedelta(days=45)).isoformat(), "kind": "締切", "g": 1, "quiet": False},
        {"id": "s2", "title": "はじめた日(例)", "date": (t - timedelta(days=400)).isoformat(), "kind": "はじめた日", "g": 4, "quiet": False},
        {"id": "s3", "title": "祖父を思う日(例)", "date": (t - timedelta(days=800)).isoformat(), "kind": "大切な人を思う日", "g": 0, "quiet": True},
    ]
    body = f"""{crumbs([("トップ", "/"), ("きせかえ", None)])}
<h1>きせかえ</h1>
<div id="season" class="season" hidden></div>
<p class="lead muted">選ぶと、すぐ変わります。標準は「ベーシック」。</p>
<h2>見え方</h2>
<p class="hint">左から、これから来る日、過ぎた日、大切な人を思う日(静かな表示)。</p>
<div class="cards">{"".join(card_html(s, own=True, actions=False, link=False) for s in samples)}</div>
<h2>選ぶ</h2>
<p><label class="chip" for="skin-auto"><input type="checkbox" id="skin-auto"> 端末が暗い設定のときは、暗い配色にする</label></p>
<div class="skins" id="skin-list">{"".join(tile(s) for s in skins.SKINS)}</div>
<noscript><p class="notice">きせかえには JavaScript が必要です。</p></noscript>"""
    return c.page("/skins/", f"きせかえ | {NAME}", "きせかえは20種類以上。大きな文字、やさしい色、にぎやかな色まで。", body, "skins")


def use_index(c: Ctx) -> str:
    secs = []
    for name, items in usecases.grouped():
        secs.append(f"<h2>{esc(name)}</h2><div class=\"uc-grid\">" + "".join(
            f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>' for u in items) + "</div>")
    body = f"""{crumbs([("トップ", "/"), ("こんな時に", None)])}
<h1>こんな時に使えます</h1>
<p class="lead muted">場面ごとの使い方です。</p>
{"".join(secs)}"""
    return c.page("/use/", f"こんな時に使えます | {NAME}", "付き合った記念日、大切な人を思う日、確定申告、受験、推し活。使い方を場面ごとに。", body, "use")


def use_page(c: Ctx, u: dict) -> str:
    quiet = u["quiet"]
    steps = "".join(f"<li>{esc(s)}</li>" for s in u["steps"])
    parts = [f'<p class="lead">{esc(u["situation"])}</p>', f'<p class="small muted">こんな方に: {esc(u["who"])}</p>', f"<h2>やり方</h2><ol class=\"steps\">{steps}</ol>"]
    acts = []
    if u["own"]:
        o = u["own"]
        acts.append(f'<a class="btn" href="/add/?kind={o["kind"]}&amp;title={quote(o["label"])}">この日を残す</a>')
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
    body = crumbs([("トップ", "/"), ("こんな時に", "/use/"), (u["title"], None)]) + f'<h1>{esc(u["title"])}</h1>\n' + "\n".join(parts)
    return c.page(f"/use/{u['slug']}/", f"{u['title']} | {NAME}", u["situation"], body, "use")


def event_page(c: Ctx, e: dict, indexable: bool, live: list[dict]) -> str:
    quiet = e["quiet"]
    today = c.today
    d = date.fromisoformat(e["date"])
    n = (d - today).days
    word = "今日です" if n == 0 else (f"あと{n}日です" if n > 0 else f"もう{-n}日です")
    fmt = fmt_date(e["date"], e["precision"])
    end = f"〜{fmt_date(e['date_end'])}" if e.get("date_end") else ""
    rel = [] if quiet else [r for r in live if r["group"] == e["group"] and r["id"] != e["id"] and not r["quiet"]][:4]
    near = [] if quiet or e["precision"] != "day" else sorted(
        (r for r in live if r["id"] != e["id"] and not r["quiet"] and r["precision"] == "day" and r not in rel and abs((date.fromisoformat(r["date"]) - d).days) <= 10),
        key=lambda r: (abs((date.fromisoformat(r["date"]) - d).days), r["date"], r["id"]))[:4]   # the days around it: a reason to look at the next page
    sentence = (f"{e['title']}は、{fmt}{end}です。" if e["precision"] == "day" else f"{e['title']}は、{fmt}です。") + (
        f"{today.year}年{today.month}月{today.day}日の時点で、{word}。" if e["precision"] == "day" else "")
    guide = GUIDES.get(e["subject"])
    art = articles.article_html(e, fmt_date, host(e["source_url"]), today, guide)   # what the day is, when and where, what to check, the usual questions
    same = [] if quiet else sorted((r for r in live if r["subject"] == e["subject"] and r["id"] != e["id"] and not r["quiet"]), key=lambda r: (r["date"], r["id"]))[:6]
    body = crumbs([("トップ", "/"), (e["group"], f"/c/{GROUP_SLUG[e['group']]}/"), (e["title"], None)]) + f"""
<h1>{esc(e['title'])}</h1>
{card_html(e, big=True, link=False)}
{'<p class="small muted">上のカードは、今日の日付で数えた数字です。</p>' if art else f'<p>{esc(sentence)}<span class="small muted">上のカードは、今日の日付で数えた数字です。</span></p>'}
{art}
{'<p class="notice quiet">この日は、静かにお知らせします。</p>' if quiet else ""}
<h2>出典と確認した日</h2>
<dl class="info"><dt>出典</dt><dd><a href="{esc(e['source_url'])}" rel="noopener nofollow" target="_blank">{esc(host(e['source_url']))}</a></dd>
<dt>確認した日</dt><dd>{esc(e['checked_on'])}</dd>{f"<dt>出典の文</dt><dd>{esc(e['source_quote'])}</dd>" if e.get('source_quote') else ""}</dl>
<p class="small muted">日付は変わることがあります。申し込みや手続きの前に、出典の公式ページでご確認ください。</p>
<p><a class="btn small" href="/plan/?key=c:{e['id']}">メモ・やることを書く</a> <a class="btn small ghost" href="/add/?title={quote(e['title'])}&amp;date={e['date']}">自分の日として残す</a></p>
{f'<details class="more"><summary>他のカレンダーアプリに入れる</summary><p class="hint">iPhone の「カレンダー」や Google カレンダーに取り込めるファイルです。</p><p><button type="button" class="btn small ghost" data-ics-for="c:{e["id"]}">ファイルを作る</button></p></details>' if e["precision"] == "day" else ""}
{(f'<h2>同じ「{esc(e["subject"])}」の日</h2><div class="cards">' + "".join(card_html(r) for r in same) + "</div>") if same else ""}
{('<h2>同じジャンルの日</h2><div class="cards">' + "".join(card_html(r) for r in rel) + "</div>") if rel else ""}
{('<h2>同じ頃の日</h2><p class="hint">この日の前後10日にある日です。</p><div class="cards">' + "".join(card_html(r) for r in near) + "</div>") if near else ""}"""
    suffix = "からもう何日？" if e["status"] == "ended" else "はいつ？あと何日？"
    title = f"{e['title']}{suffix} {fmt} | {NAME}"
    place = (e.get("place") or "").strip()
    desc = f"{e['title']}は{fmt}{end}" + (f"、{place}" if place and place not in ("全国", "地域") else "") + "。" + (f"{guide['about'].split('。')[0]}。" if guide else "") + "出典と確認した日つき。あと何日かを数えて、予定に入れられます。"
    html = c.page(f"/e/{e['id']}/", title, desc, body, "event", noindex=not indexable)
    return strip_ads(html) if quiet or not e.get("ad_ok", True) else html


def category_page(c: Ctx, group: str, live: list[dict]) -> str:
    rows = [e for e in live if e["group"] == group][:200]
    cats: list[str] = []
    for e in rows:
        if e["category"] not in cats:
            cats.append(e["category"])
    chips = ""
    if len(cats) > 1:
        chips = ('<div class="chips" role="group" aria-label="絞り込み"><button type="button" class="chip" data-cat-chip="" aria-pressed="true">すべて</button>'
                 + "".join(f'<button type="button" class="chip" data-cat-chip="{esc(x)}" aria-pressed="false">{esc(x)}</button>' for x in cats) + "</div>")
    body = f"""{crumbs([("トップ", "/"), (group, None)])}
<h1>{esc(group)}の日付</h1>
<p class="lead muted">{esc(GROUP_LEAD[group])}</p>
{search_form()}
{chips}
<div class="cards" id="grid">{"".join(card_html(e) for e in rows)}</div>"""
    if not rows:
        body = body.replace('<div class="cards" id="grid"></div>', '<p class="empty">いまは日付がありません。</p>')
    return c.page(f"/c/{GROUP_SLUG[group]}/", f"{group}の日付一覧 | {NAME}", f"{GROUP_LEAD[group]}あと何日かが一目で分かり、ワンタップで予定に入れられます。", body, "category")


def manual_page(c: Ctx) -> str:
    t = c.today
    sample = {"id": "sample", "title": "家族で行く旅行の日(例)", "date": (t + timedelta(days=45)).isoformat(), "kind": "予定", "g": 1, "quiet": False}
    past = {"id": "sample2", "title": "禁煙をはじめた日(例)", "date": (t - timedelta(days=400)).isoformat(), "kind": "はじめた日", "g": 4, "quiet": False}

    def step(n: int, head: str, text: str) -> str:
        return f'<div class="stepcard"><span class="no" aria-hidden="true">{n}</span><div><b>{head}</b><p>{text}</p></div></div>'

    def btn(label: str, ghost: bool = False) -> str:
        return f'<span class="btn small sample{" ghost" if ghost else ""}" aria-hidden="true">{label}</span>'

    qa = [
        ("料金はかかりますか？", "無料です。会員登録なしで使えます。会員(無料)になると、メールのお知らせと先着の特典が使えます。"),
        ("入力した内容は、ほかの人に見えますか？", "見えません。予定・メモ・やることは、お使いの端末の中だけにあり、当サイトのサーバーには送りません。"),
        ("予定の前に、お知らせは来ますか？", "マイページの「この端末への通知」をオンにすると、予定の当日の朝か前日の夜に、この端末へ通知が届きます(iPhone はホーム画面に追加してから)。会員はメールでも受け取れます。他のカレンダーアプリの通知を使うときは、予定の詳細の「他のカレンダーアプリに入れる」でファイルを作って取り込みます。"),
        ("「やること」とは何ですか？", "予定の何日前までに何をするかを書く欄です。たとえば「試験の1週間前: 願書を出す」。期限の日がカレンダーとホームに出て、チェックで済みになります。"),
        ("機種変更をしたら、記録はどうなりますか？", "自動では引き継がれません。変更の前にマイページの「書き出す」でファイルを作り、新しい端末で「読み込む」を押します。マイページに Google アカウントでの引き継ぎが出ていれば、それも使えます。"),
        ("「あと」と「もう」の違いは？", "「あと」はこれから来る日まで、「もう」は過ぎた日からの日数です。"),
        ("日数はどう数えますか？", "今日を0日とします。明日は「あと1日」、昨日は「もう1日」、当日は「今日」です。"),
        ("2月29日はどう数えますか？", "うるう年でない年は、2月28日として数えます。"),
        ("文字が小さくて読みにくい。", "マイページの「設定」で「文字を大きくする」にチェックを入れます。「きせかえ」の「大きな文字」「ハイコントラスト」も読みやすい設定です。"),
        ("日付が間違っているようです。", "公式の日付は変わることがあります。カードの「詳細」に出典と確認した日があります。誤りは<a href=\"/contact/\">お問い合わせ</a>からお知らせください。"),
        ("大切な人を思う日も入れられますか？", "入れられます。「大切な人を思う日」を選ぶと、静かな見た目で残ります。広告やおすすめは出しません。"),
        ("入れた日を消すには？", "マイページかカレンダーからその予定を開き、「消す」を押します。すべて消すときは、マイページの「すべて消す」。"),
    ]
    qa_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in qa)
    body = f"""{crumbs([("トップ", "/"), ("説明書", None)])}
<div class="manual">
<h1>説明書</h1>
<p class="lead">「あと何日、もう何日」の使い方です。画面のガイドは、実際のボタンを指しながら案内します。</p>
<p><button type="button" class="btn" data-guide="start">ガイドを見る</button> <span class="hint">各ページ右下の「ガイド」からも見られます。</span></p>

<h2>できること</h2>
<ul class="big-list">
<li><b>日付を数える。</b>あの日からもう何日、あの日まであと何日。</li>
<li><b>カレンダーとして使う。</b>デート・会議・記念日を入れて、月と一覧で見ます。予定ごとに、メモと「何日前までにやること」を書けます。</li>
<li><b>お知らせを受け取る。</b>予定の当日の朝か前日の夜に、この端末へ通知が届きます。</li>
<li><b>公式の日付を使う。</b>締切・試験・大会・お祭りの日付を、公式の発表で確認して載せています。「予定に入れる」で、カレンダーに入ります。</li>
</ul>

<h2>はじめて使うとき</h2>
{step(1, "「記録する」を押す", "画面の上の「記録する」(下のメニューでは「記録」)を押します。")}
{step(2, "どんな日かを選ぶ", "「予定」「記念日」「誕生日」から近いものを選びます。デートや会議は「予定」。文字の入力は要りません。")}
{step(3, "日付を選ぶ", "日付の欄を押すとカレンダーが開きます。「予定」は時刻も入れられます。")}
{step(4, "「この日を残す」を押す", "残すと、予定の詳細が開きます。続けて、メモと「やること」を書けます。")}
<p class="hint">年や月までしか分からない日は、「年と月だけ」「年だけ」で残せます。</p>

<h2>カレンダー</h2>
<ul class="big-list">
<li>「カレンダー」を押すと、月の表が出ます。「一覧」にすると、今日から60日の予定とやることが日ごとに並びます。</li>
<li>日を押すと、その日の予定とやることが下に出ます。「この日に予定を追加」で、その日の予定を残せます。</li>
<li>予定を押すと、詳細が開き、メモと「やること」を書けます。</li>
</ul>

<h2>メモと「やること」</h2>
<p>予定の詳細の「やること」に、何日前までに何をするかを書きます。たとえば次のように。</p>
<ul class="big-list">
<li>試験: 「1週間前: 願書を出す」「1日前: 持ち物を確認する」</li>
<li>引っ越し: 「2週間前: 役所の手続き」「3日前: 荷造りを終える」</li>
</ul>
<p>期限の日はカレンダーに出ます。今日が期限のものはホームの「今日の予定・やること」に出て、そこでチェックできます。</p>

<h2>カードの見方</h2>
<p>日付は「カード」で表示します。</p>
<div class="cards" style="max-width:360px;grid-template-columns:1fr">{card_html(sample, own=True, actions=False, link=False)}</div>
<ul class="big-list">
<li><b>「あと」</b> … これから来る日までの日数。</li>
<li><b>大きな数字</b> … 日数。100日を超えると「2年3か月12日」の形になり、下に合計の日数が出ます。</li>
<li><b>日付</b> … その日の年月日と曜日。</li>
</ul>
<p>過ぎた日はこの形です。「<b>もう</b>」は、その日から今日までの日数。</p>
<div class="cards" style="max-width:360px;grid-template-columns:1fr">{card_html(past, own=True, actions=False, link=False)}</div>

<h2>ボタン</h2>
<dl class="info big-dl">
<dt>{btn("☆ 予定に入れる")}</dt><dd>公式の日付を自分のカレンダーに入れます。入ると「★ 予定に入っています」に変わり、もう一度押すと外れます。</dd>
<dt>{btn("詳細", True)}</dt><dd>出典(元のページ)と確認した日を開きます。</dd>
<dt>{btn("開く")}</dt><dd>自分の予定の詳細を開きます。名前や日付の修正、メモと「やること」の記入もここから。</dd>
<dt>{btn("消す", True)}</dt><dd>自分の予定を消します。</dd>
<dt>{btn("シャッフル")}</dt><dd>ホームのカードを、別の日に入れ替えます。</dd>
<dt>{btn("並べ替え", True)}</dt><dd>カードの順をボタンで変えます。ドラッグ(スマホは長押し)でも動かせます。</dd>
<dt>{btn("さがす")}</dt><dd>言葉で日付を探します。「年賀状」「流星群」のように入れます。</dd>
<dt>{btn("きせかえ", True)}</dt><dd>色や形、文字の大きさを変えます。季節のきせかえもあります。</dd>
<dt>{btn("ホームを編集", True)}</dt><dd>ホームのブロックの順を変え、非表示にできます。ホームのいちばん下にあります。</dd>
</dl>

<h2>よくある質問</h2>
<div class="qa">{qa_html}</div>
<p>解決しないときは、<a href="/contact/">お問い合わせ</a>へ。</p>
<p><a class="btn" href="/add/">記録する</a> <a class="btn ghost" href="/use/">こんな時に</a></p>
</div>"""
    return c.page("/manual/", f"説明書 | {NAME}", "「あと何日、もう何日」の説明書。記録のしかた、カレンダーとやること、カードの見方、ボタン、よくある質問。", body, "manual")


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
        return '<p class="small">使い方の例: ' + " / ".join(f'<a href="{h}">{esc(t)}</a>' for t, h in links) + "</p>"

    body = f"""{crumbs([("トップ", "/"), ("今日の数字", None)])}
<h1>今日の数字</h1>
<p class="lead muted">年末や年度末までの日数と、その準備の目安です。選ぶと、その日までを自分の日として残せます。</p>
<section id="today"><h2>今日は {n("today")}</h2>
<p>数字は、お使いの端末の日付で数えています。</p></section>

<section id="year">
<h2>{n("y")}年は、もう{n("year")}日め</h2>
<p>年末まで、あと{n("year-left")}日です。</p>
{purposes([("年賀状の準備", "年末までの予定に", "until", "year-end"), ("ふるさと納税の期限", "その年の分は12月31日が目安", "until", "year-end"),
           ("年末の大掃除・買い出し", "年内の予定に", "until", "year-end"), ("年内に済ませたい手続き", "名前は自由に", "until", "year-end")])}
{more([("年賀状", "/use/nengajo/"), ("ふるさと納税", "/use/furusato-nozei/"), ("年末までの日数", "/use/year-end-count/")])}
</section>

<section id="newyear">
<h2>{n("newyear-y")}年まで、あと{n("newyear")}日</h2>
<p>新年の準備を始める目安に。</p>
{purposes([("お正月の準備", "おせち・帰省・買い物", "until", "new-year"), ("帰省・旅行の予約", "混む時期の予約に", "until", "new-year"),
           ("初詣の予定", "家族や友人との予定に", "until", "new-year")])}
{more([("初詣・初日の出の日付", "/search/?q=%E5%88%9D%E8%A9%A3")])}
</section>

<section id="fy">
<h2>{n("fy-y")}年度は、あと{n("fy")}日</h2>
<p>年度は4月から翌年3月まで。</p>
{purposes([("入学の用意", "入学式までの準備に", "until", "fy-start"), ("新学期の用意", "学用品や手続きに", "until", "fy-start"),
           ("引っ越しの用意", "年度末は混むので早めの予約を", "until", "fy-end"), ("年度末の手続き", "締切のある手続きに", "until", "fy-end"),
           ("転職・異動の準備", "新年度の準備に", "until", "fy-start")])}
{more([("年度末までの日数", "/use/fiscal-year-end/"), ("引っ越しの手続き", "/use/moving-procedure/"), ("就職活動", "/use/job-hunting/")])}
</section>

<section id="start">
<h2>今日から数える</h2>
<p>今日を「はじめた日」にして、続けた日数を数えます。</p>
{purposes([("禁煙をはじめた日", "続けた日数が毎日増えます", "since", "today"), ("習慣をはじめた日", "運動・勉強・早起き", "since", "today"),
           ("今日のできごと", "あとから「もう何日」と見返せます", "memo", "today")])}
{more([("禁煙", "/use/quit-smoking/"), ("習慣", "/use/habit-streak/")])}
</section>
<p>当てはまらないときは、<a href="/add/">自分で日付を入れる</a>こともできます。</p>"""
    return c.page("/today/", f"今日の数字 | {NAME}", "年末まであと何日、来年まであと何日、年度末まであと何日。入学や引っ越しの準備を、自分の日として残せます。", body, "today")


SW_PUSH = """// push: the message says only which day and slot (m = morning, e = the evening before); the text comes from the mirror that push.js keeps in the cache
const TITLE = 'あと何日、もう何日';
self.addEventListener('push', (e) => {
  e.waitUntil((async () => {
    let d = {};
    try { d = e.data ? e.data.json() : {}; } catch (x) { d = {}; }
    const key = String(d.d || '') + '|' + (d.s === 'e' ? 'e' : 'm');
    let lines = [];
    try { const c = await caches.open('atomou-notice'); const r = await c.match('/_notice'); if (r) { const m = await r.json(); lines = Array.isArray(m[key]) ? m[key] : []; } } catch (x) { lines = []; }
    const body = lines.length ? lines.map((l) => l.t).join('\\n') : (d.s === 'e' ? '明日の予定があります。' : '今日の予定・やることがあります。');
    const url = (lines.length === 1 && lines[0].u) ? lines[0].u : '/';
    await self.registration.showNotification(TITLE, { body, icon: '/assets/icon-192.png', tag: 'atomou-' + key, data: { url } });
  })());
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((ws) => {
    for (const w of ws) { if ('focus' in w) { if ('navigate' in w) w.navigate(url); return w.focus(); } }
    return clients.openWindow(url);
  }));
});
"""


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
            "});\n" + SW_PUSH)


html_escape = esc


def thanks_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("協力者のページ", None)])}
<h1>協力者のページ</h1>
<p class="lead muted">紹介してくださった方と、ご意見がサイトの改善につながったモニターの方を、毎月ご紹介します。</p>
<div class="panel"><p><b>毎月お贈りするもの</b></p><ul>
<li>紹介の人数が多かった方: 1位は無料期間を3か月、2位と3位は1か月延長。1位には称号「紹介の達人」。</li>
<li>ご意見が採用されたモニターの方: 無料期間を1か月延長し、称号「名誉モニター」。</li>
</ul><p class="hint">紹介の人数は、紹介で登録した方が1週間以上あけて2回使ったときに数えます。名前は、ご本人が公開に同意したペンネームだけを載せます。特典は期間の延長と称号で、お金や商品ではありません。延長は、次にサイトを開いたときに反映します。</p></div>
<div id="thanks-list"><p class="muted">読み込み中…</p></div>
<noscript><p class="notice">このページには JavaScript が必要です。</p></noscript>"""
    return c.page("/thanks/", f"協力者のページ | {NAME}", "紹介とご意見でサイトに協力してくださった方を、毎月ペンネームでご紹介します。", body, "thanks", noindex=True)


def terms_page(c: Ctx) -> str:
    op = html_escape(c.cfg.get("operator_name") or "運営者")
    body = f"""{crumbs([("トップ", "/"), ("利用規約", None)])}
<h1>利用規約</h1>
<p class="lead muted">「{NAME}」(以下「当サイト」)の会員機能を使うときの決まりです。会員にならなくても、当サイトは使えます。</p>
<h2>1. 会員登録</h2>
<p>会員登録は無料です。メールアドレスだけで登録でき、パスワードはありません。1人1つのメールアドレスで登録してください。13歳未満の方は、保護者の同意を得てください。</p>
<h2>2. 無料期間と先着の特典</h2>
<p>先着の枠は 2 種類あり、同時に募集します。「先着モニター」と「先着」のどちらかを選んで登録します。どちらも、登録日から決められた期間、すべての機能を無料で使えます。先着モニターは、登録の1週間後と1か月後に、マイページに出る短いアンケート(1分ほど)に、それぞれ7日以内に答えることが条件です。期限を過ぎると、答えるまで画面の上にお願いを表示します。答えなかったときも、無料期間は取り消しません。先着モニターの枠が埋まっているときは、先着の枠で登録します。期間はマイページに表示します。人数と期間は当サイトが定め、途中で変えません。期間が終わっても、自動で料金がかかることはありません。</p>
<h2>3. 紹介</h2>
<p>紹介リンクから登録した人には、無料期間が付きます。紹介した人の無料期間は、紹介で登録した人が1週間以上あけて2回使ったときに延びます(人数に上限があります)。特典は期間の延長だけで、お金や商品はありません。自分で自分を紹介すること、同じ人が複数のアドレスで登録することは、特典の対象外です。</p>
<h2>3-2. 協力者のページ</h2>
<p>紹介の人数と、採用されたご意見をもとに、毎月<a href="/thanks/">協力者のページ</a>でご紹介し、無料期間の延長や称号をお贈りします。載せる名前は、ご本人が公開に同意したペンネームだけです。順位や採用は当サイトが決め、その理由はお答えしないことがあります。</p>
<h2>4. お知らせのメール</h2>
<p>「メールでもお知らせする」をオンにした人にだけ、知らせる日の朝か前日の夜にメールを送ります。届かないことや遅れることがあります。大切な手続きは、公式のページでも確かめてください。</p>
<h2>5. してはいけないこと</h2>
<p>他人のメールアドレスでの登録、当サイトの仕組みに負担をかける行為、法令や公序良俗に反する使い方はしないでください。これらがあったときは、会員の登録を止めることがあります。</p>
<h2>6. 退会と記録の削除</h2>
<p>マイページの「退会する」で、いつでも退会できます。会員の記録はすぐに消えます。端末の中の記録は残ります。</p>
<h2>7. 免責</h2>
<p>表示する日付や計算が正しいよう努めますが、誤り・変更・中止があることがあります。当サイトの利用によって生じた損害について、当サイトは責任を負いません。ただし、当サイトに故意または重大な過失があるときは、この限りではありません。</p>
<h2>8. 変更</h2>
<p>この規約は、変えることがあります。変えたときは、このページで知らせます。</p>
<p class="muted">運営: {op}。制定: 2026年10月。</p>"""
    return c.page("/terms/", f"利用規約 | {NAME}", "会員機能の利用規約です。無料の会員登録、先着の特典、紹介、お知らせのメール、退会について。", body, "legal")


def privacy_fix(c: Ctx, html: str) -> str:
    """The shared privacy page says that no analytics is used; this site counts fixed items (and may offer a Google Drive hand-over), so that part is replaced."""
    if "<title>プライバシーポリシー" not in html:
        return html
    old = "<h2>アクセス解析</h2>\n<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>"
    if old not in html:
        raise BuildError("sitekit's privacy text changed: update privacy_fix in sites/atomou/build.py")
    if members_on(c.cfg):
        html = html.replace("当サイトは、会員登録などの機能を持ちません。", "会員登録は任意です(下の「会員登録(任意)」)。", 1)
    return html.replace(old, STATS_SECTION + ("\n" + PUSH_SECTION if c.cfg.get("vapid_public") else "") + ("\n" + MEMBERS_SECTION if members_on(c.cfg) else "") + ("\n" + GOOGLE_SECTION if c.cfg.get("google_client_id") else ""), 1)


def legal(c: Ctx) -> dict:
    cfg, site = c.cfg, c.site
    return legal_pages(
        site, cfg, c.preview,
        purpose="記録した日について、あと何日、もう何日かを数え、カレンダーに残せるようにすること。締切・試験・大会・お祭りの公式の日付を、ワンタップで予定に入れられるようにすること。",
        sources_html="各日付のページに、出典(官公庁・主催者の公式ページ)と確認した日を載せています。",
        update_text="公式の発表をもとに、随時確認・追加します。",
        disclaimer_html="<p>日付は公式の発表をもとに確認していますが、変更・中止されることがあります。申し込みや手続きの前に、出典の公式ページでご確認ください。当サイトの情報にもとづく行動の結果について、責任を負いかねます。</p>"
                        "<p>「あと○日」「もう○日」は、お使いの端末の日付をもとにブラウザの中で数えています。端末の日付がずれていれば、数字もずれます。</p>",
        contact_notice="日付の誤りのご指摘は、ページの名前と、正しい日付の出典(アドレス)を添えていただけると早く確認できます。",
        input_note=("<h2>この端末に保存する情報</h2>"
                    "<p>記録した日(名前・日付・時刻・メモ・やること・設定)と、予定に入れた日の一覧は、お使いのブラウザの中(localStorage)だけに保存します。当サイトのサーバーには送りません。"
                    "ブラウザのデータを消すと記録も消えます。バックアップはマイページの「書き出す」で作れます。</p>"),
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
    pages["api/push.php"] = push_php(cfg)
    if members_on(cfg):
        pages["api/m.php"] = member_php(cfg)
        pages["terms/index.html"] = terms_page(c)
        pages["thanks/index.html"] = thanks_page(c)
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


def build_demo_sub(cfg: dict, site_url: str, today: date | None = None) -> dict:
    """The full demo as a folder of the review copy, served as the root of its own host (demo.<domain>: the subdomain's document root is public_html/demo).
    The pages and the PHP receivers are those of the demo; only the site address differs (the receivers accept requests from it, canonical links name it), and the
    receivers find the site folder one level further up (public_html/demo/api/m.php -> <site folder>), so what members and subscribers send never lands in a public folder."""
    pages = build_pages({**cfg, "site_url": site_url}, release=False, today=today)
    for k, v in list(pages.items()):
        if k.endswith(".php"):
            if "dirname(__DIR__, 2)" not in v:
                raise BuildError(f"{k}: the site-folder line changed; update build_demo_sub")
            pages[k] = v.replace("dirname(__DIR__, 2)", "dirname(__DIR__, 3)")
    return pages


def render_site(cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    pages = build_pages(cfg, release, today)
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--review", action="store_true", help="the small review copy (sites/atomou/review.py): public to crawlers, not indexable, no application")
    ap.add_argument("--demo-sub", action="store_true", help="the full demo for the folder public_html/demo of the review copy (host demo.<domain>)")
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--today", default="")
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        if a.demo_sub:
            host = urlparse(cfg["site_url"]).netloc
            pages = build_demo_sub(cfg, f"https://demo.{host}", date.fromisoformat(a.today) if a.today else None)
            write_pages(pages, Path(a.out))
            files = sorted(pages)
        elif a.review:
            from sites.atomou import review
            pages = review.build_pages(cfg, date.fromisoformat(a.today) if a.today else None)
            write_pages(pages, Path(a.out))
            files = sorted(pages)
        else:
            files = render_site(cfg, Path(a.out), release=a.release, today=date.fromisoformat(a.today) if a.today else None)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
