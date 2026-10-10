"""データ室: charts of gift prices and gift occasions, from two kinds of numbers.

  * the site's own products (the Rakuten items it shows, refreshed every day): what is actually sold at which price, how well it is reviewed, how it ships;
  * public statistics and one survey (content/stats.json, each with its source): how many babies and weddings there are, what people say they spend.

The charts are plain HTML and CSS bars (no script, no image): they scale to a phone, can be read by a screen reader, and every chart has its numbers as a table.
Every sentence that states a number is made from the data in this build, so it is true on the day it is published and changes with the data.
"""
from __future__ import annotations

from statistics import median

from sites.yorokobu import picking
from sokuhou.sitekit import crumbs, esc

BANDS = [("3,000円未満", 0, 2999), ("3,000〜4,999円", 3000, 4999), ("5,000〜6,999円", 5000, 6999), ("7,000〜9,999円", 7000, 9999), ("10,000円以上", 10000, None)]
MIN_PRODUCTS = 20      # fewer products than this on a page: no chart (a chart of five items is an anecdote)
MIN_ROWS = 5           # a range chart needs at least this many events (and people) with enough products
MIN_PER_ROW = 8


def _b():
    from sites.yorokobu import build
    return build


def yen(v: float) -> str:
    return f"{round(v):,}円"


# ---------------------------------------------------------------- the data

def all_products(d: dict) -> list[dict]:
    """Every distinct product on any page of the site, once."""
    seen: dict[str, dict] = {}
    B = _b()
    for key in sorted(d["pairs"]):
        for it in B.pair_items(d, key)[2]:
            seen.setdefault(it["code"], it)
    return list(seen.values())


def products_of_occasion(d: dict, occasion: str) -> list[dict]:
    seen: dict[str, dict] = {}
    B = _b()
    for p in d["c"]["pairs"]:
        if p["occasion"] == occasion:
            for it in B.pair_items(d, B.ct.pair_key(p))[2]:
                seen.setdefault(it["code"], it)
    return list(seen.values())


def products_of_recipient(d: dict, recipient: str) -> list[dict]:
    seen: dict[str, dict] = {}
    B = _b()
    for p in d["c"]["pairs"]:
        if p["recipient"] == recipient:
            for it in B.pair_items(d, B.ct.pair_key(p))[2]:
                seen.setdefault(it["code"], it)
    return list(seen.values())


def in_band(price: int, lo: int, hi: int | None) -> bool:
    return price >= lo and (hi is None or price <= hi)


def band_stats(items: list[dict]) -> list[dict]:
    out = []
    for label, lo, hi in BANDS:
        xs = [i for i in items if in_band(i["price"], lo, hi)]
        out.append({"label": label, "n": len(xs), "share": len(xs) / len(items) * 100 if items else 0.0,
                    "rating": median(i["rating"] for i in xs) if xs else None,
                    "reviews": median(i["reviews"] for i in xs) if xs else None,
                    "ship": sum(1 for i in xs if i["free_shipping"]) / len(xs) * 100 if xs else None,
                    "gift": sum(1 for i in xs if i.get("gift")) / len(xs) * 100 if xs else None})
    return out


def quartiles(xs: list[int]) -> tuple[float, float, float]:
    s = sorted(xs)
    n = len(s)

    def at(q: float) -> float:
        pos = (n - 1) * q
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        return s[lo] + (s[hi] - s[lo]) * (pos - lo)
    return at(.25), at(.5), at(.75)


# ---------------------------------------------------------------- chart parts (HTML and CSS)

def _pct(v: float, top: float) -> str:
    return f"{max(0.0, min(100.0, v / top * 100)):.1f}"


def hbars(rows: list[tuple[str, float, str]], top: float | None = None, series_class: str = "s1") -> str:
    """Horizontal bars: rows of (label, value, text shown at the end of the bar)."""
    top = top or max((v for _, v, _ in rows), default=1) or 1
    body = "".join(f'<div class="hb-row"><span class="hb-l">{esc(l)}</span><span class="hb-track"><i class="hb-fill {series_class}" style="width:{_pct(v, top)}%"></i></span>'
                   f'<span class="hb-v">{esc(t)}</span></div>' for l, v, t in rows)
    return f'<div class="hb">{body}</div>'


def grouped(rows: list[tuple[str, list[tuple[str, float, str]]]], legend: list[str], top: float) -> str:
    """Bars in groups: rows of (label, [(series name, value, text)]); the series colours follow the legend order."""
    leg = "".join(f'<li><i class="hb-fill s{i + 1}"></i>{esc(n)}</li>' for i, n in enumerate(legend))
    body = ""
    for label, vals in rows:
        bars = "".join(f'<span class="hb-line"><span class="hb-track"><i class="hb-fill s{i + 1}" style="width:{_pct(v, top)}%"></i></span><span class="hb-v">{esc(t)}</span></span>'
                       for i, (_, v, t) in enumerate(vals))
        body += f'<div class="hb-row multi"><span class="hb-l">{esc(label)}</span><span class="hb-lines">{bars}</span></div>'
    return f'<ul class="hb-legend">{leg}</ul><div class="hb">{body}</div>'


def ranges(rows: list[tuple[str, str, float, float, float, str]], top: float) -> str:
    """Price ranges: rows of (label, href, p25, median, p75, text).  The pale bar is the middle half of the prices, the tick is the median."""
    body = ""
    for label, href, a, m, b, t in rows:
        left = float(_pct(a, top))
        width = max(1.2, float(_pct(b, top)) - left)
        body += (f'<div class="hb-row"><a class="hb-l" href="{esc(href)}">{esc(label)}</a><span class="hb-track">'
                 f'<i class="rg-fill" style="left:{left:.1f}%;width:{width:.1f}%"></i><i class="rg-med" style="left:{_pct(m, top)}%"></i></span>'
                 f'<span class="hb-v">{esc(t)}</span></div>')
    return f'<div class="hb">{body}</div>'


def columns(series: dict[str, int], unit_div: int = 1000, every: int = 4) -> str:
    """Columns for a yearly series; the year is written under every `every`-th column, the first, the last and the highest one carry their value."""
    years = sorted(series)
    top = max(series.values())
    peak = max(years, key=lambda y: series[y])
    cols = ""
    for i, y in enumerate(years):
        v = series[y]
        show = y in (years[0], years[-1], peak)
        val = f'<b>{v / unit_div:,.0f}</b>' if show else ""
        yr = f'<small>{y}</small>' if (i % every == 0 or y == years[-1]) else "<small>&nbsp;</small>"
        cols += f'<span class="vc-col" title="{y}年 {v:,}"><span class="vc-v">{val}</span><i style="height:{v / top * 100:.1f}%"></i>{yr}</span>'
    return f'<div class="vc" role="presentation">{cols}</div>'


def table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<details class="chart-data"><summary>数値の表を見る</summary><div class="tablewrap"><table class="gift-days"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div></details>'


def figure(title: str, inner: str, caption: str, data: str = "") -> str:
    return f'<figure class="chart"><h3>{esc(title)}</h3>{inner}{data}<figcaption>{caption}</figcaption></figure>'


def own_source(d: dict, n: int) -> str:
    return f'出典: 当サイトが楽天ウェブサービスから取得した商品データ({n:,}点、{d["fetched_label"]}時点)。当サイトで取り上げた商品の数字で、楽天市場の全体ではありません。'


def stat_source(s: dict) -> str:
    return f'出典: <a href="{esc(s["url"])}" rel="noopener nofollow" target="_blank">{esc(s["source"])}</a>'


# ---------------------------------------------------------------- pages

def _page(d: dict, cfg: dict, preview: bool, path: str, title: str, h1: str, lead: str, body: str, crumb: str) -> str:
    B = _b()
    html = f"""{B.head_band("sky", "", h1, lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("データ室", "/data/"), (crumb, None)] if path != "/data/" else [("トップ", "/"), ("データ室", None)])}</div>
{body}
<p class="notice" style="margin-top:44px">数字は、調べた時点のものです。商品の価格・在庫・レビューは変わります。調査の数字は、調査の対象や方法によって異なり、すべての人にあてはまるものではありません。</p>"""
    return B.page(cfg, preview, path=path, title=f"{title} | {cfg['site_name']}", description=lead[:110], body=html, og_image=B.og_for("default"))


def price_bands(d: dict) -> tuple | None:
    items = all_products(d)
    if len(items) < MIN_PRODUCTS:
        return None
    st = band_stats(items)
    have = [s for s in st if s["n"] >= 3]
    if len(have) < 3:
        return None
    best_rating = max(have, key=lambda s: s["rating"])
    most = max(st, key=lambda s: s["n"])
    best_ship = max(have, key=lambda s: s["ship"])
    best_gift = max(have, key=lambda s: s["gift"])
    lead = f"当サイトが取り上げている楽天市場の商品{len(items):,}点を、価格帯で分けて、レビューの評価、送料無料、ギフト対応の割合を比べました。毎日、更新しています。"
    c1 = figure("価格帯ごとの、商品の数", hbars([(s["label"], s["n"], f'{s["n"]:,}点({s["share"]:.0f}%)') for s in st]),
                own_source(d, len(items)), table(["価格帯", "商品の数", "割合"], [[s["label"], f'{s["n"]:,}', f'{s["share"]:.1f}%'] for s in st]))
    c2 = figure("送料無料の商品の割合", hbars([(s["label"], s["ship"] or 0, f'{s["ship"]:.0f}%' if s["ship"] is not None else "—") for s in st], top=100, series_class="s2"),
                "各価格帯の商品のうち、送料無料の表示がある商品の割合。" + own_source(d, len(items)),
                table(["価格帯", "送料無料の割合"], [[s["label"], f'{s["ship"]:.1f}%' if s["ship"] is not None else "—"] for s in st]))
    c3 = figure("ギフト対応の商品の割合", hbars([(s["label"], s["gift"] or 0, f'{s["gift"]:.0f}%' if s["gift"] is not None else "—") for s in st], top=100, series_class="s3"),
                "各価格帯の商品のうち、ギフト包装などのギフト対応の表示がある商品の割合。" + own_source(d, len(items)),
                table(["価格帯", "ギフト対応の割合"], [[s["label"], f'{s["gift"]:.1f}%' if s["gift"] is not None else "—"] for s in st]))
    tbl = table(["価格帯", "商品の数", "評価の中央値", "レビュー件数の中央値", "送料無料", "ギフト対応"],
                [[s["label"], f'{s["n"]:,}', f'{s["rating"]:.2f}' if s["rating"] else "—", f'{s["reviews"]:,.0f}' if s["reviews"] is not None else "—",
                  f'{s["ship"]:.0f}%' if s["ship"] is not None else "—", f'{s["gift"]:.0f}%' if s["gift"] is not None else "—"] for s in st])
    notes = [f"商品がいちばん多い価格帯は、{most['label']}({most['n']:,}点)です。",
             f"レビュー評価の中央値がいちばん高いのは、{best_rating['label']}で{best_rating['rating']:.2f}です。",
             f"送料無料の割合がいちばん高いのは{best_ship['label']}({best_ship['ship']:.0f}%)、ギフト対応の割合がいちばん高いのは{best_gift['label']}({best_gift['gift']:.0f}%)です。"]
    if best_gift["gift"] - min(s["gift"] for s in have) >= 10:
        low = min(have, key=lambda s: s["gift"])
        notes.append(f"{low['label']}の商品は、ギフト対応の割合が{low['gift']:.0f}%にとどまります。包装やのしが必要なときは、商品ページで確認してください。")
    body = (f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in notes)}</ul></section>'
            f'{c1}{c2}{c3}<section class="data-notes"><h2>数字の一覧</h2>{tbl}</section>'
            '<section class="data-notes"><h2>見かたの注意</h2><p>評価は、レビューが付いた商品のなかでの中央値です。レビューの件数が少ない商品は、評価が高く出やすい傾向があります。'
            '価格が高いほど評価が高いとも、低いとも、この数字だけでは言えません。商品選びの目安のひとつとして、お使いください。</p></section>')
    teaser = f"評価の中央値がいちばん高いのは、{best_rating['label']}({best_rating['rating']:.2f})"
    return "/data/price-bands/", "価格帯でみる、プレゼントの失敗しにくさ", lead, body, "価格帯でみる、失敗しにくさ", teaser


def occasion_prices(d: dict) -> tuple | None:
    B = _b()
    c = d["c"]
    rows_o, rows_r = [], []
    for o in c["occasions"]:
        xs = [i["price"] for i in products_of_occasion(d, o["slug"])]
        if len(xs) >= MIN_PER_ROW:
            a, m, b = quartiles(xs)
            rows_o.append((o["name"], f'/occasion/{o["slug"]}/', a, m, b, len(xs)))
    for r in c["recipients"]:
        xs = [i["price"] for i in products_of_recipient(d, r["slug"])]
        if len(xs) >= MIN_PER_ROW:
            a, m, b = quartiles(xs)
            rows_r.append((r["name"], f'/for/{r["slug"]}/', a, m, b, len(xs)))
    if len(rows_o) < MIN_ROWS or len(rows_r) < MIN_ROWS:
        return None
    cap = 20000.0
    rows_o.sort(key=lambda r: r[3])
    rows_r.sort(key=lambda r: r[3])

    def fmt(r):
        return (r[0], r[1], min(r[2], cap), min(r[3], cap), min(r[4], cap), f"{yen(r[3])}({r[5]}点)")
    sub = "濃い印が中央値、薄い帯が、価格の真ん中の半分(下から25%〜75%)の範囲です。右端は2万円で切っています。"
    cho = figure("イベントごとの、価格の目安", ranges([fmt(r) for r in rows_o], cap), sub + " " + own_source(d, len(all_products(d))),
                 table(["イベント", "商品の数", "下から25%", "中央値", "下から75%"], [[r[0], str(r[5]), yen(r[2]), yen(r[3]), yen(r[4])] for r in rows_o]))
    chr_ = figure("贈る相手ごとの、価格の目安", ranges([fmt(r) for r in rows_r], cap), sub + " " + own_source(d, len(all_products(d))),
                  table(["贈る相手", "商品の数", "下から25%", "中央値", "下から75%"], [[r[0], str(r[5]), yen(r[2]), yen(r[3]), yen(r[4])] for r in rows_r]))
    hi_o, lo_o = rows_o[-1], rows_o[0]
    hi_r, lo_r = rows_r[-1], rows_r[0]
    notes = [f"イベントでは、中央値がいちばん高いのは「{hi_o[0]}」の{yen(hi_o[3])}、いちばん低いのは「{lo_o[0]}」の{yen(lo_o[3])}です。",
             f"贈る相手では、中央値がいちばん高いのは「{hi_r[0]}」の{yen(hi_r[3])}、いちばん低いのは「{lo_r[0]}」の{yen(lo_r[3])}です。"]
    lead = "楽天市場で、イベントや贈る相手ごとに、どのくらいの価格の商品が選ばれやすいか。当サイトが取り上げている商品の価格を、中央値と、真ん中の半分の範囲で見せます。毎日、更新しています。"
    body = (f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in notes)}</ul></section>{cho}{chr_}'
            '<section class="data-notes"><h2>見かたの注意</h2><p>ここにあるのは、「売られている商品の価格」です。「贈るときにかける予算」とは、同じではありません。予算の調査は、'
            '<a href="/data/mothers-day-budget/">母の日の予算と、商品の価格</a>で見られます。</p></section>')
    return "/data/occasion-prices/", "イベント別・相手別の、価格の目安", lead, body, "イベント別・相手別の価格", f"中央値がいちばん高いのは「{hi_o[0]}」({yen(hi_o[3])})"


def mothers_day_budget(d: dict) -> tuple | None:
    s = (d["c"].get("stats") or {}).get("survey_budget", {}).get("mothers-day")
    if not s:
        return None
    years = sorted(s["years"])
    latest = years[-1]
    now = s["years"][latest]
    top_i = max(range(len(now)), key=lambda i: now[i])
    rows = [(band, [(y, s["years"][y][i], f'{s["years"][y][i]:.1f}%') for y in years]) for i, band in enumerate(s["bands"])]
    c1 = figure(f'{s["title"]}の、年ごとの変化', grouped(rows, [f"{y}年" for y in years], top=max(max(v) for v in s["years"].values())),
                stat_source(s) + f'。{esc(s["method"])}。',
                table(["予算"] + [f"{y}年" for y in years], [[b] + [f'{s["years"][y][i]:.1f}%' for y in years] for i, b in enumerate(s["bands"])]))
    notes = [f"{latest}年の調査で、いちばん多い予算は{s['bands'][top_i]}({now[top_i]:.1f}%)です。",
             f"5,000円未満は{now[0] + now[1]:.1f}%、10,000円以上は{now[-1]:.1f}%でした。"]
    if len(years) >= 2 and s["years"][years[0]][-1] < now[-1]:
        notes.append(f"10,000円以上の割合は、{years[0]}年の{s['years'][years[0]][-1]:.1f}%から、{latest}年の{now[-1]:.1f}%へと増えています。")
    body = ""
    items = products_of_occasion(d, "mothers-day")
    prod_note = ""
    if len(items) >= MIN_PRODUCTS:
        bs = band_stats(items)
        share = [b["share"] for b in bs]
        rows2 = [(band, [(f"{latest}年の調査", now[i], f"{now[i]:.0f}%"), ("当サイトの商品", share[i], f"{share[i]:.0f}%")]) for i, band in enumerate(s["bands"])]
        c2 = figure("調査の予算と、売られている商品の価格", grouped(rows2, [f"{latest}年の予算の調査", f"母の日の商品の価格({len(items)}点)"], top=max(max(now), max(share))),
                    stat_source(s) + f'。商品は、{own_source(d, len(items))[4:]}',
                    table(["価格帯", f"{latest}年の予算の調査", "当サイトの商品の割合"], [[b, f"{now[i]:.1f}%", f"{share[i]:.1f}%"] for i, b in enumerate(s["bands"])]))
        gap = max(range(len(now)), key=lambda i: share[i] - now[i])
        gap_n = max(range(len(now)), key=lambda i: now[i] - share[i])
        if share[gap] - now[gap] >= 5:
            notes.append(f"当サイトの母の日の商品は、{s['bands'][gap]}の割合が{share[gap]:.0f}%で、予算の調査({now[gap]:.0f}%)より多くなっています。")
        if now[gap_n] - share[gap_n] >= 5:
            notes.append(f"{s['bands'][gap_n]}は、予算の調査では{now[gap_n]:.0f}%と多いのに、当サイトの商品は{share[gap_n]:.0f}%です。この価格帯の商品は、相対的に少なめです。")
        prod_note = c2
    body = (f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in notes)}</ul></section>{c1}{prod_note}'
            '<section class="data-notes"><h2>見かたの注意</h2><p>調査は、インターネットで答えた人の数字で、日本中の人の平均ではありません。予算は「かけようと思っている金額」で、実際に使った金額とは限りません。'
            '母の日のプレゼントは、<a href="/occasion/mothers-day/">母の日のページ</a>から探せます。</p></section>')
    lead = "母の日のプレゼントに、みんなはいくらかけようとしているのか。日比谷花壇の調査の3年分の変化と、楽天市場で売られている商品の価格を、並べて見ます。"
    return "/data/mothers-day-budget/", "母の日の予算と、商品の価格", lead, body, "母の日の予算", f"母の日の予算は{s['bands'][top_i]}が最多({now[top_i]:.0f}%)"


def births_marriages(d: dict) -> tuple | None:
    v = (d["c"].get("stats") or {}).get("vital")
    if not v or "births" not in v or "marriages" not in v:
        return None
    b, m = v["births"], v["marriages"]
    by, my = sorted(b["series"]), sorted(m["series"])
    b0, b1 = b["series"][by[0]], b["series"][by[-1]]
    m0, m1 = m["series"][my[0]], m["series"][my[-1]]
    fig_b = figure(f'{b["label"]}の移り変わり({by[0]}〜{by[-1]}年、単位: 千{b["unit"]})', columns(b["series"]), stat_source(b) + f'。{esc(b.get("note", ""))}。',
                   table(["年", f'{b["label"]}({b["unit"]})'], [[y, f'{b["series"][y]:,}'] for y in by]))
    fig_m = figure(f'{m["label"]}の移り変わり({my[0]}〜{my[-1]}年、単位: 千{m["unit"]})', columns(m["series"]), stat_source(m) + f'。{esc(m.get("note", ""))}。',
                   table(["年", f'{m["label"]}({m["unit"]})'], [[y, f'{m["series"][y]:,}'] for y in my]))
    notes = [f"{b['label']}は、{by[0]}年の{b0 / 10000:.0f}万人から、{by[-1]}年の{b1 / 10000:.0f}万人へ、{(1 - b1 / b0) * 100:.0f}%減りました。",
             f"{m['label']}は、{my[0]}年の{m0 / 10000:.0f}万組から、{my[-1]}年の{m1 / 10000:.0f}万組へ、{(1 - m1 / m0) * 100:.0f}%減りました。"]
    occ = d["c"]["occ"]
    btns = "".join(f'<a class="btn" href="/occasion/{k}/">{n}</a>' for k, n in (("birth-gift", "出産祝い"), ("wedding-gift", "結婚祝い")) if k in occ)
    links = f'<section class="data-notes"><h2>祝いの贈り物を、探す</h2><p class="more">{btns}</p></section>' if btns else ""
    body = (f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in notes)}</ul>'
            '<p>出産祝いや結婚祝いを贈る機会は、全体としては少なくなっています。それだけに、贈るときは、相手の暮らしに合うものを、ていねいに選びたいところです。</p></section>'
            f'{fig_b}{fig_m}{links}')
    lead = "出産祝い、結婚祝いを贈る機会は、どのくらいあるのか。国の統計で、出生数と婚姻件数の移り変わりを見ます。"
    return "/data/births-marriages/", "出産祝い・結婚祝いの機会の移り変わり", lead, body, "出生数と婚姻件数", f"出生数は{by[0]}年から{(1 - b1 / b0) * 100:.0f}%減"


def ranking_prices(d: dict) -> tuple | None:
    rv = d.get("ranking")
    if not rv:
        return None
    segs = [(rv["segments"][s]["label"], rv["segments"][s]["facts"], s) for s in rv["order"] if rv["segments"][s]["kind"] == "people" and rv["segments"][s]["facts"]]
    if len(segs) < 4:
        return None
    segs.sort(key=lambda t: t[1]["median"])
    day = _b().rk.date_label(rv["date"])
    top = max(f["median"] for _, f, _ in segs)
    c1 = figure("世代・性別ごとの、売れ筋の価格(中央値)", hbars([(lab, f["median"], yen(f["median"])) for lab, f, _ in segs], top=top),
                f'出典: 楽天市場のランキング({day})から、贈り物向きの商品だけを集めた、当サイトの集計。', table(["世代・性別", "商品の数", "価格の中央値", "3,000円以下", "10,000円以上"],
                [[lab, str(f["n"]), yen(f["median"]), str(f["le3000"]), str(f["ge10000"])] for lab, f, _ in segs]))
    share = [(lab, f["le3000"] / f["n"] * 100, f"{f['le3000'] / f['n'] * 100:.0f}%") for lab, f, _ in segs]
    c2 = figure("3,000円以下の商品の割合", hbars(share, top=100, series_class="s2"), f'売れ筋の商品のうち、3,000円以下のものの割合。出典: 楽天市場のランキング({day})から、当サイトが集計。',
                table(["世代・性別", "3,000円以下の割合"], [[lab, t] for lab, _, t in share]))
    hi, lo = segs[-1], segs[0]
    notes = [f"売れ筋の価格の中央値がいちばん高いのは「{hi[0]}」の{yen(hi[1]['median'])}、いちばん低いのは「{lo[0]}」の{yen(lo[1]['median'])}です。"]
    body = (f'<section class="data-notes"><h2>わかったこと</h2><ul>{"".join(f"<li>{esc(n)}</li>" for n in notes)}</ul></section>{c1}{c2}'
            '<section class="data-notes"><h2>見かたの注意</h2><p>ランキングは、楽天市場での売れ行きの順位です。贈り物として選ばれた順位ではありません。日用品など、贈り物に向かない商品は除いています。'
            '商品は<a href="/ranking/">いま売れている商品</a>で見られます。</p></section>')
    lead = f"楽天市場のランキング({day})をもとに、世代・性別ごとの、売れ筋の商品の価格を比べました。毎日、更新しています。"
    return "/data/ranking-prices/", "世代別・性別の、売れ筋の価格", lead, body, "売れ筋の価格", f"売れ筋の価格がいちばん高いのは「{hi[0]}」({yen(hi[1]['median'])})"


BUILDERS = (price_bands, occasion_prices, mothers_day_budget, births_marriages, ranking_prices)


def results(d: dict) -> list[tuple]:
    """The chart pages this build can make: (path, h1, lead, body, crumb, finding), once per build."""
    if "_data_room" not in d:
        d["_data_room"] = [r for r in (fn(d) for fn in BUILDERS) if r]
    return d["_data_room"]


def build_pages(d: dict, cfg: dict, preview: bool) -> dict[str, str]:
    """{file path: html} for the data room: one page per chart set that has enough data, and the hub that lists them (nothing at all when no chart can be made)."""
    rs = results(d)
    if not rs:
        return {}
    out = {path.strip("/") + "/index.html": _page(d, cfg, preview, path, h1, h1, lead, body, crumb) for path, h1, lead, body, crumb, _ in rs}
    tiles = "".join(f'<li><a class="tile wide" href="{p}"><span><b>{esc(h)}</b><small>{esc(t)}</small></span></a></li>' for p, h, _, _, _, t in rs)
    lead = "プレゼントの価格、予算、贈る機会を、数字で見る場所です。当サイトが取り上げている商品のデータ(毎日更新)と、国の統計・調査を、グラフにしています。"
    body = (f'<section class="block" style="margin-top:34px"><div class="sec-head"><span class="eyebrow">Data</span><h2>数字で見る、贈り物</h2></div>'
            f'<ul class="tiles wide">{tiles}</ul></section>')
    out["data/index.html"] = _page(d, cfg, preview, "/data/", "データ室", "データ室", lead, body, "データ室")
    return out


def home_teaser(d: dict) -> list[tuple[str, str, str]]:
    """(path, title, today's finding) of each chart page that exists, for the top page."""
    return [(path, h1, finding) for path, h1, _, _, _, finding in results(d)]
