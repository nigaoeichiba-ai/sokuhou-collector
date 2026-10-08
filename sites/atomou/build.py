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
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog, skins, usecases  # noqa: E402
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
    "nav": [("さがす", "/search/", "/search/"), ("記録する", "/add/", "/add/"), ("マイページ", "/my/", "/my/"), ("きせかえ", "/skins/", "/skins/")],
    "glyph": "日",
    "assets": HERE / "assets",
    "source_html": '日付は、公式の発表などで確認しています。あなたが記録した日は、この端末の中だけに保存されます。<a href="/manual/">つかいかた(説明書)</a> | <a href="/use/">こんな時に</a>',
}
WD = "月火水木金土日"


# ---------- shared helpers ----------
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


def card_html(e: dict, *, own: bool = False, actions: bool = True, big: bool = False, link: bool = True) -> str:
    """The card markup; app.js cardHtml builds the same thing (tests/test_atomou_build.py compares the class lists)."""
    g = catalog.GROUPS.index(e["group"]) + 1 if e.get("group") in catalog.GROUPS else int(e.get("g") or 0)
    key = ("m:" if own else "c:") + e["id"]
    p = e.get("precision") or "day"
    cls = "card" + (" quiet" if e.get("quiet") else "") + (" big" if big else "")
    h = [f'<article class="{cls}" data-key="{esc(key)}" data-title="{esc(e["title"])}" data-date="{esc(e["date"])}" data-p="{p}"'
         + (f' data-g="{g}"' if g else "") + (f' data-cat="{esc(e["category"])}"' if e.get("category") else "") + ">"]
    h.append('<div class="c-top">' + (f'<span class="mark m{g}" data-g="{g}" aria-hidden="true"></span>' if g else "")
             + f'<span class="badge">{esc(e["kind"])}</span>' + (f'<span class="reg">{esc(e["region"])}</span>' if e.get("region") else "") + "</div>")
    h.append('<p class="c-count"><span class="word"></span><span class="num"></span></p><p class="c-sub"></p>')
    title = esc(e["title"])
    linked = '<a href="/e/' + e["id"] + '/">' + title + "</a>" if link and not own else title
    h.append(f'<h3 class="c-title">{linked}</h3>')
    h.append(f'<p class="c-date">{esc(fmt_date(e["date"], p))}</p>')
    h.append('<div class="c-next"></div>' if own else f'<p class="c-src">出典: {esc(host(e["source_url"]))}(確認日 {esc(e["checked_on"])})</p>')
    if actions:
        a = ['<button type="button" class="btn small ghost" data-act="save" aria-pressed="false">☆ 保存する</button>' if not own else ""]
        if p == "day":
            a.append('<button type="button" class="btn small" data-act="ics">カレンダーに入れる</button>')
        h.append('<div class="c-act">' + "".join(a) + "</div>")
        h.append('<div class="c-move"><button type="button" class="mini grip" data-act="grip" aria-label="つかんで動かす">⠿</button>'
                 '<button type="button" class="mini" data-act="up" aria-label="ひとつ前へ">↑</button><button type="button" class="mini" data-act="down" aria-label="ひとつ後ろへ">↓</button></div>')
    h.append("</article>")
    return "".join(h)


def mark_html(i: int) -> str:
    return f'<span class="mark m{i}" data-g="{i}" aria-hidden="true"></span>'


# ---------- site-wide wrapping (skins, scripts, body tag) ----------
class Ctx:
    def __init__(self, cfg: dict, preview: bool, today: date, entries: list[dict], skins_css: str):
        self.cfg, self.preview, self.today, self.entries = cfg, preview, today, entries
        self.cat_json = json.dumps(catalog.public_json(entries), ensure_ascii=False, separators=(",", ":"))
        self.skins_css = skins_css
        self.v_cat = hashlib.sha1(self.cat_json.encode("utf-8")).hexdigest()[:8]
        self.v_skin = hashlib.sha1(skins_css.encode("utf-8")).hexdigest()[:8]
        self.ver = asset_version(SITE["assets"])
        conf = {"v": self.v_cat, "groups": catalog.GROUPS, "slugs": SLUGS,
                "skins": {s["id"]: {"card": s["card"], "name": s["name"]} for s in skins.SKINS}}
        conf_js = json.dumps(conf, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        card_map = json.dumps({s["id"]: s["card"] for s in skins.SKINS}, separators=(",", ":"))
        self.head = (f"<script>window.ATOMOU={conf_js};</script>\n"
                     "<script>(function(){try{var p=(JSON.parse(localStorage.getItem('atomou.v1')||'{}').prefs)||{},m=" + card_map +
                     ",r=document.documentElement;if(p.skin&&p.skin!=='basic'&&m[p.skin]){r.setAttribute('data-skin',p.skin);r.setAttribute('data-card',m[p.skin])}"
                     "if(p.big)r.setAttribute('data-big','1')}catch(e){}})()</script>\n"
                     f'<link rel="stylesheet" href="/assets/skins.css?v={self.v_skin}">\n')
        self.tail = "".join(f'<script src="/assets/{n}.js?v={self.ver}" defer></script>\n' for n in ("core", "ics", "app"))
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
        return html.replace("</body>", self.tail + "</body>", 1)


# ---------- pages ----------
def search_form(q: str = "") -> str:
    return ('<form class="searchbox" id="searchform" action="/search/" method="get" role="search">'
            '<label class="vh" for="q">日付をさがす</label>'
            f'<input type="search" id="q" name="q" value="{esc(q)}" placeholder="さがす(例: 年賀状、共通テスト、流星群)" autocomplete="off">'
            '<button type="submit" class="btn">さがす</button></form>')


def popular_chips(entries: list[dict]) -> str:
    out = []
    for w in POPULAR:
        if any(w in e["title"] or w in e["tags"] for e in entries):
            out.append(f'<a class="chip" href="/search/?q={quote(w)}">{esc(w)}</a>')
    return '<div class="chips scroll" aria-label="よく探される言葉">' + "".join(out) + "</div>" if out else ""


def home_page(c: Ctx) -> str:
    live = live_entries(c.entries, c.today)
    first = diverse(live, 12)
    counts = {g: sum(1 for e in live if e["group"] == g) for g in catalog.GROUPS}
    tiles = "".join(f'<a href="/c/{GROUP_SLUG[g]}/">{mark_html(i + 1)}<span>{esc(g)}<br><small class="muted">{counts[g]}件</small></span></a>' for i, g in enumerate(catalog.GROUPS))
    ucs = "".join(f'<a class="uc" href="/use/{u["slug"]}/"><b>{esc(u["title"])}</b><span>{esc(u["who"])}</span></a>'
                  for u in [usecases.by_slug(s) for s in ("couple-anniversary", "furusato-nozei", "exam-university", "oshi-live", "quit-smoking", "baby-100days")] if u)
    body = f"""<section class="hero">
<h1>{esc(CATCH)}</h1>
<p class="lead">あの日からもう何日? あの日まであと何日? 日付をえらぶだけで数えて、カレンダーに入れられます。締切・試験・大会・お祭りなど、公式の日付は、ワンタップで保存できます。 <a href="/manual/">はじめての方は、説明書へ</a></p>
{search_form()}
{popular_chips(c.entries)}
<nav class="cats" aria-label="ジャンルから探す">{tiles}</nav>
<div class="daily" id="daily" aria-label="今日の数字"></div>
</section>
<section id="mine" hidden>
<div class="head-row"><h2>あなたの日</h2><div class="grow"><a class="btn small ghost" href="/my/">マイページへ</a></div></div>
<div class="cards" id="mine-grid"></div>
</section>
<section>
<div class="head-row"><h2>もうすぐの日</h2><div class="grow"><button type="button" class="btn small" id="shuffle">シャッフル</button>
<button type="button" class="btn small ghost" id="reorder" aria-pressed="false">カードを動かす</button></div></div>
<div class="cards" id="grid">{"".join(card_html(e) for e in first)}</div>
</section>
<section class="panel">
<h2>自分の日も、数えてみませんか</h2>
<ul class="steps"><li>どんな日かを、えらぶ</li><li>日付を、えらぶ</li><li>「この日を残す」を押す</li></ul>
<p>名前や日付は、この端末の中だけに保存します。サーバーには送りません。</p>
<p><a class="btn" href="/add/">日付を記録する</a></p>
</section>
<section>
<div class="head-row"><h2>こんな時に</h2><div class="grow"><a class="btn small ghost" href="/use/">使い方をもっと見る</a></div></div>
<div class="uc-grid">{ucs}</div>
</section>"""
    return c.page("/", f"{NAME}|{CATCH}", "あの日からもう何日?あの日まであと何日?日付をえらぶだけで数えて、カレンダーに入れられます。締切・試験・大会・お祭りなど、確認ずみの日付はワンタップで保存。", body, "home")


def search_page(c: Ctx) -> str:
    chips = '<button type="button" class="chip" data-g-chip="" aria-pressed="true">すべて</button>' + "".join(
        f'<button type="button" class="chip" data-g-chip="{SLUGS[i]}" aria-pressed="false">{esc(g)}</button>' for i, g in enumerate(catalog.GROUPS))
    body = f"""{crumbs([("トップ", "/"), ("さがす", None)])}
<h1>日付をさがす</h1>
<p class="lead muted">ことばで探すか、ジャンルをえらんでください。</p>
{search_form()}
<div class="chips" role="group" aria-label="ジャンル">{chips}<button type="button" class="chip" id="f-son" aria-pressed="false">損得に関わる日だけ</button></div>
<p class="small muted" id="found" aria-live="polite">&nbsp;</p>
<div class="cards" id="results"></div>
<div class="panel" id="none" hidden><p>見つかりませんでした。</p><p>ことばを短くするか、ジャンルを「すべて」にしてみてください。自分の日として、そのまま<a id="none-add" href="/add/">記録する</a>こともできます。</p></div>
<noscript><p class="notice">さがす機能には JavaScript が必要です。ジャンルから探すときは、<a href="/c/deadline/">各ジャンルのページ</a>をご覧ください。</p></noscript>"""
    return c.page("/search/", f"日付をさがす | {NAME}", "ことばやジャンルから、締切・試験・大会・お祭りなどの日付をさがせます。見つけた日はワンタップで保存。", body, "search")


def my_page(c: Ctx) -> str:
    body = f"""{crumbs([("トップ", "/"), ("マイページ", None)])}
<h1>マイページ</h1>
<p class="lead muted">記録した日と、保存した日が並びます。この端末の中だけに保存されます。</p>
<div class="panel" id="my-empty" hidden><p>まだ、ありません。</p><p><a class="btn" href="/add/">日付を記録する</a> <a class="btn ghost" href="/search/">日付をさがす</a></p></div>
<div class="head-row" id="my-tools" hidden><div class="grow" style="margin-left:0"><button type="button" class="btn small ghost" id="reorder" aria-pressed="false">カードを動かす</button>
<button type="button" class="btn small" id="ics-all">まとめてカレンダーに入れる</button></div></div>
<div class="cards" id="my-grid"></div>
<h2>設定</h2>
<div class="panel">
<div class="field"><label class="lab" for="p-big"><input type="checkbox" id="p-big"> 文字を大きくする</label></div>
<div class="field"><label for="p-alarm">保存した日をカレンダーに入れるとき、知らせる時間</label>
<select id="p-alarm"><option value="morning">当日の朝9時</option><option value="eve">前の日の夜9時</option><option value="none">お知らせなし</option></select></div>
<p><a href="/skins/">きせかえ(見た目を変える)</a></p>
</div>
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
<p class="lead muted">えらぶだけで、数えます。年月日が分からなくても、年だけで残せます。</p>
<div id="wizard" class="wizard"><noscript><p class="notice">日付の記録には JavaScript が必要です。</p></noscript></div>"""
    return c.page("/add/", f"日付を記録する | {NAME}", "記念日・誕生日・はじめた日・命日などを、えらぶだけで記録。あと何日、もう何日かをすぐに表示します。", body, "add")


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
<p class="lead muted">見た目を、好きなものに変えられます。えらぶと、すぐに変わります。いちばん上の「ベーシック」が標準です。</p>
<h2>見えかた</h2>
<div class="cards">{"".join(card_html(s, own=True, actions=False, link=False) for s in samples)}</div>
<h2>えらぶ</h2>
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
            parts.append(f'<p class="small muted">さがすことば</p><div class="chips">{tags}</div>')
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
<p><a class="btn ghost" href="/add/?title={quote(e['title'])}&amp;date={e['date']}">自分の日として記録する</a></p>
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
    sample = {"id": "sample", "title": "たとえば、家族で行く旅行の日", "date": (t + timedelta(days=45)).isoformat(), "kind": "楽しみな日", "g": 1, "quiet": False}
    past = {"id": "sample2", "title": "たとえば、はじめた日", "date": (t - timedelta(days=400)).isoformat(), "kind": "はじめた日", "g": 4, "quiet": False}

    def step(n: int, head: str, text: str) -> str:
        return f'<div class="stepcard"><span class="no" aria-hidden="true">{n}</span><div><b>{head}</b><p>{text}</p></div></div>'

    def btn(label: str, ghost: bool = False) -> str:
        return f'<span class="btn small sample{" ghost" if ghost else ""}" aria-hidden="true">{label}</span>'

    qa = [
        ("お金は かかりますか?", "かかりません。会員登録(ログイン)も いりません。"),
        ("入れた日づけは、ほかの人に見えますか?", "見えません。入れた日づけは、いま使っている スマホ・パソコンの中だけに 入ります。当サイトの サーバーには 送りません。"),
        ("スマホを 買いかえたら、どうなりますか?", "新しい スマホには 引きつがれません。買いかえる前に、「マイページ」の「書き出す」で ファイルを 作り、新しい スマホの「読み込む」で もどせます。"),
        ("「カレンダーに入れる」を 押しても、お知らせが 来ません。", "お知らせを 出すのは、カレンダーの アプリです。アプリの 設定で、通知が オンに なっているか 見てください。アプリによっては、お知らせが 出ないことも あります。大切な日は、カレンダーの 画面でも 見て ください。"),
        ("「あと」と「もう」は、どう ちがいますか?", "「あと」は、これから来る日までの 日数です。「もう」は、すぎた日からの 日数です。"),
        ("日数の 数え方を おしえてください。", "今日を 0日 として 数えます。明日は「あと1日」、昨日は「もう1日」です。その日が 今日なら「今日」と 出ます。"),
        ("文字が 小さくて 読みにくいです。", "「マイページ」の「設定」で「文字を大きくする」に 印を 入れてください。「きせかえ」の「大きな文字」や「ハイコントラスト」も 読みやすいです。"),
        ("日づけが まちがっているようです。", "公式の日づけは、変わることが あります。その ページの 出典(もとの ページ)を 見てください。まちがいを 見つけたら、<a href=\"/contact/\">お問い合わせ</a>から 教えてください。"),
        ("大切な人の 日も 入れて いいですか?", "いいです。「大切な人を思う日」を えらぶと、静かな 見た目で 残せます。広告や おすすめは 出しません。"),
        ("入れた日を 消したいです。", "「マイページ」を ひらき、その カードの「消す」を 押します。ぜんぶ 消すときは、「設定」の下の「すべて消す」を 押します。"),
    ]
    qa_html = "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in qa)
    body = f"""{crumbs([("トップ", "/"), ("説明書", None)])}
<div class="manual">
<h1>つかいかた(説明書)</h1>
<p class="lead">むずかしい ことは ありません。ゆっくり 見てください。このページは、いつでも ここに あります。</p>

<h2>このサイトで できること</h2>
<ul class="big-list">
<li><b>日づけを 数えます。</b>「あの日から もう何日」「あの日まで あと何日」が すぐ 分かります。</li>
<li><b>カレンダーに 入れられます。</b>忘れたくない日を、スマホの カレンダーに 入れて、当日に お知らせを 出せます。</li>
<li><b>世の中の 大事な日も 見られます。</b>しめきり、しけん、大会、おまつりなど。正しい 日づけを 調べて 載せています。</li>
</ul>

<h2>はじめて 使うとき</h2>
{step(1, "「記録する」を 押す", "いちばん上の 青い「記録する」を 押します。")}
{step(2, "どんな日かを えらぶ", "「記念日」「誕生日」などの 四角を ひとつ 押します。文字を 打たなくても 大丈夫です。")}
{step(3, "日づけを えらぶ", "日づけの 欄を 押すと、カレンダーが 出ます。そこから えらびます。")}
{step(4, "「この日を残す」を 押す", "これで 終わりです。「マイページ」に 入ります。")}
<p class="hint">日づけの 年や 月が 分からない ときは、「年と月だけ」「年だけ」を えらべます。</p>

<h2>カードの 見かた</h2>
<p>日づけは、「カード」という 四角に 出ます。</p>
<div class="cards" style="max-width:360px">{card_html(sample, own=True, actions=False, link=False)}</div>
<ul class="big-list">
<li><b>「あと」</b> … これから 来る 日までの 日数です。</li>
<li><b>大きな 数字</b> … 日数です。100日より 多いときは、「2年3か月12日」のように 出て、すぐ下に 全部の 日数も 出ます。</li>
<li><b>日づけ</b> … その日が 何月何日の 何曜日かです。</li>
</ul>
<p>すぎた日は、こう 出ます。</p>
<div class="cards" style="max-width:360px">{card_html(past, own=True, actions=False, link=False)}</div>
<p>「<b>もう</b>」は、すぎた日から 数えた 日数です。</p>

<h2>ボタンの はたらき</h2>
<dl class="info big-dl">
<dt>{btn("☆ 保存する", True)}</dt><dd>気に入った日を、マイページに 取っておきます。もう一度 押すと、はずれます。</dd>
<dt>{btn("カレンダーに入れる")}</dt><dd>スマホの カレンダーに 入れる ための ファイルを 作ります。作った ファイルを 開いて、「追加」を 押してください。</dd>
<dt>{btn("消す", True)}</dt><dd>自分で 入れた日を 消します。</dd>
<dt>{btn("シャッフル")}</dt><dd>トップページの カードを、ほかの日に 入れかえます。</dd>
<dt>{btn("カードを動かす", True)}</dt><dd>カードの 並び方を かえられます。「⠿」を 指で つかんで 動かすか、「↑」「↓」を 押します。</dd>
<dt>{btn("さがす")}</dt><dd>ことばで 日づけを さがします。「年賀状」「流星群」など、思いついた ことばを 入れてください。</dd>
<dt>{btn("きせかえ", True)}</dt><dd>見た目を かえます。色や 文字の 大きさを、好きな ものに できます。</dd>
</dl>

<h2>こまったときは</h2>
<div class="qa">{qa_html}</div>
<p>それでも 分からない ときは、<a href="/contact/">お問い合わせ</a>から 聞いてください。</p>
<p><a class="btn" href="/add/">日付を 記録する</a> <a class="btn ghost" href="/use/">こんな時に 使えます(使い方の例)</a></p>
</div>"""
    return c.page("/manual/", f"つかいかた(説明書) | {NAME}", "あと何日、もう何日の使い方を、やさしい言葉で説明します。日づけの入れ方、カードの見かた、ボタンのはたらき、よくある質問。", body, "manual")


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
                    "<p>あなたが記録した日(名前・日付・設定)と、保存した日の一覧は、お使いのブラウザの中(localStorage)だけに保存します。当サイトのサーバーには送りません。"
                    "ブラウザのデータを消すと、記録も消えます。マイページの「書き出す」で、バックアップを作れます。</p>"),
        finish=lambda html: c.finish(html, "legal"),
    )


# ---------- the site ----------
def build_pages(cfg: dict, release: bool = False, today: date | None = None) -> dict:
    today = today or date.today()
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
        "skins/index.html": skins_page(c), "use/index.html": use_index(c), "manual/index.html": manual_page(c),
    }
    for u in usecases.USECASES:
        pages[f"use/{u['slug']}/index.html"] = use_page(c, u)
    for g in catalog.GROUPS:
        pages[f"c/{GROUP_SLUG[g]}/index.html"] = category_page(c, g, live)
    for e in entries:
        pages[f"e/{e['id']}/index.html"] = event_page(c, e, e["id"] in index_ids, live)
    pages.update(legal(c))
    pages["assets/catalog.json"] = c.cat_json
    pages["assets/skins.css"] = c.skins_css
    pages.update(asset_pages(SITE["assets"]))
    # the sitemap lists indexable pages only (not /my/, not event pages that are held back)
    listed = {k: 1 for k in pages if k.endswith("index.html") and k != "my/index.html"
              and not (k.startswith("e/") and k.split("/")[1] not in index_ids)}
    pages.update(standard_files(listed, cfg, preview, today.isoformat()))
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
