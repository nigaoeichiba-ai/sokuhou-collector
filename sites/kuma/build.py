"""クマ出没速報 (kuma-sokuho.com): a static site built from data/env_kuma.json (Ministry of the Environment).

    python sites/kuma/build.py [--release] [--out DIR]

Every number and every sentence about numbers is generated from the data, so a page cannot disagree with the table
it comes from.  The ministry's own cautions (provisional values; each prefecture counts sightings differently; which
months are in) are printed on every page that shows a comparison.
"""
from __future__ import annotations

import argparse
from urllib.parse import quote
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.kuma import charts, content, digest  # noqa: E402
from sites.kuma import captures as captures_mod  # noqa: E402
from sites.kuma import cite as cite_mod  # noqa: E402
from sites.kuma import live as live_mod  # noqa: E402
from sites.kuma.fmt import day_text, fy_label, fy_start, jp_date, md, n, ratio_text, table  # noqa: E402
from sokuhou import prefectures as pf  # noqa: E402
from sokuhou.sitekit import BuildError, amazon_disclosure, asset_pages, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

JST = timezone(timedelta(hours=9))
MINISTRY_PAGE = "https://www.env.go.jp/nature/choju/effort/effort12/effort12.html"
SOURCE_HTML = (f'出典: <a href="{MINISTRY_PAGE}" rel="noopener" target="_blank">環境省「クマに関する各種情報・取組」</a>の公表資料(速報値)を加工して作成。'
               "環境省が作成したものではありません。")
BASE_NAV = [("全国", "/", "/"), ("最新の目撃", "/live/", "/live/"), ("ランキング", "/ranking/sightings/", "/ranking/"),
            ("推移", "/trend/", "/trend/"), ("緊急銃猟", "/emergency/", "/emergency/"), ("お知らせ", "/news/", "/news/"),
            ("対処法", "/guide/", "/guide/")]
SITE = {
    "nav": BASE_NAV,
    "glyph": "&#128059;",
    "assets": HERE / "assets",
    "source_html": SOURCE_HTML,
}
WEEKDAY_SKIP = None
CAUTION = ("環境省が都道府県から聞き取った<strong>速報値</strong>で、後から修正されることがあります。"
           "出没数は、<strong>都道府県ごとに異なる方法</strong>で取りまとめられているため、都道府県どうしの数の大小は、そのまま比べられません。")


def rank_of(values: dict) -> dict:
    """1 = largest; ties share a rank; None is left out."""
    have = {k: v for k, v in values.items() if v is not None}
    return {k: 1 + sum(1 for x in have.values() if x > v) for k, v in have.items()}


# ---------------------------------------------------------------- data

def prepare(raw: dict) -> dict:
    s, inj = raw["sightings"], raw["injuries"]
    years = s["years"]
    cur, done = years[-1], years[-2]
    li = s["months"].index(s["latest_month"])
    months = s["months"]
    rows = []
    for p in s["prefectures"]:
        name = p["name"]
        has = any(v is not None for v in p["total"].values())
        i_by = next(x for x in inj["prefectures"] if x["name"] == name)["by_year"]
        row = {
            "short": name, "name": pf.full(name), "slug": pf.SLUG[name], "region": pf.region_of(name)[1],
            "region_slug": pf.region_of(name)[0], "has": has, "monthly": p["monthly"], "total": p["total"],
            "inj": i_by,
            "ytd": {y: (sum(v or 0 for v in p["monthly"][y][: li + 1]) if has else None) for y in years},
        }
        rows.append(row)
    ranks = {
        "done": rank_of({r["short"]: r["total"][done] for r in rows if r["has"]}),
        "ytd": rank_of({r["short"]: r["ytd"][cur] for r in rows if r["has"]}),
        "injured": rank_of({r["short"]: r["inj"][done][1] for r in rows}),
        "injured7": rank_of({r["short"]: sum(r["inj"][y][1] for y in inj["years"] if y.startswith("R0") and y != cur and int(y[1:]) >= 1) for r in rows}),
    }
    base_floor = 30
    ranks["change"] = rank_of({r["short"]: round(r["ytd"][cur] / r["ytd"][done] * 100, 1)
                               for r in rows if r["has"] and r["ytd"][done] >= base_floor})
    for r in rows:
        k = r["short"]
        r["rank"] = {key: ranks[key].get(k) for key in ranks}
        r["injured7"] = sum(r["inj"][y][1] for y in inj["years"] if y.startswith("R0") and y != cur)
    # The national row shows 0 for months that are not published yet; those are "no data", not zero sightings.
    nat = {**s["national"], "monthly": {y: [None if (y == cur and i > li) else v for i, v in enumerate(vals)]
                                        for y, vals in s["national"]["monthly"].items()}}
    nat_ytd = {y: sum(v or 0 for v in nat["monthly"][y][: li + 1]) for y in years}
    peak = max(range(12), key=lambda i: nat["monthly"][done][i] or 0)
    return {
        "raw": raw, "years": years, "cur": cur, "done": done, "months": months, "li": li, "latest_month": s["latest_month"],
        "rows": rows, "by_slug": {r["slug"]: r for r in rows}, "national": nat, "nat_ytd": nat_ytd,
        "peak_month": months[peak], "base_floor": base_floor,
        "inj": inj, "fatal": raw["fatal"], "emergency": raw["emergency"], "notices": raw.get("notices", []),
        "sight_updated": s["updated"], "inj_updated": inj["updated"], "inj_as_of": inj["as_of"],
        "fetched_date": raw["fetched_at"][:10], "fetched_at": raw["fetched_at"],
        "unlisted": [pf.full(x) for x in pf.SHORT[39:]],
    }


def month_range(d: dict) -> str:
    """'4月から7月'."""
    return f"{d['months'][0]}月から{d['latest_month']}月"


def freshness(d: dict) -> str:
    emg = d["emergency"][d["cur"]]
    return (f"最新の公表: 出没件数は{d['latest_month']}月分まで({jp_date(d['sight_updated'])}更新)、"
            f"人身被害は{d['inj_as_of'].replace('R08年', '令和8年')}({jp_date(d['inj_updated'])}更新)、"
            f"緊急銃猟は{md(emg['cases'][-1]['date'])}分まで({jp_date(emg['updated'])}更新)。"
            "環境省は、出没件数を翌月末ごろ、人身被害を翌月の第1週に掲載します。")


# ---------------------------------------------------------------- small html helpers

def pref_link(r: dict) -> str:
    return f'<a href="/{r["slug"]}/">{esc(r["name"])}</a>'


def caution_box() -> str:
    return f'<p class="notice">{CAUTION}</p>'


def icon(name: str) -> str:
    return f'<svg class="icon" aria-hidden="true"><use href="/assets/icons.svg#{name}"/></svg>'


GUIDE_ICONS = {"prepare": "guide", "encounter": "paw", "spray": "emergency", "home": "location", "data": "chart"}
TILE_COLORS = ("#e5ede7", "#d9f99d", "#86efac", "#22c55e", "#f97316", "#dc2626")


def guide_card(g: dict) -> str:
    return (f'<a class="guide-card" href="/guide/{g["slug"]}/"><img class="gc-img" src="/assets/img/guide-{g["slug"]}.webp" alt="" '
            f'width="800" height="450" loading="lazy"><div class="gc-body"><b>{esc(g["title"])}</b><span>{esc(g["lead"])}</span></div></a>')


def stat(label: str, big: str, sub: str, strong: bool = False, ico: str = "") -> str:
    return (f'<div class="stat{" strong" if strong else ""}">{icon(ico) if ico else ""}<span>{label}</span><b>{big}</b>'
            f'<span>{sub}</span></div>')


def tile_map(d: dict) -> str:
    """47 square tiles (a Japan tile-grid map); shade = the latest full year's sightings, in five quantile steps."""
    from sokuhou import tilegrid
    done = d["done"]
    by_short = {r["slug"]: r for r in d["rows"]}
    values = sorted(r["total"][done] for r in d["rows"] if r["has"])
    cell, pad = 46, 2
    parts = []
    for slug, col, row in tilegrid.tiles():
        short = next(k for k, v in pf.SLUG.items() if v == slug)
        x, y = pad + col * cell, pad + row * cell
        label = short[:2]
        r = by_short.get(slug)
        if r and r["has"]:
            v = r["total"][done]
            below = sum(1 for x_ in values if x_ < v)
            cls = "t0" if v == 0 else f"t{1 + min(4, int(5 * below / len(values)))}"
            line = f"{fy_label(done)}の出没 {n(v)}件(39道府県中{r['rank']['done']}位)"
            parts.append(f'<a href="/{slug}/" data-slug="{slug}" data-name="{esc(r["name"])}" data-line="{esc(line)}" '
                         f'aria-label="{esc(r["name"])} {n(v)}件"><rect class="tile {cls}" x="{x}" y="{y}" width="{cell - 4}" height="{cell - 4}" rx="7"/>'
                         f'<text x="{x + (cell - 4) / 2}" y="{y + (cell - 4) / 2}">{esc(label)}</text></a>')
        else:
            parts.append(f'<g><title>{esc(pf.full(short))}: 環境省の表に数値がありません</title><rect class="tile na" x="{x}" y="{y}" width="{cell - 4}" height="{cell - 4}" rx="7"/>'
                         f'<text x="{x + (cell - 4) / 2}" y="{y + (cell - 4) / 2}">{esc(label)}</text></g>')
    w, h = tilegrid.GRID_COLS * cell + pad * 2, tilegrid.GRID_ROWS * cell + pad * 2
    legend = "".join(f'<i style="background:{c}"></i>' for c in TILE_COLORS)
    return (f'<div class="tilemap-box"><svg class="tilemap" viewBox="0 0 {w} {h}" role="group" aria-label="都道府県別の出没件数({fy_label(done)})">'
            f'{"".join(parts)}</svg><div class="tile-legend"><b>{fy_label(done)}の出没件数</b><span class="lg">少ない {legend} 多い</span><span>(破線の枠は、環境省の表に数値がない県)</span></div></div>')


def bar_list(rows: list[tuple[str, str, int]], top: int) -> str:
    """rows: (link html, value text, value); bars are relative to the largest."""
    mx = max(v for _, _, v in rows) or 1
    return '<ol class="bar-list">' + "".join(f'<li style="--v:{round(v / mx * 100)}">{a}<b>{t}</b><i></i></li>' for a, t, v in rows[:top]) + "</ol>"


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og-kuma-alert.webp")
    alternates = (("更新のお知らせ", "/feed.xml"),) + tuple(kw.pop("alternates", ()))
    return layout(SITE, cfg, preview, alternates=alternates, **kw)


# ---------------------------------------------------------------- pages

def index_page(d: dict, cfg: dict, preview: bool) -> str:
    done, cur = d["done"], d["cur"]
    nat, inj = d["national"], d["inj"]["national"]
    total_done, total_prev = nat["total"][done], nat["total"][d["years"][-3]]
    i_done = inj[done]
    inj_max = max(inj, key=lambda y: inj[y][1])
    top = sorted((r for r in d["rows"] if r["has"]), key=lambda r: (-r["total"][done], r["name"]))[:5]
    emg = d["emergency"][cur]
    latest = emg["cases"][-3:][::-1]
    fatal = d["fatal"][cur]
    ytd_cur, ytd_prev = d["nat_ytd"][cur], d["nat_ytd"][done]
    top_rows = bar_list([(pref_link(r), f'{n(r["total"][done])}件', r["total"][done]) for r in top], 5)
    emg_rows = "".join(f'<li>{md(c["date"])} {esc(c["prefecture"])}{esc(c["place"])}<b>{esc(c["species"])}</b></li>' for c in latest)
    guides = "".join(guide_card(g)
                     for g in content.GUIDES)
    live_home = ""
    lv = d.get("lv")
    if lv and lv["records"]:
        sights = [x for x in lv["records"] if x["kind"].startswith("目撃")][:8] or lv["records"][:8]
        items = "".join(f'<li>{md(x["at"][:10])} {esc(pf.full(x["pref"]))}{esc(live_mod.place_text(x["city"], x["place"]))}<b>{esc(x["kind"])}</b></li>' for x in sights)
        live_home = (f'<h2>最新の目撃情報(自治体の公式)</h2>\n'
                     f'<p class="alert">{fy_label(d["cur"])}は、自治体が公表した記録が{n(len(lv["records"]))}件(直近30日は{n(live_mod.last30(lv["records"], lv["today"]))}件)。'
                     f'最新は{md(lv["records"][0]["at"][:10])}({live_mod.ago_text(lv["records"][0]["at"], lv["today"])})です。</p>\n'
                     f'<ul class="mini-list wide">{items}</ul>\n'
                     f'<p><a href="/live/">自治体の目撃情報の一覧</a> / <a href="/map/">地図で見る(現在地の近く)</a> / <a href="/digest/">週ごとのまとめ</a>{' / <a href="/data/">データ(CSV)</a>' if live_mod.licensed_sources(lv) else ''} / <a href="/cite/">データの出典・引用のしかた</a></p>\n')
    news_block = ""
    if d["notices"]:
        items = "".join(f'<li><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["title"])}</a><b>{md(x["date"])}</b></li>' for x in d["notices"][:4])
        news_block = (f'<h2>環境省の最近のお知らせ</h2>\n<ul class="link-list">{items}</ul>\n'
                      '<p><a href="/news/">お知らせの一覧</a></p>\n')
    body = f"""<section class="hero hero--kuma">
<div class="hero-copy">
<p class="eyebrow">環境省の速報値(都道府県からの聞き取り)</p>
<h1>クマ出没速報</h1>
<div class="hero-main"><div><span class="hero-sub">{fy_label(done)}の出没件数(全国)</span><b class="big">{n(total_done)}件</b></div>
<span class="hero-sub"><em>{fy_label(d['years'][-3])}({n(total_prev)}件)の{ratio_text(total_done, total_prev)}</em></span></div>
</div>
<ul class="hero-facts">
<li><span>{icon("injury")}{fy_label(done)}の人身被害</span><b>{n(i_done[0])}件・{n(i_done[1])}人(うち死亡{n(i_done[2])}人)</b></li>
<li><span>{icon("sightings")}{fy_label(cur)}の出没({month_range(d)})</span><b>{n(ytd_cur)}件(前年度の同じ期間は{n(ytd_prev)}件・{ratio_text(ytd_cur, ytd_prev)})</b></li>
<li><span>{icon("emergency")}{fy_label(cur)}の緊急銃猟</span><b>{n(len(emg['cases']))}件(死亡事故は{n(fatal['deaths'])}人、{jp_date(fatal['as_of'])}現在)</b></li>
</ul>
<a class="btn" href="/ranking/sightings/">都道府県別のランキングを見る</a>
</section>
<p class="notice" style="margin-top:12px">{freshness(d)}</p>
{live_home}<h2>お住まいの地域の、最新の出没情報は</h2>
<p>環境省の数字は、公表までに時間がかかります。<strong>いま近くで出ているかどうかは、お住まいの都道府県・市町村の公式ページで確認してください。</strong>各道府県のページから、公式の出没情報へ案内します。</p>
<section id="mypref" class="mypref" hidden><h3>{icon("location")}マイ都道府県</h3><div class="mp-body"></div><label>都道府県を選ぶ <select><option value="">選んでください</option></select></label></section>
{tile_map(d)}
<h2>{fy_label(done)}に出没が多かった道府県</h2>
{top_rows}
<p><a href="/ranking/sightings/">全国のランキング</a> / <a href="/ranking/change/">前年度の同じ期間との比較</a> / <a href="/ranking/injuries/">人身被害のランキング</a>{' / <a href="/ranking/captures/">許可捕獲数のランキング</a>' if d.get('captures') else ''}</p>
<h2>{fy_label(done)}は、出没が秋に集中しました</h2>
<p>全国の月別では、{d['peak_month']}月が最も多く({n(nat['monthly'][done][d['months'].index(d['peak_month'])])}件)でした。{fy_label(cur)}の月別も、公表が進み次第、追加します。</p>
{charts.lines([{"label": fy_label(y), "values": nat["monthly"][y], "cls": c, "strong": y == cur} for y, c in zip(d["years"], ("c0", "c1", "c2", "c3", "c4"))], [f"{m}月" for m in d["months"]], title="全国の月別の出没件数", desc="令和4年度から令和8年度までの、全国の月別の出没件数(件)", uid="home")}
<h2>最近の緊急銃猟({fy_label(cur)})</h2>
<ul class="mini-list">{emg_rows}</ul>
<p><a href="/emergency/">緊急銃猟と死亡事故の一覧</a></p>
{news_block}<h2>クマに出会わないために</h2>
<div class="card-grid" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">{guides}</div>
<div class="pictos"><img src="/assets/img/pictogram-bell-radio-spray.webp" alt="音の出るもの、ラジオ、クマ撃退スプレーを携帯する、という対策のイラスト" width="800" height="450" loading="lazy"><img src="/assets/img/pictogram-slow-retreat.webp" alt="クマに出会ったときは、慌てず、ゆっくり後退する、というイラスト" width="800" height="450" loading="lazy"></div>
<p><a href="/notify/">更新を通知で受け取る方法</a></p>
<p class="notice">人身被害は、{fy_label(inj_max)}が、{n(inj[inj_max][1])}人で、表にある平成20年度以降で最も多くなっています。{CAUTION}</p>"""
    return page(cfg, preview, scripts=True, path="/", title=f"クマ出没速報 | 都道府県別の出没件数・人身被害・緊急銃猟(環境省の速報値)",
                description=f"{fy_label(done)}の全国のクマ出没は{n(total_done)}件。都道府県別のランキング、月別の推移、人身被害、緊急銃猟の一覧を、環境省の速報値からまとめています。",
                body=body)


def ranking_tabs(kind: str, captures: bool = False) -> str:
    tabs = [("sightings", "出没件数"), ("change", "前年度との比較"), ("injuries", "人身被害")] + ([("captures", "許可捕獲数")] if captures else [])
    return '<div class="tabs" role="tablist">' + "".join(
        f'<a href="/ranking/{k}/"{" class=\"on\"" if k == kind else ""}>{label}</a>' for k, label in tabs) + "</div>"


def ranking_page(d: dict, kind: str, cfg: dict, preview: bool) -> str:
    done, cur, prev = d["done"], d["cur"], d["years"][-3]
    note = f'<p class="notice">環境省の表には、北海道から高知県までの39道府県が載っています({"・".join(d["unlisted"][:3])}など、福岡県から沖縄県までは載っていません)。{CAUTION}</p>'
    if kind == "sightings":
        rows = sorted((r for r in d["rows"] if r["has"]), key=lambda r: (-r["total"][done], r["name"]))
        lines = [[str(r["rank"]["done"]), pref_link(r), n(r["total"][done]), n(r["total"][prev]), ratio_text(r["total"][done], r["total"][prev]),
                  f'{n(r["ytd"][cur])}'] for r in rows]
        head = ["順位", "道府県", f"{fy_label(done)}", f"{fy_label(prev)}", "前年度との比", f"{fy_label(cur)}({month_range(d)})"]
        extra = bar_list([(pref_link(r), f'{n(r["total"][done])}件', r["total"][done]) for r in rows], 10)
        h1, lead = "クマの出没件数ランキング", f"{fy_label(done)}の出没件数が多い順に、並べています。{'と'.join(r['name'] for r in d['rows'] if not r['has'])}は、環境省の表に数値がありません(「-」)ので、載せていません。"
    elif kind == "change":
        extra = ""
        rows = sorted((r for r in d["rows"] if r["rank"]["change"]), key=lambda r: (r["rank"]["change"], r["name"]))
        lines = [[str(r["rank"]["change"]), pref_link(r), n(r["ytd"][cur]), n(r["ytd"][done]),
                  f'{r["ytd"][cur] / r["ytd"][done] * 100:.0f}%'] for r in rows]
        lines = [[str(i + 1)] + ln[1:] for i, ln in enumerate(lines)]
        head = ["順位", "道府県", f"{fy_label(cur)}({month_range(d)})", f"{fy_label(done)}の同じ期間", "前年度の同じ期間に対する割合"]
        h1 = "クマの出没件数 前年度の同じ期間との比較"
        lead = (f"{fy_label(cur)}の{month_range(d)}の出没件数が、{fy_label(done)}の同じ期間の何%にあたるかを、高い順に並べています。"
                f"{fy_label(done)}の同じ期間が{d['base_floor']}件未満の道府県は、割合が不安定になるため、載せていません。")
        extra = ""
    else:
        rows = sorted(d["rows"], key=lambda r: (-r["inj"][done][1], r["name"]))
        lines = [[str(r["rank"]["injured"]), pref_link(r), f'{n(r["inj"][done][0])}', f'{n(r["inj"][done][1])}', f'{n(r["inj"][done][2])}',
                  f'{n(r["injured7"])}'] for r in rows]
        head = ["順位", "道府県", f"{fy_label(done)} 件数", "人数", "死亡", f"令和元年度〜{fy_label(done)}の人数の合計"]
        h1 = "クマによる人身被害ランキング"
        lead = f"{fy_label(done)}の人身被害(人数)が多い順に、39道府県を並べています。人身被害は、出没件数と違って、全国で同じ基準(件数・人数・死亡者数)で数えられています。"
        extra = f'<p class="notice">人身被害の{fy_label(cur)}は、{d["inj_as_of"].replace("R08年", "令和8年")}の速報値で、全国で{n(d["inj"]["national"][cur][0])}件・{n(d["inj"]["national"][cur][1])}人(うち死亡{n(d["inj"]["national"][cur][2])}人)です。</p>'
    body = f"""{crumbs([("全国", "/"), ("ランキング", None)])}
<h1>{h1}</h1>
<p class="lead">{lead}</p>
{ranking_tabs(kind, bool(d.get('captures')))}
{extra if kind == "sightings" else ""}{table(head, lines)}
{extra if kind == "injuries" else ""}{note}
<p class="notice">{freshness(d)}</p>"""
    return page(cfg, preview, path=f"/ranking/{kind}/", title=f"{h1}({fy_label(done)}・環境省の速報値)",
                description=f"{lead[:110]}", body=body)


def injuries_table(d: dict, r: dict | None) -> str:
    years = d["inj"]["years"]
    src = d["inj"]["national"] if r is None else r["inj"]
    return table(["年度", "件数", "人数", "死亡"], [[fy_or_h(y), n(src[y][0]), n(src[y][1]), n(src[y][2])] for y in reversed(years)])


def fy_or_h(y: str) -> str:
    return f"平成{int(y[1:])}年度" if y.startswith("H") else fy_label(y)


def trend_page(d: dict, cfg: dict, preview: bool) -> str:
    inj = d["inj"]
    years = inj["years"]
    nat = d["national"]
    monthly_rows = [[fy_label(y)] + [n(nat["monthly"][y][i]) for i in range(12)] + [n(nat["total"][y])] for y in reversed(d["years"])]
    head = ["年度"] + [f"{m}月" for m in d["months"]] + ["合計"]
    bars = charts.bars([y.replace("H", "H").replace("R0", "R") if False else y for y in years], [inj["national"][y][1] for y in years],
                       title="人身被害の人数", desc="平成20年度から令和8年度までの、全国のクマによる人身被害の人数と、うち死亡者数",
                       uid="inj", marks=[inj["national"][y][2] for y in years], marks_label="うち死亡者数")
    body = f"""{crumbs([("全国", "/"), ("全国の推移", None)])}
<h1>クマの出没・人身被害の推移(全国)</h1>
<p class="lead">全国の出没件数を月別に、人身被害を年度別に、環境省の速報値から並べています。</p>
<h2>月別の出没件数(令和4年度から)</h2>
{charts.lines([{"label": fy_label(y), "values": nat["monthly"][y], "cls": c, "strong": y == d["cur"]} for y, c in zip(d["years"], ("c0", "c1", "c2", "c3", "c4"))], [f"{m}月" for m in d["months"]], title="全国の月別の出没件数", desc="全国の月別の出没件数", uid="tr")}
{table(head, monthly_rows)}
<p class="notice">{fy_label(d['cur'])}は、{month_range(d)}までの公表です。{CAUTION}</p>
<h2>人身被害の人数(平成20年度から)</h2>
{bars}
{injuries_table(d, None)}
<p class="notice">表の「R」は令和、「H」は平成です。{fy_label(d['cur'])}は、{d['inj_as_of'].replace('R08年', '令和8年')}までの速報値です。</p>"""
    return page(cfg, preview, path="/trend/", title="クマの出没・人身被害の推移(全国・環境省の速報値)",
                description="全国のクマの出没件数(月別・令和4年度から)と人身被害(平成20年度から)の推移を、環境省の速報値からまとめています。", body=body)


def emergency_page(d: dict, cfg: dict, preview: bool) -> str:
    cur, done = d["cur"], d["done"]
    emg, prev_emg = d["emergency"][cur], d["emergency"][done]
    fatal, prev_fatal = d["fatal"][cur], d["fatal"][done]
    species = {}
    for c in emg["cases"]:
        species[c["species"]] = species.get(c["species"], 0) + 1
    by_pref = {}
    for c in emg["cases"]:
        by_pref[c["prefecture"]] = by_pref.get(c["prefecture"], 0) + 1
    pref_text = "、".join(f"{k}{v}件" for k, v in sorted(by_pref.items(), key=lambda kv: (-kv[1], kv[0]))[:6])
    sp_text = "、".join(f"{k}{v}件" for k, v in sorted(species.items(), key=lambda kv: -kv[1]))
    emg_rows = [[md(c["date"]), esc(c["prefecture"] + c["place"]), esc(c["species"])] for c in reversed(emg["cases"])]
    fatal_rows = [[md(i["date"]) + ("(被害者発見日)" if i["found_date"] else ""), esc(i["prefecture"] + i["place"]), f'{i["victims"]}人'] for i in reversed(fatal["incidents"])]
    prev_fatal_rows = [[md(i["date"]), esc(i["prefecture"] + i["place"])] for i in reversed(prev_fatal["incidents"])]
    body = f"""{crumbs([("全国", "/"), ("緊急銃猟・死亡事故", None)])}
<h1>緊急銃猟と、クマによる死亡事故({fy_label(cur)})</h1>
<p class="lead">環境省が把握している、{fy_label(cur)}の緊急銃猟の実施状況(日付・場所・対象)と、クマによる死亡事故の概要(日付・場所)です。どちらも、環境省が把握する事例に限ります。</p>
<div class="stats">{stat("緊急銃猟(実施)", f"{n(len(emg['cases']))}件", f"{jp_date(emg['updated'])}更新・{md(emg['cases'][-1]['date'])}分まで", True)}{stat("死亡事故", f"{n(fatal['deaths'])}人", f"{jp_date(fatal['as_of'])}現在")}{stat(f"{fy_label(done)}(1年間)", f"緊急銃猟{n(len(prev_emg['cases']))}件", f"死亡事故{n(prev_fatal['deaths'])}人")}</div>
<p>{fy_label(cur)}の緊急銃猟は、対象が{sp_text}です。件数が多い道府県は、{pref_text}です。</p>
<h2>緊急銃猟の実施状況({fy_label(cur)})</h2>
{table(["日付", "場所", "対象"], emg_rows)}
<p class="notice">環境省の資料(令和8年度の緊急銃猟実施状況、{jp_date(emg['updated'])}更新)を、日付順に並べ替えたものです。</p>
<h2>クマによる死亡事故({fy_label(cur)})</h2>
{table(["日付", "場所", "人数"], fatal_rows)}
<p class="notice">環境省の資料(令和8年度のクマによる死亡事故数等、{jp_date(fatal['as_of'])}現在)です。「被害者発見日」は、事故の日ではなく、被害者が見つかった日です。この資料の更新が、人身被害の表より遅れることがあります。</p>
<h2>{fy_label(done)}の死亡事故(参考)</h2>
{table(["日付", "場所"], prev_fatal_rows)}
<p class="notice">{jp_date(prev_fatal['as_of'])}現在の環境省の資料です。</p>"""
    return page(cfg, preview, path="/emergency/", title=f"クマの緊急銃猟と死亡事故の一覧({fy_label(cur)}・環境省)",
                description=f"{fy_label(cur)}のクマの緊急銃猟{n(len(emg['cases']))}件と、死亡事故の日付・場所を、環境省の資料から一覧にしています。", body=body)


OTSU_PAGE = "https://www.city.otsu.lg.jp/soshiki/025/1605/g/t/74581.html"
OTSU_MAP = "https://www.google.com/maps/d/viewer?mid=1rE5HcSdJnm2gX3iT1FMt0aCVuQ9ArDs"


def prepare_live(otsu: dict | None) -> dict | None:
    """Otsu City's own sighting list (from the city's published map), newest first. None when there is no data."""
    if not otsu or not otsu.get("sightings"):
        return None
    items = sorted((s for s in otsu["sightings"] if s.get("observed_at")), key=lambda s: s["observed_at"], reverse=True)
    if not items:
        return None
    by_fy: dict[str, list] = {}
    for s in items:
        by_fy.setdefault(s["fiscal_year"], []).append(s)
    return {"items": items, "by_fy": by_fy, "official": otsu.get("official_counts", {}), "fetched_date": otsu["fetched_at"][:10],
            "latest_fy": items[0]["fiscal_year"]}


PREF_LIVE = live_mod.LIVE_SOURCES
FY_MONTHS = (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)


def prepare_prefs(prefs: dict | None) -> list[dict]:
    """Prefecture-published sighting lists (Miyagi, Akita): newest first, nothing dated after the prefecture's own as-of date."""
    out = []
    for key, meta in PREF_LIVE.items():
        raw = (prefs or {}).get(key)
        if not raw or not raw.get("sightings"):
            continue
        as_of = raw["as_of"]
        items = sorted((x for x in raw["sightings"] if x.get("observed_at") and x["observed_at"][:10] <= as_of),
                       key=lambda x: x["observed_at"], reverse=True)
        if not items:
            continue
        fy = raw["fy_current"]
        out.append({"key": key, **meta, "items": items, "sights": [x for x in items if x["kind"] == "目撃"] or items,
                    "fy": fy, "monthly": raw.get("monthly", {}).get(fy, {}), "as_of": as_of, "credit": raw["credit"],
                    "page": raw["source_page"], "update_note": raw["update_note"],
                    "after": raw.get("dates_after_as_of", 0), "fetched_date": raw["fetched_at"][:10]})
    return out


def place_text(x: dict) -> str:
    place = x["place"]
    return place if x["city"] in place else f"{x['city']}{place}"




def news_page(d: dict, cfg: dict, preview: bool) -> str:
    rows = "".join(
        f'<li id="n-{x["date"]}-{i}"><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["title"])}</a>'
        f'<span>{jp_date(x["date"])}</span></li>' for i, x in enumerate(d["notices"]))
    body = f"""{crumbs([("全国", "/"), ("環境省のお知らせ", None)])}
<h1>環境省の、クマに関するお知らせ</h1>
<p class="lead">環境省の「クマに関する各種情報・取組」のページに載っている、日付つきのお知らせ(大臣の談話・会見、自治体への事務連絡、講習会の案内など)を、新しい順に並べています。リンク先は、環境省のページです。</p>
<ul class="link-list news-list">{rows}</ul>
<p class="notice">題名は、環境省のページの表記のままです(日付の後ろにある発信元の記載は省いています)。このサイトでは、報道各社の記事は載せていません。お住まいの地域の最新の情報は、<a href="/ranking/sightings/">各道府県のページ</a>から、公式の出没情報へ進んでください。</p>
<p class="notice">出典: <a href="{MINISTRY_PAGE}" rel="noopener" target="_blank">環境省「クマに関する各種情報・取組」</a>を加工して作成。環境省が作成したものではありません。取得日: {jp_date(d['fetched_date'])}。</p>"""
    return page(cfg, preview, path="/news/", title="環境省のクマに関するお知らせ(新着)",
                description="環境省が公表している、クマに関する大臣の談話・会見、自治体への事務連絡などの新着を、日付順に一覧にしています。", body=body)


def pref_page(d: dict, r: dict, cfg: dict, preview: bool, links: dict) -> str:
    done, cur, prev = d["done"], d["cur"], d["years"][-3]
    emg = [c for c in d["emergency"][cur]["cases"] if c["prefecture"] == r["name"]]
    fat = [i for y in (cur, done) for i in d["fatal"][y]["incidents"] if i["prefecture"] == r["name"]]
    i_done = r["inj"][done]
    official = links.get(r["short"]) or []
    off_html = ("<ul class='link-list'>" + "".join(
        f'<li><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["label"])}</a></li>' for x in official) + "</ul>") if official else (
        f'<p>{esc(r["name"])}の公式サイトで、「クマ 出没」で検索してください。市町村が、独自に出没情報を公開していることもあります。</p>')
    if r["has"]:
        peak_i = max(range(12), key=lambda i: r["monthly"][done][i] or 0)
        sight = f"""<div class="stats">{stat(f"{fy_label(done)}の出没件数", f"{n(r['total'][done])}件", f"39道府県中{r['rank']['done']}位", True, "sightings")}{stat(f"{fy_label(prev)}", f"{n(r['total'][prev])}件", f"前年度との比: {ratio_text(r['total'][done], r['total'][prev])}")}{stat(f"{fy_label(cur)}({month_range(d)})", f"{n(r['ytd'][cur])}件", f"前年度の同じ期間: {n(r['ytd'][done])}件")}</div>
<p>{fy_label(done)}は、{d['months'][peak_i]}月が最も多く({n(r['monthly'][done][peak_i])}件)でした。</p>
<h2>月別の出没件数</h2>
{charts.lines([{"label": fy_label(y), "values": r["monthly"][y], "cls": c, "strong": y == cur} for y, c in zip((prev, done, cur), ("c1", "c3", "c4"))], [f"{m}月" for m in d["months"]], title=f"{r['name']}の月別の出没件数", desc=f"{r['name']}の月別の出没件数", uid="p")}
{table(["年度"] + [f"{m}月" for m in d["months"]] + ["合計"], [[fy_label(y)] + [n(r["monthly"][y][i]) for i in range(12)] + [n(r["total"][y])] for y in reversed(d["years"])])}"""
    else:
        sight = f"<p>環境省の出没件数の表には、{esc(r['name'])}の数値がありません(「-」)。人身被害の件数は、下に載せています。</p>"
    emg_html = ("<ul class='mini-list'>" + "".join(f'<li>{md(c["date"])} {esc(c["place"])}<b>{esc(c["species"])}</b></li>' for c in emg) + "</ul>") if emg else f"<p>環境省の{fy_label(cur)}の一覧には、{esc(r['name'])}の事例はありません(環境省が把握する事例に限ります)。</p>"
    fat_html = ("<ul class='mini-list'>" + "".join(f'<li>{jp_date(i["date"])} {esc(i["place"])}<b>{i["victims"]}人</b></li>' for i in sorted(fat, key=lambda i: i["date"], reverse=True)) + "</ul>") if fat else f"<p>環境省の資料(令和7・8年度)には、{esc(r['name'])}の死亡事故はありません。</p>"
    live_block = ""
    if d.get("live") and r["slug"] == "shiga":
        lv = d["live"]
        recent = "".join(f'<li>{day_text(x["observed_at"])} {esc(x["place"])}</li>' for x in lv["items"][:5])
        live_block = (f'<h2>大津市の最新の目撃情報(市の公式)</h2>\n<ul class="mini-list">{recent}</ul>\n'
                      '<p><a href="/live/shiga/">大津市の目撃情報の一覧(市町村別・地図)</a></p>\n')
    for src in d["live_prefs"]:
        if live_mod.LIVE_SOURCES[src["key"]]["pref"] == r["short"]:
            recent = "".join(f'<li>{day_text(x["observed_at"])} {esc(place_text(x))}</li>' for x in src["sights"][:5])
            live_block = (f'<h2>{src["name"]}が公表している最新の目撃情報</h2>\n'
                          f'<p>{src["as_of_text"].format(d=jp_date(src["as_of"]))}。</p>\n<ul class="mini-list">{recent}</ul>\n'
                          f'<p><a href="/live/{r["slug"]}/">{src["name"]}の目撃情報の一覧(市町村別・地図)</a></p>\n')
    cap_html = captures_mod.pref_block(d["captures"], r["short"], r["name"])
    for c in d["live_counts"]:
        if c["pref"] == r["short"]:
            live_block = (f'<h2>{c["name"]}が公表している件数</h2>\n<p>{fy_label(c["fy"])}は{n(c["total"])}件で、最新は{md(c["latest"])}の分です。件数だけを載せています。</p>\n'
                          f'<p><a href="/live/{r["slug"]}/">市町村別・月別の件数</a></p>\n')
    nav = "".join(f'<li><a href="/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in d["rows"] if x is not r)
    mates = [x for x in d["rows"] if x is not r and x["region_slug"] == r["region_slug"]]
    rel = ""
    if mates:
        rel = (f'<h2>{esc(r["region"])}のほかの道府県</h2>\n<div class="rel-grid">' + "".join(
            f'<a href="/{x["slug"]}/">{esc(x["name"])}<span>{n(x["total"][done]) + "件" if x["has"] else "-"}</span></a>' for x in mates) + "</div>\n")
    body = f"""{crumbs([("全国", "/"), ("ランキング", "/ranking/sightings/"), (r["name"], None)])}
<h1>{esc(r['name'])}のクマ出没({fy_label(done)}・環境省の速報値)</h1>
<button class="btn-ghost" type="button" data-mypref-toggle data-slug="{r['slug']}" data-name="{esc(r['name'])}" aria-pressed="false" hidden>この県を「マイ都道府県」にする</button>
{sight}
{live_block}<h2>人身被害</h2>
<p>{fy_label(done)}は、{n(i_done[0])}件・{n(i_done[1])}人(うち死亡{n(i_done[2])}人)で、39道府県中{r['rank']['injured']}位(人数)でした。令和元年度から{fy_label(done)}までの7年間の合計は、{n(r['injured7'])}人です。</p>
{charts.bars([y for y in d['inj']['years']], [r['inj'][y][1] for y in d['inj']['years']], title="人身被害の人数", desc=f"{r['name']}の人身被害の人数と死亡者数(平成20年度から)", uid="pi", marks=[r['inj'][y][2] for y in d['inj']['years']], marks_label="うち死亡者数")}
{injuries_table(d, r)}
<h2>{fy_label(cur)}の緊急銃猟</h2>
{emg_html}
<h2>クマによる死亡事故({fy_label(done)}・{fy_label(cur)})</h2>
{fat_html}
{cap_html}<h2>{esc(r['name'])}の公式の出没情報</h2>
<p>いま近くで出ているかは、公式の情報で確認してください。</p>
{off_html}
{caution_box()}
{rel}<h2>ほかの道府県</h2>
<ul class="pref-nav">{nav}</ul>
<div class="next-box"><h2>次に見る</h2><ul><li><a href="/ranking/sightings/">{icon("chart")}出没件数ランキング</a></li><li><a href="/trend/">{icon("calendar")}月別の推移</a></li><li><a href="/emergency/">{icon("emergency")}緊急銃猟</a></li><li><a href="/guide/">{icon("guide")}クマへの対処法</a></li></ul></div>
<p class="notice">{freshness(d)}</p>"""
    return page(cfg, preview, scripts=True, path=f"/{r['slug']}/", title=f"{r['name']}のクマ出没・人身被害({fy_label(done)}・環境省の速報値)",
                description=f"{r['name']}のクマの出没件数(月別)、人身被害、緊急銃猟、公式の出没情報への案内。環境省の速報値をもとにしています。", body=body)


def guide_hub(cfg: dict, preview: bool) -> str:
    cards = "".join(guide_card(g) for g in content.GUIDES)
    body = f"""{crumbs([("全国", "/"), ("対処法・解説", None)])}
<h1>クマへの対処法と、データの見方</h1>
<p class="lead">公的機関の資料にもとづいて、クマに出会わないための備えと、出会ったときの行動、数字の読み方をまとめています。</p>
<div class="card-grid" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">{cards}</div>"""
    return page(cfg, preview, path="/guide/", title="クマへの対処法と、出没データの見方", description="クマに出会わないための備え、出会ったときの行動、出没データの読み方を、公的機関の資料にもとづいてまとめています。", body=body)


def guide_page(g: dict, cfg: dict, preview: bool) -> str:
    sources = "".join(f'<li><a href="{esc(u)}" rel="noopener" target="_blank">{esc(t)}</a></li>' for t, u in g["sources"])
    others = "".join(f'<li><a href="/guide/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in content.GUIDES if x is not g)
    body = f"""{crumbs([("全国", "/"), ("対処法・解説", "/guide/"), (g["title"], None)])}
<h1>{esc(g['title'])}</h1>
<p class="lead">{esc(g['lead'])}</p>
<img class="page-banner" src="/assets/img/guide-{g['slug']}.webp" alt="" width="800" height="450">
<article class="prose">{g['body']}</article>
<h2>出典</h2>
<ul class="link-list">{sources}</ul>
<p class="notice">内容の確認日: {jp_date(content.VERIFIED_AT)}。公的機関の資料は更新されることがあります。最新の内容は、出典でご確認ください。身の危険があるときは、ためらわず 110 番へ連絡してください。</p>
<h2>ほかの解説</h2>
<ul class="link-list">{others}</ul>"""
    return page(cfg, preview, path=f"/guide/{g['slug']}/", title=f"{g['title']} | {cfg['site_name']}", description=g["description"], body=body)


def notify_page(d: dict, cfg: dict, preview: bool) -> str:
    social = ""
    if cfg.get("bluesky_handle"):
        social += f'<li><a href="https://bsky.app/profile/{esc(cfg["bluesky_handle"])}" rel="noopener" target="_blank">Bluesky(@{esc(cfg["bluesky_handle"])})</a>をフォローすると、環境省のデータが更新されたときのお知らせが届きます。</li>'
    if cfg.get("x_handle"):
        social += f'<li><a href="https://x.com/{esc(cfg["x_handle"])}" rel="noopener" target="_blank">X(@{esc(cfg["x_handle"])})</a>でも、主なお知らせを載せます。</li>'
    body = f"""{crumbs([("全国", "/"), ("通知を受け取る", None)])}
<h1>更新を、通知で受け取る</h1>
<p class="lead">環境省のクマの出没・人身被害・緊急銃猟のデータが更新されたときに、お知らせを受け取れます。登録は不要で、メールアドレスなどの個人情報も預かりません。</p>
<h2>フィード(RSS)</h2>
<ul class="link-list"><li><a href="/feed.xml">更新のお知らせ(フィード)</a>: 出没件数・人身被害・緊急銃猟のデータが更新されるたびに、1件ずつ載ります。</li></ul>
<p>フィードリーダーに、このアドレスを登録してください。</p>
{"<h2>SNS</h2><ul class='link-list'>" + social + "</ul>" if social else ""}
<p class="notice">お知らせは、環境省の公表にあわせて、自動で作っています。{freshness(d)}</p>"""
    return page(cfg, preview, path="/notify/", title=f"更新を通知で受け取る方法 | {cfg['site_name']}",
                description="環境省のクマのデータが更新されたときのお知らせを、フィード(RSS)や SNS で受け取る方法です。", body=body)


def feed_xml(d: dict, cfg: dict) -> str:
    """One entry per data update, dated by the ministry's own update date (so rebuilding never re-announces)."""
    base = cfg["site_url"].rstrip("/")
    host = urlparse(base).hostname or "localhost"
    done, cur = d["done"], d["cur"]
    emg = d["emergency"][cur]
    nat = d["national"]
    entries = [
        (d["sight_updated"], f"sightings-{d['sight_updated']}", f"クマの出没件数を、{fy_label(cur)}の{d['latest_month']}月分まで更新しました(環境省)",
         f"{fy_label(cur)}の{month_range(d)}は、全国で{n(d['nat_ytd'][cur])}件です(前年度の同じ期間は{n(d['nat_ytd'][done])}件)。", "/trend/"),
        (d["inj_updated"], f"injuries-{d['inj_updated']}", f"クマによる人身被害を、{d['inj_as_of'].replace('R08年', '令和8年')}まで更新しました(環境省)",
         f"{fy_label(cur)}は、{n(d['inj']['national'][cur][0])}件・{n(d['inj']['national'][cur][1])}人(うち死亡{n(d['inj']['national'][cur][2])}人)です。", "/ranking/injuries/"),
        (emg["updated"], f"emergency-{emg['updated']}", f"クマの緊急銃猟の実施状況を更新しました({fy_label(cur)}は{n(len(emg['cases']))}件)",
         f"最新は、{md(emg['cases'][-1]['date'])}の{emg['cases'][-1]['prefecture']}{emg['cases'][-1]['place']}です。", "/emergency/"),
    ]
    for i, x in enumerate(d["notices"][:3]):
        entries.append((x["date"], f"notice-{x['date']}-{i}", f"環境省が、クマに関するお知らせを掲載しました: {x['title']}",
                        "環境省のページに載っている、日付つきのお知らせです。", f"/news/#n-{x['date']}-{i}"))
    c = d.get("captures")
    if c:
        entries.append((c["updated"], f"captures-{c['updated']}", f"クマの許可捕獲数を、{c['as_of_text']}まで更新しました(環境省)",
                        f"{fy_label(c['cur'])}は、{c['as_of_text']}までで全国{n(c['national'][c['cur']][0])}頭です(暫定値)。", "/ranking/captures/"))
    entries.sort(reverse=True)
    body = "".join(
        f"<entry><id>tag:{host},{day}:{eid}</id><title>{esc(t)}</title><link href=\"{esc(base + path + ('' if '#' in path else '#u-' + day))}\"/>"
        f"<updated>{day}T00:00:00+09:00</updated><summary>{esc(s)}</summary></entry>\n" for day, eid, t, s, path in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja">\n'
            f"<id>tag:{host},2026:updates</id><title>{esc(cfg['site_name'])} 更新のお知らせ</title>"
            f'<link href="{esc(base)}/feed.xml" rel="self"/><link href="{esc(base)}/"/>'
            f"<updated>{entries[0][0]}T00:00:00+09:00</updated>\n{body}</feed>\n")



# ---------------------------------------------------------------- goods (affiliate; every link is marked PR)

GOODS = [
    {"title": "クマ鈴・ベル", "query": "クマ鈴", "guide": ("prepare", "山に入る前の備え"),
     "points": ["音で、人がいることを知らせるための道具です(環境省・自治体は、音の出るものの携帯を呼びかけています)。",
                "登山・農作業・散歩など、使う場面に合うか、音の大きさ・重さ・取り付け方を、商品ページで確認します。"]},
    {"title": "携帯ラジオ", "query": "携帯ラジオ 防災", "guide": ("prepare", "山に入る前の備え"),
     "points": ["音を出して人の存在を知らせるほか、天気や災害の情報を得る手段にもなります。",
                "電池の種類・持ち運びやすさ・受信できる放送(AM/FM)を、商品ページで確認します。"]},
    {"title": "ヘッドライト・小型ライト", "query": "ヘッドライト 防災", "guide": ("prepare", "山に入る前の備え"),
     "points": ["クマは、早朝や夕方に注意が必要とされています(自治体の啓発資料)。薄暗い時間の作業・行動に、明るさの確保が役立ちます。",
                "明るさ(ルーメン)・点灯時間・防水を、商品ページで確認します。"]},
    {"title": "ホイッスル(笛)", "query": "ホイッスル 登山", "guide": ("prepare", "山に入る前の備え"),
     "points": ["音で存在を知らせる、軽い道具です。ザックに付けておけます。",
                "音の大きさ・紐の長さ・水に濡れても鳴るかを、商品ページで確認します。"]},
    {"title": "クマ撃退スプレー", "query": "クマ撃退スプレー", "guide": ("spray", "選び方と使い方(消費者庁・環境省)"),
     "points": ["出会ってしまったときの「最終手段」です。まず、出会わないための対策が第一です。",
                "クマ用で、撃退用のものを選びます。噴射距離・噴射時間などの性能表示を確認します(消費者庁)。環境省は、令和8年8月に、性能に係る推奨要件を公表しています。",
                "このサイトは、製品の効果を保証しません。保管・持ち運び・航空機への持ち込み不可などの注意は、解説のページで確認してください。"]},
    {"title": "ごみ・食べ物を、外に置かないための容器", "query": "密閉 ごみ容器 屋外", "guide": ("home", "家の周りに、クマを寄せつけない"),
     "points": ["生ごみ・果樹・農作物などが、クマを人里に引き寄せる要因になります(秋田県の資料)。",
                "ふたが閉まり、においが漏れにくいか・固定できるかを、商品ページで確認します。"]},
]


def rakuten_url(cfg: dict, target: str) -> str:
    """Rakuten Affiliate link to a Rakuten Ichiba page (here: a search results page, so it never goes stale)."""
    aid, tid = cfg["rakuten_affiliate_id"], cfg.get("rakuten_tracking_id")
    enc = quote(target, safe="")
    path = f"{aid}/{tid}" if tid else f"{aid}/"
    return f"https://hb.afl.rakuten.co.jp/hgc/{path}?pc={enc}&m={enc}"


def amazon_url(cfg: dict, query: str) -> str:
    """Amazon.co.jp search results for a keyword, with the Associates tracking ID."""
    return f"https://www.amazon.co.jp/s?k={quote(query, safe='')}&tag={quote(cfg['amazon_tracking_id'], safe='')}"


def goods_page(d: dict, cfg: dict, preview: bool) -> str:
    cards = ""
    for g in GOODS:
        target = "https://search.rakuten.co.jp/search/mall/" + quote(g["query"], safe="") + "/"
        pts = "".join(f"<li>{esc(p)}</li>" for p in g["points"])
        cards += (f'<div class="goods-card"><h3>{esc(g["title"])}</h3><ul>{pts}</ul>'
                  f'<p style="margin:0;font-size:.88rem"><a href="/guide/{g["guide"][0]}/">{esc(g["guide"][1])}</a>を読む</p>'
                  f'<a class="btn" href="{esc(rakuten_url(cfg, target))}" rel="sponsored nofollow noopener" target="_blank">'
                  f'<span class="pr-note">PR</span>楽天市場で探す</a>'
                  + (f'<a class="btn btn-amazon" href="{esc(amazon_url(cfg, g["query"]))}" rel="sponsored nofollow noopener" target="_blank">'
                     f'<span class="pr-note">PR</span>Amazonで探す</a>' if cfg.get("amazon_tracking_id") else "")
                  + '</div>')
    body = f"""{crumbs([("全国", "/"), ("クマ対策グッズ", None)])}
<h1>クマ対策のグッズ</h1>
<p class="lead"><span class="pr-note">PR</span>このページは、広告(楽天アフィリエイト・Amazonアソシエイト)のリンクを含みます。リンク先で購入されると、運営者に報酬が支払われることがあります。</p>
{amazon_disclosure(cfg)}
<p>グッズは、<strong>クマに出会わないための対策の、補助</strong>です。まず、<a href="/guide/prepare/">山に入る前の備え</a>と、<a href="/guide/home/">家の周りの対策</a>を、お読みください。以下は、公的機関の資料に出てくる対策に関連する、商品の種類です。個々の商品を推奨するものではなく、効果も保証しません。各リンクは、楽天市場・Amazonの検索結果のページです。商品の仕様・価格・在庫は、販売ページでご確認ください。</p>
<div class="goods-grid">{cards}</div>
<p class="notice">クマの目撃や被害の通報は、お住まいの市町村、または警察(110番)へお願いします。製品の安全な使い方は、各製品の取扱説明書に従ってください。</p>"""
    return page(cfg, preview, path="/goods/", title="クマ対策のグッズ(PR) 音の出る道具・ライト・撃退スプレーの選び方",
                description="クマに出会わないための備えに関連する、グッズの種類と、確認するポイントを、公的機関の資料にもとづいてまとめています。広告(PR)を含みます。", body=body)


# ---------------------------------------------------------------- weekly digest

def digest_sources(otsu: dict | None, prefs: dict | None) -> list[dict]:
    out = [digest.pref_source(k, meta["name"], (prefs or {})[k]) for k, meta in PREF_LIVE.items() if (prefs or {}).get(k)]
    if otsu:
        out.append(digest.otsu_source(otsu))
    return [x for x in out if x]


def week_range(key: str) -> str:
    a = digest.week_start(key)
    b = a + timedelta(days=6)
    return f"{a.year}年{a.month}月{a.day}日から{b.month}月{b.day}日" if a.year == b.year else f"{a.year}年{a.month}月{a.day}日から{b.year}年{b.month}月{b.day}日"


DIGEST_NOTE = ("各自治体が公表している目撃情報の一覧を、月曜から日曜までの週ごとに数えたものです。自治体ごとに、数える対象(目撃のみか、痕跡などを含むか)と、更新の時期が違うため、"
               "<strong>自治体どうしの件数の大小は、そのまま比べられません</strong>。自治体が後から記録を追加・修正すると、件数が変わることがあります。"
               "一覧の件数が、その自治体の月の合計と合わない月は、対象から外しています。")


def digest_hub(dig: dict, cfg: dict, preview: bool) -> str:
    rows = []
    for k in dig["weeks"]:
        tot, prev, both = digest.common_total(dig, k)
        rows.append([f'<a href="/digest/{k}/">{week_range(k)}</a>', n(sum(dig["by_week"][k].values())),
                     f"{len(dig['by_week'][k])}か所", ratio_text(tot, prev) if prev is not None else "-"])
    names = "・".join(s["name"] for s in dig["sources"].values())
    body = f"""{crumbs([("全国", "/"), ("週ごとのまとめ", None)])}
<h1>クマの目撃情報 週ごとのまとめ</h1>
<p class="lead">自治体が公式に公表しているクマの目撃情報を、週ごとに数えて、前の週と比べています。いまは、{esc(names)}の公表分です。</p>
{table(["週", "件数(取得できた自治体の合計)", "対象", "前の週との比較"], rows)}
<p class="notice">{DIGEST_NOTE}「前の週との比較」は、両方の週で数えられた自治体だけの合計どうしです。</p>"""
    return page(cfg, preview, path="/digest/", title="クマの目撃情報 週ごとのまとめ(自治体の公式)",
                description="自治体が公表しているクマの目撃情報を、週ごとに数えて、前の週と比べています。", body=body)


def digest_page(dig: dict, key: str, cfg: dict, preview: bool) -> str:
    cur, prev = dig["by_week"][key], dig["by_week"].get(digest.prev_key(key), {})
    tot, ptot, both = digest.common_total(dig, key)
    rows, notes = [], ""
    for sk, c in cur.items():
        src = dig["sources"][sk]
        rows.append([esc(src["name"]), n(c), n(prev[sk]) if sk in prev else "-", ratio_text(c, prev[sk]) if sk in prev else "-"])
        if src["note"]:
            notes += f'<p class="notice">{esc(src["name"])}: {esc(src["note"])}</p>\n'
    if both:
        rows.append(["<strong>合計(両週で数えた自治体)</strong>", n(tot), n(ptot), ratio_text(tot, ptot)])
    ws = digest.week_start(key)
    places = ""
    for sk in cur:
        src = dig["sources"][sk]
        days = [x for x in src["days"] if ws <= x <= ws + timedelta(days=6)]
        places += (f"<li>{esc(src['name'])}: {md(min(days).isoformat())}から{md(max(days).isoformat())}まで({n(len(days))}件)</li>" if days
                   else f"<li>{esc(src['name'])}: 記録なし</li>")
    ks = dig["weeks"]
    i = ks.index(key)
    links = ([f'<a href="/digest/{ks[i + 1]}/">前の週</a>'] if i + 1 < len(ks) else []) + ([f'<a href="/digest/{ks[i - 1]}/">次の週</a>'] if i > 0 else [])
    head = f"{week_range(key)}の週に、自治体が公表したクマの目撃は、取得できた{len(cur)}か所で、合計{n(sum(cur.values()))}件です。"
    if both:
        head += (f"前の週と同じ{len(both)}か所で比べると、{n(tot)}件で、前の週({n(ptot)}件)と同じです。" if tot == ptot
                 else f"前の週と同じ{len(both)}か所で比べると、{n(tot)}件で、前の週({n(ptot)}件)の{ratio_text(tot, ptot)}です。")
    body = f"""{crumbs([("全国", "/"), ("週ごとのまとめ", "/digest/"), (week_range(key), None)])}
<h1>{week_range(key)}の、クマの目撃情報</h1>
<p class="lead">{head}</p>
{table(["自治体", "この週の件数", "前の週", "前の週との比較"], rows)}
<h2>記録のあった日</h2>
<ul>{places}</ul>
<p>{" ・ ".join(links)} ・ <a href="/digest/">週ごとのまとめの一覧</a></p>
<p class="notice">{DIGEST_NOTE}</p>
{notes}<p class="notice">出典: 各自治体が公開している目撃情報(<a href="/live/">最新の目撃情報</a>に、出典と取得日を載せています)を加工して作成。各自治体が作成したものではありません。取得日: {jp_date(dig['fetched_date'])}。</p>"""
    return page(cfg, preview, path=f"/digest/{key}/", title=f"{week_range(key)}のクマの目撃情報(週ごとのまとめ)",
                description=head, body=body)


# ---------------------------------------------------------------- site

def render_site(raw: dict, cfg: dict, out: Path, release: bool = False, links: dict | None = None,
                otsu: dict | None = None, prefs: dict | None = None, today: date | None = None,
                captures: dict | None = None) -> list[str]:
    global SITE
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    d = prepare(raw)
    d["captures"] = captures_mod.prepare(captures)
    links = links or {}
    from sokuhou.sources import kumalib   # a source on the stop list is shown nowhere (list, counts, map, feed, CSV, digest, sources page)
    prefs = {k: v for k, v in (prefs or {}).items() if not kumalib.is_stopped(k)} or None
    otsu = None if kumalib.is_stopped("otsu") else otsu
    live = prepare_live(otsu)
    d["live"] = live
    d["live_prefs"] = prepare_prefs(prefs)
    d["live_counts"] = live_mod.prepare_counts(prefs)
    any_live = bool(live or d["live_prefs"] or d["live_counts"])
    nav = [x for x in BASE_NAV if x[1] != "/live/" or any_live]
    if any_live:
        nav = nav[:-1] + [("地図", "/map/", "/map/"), ("週ごとのまとめ", "/digest/", "/digest/")] + nav[-1:]
    if cfg.get("rakuten_affiliate_id"):
        nav = nav[:-1] + [("グッズ(PR)", "/goods/", "/goods/")] + nav[-1:]
    SITE = {**SITE, "nav": nav}
    # the footer of every page links to where the numbers come from (the page exists only with live data); SITE is module-wide, so set it every time
    SITE["source_html"] = SOURCE_HTML + (' 数字の出典・数え方・引用のしかたは、<a href="/cite/">こちら</a>。' if any_live else "")
    d["lv"] = live_mod.prepare_live(d, today or datetime.now(JST).date()) if any_live else None
    pages: dict[str, str | bytes] = {"index.html": index_page(d, cfg, preview)}
    for kind in ("sightings", "change", "injuries"):
        pages[f"ranking/{kind}/index.html"] = ranking_page(d, kind, cfg, preview)
    if d["captures"]:
        pages["ranking/captures/index.html"] = captures_mod.ranking_page(lambda **kw: page(cfg, preview, **kw), d["captures"], lambda kind: ranking_tabs(kind, True))
    pages["trend/index.html"] = trend_page(d, cfg, preview)
    pages["emergency/index.html"] = emergency_page(d, cfg, preview)
    pages["news/index.html"] = news_page(d, cfg, preview)
    if any_live:
        lv = d["lv"]
        page_fn = lambda **kw: page(cfg, preview, **kw)  # noqa: E731
        pages["live/index.html"] = live_mod.hub_page(page_fn, d, lv)
        for slug in lv["by_pref"]:
            pages[f"live/{slug}/index.html"] = live_mod.pref_live_page(page_fn, d, lv, slug, links)
            for city, rows in lv["by_pref"][slug].items():
                if live_mod.city_has_page(rows):
                    pages[f"live/{slug}/{live_mod.city_slug(slug, city)}/index.html"] = live_mod.city_page(page_fn, d, lv, slug, city, links)
        for c in lv["counts"]:
            if c["slug"] in lv["by_pref"]:
                raise BuildError(f"{c['slug']} has both a record source and a counts-only source")
            pages[f"live/{c['slug']}/index.html"] = live_mod.counts_page(page_fn, d, c, lv["today"], links)
        pages["live/feed.xml"] = live_mod.feed_xml(lv, cfg)
        for slug in lv["by_pref"]:
            pages[f"live/{slug}/feed.xml"] = live_mod.feed_xml(lv, cfg, slug)
        pages["map/index.html"] = live_mod.map_page(page_fn, d, lv)
        pages["cite/index.html"] = cite_mod.cite_page(page_fn, d, lv, cfg, cfg["site_url"].rstrip("/"))
        pages["map/points.json"] = live_mod.points_json(lv)
        if live_mod.licensed_sources(lv):
            pages["data/index.html"] = live_mod.data_page(page_fn, d, lv, cfg["site_url"].rstrip("/"))
            pages["data/" + live_mod.CSV_NAME] = live_mod.csv_text(lv)
    for r in d["rows"]:
        pages[f"{r['slug']}/index.html"] = pref_page(d, r, cfg, preview, links)
    pages["guide/index.html"] = guide_hub(cfg, preview)
    for g in content.GUIDES:
        pages[f"guide/{g['slug']}/index.html"] = guide_page(g, cfg, preview)
    pages["notify/index.html"] = notify_page(d, cfg, preview)
    if cfg.get("rakuten_affiliate_id"):
        pages["goods/index.html"] = goods_page(d, cfg, preview)
    dig = digest.build(digest_sources(otsu, prefs))
    if dig["weeks"]:
        dig["fetched_date"] = d["fetched_date"]
        pages["digest/index.html"] = digest_hub(dig, cfg, preview)
        for k in dig["weeks"]:
            pages[f"digest/{k}/index.html"] = digest_page(dig, k, cfg, preview)
    pages["feed.xml"] = feed_xml(d, cfg)
    lv_ = d.get("lv")
    detail_names = [i["name"] for i in lv_["infos"].values()] if lv_ else []
    count_names = [c["name"] for c in d["live_counts"]]
    live_sources_text = ""
    if detail_names:
        live_sources_text += f"。「最新の目撃」のページは、{'・'.join(detail_names)}が公開している目撃情報(各ページに出典と取得日を表示)"
    if count_names:
        live_sources_text += f"。{'・'.join(count_names)}は、再利用の許可が明示されていないため、公開されている情報から件数と最新の日付だけを集計して載せています"
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="クマの出没や人身被害に関する、環境省の公表データを、都道府県別・月別に整理して、暮らしの安全の判断に役立てていただくこと。",
        sources_html=f'環境省「クマに関する各種情報・取組」(<a href="{MINISTRY_PAGE}" rel="noopener" target="_blank">公表ページ</a>)の、出没情報・人身被害件数・緊急銃猟の実施状況・死亡事故の資料(いずれも速報値)' + live_sources_text,
        update_text="環境省の公表にあわせて、自動で更新します。各ページに、公表された日付と、どの月までのデータかを表示します。",
        disclaimer_html=("<p>掲載内容は、環境省が都道府県から聞き取った速報値を加工したもので、後から修正されることがあります。出没数は、都道府県ごとに異なる方法で取りまとめられています。"
                         "正確性・完全性・最新性を保証するものではありません。身近な出没情報は、お住まいの都道府県・市町村の公式の情報をご確認ください。</p>"
                         "<p>このサイトは、環境省や自治体が公表している情報を加工して作成したもので、環境省・自治体が作成したものではありません。クマ撃退スプレーなどの商品の効果を保証するものでもありません。</p>"
                         '<p>掲載の中止のご依頼(自治体・運営者の方を含む)は、<a href="/contact/">お問い合わせ</a>の「掲載内容に関するご連絡」からお願いします。該当の掲載を、速やかに取りやめます。</p>'),
        contact_notice="クマの目撃や被害の通報は、お住まいの市町村、または警察(110番)へお願いします。このサイトでは、通報や個別の相談を受け付けていません。掲載内容(データの誤り、掲載の中止のご依頼など)は、種類を選んで、ご連絡ください。",
        input_note="",
        finish=lambda s: s))
    pages.update(standard_files(pages, cfg, preview, d["fetched_date"]))
    pages.update(asset_pages(HERE / "assets"))
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--data", default=str(ROOT / "data"), help="folder with the collected data/*.json (default: the repository's data/)")
    args = ap.parse_args()
    data = Path(args.data)
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw = json.loads((data / "env_kuma.json").read_text(encoding="utf-8"))
    otsu_file = data / "otsu_bear.json"
    otsu = json.loads(otsu_file.read_text(encoding="utf-8")) if otsu_file.exists() else None
    prefs = {k: json.loads((data / f"{k}_kuma.json").read_text(encoding="utf-8"))
             for k in live_mod.LIVE_SOURCES if (data / f"{k}_kuma.json").exists()}
    cap_file = data / "env_capture_kuma.json"
    captures = json.loads(cap_file.read_text(encoding="utf-8")) if cap_file.exists() else None
    links_file = HERE / "links.json"
    links = json.loads(links_file.read_text(encoding="utf-8")) if links_file.exists() else {}
    try:
        files = render_site(raw, cfg, Path(args.out), release=args.release, links=links, otsu=otsu, prefs=prefs, captures=captures)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {args.out}")


if __name__ == "__main__":
    main()
