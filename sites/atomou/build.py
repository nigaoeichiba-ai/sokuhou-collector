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
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import articles, catalog, datecore, feeds, ogimage, skins, usecases  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, asset_version, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

NAME = "あと何日、もう何日"
PREFECTURES = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
CATCH = "忘れたくない日を、お知らせします。"   # decided by the owner (2026-10-08); the copy pass may not change it
SLUGS = ["deadline", "sale", "sports", "exams", "sky", "trip", "it", "hobby", "shows", "life"]
GROUP_SLUG = dict(zip(catalog.GROUPS, SLUGS))
GROUP_LEAD = {
    "お金・税金・制度": "税金、年金、保険、最低賃金、補助金、制度の変更。期限のある手続きの日。",
    "買い物・料金・セール": "年賀状、大型セール、宝くじ、ポイントの期限、電気・宅配・食品などの料金の改定。",
    "スポーツ": "野球、サッカー、マラソン・駅伝、相撲、競馬、F1など、大会や試合の日。",
    "学校・資格": "大学入試、高校入試、資格試験、就活、奨学金の締切。",
    "天文・暦": "流星群、満月、日食、惑星、二十四節気。星と暦の節目。",
    "おでかけ・旅行": "祭り、花火、イルミネーション、紅葉、初詣、観光列車、キャンプ。出かけたい日。",
    "通信・IT・アプリ": "携帯・回線の料金、アプリやソフトのサービス終了、サポート期限。",
    "趣味・ゲーム・アニメ": "コミケ、ゲームマーケット、アニメ、将棋、手芸、盆栽、写真、即売会、車・バイクのショー。",
    "エンタメ・音楽・賞": "紅白歌合戦、ライブ、ノーベル賞、アカデミー賞、映画祭。発表や放送を待つ日。",
    "暮らし・健康・グルメ": "結婚、健康、食のイベント、旬の解禁。暮らしの節目になる日。",
}
POPULAR = ["年賀状", "ふるさと納税", "共通テスト", "流星群", "紅白", "コミケ", "最低賃金", "確定申告", "ドラフト"]
SITE = {
    "nav": [("さがす", "/search/", "/search/"), ("カレンダー", "/calendar/", "/calendar/"), ("記録する", "/add/", "/add/"), ("マイページ", "/my/", "/my/")],
    "glyph": "",
    "assets": HERE / "assets",
    "source_html": '公式の日付には、出典と確認日を載せています。<a href="/manual/">説明書</a> | <a href="/manual/#guide">使い方</a> | <a href="/use/">こんな時に</a> | <a href="/skins/">きせかえ</a>',
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


PUSH_BOX = '''<h2 id="push">この端末で受け取る通知</h2>
<div class="panel" id="push-box" hidden>
<p>予定の日ややることの期限に、この端末へ通知します。通知の時間は設定で選べます(当日の朝7時ごろ、または前日の夜21時ごろ)。サーバーに保存されるのは、通知に必要な日付だけです。予定の内容は、この端末に保存されます。<a href="/privacy/#push">詳しく</a></p>
<p id="push-status" class="muted"></p>
<p id="push-ios" class="hint" hidden>iPhone・iPad は、共有ボタンから「ホーム画面に追加」し、そのアイコンから開くと通知を使えます。</p>
<p><button type="button" class="btn" id="push-on">この端末で通知を受け取る</button> <button type="button" class="btn ghost" id="push-off" hidden>通知を止める</button></p>
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


STATS_SECTION = '<h2 id="stats">利用状況の統計</h2>\n<p>使いやすくするため、件数だけの統計を取ります。送るのは、あらかじめ決めた項目の件数です。「どのページが開かれたか」「選ばれたきせかえ」「ホームに表示する項目の並びと非表示」「予定に入れる・ファイルを作る・共有するボタンが押された回数」「選ばれた好きな分野(あらかじめ決めた一覧にあるものだけ)の回数」「検索で見つかったか(検索した言葉は送りません)」。</p>\n<p>名前・日付・メモ・メールアドレス・検索した言葉・端末を識別する番号は送りません。Cookie は使いません。サーバーに残るのは1日ごとの合計の件数だけで、同じ人かどうかは分かりません。送りすぎを防ぐため、アドレスから作った1日限りの符号を回数の制限にだけ使い、翌日に削除します。</p>\n<p>マイページの「利用状況の統計に協力する」でいつでも止められます。ブラウザの「トラッキングしない」(DNT・Global Privacy Control)がオンのときは、初めから止まっています。</p>'
PUSH_SECTION = '<h2 id="push">通知(任意)</h2>\n<p>マイページの「この端末で通知を受け取る」を押し、ブラウザで許可したときだけ通知を使えます。当サイトのサーバーに保存するのは、ブラウザが作った通知の宛先(購読情報)と、通知する日(日付と、朝か夜か)だけです。予定の名前・時刻・メモ・やることの内容は保存しません。通知文は、お使いの端末で作ります。</p>\n<p>通知は、当サイトが GitHub Actions(GitHub, Inc.)で動かす送信プログラムから、お使いのブラウザのプッシュ配信サービス(Google、Apple、Mozilla など)を通して届きます。「通知を止める」を押すか、ブラウザの設定で通知を止めると、購読情報はサーバーから削除します。配信サービスから「宛先がない」と返されたものも削除します。</p>'
MEMBERS_SECTION = '<h2 id="members">会員登録(任意)</h2>\n<p>会員登録は無料で、パスワードはありません。メールアドレスに送る確認コードでログインします。サーバーに保存するのは、メールアドレス、登録日、プランと無料期間、紹介コード、ログイン中の端末の印(ランダムな値の要約)です。「メールでもお知らせする」をオンにした人に限り、知らせる日(日付と、朝か夜か)と予定の名前(短く)も保存します。オフにすると、その部分はすぐ消します。</p>\n<p>これらは、サーバーの公開されない場所に暗号化して保存します。記録した日・メモ・やることの内容そのものは、会員でも端末の中だけにあります。ペンネームを入れて公開に同意した人は、そのペンネームを協力者のページに載せます。紹介の確認のため、サイトを使った日(直近20日分)を保存します。モニターのアンケートの答えは、サイトの改善のためだけに使い、運営者だけが読みます。確認コードのメールは、ログインのためだけに送ります。広告のメールは、別に同意した人にしか送りません。マイページの「退会する」で、会員の記録はすぐ消えます。</p>'
GOOGLE_SECTION = '<h2 id="google">Google アカウントでの引き継ぎ(任意)</h2>\n<p>マイページの「Google アカウントで同期する」を押したときだけ、Google の画面が開きます。許可するのは、あなたの Google ドライブの中にあるこのサイト専用の非表示フォルダ(アプリデータ)への保存だけです。記録した日・予定に入れた日・好きな分野・設定をそこに保存し、別の端末で読み込めます。当サイトのサーバーには送りません。Google アカウントの氏名やメールアドレスは取得しません。</p>\n<p>やめるときは、<a href="https://myaccount.google.com/permissions" rel="noopener" target="_blank">Google アカウントの権限の管理</a>で「あと何日、もう何日」の権限を削除してください。</p>'


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


AREA_KINDS = {"改定", "終了", "施行", "改正", "締切"}   # the place of these is the area they apply to, not a venue


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
         + (f' data-g="{g}"' if g else "") + (f' data-cat="{esc(e["mid"])}"' if e.get("mid") else "") + (f' data-sub="{esc(e["subject"])}"' if e.get("mid") and e.get("subject") else "") + ">"]
    subject = e.get("subject") or (e.get("category") if not own else None) or e["kind"]
    what = e.get("what") or (e.get("kind") if not own else None)
    place = e.get("place") if e.get("place") is not None else (e.get("region") if not own else None)
    h.append('<div class="c-top">' + (f'<span class="mark m{g}" data-g="{g}" aria-hidden="true"></span>' if g else "")
             + f'<span class="badge">{esc(subject if not own else e["kind"])}</span>' + (f'<span class="what">{esc(what)}</span>' if what and not own else "") + "</div>")
    h.append(f'<p class="c-count"><span class="word">{word}</span><span class="num">{esc(num)}</span><span class="rel">{rel}</span></p><p class="c-sub">{esc(sub)}</p>')
    title = esc(e["title"])
    linked = '<a href="/e/' + e["id"] + '/">' + title + "</a>" if link and not own else title
    h.append(f'<h3 class="c-title">{linked}</h3>')
    pl = f'<span class="pl"><b>{"対象地域" if e.get("kind") in AREA_KINDS else "場所"}</b>{esc(place)}</span>' if place and place != "全国" and not own else ""
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


BUNDLE = ('core', 'ics', 'app', 'tier', 'share', 'card', 'ical', 'plan', 'quick', 'guide', 'push', 'member')   # one script instead of six requests; the sources stay separate files


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
        conf = {"v": self.v_cat, "groups": catalog.GROUPS, "slugs": SLUGS, "regions": PREFECTURES, "css": css_urls,
                "skins": {s["id"]: {"card": s["card"], "name": s["name"], "attrs": s.get("attrs", {}), **({"dark": True} if s.get("dark") else {}), **({"season": s["season"]} if s.get("season") else {})} for s in skins.SKINS}}
        if cfg.get("google_client_id"):
            conf["gclient"] = cfg["google_client_id"]
        if cfg.get("vapid_public"):
            conf["vapid"] = cfg["vapid_public"]
        if isinstance(cfg.get("plans"), dict) and cfg["plans"].get("on"):
            conf["plans"] = {k: cfg["plans"][k] for k in ("on", "plus_open", "free_cards", "shares_per_slot", "extra_max", "free_remind") if k in cfg["plans"]}
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

    def page(self, path: str, title: str, desc: str, body: str, kind: str, *, noindex: bool = False, og: str | None = None) -> str:
        html = layout(self.site, self.cfg, self.preview, path=path, title=title, description=desc, body=body, og_image=og or "/assets/og.png")   # the share picture (make_og.py; a public day has its own: ogimage.py)
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
    body = f"""<section class="intro" id="intro" aria-labelledby="intro-h" hidden>
<h2 id="intro-h">はじめての方へ</h2>
<p class="intro-lead">試験や締切までの日数も、記念日からの日数も、ここで数えられます。</p>
<ol class="intro-steps">
<li><b>さがす</b><span>試験・締切・大会・お祭りなど、公式の日付が見つかります(出典つき)</span></li>
<li><b>記録する</b><span>記念日や予定など、大切な日を1行で記録できます</span></li>
<li><b>知らせる</b><span>あと何日かがひと目で分かります。カレンダーへの追加や通知は、必要なときだけ使えます。</span></li>
</ol>
<p class="intro-note">登録なしで、無料で使えます。</p>
<p class="intro-btns"><button type="button" class="btn" data-intro="start">30秒で使い方を見る</button> <button type="button" class="btn ghost" data-intro="close">すぐ使う</button></p>
<p class="hint">この案内は、画面上の「?」や、ページ下の「使い方」から、いつでも見直せます。</p>
</section>
<section class="hero"><h1>{esc(CATCH)}</h1>
<div class="hero-cta" id="hero-cta" hidden>
<p class="hero-note">登録なしで、無料で使えます。</p>
<p class="hero-btns"><a class="btn" href="/add/">大切な日を記録する</a> <a class="btn ghost" href="/interests/">好きな分野から探す</a></p>
<nav class="chiprow" aria-label="残せる日の例"><a class="chip" href="/add/?kind=anniversary">記念日</a><a class="chip" href="/add/?kind=birthday">誕生日</a><a class="chip" href="/add/?kind=until">楽しみな日・期限</a><a class="chip" href="/add/?kind=memorial">大切な人を思う日</a></nav>
</div></section>
<div id="season" class="season" hidden></div>
<div id="blocks">
<section id="todo" data-block="todo" data-title="今日の予定・やること" hidden>
<div class="head-row"><h2>今日の予定・やること</h2><div class="grow"><a class="btn small ghost" href="/calendar/">カレンダー</a></div></div>
<ul class="plist" id="todo-list"><li class="muted">読み込み中…</li></ul>
</section>
<section id="mine" data-block="mine" data-title="記録した日" hidden>
<div class="head-row"><h2>記録した日</h2><div class="grow"><a class="btn small ghost" href="/my/">マイページ</a></div></div>
<div class="cards" id="mine-grid" data-save-order="1"></div>
</section>
<section id="interests" data-block="interests" data-title="好きな分野の日" hidden>
<div class="head-row"><h2>好きな分野の日</h2><div class="grow"><a class="btn small ghost" href="/interests/">分野を選ぶ</a></div></div>
<p class="hint" id="int-prompt" hidden>将棋、流星群、英検など、好きな分野を選ぶと、その分野の日がここに並びます。<a href="/interests/">選んでみる</a></p>
<div id="int-wrap" hidden><div class="cards" id="int-grid"></div><p class="hint" id="int-miss"></p></div>
</section>
<section id="region" data-block="region" data-title="お住まいの地域の日" hidden>
<div class="head-row"><h2 id="reg-title">お住まいの地域の日</h2><div class="grow"><a class="btn small ghost" href="/interests/#region">地域を選ぶ</a></div></div>
<p class="hint" id="reg-none" hidden>お住まいの都道府県を選ぶと、その地域の日が、ここに並びます。<a href="/interests/#region">選んでみる</a></p>
<div id="reg-wrap" hidden><div class="cards" id="reg-grid"></div><p class="hint" id="reg-more"></p></div>
</section>
<section data-block="search" data-title="さがす">
{search_form()}
</section>
<section data-block="cats" data-title="ジャンル"><nav class="chiprow" aria-label="ジャンルから探す">{chips}</nav></section>
<section data-block="daily" data-title="今日の数字"><div class="daily" id="daily" aria-label="今日の数字"><span>今日の日付と、年末・年度末までの日数。</span></div></section>
<section data-block="soon" data-title="もうすぐの日">
<div class="head-row"><h2>もうすぐの日</h2><div class="grow"><button type="button" class="btn small ghost" id="shuffle">シャッフル</button></div></div>
<div class="cards" id="grid" data-save-order="1">{"".join(card_html(e) for e in first)}</div>
<p class="more-row"><button type="button" class="btn ghost" id="more">もっと見る</button></p>
</section>
<section data-block="usecases" data-title="こんな時に">
<div class="head-row"><h2>こんな時に</h2><div class="grow"><a class="btn small ghost" href="/card/">カードを作って送る</a> <a class="btn small ghost" href="/use/">一覧</a></div></div>
<div class="uc-grid compact">{ucs}</div>
</section>
</div>
<p class="edit-home"><button type="button" class="btn small ghost" id="edit-home" aria-pressed="false">ホームを編集</button> <button type="button" class="btn small ghost" id="reset-home" hidden>元に戻す</button></p>"""
    return c.page("/", f"{NAME}|{CATCH}", "あの日からもう何日、あの日まであと何日。日付を選ぶだけで数えて、カレンダーで見られます。締切・試験・大会・お祭りの確認済みの日付は、ワンタップで予定に入れられます。", body, "home")


def _norm(s: str) -> str:
    """The same folding as the script's norm(): full/half width and case folded, katakana as hiragana, white space collapsed."""
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in s)
    return re.sub(r"\s+", " ", s).strip()


def _hay(e: dict) -> str:
    return _norm(" ".join([e["title"], e.get("subject") or "", e.get("what") or "", e.get("category") or "", e["group"], e.get("place") or e.get("region") or "", e["kind"]] + list(e.get("tags") or [])))


def interest_sections(live: list[dict]) -> list[dict]:
    """[{"name", "items": [{"id", "name", "n"}]}]: the fields a visitor may choose (data/atomou/interests.json), each with the number of upcoming days that belong to it
    (the same word test the home page uses), and a last section for the fields of the catalogue that no name above reaches."""
    data = json.loads((ROOT / "data/atomou/interests.json").read_text(encoding="utf-8"))
    days = [e for e in live if not e["quiet"]]
    hays = [(e, _hay(e)) for e in days]
    out, reached = [], set()
    for s in data["sections"]:
        items = []
        for it in s["items"]:
            w = _norm(it["name"])
            hit = [e for e, h in hays if e["subject"] == it["name"] or w in h]
            reached.update(e["id"] for e in hit)
            items.append({"id": it["id"], "name": it["name"], "n": len(hit)})
        out.append({"name": s["name"], "items": items})
    rest: dict[str, int] = {}
    for e in days:
        if e["id"] not in reached and e.get("subject"):
            rest[e["subject"]] = rest.get(e["subject"], 0) + 1
    if rest:
        out.append({"name": "そのほかの日付のある分野", "items": [{"id": 0, "name": k, "n": v} for k, v in sorted(rest.items(), key=lambda kv: (-kv[1], kv[0]))]})
    return out


def interests_page(c: Ctx, live: list[dict]) -> str:
    """"好きな分野を選ぶ": fields in groups as chips (what is chosen is kept on this device and shown on the home page), a box to add any word, and a share box."""
    secs = []
    for i, s in enumerate(interest_sections(live)):
        chips = ""
        for it in s["items"]:
            soon = " soon" if not it["n"] else ""
            ident = ' data-id="' + str(it["id"]) + '"' if it["id"] else ""
            count = str(it["n"]) if it["n"] else "準備中"
            chips += f'<button type="button" class="chip{soon}" aria-pressed="false" data-int="{esc(it["name"])}"{ident}>{esc(it["name"])}<span class="n">{count}</span></button>'
        secs.append(f'<section data-int-sec="{i + 1}"><h2 class="int-h">{esc(s["name"])}</h2><div class="chiprow">{chips}</div></section>')
    body = f"""{crumbs([("トップ", "/"), ("好きな分野", None)])}
<h1>好きな分野を選ぶ</h1>
<p class="lead muted">選んだ分野の日が、ホームにまとまって並びます。まだ日付のない分野(準備中)も選べます。</p>
<div id="int-chosen"></div>
<div class="field" id="region-pick"><label for="reg-select">お住まいの都道府県</label><select id="reg-select"><option value="">選ばない</option>{"".join(f'<option value="{p}">{p}</option>' for p in PREFECTURES)}</select>
<p class="hint">選ぶと、その地域の日が、ホームの先頭近くに並びます。</p><p class="small muted" id="reg-note" aria-live="polite"></p></div>
<div class="sbox"><form class="searchbox" id="int-form" role="search"><label class="vh" for="int-q">分野を探す・追加する</label>
<input type="text" id="int-q" maxlength="24" autocomplete="off" placeholder="探す・追加する(例: 剣道、釣り、写真)" enterkeyhint="done"><button type="submit" class="sbtn" aria-label="追加">{ICONS['plus']}</button></form></div>
<p class="small muted" id="int-note" aria-live="polite"></p>
<p class="int-go" id="int-go" hidden><a class="btn" href="/">選んだ分野の日を見る</a></p>
{"".join(secs)}
<noscript><p class="notice">分野を選ぶには JavaScript が必要です。<a href="/search/">さがす</a>からも探せます。</p></noscript>"""
    return c.page("/interests/", f"好きな分野を選ぶ | {NAME}", "将棋・流星群・英検・剣道・手芸など、好きな分野を選ぶと、その分野の日付がホームに並びます。", body, "interests", noindex=True)


def card_page(c: Ctx) -> str:
    """/card/: make a card (a day with a name, a note and things to do before it) and send it as a link or a picture; open a card somebody sent.  All of it is in the part of the address after the "#"."""
    body = f"""{crumbs([("トップ", "/"), ("カードを作って送る", None)])}
<h1>カードを作って送る</h1>
<div id="card-box"><noscript><p class="notice">カードを作るには JavaScript が必要です。</p></noscript></div>"""
    return c.page("/card/", f"カードを作って送る | {NAME}", "日付・ひとこと・やることを入れたカードを、リンクや画像で送れます。受け取った人は、1タップで自分の予定帳に入れられます。", body, "card", noindex=True)


def search_page(c: Ctx) -> str:
    chips = '<button type="button" class="chip" data-g-chip="" aria-pressed="true">すべて</button>' + "".join(
        f'<button type="button" class="chip" data-g-chip="{SLUGS[i]}" aria-pressed="false">{esc(g)}</button>' for i, g in enumerate(catalog.GROUPS))
    body = f"""{crumbs([("トップ", "/"), ("さがす", None)])}
<h1>日付をさがす</h1>
<p class="lead muted">言葉を入力するか、ジャンルを選んでください。</p>
{search_form()}
<div class="chips" role="group" aria-label="ジャンル">{chips}<button type="button" class="chip" id="f-son" aria-pressed="false">お金や手続きの日だけ</button></div>
<div class="chips" id="mid-chips" role="group" aria-label="中分類" hidden></div>
<div class="chips" id="sub-chips" role="group" aria-label="小分類" hidden></div>
<p class="small muted" id="found" aria-live="polite">&nbsp;</p>
<div class="cards" id="results"></div>
<div class="panel" id="none" hidden><p>該当する日付が見つかりませんでした。</p><p>言葉を短くするか、ジャンルを「すべて」にしてみてください。この言葉のまま<a id="none-add" href="/add/">日付として記録する</a>こともできます。</p><p class="muted">探している日がなければ、<a id="none-ask" href="/contact/?kind=request">お問い合わせ</a>から、載せてほしい日を送ってください。</p></div>
<noscript><p class="notice">検索には JavaScript が必要です。<a href="/c/deadline/">ジャンルのページ</a>からも探せます。</p></noscript>"""
    return c.page("/search/", f"日付をさがす | {NAME}", "言葉やジャンルから、締切・試験・大会・お祭りの日付を探せます。見つけた日は、ワンタップで予定に。", body, "search")


def my_page(c: Ctx) -> str:
    sync_html = ""
    push_html = PUSH_BOX if c.cfg.get("vapid_public") else ""
    member_html = MEMBER_BOX if members_on(c.cfg) else ""
    if c.cfg.get("google_client_id"):
        sync_html = ('<h2 id="sync">別の端末に引き継ぐ</h2>\n<div class="panel" id="sync-box" hidden>'
                     '<p>Google アカウントでつなぐと、記録した日を自分の Google ドライブに保存して、別の端末に引き継げます。'
                     '<a href="/privacy/#google">詳しく</a></p><p><button type="button" class="btn" id="sync-now">Google アカウントで同期する</button></p></div>\n')
    body = f"""{crumbs([("トップ", "/"), ("マイページ", None)])}
<h1>マイページ</h1>
<p class="lead muted">記録した日と、予定に入れた日がここに並びます。</p>
<div class="panel" id="my-empty" hidden><p>まだ記録がありません。忘れたくない日を記録すると、ここに表示されます。</p><p><a class="btn" href="/add/">日を記録する</a> <a class="btn ghost" href="/search/">公式の日付をさがす</a></p></div>
<div class="head-row" id="my-tools" hidden><div class="grow" style="margin-left:0"><button type="button" class="btn small ghost" id="reorder" aria-pressed="false">並べ替え</button></div></div>
<div class="cards" id="my-grid" data-save-order="1"></div>
<h2>設定</h2>
<div class="panel">
<div class="field"><label class="lab" for="p-big"><input type="checkbox" id="p-big"> 文字を大きくする</label></div>
<div class="field"><label for="p-alarm">通知の時間(通知・カレンダーに入れるとき)</label>
<select id="p-alarm"><option value="morning">当日の朝</option><option value="eve">前日の夜</option><option value="week">1週間前の朝</option><option value="none">なし</option></select></div>
<div class="field"><label class="lab" for="p-stats"><input type="checkbox" id="p-stats"> 利用状況の統計に協力する(個人は特定されません。<a href="/privacy/#stats">詳しい説明</a>)</label></div>
<p><a href="/skins/">きせかえ</a></p>
<p><a href="/?edit=1">ホームを編集</a></p>
<p><a href="/?intro=1">はじめての方へ(このサイトの説明)を見る</a></p>
<p><button type="button" class="btn small ghost" data-guide="start">使い方を見る</button></p>
</div>
{member_html}<div id="tier-box"></div>{push_html}{sync_html}<h2>他のカレンダーアプリに入れる</h2>
<div class="panel"><p>iPhone の「カレンダー」や Google カレンダーに取り込めるファイルを作れます。1件ずつ作るときは、予定の詳細から。</p>
<p><button type="button" class="btn small ghost" id="ics-all">すべての予定をファイルにする</button></p></div>
<h2 id="ical-h">ほかのカレンダーから取り込む</h2>
<div class="panel"><p>Google カレンダーなどから書き出した .ics のファイルを、この予定帳に入れられます。</p>
<details class="more"><summary>Google カレンダーからの書き出し方</summary><ol><li>パソコンで Google カレンダーを開きます。</li><li>右上の歯車から「設定」を開きます。</li><li>「インポート/エクスポート」の「エクスポート」を押します。</li><li>ダウンロードした ZIP を開き、中の .ics のファイルを、下から選びます。</li></ol></details>
<p><label class="btn small ghost" for="ical-file">.ics のファイルを選ぶ</label><input class="vh" type="file" id="ical-file" accept=".ics,text/calendar"></p><div id="ical-out" aria-live="polite"></div></div>
<h2 id="backup-h">バックアップ</h2>
<div class="panel">
<p>記録はこの端末に保存されています。機種変更の前に書き出し、新しい端末で読み込んでください。</p>
<p><button type="button" class="btn small" id="backup">書き出す</button>
<label class="btn small ghost" for="restore">読み込む</label><input class="vh" type="file" id="restore" accept="application/json,.json">
<button type="button" class="btn small ghost" id="wipe">すべて消す</button></p>
</div>
<noscript><p class="notice">マイページには JavaScript が必要です。</p></noscript>"""
    return c.page("/my/", f"マイページ | {NAME}", "記録した日と、予定に入れた日の一覧です。", body, "my", noindex=True)


def add_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("記録する", None)])}
<h1>日付を記録する</h1>
<p class="lead muted">日付を選ぶだけで数えます。年だけでも記録できます。</p>
<div id="wizard" class="wizard"><noscript><p class="notice">日付の記録には JavaScript が必要です。</p></noscript></div>"""
    return c.page("/add/", f"日付を記録する | {NAME}", "記念日・誕生日・はじめた日・命日を、選ぶだけで記録できます。あと何日、もう何日かをその場で数えます。", body, "add")


def calendar_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", None)])}
<h1>カレンダー</h1>
<p class="lead muted">記録した日と予定に入れた日が並びます。日付を選ぶと、その日の予定とやることが表示されます。</p>
<div id="cal"></div>
<noscript><p class="notice">カレンダーには JavaScript が必要です。</p></noscript>"""
    return c.page("/calendar/", f"カレンダー | {NAME}", "記録した日と公式の日付を、月のカレンダーと一覧で確認できます。予定ごとにメモと「何日前までにやること」を書けます。", body, "calendar")


def plan_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("カレンダー", "/calendar/"), ("予定の詳細", None)])}
<h1>予定の詳細</h1>
<div id="plan"><p class="muted">読み込み中…</p></div>
<noscript><p class="notice">予定の詳細には JavaScript が必要です。</p></noscript>"""
    return c.page("/plan/", f"予定の詳細 | {NAME}", "予定のメモと、何日前までにやることを保存できます。", body, "plan", noindex=True)


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
<p class="hint">左から、これから来る日、過ぎた日、大切な人を思う日(静かな表示)です。</p>
<div class="cards">{"".join(card_html(s, own=True, actions=False, link=False) for s in samples)}</div>
<h2>選ぶ</h2>
<p><label class="chip" for="skin-auto"><input type="checkbox" id="skin-auto"> 端末が暗い設定のときは、暗い配色にする</label></p>
<div class="skins" id="skin-list">{"".join(tile(s) for s in skins.SKINS)}</div>
<noscript><p class="notice">きせかえには JavaScript が必要です。</p></noscript>"""
    return c.page("/skins/", f"きせかえ | {NAME}", "きせかえは20種類以上あります。大きな文字、やさしい色、にぎやかな色も選べます。", body, "skins")


def use_index(c: Ctx) -> str:
    secs = []
    for name, items in usecases.grouped():
        secs.append(f"<h2>{esc(name)}</h2><div class=\"uc-grid\">" + "".join(
            f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>' for u in items) + "</div>")
    popular = "".join(f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>'
                      for u in [usecases.by_slug(s) for s in ("couple-anniversary", "furusato-nozei", "exam-university", "oshi-live", "quit-smoking", "baby-100days")] if u)
    body = f"""{crumbs([("トップ", "/"), ("こんな時に", None)])}
<h1>こんなときに使えます</h1>
<p class="lead muted">場面ごとの使い方をまとめました。まずは、よく使われる6つをご覧ください。</p>
<h2>よく使われる</h2><div class="uc-grid">{popular}</div>
{"".join(secs)}"""
    return c.page("/use/", f"こんなときに使えます | {NAME}", "付き合った記念日、大切な人を思う日、確定申告、受験、推し活。使い方を場面ごとに。", body, "use")


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
    body = crumbs([("トップ", "/"), ("こんな時に", "/use/"), (u["title"], None)]) + f'<h1>{esc(u["title"])}</h1>\n' + "\n".join(parts)
    return c.page(f"/use/{u['slug']}/", f"{u['title']} | {NAME}", u["situation"], body, "use")


def og_path(e: dict) -> str | None:
    """The address of the day's own share picture (None when pictures cannot be drawn here, or the day is a quiet one)."""
    return f"/og/{e['id']}.png" if ogimage.available() and not e["quiet"] else None


def og_pages(live: list[dict]) -> dict[str, bytes]:
    if not ogimage.available():
        return {}
    base = skins.SKINS[0]["vars"]
    out = {}
    for e in live:
        if e["quiet"]:
            continue
        i = catalog.GROUPS.index(e["group"]) + 1 if e["group"] in catalog.GROUPS else 1
        h = str(base.get(f"g{i}", "#1D4ED8")).lstrip("#")
        end = f"〜{fmt_date(e['date_end'])}" if e.get("date_end") else ""
        out[f"og/{e['id']}.png"] = ogimage.card(title=e["title"], date_text=fmt_date(e["date"], e["precision"]) + end,
                                                field=f"{e['group']} / {e['subject']}" if e.get("subject") else e["group"], colour=tuple(int(h[k:k + 2], 16) for k in (0, 2, 4)))
    return out


def google_calendar_url(e: dict, page_url: str) -> str:
    """The address that opens Google Calendar's own form with the day filled in (a whole day: the end date is the day after).  The page address goes into the details, so the day leads back here."""
    d = date.fromisoformat(e["date"])
    last = date.fromisoformat(e.get("date_end") or e["date"]) + timedelta(days=1)
    detail = f"詳しい日付と出典: {page_url}"
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + quote(e["title"]) + "&dates=" + d.strftime("%Y%m%d") + "/" + last.strftime("%Y%m%d")
            + "&details=" + quote(detail) + "&ctz=Asia%2FTokyo")


def outlook_calendar_url(e: dict, page_url: str) -> str:
    """Outlook.com / Microsoft 365 on the web: the same day as a whole-day event in its own form."""
    d = date.fromisoformat(e["date"])
    last = date.fromisoformat(e.get("date_end") or e["date"]) + timedelta(days=1)
    return ("https://outlook.live.com/calendar/0/deeplink/compose?path=%2Fcalendar%2Faction%2Fcompose&rru=addevent&subject=" + quote(e["title"]) + "&startdt=" + d.isoformat()
            + "&enddt=" + last.isoformat() + "&allday=true&body=" + quote(f"詳しい日付と出典: {page_url}"))


SHARE_ICONS = {
    "line": '<path d="M4 5h16v11h-8.5L7 20v-4H4z"/>',
    "x": '<path d="M5 5l14 14M19 5L5 19"/>',
    "copy": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "image": '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
    "native": '<circle cx="6" cy="12" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="17" cy="18" r="2"/><path d="M8 11l7-4M8 13l7 4"/>',
}


def share_icon(kind: str, label: str, *, href: str = "", hidden: bool = False) -> str:
    """One small round icon button of the share row (the words are for screen readers and the tooltip)."""
    svg = f'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{SHARE_ICONS[kind]}</svg><span class="vh">{label}</span>'
    if kind in ("line", "x"):
        return f'<a class="sbt" data-share-to="{kind}" href="{esc(href)}" target="_blank" rel="noopener" title="{label}">{svg}</a>'
    return f'<button type="button" class="sbt" data-share="{kind}" title="{label}"{" hidden" if hidden else ""}>{svg}</button>'


def share_block(c: Ctx, e: dict) -> str:
    """Icons to send a public day to somebody (LINE, X, the link, a picture, the phone's share sheet) in one thin row.  share.js fills in today's count; the links work without it."""
    page_url = f"{str(c.cfg['site_url']).rstrip('/')}/e/{e['id']}/"
    fmt = fmt_date(e["date"], e["precision"])
    text = f"「{e['title']}」({fmt})。出典つきの公式の日付です。"
    line = "https://line.me/R/msg/text/?" + quote(text + chr(10) + page_url)
    x = "https://twitter.com/intent/tweet?text=" + quote(text) + "&url=" + quote(page_url, safe="")
    return (f'<div class="share share-row" aria-label="人に送る" data-title="{esc(e["title"])}" data-date="{e["date"]}" data-p="{e["precision"]}" data-url="{esc(page_url)}">'
            '<span class="share-lead">送る</span>'
            + share_icon("line", "LINEで送る", href=line) + share_icon("x", "Xで投稿", href=x) + share_icon("copy", "リンクをコピー") + share_icon("image", "画像で保存") + share_icon("native", "ほかのアプリで送る", hidden=True)
            + f'<a class="share-more" href="/card/#from=c:{e["id"]}" title="ひとこと・やることを足したカードにして送ります">カードにして送る</a></div>')


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
    body = crumbs([("トップ", "/"), (e["group"], f"/c/{GROUP_SLUG[e['group']]}/")] + ([(e["mid"], f"/c/{GROUP_SLUG[e['group']]}/#m={quote(e['mid'])}")] if e.get("mid") and e["mid"] != catalog.MID_OTHER else []) + [(e["title"], None)]) + f"""
<h1>{esc(e['title'])}</h1>
{card_html(e, big=True, link=False)}
{'<p class="small muted">上のカードの日数は、今日の日付をもとに数えています。</p>' if art else f'<p>{esc(sentence)}<span class="small muted">上のカードの日数は、今日の日付をもとに数えています。</span></p>'}
<p class="small muted src-line">出典: <a href="#src">{esc(host(e['source_url']))}</a>(確認日 {esc(e['checked_on'])})</p>
{art}
{'<p class="notice quiet">この日は、静かにお知らせします。</p>' if quiet else ""}
<h2 id="src">出典と確認日</h2>
<dl class="info"><dt>出典</dt><dd><a href="{esc(e['source_url'])}" rel="noopener nofollow" target="_blank">{esc(host(e['source_url']))}</a></dd>
<dt>確認日</dt><dd>{esc(e['checked_on'])}</dd>{f"<dt>出典の文</dt><dd>{esc(e['source_quote'])}</dd>" if e.get('source_quote') else ""}</dl>
<p class="small muted">日付や時刻は変わることがあります。出典の公式ページで、最新の情報をご確認ください。</p>
<p><a class="btn small" href="/plan/?key=c:{e['id']}">メモ・やることを追加</a> <a class="btn small ghost" href="/add/?title={quote(e['title'])}&amp;date={e['date']}">自分の予定として記録する</a>{(' <a class="btn small ghost" href="' + esc(google_calendar_url(e, str(c.cfg['site_url']).rstrip('/') + '/e/' + e['id'] + '/')) + '" target="_blank" rel="noopener">Googleカレンダーに追加</a>') if e["precision"] == "day" else ""}</p>
{"" if quiet else share_block(c, e)}
{"" if quiet else '<p class="int-line"><button type="button" class="btn small ghost" data-int-toggle="' + esc(e["subject"]) + '">「' + esc(e["subject"]) + '」を好きな分野に入れる</button> <a class="small" href="/interests/">好きな分野を選ぶ</a></p>'}
{f'<details class="more"><summary>ほかのカレンダーアプリに入れる</summary><p class="hint">Outlook は下のボタンから入れられます。iPhone の「カレンダー」、Yahoo!カレンダー、TimeTree などには、ファイルを作って取り込みます。</p><p><a class="btn small ghost" href="{esc(outlook_calendar_url(e, str(c.cfg["site_url"]).rstrip("/") + "/e/" + e["id"] + "/"))}" target="_blank" rel="noopener">Outlookに追加</a> <button type="button" class="btn small ghost" data-ics-for="c:{e["id"]}">ファイルを作る</button></p></details>' if e["precision"] == "day" else ""}
{(f'<h2>同じ「{esc(e["subject"])}」の日</h2><p class="saveall"><button type="button" class="btn small" data-saveall="{",".join([e["id"]] + [r["id"] for r in same])}">この日を含む{len(same) + 1}件をまとめて予定に入れる</button></p><div class="cards">' + "".join(card_html(r) for r in same) + "</div>") if same else ""}
{('<h2>同じジャンルの日</h2><div class="cards">' + "".join(card_html(r) for r in rel) + "</div>") if rel else ""}
{('<h2>同じ頃の日</h2><p class="hint">この日の前後10日にある日です。</p><div class="cards">' + "".join(card_html(r) for r in near) + "</div>") if near else ""}"""
    suffix = "からもう何日？" if e["status"] == "ended" else "はいつ？あと何日？"
    title = f"{e['title']}{suffix} {fmt} | {NAME}"
    place = (e.get("place") or "").strip()
    desc = f"{e['title']}は{fmt}{end}" + (f"、{place}" if place and place not in ("全国", "地域") else "") + "。" + (f"{guide['about'].split('。')[0]}。" if guide else "") + "出典と確認日つき。あと何日かを数えて、予定に入れられます。"
    html = c.page(f"/e/{e['id']}/", title, desc, body, "event", noindex=not indexable, og=og_path(e))
    return strip_ads(html) if quiet or not e.get("ad_ok", True) else html


def category_page(c: Ctx, group: str, live: list[dict]) -> str:
    rows = [e for e in live if e["group"] == group][:200]
    mids = [m["name"] for m in catalog.TAXONOMY.get(group, []) if any(e.get("mid") == m["name"] for e in rows)]
    chips = ""
    if len(mids) > 1:
        chips = ('<div class="chips" role="group" aria-label="中分類で絞り込む"><button type="button" class="chip" data-cat-chip="" aria-pressed="true">すべて</button>'
                 + "".join(f'<button type="button" class="chip" data-cat-chip="{esc(x)}" aria-pressed="false">{esc(x)}<small> {sum(1 for e in rows if e.get("mid") == x)}</small></button>' for x in mids)
                 + '</div><div class="chips" id="subchips" role="group" aria-label="小分類で絞り込む" hidden></div>')
    body = f"""{crumbs([("トップ", "/"), (group, None)])}
<h1>{esc(group)}の日付</h1>
<p class="lead muted">{esc(GROUP_LEAD[group])}</p>
{search_form()}
{chips}
<div class="cards" id="grid">{"".join(card_html(e) for e in rows)}</div>
{feeds.subscribe_html(GROUP_SLUG[group] + ".ics", str(c.cfg["site_url"]).rstrip("/"), urlparse(str(c.cfg["site_url"])).netloc) if any(feeds.feedable(e) for e in rows) else ""}"""
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
        ("料金はかかりますか？", "無料です。会員登録なしで使えます。会員(無料)になると、メール通知と先着の特典を使えます。"),
        ("入力した内容は、ほかの人に見えますか？", "見えません。予定・メモ・やることは、お使いの端末の中だけにあり、当サイトのサーバーには送りません。"),
        ("予定の前に、お知らせは来ますか？", "マイページの「この端末で受け取る通知」をオンにすると、予定の当日の朝か前日の夜に、この端末へ通知が届きます(iPhone はホーム画面に追加してから)。会員はメールでも受け取れます。他のカレンダーアプリの通知を使うときは、予定の詳細の「他のカレンダーアプリに入れる」でファイルを作って取り込みます。"),
        ("「やること」とは何ですか？", "予定の何日前までに何をするかを書く欄です。たとえば「試験の1週間前: 願書を出す」。期限の日がカレンダーとホームに表示され、チェックすると完了になります。"),
        ("機種変更をしたら、記録はどうなりますか？", "自動では引き継がれません。機種変更の前にマイページの「書き出す」でファイルを作り、新しい端末で「読み込む」を押します。マイページに Google アカウントでの引き継ぎが出ていれば、それも使えます。"),
        ("「あと」と「もう」の違いは？", "「あと」はこれから来る日まで、「もう」は過ぎた日からの日数です。"),
        ("日数はどう数えますか？", "今日を0日とします。明日は「あと1日」、昨日は「もう1日」、当日は「今日」です。"),
        ("2月29日はどう数えますか？", "うるう年でない年は、2月28日として数えます。"),
        ("文字が小さくて読みにくい。", "マイページの「設定」で「文字を大きくする」にチェックを入れます。「きせかえ」の「大きな文字」「ハイコントラスト」も読みやすい設定です。"),
        ("日付が間違っているようです。", "公式の日付は変わることがあります。カードの「詳細」に出典と確認日があります。誤りは<a href=\"/contact/\">お問い合わせ</a>からお知らせください。"),
        ("大切な人を思う日も入れられますか？", "入れられます。「大切な人を思う日」を選ぶと、静かな表示で記録されます。広告は表示しません。"),
        ("入れた日を消すには？", "マイページかカレンダーからその予定を開き、「消す」を押します。すべて消すときは、マイページの「すべて消す」。"),
    ]
    qa_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in qa)
    body = f"""{crumbs([("トップ", "/"), ("使い方", None)])}
<div class="manual">
<h1>使い方</h1>
<p class="lead">「あと何日、もう何日」の使い方です。画面のガイドは、実際のボタンを指しながら案内します。</p>
<p id="guide"><button type="button" class="btn" data-guide="start">ガイドを見る</button> <span class="hint">各ページ右下の「ガイド」からも見られます。</span></p>

<h2>できること</h2>
<ul class="big-list">
<li><b>日付を数える。</b>過ぎた日からの日数も、これから来る日までの日数も、すぐに分かります。</li>
<li><b>カレンダーとして使える。</b>デート・会議・記念日を入れて、月の表示と一覧で確認できます。予定ごとに、メモと「何日前までにやること」を書けます。</li>
<li><b>通知を受け取れる。</b>予定の当日の朝か前日の夜に、この端末へ通知が届きます。</li>
<li><b>公式の日付を使える。</b>締切・試験・大会・お祭りの日付を、公式の発表で確認して載せています。「予定に入れる」を押すと、自分のカレンダーに追加されます。</li>
</ul>

<h2>はじめて使うとき</h2>
{step(1, "「記録する」を押す", "画面の上の「記録する」(下のメニューでは「記録」)を押します。")}
{step(2, "どんな日かを選ぶ", "「予定」「記念日」「誕生日」から近いものを選びます。デートや会議は「予定」。文字の入力は要りません。")}
{step(3, "日付を選ぶ", "日付の欄を押すとカレンダーが開きます。「予定」は時刻も入れられます。")}
{step(4, "「この日を記録する」を押す", "記録すると、予定の詳細が開きます。続けて、メモと「やること」を書けます。")}
<p class="hint">年や月までしか分からない日は、「年と月だけ」「年だけ」で記録できます。</p>

<h2>カレンダー</h2>
<ul class="big-list">
<li>「カレンダー」を押すと、月の表が出ます。「一覧」にすると、今日から60日の予定とやることが日ごとに並びます。</li>
<li>日付を選ぶと、その日の予定とやることが下に表示されます。「この日に予定を追加」で、その日の予定を記録できます。</li>
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
<li><b>大きな数字</b> … 日数です。100日を超えると「2年3か月12日」の形になり、下に合計の日数が出ます。</li>
<li><b>日付</b> … その日の年月日と曜日。</li>
</ul>
<p>過ぎた日はこの形です。「<b>もう</b>」は、その日から今日までの日数。</p>
<div class="cards" style="max-width:360px;grid-template-columns:1fr">{card_html(past, own=True, actions=False, link=False)}</div>

<h2>ボタン</h2>
<dl class="info big-dl">
<dt>{btn("☆ 予定に入れる")}</dt><dd>公式の日付を自分のカレンダーに入れます。入ると「★ 予定に入っています」に変わり、もう一度押すと外れます。</dd>
<dt>{btn("詳細", True)}</dt><dd>出典(元のページ)と確認日を開きます。</dd>
<dt>{btn("開く")}</dt><dd>自分の予定の詳細を開きます。名前や日付の修正、メモと「やること」の記入もここから。</dd>
<dt>{btn("消す", True)}</dt><dd>自分の予定を消します。</dd>
<dt>{btn("シャッフル")}</dt><dd>ホームのカードを、別の日に入れ替えます。</dd>
<dt>{btn("並べ替え", True)}</dt><dd>カードの順をボタンで変えます。ドラッグ(スマホは長押し)でも動かせます。</dd>
<dt>{btn("さがす")}</dt><dd>言葉で日付を探します。「年賀状」「流星群」のように入れます。</dd>
<dt>{btn("きせかえ", True)}</dt><dd>色や形、文字の大きさを変えます。季節のきせかえもあります。</dd>
<dt>{btn("ホームを編集", True)}</dt><dd>ホームに表示する項目の順を変え、非表示にできます。ホームのいちばん下にあります。</dd>
</dl>

<h2>よくある質問</h2>
<div class="qa">{qa_html}</div>
<p>解決しないときは、<a href="/contact/">お問い合わせ</a>から送ってください。</p>
<p><a class="btn" href="/add/">記録する</a> <a class="btn ghost" href="/use/">こんな時に</a></p>
</div>"""
    return c.page("/manual/", f"使い方 | {NAME}", "「あと何日、もう何日」の使い方。記録のしかた、カレンダーとやること、カードの見方、ボタン、よくある質問。", body, "manual")


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
<p class="lead muted">年末や年度末までの日数と、その準備の目安です。選ぶと、その日までの日数を記録できます。</p>
<section id="today"><h2>今日は {n("today")}</h2>
<p>数字は、お使いの端末の日付で数えています。</p></section>

<section id="year">
<h2>{n("y")}年は、今日で{n("year")}日目</h2>
<p>年末まで、あと{n("year-left")}日です。</p>
{purposes([("年賀状の準備", "年末までの予定に", "until", "year-end"), ("ふるさと納税の期限", "その年の分は12月31日が目安", "until", "year-end"),
           ("年末の大掃除・買い出し", "年内の予定に", "until", "year-end"), ("年内に済ませたい手続き", "名前は自由に", "until", "year-end")])}
{more([("年賀状", "/use/nengajo/"), ("ふるさと納税", "/use/furusato-nozei/"), ("年末までの日数", "/use/year-end-count/")])}
</section>

<section id="newyear">
<h2>{n("newyear-y")}年まで、あと{n("newyear")}日</h2>
<p>新年の準備を始める目安です。</p>
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
<p>当てはまらないときは、<a href="/add/">自分で日付を記録</a>できます。</p>"""
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
            "  if (r.method === 'POST' && u.origin === location.origin && u.pathname === '/card/') { e.respondWith((async () => { const f = await r.formData(); const t = JSON.stringify({ title: String(f.get('title') || '').slice(0, 200), text: String(f.get('text') || '').slice(0, 3000), url: String(f.get('url') || '').slice(0, 300) }); return Response.redirect('/card/#share=' + btoa(unescape(encodeURIComponent(t))).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, ''), 303); })()); return; }\n"
            "  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;\n"
            "  if (u.pathname.startsWith('/assets/')) { e.respondWith(caches.match(r).then((m) => m || fetch(r).then((x) => { if (x.ok) { const y = x.clone(); caches.open(CACHE).then((c) => c.put(r, y)); } return x; }))); return; }\n"
            "  if (r.mode === 'navigate') { e.respondWith(fetch(r).then((x) => { if (x.ok) { const y = x.clone(); caches.open(CACHE).then((c) => c.put(r, y)); } return x; }).catch(() => caches.match(r).then((m) => m || caches.match('/')))); }\n"
            "});\n" + SW_PUSH)


html_escape = esc


def thanks_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("協力者のページ", None)])}
<h1>協力者のページ</h1>
<p class="lead muted">紹介してくださった方と、サイト改善につながるご意見をくださったモニターの方を、毎月ご紹介します。</p>
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
<p class="lead muted">「{NAME}」(以下「当サイト」)の会員機能の利用規約です。会員にならなくても、当サイトは使えます。</p>
<h2>1. 会員登録</h2>
<p>会員登録は無料です。メールアドレスだけで登録でき、パスワードはありません。1人1つのメールアドレスで登録してください。13歳未満の方は、保護者の同意を得てください。</p>
<h2>2. 無料期間と先着の特典</h2>
<p>先着の枠は 2 種類あり、同時に募集します。「先着モニター」と「先着」のどちらかを選んで登録します。どちらも、登録日から決められた期間、すべての機能を無料で使えます。先着モニターは、登録の1週間後と1か月後に、マイページに出る短いアンケート(1分ほど)に、それぞれ7日以内に答えることが条件です。期限を過ぎると、回答するまで、画面の上部に案内を表示します。回答しなかったときも、無料期間は取り消しません。先着モニターの枠が埋まっているときは、先着の枠で登録します。期間はマイページに表示します。人数と期間は当サイトが定め、途中で変えません。期間が終わっても、自動で料金がかかることはありません。</p>
<h2>3. 紹介</h2>
<p>紹介リンクから登録した人には、無料期間が付きます。紹介した人の無料期間は、紹介で登録した人が1週間以上あけて2回使ったときに延びます(人数に上限があります)。特典は期間の延長だけで、お金や商品はありません。自分で自分を紹介すること、同じ人が複数のアドレスで登録することは、特典の対象外です。</p>
<h2>3-2. 協力者のページ</h2>
<p>紹介の人数と、採用されたご意見をもとに、毎月<a href="/thanks/">協力者のページ</a>で紹介します。無料期間の延長や称号を贈ります。載せる名前は、ご本人が公開に同意したペンネームだけです。順位や採用は当サイトが決め、その理由はお答えしないことがあります。</p>
<h2>4. お知らせのメール</h2>
<p>「メールでもお知らせする」をオンにした人にだけ、通知する日の朝か前日の夜にメールを送ります。届かないことや遅れることがあります。大切な手続きは、公式のページでも確かめてください。</p>
<h2>5. してはいけないこと</h2>
<p>他人のメールアドレスでの登録、当サイトの仕組みに負担をかける行為、法令や公序良俗に反する使い方はしないでください。これらがあったときは、会員の登録を止めることがあります。</p>
<h2>6. 退会と記録の削除</h2>
<p>マイページの「退会する」で、いつでも退会できます。会員の記録はすぐに消えます。端末の中の記録は残ります。</p>
<h2>7. 免責</h2>
<p>表示する日付や計算が正しいよう努めますが、誤り・変更・中止があることがあります。当サイトの利用によって生じた損害について、当サイトは責任を負いません。ただし、当サイトに故意または重大な過失があるときは、この限りではありません。</p>
<h2>8. 変更</h2>
<p>この規約は変更することがあります。変更したときは、このページでお知らせします。</p>
<p class="muted">運営: {op}。制定: 2026年10月。</p>"""
    return c.page("/terms/", f"利用規約 | {NAME}", "会員機能の利用規約です。無料の会員登録、先着の特典、紹介、お知らせのメール、退会について。", body, "legal")


# The shared legal pages (sokuhou/sitekit.py, also used by the other sites) are worded for all of them; this site's owner approved a plainer wording on 2026-10-10.
# Each pair is (the shared sentence, this site's sentence); a test checks that none of the shared sentences is left on the three pages.
LEGAL_WORDING = [
    ("お問い合わせの際にいただいたお名前・メールアドレスなどは、返信のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。", "お問い合わせでいただいた内容は、返信のためだけに使います。法令にもとづく場合を除いて、第三者には提供しません。"),
    ("お問い合わせフォームでは、ご用件の内容と、(任意で)該当ページのアドレス、メールアドレスをお預かりします。あわせて、迷惑メッセージを防ぐため、送信元のIPアドレスを、毎日変わる値で変換した記号(元のIPアドレスには戻せません)と、ブラウザの種類を記録します。これらは、サイトの改善と、お返事のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。メールアドレスをいただいても、お返事できないことがあります。",
     "お問い合わせフォームでは、ご用件の内容と、入力された場合のページのアドレスとメールアドレスをお預かりします。迷惑メッセージを防ぐため、送信元のIPアドレスを毎日変わる値に変換した記号(元のIPアドレスには戻せません)と、ブラウザの種類も記録します。いただいた情報は、サイトの改善と返信のためだけに使います。法令にもとづく場合を除いて、第三者には提供しません。メールアドレスをいただいても、返信できないことがあります。"),
    ("当サイトは、第三者配信の広告サービス「Google AdSense」を利用する場合があります。広告配信事業者は、利用者の興味に応じた広告を表示するために、Cookie(クッキー)を使用することがあります。", "当サイトでは、第三者配信の広告サービス「Google AdSense」を利用することがあります。広告配信事業者は、利用者の興味に合わせた広告を表示するために、Cookie を使うことがあります。"),
    ("Cookie を無効にする、または、パーソナライズ広告を無効にするには、", "Cookie やパーソナライズ広告を無効にするには、"),
    ("第三者配信事業者による Cookie の使用を無効にするには、", "第三者配信事業者による Cookie の使用は、"),
    ('aboutads.info</a> もご利用いただけます。', 'aboutads.info</a> からも無効にできます。'),
    ("広告の配信にあたり、お使いのブラウザから広告配信事業者へ、閲覧に関する情報が送信されることがあります。", "広告を配信するため、お使いのブラウザから広告配信事業者へ、閲覧に関する情報が送られることがあります。"),
    ("当サイトには、商品やサービスの紹介リンク(アフィリエイトリンク)が含まれる場合があります。該当するページには、広告であることを明示します。リンク先で商品が購入されると、当サイトの運営者に報酬が支払われることがあります。", "当サイトには、商品やサービスを紹介するリンク(アフィリエイトリンク)が含まれることがあります。該当するページには、広告であることを書いています。リンク先で商品が購入されると、運営者に報酬が支払われることがあります。"),
    ("</a>に記載しています。</p>", "</a>に載せています。</p>"),
    ("このポリシーは、必要に応じて見直し、変更する場合があります。変更後の内容は、このページに掲載した時点から効力を持ちます。", "このポリシーは、必要に応じて見直し、変更することがあります。変更後の内容は、このページに載せた時点から有効です。"),
    ("データの誤りのご指摘、ご意見・ご要望は、次からお送りください。内容によっては、お返事に日数がかかることや、お返事できないことがあります。", "データの誤りのご指摘、ご意見・ご要望は、次のフォームからお送りください。内容によっては、返信に日数がかかることや、返信できないことがあります。"),
    ("の内容に同意したものとみなします。いただいた内容は、サイトの改善と、お返事のためだけに使います。", "に同意したものとして扱います。いただいた内容は、サイトの改善と返信のためだけに使います。"),
]


def legal_wording(html: str) -> str:
    for old, new in LEGAL_WORDING:
        html = html.replace(old, new)
    return re.sub(r"このポリシーに関するお問い合わせは、(.*?)からお願いします。", r"このポリシーについてのお問い合わせは、\1からお送りください。", html)


def privacy_fix(c: Ctx, html: str) -> str:
    """The shared privacy page says that no analytics is used; this site counts fixed items (and may offer a Google Drive hand-over), so that part is replaced."""
    if "<title>プライバシーポリシー" not in html:
        return html
    old = "<h2>アクセス解析</h2>\n<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>"
    if old not in html:
        raise BuildError("sitekit's privacy text changed: update privacy_fix in sites/atomou/build.py")
    if members_on(c.cfg):
        html = html.replace("当サイトは、会員登録などの機能を持ちません。", "会員登録は任意です(下の「会員登録(任意)」を参照)。", 1)
    return html.replace(old, STATS_SECTION + ("\n" + PUSH_SECTION if c.cfg.get("vapid_public") else "") + ("\n" + MEMBERS_SECTION if members_on(c.cfg) else "") + ("\n" + GOOGLE_SECTION if c.cfg.get("google_client_id") else ""), 1)


def legal(c: Ctx) -> dict:
    cfg, site = c.cfg, c.site
    return legal_pages(
        site, cfg, c.preview,
        purpose="記録した日について、あと何日、もう何日かを数え、カレンダーで見られるようにすること。締切・試験・大会・お祭りの公式の日付を、ワンタップで予定に入れられるようにすること。",
        sources_html="各日付のページに、出典(官公庁・主催者の公式ページ)と確認日を載せています。",
        update_text="公式の発表をもとに、随時確認・追加します。",
        disclaimer_html="<p>日付は公式の発表をもとに確認していますが、変更や中止になることがあります。申し込みや手続きの前に、出典の公式ページで確認してください。当サイトの情報をもとにした行動の結果について、当サイトは責任を負いません。</p>"
                        "<p>「あと○日」「もう○日」は、お使いの端末の日付をもとに、ブラウザの中で数えています。端末の日付がずれていると、数字もずれます。</p>",
        contact_notice="日付の誤りのご指摘は、ページの名前と、正しい日付の出典(アドレス)を添えていただけると、早く確認できます。",
        input_note=("<h2>この端末に保存する情報</h2>"
                    "<p>記録した日(名前・日付・時刻・メモ・やること・設定)と、予定に入れた日の一覧、選んだ好きな分野は、お使いのブラウザの中(localStorage)だけに保存します。当サイトのサーバーには送りません。"
                    "ブラウザのデータを消すと記録も消えます。バックアップはマイページの「書き出す」で作れます。</p>"
                    "<h2>カレンダーの購読(任意)</h2>"
                    "<p>ジャンルのページから、公式の日付をカレンダーアプリに購読できます。購読用のファイルは、誰でも取得できる公開データです。購読すると、Google などのカレンダーのサービスが、定期的にこのファイルを取りに来ます。当サイトは、購読した人を知ることはありません。</p>"
                    "<h2>カードの共有(任意)</h2>"
                    "<p>「カードを作って送る」で作ったカードの内容(題名・日付・ひとこと・やること)は、リンクのうち「#」より後ろに入ります。この部分は、ブラウザから当サイトのサーバーへは送られず、保存もされません。リンクを渡した相手の端末で、カードとして表示されます。スマホの共有メニューから渡した文章も、サーバーには送られず、ご利用の端末の中で、カードを作るページに渡されます。リンクを送る相手と手段は、あなたが選びます。</p>"),
        finish=lambda html: c.finish(legal_wording(privacy_fix(c, html)), "legal"),
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
        "index.html": home_page(c), "search/index.html": search_page(c), "interests/index.html": interests_page(c, live), "card/index.html": card_page(c), "my/index.html": my_page(c), "add/index.html": add_page(c),
        "skins/index.html": skins_page(c), "use/index.html": use_index(c), "manual/index.html": manual_page(c), "today/index.html": today_page(c), "calendar/index.html": calendar_page(c), "plan/index.html": plan_page(c),
    }
    for u in usecases.USECASES:
        pages[f"use/{u['slug']}/index.html"] = use_page(c, u)
    for g in catalog.GROUPS:
        pages[f"c/{GROUP_SLUG[g]}/index.html"] = category_page(c, g, live)
    pages.update(og_pages(live))      # og/<id>.png: the picture a chat app shows for a day's link
    pages.update(feeds.feed_pages(live, catalog.GROUPS, GROUP_SLUG, str(cfg["site_url"]).rstrip("/"), today))   # cal/<genre>.ics, cal/all.ics: the days as a calendar to subscribe to
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
        "share_target": {"action": "/card/", "method": "POST", "enctype": "application/x-www-form-urlencoded", "params": {"title": "title", "text": "text", "url": "url"}},
        "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, ensure_ascii=False, indent=1) + "\n"
    pages["sw.js"] = sw_js(c)
    pages["assets/catalog.json"] = c.cat_json
    pages["assets/skins.css"] = c.skins_css
    pages["assets/atomou.js"] = c.bundle
    pages.update(asset_pages(SITE["assets"]))
    # the sitemap lists indexable pages only (not /my/, not event pages that are held back)
    listed = {k: 1 for k in pages if k.endswith("index.html") and k != "my/index.html"
              and k != "plan/index.html" and k != "interests/index.html" and k != "card/index.html" and not (k.startswith("e/") and k.split("/")[1] not in index_ids)}
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
