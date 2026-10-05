"""クマ出没速報 (kuma-sokuho.com): a static site built from data/env_kuma.json (Ministry of the Environment).

    python sites/kuma/build.py [--release] [--out DIR]

Every number and every sentence about numbers is generated from the data, so a page cannot disagree with the table
it comes from.  The ministry's own cautions (provisional values; each prefecture counts sightings differently; which
months are in) are printed on every page that shows a comparison.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.kuma import charts, content  # noqa: E402
from sokuhou import prefectures as pf  # noqa: E402
from sokuhou.sitekit import BuildError, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

MINISTRY_PAGE = "https://www.env.go.jp/nature/choju/effort/effort12/effort12.html"
SOURCE_HTML = (f'出典: <a href="{MINISTRY_PAGE}" rel="noopener" target="_blank">環境省「クマに関する各種情報・取組」</a>の公表資料(速報値)を加工して作成。'
               "環境省が作成したものではありません。")
SITE = {
    "nav": [("全国", "/", "/"), ("ランキング", "/ranking/sightings/", "/ranking/"), ("推移", "/trend/", "/trend/"),
            ("緊急銃猟", "/emergency/", "/emergency/"), ("対処法", "/guide/", "/guide/"), ("通知", "/notify/", "/notify/")],
    "glyph": "&#128059;",
    "assets": HERE / "assets",
    "source_html": SOURCE_HTML,
}
WEEKDAY_SKIP = None
CAUTION = ("環境省が都道府県から聞き取った<strong>速報値</strong>で、後から修正されることがあります。"
           "出没数は、<strong>都道府県ごとに異なる方法</strong>で取りまとめられているため、都道府県どうしの数の大小は、そのまま比べられません。")


def n(v) -> str:
    return "-" if v is None else f"{v:,}"


def fy_label(y: str) -> str:
    """'R07' -> '令和7年度'."""
    return f"令和{int(y[1:])}年度"


def fy_start(y: str) -> int:
    return 2018 + int(y[1:])


def jp_date(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def md(iso: str) -> str:
    _, m, d = (int(x) for x in iso.split("-"))
    return f"{m}月{d}日"


def ratio_text(new: int, old: int) -> str:
    """'約2.5倍', '38%減', '同じ' -- from two counts, never typed by hand."""
    if not old:
        return "比べられません"
    if new == old:
        return "同じ"
    if new > old * 1.5:
        return f"約{new / old:.1f}倍"
    pct = round(abs(new - old) / old * 100)
    return f"{pct}%{'増' if new > old else '減'}"


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
        "inj": inj, "fatal": raw["fatal"], "emergency": raw["emergency"],
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

def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table{" class=" + cls if cls else ""}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def pref_link(r: dict) -> str:
    return f'<a href="/{r["slug"]}/">{esc(r["name"])}</a>'


def caution_box() -> str:
    return f'<p class="notice">{CAUTION}</p>'


def stat(label: str, big: str, sub: str, strong: bool = False) -> str:
    return f'<div class="stat{" strong" if strong else ""}"><span>{label}</span><b>{big}</b><span>{sub}</span></div>'


def page(cfg, preview, **kw):
    return layout(SITE, cfg, preview, alternates=(("更新のお知らせ", "/feed.xml"),), **kw)


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
    top_rows = "".join(f'<li>{pref_link(r)}<b>{n(r["total"][done])}件</b></li>' for r in top)
    emg_rows = "".join(f'<li>{md(c["date"])} {esc(c["prefecture"])}{esc(c["place"])}<b>{esc(c["species"])}</b></li>' for c in latest)
    guides = "".join(f'<a class="guide-card" href="/guide/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["lead"])}</span></a>'
                     for g in content.GUIDES)
    body = f"""<section class="hero">
<p class="eyebrow">環境省の速報値(都道府県からの聞き取り)</p>
<h1>クマ出没速報</h1>
<div class="hero-main"><div><span class="hero-sub">{fy_label(done)}の出没件数(全国)</span><b style="font-size:3rem;line-height:1.2">{n(total_done)}件</b></div>
<span class="hero-sub"><em>{fy_label(d['years'][-3])}({n(total_prev)}件)の{ratio_text(total_done, total_prev)}</em></span></div>
<ul class="hero-facts">
<li><span>{fy_label(done)}の人身被害</span><b>{n(i_done[0])}件・{n(i_done[1])}人(うち死亡{n(i_done[2])}人)</b></li>
<li><span>{fy_label(cur)}の出没({month_range(d)})</span><b>{n(ytd_cur)}件(前年度の同じ期間は{n(ytd_prev)}件・{ratio_text(ytd_cur, ytd_prev)})</b></li>
<li><span>{fy_label(cur)}の緊急銃猟</span><b>{n(len(emg['cases']))}件(死亡事故は{n(fatal['deaths'])}人、{jp_date(fatal['as_of'])}現在)</b></li>
</ul>
<a class="btn" href="/ranking/sightings/">都道府県別のランキングを見る</a>
</section>
<p class="notice" style="margin-top:12px">{freshness(d)}</p>
<h2>お住まいの地域の、最新の出没情報は</h2>
<p>環境省の数字は、公表までに時間がかかります。<strong>いま近くで出ているかどうかは、お住まいの都道府県・市町村の公式ページで確認してください。</strong>各道府県のページから、公式の出没情報へ案内します。</p>
<h2>{fy_label(done)}に出没が多かった道府県</h2>
<ul class="mini-list">{top_rows}</ul>
<p><a href="/ranking/sightings/">全国のランキング</a> / <a href="/ranking/change/">前年度の同じ期間との比較</a> / <a href="/ranking/injuries/">人身被害のランキング</a></p>
<h2>{fy_label(done)}は、出没が秋に集中しました</h2>
<p>全国の月別では、{d['peak_month']}月が最も多く({n(nat['monthly'][done][d['months'].index(d['peak_month'])])}件)でした。{fy_label(cur)}の月別も、公表が進み次第、追加します。</p>
{charts.lines([{"label": fy_label(y), "values": nat["monthly"][y], "cls": c, "strong": y == cur} for y, c in zip(d["years"], ("c0", "c1", "c2", "c3", "c4"))], [f"{m}月" for m in d["months"]], title="全国の月別の出没件数", desc="令和4年度から令和8年度までの、全国の月別の出没件数(件)", uid="home")}
<h2>最近の緊急銃猟({fy_label(cur)})</h2>
<ul class="mini-list">{emg_rows}</ul>
<p><a href="/emergency/">緊急銃猟と死亡事故の一覧</a></p>
<h2>クマに出会わないために</h2>
<div class="card-grid" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">{guides}</div>
<p class="notice">人身被害は、{fy_label(inj_max)}が、{n(inj[inj_max][1])}人で、表にある平成20年度以降で最も多くなっています。{CAUTION}</p>"""
    return page(cfg, preview, path="/", title=f"クマ出没速報 | 都道府県別の出没件数・人身被害・緊急銃猟(環境省の速報値)",
                description=f"{fy_label(done)}の全国のクマ出没は{n(total_done)}件。都道府県別のランキング、月別の推移、人身被害、緊急銃猟の一覧を、環境省の速報値からまとめています。",
                body=body)


def ranking_tabs(kind: str) -> str:
    tabs = [("sightings", "出没件数"), ("change", "前年度との比較"), ("injuries", "人身被害")]
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
        h1, lead = "クマの出没件数ランキング", f"{fy_label(done)}の出没件数が多い順に、並べています。{'と'.join(r['name'] for r in d['rows'] if not r['has'])}は、環境省の表に数値がありません(「-」)ので、載せていません。"
        extra = ""
    elif kind == "change":
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
{ranking_tabs(kind)}
{table(head, lines)}
{extra}{note}
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
        sight = f"""<div class="stats">{stat(f"{fy_label(done)}の出没件数", f"{n(r['total'][done])}件", f"39道府県中{r['rank']['done']}位", True)}{stat(f"{fy_label(prev)}", f"{n(r['total'][prev])}件", f"前年度との比: {ratio_text(r['total'][done], r['total'][prev])}")}{stat(f"{fy_label(cur)}({month_range(d)})", f"{n(r['ytd'][cur])}件", f"前年度の同じ期間: {n(r['ytd'][done])}件")}</div>
<p>{fy_label(done)}は、{d['months'][peak_i]}月が最も多く({n(r['monthly'][done][peak_i])}件)でした。</p>
<h2>月別の出没件数</h2>
{charts.lines([{"label": fy_label(y), "values": r["monthly"][y], "cls": c, "strong": y == cur} for y, c in zip((prev, done, cur), ("c1", "c3", "c4"))], [f"{m}月" for m in d["months"]], title=f"{r['name']}の月別の出没件数", desc=f"{r['name']}の月別の出没件数", uid="p")}
{table(["年度"] + [f"{m}月" for m in d["months"]] + ["合計"], [[fy_label(y)] + [n(r["monthly"][y][i]) for i in range(12)] + [n(r["total"][y])] for y in reversed(d["years"])])}"""
    else:
        sight = f"<p>環境省の出没件数の表には、{esc(r['name'])}の数値がありません(「-」)。人身被害の件数は、下に載せています。</p>"
    emg_html = ("<ul class='mini-list'>" + "".join(f'<li>{md(c["date"])} {esc(c["place"])}<b>{esc(c["species"])}</b></li>' for c in emg) + "</ul>") if emg else f"<p>環境省の{fy_label(cur)}の一覧には、{esc(r['name'])}の事例はありません(環境省が把握する事例に限ります)。</p>"
    fat_html = ("<ul class='mini-list'>" + "".join(f'<li>{jp_date(i["date"])} {esc(i["place"])}<b>{i["victims"]}人</b></li>' for i in sorted(fat, key=lambda i: i["date"], reverse=True)) + "</ul>") if fat else f"<p>環境省の資料(令和7・8年度)には、{esc(r['name'])}の死亡事故はありません。</p>"
    nav = "".join(f'<li><a href="/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in d["rows"] if x is not r)
    body = f"""{crumbs([("全国", "/"), ("ランキング", "/ranking/sightings/"), (r["name"], None)])}
<h1>{esc(r['name'])}のクマ出没({fy_label(done)}・環境省の速報値)</h1>
{sight}
<h2>人身被害</h2>
<p>{fy_label(done)}は、{n(i_done[0])}件・{n(i_done[1])}人(うち死亡{n(i_done[2])}人)で、39道府県中{r['rank']['injured']}位(人数)でした。令和元年度から{fy_label(done)}までの7年間の合計は、{n(r['injured7'])}人です。</p>
{charts.bars([y for y in d['inj']['years']], [r['inj'][y][1] for y in d['inj']['years']], title="人身被害の人数", desc=f"{r['name']}の人身被害の人数と死亡者数(平成20年度から)", uid="pi", marks=[r['inj'][y][2] for y in d['inj']['years']], marks_label="うち死亡者数")}
{injuries_table(d, r)}
<h2>{fy_label(cur)}の緊急銃猟</h2>
{emg_html}
<h2>クマによる死亡事故({fy_label(done)}・{fy_label(cur)})</h2>
{fat_html}
<h2>{esc(r['name'])}の公式の出没情報</h2>
<p>いま近くで出ているかは、公式の情報で確認してください。</p>
{off_html}
{caution_box()}
<h2>ほかの道府県</h2>
<ul class="pref-nav">{nav}</ul>
<p class="notice">{freshness(d)}</p>"""
    return page(cfg, preview, path=f"/{r['slug']}/", title=f"{r['name']}のクマ出没・人身被害({fy_label(done)}・環境省の速報値)",
                description=f"{r['name']}のクマの出没件数(月別)、人身被害、緊急銃猟、公式の出没情報への案内。環境省の速報値をもとにしています。", body=body)


def guide_hub(cfg: dict, preview: bool) -> str:
    cards = "".join(f'<a class="guide-card" href="/guide/{g["slug"]}/"><b>{esc(g["title"])}</b><span>{esc(g["lead"])}</span></a>' for g in content.GUIDES)
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
    entries.sort(reverse=True)
    body = "".join(
        f"<entry><id>tag:{host},{day}:{eid}</id><title>{esc(t)}</title><link href=\"{esc(base + path)}#u-{day}\"/>"
        f"<updated>{day}T00:00:00+09:00</updated><summary>{esc(s)}</summary></entry>\n" for day, eid, t, s, path in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja">\n'
            f"<id>tag:{host},2026:updates</id><title>{esc(cfg['site_name'])} 更新のお知らせ</title>"
            f'<link href="{esc(base)}/feed.xml" rel="self"/><link href="{esc(base)}/"/>'
            f"<updated>{entries[0][0]}T00:00:00+09:00</updated>\n{body}</feed>\n")


# ---------------------------------------------------------------- site

def render_site(raw: dict, cfg: dict, out: Path, release: bool = False, links: dict | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    d = prepare(raw)
    links = links or {}
    pages: dict[str, str | bytes] = {"index.html": index_page(d, cfg, preview)}
    for kind in ("sightings", "change", "injuries"):
        pages[f"ranking/{kind}/index.html"] = ranking_page(d, kind, cfg, preview)
    pages["trend/index.html"] = trend_page(d, cfg, preview)
    pages["emergency/index.html"] = emergency_page(d, cfg, preview)
    for r in d["rows"]:
        pages[f"{r['slug']}/index.html"] = pref_page(d, r, cfg, preview, links)
    pages["guide/index.html"] = guide_hub(cfg, preview)
    for g in content.GUIDES:
        pages[f"guide/{g['slug']}/index.html"] = guide_page(g, cfg, preview)
    pages["notify/index.html"] = notify_page(d, cfg, preview)
    pages["feed.xml"] = feed_xml(d, cfg)
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="クマの出没や人身被害に関する、環境省の公表データを、都道府県別・月別に整理して、暮らしの安全の判断に役立てていただくこと。",
        sources_html=f'環境省「クマに関する各種情報・取組」(<a href="{MINISTRY_PAGE}" rel="noopener" target="_blank">公表ページ</a>)の、出没情報・人身被害件数・緊急銃猟の実施状況・死亡事故の資料(いずれも速報値)',
        update_text="環境省の公表にあわせて、自動で更新します。各ページに、公表された日付と、どの月までのデータかを表示します。",
        disclaimer_html=("<p>掲載内容は、環境省が都道府県から聞き取った速報値を加工したもので、後から修正されることがあります。出没数は、都道府県ごとに異なる方法で取りまとめられています。"
                         "正確性・完全性・最新性を保証するものではありません。身近な出没情報は、お住まいの都道府県・市町村の公式の情報をご確認ください。</p>"
                         "<p>このサイトは、環境省が公表している情報を加工して作成したもので、環境省が作成したものではありません。クマ撃退スプレーなどの商品の効果を保証するものでもありません。</p>"),
        contact_notice="クマの目撃や被害の通報は、お住まいの市町村、または警察(110番)へお願いします。このサイトでは、通報や個別の相談を受け付けていません。",
        input_note="",
        finish=lambda s: s))
    pages.update(standard_files(pages, cfg, preview, d["fetched_date"]))
    for asset in sorted((HERE / "assets").iterdir()):
        pages[f"assets/{asset.name}"] = asset.read_text(encoding="utf-8")
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    args = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    raw = json.loads((ROOT / "data" / "env_kuma.json").read_text(encoding="utf-8"))
    links_file = HERE / "links.json"
    links = json.loads(links_file.read_text(encoding="utf-8")) if links_file.exists() else {}
    try:
        files = render_site(raw, cfg, Path(args.out), release=args.release, links=links)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {args.out}")


if __name__ == "__main__":
    main()
