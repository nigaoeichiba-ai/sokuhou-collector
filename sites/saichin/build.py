"""Static site generator for the minimum-wage site.

Every page is complete HTML (no script needed to read it); app.js only adds sorting, live status and a checker.
Preview builds are marked noindex. A release build refuses to run while operator info is missing.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))  # repo root, so `python sites/saichin/build.py` finds `sokuhou`

from sokuhou.sources import mhlw_minwage  # noqa: E402

SLUGS = dict(zip(
    mhlw_minwage.PREFECTURES,
    "hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa "
    "niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama "
    "tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita "
    "miyazaki kagoshima okinawa".split(),
))
SUFFIX = {"北海道": "", "東京": "都", "大阪": "府", "京都": "府"}
REQUIRED_FOR_RELEASE = ("operator_name", "contact_email")
SOURCE_LABEL = "厚生労働省「地域別最低賃金の全国一覧」"
WEEKLY_HOURS, WEEKS_PER_YEAR = 40, 52


class BuildError(Exception):
    pass


esc = html.escape
yen = lambda n: f"{n:,}円"  # noqa: E731


def jp_date(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def monthly_estimate(hourly: int) -> int:
    """Hourly wage x 40h x 52 weeks / 12 months, rounded to 100 yen."""
    return round(hourly * WEEKLY_HOURS * WEEKS_PER_YEAR / 12 / 100) * 100


# ---------------------------------------------------------------- data

def prepare(raw: dict) -> dict:
    fy = raw["latest_fiscal_year"]
    labels = raw["fiscal_year_labels"]
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
                history.append({
                    "label": labels[str(y)], "amount": cur["amount"], "effective_date": cur["effective_date"],
                    "raise": cur["amount"] - before["amount"] if before else None,
                })
        rows.append({
            "short": p["name"], "name": p["name"] + SUFFIX.get(p["name"], "県"), "slug": SLUGS[p["name"]],
            "amount": new["amount"], "prev_amount": prev["amount"], "raise": new["amount"] - prev["amount"],
            "effective_date": eff, "history": history,
        })
    ranked = sorted((r["amount"] for r in rows), reverse=True)
    for r in rows:
        r["rank"] = ranked.index(r["amount"]) + 1
    avg = raw["national_weighted_average"]
    return {
        "fy": fy, "label": labels[str(fy)], "rows": rows,
        "avg": avg[str(fy)], "avg_prev": avg[str(fy - 1)],
        "source_page": raw["source_page"], "fetched_date": raw["fetched_at"][:10],
    }


# ---------------------------------------------------------------- layout

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
    script = '<script src="/assets/app.js" defer></script>\n' if scripts else ""
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
<link rel="stylesheet" href="/assets/style.css">
{adsense}</head>
<body>
{banner}<header class="site"><div class="wrap">
<a class="brand" href="/">{name}</a>
<nav><a href="/">全国一覧</a><a href="/about/">運営者情報</a><a href="/privacy/">プライバシーポリシー</a><a href="/contact/">お問い合わせ</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p>出典: <a href="{{source}}" rel="noopener" target="_blank">{SOURCE_LABEL}</a>を加工して作成。厚生労働省が作成したものではありません。</p>
<p>このサイトは「地域別最低賃金」を扱います。業種ごとの最低賃金(特定最低賃金など)は含みません。実際に適用される額は、都道府県労働局・厚生労働省の発表でご確認ください。</p>
<p>&copy; {name}</p>
</div></footer>
{script}</body>
</html>
"""


def finish(page: str, d: dict) -> str:
    return page.replace("{source}", esc(d["source_page"]))


# ---------------------------------------------------------------- pages

def index_page(d: dict, cfg: dict, preview: bool) -> str:
    rows = d["rows"]
    hi = max(rows, key=lambda r: r["amount"])
    lo = min(rows, key=lambda r: r["amount"])
    stats = [
        ("全国加重平均", yen(round(d["avg"])), f"昨年度 {yen(round(d['avg_prev']))}(+{round(d['avg'] - d['avg_prev'])}円)"),
        ("最も高い", yen(hi["amount"]), hi["name"]),
        ("最も低い", yen(lo["amount"]), lo["name"]),
        ("発効日の範囲", f"{jp_date(min(r['effective_date'] for r in rows))} 〜 {jp_date(max(r['effective_date'] for r in rows))}", "都道府県ごとに異なります"),
    ]
    stats_html = "".join(f'<div class="stat"><span>{esc(a)}</span><b>{esc(b)}</b><span>{esc(c)}</span></div>' for a, b, c in stats)
    trs = "".join(
        f'<tr data-name="{esc(r["name"])}" data-amount="{r["amount"]}" data-prev="{r["prev_amount"]}" '
        f'data-raise="{r["raise"]}" data-date="{r["effective_date"]}">'
        f'<td><a href="/{r["slug"]}/">{esc(r["name"])}</a></td><td>{yen(r["amount"])}</td><td>{yen(r["prev_amount"])}</td>'
        f'<td>+{r["raise"]}円</td><td>{jp_date(r["effective_date"])}</td><td class="state" data-date="{r["effective_date"]}"></td></tr>'
        for r in sorted(rows, key=lambda r: (r["effective_date"], r["name"]))
    )
    options = "".join(f'<option value="{esc(r["name"])}">{esc(r["name"])}</option>' for r in rows)
    data = json.dumps(
        [{"name": r["name"], "amount": r["amount"], "prev": r["prev_amount"], "date": r["effective_date"]} for r in rows],
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    body = f"""<h1>{esc(d['label'])} 最低賃金の改定速報</h1>
<p class="lead">都道府県別の最低賃金(時給)の新しい額と、発効日の一覧です。都道府県名を押すと、過去の推移などを見られます。</p>
<div class="stats">{stats_html}</div>

<h2>あなたの時給は大丈夫?</h2>
<div class="box js-only" hidden>
<div class="controls"><select id="pref" aria-label="都道府県"><option value="">都道府県を選ぶ</option>{options}</select>
<input id="wage" type="number" inputmode="numeric" min="0" step="1" placeholder="時給(円)" aria-label="時給(円)"></div>
<p class="result" id="check">都道府県と時給を入れると、現在の最低賃金と比べます。</p>
</div>
<noscript><p class="notice">この機能にはJavaScriptが必要です。下の一覧で、お住まいの都道府県の額をご確認ください。</p></noscript>

<h2>都道府県別の一覧</h2>
<div class="controls js-only" hidden>
<input id="q" type="search" placeholder="都道府県で絞り込み" aria-label="都道府県で絞り込み">
<select id="status" aria-label="状態"><option value="">すべて</option><option value="done">発効済み</option><option value="soon">これから発効</option></select>
</div>
<div class="tablewrap"><table id="wage-table">
<thead><tr><th data-key="name">都道府県</th><th data-key="amount">新しい最低賃金</th><th data-key="prev">昨年度</th><th data-key="raise">引上げ額</th><th data-key="date">発効日</th><th data-key="state">状態</th></tr></thead>
<tbody>{trs}</tbody></table></div>
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
        f'<td>{jp_date(h["effective_date"]) if h["effective_date"] else "-"}</td></tr>'
        for h in reversed(r["history"])
    )
    nav = "".join(f'<li><a href="/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in d["rows"] if x is not r)
    body = f"""<h1>{esc(r['name'])}の最低賃金({esc(d['label'])}) {yen(r['amount'])}</h1>
<p class="lead">{esc(d['label'])}の最低賃金は、{yen(r['prev_amount'])}から{yen(r['amount'])}(+{r['raise']}円)に改定され、発効日は{jp_date(r['effective_date'])}です。</p>
<p class="status" data-status data-date="{r['effective_date']}" data-amount="{r['amount']}" data-prev="{r['prev_amount']}"></p>
<div class="stats">
<div class="stat"><span>新しい最低賃金</span><b>{yen(r['amount'])}</b><span>{jp_date(r['effective_date'])} 発効</span></div>
<div class="stat"><span>昨年度</span><b>{yen(r['prev_amount'])}</b><span>引上げ額 +{r['raise']}円</span></div>
<div class="stat"><span>全国での順位</span><b>47都道府県中 {r['rank']}位</b><span>同額は同じ順位とします</span></div>
</div>
<h2>全国と比べると</h2>
<p>{esc(r['name'])}の{esc(d['label'])}の最低賃金は{yen(r['amount'])}で、{diff_text}(全国加重平均 {yen(round(d['avg']))})。</p>
<h2>月給にすると(目安)</h2>
<p>週{WEEKLY_HOURS}時間・年{WEEKS_PER_YEAR}週で働くと、1か月あたり約{WEEKLY_HOURS * WEEKS_PER_YEAR / 12:.1f}時間です。最低賃金で働いた場合の月給の目安は、改定前が約{yen(monthly_estimate(r['prev_amount']))}、改定後が約{yen(monthly_estimate(r['amount']))}です。実際の月給は、勤務時間・手当・控除などで変わります。</p>
<h2>過去の推移</h2>
<div class="tablewrap"><table><thead><tr><th>年度</th><th>最低賃金</th><th>前年度からの引上げ</th><th>発効日</th></tr></thead><tbody>{hist}</tbody></table></div>
<h2>ほかの都道府県</h2>
<p><a href="/">全国の一覧に戻る</a></p>
<ul class="pref-nav">{nav}</ul>
<p class="notice">データの取得日: {jp_date(d['fetched_date'])}。{esc(SOURCE_LABEL)}をもとに作成しています。</p>"""
    return finish(layout(
        cfg, preview, path=f"/{r['slug']}/",
        title=f"{r['name']}の最低賃金は{yen(r['amount'])}({d['label']}) 発効日と過去の推移",
        description=f"{r['name']}の{d['label']}の最低賃金は{yen(r['amount'])}(+{r['raise']}円)。発効日は{jp_date(r['effective_date'])}。過去の推移と月給の目安も掲載しています。",
        body=body,
    ), d)


def about_page(d: dict, cfg: dict, preview: bool) -> str:
    op = esc(cfg["operator_name"] or "(未設定)")
    mail = esc(cfg["contact_email"] or "(未設定)")
    body = f"""<h1>運営者情報</h1>
<dl class="info">
<dt>サイト名</dt><dd>{esc(cfg['site_name'])}</dd>
<dt>運営者</dt><dd>{op}</dd>
<dt>連絡先</dt><dd>{mail}</dd>
<dt>目的</dt><dd>最低賃金の改定内容を、働く方・雇う方が確認しやすい形で整理してお伝えすること。</dd>
<dt>情報の出典</dt><dd>{esc(SOURCE_LABEL)}(<a href="{{source}}" rel="noopener" target="_blank">公表ページ</a>)</dd>
<dt>更新</dt><dd>公表データを定期的に取得して更新します。各ページに、データの取得日を表示しています。</dd>
</dl>
<h2>免責事項</h2>
<p>掲載内容は、正確を期して作成していますが、その正確性・完全性・最新性を保証するものではありません。実際に適用される最低賃金は、都道府県労働局・厚生労働省の発表をご確認ください。当サイトの情報を利用して生じた損害について、運営者は責任を負いません。</p>
<p>このサイトは、厚生労働省が公表している情報を加工して作成したもので、厚生労働省が作成したものではありません。</p>"""
    return finish(layout(cfg, preview, path="/about/", title=f"運営者情報 | {cfg['site_name']}",
                         description="最低賃金速報の運営者情報、情報の出典、免責事項です。", body=body, scripts=False), d)


def privacy_page(d: dict, cfg: dict, preview: bool) -> str:
    mail = esc(cfg["contact_email"] or "(未設定)")
    body = f"""<h1>プライバシーポリシー</h1>
<h2>取得する情報</h2>
<p>当サイトは、会員登録などの機能を持ちません。お問い合わせの際にいただいたお名前・メールアドレスなどは、返信のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。</p>
<h2>入力された内容について</h2>
<p>「あなたの時給は大丈夫?」に入力された都道府県と時給は、お使いの端末の中で計算するだけで、当サイトのサーバーへは送信・保存しません。</p>
<h2>アクセス解析</h2>
<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>
<h2>広告について</h2>
<p>当サイトは、第三者配信の広告サービス「Google AdSense」を利用する場合があります。広告配信事業者は、利用者の興味に応じた広告を表示するために、Cookie(クッキー)を使用することがあります。</p>
<p>Cookie を無効にする、または、パーソナライズ広告を無効にするには、<a href="https://adssettings.google.com/" rel="noopener" target="_blank">Google の広告設定</a>をご利用ください。第三者配信事業者による Cookie の使用については、<a href="https://www.aboutads.info/" rel="noopener" target="_blank">aboutads.info</a> でも無効にできます。詳しくは、<a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">Google のポリシーと規約</a>をご覧ください。</p>
<p>広告の配信にあたり、お使いのブラウザから広告配信事業者へ、閲覧に関する情報が送信されることがあります。</p>
<h2>免責事項・著作権</h2>
<p>免責事項と情報の出典は、<a href="/about/">運営者情報</a>に記載しています。</p>
<h2>お問い合わせ</h2>
<p>このポリシーに関するお問い合わせは、{mail}までお願いします。</p>
<h2>改定</h2>
<p>このポリシーは、必要に応じて見直し、変更する場合があります。変更後の内容は、このページに掲載した時点から効力を持ちます。</p>"""
    return finish(layout(cfg, preview, path="/privacy/", title=f"プライバシーポリシー | {cfg['site_name']}",
                         description="最低賃金速報のプライバシーポリシーです。取得する情報、広告、Cookie の扱いについて説明します。",
                         body=body, scripts=False), d)


def contact_page(d: dict, cfg: dict, preview: bool) -> str:
    mail = cfg["contact_email"]
    link = f'<a href="mailto:{esc(mail)}">{esc(mail)}</a>' if mail else "(未設定)"
    body = f"""<h1>お問い合わせ</h1>
<p>データの誤りのご指摘、ご意見・ご要望は、次のメールアドレスへお送りください。内容によっては、お返事に日数がかかることや、お返事できないことがあります。</p>
<p>{link}</p>
<p class="notice">個別の労働条件や、賃金に関する法律相談にはお答えできません。お近くの都道府県労働局や労働基準監督署へご相談ください。</p>"""
    return finish(layout(cfg, preview, path="/contact/", title=f"お問い合わせ | {cfg['site_name']}",
                         description="最低賃金速報へのお問い合わせ先です。", body=body, scripts=False), d)


def not_found_page(d: dict, cfg: dict, preview: bool) -> str:
    body = '<h1>ページが見つかりません</h1>\n<p><a href="/">全国の最低賃金の一覧へ</a></p>'
    return finish(layout(cfg, preview, path="/404.html", title=f"ページが見つかりません | {cfg['site_name']}",
                         description="ページが見つかりません。", body=body, scripts=False), d)


# ---------------------------------------------------------------- site

def render_site(raw: dict, cfg: dict, out: Path, release: bool = False) -> list[str]:
    missing = [k for k in REQUIRED_FOR_RELEASE if not cfg.get(k)]
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    d = prepare(raw)
    base = cfg["site_url"].rstrip("/")

    if out.exists():
        shutil.rmtree(out)
    pages: dict[str, str] = {"index.html": index_page(d, cfg, preview)}
    for r in d["rows"]:
        pages[f"{r['slug']}/index.html"] = pref_page(d, r, cfg, preview)
    pages["about/index.html"] = about_page(d, cfg, preview)
    pages["privacy/index.html"] = privacy_page(d, cfg, preview)
    pages["contact/index.html"] = contact_page(d, cfg, preview)
    pages["404.html"] = not_found_page(d, cfg, preview)

    urls = ["/"] + [f"/{r['slug']}/" for r in d["rows"]] + ["/about/", "/privacy/", "/contact/"]
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

    for rel, content in pages.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
    shutil.copytree(HERE / "assets", out / "assets")
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true", help="refuse to build while operator info is missing")
    ap.add_argument("--out", default=str(HERE / "dist"))
    args = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        files = render_site(mhlw_minwage.collect(), cfg, Path(args.out), release=args.release)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {args.out}")


if __name__ == "__main__":
    main()
