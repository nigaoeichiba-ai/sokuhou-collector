"""/season/ -- in which months do bears appear, prefecture by prefecture (the four complete fiscal years of the ministry's table).

Everything is computed from the ministry's monthly sighting counts that the build was given (the complete fiscal years only: the current year is
unfinished and the latest months are not published yet), so the page cannot disagree with the prefecture pages.  It says in which months a
prefecture's sightings have been concentrated, and how much the autumn varies from year to year; it does not say what this year will bring.
"""
from __future__ import annotations

from sites.kuma import charts
from sites.kuma.fmt import fy_label, n, table
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc

MIN_YEARLY = 50          # a prefecture needs at least this many sightings in each complete year to have a pattern worth reading
AUTUMN = (9, 10, 11)     # calendar months counted as autumn
QUIET_SHARE = 0.02       # a month with less than this share of the year is "almost none"


def complete_years(d: dict) -> list[str]:
    """The fiscal years before the current one (the ministry's table has every month of them)."""
    return [y for y in d["years"] if y != d["cur"]]


def month_order(d: dict) -> list[int]:
    return list(d["months"])        # April .. March


def pref_pattern(d: dict, r: dict) -> dict | None:
    """Per prefecture: the average share of each month, the peak month, the autumn share and its range over the years.  None if the data is too thin."""
    years = complete_years(d)
    months = month_order(d)
    per_year = []
    for y in years:
        vals = r["monthly"].get(y)
        if not vals or any(v is None for v in vals):
            return None
        per_year.append([int(v) for v in vals])
    totals = [sum(v) for v in per_year]
    if min(totals) < MIN_YEARLY:
        return None
    share = [sum(per_year[i][k] / totals[i] for i in range(len(years))) / len(years) for k in range(12)]
    peak = max(range(12), key=lambda k: share[k])
    autumn_idx = [months.index(m) for m in AUTUMN]
    autumn = [sum(per_year[i][k] for k in autumn_idx) for i in range(len(years))]
    autumn_share = sum(autumn[i] / totals[i] for i in range(len(years))) / len(years)
    return {"share": share, "peak": months[peak], "autumn_share": autumn_share, "autumn_min": min(autumn), "autumn_max": max(autumn),
            "autumn_by_year": dict(zip(years, autumn)), "yearly": dict(zip(years, totals)), "quiet": [months[k] for k in range(12) if share[k] < QUIET_SHARE]}


def national_pattern(d: dict) -> list[float]:
    years = complete_years(d)
    nat = d["national"]["monthly"]
    tot = {y: sum(int(v or 0) for v in nat[y]) for y in years}
    return [sum((nat[y][k] or 0) / tot[y] for y in years) / len(years) for k in range(12)]


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def season_page(page, d: dict, today, live: bool = True) -> str:
    years = complete_years(d)
    months = month_order(d)
    now = today.month
    nat = national_pattern(d)
    first, last = fy_label(years[0]), fy_label(years[-1])
    rows, thin = [], []
    for r in d["rows"]:
        p = pref_pattern(d, r)
        if p is None:
            if r["has"]:
                thin.append(r["name"])
            continue
        rows.append((r, p))
    rows.sort(key=lambda rp: -sum(rp[1]["yearly"].values()))
    tr = []
    for r, p in rows:
        k = months.index(now)
        tr.append([f'<a href="/{r["slug"]}/">{esc(r["name"])}</a>', f'{p["peak"]}月', pct(p["share"][k]), pct(p["autumn_share"]),
                   f'{n(p["autumn_min"])}〜{n(p["autumn_max"])}件', n(round(sum(p["yearly"].values()) / len(years)))])
    chart = charts.bars([f"{m}月" for m in months], [round(v * 100, 1) for v in nat],
                        title=f"全国の月別の出没件数(年間に占める割合・{first}〜{last}の平均)", desc="全国の月別の出没件数の、年間に占める割合(%)を、完全な4年度の平均で示したもの", uid="season")
    peak_nat = months[max(range(12), key=lambda k: nat[k])]
    live_link = 'と、<a href="/live/">自治体の最新の目撃情報</a>' if live else ""       # /live/ exists only with live data
    body = f"""{crumbs([("全国", "/"), ("出没の季節性", None)])}
<h1>クマの出没は、何月に多い?(都道府県別・{first}〜{last}の{len(years)}年度)</h1>
<p class="lead">環境省が公表している月別の出没件数のうち、<strong>月がそろっている{len(years)}年度({first}〜{last})</strong>を使って、「年間の出没の、何%が、何月に出ているか」を、都道府県ごとに出しました。全国では、<strong>{peak_nat}月</strong>が、いちばん多い月です(年間の{pct(max(nat))})。いまは{now}月で、全国の平均では、年間の{pct(nat[months.index(now)])}が、この月に出ています。</p>
<h2>全国の月別の割合</h2>
{chart}{table(["月"] + [f"{m}月" for m in months], [["年間に占める割合"] + [pct(v) for v in nat]])}
<h2>都道府県別(年間の出没が、毎年{MIN_YEARLY}件以上あるところ)</h2>
<p>「いまの月」は、{now}月が、年間の何%にあたるかです。「秋の件数」は、9〜11月の合計で、{len(years)}年度の最少から最多までを示しています。<strong>年による差が、大きい</strong>ことが、わかります。</p>
{table(["都道府県", "最も多い月", f"{now}月の割合", "9〜11月の割合", f"9〜11月の件数({len(years)}年度の幅)", "年間の出没件数(平均)"], tr)}
<h2>この表の読み方</h2>
<ul>
<li>「割合」は、年ごとに、その月の件数を、その年の年間の件数で割り、{len(years)}年度で平均したものです(件数の多い年に、引きずられないためです)。</li>
<li>これは、<strong>これまでの傾向</strong>です。今年が、同じになるとは、限りません。年によって、秋の件数は、大きく変わります(上の表の「幅」)。いま近くで出ているかは、<a href="/official/">公式のページ</a>{live_link}で、確認してください。</li>
<li>出没の数え方は、都道府県ごとに違います。県どうしの件数の大小は、そのまま比べられません。割合は、同じ県の中での、月ごとの比較に使ってください。</li>
{('<li>年間の出没が少なく、傾向を出していない都道府県: ' + esc('・'.join(thin)) + '。</li>') if thin else ''}
</ul>
<p class="notice">出典: 環境省「クマ類の出没情報について」の都道府県別・月別の件数(速報値)を、当サイトが集計して作成。環境省が作成したものではありません。使った年度の数字は、後から修正されることがあります。{esc(f"最新の公表: {d['sight_updated']}")}。</p>"""
    return page(path="/season/", title=f"クマの出没は何月に多い?都道府県別の月別の割合({first}〜{last})",
                description=f"環境省の月別の出没件数から、都道府県ごとに、年間の何%が何月に出ているかを出しました({first}〜{last}の{len(years)}年度)。全国では{peak_nat}月が最多。年による差も示しています。", body=body)
