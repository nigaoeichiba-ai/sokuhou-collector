"""Static site generator for the minimum-wage site.

Every page is complete HTML (no script needed to read it); app.js only adds sorting, live status and calculators.
Preview builds are marked noindex. A release build refuses to run while operator info is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))  # repo root, so `python sites/saichin/build.py` finds `sokuhou`

from sites.saichin import charts, content, ogimage, wage as wagelib  # noqa: E402
from sokuhou.sitekit import asset_files, asset_pages  # noqa: E402
from sokuhou.sources import mhlw_minwage  # noqa: E402

SLUGS = dict(zip(
    mhlw_minwage.PREFECTURES,
    "hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa "
    "niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama "
    "tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita "
    "miyazaki kagoshima okinawa".split(),
))
SUFFIX = {"北海道": "", "東京": "都", "大阪": "府", "京都": "府"}
REGIONS = [
    ("hokkaido-tohoku", "北海道・東北", "北海道 青森 岩手 宮城 秋田 山形 福島".split()),
    ("kanto", "関東", "茨城 栃木 群馬 埼玉 千葉 東京 神奈川".split()),
    ("chubu", "中部", "新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知".split()),
    ("kinki", "近畿", "三重 滋賀 京都 大阪 兵庫 奈良 和歌山".split()),
    ("chugoku", "中国", "鳥取 島根 岡山 広島 山口".split()),
    ("shikoku", "四国", "徳島 香川 愛媛 高知".split()),
    ("kyushu-okinawa", "九州・沖縄", "福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄".split()),
]
SOURCE_LABEL = "厚生労働省「地域別最低賃金の全国一覧」"
WEEKLY_HOURS, WEEKS_PER_YEAR = 40, 52
WEEKDAYS = "月火水木金土日"
RANKINGS = {
    "high": ("高い順", "最低賃金が高い順", lambda r: (-r["amount"], r["name"])),
    "low": ("低い順", "最低賃金が低い順", lambda r: (r["amount"], r["name"])),
    "raise": ("引上げ額順", "引上げ額が大きい順", lambda r: (-r["raise"], r["name"])),
}


# Xserver's default rules for a new domain: HTTP -> HTTPS redirect and the server cache switches.
# Replacing public_html drops the file, so every build ships it (copied from the live default).
HTACCESS = (
    'SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=off\n'
    'SetEnvIf Request_URI ".*" Ngx_Cache_AllCacheMode\n'
    "AddType text/calendar .ics\n"
    "RewriteEngine on\n"
    "RewriteCond %{HTTPS} !on\n"
    "RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]\n"
)


def asset_version() -> str:
    """Short content hash of the assets; part of their URLs so browsers and server caches never serve stale ones."""
    h = hashlib.sha1()
    for a in asset_files(HERE / "assets"):
        h.update(a.relative_to(HERE / "assets").as_posix().encode("utf-8"))
        h.update(a.read_bytes())
    return h.hexdigest()[:8]


class BuildError(Exception):
    pass


def missing_config(cfg: dict) -> list[str]:
    """Release needs an operator name and at least one way to be contacted (a form URL and/or an email)."""
    missing = [] if cfg.get("operator_name") else ["operator_name"]
    form = cfg.get("contact_form_url")
    if form and not form.startswith("https://"):
        missing.append("contact_form_url (must start with https://)")
    elif not form and not cfg.get("contact_email"):
        missing.append("contact_form_url or contact_email")
    return missing


esc = html.escape
yen = lambda n: f"{n:,}円"  # noqa: E731


def jp_date(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def md(iso: str) -> str:
    _, m, d = (int(x) for x in iso.split("-"))
    return f"{m}月{d}日"


def monthly_for(hourly: int, weekly_hours: int) -> int:
    """Hourly wage x weekly hours x 52 weeks / 12 months, rounded to 100 yen."""
    return round(hourly * weekly_hours * WEEKS_PER_YEAR / 12 / 100) * 100


def monthly_estimate(hourly: int) -> int:
    return monthly_for(hourly, WEEKLY_HOURS)


def man(yen_amount: int) -> str:
    return f"{yen_amount / 10000:.1f}万円"


WORK_PATTERNS = [("フルタイム(週40時間)", 40), ("週30時間", 30), ("週20時間", 20), ("週10時間", 10)]


def earnings_table(r: dict) -> str:
    rows = ""
    for label, hours in WORK_PATTERNS:
        new_y, old_y = r["amount"] * hours * WEEKS_PER_YEAR, r["prev_amount"] * hours * WEEKS_PER_YEAR
        rows += (
            f"<tr><td>{label}</td><td>{yen(monthly_for(r['amount'], hours))}</td><td>{man(new_y)}</td>"
            f"<td>{man(old_y)}</td><td>+{man(new_y - old_y)}</td></tr>"
        )
    return (
        '<div class="tablewrap"><table><thead><tr><th>働き方</th><th>月収の目安(改定後)</th><th>年収の目安(改定後)</th>'
        f"<th>年収の目安(改定前)</th><th>年収の差</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


# ---------------------------------------------------------------- data

def plausible_effective(name: str, fy: int, iso: str) -> tuple[str, str | None]:
    """Effective date of a revision made in fiscal year `fy`, and the original if it had to be corrected.

    A revision is decided from summer onwards and takes effect between October of that year and March of the next.
    MHLW's workbook has, for revisions that took effect in January to March, the year of the decision instead of
    the next year (Akita, Reiwa 7: the workbook says 2025-03-31; the Akita labour bureau says 31 March 2026).
    A date before April of the fiscal year is therefore moved one year on; anything still outside the window is refused.
    """
    lo, hi = date(fy, 4, 1), date(fy + 1, 3, 31)
    dt = date.fromisoformat(iso)
    if lo <= dt <= hi:
        return iso, None
    if dt.month <= 3 and dt.year == fy:
        shifted = date(dt.year + 1, dt.month, dt.day)
        if lo <= shifted <= hi:
            return shifted.isoformat(), iso
    raise BuildError(f"{name}: effective date {iso} of fiscal year {fy} is outside {lo}..{hi} and cannot be corrected")


def prepare(raw: dict) -> dict:
    fy = raw["latest_fiscal_year"]
    labels = raw["fiscal_year_labels"]
    region_of = {p: (slug, name) for slug, name, ps in REGIONS for p in ps}
    if set(region_of) != set(mhlw_minwage.PREFECTURES):
        raise BuildError("REGIONS must cover every prefecture exactly once")
    rows = []
    for p in raw["prefectures"]:
        h = p["history"]
        new, prev = h[str(fy)], h.get(str(fy - 1))
        if prev is None:
            raise BuildError(f"{p['name']}: no previous-year amount")
        eff = new["effective_date"]
        if not eff or not (date(fy, 4, 1) <= date.fromisoformat(eff) <= date(fy + 1, 3, 31)):
            raise BuildError(f"{p['name']}: effective date {eff!r} is outside fiscal year {fy}")
        if not (500 <= new["amount"] <= 3000) or new["amount"] < prev["amount"]:
            raise BuildError(f"{p['name']}: implausible amount {new['amount']} (previous {prev['amount']})")
        history = []
        for y in range(max(2002, fy - 10), fy + 1):
            cur, before = h.get(str(y)), h.get(str(y - 1))
            if cur:
                eff_y = cur["effective_date"]
                fixed_from = None
                if eff_y and before and cur["amount"] != before["amount"]:
                    eff_y, fixed_from = plausible_effective(p["name"], y, eff_y)
                history.append({
                    "fy": y, "label": labels[str(y)], "amount": cur["amount"], "effective_date": eff_y,
                    "raise": cur["amount"] - before["amount"] if before else None, "date_fixed_from": fixed_from,
                })
        slug, region = region_of[p["name"]]
        rows.append({
            "short": p["name"], "name": p["name"] + SUFFIX.get(p["name"], "県"), "slug": SLUGS[p["name"]],
            "amount": new["amount"], "prev_amount": prev["amount"], "raise": new["amount"] - prev["amount"],
            "effective_date": eff, "history": history, "region_slug": slug, "region": region,
        })
    # Rank among the 47 prefectures in every year shown (ties share a rank).
    by_year: dict[str, list[int]] = {}
    for p in raw["prefectures"]:
        for y, v in p["history"].items():
            by_year.setdefault(y, []).append(v["amount"])
    for r, p in zip(rows, raw["prefectures"]):
        for h, y in zip(r["history"], [str(y) for y in range(max(2002, fy - 10), fy + 1) if str(y) in p["history"]]):
            h["rank"] = 1 + sum(1 for a in by_year[y] if a > h["amount"])
    amounts = [r["amount"] for r in rows]
    lo, hi = min(amounts), max(amounts)
    ranked = sorted(amounts, reverse=True)
    for r in rows:
        r["rank"] = ranked.index(r["amount"]) + 1
        r["meter"] = max(8, round((r["amount"] - lo) / ((hi - lo) or 1) * 100))
    raises = sorted((r["raise"] for r in rows), reverse=True)
    for r in rows:
        r["raise_rank"] = raises.index(r["raise"]) + 1
    avg = raw["national_weighted_average"]
    # Year-by-year national summary, from the same workbook.
    years = []
    for y in sorted(int(k) for k in labels):
        amts = [(p["history"][str(y)]["amount"], p["name"]) for p in raw["prefectures"] if str(y) in p["history"]]
        if str(y) in avg and amts:
            top, bottom = max(amts), min(amts)
            years.append({"fy": y, "label": labels[str(y)], "avg": avg[str(y)],
                          "max": top[0], "max_name": top[1], "min": bottom[0], "min_name": bottom[1]})
    return {
        "fy": fy, "label": labels[str(fy)], "rows": rows,
        "avg": avg[str(fy)], "avg_prev": avg[str(fy - 1)], "years": years,
        "source_page": raw["source_page"], "fetched_date": raw["fetched_at"][:10], "fetched_at": raw["fetched_at"],
    }


# ---------------------------------------------------------------- layout

# (label, link, section prefix used to mark the current section)
NAV = [("全国一覧", "/", "/"), ("地方別", "/area/", "/area/"), ("ランキング", "/ranking/high/", "/ranking/"),
       ("発効日", "/calendar/", "/calendar/"), ("推移", "/history/", "/history/"), ("解説", "/guide/", "/guide/"),
       ("通知", "/notify/", "/notify/")]


def icon(name: str) -> str:
    return f'<svg class="icon" aria-hidden="true"><use href="/assets/icons.svg#{name}"/></svg>'


GUIDE_ICONS = {"what-is": "guide", "how-decided": "chart", "excluded": "compare", "calculate": "yen", "below": "emergency"}


def guide_card(g: dict) -> str:
    return (f'<a class="guide-card" href="/guide/{g["slug"]}/"><img class="gc-img" src="/assets/img/guide-{g["slug"]}.webp" alt="" '
            f'width="800" height="450" loading="lazy"><div class="gc-body"><b>{esc(g["title"])}</b><span>{esc(g["lead"])}</span></div></a>')


def nav_html(path: str) -> str:
    out = []
    for label, href, prefix in NAV:
        current = path == "/" if prefix == "/" else path.startswith(prefix)
        out.append(f'<a href="{href}"{" aria-current=\'page\'" if current else ""}>{label}</a>')
    return "".join(out)


def layout(cfg: dict, preview: bool, *, path: str, title: str, description: str, body: str, scripts: bool = True) -> str:
    base = cfg["site_url"].rstrip("/")
    name = esc(cfg["site_name"])
    robots = '<meta name="robots" content="noindex,nofollow">\n' if preview else ""
    banner = (
        '<div class="preview">プレビュー版です。運営者情報などが未設定のため、検索エンジンには公開されません。</div>\n'
        if preview else ""
    )
    adsense = ""
    if cfg.get("adsense_pub_id"):
        pub = cfg["adsense_pub_id"].replace("ca-", "")
        adsense = (
            '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client=ca-{esc(pub)}" crossorigin="anonymous"></script>\n'
        )
    ver = asset_version()
    og = cfg.get("_og") or {}
    if og.get("enabled"):
        key = path.strip("/")
        url = f"{base}/og/{key if key in og.get('slugs', ()) else 'default'}.png"
        og_tags = "".join(
            f"{line}\n" for line in (
                f'<meta property="og:image" content="{esc(url)}">',
                '<meta property="og:image:width" content="1200">',
                '<meta property="og:image:height" content="630">',
                '<meta name="twitter:card" content="summary_large_image">',
                f'<meta name="twitter:image" content="{esc(url)}">',
            )
        )
    else:
        og_tags = '<meta name="twitter:card" content="summary">\n'
    script = f'<script src="/assets/app.js?v={ver}" defer></script>\n' if scripts else ""
    nav = nav_html(path)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(base + path)}">
{robots}<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(base + path)}">
{og_tags}<link rel="alternate" type="application/atom+xml" title="発効のお知らせ" href="/feed.xml">
<link rel="stylesheet" href="/assets/style.css?v={ver}">
{adsense}</head>
<body>
{banner}<header class="site"><div class="wrap">
<a class="brand" href="/"><span class="logo" aria-hidden="true">&yen;</span>{name}</a>
<nav aria-label="メイン">{nav}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p class="src">出典: <a href="{{source}}" rel="noopener" target="_blank">{SOURCE_LABEL}</a>を加工して作成。厚生労働省が作成したものではありません。このサイトは「地域別最低賃金」を扱い、業種ごとの最低賃金(特定最低賃金など)は含みません。</p>
<p class="legal"><a href="/about/">運営者情報</a><a href="/privacy/">プライバシーポリシー</a><a href="/contact/">お問い合わせ</a><span>&copy; {name}</span></p>
</div></footer>
{script}</body>
</html>
"""


def finish(page: str, d: dict) -> str:
    return page.replace("{source}", esc(d["source_page"]))


def crumbs(items: list[tuple[str, str | None]]) -> str:
    out = []
    for label, href in items:
        out.append(f'<a href="{href}">{esc(label)}</a>' if href else f"<span>{esc(label)}</span>")
    return '<nav class="crumbs" aria-label="パンくず">' + " &gt; ".join(out) + "</nav>"


def pref_card(r: dict) -> str:
    return (
        f'<a class="pref-card" href="/{r["slug"]}/" data-date="{r["effective_date"]}">'
        f'<span class="pc-name">{esc(r["name"])}</span>'
        f'<span class="pc-amt">{r["amount"]:,}<small>円</small></span>'
        f'<span class="pc-meta"><b class="up">+{r["raise"]}円</b><span>{md(r["effective_date"])}発効</span></span>'
        f'<span class="chip state" data-date="{r["effective_date"]}"></span>'
        f'<span class="meter" aria-hidden="true"><i style="width:{r["meter"]}%"></i></span></a>'
    )


def mini_list(rows: list[dict], fmt) -> str:
    return "<ol class=\"mini\">" + "".join(
        f'<li><a href="/{r["slug"]}/">{esc(r["name"])}</a><b>{fmt(r)}</b></li>' for r in rows
    ) + "</ol>"


# ---------------------------------------------------------------- pages

def index_page(d: dict, cfg: dict, preview: bool) -> str:
    rows = d["rows"]
    hi = max(rows, key=lambda r: r["amount"])
    lo = min(rows, key=lambda r: r["amount"])
    first, last = min(r["effective_date"] for r in rows), max(r["effective_date"] for r in rows)
    diff = round(d["avg"]) - round(d["avg_prev"])
    options = "".join(f'<option value="{esc(r["name"])}">{esc(r["name"])}</option>' for r in rows)
    data = json.dumps(
        [{"name": r["name"], "amount": r["amount"], "prev": r["prev_amount"], "date": r["effective_date"]} for r in rows],
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    regions = ""
    for slug, rname, shorts in REGIONS:
        members = [r for r in rows if r["short"] in shorts]
        regions += (
            f'<section class="region" id="r-{slug}"><div class="region-head"><h3>{esc(rname)}</h3>'
            f'<a href="/area/{slug}/">{esc(rname)}のまとめを見る</a></div>'
            f'<div class="card-grid">{"".join(pref_card(r) for r in members)}</div></section>'
        )
    top = sorted(rows, key=RANKINGS["high"][2])[:5]
    bottom = sorted(rows, key=RANKINGS["low"][2])[:5]
    ups = sorted(rows, key=RANKINGS["raise"][2])[:5]
    trs = "".join(
        f'<tr data-name="{esc(r["name"])}" data-amount="{r["amount"]}" data-prev="{r["prev_amount"]}" '
        f'data-raise="{r["raise"]}" data-date="{r["effective_date"]}">'
        f'<td><a href="/{r["slug"]}/">{esc(r["name"])}</a></td><td>{yen(r["amount"])}</td><td>{yen(r["prev_amount"])}</td>'
        f'<td>+{r["raise"]}円</td><td>{jp_date(r["effective_date"])}</td><td class="state" data-date="{r["effective_date"]}"></td></tr>'
        for r in sorted(rows, key=lambda r: (r["effective_date"], r["name"]))
    )
    guides = "".join(guide_card(g) for g in content.GUIDES)
    body = f"""<section class="hero hero--saichin">
<div class="hero-copy">
<p class="eyebrow">{esc(d['label'])} 地域別最低賃金</p>
<h1>最低賃金 改定速報</h1>
<div class="hero-main">
<div class="big" aria-label="全国加重平均 {round(d['avg']):,}円">{round(d['avg']):,}<small>円</small></div>
<div class="hero-sub"><b>全国加重平均</b><span>昨年度 {round(d['avg_prev']):,}円から <em>+{diff}円</em></span></div>
</div>
</div>
<ul class="hero-facts">
<li><span>{icon("up")}最も高い</span><b>{esc(hi['name'])} {yen(hi['amount'])}</b></li>
<li><span>{icon("down")}最も低い</span><b>{esc(lo['name'])} {yen(lo['amount'])}</b></li>
<li><span>{icon("calendar")}発効日</span><b>{md(first)} 〜 {md(last)}</b></li>
</ul>
<div class="progress js-only" hidden><div class="progress-text">発効済み <b id="done-count">0</b> / {len(rows)} 都道府県</div><div class="progress-bar"><i id="done-bar" style="width:0"></i></div></div>
<a class="btn" href="#check">自分の時給をチェック</a>
</section>

<section id="check" class="panel">
<h2>あなたの時給は大丈夫?</h2>
<div class="box js-only" hidden>
<div class="controls"><select id="pref" aria-label="都道府県"><option value="">都道府県を選ぶ</option>{options}</select>
<input id="wage" type="number" inputmode="numeric" min="0" step="1" placeholder="時給(円)" aria-label="時給(円)"></div>
<p class="result" id="check-out">都道府県と時給を入れると、現在の最低賃金と比べます。</p>
</div>
<noscript><p class="notice">この機能にはJavaScriptが必要です。下の一覧で、お住まいの都道府県の額をご確認ください。月給の場合は、<a href="/guide/calculate/">時間額への換算</a>をご覧ください。</p></noscript>
</section>

<section>
<h2>都道府県別の最低賃金</h2>
<p class="section-lead">地方ごとに並べています。都道府県名を押すと、過去の推移や月給の目安を見られます。</p>
{regions}
</section>

<img class="page-banner" src="/assets/img/section-work.webp" alt="いろいろな仕事で働く人たちのイラスト" width="1200" height="500" loading="lazy">

<section>
<h2>ランキング</h2>
<div class="rank-grid">
<div class="rank-box"><h3>高い順 TOP5</h3>{mini_list(top, lambda r: yen(r["amount"]))}<a href="/ranking/high/">全47都道府県を見る</a></div>
<div class="rank-box"><h3>低い順 TOP5</h3>{mini_list(bottom, lambda r: yen(r["amount"]))}<a href="/ranking/low/">全47都道府県を見る</a></div>
<div class="rank-box"><h3>引上げ額 TOP5</h3>{mini_list(ups, lambda r: "+" + str(r["raise"]) + "円")}<a href="/ranking/raise/">全47都道府県を見る</a></div>
</div>
</section>

<section>
<h2>表で見る・並べ替える</h2>
<div class="controls js-only" hidden>
<input id="q" type="search" placeholder="都道府県で絞り込み" aria-label="都道府県で絞り込み">
<select id="status" aria-label="状態"><option value="">すべて</option><option value="done">発効済み</option><option value="soon">これから発効</option></select>
</div>
<div class="tablewrap"><table id="wage-table">
<thead><tr><th data-key="name">都道府県</th><th data-key="amount">新しい最低賃金</th><th data-key="prev">昨年度</th><th data-key="raise">引上げ額</th><th data-key="date">発効日</th><th data-key="state">状態</th></tr></thead>
<tbody>{trs}</tbody></table></div>
</section>

<section>
<h2>最低賃金のきほん</h2>
<div class="guide-grid">{guides}</div>
</section>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。{esc(SOURCE_LABEL)}をもとに作成しています。</p>
<script type="application/json" id="data">{data}</script>"""
    return finish(layout(
        cfg, preview, path="/", title=f"{d['label']} 最低賃金の改定速報 都道府県別の新額と発効日",
        description=f"{d['label']}の地域別最低賃金を、全国47都道府県の新しい時給と発効日で一覧にします。全国加重平均は{round(d['avg']):,}円です。",
        body=body,
    ), d)


def pref_page(d: dict, r: dict, cfg: dict, preview: bool) -> str:
    diff_avg = r["amount"] - round(d["avg"])
    diff_text = "全国加重平均と同じ額です" if diff_avg == 0 else f"全国加重平均より{abs(diff_avg)}円{'高い' if diff_avg > 0 else '低い'}額です"
    hist = "".join(
        f'<tr><td>{esc(h["label"])}</td><td>{yen(h["amount"])}</td><td>{"+" + str(h["raise"]) + "円" if h["raise"] is not None else "-"}</td>'
        f'<td>{h["rank"]}位</td><td>{jp_date(h["effective_date"]) if h["effective_date"] else "-"}{"※" if h.get("date_fixed_from") else ""}</td></tr>'
        for h in reversed(r["history"])
    )
    fixed = [h for h in r["history"] if h.get("date_fixed_from")]
    fixed_note = "".join(
        f'<p class="notice">※ 厚生労働省の一覧表では、{esc(h["label"])}の発効日が{jp_date(h["date_fixed_from"])}となっています。'
        f'改定は夏以降に決まるため、この日付より前に発効することはなく、1年後の{jp_date(h["effective_date"])}として表示しています。</p>'
        for h in fixed
    )
    chart = charts.line(
        [(h["label"].replace("年度", "").replace("令和", "R").replace("平成", "H"), h["amount"]) for h in r["history"]],
        title=f"{r['name']}の最低賃金の推移", desc=f"{r['history'][0]['label']}から{r['history'][-1]['label']}までの{r['name']}の最低賃金(円)の推移", label_every=2,
    )
    mates = sorted((x for x in d["rows"] if x["region_slug"] == r["region_slug"] and x is not r), key=lambda x: -x["amount"])
    mate_html = "".join(f'<li><a href="/{x["slug"]}/">{esc(x["name"])}</a><b>{yen(x["amount"])}</b></li>' for x in mates)
    nav = "".join(f'<li><a href="/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in d["rows"] if x is not r)
    body = f"""{crumbs([("全国", "/"), (r["region"], f"/area/{r['region_slug']}/"), (r["name"], None)])}
<h1>{esc(r['name'])}の最低賃金({esc(d['label'])}) {yen(r['amount'])}</h1>
<p class="lead">{esc(d['label'])}の最低賃金は、{yen(r['prev_amount'])}から{yen(r['amount'])}(+{r['raise']}円)に改定され、発効日は{jp_date(r['effective_date'])}です。</p>
<p class="status" data-status data-date="{r['effective_date']}" data-amount="{r['amount']}" data-prev="{r['prev_amount']}"></p>
<div class="stats">
<div class="stat strong"><span>新しい最低賃金</span><b>{yen(r['amount'])}</b><span>{jp_date(r['effective_date'])} 発効</span></div>
<div class="stat"><span>昨年度</span><b>{yen(r['prev_amount'])}</b><span>引上げ額 +{r['raise']}円</span></div>
<div class="stat"><span>全国での順位</span><b>47都道府県中 {r['rank']}位</b><span>同額は同じ順位とします</span></div>
</div>
<h2>全国と比べると</h2>
<p>{esc(r['name'])}の{esc(d['label'])}の最低賃金は{yen(r['amount'])}で、{diff_text}(全国加重平均 {yen(round(d['avg']))})。引上げ額の+{r['raise']}円は、47都道府県中{r['raise_rank']}位です。</p>
<h2>最低賃金の推移</h2>
{chart}
<div class="tablewrap"><table><thead><tr><th>年度</th><th>最低賃金</th><th>前年度からの引上げ</th><th>全国順位</th><th>発効日</th></tr></thead><tbody>{hist}</tbody></table></div>
{fixed_note}
<h2>最低賃金で働いた場合の月収・年収の目安</h2>
<p>最低賃金ちょうどで働いた場合の目安です。1年を52週、月収は年収を12で割った額として計算しています。税・社会保険料・手当・賞与・祝日などは含みません。実際の給料と比べるときは、<a href="/guide/calculate/">時間額への換算</a>をご覧ください。</p>
{earnings_table(r)}
{wage_section(d, r) if d.get("wage") else ""}
<h2>同じ地方({esc(r['region'])})の最低賃金</h2>
<ul class="mini-list">{mate_html}</ul>
<p><a href="/area/{r['region_slug']}/">{esc(r['region'])}のまとめを見る</a></p>
<h2>発効日を通知で受け取る</h2>
<p><a href="/calendar/{r['slug']}.ics">{esc(r['name'])}の発効日を、カレンダーに入れる</a>(前日の朝9時に通知。登録不要)。ほかの方法は、<a href="/notify/">通知を受け取る</a>をご覧ください。</p>
<h2>あわせて読む</h2>
<ul class="link-list"><li><a href="/guide/excluded/">最低賃金に含まれない賃金は?</a></li><li><a href="/guide/below/">最低賃金を下回っていたら?</a></li><li><a href="/calendar/">発効日カレンダー</a></li></ul>
<h2>ほかの都道府県</h2>
<ul class="pref-nav">{nav}</ul>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。{esc(SOURCE_LABEL)}をもとに作成しています。</p>"""
    return finish(layout(
        cfg, preview, path=f"/{r['slug']}/",
        title=f"{r['name']}の最低賃金は{yen(r['amount'])}({d['label']}) 発効日と過去の推移",
        description=f"{r['name']}の{d['label']}の最低賃金は{yen(r['amount'])}(+{r['raise']}円)。発効日は{jp_date(r['effective_date'])}。過去の推移と月給の目安も掲載しています。",
        body=body,
    ), d)


def area_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    cards = ""
    for slug, rname, shorts in REGIONS:
        members = [r for r in d["rows"] if r["short"] in shorts]
        lo, hi = min(r["amount"] for r in members), max(r["amount"] for r in members)
        cards += (
            f'<a class="guide-card" href="/area/{slug}/"><b>{esc(rname)}</b>'
            f'<span>{len(members)}都道府県 / {yen(lo)}〜{yen(hi)}</span></a>'
        )
    body = f"""{crumbs([("全国", "/"), ("地方別", None)])}
<h1>地方別の最低賃金({esc(d['label'])})</h1>
<p class="lead">全国を7つの地方に分けて、最低賃金をまとめています。</p>
<div class="guide-grid">{cards}</div>"""
    return finish(layout(cfg, preview, path="/area/", title=f"地方別の最低賃金一覧({d['label']})",
                         description=f"{d['label']}の最低賃金を、北海道・東北、関東、中部、近畿、中国、四国、九州・沖縄の7つの地方別にまとめます。", body=body), d)


def area_page(d: dict, slug: str, rname: str, shorts: list[str], cfg: dict, preview: bool) -> str:
    members = sorted((r for r in d["rows"] if r["short"] in shorts), key=lambda r: (-r["amount"], r["name"]))
    hi, lo = members[0], members[-1]
    mean = sum(r["amount"] for r in members) / len(members)
    cards = "".join(pref_card(r) for r in members)
    rows = "".join(
        f'<tr><td><a href="/{r["slug"]}/">{esc(r["name"])}</a></td><td>{yen(r["amount"])}</td><td>+{r["raise"]}円</td><td>{jp_date(r["effective_date"])}</td></tr>'
        for r in members
    )
    others = "".join(f'<li><a href="/area/{s}/">{esc(n)}</a></li>' for s, n, _ in REGIONS if s != slug)
    body = f"""{crumbs([("全国", "/"), ("地方別", "/area/"), (rname, None)])}
<h1>{esc(rname)}の最低賃金({esc(d['label'])})</h1>
<p class="lead">{esc(rname)}の{len(members)}都道府県の最低賃金です。最も高いのは{esc(hi['name'])}の{yen(hi['amount'])}、最も低いのは{esc(lo['name'])}の{yen(lo['amount'])}で、差は{hi['amount'] - lo['amount']}円です。</p>
<div class="stats">
<div class="stat strong"><span>最も高い</span><b>{yen(hi['amount'])}</b><span>{esc(hi['name'])}</span></div>
<div class="stat"><span>最も低い</span><b>{yen(lo['amount'])}</b><span>{esc(lo['name'])}</span></div>
<div class="stat"><span>単純平均</span><b>{yen(round(mean))}</b><span>各都道府県の額の平均(加重なし)</span></div>
</div>
<h2>都道府県別</h2>
<div class="card-grid">{cards}</div>
<h2>一覧表</h2>
<div class="tablewrap"><table><thead><tr><th>都道府県</th><th>最低賃金</th><th>引上げ額</th><th>発効日</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>ほかの地方</h2>
<ul class="pref-nav">{others}</ul>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。{esc(SOURCE_LABEL)}をもとに作成しています。単純平均は、このサイトで計算した参考値です。</p>"""
    return finish(layout(cfg, preview, path=f"/area/{slug}/", title=f"{rname}の最低賃金一覧({d['label']})",
                         description=f"{rname}の最低賃金を一覧にします。最高は{hi['name']}の{yen(hi['amount'])}、最低は{lo['name']}の{yen(lo['amount'])}。発効日も掲載しています。", body=body), d)


WAGE_RANKINGS = {
    "wage": ("平均賃金の高い順", "平均賃金(時給換算)が高い順"),
    "ratio": ("最低賃金の比率順", "最低賃金が平均賃金に近い順"),
}


def ranking_tabs(d: dict, current: str) -> str:
    kinds = {k: v[0] for k, v in RANKINGS.items()}
    if d.get("wage"):
        kinds.update({k: v[0] for k, v in WAGE_RANKINGS.items()})
    return "".join(f'<a href="/ranking/{k}/"{" class=\"on\"" if k == current else ""}>{label}</a>' for k, label in kinds.items())


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def wage_notes(d: dict) -> str:
    """How to read the wage figures; every statement is taken from the cited MHLW pages (checked 2026-10-05)."""
    w = d["wage"]
    return f"""<h2>この数字の見方</h2>
<ul class="prose-list">
<li><strong>賃金統計の対象:</strong> {esc(w['year_label'])}賃金構造基本統計調査の、一般労働者(短時間労働者以外の常用労働者)の賃金です。調査は、毎年6月分の賃金について行われます。</li>
<li><strong>所定内給与:</strong> 6月に支払われた現金給与額から、残業代などの超過労働給与額を除いた額です。税や社会保険料を引く前の額で、手取りではありません。</li>
<li><strong>時給換算:</strong> このサイトで、月の所定内給与を、月の所定内実労働時間数で割って求めた目安です。厚生労働省が公表している「1時間当たり所定内給与額」(労働者ごとに計算した値)とは、計算の方法が違います。</li>
<li><strong>年収相当:</strong> 6月のきまって支給する現金給与額を12倍し、昨年1年間の賞与などの特別給与額を足した額です。実際の年収とは異なります。</li>
<li><strong>最低賃金との比較:</strong> 賃金の調査時点(調査年の6月)に有効だった最低賃金({esc(w['min_then_label'])}の額)と比べています。最新の{esc(d['label'])}の額とは比べていません。比べる相手は、賃金の<strong>平均</strong>です。平均は高い賃金の影響を受けやすいため、中央値と比べた場合とは、比率が違います。</li>
<li><strong>誤差:</strong> 調査は標本調査で、集計の区分によっては標本誤差が大きくなることがあります。都道府県どうしの小さな差は、順位を比べるときに注意してください。</li>
</ul>
<p class="notice">出典: <a href="{esc(w['source_page'])}" rel="noopener" target="_blank">{esc(wagelib.SOURCE_LABEL)}</a>、<a href="{wagelib.SURVEY_PAGE}" rel="noopener" target="_blank">賃金構造基本統計調査の概要</a>を加工して作成。厚生労働省が作成したものではありません。最低賃金は、<a href="{{source}}" rel="noopener" target="_blank">{SOURCE_LABEL}</a>です。</p>"""


def wage_ranking_page(d: dict, kind: str, cfg: dict, preview: bool) -> str:
    w = d["wage"]
    short, long_ = WAGE_RANKINGS[kind]
    field = {"wage": "hourly", "ratio": "ratio"}[kind]
    rank_key = {"wage": "hourly_rank", "ratio": "ratio_rank"}[kind]
    by_slug = {r["name"]: r for r in d["rows"]}
    ordered = sorted(w["rows"].items(), key=lambda kv: (-kv[1][field], kv[0]))
    if kind == "wage":
        head = "<th>順位</th><th>都道府県</th><th>平均賃金(時給換算)</th><th>所定内給与(月)</th><th>年収相当</th>"
        lines = "".join(
            f'<tr><td class="rk">{v[rank_key]}</td><td><a href="/{by_slug[n]["slug"]}/">{esc(n)}</a></td><td>{yen(v["hourly"])}</td>'
            f'<td>{v["pay_k"] / 10:.1f}万円</td><td>{man(v["annual"])}</td></tr>' for n, v in ordered)
        lead = (f"{w['year_label']}の賃金統計から、47都道府県を、平均賃金(月の所定内給与を所定内実労働時間で割った時給換算)が高い順に並べています。"
                f"全国は{yen(w['national']['hourly'])}です。")
    else:
        head = (f"<th>順位</th><th>都道府県</th><th>最低賃金÷平均賃金</th><th>最低賃金({esc(w['min_then_label'])})</th><th>平均賃金(時給換算)</th>")
        lines = "".join(
            f'<tr><td class="rk">{v[rank_key]}</td><td><a href="/{by_slug[n]["slug"]}/">{esc(n)}</a></td><td>{pct(v["ratio"])}</td>'
            f'<td>{yen(v["min_then"])}</td><td>{yen(v["hourly"])}</td></tr>' for n, v in ordered)
        lead = (f"賃金の調査時点(調査年の6月)に有効だった最低賃金が、平均賃金(時給換算)の何%にあたるかを、高い順に並べています。"
                f"全国は{pct(w['national']['ratio'])}です。比率が高い都道府県ほど、平均的な賃金に対して最低賃金が近い水準です。")
    body = f"""{crumbs([("全国", "/"), ("ランキング", None)])}
<h1>{short}({esc(w['year_label'])}賃金統計)</h1>
<p class="lead">{lead}</p>
<div class="tabs" role="tablist">{ranking_tabs(d, kind)}</div>
<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{lines}</tbody></table></div>
{wage_notes(d)}"""
    return finish(layout(cfg, preview, path=f"/ranking/{kind}/", title=f"{short} 47都道府県({w['year_label']}賃金統計)",
                         description=f"{w['year_label']}賃金構造基本統計調査をもとに、{long_}に47都道府県を並べました。定義と読み方も説明します。", body=body), d)


def wage_section(d: dict, r: dict) -> str:
    """Block for a prefecture page: how its pay compares with the nation, and where the minimum wage sits."""
    w = d["wage"]
    v, n = w["rows"][r["name"]], w["national"]
    ratio_gap = "高い" if v["ratio"] > n["ratio"] else "低い"
    return f"""<h2>賃金の実態との比較({esc(w['year_label'])}賃金統計)</h2>
<p>{esc(r['name'])}の一般労働者の平均賃金(時給換算)は{yen(v['hourly'])}で、47都道府県中{v['hourly_rank']}位です(全国は{yen(n['hourly'])})。{esc(w['min_then_label'])}の最低賃金({yen(v['min_then'])})は、その{pct(v['ratio'])}にあたり、全国の{pct(n['ratio'])}より{ratio_gap}比率です。</p>
<div class="tablewrap"><table><thead><tr><th>項目</th><th>{esc(r['name'])}</th><th>全国</th></tr></thead><tbody>
<tr><td>所定内給与(月・男女計)</td><td>{v['pay_k'] / 10:.1f}万円</td><td>{n['pay_k'] / 10:.1f}万円</td></tr>
<tr><td>うち男性</td><td>{v['male_k'] / 10:.1f}万円</td><td>{n['male_k'] / 10:.1f}万円</td></tr>
<tr><td>うち女性</td><td>{v['female_k'] / 10:.1f}万円</td><td>{n['female_k'] / 10:.1f}万円</td></tr>
<tr><td>所定内実労働時間(月)</td><td>{v['hours']}時間</td><td>{n['hours']}時間</td></tr>
<tr><td>平均賃金(時給換算)</td><td>{yen(v['hourly'])}</td><td>{yen(n['hourly'])}</td></tr>
<tr><td>年収相当</td><td>{man(v['annual'])}</td><td>{man(n['annual'])}</td></tr>
<tr><td>最低賃金({esc(w['min_then_label'])})</td><td>{yen(v['min_then'])}</td><td>{yen(n['min_then'])}(全国加重平均)</td></tr>
<tr><td>最低賃金÷平均賃金</td><td>{pct(v['ratio'])}(全国{v['ratio_rank']}位)</td><td>{pct(n['ratio'])}</td></tr>
</tbody></table></div>
<p class="notice">一般労働者の6月分の賃金です。時給換算と年収相当は、このサイトでの計算です。定義と読み方は<a href="/ranking/wage/">平均賃金のランキング</a>のページをご覧ください。</p>"""


def ranking_page(d: dict, kind: str, cfg: dict, preview: bool) -> str:
    short, long_, key = RANKINGS[kind]
    rows = sorted(d["rows"], key=key)
    tabs = ranking_tabs(d, kind)
    ascending = sorted(r["amount"] for r in d["rows"])
    rank_of = {
        "high": lambda r: r["rank"],
        "low": lambda r: ascending.index(r["amount"]) + 1,
        "raise": lambda r: r["raise_rank"],
    }[kind]
    body_rows = "".join(
        f'<tr><td class="rk">{rank_of(r)}</td><td><a href="/{r["slug"]}/">{esc(r["name"])}</a></td><td>{yen(r["amount"])}</td>'
        f'<td>+{r["raise"]}円</td><td>{md(r["effective_date"])}</td></tr>'
        for r in rows
    )
    body = f"""{crumbs([("全国", "/"), ("ランキング", None)])}
<h1>最低賃金ランキング({esc(d['label'])}) {short}</h1>
<p class="lead">全47都道府県を、{long_}に並べています。同額・同じ引上げ額は、同じ順位です。</p>
<div class="tabs" role="tablist">{tabs}</div>
<div class="tablewrap"><table><thead><tr><th>順位</th><th>都道府県</th><th>最低賃金</th><th>引上げ額</th><th>発効日</th></tr></thead><tbody>{body_rows}</tbody></table></div>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。{esc(SOURCE_LABEL)}をもとに作成しています。</p>"""
    return finish(layout(cfg, preview, path=f"/ranking/{kind}/", title=f"最低賃金ランキング{short}({d['label']}) 47都道府県",
                         description=f"{d['label']}の最低賃金を、{long_}に47都道府県すべてランキングにしました。", body=body), d)


def calendar_page(d: dict, cfg: dict, preview: bool) -> str:
    days: dict[str, list[dict]] = {}
    for r in d["rows"]:
        days.setdefault(r["effective_date"], []).append(r)
    sections = ""
    for iso in sorted(days):
        y, m, dd = (int(x) for x in iso.split("-"))
        wd = WEEKDAYS[date(y, m, dd).weekday()]
        chips = "".join(
            f'<li><a href="/{r["slug"]}/">{esc(r["name"])}</a><span>{yen(r["amount"])}</span></li>'
            for r in sorted(days[iso], key=lambda r: (-r["amount"], r["name"]))
        )
        sections += (
            f'<section class="cal-day" id="d-{iso}" data-date="{iso}"><h2>{m}月{dd}日({wd}) <span class="chip state" data-date="{iso}"></span>'
            f'<small>{len(days[iso])}都道府県</small></h2><ul class="cal-list">{chips}</ul></section>'
        )
    body = f"""{crumbs([("全国", "/"), ("発効日カレンダー", None)])}
<h1>最低賃金の発効日カレンダー({esc(d['label'])})</h1>
<p class="lead">新しい最低賃金が、いつ、どの都道府県で効力を持つかを、日付順にまとめています。発効日は都道府県ごとに異なります。<a href="/notify/">発効日をカレンダーや通知で受け取る方法</a>もあります。</p>
{sections}
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。発効日が決まる仕組みは、<a href="/guide/how-decided/">最低賃金はどう決まる?</a>をご覧ください。</p>"""
    return finish(layout(cfg, preview, path="/calendar/", title=f"最低賃金の発効日カレンダー({d['label']}) 日付順の一覧",
                         description=f"{d['label']}の最低賃金の発効日を、日付順に一覧にします。{len(days)}日に分かれて、都道府県ごとに順次発効します。", body=body), d)


def history_page(d: dict, cfg: dict, preview: bool) -> str:
    ys = d["years"]
    chart = charts.line(
        [(y["label"].replace("年度", "").replace("令和", "R").replace("平成", "H"), y["avg"]) for y in ys],
        title="全国加重平均の最低賃金の推移", desc=f"{ys[0]['label']}から{ys[-1]['label']}までの、全国加重平均の最低賃金(円)の推移", label_every=4,
    )
    prev = None
    rows = ""
    for y in ys:
        up = f"+{round(y['avg'] - prev)}円" if prev is not None else "-"
        rows += (f'<tr><td>{esc(y["label"])}</td><td>{yen(round(y["avg"]))}</td><td>{up}</td>'
                 f'<td>{yen(y["max"])}({esc(y["max_name"])})</td><td>{yen(y["min"])}({esc(y["min_name"])})</td></tr>')
        prev = y["avg"]
    first, last = ys[0], ys[-1]
    body = f"""{crumbs([("全国", "/"), ("全国の推移", None)])}
<h1>最低賃金の推移 {esc(first['label'])}〜{esc(last['label'])}</h1>
<p class="lead">全国加重平均は、{esc(first['label'])}の{yen(round(first['avg']))}から、{esc(last['label'])}の{yen(round(last['avg']))}になりました。年度ごとの全国加重平均と、最高額・最低額の推移です。</p>
<h2>全国加重平均の推移</h2>
{chart}
<h2>年度別の一覧</h2>
<div class="tablewrap"><table><thead><tr><th>年度</th><th>全国加重平均</th><th>前年度から</th><th>最高額</th><th>最低額</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。出典の表にある各年度の額をもとに、このサイトで並べ替えました。グラフの縦軸は0から始まっていません。</p>"""
    return finish(layout(cfg, preview, path="/history/", title=f"最低賃金の推移 全国加重平均の年度別一覧({first['label']}〜{last['label']})",
                         description=f"{first['label']}から{last['label']}までの全国加重平均の最低賃金の推移を、グラフと年度別の表でまとめます。最高額・最低額も掲載。", body=body), d)


def guide_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    cards = "".join(guide_card(g) for g in content.GUIDES)
    body = f"""{crumbs([("全国", "/"), ("最低賃金のきほん", None)])}
<h1>最低賃金のきほん</h1>
<p class="lead">仕組み、決まり方、計算の方法、下回っていたときの扱いを、厚生労働省の公表情報と最低賃金法にもとづいて説明します。</p>
<div class="guide-grid">{cards}</div>"""
    return finish(layout(cfg, preview, path="/guide/", title="最低賃金のきほん 仕組み・決まり方・計算方法",
                         description="最低賃金の仕組み、決まり方、時給への換算方法、下回っていたときの扱いを、公的な情報にもとづいて説明します。", body=body), d)


def guide_page(d: dict, g: dict, cfg: dict, preview: bool) -> str:
    sources = "".join(f'<li><a href="{esc(u)}" rel="noopener" target="_blank">{esc(n)}</a></li>' for n, u in g["sources"])
    others = "".join(f'<li><a href="/guide/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in content.GUIDES if x is not g)
    extra = ""
    if g["slug"] == "calculate":
        data = json.dumps(
            [{"name": r["name"], "amount": r["amount"], "prev": r["prev_amount"], "date": r["effective_date"]} for r in d["rows"]],
            ensure_ascii=False,
        ).replace("<", "\\u003c")
        extra = f'<script type="application/json" id="data">{data}</script>'
    body = f"""{crumbs([("全国", "/"), ("最低賃金のきほん", "/guide/"), (g["title"], None)])}
<h1>{esc(g['title'])}</h1>
<p class="lead">{esc(g['lead'])}</p>
<img class="page-banner guide" src="/assets/img/guide-{g['slug']}.webp" alt="" width="800" height="450">
<article class="prose">{g['body']}</article>
<h2>出典</h2>
<ul class="link-list">{sources}</ul>
<p class="notice">内容の確認日: {jp_date(content.VERIFIED_AT)}。制度は改正されることがあります。最新の内容は、出典でご確認ください。</p>
<h2>ほかの解説</h2>
<ul class="link-list">{others}</ul>
{extra}"""
    return finish(layout(cfg, preview, path=f"/guide/{g['slug']}/", title=f"{g['title']} | {cfg['site_name']}",
                         description=g["description"], body=body), d)


def contact_summary(cfg: dict) -> str:
    """How to reach the operator, in the order of preference: the form, then the address (if one is published)."""
    parts = []
    if cfg.get("contact_form_url"):
        parts.append('<a href="/contact/">お問い合わせフォーム</a>')
    if cfg.get("contact_email"):
        parts.append(esc(cfg["contact_email"]))
    return " / ".join(parts) or "(未設定)"


def about_page(d: dict, cfg: dict, preview: bool) -> str:
    op = esc(cfg["operator_name"] or "(未設定)")
    body = f"""<h1>運営者情報</h1>
<dl class="info">
<dt>サイト名</dt><dd>{esc(cfg['site_name'])}</dd>
<dt>運営者</dt><dd>{op}</dd>
<dt>連絡先</dt><dd>{contact_summary(cfg)}</dd>
<dt>目的</dt><dd>最低賃金の改定内容を、働く方・雇う方が確認しやすい形で整理してお伝えすること。</dd>
<dt>情報の出典</dt><dd>{esc(SOURCE_LABEL)}(<a href="{{source}}" rel="noopener" target="_blank">公表ページ</a>)、厚生労働省の最低賃金制度の特設サイト、最低賃金法</dd>
<dt>更新</dt><dd>厚生労働省の公表データをもとに作成し、内容を更新したときは、各ページに表示するデータの取得日も更新します。</dd>
</dl>
<h2>免責事項</h2>
<p>掲載内容は、正確を期して作成していますが、その正確性・完全性・最新性を保証するものではありません。実際に適用される最低賃金は、都道府県労働局・厚生労働省の発表をご確認ください。当サイトの情報を利用して生じた損害について、運営者は責任を負いません。</p>
<p>このサイトは、厚生労働省が公表している情報を加工して作成したもので、厚生労働省が作成したものではありません。</p>"""
    return finish(layout(cfg, preview, path="/about/", title=f"運営者情報 | {cfg['site_name']}",
                         description="最低賃金速報の運営者情報、情報の出典、免責事項です。", body=body, scripts=False), d)


def privacy_page(d: dict, cfg: dict, preview: bool) -> str:
    body = f"""<h1>プライバシーポリシー</h1>
<h2>取得する情報</h2>
<p>当サイトは、会員登録などの機能を持ちません。お問い合わせの際にいただいたお名前・メールアドレスなどは、返信のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。</p>
<h2>入力された内容について</h2>
<p>「あなたの時給は大丈夫?」や計算ツールに入力された都道府県・時給・月給などは、お使いの端末の中で計算するだけで、当サイトのサーバーへは送信・保存しません。</p>
<h2>アクセス解析</h2>
<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>
<h2>広告について</h2>
<p>当サイトは、第三者配信の広告サービス「Google AdSense」を利用する場合があります。広告配信事業者は、利用者の興味に応じた広告を表示するために、Cookie(クッキー)を使用することがあります。</p>
<p>Cookie を無効にする、または、パーソナライズ広告を無効にするには、<a href="https://adssettings.google.com/" rel="noopener" target="_blank">Google の広告設定</a>をご利用ください。第三者配信事業者による Cookie の使用については、<a href="https://www.aboutads.info/" rel="noopener" target="_blank">aboutads.info</a> でも無効にできます。詳しくは、<a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">Google のポリシーと規約</a>をご覧ください。</p>
<p>広告の配信にあたり、お使いのブラウザから広告配信事業者へ、閲覧に関する情報が送信されることがあります。</p>
<h2>免責事項・著作権</h2>
<p>免責事項と情報の出典は、<a href="/about/">運営者情報</a>に記載しています。</p>
<h2>お問い合わせ</h2>
<p>このポリシーに関するお問い合わせは、{contact_summary(cfg)}からお願いします。</p>
<h2>改定</h2>
<p>このポリシーは、必要に応じて見直し、変更する場合があります。変更後の内容は、このページに掲載した時点から効力を持ちます。</p>"""
    return finish(layout(cfg, preview, path="/privacy/", title=f"プライバシーポリシー | {cfg['site_name']}",
                         description="最低賃金速報のプライバシーポリシーです。取得する情報、広告、Cookie の扱いについて説明します。",
                         body=body, scripts=False), d)


def contact_page(d: dict, cfg: dict, preview: bool) -> str:
    form, mail = cfg.get("contact_form_url"), cfg.get("contact_email")
    links = []
    if form:
        links.append(f'<p><a class="btn" href="{esc(form)}" rel="noopener" target="_blank">お問い合わせフォームを開く</a></p>')
    if mail:
        links.append(f'<p>メール: <a href="mailto:{esc(mail)}">{esc(mail)}</a></p>')
    link = "\n".join(links) or "<p>(未設定)</p>"
    body = f"""<h1>お問い合わせ</h1>
<p>データの誤りのご指摘、ご意見・ご要望は、次からお送りください。内容によっては、お返事に日数がかかることや、お返事できないことがあります。</p>
{link}
<p class="notice">個別の労働条件や、賃金に関する法律相談にはお答えできません。お近くの都道府県労働局や労働基準監督署へご相談ください。</p>"""
    return finish(layout(cfg, preview, path="/contact/", title=f"お問い合わせ | {cfg['site_name']}",
                         description="最低賃金速報へのお問い合わせ先です。データの誤りのご指摘、ご意見・ご要望を、フォームで受け付けています。", body=body, scripts=False), d)


def not_found_page(d: dict, cfg: dict, preview: bool) -> str:
    body = '<h1>ページが見つかりません</h1>\n<p><a href="/">全国の最低賃金の一覧へ</a></p>'
    return finish(layout(cfg, preview, path="/404.html", title=f"ページが見つかりません | {cfg['site_name']}",
                         description="ページが見つかりません。", body=body, scripts=False), d)


def feed_xml(d: dict, cfg: dict) -> str:
    """Atom feed: one entry per prefecture whose new minimum wage has already taken effect (dated by its effective date)."""
    base = cfg["site_url"].rstrip("/")
    host = urlparse(base).hostname or "localhost"
    done = sorted((r for r in d["rows"] if r["effective_date"] <= d["fetched_date"]),
                  key=lambda r: (r["effective_date"], r["name"]), reverse=True)
    entries = "".join(
        f"<entry><id>tag:{host},{d['fy']}:minwage-{r['slug']}</id>"
        f"<title>{esc(r['name'])}の最低賃金が{esc(yen(r['amount']))}になりました(+{r['raise']}円)</title>"
        f'<link href="{esc(base)}/{r["slug"]}/"/>'
        f"<updated>{r['effective_date']}T00:00:00+09:00</updated>"
        f"<summary>{esc(d['label'])}の最低賃金は、{esc(yen(r['prev_amount']))}から{esc(yen(r['amount']))}(+{r['raise']}円)に"
        f"改定され、{esc(jp_date(r['effective_date']))}に発効しました。</summary></entry>\n"
        for r in done
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja">\n'
        f"<id>tag:{host},{d['fy']}:minwage</id><title>{esc(cfg['site_name'])} 発効のお知らせ</title>"
        f'<link href="{esc(base)}/feed.xml" rel="self"/><link href="{esc(base)}/"/>'
        f"<updated>{d['fetched_date']}T00:00:00+09:00</updated>\n{entries}</feed>\n"
    )


def dates_feed_xml(d: dict, cfg: dict) -> str:
    """Atom feed with one entry per effective date that has already passed (what the social posts are made from)."""
    base = cfg["site_url"].rstrip("/")
    host = urlparse(base).hostname or "localhost"
    days: dict[str, list[dict]] = {}
    for r in d["rows"]:
        if r["effective_date"] <= d["fetched_date"]:
            days.setdefault(r["effective_date"], []).append(r)
    entries = ""
    for iso in sorted(days, reverse=True):
        rows = sorted(days[iso], key=lambda r: (-r["amount"], r["name"]))
        _, m, dd = (int(x) for x in iso.split("-"))
        listing = "、".join(f"{r['name']} {yen(r['amount'])}" for r in rows)
        entries += (
            f"<entry><id>tag:{host},{d['fy']}:minwage-date-{iso}</id>"
            f"<title>{m}月{dd}日、{len(rows)}都道府県で最低賃金の新しい額が発効しました</title>"
            f'<link href="{esc(base)}/calendar/#d-{iso}"/><updated>{iso}T00:00:00+09:00</updated>'
            f"<summary>{esc(listing)}</summary></entry>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja">\n'
        f"<id>tag:{host},{d['fy']}:minwage-dates</id><title>{esc(cfg['site_name'])} 発効日ごとのお知らせ</title>"
        f'<link href="{esc(base)}/feed/dates.xml" rel="self"/><link href="{esc(base)}/calendar/"/>'
        f"<updated>{d['fetched_date']}T00:00:00+09:00</updated>\n{entries}</feed>\n"
    )


def ics_escape(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line: str) -> str:
    """RFC 5545 line folding: at most 75 octets per line, never splitting a multi-byte character."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not out else 74):
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return "\r\n ".join(out)


def ics_calendar(d: dict, cfg: dict, name: str, events: list[dict]) -> str:
    """A subscribable calendar of all-day events, each with a reminder at 9:00 the day before."""
    base = cfg["site_url"].rstrip("/")
    host = urlparse(base).hostname or "localhost"
    # The full fetch time (UTC): a correction made on the same day still looks newer to calendar apps.
    stamp = datetime.fromisoformat(d["fetched_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{host}//minwage//JA", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{ics_escape(name)}", "X-WR-TIMEZONE:Asia/Tokyo"]
    for ev in events:
        start = date.fromisoformat(ev["date"])
        lines += [
            "BEGIN:VEVENT", f"UID:{ev['uid']}@{host}", f"DTSTAMP:{stamp}", f"LAST-MODIFIED:{stamp}",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{ics_escape(ev['summary'])}", f"DESCRIPTION:{ics_escape(ev['description'])}",
            f"URL:{ev['url']}", "TRANSP:TRANSPARENT",
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_escape(ev['summary'])}", "TRIGGER:-PT15H", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(x) for x in lines) + "\r\n"


def ics_files(d: dict, cfg: dict) -> dict[str, str]:
    """calendar/<slug>.ics for each prefecture, and calendar/all.ics with one event per effective date."""
    base = cfg["site_url"].rstrip("/")
    files: dict[str, str] = {}
    for r in d["rows"]:
        files[f"calendar/{r['slug']}.ics"] = ics_calendar(d, cfg, f"{r['name']}の最低賃金", [{
            "uid": f"minwage-{d['fy']}-{r['slug']}", "date": r["effective_date"],
            "summary": f"{r['name']}の最低賃金が{yen(r['amount'])}に(発効日)",
            "description": f"{d['label']}の{r['name']}の最低賃金は、{yen(r['prev_amount'])}から{yen(r['amount'])}(+{r['raise']}円)に改定されます。",
            "url": f"{base}/{r['slug']}/"}])
    days: dict[str, list[dict]] = {}
    for r in d["rows"]:
        days.setdefault(r["effective_date"], []).append(r)
    events = []
    for iso in sorted(days):
        rows = sorted(days[iso], key=lambda r: (-r["amount"], r["name"]))
        events.append({
            "uid": f"minwage-{d['fy']}-date-{iso}", "date": iso,
            "summary": f"{len(rows)}都道府県で最低賃金の新しい額が発効",
            "description": "、".join(f"{r['name']} {yen(r['amount'])}" for r in rows),
            "url": f"{base}/calendar/#d-{iso}"})
    files["calendar/all.ics"] = ics_calendar(d, cfg, f"{cfg['site_name']} 発効日", events)
    return files


def notify_page(d: dict, cfg: dict, preview: bool) -> str:
    base = cfg["site_url"].rstrip("/")
    host = urlparse(base).hostname or "localhost"
    rows = "".join(
        f'<li><a href="/{r["slug"]}/">{esc(r["name"])}</a>'
        f'<span><a href="/calendar/{r["slug"]}.ics">カレンダー(.ics)</a></span></li>' for r in d["rows"])
    social = ""
    if cfg.get("bluesky_handle"):
        social += f'<li><a href="https://bsky.app/profile/{esc(cfg["bluesky_handle"])}" rel="noopener" target="_blank">Bluesky(@{esc(cfg["bluesky_handle"])})</a>をフォローすると、発効日ごとのお知らせが届きます。</li>'
    if cfg.get("x_handle"):
        social += f'<li><a href="https://x.com/{esc(cfg["x_handle"])}" rel="noopener" target="_blank">X(@{esc(cfg["x_handle"])})</a>でも、同じお知らせを載せます。</li>'
    body = f"""{crumbs([("全国", "/"), ("通知を受け取る", None)])}
<h1>最低賃金の更新を、通知で受け取る</h1>
<p class="lead">サイトを開かなくても、新しい最低賃金の発効日や更新が届くようにできます。登録は不要で、メールアドレスなどの個人情報も預かりません。</p>
<h2>1. 発効日をカレンダーに入れる</h2>
<p>お住まいの都道府県の発効日が、カレンダーアプリの予定として入ります。前日の朝9時に通知が出ます。Google カレンダーや iPhone の「カレンダー」などで、このページのファイルを購読(URL で追加)してください。下の一覧の「カレンダー(.ics)」を、ファイルとして開く方法もあります。</p>
<p><a href="https://calendar.google.com/calendar/r?cid=webcal://{esc(host)}/calendar/all.ics">全国の発効日を、Google カレンダーに追加</a>(発効日ごとに1件の予定になります)</p>
<ul class="mini-list notify-list">{rows}</ul>
<h2>2. フィード(RSS)で受け取る</h2>
<ul class="link-list">
<li><a href="/feed/dates.xml">発効日ごとのお知らせ(フィード)</a>: 日付ごとに、発効した都道府県と新しい額をまとめます。</li>
<li><a href="/feed.xml">都道府県ごとのお知らせ(フィード)</a>: 発効した県ごとに1件ずつ載ります。</li>
</ul>
<p>フィードリーダーに、上のアドレスを登録してください。</p>
{"<h2>3. SNS で受け取る</h2><ul class='link-list'>" + social + "</ul>" if social else ""}
<p class="notice">カレンダーとフィードは、このサイトのデータから自動で作っています。発効日などは、厚生労働省の公表をもとにしています。内容が変わったときは、次の更新で自動的に反映されます。</p>"""
    return finish(layout(cfg, preview, path="/notify/", title=f"最低賃金の更新を通知で受け取る方法 | {cfg['site_name']}",
                         description="新しい最低賃金の発効日を、カレンダーやフィード(RSS)で受け取る方法です。登録や個人情報は不要です。", body=body, scripts=False), d)


def og_cards(d: dict) -> dict[str, bytes]:
    """Share cards: one default plus one per prefecture."""
    cards = {"og/default.png": ogimage.card(
        title=f"{d['label']} 最低賃金 改定速報", big=f"{round(d['avg']):,}円",
        sub=f"全国加重平均  昨年度から +{round(d['avg'] - d['avg_prev'])}円", foot="全国47都道府県の新額と発効日  |  saichin-sokuho.com")}
    for r in d["rows"]:
        cards[f"og/{r['slug']}.png"] = ogimage.card(
            title=f"{r['name']}の最低賃金({d['label']})", big=yen(r["amount"]),
            sub=f"+{r['raise']}円  /  {jp_date(r['effective_date'])} 発効", foot=f"全国{r['rank']}位  |  saichin-sokuho.com")
    return cards


# ---------------------------------------------------------------- site

def render_site(raw: dict, cfg: dict, out: Path, release: bool = False, wage: dict | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    d = prepare(raw)
    if wage:
        try:
            d["wage"] = wagelib.view(wage, d)
        except wagelib.WageError as e:
            raise BuildError(f"wage survey does not fit the minimum-wage data: {e}")
    base = cfg["site_url"].rstrip("/")
    use_og = ogimage.available() and not os.environ.get("SOKUHOU_NO_OG")
    cfg = {**cfg, "_og": {"enabled": use_og, "slugs": {r["slug"] for r in d["rows"]}}}

    pages: dict[str, str | bytes] = {"index.html": index_page(d, cfg, preview)}
    for r in d["rows"]:
        pages[f"{r['slug']}/index.html"] = pref_page(d, r, cfg, preview)
    pages["area/index.html"] = area_hub_page(d, cfg, preview)
    for slug, rname, shorts in REGIONS:
        pages[f"area/{slug}/index.html"] = area_page(d, slug, rname, shorts, cfg, preview)
    for kind in RANKINGS:
        pages[f"ranking/{kind}/index.html"] = ranking_page(d, kind, cfg, preview)
    if d.get("wage"):
        for kind in WAGE_RANKINGS:
            pages[f"ranking/{kind}/index.html"] = wage_ranking_page(d, kind, cfg, preview)
    pages["calendar/index.html"] = calendar_page(d, cfg, preview)
    pages["history/index.html"] = history_page(d, cfg, preview)
    pages["notify/index.html"] = notify_page(d, cfg, preview)
    pages["guide/index.html"] = guide_hub_page(d, cfg, preview)
    for g in content.GUIDES:
        pages[f"guide/{g['slug']}/index.html"] = guide_page(d, g, cfg, preview)
    pages["about/index.html"] = about_page(d, cfg, preview)
    pages["privacy/index.html"] = privacy_page(d, cfg, preview)
    pages["contact/index.html"] = contact_page(d, cfg, preview)
    pages["404.html"] = not_found_page(d, cfg, preview)

    urls = ["/" + p[: -len("index.html")] for p in pages if p.endswith("index.html")]
    urls = sorted(set(urls), key=lambda u: (u != "/", u))
    pages["sitemap.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{d['fetched_date']}</lastmod></url>\n" for u in urls)
        + "</urlset>\n"
    )
    pages["robots.txt"] = (
        "User-agent: *\nDisallow: /\n" if preview else f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    )
    if cfg.get("adsense_pub_id"):
        pub = cfg["adsense_pub_id"].replace("ca-", "")
        pages["ads.txt"] = f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n"
    pages["feed.xml"] = feed_xml(d, cfg)
    pages["feed/dates.xml"] = dates_feed_xml(d, cfg)
    pages.update(ics_files(d, cfg))
    if use_og:
        pages.update(og_cards(d))
    pages[".htaccess"] = HTACCESS
    verification = cfg.get("google_site_verification")
    if verification:
        if not re.fullmatch(r"google[0-9a-f]{16}\.html", verification):
            raise BuildError(f"google_site_verification must look like google<16 hex>.html, got {verification!r}")
        pages[verification] = f"google-site-verification: {verification}\n"
    pages.update(asset_pages(HERE / "assets"))

    # Overwrite in place and delete only stale files. Removing the whole folder fails on Windows when
    # Dropbox or the indexer briefly holds a directory open.
    for rel, text in pages.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8", newline="\n")
    if out.exists():
        for f in out.rglob("*"):
            if f.is_file() and f.relative_to(out).as_posix() not in pages:
                f.unlink()
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true", help="refuse to build while operator info is missing")
    ap.add_argument("--out", default=str(HERE / "dist"))
    args = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        wage_file = HERE.parents[1] / "data" / "estat_wage.json"
        wage = json.loads(wage_file.read_text(encoding="utf-8")) if wage_file.exists() else None
        files = render_site(mhlw_minwage.collect(), cfg, Path(args.out), release=args.release, wage=wage)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {args.out}")


if __name__ == "__main__":
    main()
