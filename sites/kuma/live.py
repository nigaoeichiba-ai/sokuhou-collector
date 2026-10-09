"""The "latest sightings" section of kuma-sokuho.com: one record list built from every published municipal source, and the pages made from it.

    /live/                       national feed (newest first), the sources, links to every prefecture
    /live/<pref>/                one prefecture: municipalities, newest records, monthly counts
    /live/<pref>/m-xxxxxx/       one municipality (only when it has MIN_CITY_ROWS records this fiscal year)
    /live/feed.xml               Atom feed of the newest records
    /map/ , /map/points.json     map of the last MAP_DAYS days (coordinates only where the source publishes them)

Every number on these pages is counted from the stored rows, so a page cannot disagree with its table.  What each source counts
(sightings only, or traces too) differs, so counts are never added up or compared across sources without saying so.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from urllib.parse import urlparse

from sites.kuma import charts
from sites.kuma.fmt import day_text, fy_label, jp_date, md, n, table
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc

MIN_CITY_ROWS = 3        # a municipality with fewer records is listed on its prefecture page but has no page of its own
RECENT_ROWS = 100        # rows listed on a prefecture page
CITY_ROWS = 60           # rows listed on a municipality page
FEED_ROWS = 60
HUB_ROWS = 50
MAP_DAYS = 90
FY_MONTHS = (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)

# One entry per published source.  key = the data file (data/<key>_kuma.json); "pref" = the prefecture's short name.
LIVE_SOURCES = {
    "miyagi": {"pref": "宮城", "license": "宮城県の規約(自由に二次利用可)", "name": "宮城県", "label": "宮城県・県の公式", "monthly_label": "目撃のほか、痕跡などを含む",
               "as_of_text": "データは{d}時点です"},
    "yamaguchi": {"pref": "山口", "license": "CC BY", "name": "山口県", "label": "山口県・県警の公式", "monthly_label": "山口県警察が認知した目撃のほか、痕跡などを含む",
                  "as_of_text": "データは{d}の分までです"},
    "okayama": {"pref": "岡山", "license": "公共データ利用規約(第1.0版)", "name": "岡山県", "label": "岡山県・県の公式。更新は不定期", "monthly_label": "種別の区別がなく、すべてを目撃として数えています",
                "as_of_text": "最新の記録は{d}の分までです(県の更新は不定期で、遅れて載ります)"},
    "yamanashi": {"pref": "山梨", "license": "山梨県オープンデータ利用規約(商用利用可・出典明記)", "name": "山梨県", "label": "山梨県・県の公式。ほぼ毎週更新", "monthly_label": "目撃の記録のみ",
                  "as_of_text": "最新の記録は{d}の分までです"},
    "sorachi": {"pref": "北海道", "scope": "空知管内の24市町のみ", "license": "CC-BY(北海道のサイトポリシー)", "name": "北海道空知総合振興局", "label": "北海道・空知総合振興局の公式(空知管内の24市町)", "monthly_label": "目撃のほか、痕跡などを含む(ヒグマの記録)",
                "as_of_text": "データは{d}時点です"},
    "toyama": {"pref": "富山", "license": "富山県自然保護課の許可(2026年10月・出典表記は不要)", "name": "富山県", "label": "富山県・県の公式(クマっぷ。位置は載せていません)", "coords": False, "monthly_label": "目撃のほか、痕跡や人身被害の報告を含む",
               "as_of_text": "最新の記録は{d}の分までです"},
    "akita": {"pref": "秋田", "license": "CC BY 4.0", "name": "秋田県", "label": "秋田県・県の公式。オープンデータは月1回ほど更新", "monthly_label": "目撃のほか、痕跡などを含む(クマの記録のみ)",
              "as_of_text": "最新の記録は{d}の分までです"},
}
# Sources without an explicit licence: counts only (mode "counts" in the stored file); no "license" key, so they never reach the CSV.
LIVE_SOURCES.update({
    "fukushima": {"pref": "福島", "name": "福島県", "label": "福島県・県の公式(件数のみ)", "monthly_label": "目撃のほか、痕跡や被害の報告を含む",
                  "as_of_text": "最新の記録は{d}の分までです"},
    "niigata": {"pref": "新潟", "name": "新潟県", "label": "新潟県・県の公式(件数のみ)", "monthly_label": "目撃のほか、痕跡や人身被害の報告を含む",
                "as_of_text": "最新の記録は{d}の分までです"},
    "yamagata": {"pref": "山形", "name": "山形県", "label": "山形県・県の公式データを集計(件数のみ)", "monthly_label": "クマ目撃マップの報告(人身被害を含む)",
                 "as_of_text": "最新の記録は{d}の分までです"},
    "aomori": {"pref": "青森", "name": "青森県", "label": "青森県「くまログあおもり」を集計(件数のみ)", "monthly_label": "県が確認した報告のみ(目撃のほか、痕跡などを含む)",
               "as_of_text": "最新の記録は{d}の分までです"},
    "nara": {"pref": "奈良", "name": "奈良県", "label": "奈良県・県の公式データを集計(件数のみ)", "monthly_label": "「クマ」と「クマらしき」の報告を合わせた件数",
             "as_of_text": "最新の記録は{d}の分までです"},
    "saitama": {"pref": "埼玉", "name": "埼玉県", "label": "埼玉県・県の公式データを集計(件数のみ)", "monthly_label": "市町村が県に報告した出没の件数",
                "as_of_text": "最新の記録は{d}の分までです"},
})
OTSU_PAGE = "https://www.city.otsu.lg.jp/soshiki/025/1605/g/t/74581.html"
OTSU_MAP = "https://www.google.com/maps/d/viewer?mid=1rE5HcSdJnm2gX3iT1FMt0aCVuQ9ArDs"
OTSU_CREDIT = "出典: 大津市が公開している、クマ出没マップ(ツキノワグマ目撃情報)を加工して作成。大津市が作成したものではありません"


def fy_of(day: str) -> str:
    y, m = int(day[:4]), int(day[5:7])
    return f"R{(y if m >= 4 else y - 1) - 2018:02d}"


def city_slug(pref_slug: str, city: str) -> str:
    """A stable ASCII URL name (the same prefecture and municipality always give the same address, with no list to maintain)."""
    return "m-" + hashlib.sha1(f"{pref_slug}/{city}".encode("utf-8")).hexdigest()[:6]


def norm_city(city: str) -> str:
    """'阿武郡阿武町' and '阿武町' are one municipality: the county prefix is dropped."""
    return re.sub(r"^[^市区町村]{1,5}郡(?=[^市区町村郡]+[町村]$)", "", city.strip())


def place_text(city: str, place: str) -> str:
    return place if city in place else f"{city}{place}"


# ---------------------------------------------------------------- records

def build_records(d: dict) -> list[dict]:
    """Every stored row of the current fiscal year, one dict each, newest first.  d = build.prepare() + live + live_prefs."""
    out: list[dict] = []
    for src in d["live_prefs"]:
        pref = LIVE_SOURCES[src["key"]]["pref"]
        for x in src["items"]:
            out.append({"src": src["key"], "pref": pref, "slug": pf.SLUG[pref], "city": norm_city(x["city"]), "place": x["place"],
                        "at": x["observed_at"], "kind": x["kind"], "count": x.get("count"), "lat": x.get("lat"), "lon": x.get("lon")})
    live = d.get("live")
    if live:
        for x in live["items"]:
            out.append({"src": "otsu", "pref": "滋賀", "slug": "shiga", "city": "大津市", "place": x["place"], "at": x["observed_at"],
                        "kind": "目撃", "count": None, "lat": x.get("lat"), "lon": x.get("lon")})
    cur = d["cur"]
    out = [r for r in out if fy_of(r["at"]) == cur]
    out.sort(key=lambda r: (r["at"], r["place"]), reverse=True)
    return out


def sources_info(d: dict) -> dict[str, dict]:
    """Per source: name, prefecture, as-of date, credit, source page, update note (what a reader needs to judge the numbers)."""
    out: dict[str, dict] = {}
    for src in d["live_prefs"]:
        out[src["key"]] = {"name": src["name"], "pref": LIVE_SOURCES[src["key"]]["pref"], "as_of": src["as_of"], "credit": src["credit"],
                           "page": src["page"], "note": src["update_note"], "monthly": src["monthly"], "monthly_label": src["monthly_label"],
                           "label": src["label"], "fetched": src["fetched_date"], "as_of_text": src["as_of_text"], "after": src["after"]}
    live = d.get("live")
    if live:
        last = live["items"][0]["observed_at"][:10]
        out["otsu"] = {"name": "滋賀県大津市", "pref": "滋賀", "as_of": last, "credit": OTSU_CREDIT, "page": OTSU_PAGE,
                       "note": "市の更新には、数日かかることがあります", "monthly": None, "monthly_label": "", "label": "大津市・市の公式",
                       "fetched": live["fetched_date"], "as_of_text": "最新の記録は{d}の分です", "after": 0}
    return out


def ago_text(day: str, today: date) -> str:
    k = (today - date.fromisoformat(day[:10])).days
    return "きょう" if k <= 0 else ("きのう" if k == 1 else f"{k}日前")


def group(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        out[r["slug"]][r["city"]].append(r)
    return out


def prepare_live(d: dict, today: date) -> dict:
    """today = the day the site is built (JST): "2 days ago" and "last 30 days" count from it, so a page never claims a stale 'today'."""
    records = build_records(d)
    infos = sources_info(d)
    return {"records": records, "infos": infos, "today": today, "by_pref": group(records), "counts": d.get("live_counts", [])}


def last30(rows: list[dict], today: date) -> int:
    lo = (today - timedelta(days=29)).isoformat()
    return sum(1 for r in rows if lo <= r["at"][:10] <= today.isoformat())


def city_has_page(rows: list[dict]) -> bool:
    return len(rows) >= MIN_CITY_ROWS


def city_url(slug: str, city: str) -> str:
    return f"/live/{slug}/{city_slug(slug, city)}/"


def pref_name(slug: str) -> str:
    short = next(k for k, v in pf.SLUG.items() if v == slug)
    return pf.full(short)


def kind_note(infos: dict, slug: str) -> str:
    names = [i["monthly_label"] for k, i in infos.items() if pf.SLUG[i["pref"]] == slug and i["monthly_label"]]
    return names[0] if names else ""


# ---------------------------------------------------------------- html pieces

def record_rows(rows: list[dict], with_pref: bool = False, with_city_link: bool = False, by_slug_cities: dict | None = None) -> str:
    lines = []
    for r in rows:
        place = esc(place_text(r["city"], r["place"]))
        if with_city_link and by_slug_cities is not None and city_has_page(by_slug_cities.get(r["slug"], {}).get(r["city"], [])):
            place = f'<a href="{city_url(r["slug"], r["city"])}">{esc(r["city"])}</a>' + esc(r["place"][len(r["city"]):] if r["place"].startswith(r["city"]) else r["place"])
        cells = [day_text(r["at"], year=True), (esc(pf.full(r["pref"])) + " " if with_pref else "") + place, esc(r["kind"])]
        lines.append(cells)
    return table(["日時", "場所", "種別"], lines)


def stat(label: str, big: str, sub: str, strong: bool = False) -> str:
    return f'<div class="stat{" strong" if strong else ""}"><span>{label}</span><b>{big}</b><span>{sub}</span></div>'


def stats_html(cur_rows: int, recent: int, latest: dict | None, today: date, fy: str, what: str = "記録") -> str:
    s = stat(f"{fy_label(fy)}の{what}", f"{n(cur_rows)}件", "公表された、すべての記録", True)
    s += stat("直近30日", f"{n(recent)}件", f"{md((today - timedelta(days=29)).isoformat())}から{md(today.isoformat())}まで")
    if latest:
        s += stat("最新の記録", md(latest["at"][:10]), ago_text(latest["at"], today))
    return f'<div class="stats">{s}</div>'


def source_notes(infos: dict, keys: list[str]) -> str:
    out = ""
    for k in keys:
        i = infos[k]
        where = "位置の座標は、地図にだけ使っています。" if LIVE_SOURCES.get(k, {}).get("coords", True) else "位置の座標は、載せていません。"
        out += (f'<p class="notice">{esc(i["credit"])}。{where}{esc(i["note"])}。取得日: {jp_date(i["fetched"])}。'
                f'公式ページは<a href="{esc(i["page"])}" rel="noopener" target="_blank">こちら</a>です。</p>\n')
    return out


CAUTION = ("自治体が公表した記録をそのまま並べています。通報から掲載まで日がかかること、同じ出没が重ねて通報されること、クマ以外の動物の見間違いが"
           "含まれることがあります。自治体ごとに、数える対象(目撃のみか、痕跡などを含むか)と更新の時期が違うため、<strong>自治体どうしの件数の大小は、"
           "そのまま比べられません</strong>。")


# ---------------------------------------------------------------- pages

def hub_page(page, d: dict, lv: dict) -> str:
    recs, infos, today = lv["records"], lv["infos"], lv["today"]
    cur = d["cur"]
    by_pref = lv["by_pref"]
    latest = recs[0] if recs else None
    src_rows = []
    for k, i in sorted(infos.items(), key=lambda kv: kv[1]["as_of"], reverse=True):
        slug = pf.SLUG[i["pref"]]
        rows = [r for r in recs if r["src"] == k]
        src_rows.append([f'<a href="/live/{slug}/">{esc(i["name"])}</a>', n(len(rows)), md(i["as_of"]) + "の分まで", esc(i["note"])])
    pref_links = "".join(
        f'<li><a href="/live/{slug}/">{esc(pref_name(slug))}</a><span>{n(sum(len(v) for v in cities.values()))}件</span></li>'
        for slug, cities in sorted(by_pref.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())))
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", None)])}
<h1>最新のクマの目撃情報(自治体の公式)</h1>
<p class="lead">環境省の数字は、公表まで1〜2か月かかります。ここでは、自治体が公式に公表している目撃情報を、取得できるところから順に載せています。いまは、{len(infos)}か所({'・'.join(i['name'] for i in infos.values())})です。</p>
{stats_html(len(recs), last30(recs, today), latest, today, cur)}
<p><a class="btn" href="/map/">地図で見る(現在地の近くを探す)</a>{' <a href="/data/">データ(CSV)をダウンロード</a>' if licensed_sources(lv) else ''}</p>
<h2>新しい順の記録(全国)</h2>
{record_rows(recs[:HUB_ROWS], with_pref=True, with_city_link=True, by_slug_cities=by_pref)}
<p class="notice">直近{HUB_ROWS}件です。道府県ごとの全件と、月別・市町村別は、下の道府県のページにあります。{CAUTION}</p>
<h2>道府県別(取得できたところ)</h2>
<ul class="mini-list">{pref_links}</ul>
<h2>取得元と、更新の状況</h2>
{table(["取得元", f"{fy_label(cur)}の記録", "最新", "更新について"], src_rows)}
{counts_section(lv)}<p class="notice">再利用の許可が明示されている取得元は、詳しい記録を載せ、明示されていない取得元は、件数と最新の日付だけを載せています。載っていない地域は、<a href="/ranking/sightings/">各道府県のページ</a>から、公式の出没情報へ進んでください。取得は、1日に数回、自動で行っています。</p>"""
    return page(path="/live/", title=f"クマの最新の目撃情報(自治体の公式・{len(infos)}か所・{fy_label(cur)})",
                description=f"{'・'.join(i['name'] for i in infos.values())}が公表しているクマの目撃情報を、新しい順に一覧にしています。{fy_label(cur)}の記録は{n(len(recs))}件です。",
                body=body, alternates=(("最新の目撃", "/live/feed.xml"),))


def counts_section(lv: dict) -> str:
    """The hub's block for the sources shown as counts only."""
    cs = lv.get("counts") or []
    if not cs:
        return ""
    rows = [[f'<a href="/live/{c["slug"]}/">{esc(c["name"])}</a>', n(c["total"]), md(c["latest"]) + "の分まで"] for c in cs]
    cur = cs[0]["fy"]
    return ("<h2>件数だけを載せている取得元</h2>\n<p>次の取得元は、件数と最新の日付だけを載せています(詳しい記録は、公式のページへ)。</p>\n"
            + table(["取得元", f"{fy_label(cur)}の件数", "最新"], rows) + "\n")


def month_counts(rows: list[dict]) -> dict[int, int]:
    c = Counter(int(r["at"][5:7]) for r in rows)
    return {m: c[m] for m in FY_MONTHS if c.get(m)}


def month_table(rows: list[dict]) -> str:
    mc = month_counts(rows)
    return table(["月", "記録"], [[f"{m}月", n(v)] for m, v in mc.items()])


def pref_live_page(page, d: dict, lv: dict, slug: str, links: dict) -> str:
    recs, infos, today = lv["records"], lv["infos"], lv["today"]
    cur = d["cur"]
    cities = lv["by_pref"][slug]
    rows = [r for r in recs if r["slug"] == slug]
    pname = pref_name(slug)
    keys = sorted({r["src"] for r in rows})
    names = "・".join(infos[k]["name"] for k in keys)
    note = kind_note(infos, slug)
    scopes = [LIVE_SOURCES[k]["scope"] for k in keys if LIVE_SOURCES.get(k, {}).get("scope")]
    scope = scopes[0] if scopes and len(scopes) == len(keys) else ""   # a prefecture page that covers only part of the prefecture says so
    pname_s = f"{pname}({scope})" if scope else pname
    city_rows = []
    for city, cr in sorted(cities.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        label = f'<a href="{city_url(slug, city)}">{esc(city)}</a>' if city_has_page(cr) else esc(city)
        city_rows.append([label, n(len(cr)), n(last30(cr, today)), md(cr[0]["at"][:10])])
    after = "".join(f'<p class="notice">{esc(infos[k]["name"])}の表には、日付が公表時点より後になっている記録が{infos[k]["after"]}件あります(入力の誤りの可能性があります)。一覧と件数からは除いています。</p>\n'
                    for k in keys if infos[k]["after"])
    published = "".join(f'<p>{esc(i["label"])}。{esc(i["as_of_text"].format(d=jp_date(i["as_of"])))}。</p>\n' for k, i in infos.items() if k in keys)
    official = links.get(next(k for k, v in pf.SLUG.items() if v == slug)) or []
    off_html = ("<ul class='link-list'>" + "".join(f'<li><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["label"])}</a></li>' for x in official) + "</ul>") if official else ""
    month_blocks = ""
    for k in keys:
        i = infos[k]
        mine = [r for r in rows if r["src"] == k]
        mc = month_counts(mine)
        chart = charts.bars([f"{m}月" for m in mc], list(mc.values()), title=f"{i['name']}の月別の記録", desc=f"{i['name']}が公表した{fy_label(cur)}の記録の月別の件数", uid=f"m{k}") if len(mc) >= 2 else ""
        month_blocks += f"<h3>{esc(i['name'])}</h3>\n{chart}{month_table(mine)}\n"
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", "/live/"), (pname, None)])}
<h1>{esc(pname_s)}のクマの目撃情報({fy_label(cur)}・{esc(names)}の公式)</h1>
<p class="lead">{esc(names)}が公表している{fy_label(cur)}の記録は、{n(len(rows))}件です{('(' + esc(note) + ')') if note else ''}。市町村ごとの件数と、新しい順の記録を載せています。</p>
{stats_html(len(rows), last30(rows, today), rows[0], today, cur)}
{published}{after}<h2>市町村別の記録({fy_label(cur)})</h2>
{table(["市町村", "記録", "直近30日", "最新"], city_rows)}
<p class="notice">記録が{MIN_CITY_ROWS}件以上の市町村には、その市町村のページがあります。</p>
<h2>新しい順の記録</h2>
{record_rows(rows[:RECENT_ROWS], with_city_link=True, by_slug_cities=lv["by_pref"])}
<p class="notice">直近{min(RECENT_ROWS, len(rows))}件です。{CAUTION}</p>
<h2>月別の記録</h2>
{month_blocks}<p><a href="/map/?pref={slug}">{esc(pname)}の目撃を地図で見る</a> ・ <a href="/{slug}/">{esc(pname)}の出没件数・人身被害(環境省)</a></p>
{('<h2>' + esc(pname) + 'の公式の出没情報</h2>' + off_html) if off_html else ''}
<p><a href="/live/{slug}/feed.xml">{esc(pname)}の最新の目撃(フィード)</a>を、フィードリーダーに登録すると、新しい記録が公表されるたびに届きます。</p>
{source_notes(infos, keys)}"""
    return page(path=f"/live/{slug}/", title=f"{pname_s}のクマの目撃情報({fy_label(cur)}・最新{n(len(rows))}件・市町村別)",
                description=f"{pname_s}の{fy_label(cur)}のクマの目撃情報{n(len(rows))}件を、新しい順・市町村別に一覧にしています。最新は{md(rows[0]['at'][:10])}の{place_text(rows[0]['city'], rows[0]['place'])}です。",
                body=body, alternates=((f"{pname}の最新の目撃", f"/live/{slug}/feed.xml"),))


def city_page(page, d: dict, lv: dict, slug: str, city: str, links: dict) -> str:
    infos, today = lv["infos"], lv["today"]
    cur = d["cur"]
    pname = pref_name(slug)
    rows = lv["by_pref"][slug][city]
    keys = sorted({r["src"] for r in rows})
    last = rows[0]
    recent = last30(rows, today)
    mc = month_counts(rows)
    peak_m = max(mc, key=lambda m: mc[m])
    others = [(c, cr) for c, cr in sorted(lv["by_pref"][slug].items(), key=lambda kv: (-len(kv[1]), kv[0])) if c != city and city_has_page(cr)][:12]
    other_html = ("<ul class='pref-nav'>" + "".join(f'<li><a href="{city_url(slug, c)}">{esc(c)}<span>{n(len(cr))}件</span></a></li>' for c, cr in others) + "</ul>") if others else ""
    chart = charts.bars([f"{m}月" for m in mc], list(mc.values()), title=f"{city}の月別の記録", desc=f"{city}の{fy_label(cur)}の記録の月別の件数", uid="cm") if len(mc) >= 2 else ""
    note = kind_note(infos, slug)
    with_count = [r for r in rows if r["count"]]
    head_extra = ""
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", "/live/"), (pname, f"/live/{slug}/"), (city, None)])}
<h1>{esc(city)}のクマの目撃情報({esc(pname)}・{fy_label(cur)})</h1>
<p class="lead">{esc(pname)}{esc(city)}で、{esc('・'.join(infos[k]['name'] for k in keys))}が公表した{fy_label(cur)}の記録は{n(len(rows))}件で、直近30日は{n(recent)}件です。最新は{md(last['at'][:10])}({ago_text(last['at'], today)})の「{esc(last['place'])}」です。</p>
{stats_html(len(rows), recent, last, today, cur)}
<p class="alert">最新の記録: {md(last['at'][:10])}({ago_text(last['at'], today)}) {esc(place_text(city, last['place']))}({esc(last['kind'])})</p>
<h2>{esc(city)}の月別の記録</h2>
<p>{fy_label(cur)}は、{peak_m}月が最も多く({n(mc[peak_m])}件)でした{('(' + esc(note) + ')') if note else ''}。</p>
{chart}{month_table(rows)}
<h2>新しい順の記録</h2>
{record_rows(rows[:CITY_ROWS])}
<p class="notice">{'直近' + str(CITY_ROWS) + '件です。' if len(rows) > CITY_ROWS else ''}{CAUTION}</p>
<p><a href="/map/?pref={slug}&amp;city={esc(city)}">{esc(city)}の目撃を地図で見る</a> ・ <a href="/live/{slug}/">{esc(pname)}の目撃情報</a> ・ <a href="/{slug}/">{esc(pname)}の出没件数・人身被害(環境省)</a></p>
{('<h2>' + esc(pname) + 'のほかの市町村</h2>' + other_html) if other_html else ''}
{source_notes(infos, keys)}"""
    return page(path=city_url(slug, city), title=f"{city}のクマ出没・目撃情報({pname}・{fy_label(cur)}・{n(len(rows))}件)",
                description=f"{pname}{city}のクマの目撃情報を、新しい順に一覧にしています。{fy_label(cur)}は{n(len(rows))}件(直近30日は{n(recent)}件)で、最新は{md(last['at'][:10])}です。",
                body=body, alternates=(("最新の目撃", "/live/feed.xml"),))


# ---------------------------------------------------------------- feed and map

def feed_xml(lv: dict, cfg: dict, slug: str | None = None) -> str:
    """The newest records as an Atom feed: every prefecture (slug=None) or one prefecture."""
    recs = [r for r in lv["records"] if slug is None or r["slug"] == slug][:FEED_ROWS]
    base = cfg["site_url"].rstrip("/")
    path = "/live/feed.xml" if slug is None else f"/live/{slug}/feed.xml"
    what = "最新の目撃情報(自治体の公式)" if slug is None else f"{pref_name(slug)}の最新の目撃情報(自治体の公式)"
    host = urlparse(base).hostname or "localhost"
    entries = ""
    for r in recs:
        eid = hashlib.sha1(f"{r['src']}|{r['at']}|{r['city']}|{r['place']}".encode("utf-8")).hexdigest()[:12]
        link = base + (city_url(r["slug"], r["city"]) if city_has_page(lv["by_pref"][r["slug"]][r["city"]]) else f"/live/{r['slug']}/")
        where = place_text(r["city"], r["place"])
        entries += (f"<entry><id>tag:{host},{r['at'][:10]}:{eid}</id><title>{esc(pf.full(r['pref']))}: {esc(where)}({esc(r['kind'])})</title>"
                    f'<link href="{esc(link)}"/><updated>{r["at"][:10]}T00:00:00+09:00</updated>'
                    f"<summary>{esc(day_text(r['at'], year=True))}、{esc(pf.full(r['pref']))}{esc(where)}で、{esc(r['kind'])}の記録が公表されています。</summary></entry>\n")
    updated = recs[0]["at"][:10] if recs else "2026-01-01"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja">\n'
            f"<id>tag:{host},2026:live{'' if slug is None else ':' + slug}</id><title>{esc(cfg['site_name'])} {esc(what)}</title>"
            f'<link href="{esc(base + path)}" rel="self"/><link href="{esc(base)}/live/{"" if slug is None else slug + "/"}"/>'
            f"<updated>{updated}T00:00:00+09:00</updated>\n{entries}</feed>\n")


def points_json(lv: dict) -> str:
    """[lat, lon, 'YYYY-MM-DD', kind, pref slug, city, place]: the last MAP_DAYS days that have coordinates, newest first."""
    lo = (lv["today"] - timedelta(days=MAP_DAYS)).isoformat()
    pts = [[r["lat"], r["lon"], r["at"][:10], r["kind"], r["slug"], r["city"], r["place"]]
           for r in lv["records"] if r["lat"] is not None and r["at"][:10] >= lo]
    prefs = {slug: pref_name(slug) for slug in sorted({p[4] for p in pts})}
    return json.dumps({"today": lv["today"].isoformat(), "days": MAP_DAYS, "prefs": prefs, "points": pts}, ensure_ascii=False, separators=(",", ":"))


def map_page(page, d: dict, lv: dict) -> str:
    infos = lv["infos"]
    pts = json.loads(points_json(lv))["points"]
    have = sorted({infos[k]["name"] for k in infos if any(r["lat"] is not None and r["src"] == k for r in lv["records"])})
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", "/live/"), ("地図", None)])}
<h1>クマの目撃マップ(自治体の公式・直近{MAP_DAYS}日)</h1>
<p class="lead">自治体が公表している目撃の位置を、地図に載せています。いまは、{esc('・'.join(have))}の{n(len(pts))}か所です。位置を公表していない自治体の記録は、地図に出ません。</p>
<div class="map-tools">
<button class="btn" type="button" id="near-btn" hidden>現在地の近くを探す</button>
<label>道府県 <select id="map-pref"><option value="">すべて</option></select></label>
<span id="near-msg" class="muted" role="status"></span>
</div>
<div id="kuma-map" class="map-box" role="region" aria-label="クマの目撃マップ"><p class="map-fallback">地図には JavaScript が必要です。下の一覧と、<a href="/live/">最新の目撃情報</a>をご覧ください。</p></div>
<div class="map-legend"><span><i class="m7"></i>7日以内</span><span><i class="m30"></i>8〜30日前</span><span><i class="m90"></i>31日より前</span></div>
<div id="near-list" hidden><h2>現在地の近くの記録</h2><div class="near-slot"></div><p class="notice">現在地は、この端末の中だけで使い、サイトには送りません。直線距離です。</p></div>
<p class="notice">地図の背景は、<a href="https://maps.gsi.go.jp/development/ichiran.html" rel="noopener" target="_blank">国土地理院の地理院タイル</a>です。位置は、自治体が公表した座標(小数点以下4桁に丸めたもの)で、実際の場所と、数十メートルほど違うことがあります。{CAUTION}</p>
{source_notes(infos, [k for k in infos if any(r["lat"] is not None and r["src"] == k for r in lv["records"])])}
<script src="/assets/leaflet.js"></script>
<script src="/assets/map.js" defer></script>"""
    return page(path="/map/", title=f"クマの目撃マップ(自治体の公式・直近{MAP_DAYS}日・{n(len(pts))}か所)",
                description=f"自治体が公表したクマの目撃の位置を、地図に載せています。現在地の近くの記録も探せます(位置は端末の中だけで使います)。", body=body,
                scripts=True, head_extra='<link rel="stylesheet" href="/assets/leaflet.css">\n')


# ---------------------------------------------------------------- open data download

CSV_NAME = "kuma-sightings.csv"
CSV_HEAD = ["取得元", "ライセンス・利用条件", "都道府県", "市町村", "場所", "日時", "種別", "頭数", "緯度", "経度"]


def licensed_sources(lv: dict) -> list[str]:
    """Sources whose own terms allow re-use with a credit (the city of Otsu publishes none, so its records are not offered for download)."""
    return [k for k in lv["infos"] if LIVE_SOURCES.get(k, {}).get("license")]


def csv_text(lv: dict) -> str:
    keys = set(licensed_sources(lv))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(CSV_HEAD)
    for r in lv["records"]:
        if r["src"] not in keys:
            continue
        i = lv["infos"][r["src"]]
        w.writerow([i["name"], LIVE_SOURCES[r["src"]]["license"], pf.full(r["pref"]), r["city"], r["place"], r["at"], r["kind"],
                    "" if r["count"] is None else r["count"], "" if r["lat"] is None else r["lat"], "" if r["lon"] is None else r["lon"]])
    return "\ufeff" + buf.getvalue()


def data_page(page, d: dict, lv: dict, base: str) -> str:
    cur = d["cur"]
    keys = licensed_sources(lv)
    rows_by = Counter(r["src"] for r in lv["records"])
    src_rows = [[esc(lv["infos"][k]["name"]), esc(LIVE_SOURCES[k]["license"]), n(rows_by[k]), esc(lv["infos"][k]["credit"])] for k in keys]
    skipped = [lv["infos"][k]["name"] for k in lv["infos"] if k not in keys]
    total = sum(rows_by[k] for k in keys)
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", "/live/"), ("データのダウンロード", None)])}
<h1>クマの目撃情報のデータ(CSV・{fy_label(cur)})</h1>
<p class="lead">自治体が公表しているクマの目撃情報のうち、<strong>再利用の条件が明示されている{len(keys)}か所</strong>の{fy_label(cur)}の記録{n(total)}件を、1つのCSVにまとめました。取得元・ライセンス・市町村名を、そろえてあります。</p>
<p><a class="btn" href="/data/{CSV_NAME}" download>CSVをダウンロード({n(total)}件)</a></p>
<h2>収録している取得元</h2>
{table(["取得元", "ライセンス・利用条件", f"{fy_label(cur)}の記録", "出典の表記"], src_rows)}
{('<p class="notice">次の取得元は、再利用の条件を確認できていないため、収録していません: ' + esc("・".join(skipped)) + '。</p>') if skipped else ''}
<h2>列の意味</h2>
<ul>
<li><strong>取得元・ライセンス</strong>: 各行の出どころと、その取得元が示している利用条件です。再利用するときは、その条件(多くは出典の表示)に従ってください。</li>
<li><strong>市町村</strong>: 郡の名前を除いて、そろえています(「阿武郡阿武町」は「阿武町」)。<strong>種別</strong>: 目撃・痕跡など、取得元の区分のままです。</li>
<li><strong>日時</strong>: 取得元が公表している日付(と、あれば時刻)です。<strong>緯度・経度</strong>: 取得元が公表している場合だけです(小数点以下4桁に丸めています)。</li>
</ul>
<p class="notice">{CAUTION}このCSVは、このサイトが各自治体の公開データを加工して作成したもので、各自治体が作成したものではありません。引用するときは、「出典:各自治体の公開データを加工して作成(クマ出没速報)」のように、元の取得元と、加工したことを書いてください。ファイルは、データが更新されるたびに作り直しています(取得日: {jp_date(lv['today'].isoformat())})。</p>"""
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"クマの目撃情報(自治体の公式・{fy_label(cur)})",
          "description": f"自治体が公表しているクマの目撃情報({len(keys)}か所・{total}件)の、取得元とライセンスつきの一覧", "inLanguage": "ja",
          "url": base + "/data/", "isAccessibleForFree": True,
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": base + "/data/" + CSV_NAME}]}
    head = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<" + chr(92) + "/") + "</script>" + chr(10)
    return page(path="/data/", head_extra=head, title=f"クマの目撃情報のデータ(CSV・{fy_label(cur)}・{len(keys)}か所・{n(total)}件)",
                description=f"自治体が公表しているクマの目撃情報(再利用の条件が明示されている{len(keys)}か所・{n(total)}件)を、取得元とライセンスつきのCSVにまとめています。", body=body)


# ---------------------------------------------------------------- sources without an explicit licence: counts and latest date only

COUNTS_NOTE = ("このサイトでは、件数と最新の日付だけを載せています。場所などの詳しい記録は、公式のページでご確認ください。"
               "掲載しているのは、公開されている情報から、このサイトが項目を抽出し、市町村別・月別に集計したもので、{name}が作成・保証したものではありません。"
               "日付や市町村が読めない行の割合の検査など、集計の検算は、このサイトで行っています。掲載の中止をご希望の場合は、<a href=\"/contact/\">お問い合わせ</a>からご連絡ください。")


def prepare_counts(prefs: dict | None) -> list[dict]:
    """The stored counts-only sources (mode 'counts') that are listed in LIVE_SOURCES and not stopped, newest data first."""
    from sokuhou.sources import kumalib
    out = []
    for key, meta in LIVE_SOURCES.items():
        raw = (prefs or {}).get(key)
        if not raw or raw.get("mode") != "counts" or key in kumalib.STOPPED:
            continue
        fy = raw["fy_current"]
        munis = [(city, sum(m["monthly"].get(fy, {}).values()), m["latest"]) for city, m in raw["municipalities"].items()
                 if m["monthly"].get(fy)]
        munis.sort(key=lambda x: (-x[1], x[0]))
        out.append({"key": key, "pref": meta["pref"], "slug": pf.SLUG[meta["pref"]], "name": meta["name"], "label": meta["label"], "fy": fy,
                    "total": raw["total_fy"], "monthly": raw["monthly"].get(fy, {}), "munis": munis, "as_of": raw["as_of"],
                    "credit": raw["credit"], "page": raw["source_page"], "note": raw["update_note"], "fetched": raw["fetched_at"][:10],
                    "latest": max((m[2] for m in munis), default=raw["as_of"])})
    out.sort(key=lambda c: c["as_of"], reverse=True)
    return out


def counts_page(page, d: dict, c: dict, today: date, links: dict) -> str:
    cur, slug, pname = c["fy"], c["slug"], pref_name(c["slug"])
    mc = {m: c["monthly"][str(m)] for m in FY_MONTHS if c["monthly"].get(str(m))}
    chart = charts.bars([f"{m}月" for m in mc], list(mc.values()), title=f"{c['name']}の月別の件数", desc=f"{c['name']}が公表した{fy_label(cur)}の件数の月別",
                        uid="cc") if len(mc) >= 2 else ""
    rows = [[esc(city), n(k), md(latest)] for city, k, latest in c["munis"]]
    short = next(k for k, v in pf.SLUG.items() if v == slug)
    official = links.get(short) or []
    off_html = ("<ul class='link-list'>" + "".join(f'<li><a href="{esc(x["url"])}" rel="noopener" target="_blank">{esc(x["label"])}</a></li>' for x in official) + "</ul>") if official else ""
    body = f"""{crumbs([("全国", "/"), ("最新の目撃情報", "/live/"), (pname, None)])}
<h1>{esc(pname)}のクマの目撃・出没の件数({fy_label(cur)}・{esc(c['name'])})</h1>
<p class="lead">{esc(c['name'])}が公表している{fy_label(cur)}の記録は、{n(c['total'])}件です。最新は{md(c['latest'])}({ago_text(c['latest'], today)})の分です。市町村別・月別の件数を載せています。</p>
<div class="stats">{stat(f"{fy_label(cur)}の件数", f"{n(c['total'])}件", "公表された、すべての記録", True)}{stat("最新の日付", md(c['latest']), ago_text(c['latest'], today))}</div>
<h2>市町村別の件数({fy_label(cur)})</h2>
{table(["市町村", "件数", "最新の日付"], rows)}
<h2>月別の件数</h2>
{chart}{table(["月", "件数"], [[f"{m}月", n(v)] for m, v in mc.items()])}
<h2>くわしい記録は、公式のページで</h2>
<p>いつ・どこで出たかの記録は、<a href="{esc(c['page'])}" rel="noopener" target="_blank">{esc(c['name'])}の公式ページ</a>でご確認ください。</p>
{off_html}<p class="notice">出典: <a href="{esc(c['page'])}" rel="noopener" target="_blank">{esc(c['name'])}の公開ページ</a>。{COUNTS_NOTE.format(name=esc(c['name']))}取得日: {jp_date(c['fetched'])}。{esc(c['note'])}。{CAUTION}</p>
<p><a href="/{slug}/">{esc(pname)}の出没件数・人身被害(環境省)</a></p>"""
    return page(path=f"/live/{slug}/", title=f"{pname}のクマの目撃・出没の件数({fy_label(cur)}・{n(c['total'])}件・市町村別)",
                description=f"{c['name']}が公表している{fy_label(cur)}のクマの目撃・出没の件数({n(c['total'])}件)を、市町村別・月別に整理しています。最新は{md(c['latest'])}の分です。", body=body)
