"""/search/ -- find a municipality and see, for the sources this site holds, how many sightings it has this fiscal year and when the latest one was.

One table of every municipality of the stored sources (those with records and those with counts only), built from the same rows and counts as the
prefecture pages.  A small script (assets/finder.js) narrows the table while the visitor types; without it the page is the full list.
"""
from __future__ import annotations

import re

from sites.kuma.fmt import fy_label, md, n
from sites.kuma.live import ago_text, city_has_page, city_url, last30, pref_name
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc


def municipalities(d: dict, lv: dict) -> list[dict]:
    """One dict per municipality: name, prefecture, kind of source, this year's count, last 30 days (records only), latest date, page."""
    today = lv["today"]
    out: list[dict] = []
    for slug, cities in lv["by_pref"].items():
        pname = pref_name(slug)
        for city, rows in cities.items():
            out.append({"name": city, "pref": pname, "slug": slug, "mode": "records", "total": len(rows), "last30": last30(rows, today), "latest": rows[0]["at"][:10],
                        "url": city_url(slug, city) if city_has_page(rows) else f"/live/{slug}/"})
    for c in lv["counts"]:
        pname = pref_name(c["slug"])
        for city, k, latest in c["munis"]:
            out.append({"name": city, "pref": pname, "slug": c["slug"], "mode": "counts", "total": k, "last30": None, "latest": latest, "url": f"/live/{c['slug']}/"})
    out = [m for m in out if re.fullmatch(r".+[市町村区]", m["name"])]      # a place name that is not a municipality (e.g. 大台ヶ原) stays out of a list of municipalities
    out.sort(key=lambda m: (m["latest"], m["total"]), reverse=True)
    return out


def finder_page(page, d: dict, lv: dict) -> str:
    cur, today = d["cur"], lv["today"]
    ms = municipalities(d, lv)
    rows = []
    for m in ms:
        kind = "記録(一覧・地図)" if m["mode"] == "records" else "件数のみ"
        recent = n(m["last30"]) if m["last30"] is not None else "-"
        rows.append(f'<tr data-q="{esc(m["name"] + " " + m["pref"])}"><td><a href="{esc(m["url"])}">{esc(m["name"])}</a></td><td>{esc(m["pref"])}</td><td>{n(m["total"])}</td>'
                    f'<td>{recent}</td><td>{md(m["latest"])}({ago_text(m["latest"], today)})</td><td>{kind}</td></tr>')
    prefs = sorted({m["slug"] for m in ms}, key=lambda s: pf.SHORT.index(next(k for k, v in pf.SLUG.items() if v == s)))
    pref_names = "・".join(pref_name(s) for s in prefs)
    body = f"""{crumbs([("全国", "/"), ("市町村から探す", None)])}
<h1>市町村名から、クマの出没(公式)を調べる</h1>
<p class="lead">お住まいの市町村、行き先の市町村の名前を入れると、{fy_label(cur)}の記録の件数と、いちばん新しい日付が、わかります。自治体が公式に公表している情報だけを、{n(len(ms))}の市町村について、並べています({esc(pref_names)})。</p>
<form id="finder-tools" role="search" hidden>
<label>市町村・都道府県の名前 <input id="finder-q" type="search" name="q" autocomplete="off" placeholder="例: 盛岡、岩国、富山"></label>
<p id="finder-msg" class="muted" role="status"></p>
</form>
<div class="tablewrap"><table id="finder-table"><thead><tr><th>市町村</th><th>都道府県</th><th>{fy_label(cur)}の件数</th><th>直近30日</th><th>最新の日付</th><th>載せ方</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="notice">新しい日付の順に並べています。「直近30日」は、記録を載せている取得元だけです(件数だけの取得元は、「-」)。載っていない市町村は、「出没がない」「安全」という意味ではなく、<strong>このサイトが、その地域の取得元を、まだ持っていない</strong>ということです。公式のページへのリンクは、<a href="/official/">都道府県の公式の出没情報</a>に、取得元と数え方は、<a href="/cite/">データの出典・数え方・引用のしかた</a>にあります。取得元ごとに数え方が違うため、市町村どうしの件数は、そのまま比べられません。市町村ではない地名(山の名前など)で報告された分は、この表に入れていません。</p>
<script src="/assets/finder.js" defer></script>"""
    return page(path="/search/", title=f"市町村名から、クマの出没(公式)を調べる({n(len(ms))}市町村・{fy_label(cur)})",
                description=f"{n(len(ms))}の市町村について、自治体が公式に公表しているクマの出没の件数({fy_label(cur)})と最新の日付を、名前で探せます。", body=body)
