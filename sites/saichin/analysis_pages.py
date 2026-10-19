"""The /analysis/ pages and the "25 years in numbers" blocks of the prefecture and area pages.

The numbers come from analysis.py (arithmetic on the history workbook).  `k` is the build module: esc, yen, jp_date, crumbs, charts and
SOURCE_LABEL are taken from it, so this file does not import build.py.  Every sentence states a computed fact; none states a cause.
"""
from __future__ import annotations

from sites.saichin.analysis import (
    THRESHOLDS, date_series, gap_series, milestone_rank, milestones, names, national_milestones, number_one_years,
    pref_facts, rank_table, raise_series, region_facts, short_label, top_bottom_means,
)

INDEX = [
    ("gap", "地域差は広がったのか(最高額と最低額の差)"),
    ("milestones", "1,000円に届いたのはいつか(節目を超えた年度)"),
    ("ranks", "順位が上がった県・下がった県"),
    ("raises", "引上げ額は年ごとにどう変わったか"),
    ("dates", "発効日はそろっているのか(いつ、どの県で)"),
]
ORDER = [s for s, _ in INDEX]


def _lab(d: dict, fy: int) -> str:
    return next(y["label"] for y in d["years"] if y["fy"] == fy)


def _table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def _link(r: dict) -> str:
    return f'<a href="/{r["slug"]}/">{r["name"]}</a>'


def _src(d: dict, k) -> str:
    return (f'<p class="notice">データの取得日: {k.jp_date(d["fetched_date"])}。{k.esc(k.SOURCE_LABEL)}の年度別の額と発効日から計算した数字です。'
            f'数字は<a href="/data/">CSV・JSON</a>でも取れます。引用するときは<a href="/cite/">引用のしかた</a>をご覧ください。'
            f'額が動いた理由は調べていません。物価や賃金全体の動きとの関係は、この分析では扱っていません。</p>')


def _more(slug: str) -> str:
    items = "".join(f'<li><a href="/analysis/{s}/">{t}</a></li>' for s, t in INDEX if s != slug)
    return f'<h2>ほかの分析</h2><ul class="link-list">{items}<li><a href="/history/">最低賃金の推移(全国と都道府県別)</a></li></ul>'


# ---------------------------------------------------------------- the five analysis pages
def gap_page(d: dict, k) -> dict:
    g = gap_series(d)
    first, last = g[0], g[-1]
    widest = max(g, key=lambda x: (x["gap"], x["fy"]))
    narrowest = min(g, key=lambda x: (x["ratio"], -x["fy"]))
    earlier = [x for x in g[:-1] if x["ratio"] >= last["ratio"]]
    ratio_sentence = (f"{last['label']}の{last['ratio']:.1f}%は、{earlier[-1]['label']}({earlier[-1]['ratio']:.1f}%)以来の高さです。"
                      if earlier else f"{last['label']}の{last['ratio']:.1f}%は、調べた期間で最も高い比率です。")
    near = abs(last["ratio"] - first["ratio"]) < 2
    compare = (f"円の差は{first['label']}の{first['gap']}円より大きいままですが、比率は{first['label']}に近い水準です。" if near and last["gap"] > first["gap"]
               else f"{first['label']}の比率は{first['ratio']:.1f}%でした。")
    tokyo_always = all(set(r["name"] for r in x["hi_rows"]) & set(r["name"] for r in g[0]["hi_rows"]) for x in g)
    chart = k.charts.line([(short_label(x["label"]), x["gap"]) for x in g], title="最高額と最低額の差(円)の推移",
                          desc=f"{first['label']}から{last['label']}までの、都道府県の最低賃金の最高額と最低額の差(円)", label_every=4)
    rows = [[k.esc(x["label"]), f"{k.yen(x['max'])}({k.esc(names(x['hi_rows']))})", f"{k.yen(x['min'])}({k.esc(names(x['lo_rows']))})",
             f"{x['gap']:,}円", f"{x['ratio']:.1f}%"] for x in reversed(g)]
    tb = top_bottom_means(d)
    t0, t1 = tb[0], tb[-1]
    body = f"""{k.crumbs([("全国", "/"), ("分析", "/analysis/"), ("地域差", None)])}
<h1>最低賃金の地域差は広がったのか 最高額と最低額の差の{len(g)}年</h1>
<p class="lead">最低賃金が最も高い都道府県と最も低い都道府県の差は、{k.esc(first['label'])}の{first['gap']}円から、{k.esc(last['label'])}の{last['gap']}円になりました。差が最も大きかったのは{k.esc(widest['label'])}の{widest['gap']}円です。</p>
<h2>差の推移</h2>
{chart}
<p>差は{k.esc(first['label'])}から{k.esc(widest['label'])}までに{widest['gap'] - first['gap']}円広がり、{k.esc(widest['label'])}から{k.esc(last['label'])}までに{widest['gap'] - last['gap']}円縮まりました。{f"最高額の都道府県は、どの年度も{k.esc(names(g[0]['hi_rows']))}を含みます。" if tokyo_always else ""}</p>
<h2>比率で見ると</h2>
<p>最低額を最高額で割った比率は、{k.esc(first['label'])}が{first['ratio']:.1f}%、最も低かった{k.esc(narrowest['label'])}が{narrowest['ratio']:.1f}%、{k.esc(last['label'])}が{last['ratio']:.1f}%です。{k.esc(ratio_sentence)}</p>
<p>{k.esc(compare)}</p>
<h2>上位5都道府県と下位5都道府県</h2>
<p>高い方から5都道府県の平均は、{k.esc(first['label'])}の{t0['top']:,.0f}円から{k.esc(last['label'])}の{t1['top']:,.0f}円へ上がりました。低い方から5都道府県の平均は、{t0['bottom']:,.0f}円から{t1['bottom']:,.0f}円です。2つの平均の差は、{t0['top'] - t0['bottom']:,.0f}円から{t1['top'] - t1['bottom']:,.0f}円になりました。</p>
<h2>年度別の一覧</h2>
{_table(["年度", "最高額(都道府県)", "最低額(都道府県)", "差", "最低額÷最高額"], rows)}
<h2>数え方</h2>
<ul>
<li>差は「最高額 − 最低額」、比率は「最低額 ÷ 最高額」です。</li>
<li>額は、その年度に決まった地域別最低賃金(時間額)です。発効日の違いは考慮していません。</li>
<li>同額の都道府県が複数あるときは「ほか○都道府県」と書いています。</li>
</ul>
{_more("gap")}
{_src(d, k)}"""
    return {"title": f"最低賃金の地域差 最高額と最低額の差の推移({first['label']}〜{last['label']})",
            "description": f"最低賃金が最も高い都道府県と最も低い都道府県の差は、{first['label']}の{first['gap']}円から{last['label']}の{last['gap']}円になりました。{len(g)}年分の差と比率を表にしました。",
            "lead": f"最高額と最低額の差は、{first['label']}の{first['gap']}円から{last['label']}の{last['gap']}円へ(最大は{widest['label']}の{widest['gap']}円)。", "body": body}


def milestones_page(d: dict, k) -> dict:
    ms, nat = milestones(d), national_milestones(d)
    last_label = d["years"][-1]["label"]
    n_rows = len(d["rows"])
    lines, spans = [], []
    for t in THRESHOLDS:
        got = ms[t]
        if not got:
            lines.append([f"{t:,}円", "まだ届いていません", "-", "0", "-"])
            continue
        f, l = got[0], got[-1]
        first_rows = [g["row"] for g in got if g["fy"] == f["fy"]]
        last_rows = [g["row"] for g in got if g["fy"] == l["fy"]]
        done = len(got) == n_rows
        if done:
            spans.append(l["fy"] - f["fy"])
        lines.append([f"{t:,}円", f"{k.esc(f['label'])}({k.esc(names(first_rows))})",
                      f"{k.esc(l['label'])}({k.esc(names(last_rows))})" if done else "まだ全都道府県は届いていません",
                      f"{len(got)}都道府県", f"{l['fy'] - f['fy']}年" if done else "-"])
    nat_rows = [[f"{t:,}円", (f"{k.esc(nat[t]['label'])}({round(nat[t]['avg']):,}円)" if nat[t] else "まだ届いていません")] for t in THRESHOLDS]
    pref_rows = []
    for r in sorted(d["rows"], key=lambda r: (-r["amount"], r["name"])):
        cells = []
        for t in THRESHOLDS:
            mr = milestone_rank(ms, r, t)
            cells.append(short_label(next(x["label"] for x in r["history"] if x["fy"] == mr[1])) if mr else "-")
        pref_rows.append([_link(r)] + cells)
    t1000 = ms[1000]
    n1100, n1200 = len(ms[1100]), len(ms[1200])
    last_1000 = t1000[-1] if len(t1000) == n_rows else None
    first_1000 = [g["row"] for g in t1000 if g["fy"] == t1000[0]["fy"]]
    lead = (f"最低賃金が初めて1,000円以上になったのは{k.esc(t1000[0]['label'])}の{k.esc(names(first_1000))}です。"
            + (f"全{n_rows}都道府県が1,000円以上になったのは{k.esc(last_1000['label'])}で、最初の都道府県から{last_1000['fy'] - t1000[0]['fy']}年かかりました。" if last_1000 else "")
            + f"{k.esc(last_label)}は、1,100円以上が{n1100}都道府県、1,200円以上が{n1200}都道府県です。")
    shrink = ("<p>最初の都道府県が届いてから、最後の都道府県が届くまでの年数は、節目が大きくなるほど短くなっています。</p>"
              if len(spans) >= 2 and all(a > b for a, b in zip(spans, spans[1:])) else "")
    body = f"""{k.crumbs([("全国", "/"), ("分析", "/analysis/"), ("節目を超えた年度", None)])}
<h1>最低賃金が1,000円を超えたのはいつか 節目ごとの到達年度</h1>
<p class="lead">{lead}</p>
<h2>全国加重平均が節目を超えた年度</h2>
<p>全国加重平均(都道府県の額を労働者数で重みづけした平均)が、初めてその額以上になった年度です。</p>
{_table(["節目", "初めて超えた年度(全国加重平均)"], nat_rows)}
<h2>節目ごとの最初と最後</h2>
{_table(["節目", "最初に届いた年度(都道府県)", "最後に届いた年度(都道府県)", f"{k.esc(last_label)}までに届いた数", "最初から最後まで"], lines)}
{shrink}
<h2>都道府県別の到達年度</h2>
<p>その額以上になった最初の年度です。{k.esc(last_label)}の高い順に並べています。「-」はまだ届いていません。都道府県名を押すと、その都道府県の推移を見られます。</p>
{_table(["都道府県"] + [f"{t:,}円" for t in THRESHOLDS], pref_rows)}
<h2>数え方</h2>
<ul>
<li>年度の額は、その年度に決まった額です。実際に適用されるのは、都道府県ごとの発効日からです。</li>
<li>R は令和、H は平成です(R8 は令和8年度)。</li>
<li>一度届いたあとに額が下がった都道府県はありません(下がったデータがあれば、ページを作る時点で公開を止めています)。</li>
</ul>
{_more("milestones")}
{_src(d, k)}"""
    return {"title": f"最低賃金が1,000円を超えたのはいつ 都道府県別の到達年度({d['years'][0]['label']}〜{last_label})",
            "description": f"最低賃金が800円・900円・1,000円・1,100円・1,200円を超えた年度を、全国加重平均と47都道府県別に一覧にしました。{last_label}は1,100円以上が{n1100}都道府県です。",
            "lead": f"1,000円以上は{t1000[0]['label']}に始まり、{last_label}は1,100円以上が{n1100}都道府県、1,200円以上が{n1200}都道府県。", "body": body}


def ranks_page(d: dict, k) -> dict:
    rt = rank_table(d)
    first_lab, last_lab = rt[0]["row"]["history"][0]["label"], rt[0]["row"]["history"][-1]["label"]
    up_max, down_max = max(x["change"] for x in rt), min(x["change"] for x in rt)
    ups = [x for x in rt if x["change"] == up_max]
    downs = [x for x in rt if x["change"] == down_max]
    climbers = sorted((x for x in rt if x["change"] > 0), key=lambda x: (-x["change"], x["row"]["name"]))[:5]
    fallers = sorted((x for x in rt if x["change"] < 0), key=lambda x: (x["change"], x["row"]["name"]))[:5]
    n_up, n_down = sum(1 for x in rt if x["change"] > 0), sum(1 for x in rt if x["change"] < 0)
    same = len(rt) - n_up - n_down
    firsts = number_one_years(d)
    n_years = len(firsts)
    count_first: dict[str, int] = {}
    for n in firsts:
        for r in n["rows"]:
            count_first[r["name"]] = count_first.get(r["name"], 0) + 1
    count_low: dict[str, int] = {}
    for g in gap_series(d):
        for r in g["lo_rows"]:
            count_low[r["name"]] = count_low.get(r["name"], 0) + 1
    by_name = {r["name"]: r for r in d["rows"]}
    top_low = sorted(count_low.items(), key=lambda t: (-t[1], t[0]))[:6]
    latest = sorted(r["history"][-1]["amount"] for r in d["rows"])
    lo = latest[0]
    within = sum(1 for a in latest if a <= lo + 15)
    mid_fy = d["years"][-1]["fy"] - 10
    mid_lab = _lab(d, mid_fy)

    def move(x):
        h = x["row"]["history"]
        return f"{h[0]['rank']}位→{h[-1]['rank']}位"

    def change_row(x):
        return [_link(x["row"]), f"{x['first']}位", f"{x['last']}位", f"{abs(x['change'])}位{'上がった' if x['change'] > 0 else '下がった'}"]
    if len(count_first) == 1 and next(iter(count_first.values())) == n_years:
        first_text = f"{k.esc(next(iter(count_first)))}は、調べた{n_years}年度すべてで1位(同額の首位を含む)でした。"
    else:
        first_text = "1位(同額の首位を含む)になったことがあるのは、" + "、".join(
            f"{k.esc(n)}({c}年度)" for n, c in sorted(count_first.items(), key=lambda t: (-t[1], t[0]))) + "です。"
    pref_rows = []
    for x in sorted(rt, key=lambda x: (x["last"], x["row"]["name"])):
        r = x["row"]
        mid = next(h["rank"] for h in r["history"] if h["fy"] == mid_fy)
        pref_rows.append([_link(r), f"{x['first']}位", f"{mid}位", f"{x['last']}位", f"{x['best']}位", f"{x['worst']}位"])
    up_names, down_names = "、".join(x["row"]["name"] for x in ups), "、".join(x["row"]["name"] for x in downs)
    body = f"""{k.crumbs([("全国", "/"), ("分析", "/analysis/"), ("順位の動き", None)])}
<h1>最低賃金の順位は{len(d['years'])}年でどう動いたか 上がった県・下がった県</h1>
<p class="lead">{k.esc(first_lab)}から{k.esc(last_lab)}までに最も順位を上げたのは{k.esc(up_names)}({k.esc(move(ups[0]))})、最も下げたのは{k.esc(down_names)}({k.esc(move(downs[0]))})です。{n_up}都道府県が上がり、{n_down}都道府県が下がり、{same}都道府県は同じ順位でした。</p>
<h2>順位を上げた都道府県</h2>
{_table(["都道府県", k.esc(first_lab), k.esc(last_lab), "変化"], [change_row(x) for x in climbers])}
<h2>順位を下げた都道府県</h2>
{_table(["都道府県", k.esc(first_lab), k.esc(last_lab), "変化"], [change_row(x) for x in fallers])}
<h2>1位は変わったのか</h2>
<p>{first_text}</p>
<h2>いちばん低い額に並んだ都道府県</h2>
<p>最も低い額(同額を含む)になった都道府県は、{n_years}年度で延べ{sum(count_low.values())}回、{len(count_low)}都道府県に上ります。回数が多いのは次の都道府県です。</p>
{_table(["都道府県", f"最も低い額になった年度の数(全{n_years}年度)"], [[_link(by_name[n]), f"{c}年度"] for n, c in top_low])}
<p>{k.esc(last_lab)}は、最も低い額の{lo:,}円から{lo + 15:,}円までの間に、{within}都道府県が入っています。額の差が数円でも、順位は数位変わります。</p>
<h2>47都道府県の順位表</h2>
<p>{k.esc(last_lab)}の順位の順です。同額の都道府県は同じ順位です。「最高の順位」「最低の順位」は、{k.esc(first_lab)}から{k.esc(last_lab)}までの間のものです。</p>
{_table(["都道府県", k.esc(first_lab), k.esc(mid_lab), k.esc(last_lab), "最高の順位", "最低の順位"], pref_rows)}
<h2>数え方</h2>
<ul>
<li>順位は、その年度の額が高い順です。同額は同じ順位で、次の順位は飛びます(2都道府県が1位なら次は3位)。</li>
<li>順位の変化は、{k.esc(first_lab)}と{k.esc(last_lab)}の2点の比べです。途中で上下した分は、表の「最高の順位」「最低の順位」に出ます。</li>
</ul>
{_more("ranks")}
{_src(d, k)}"""
    return {"title": f"最低賃金の都道府県別ランキングの変化 順位が上がった県・下がった県({first_lab}〜{last_lab})",
            "description": f"{first_lab}から{last_lab}までに、最低賃金の全国順位が最も上がったのは{up_names}、最も下がったのは{down_names}です。47都道府県の順位表つき。",
            "lead": f"最も上がったのは{up_names}、最も下がったのは{down_names}。", "body": body}


def raises_page(d: dict, k) -> dict:
    rs = raise_series(d)
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    n = len(d["rows"])
    last, prev = rs[-1], rs[-2]
    peak = max(rs, key=lambda x: (x["avg_up"], x["fy"]))
    all30 = next((x["fy"] for x in rs if all(y["n_30"] == n for y in rs if y["fy"] >= x["fy"])), None)
    all50 = next((x["fy"] for x in rs if all(y["n_50"] == n for y in rs if y["fy"] >= x["fy"])), None)
    zero_years = [x for x in rs if x["n_zero"] > 0]
    rows = [[k.esc(x["label"]), f"+{x['avg_up']}円", f"{x['avg_up'] / round(avg[x['fy'] - 1]) * 100:.1f}%",
             f"+{x['max']}円({k.esc(names(x['hi_rows']))})", f"+{x['min']}円({k.esc(names(x['lo_rows']))})", f"{x['n_30']}", f"{x['n_50']}"] for x in reversed(rs)]
    chart = k.charts.line([(short_label(x["label"]), x["avg_up"]) for x in rs], title="全国加重平均の引上げ額(円)の推移",
                          desc=f"{rs[0]['label']}から{last['label']}までの、全国加重平均の前年度からの引上げ額(円)", label_every=4)
    diff = last["avg_up"] - prev["avg_up"]
    change = f"{prev['label']}より{abs(diff)}円{'小さい' if diff < 0 else '大きい'}引上げ" if diff else f"{prev['label']}と同じ引上げ"
    bullets = []
    if all30:
        bullets.append(f"全{n}都道府県が30円以上引き上げられたのは、{k.esc(_lab(d, all30))}から{k.esc(last['label'])}まで毎年です。")
    if all50:
        bullets.append(f"全{n}都道府県が50円以上引き上げられたのは、{k.esc(_lab(d, all50))}から{k.esc(last['label'])}まで毎年です。")
    if zero_years:
        bullets.append(f"引上げ額が0円の都道府県が出た年度は、{len(zero_years)}回あります。" + "、".join(f"{k.esc(x['label'])}は{x['n_zero']}" for x in zero_years) + "都道府県でした。")
    bullets.append(f"{k.esc(last['label'])}の都道府県別の引上げ額は、+{last['min']}円({k.esc(names(last['lo_rows']))})から+{last['max']}円({k.esc(names(last['hi_rows']))})です。")
    li = "".join(f"<li>{b}</li>\n" for b in bullets)
    body = f"""{k.crumbs([("全国", "/"), ("分析", "/analysis/"), ("引上げ額", None)])}
<h1>最低賃金の引上げ額は年ごとにどう変わったか</h1>
<p class="lead">全国加重平均の引上げ額は、{k.esc(rs[0]['label'])}の+{rs[0]['avg_up']}円から、最も大きい{k.esc(peak['label'])}の+{peak['avg_up']}円まで動きました。{k.esc(last['label'])}は+{last['avg_up']}円で、{k.esc(change)}です。</p>
<h2>全国加重平均の引上げ額</h2>
{chart}
<p>{k.esc(peak['label'])}の+{peak['avg_up']}円は、{k.esc(rs[0]['label'])}から{k.esc(last['label'])}までの{len(rs)}年度で最大です。{k.esc(prev['label'])}は+{prev['avg_up']}円、{k.esc(last['label'])}は+{last['avg_up']}円でした。</p>
<h2>都道府県ごとの引上げ額</h2>
<ul>
{li}</ul>
<h2>年度別の一覧</h2>
<p>引上げ率は、前年度の全国加重平均(円未満を四捨五入)に対する、引上げ額の割合です。</p>
{_table(["年度", "全国加重平均の引上げ", "引上げ率", "最大の引上げ(都道府県)", "最小の引上げ(都道府県)", "30円以上の都道府県数", "50円以上の都道府県数"], rows)}
<h2>数え方</h2>
<ul>
<li>引上げ額は、その年度の額から前の年度の額を引いた値です。</li>
<li>全国加重平均の引上げ額は、円未満を四捨五入した平均の差です。</li>
<li>引上げ額の大小の理由は調べていません。目安額や審議の内容は、厚生労働省の公表資料をご覧ください。</li>
</ul>
{_more("raises")}
{_src(d, k)}"""
    return {"title": f"最低賃金の引上げ額の推移 年度別・都道府県別({rs[0]['label']}〜{last['label']})",
            "description": f"全国加重平均の最低賃金の引上げ額を、{rs[0]['label']}から{last['label']}まで年度別に比べました。最大は{peak['label']}の+{peak['avg_up']}円、{last['label']}は+{last['avg_up']}円です。",
            "lead": f"全国加重平均の引上げ額は、最大が{peak['label']}の+{peak['avg_up']}円、{last['label']}は+{last['avg_up']}円。", "body": body}


def dates_page(d: dict, k) -> dict:
    ds = [s for s in date_series(d) if s["n"]]
    last, widest = ds[-1], max(ds, key=lambda s: (s["span"], s["fy"]))
    window = [s for s in ds if 2019 <= s["fy"] <= last["fy"] - 3]
    base_text = ""
    if len(window) >= 2:
        sp = [s["span"] for s in window]
        base_text = f"{k.esc(window[0]['label'])}から{k.esc(window[-1]['label'])}までは、最初の発効と最後の発効の間は{min(sp)}日から{max(sp)}日でした。"
    rows = [[k.esc(s["label"]), f"{s['n']}", f"{k.jp_date(s['first'].isoformat())}({k.esc(names(s['first_rows']))})",
             f"{k.jp_date(s['last'].isoformat())}({k.esc(names(s['last_rows']))})", f"{s['span']}日",
             f"{s['by_oct1']}", f"{s['in_oct']}", f"{s['in_nov_dec']}", f"{s['next_year']}"] for s in reversed(ds)]
    chart = k.charts.line([(short_label(s["label"]), s["span"]) for s in ds], title="最初の発効から最後の発効までの日数",
                          desc=f"{ds[0]['label']}から{last['label']}までの、最初に発効した都道府県から最後に発効した都道府県までの日数", unit="日", label_every=4)
    later = f"、翌年が{last['next_year']}" if last["next_year"] else ""
    body = f"""{k.crumbs([("全国", "/"), ("分析", "/analysis/"), ("発効日", None)])}
<h1>最低賃金の発効日はそろっているのか いつ、どの都道府県で</h1>
<p class="lead">{k.esc(last['label'])}は、{last['n']}都道府県のうち{last['by_oct1']}都道府県の発効日が10月1日まで(9月30日を含む)で、最も遅いのは{k.esc(names(last['last_rows']))}の{k.jp_date(last['last'].isoformat())}です。最初の発効から最後の発効まで{last['span']}日あります。</p>
<h2>最初と最後の間の日数</h2>
{chart}
<p>{base_text}最も長かったのは{k.esc(widest['label'])}の{widest['span']}日で、最後の発効は{k.esc(names(widest['last_rows']))}の{k.jp_date(widest['last'].isoformat())}でした。{k.esc(last['label'])}は{last['span']}日です。</p>
<h2>発効日の内訳</h2>
<p>{k.esc(last['label'])}は、発効日が10月1日までの都道府県が{last['by_oct1']}、10月2日から31日までが{last['in_oct']}、11月と12月が{last['in_nov_dec']}{later}です。都道府県ごとの日付は、<a href="/calendar/">発効日カレンダー</a>にあります。</p>
<h2>年度別の一覧</h2>
<p>その年度に額を引き上げた都道府県だけを数えています。据え置いた都道府県は含みません。</p>
{_table(["年度", "引き上げた都道府県数", "最初に発効", "最後に発効", "最初から最後まで", "発効日が10月1日まで", "10月2〜31日", "11〜12月", "翌年"], rows)}
<h2>数え方</h2>
<ul>
<li>日付は、厚生労働省の一覧表の発効日です。「10月1日まで」には、9月30日の都道府県を含みます。</li>
<li>表の4つの欄(発効日が10月1日まで・10月2〜31日・11〜12月・翌年)は、重ならず、合計が「引き上げた都道府県数」になります。</li>
<li>発効日が年度内(4月から翌年3月)に入らない日付は、一覧表の誤記とみて翌年に直しています。直したときは、その都道府県のページに注を付けています。</li>
</ul>
{_more("dates")}
{_src(d, k)}"""
    return {"title": f"最低賃金の発効日の推移 どの県がいつ発効したか({ds[0]['label']}〜{last['label']})",
            "description": f"最低賃金の発効日が、年度ごとにどれだけ散らばったかを比べました。{last['label']}は発効日が10月1日までの都道府県が{last['by_oct1']}、最後は{names(last['last_rows'])}の{k.jp_date(last['last'].isoformat())}です。",
            "lead": f"{last['label']}は最初から最後まで{last['span']}日。発効日が10月1日までなのは{last['by_oct1']}都道府県。", "body": body}


PAGES = {"gap": gap_page, "milestones": milestones_page, "ranks": ranks_page, "raises": raises_page, "dates": dates_page}


def pages(d: dict, k) -> dict[str, dict]:
    return {slug: fn(d, k) for slug, fn in PAGES.items()}


def hub_body(d: dict, k, built: dict[str, dict]) -> str:
    cards = "".join(
        f'<a class="guide-card" href="/analysis/{slug}/"><b>{k.esc(dict(INDEX)[slug])}</b><span>{k.esc(built[slug]["lead"])}</span></a>' for slug in ORDER)
    first, last = d["years"][0]["label"], d["years"][-1]["label"]
    return f"""{k.crumbs([("全国", "/"), ("分析", None)])}
<h1>最低賃金の分析</h1>
<p class="lead">{k.esc(first)}から{k.esc(last)}までの{len(d['years'])}年度、47都道府県の最低賃金を、このサイトで計算して比べました。地域差、節目を超えた年度、順位、引上げ額、発効日の5つです。</p>
<div class="guide-grid">{cards}</div>
<h2>この分析のしかた</h2>
<ul>
<li>元のデータは、{k.esc(k.SOURCE_LABEL)}の年度別の額と発効日です。他の統計や報道の数字は使っていません。</li>
<li>数字はすべてプログラムで計算し、ページを作るたびに計算し直しています。手で書き写した数字はありません。</li>
<li>観察した事実と計算だけを書き、理由は断定しません。物価や賃金全体との関係は扱っていません。</li>
</ul>
<p>元の数字を確かめたいときは<a href="/data/">CSV・JSONのデータ</a>、全国の推移は<a href="/history/">推移のページ</a>をご覧ください。</p>"""


# ---------------------------------------------------------------- blocks on the existing pages
def _labels(xs: list[str]) -> str:
    """'令和6年度' for one year, '平成22年度を含む3回' for several."""
    return xs[0] if len(xs) == 1 else f"{xs[0]}を含む{len(xs)}回"


def pref_block(d: dict, r: dict, k) -> str:
    f = pref_facts(d, r)
    h0, h1 = r["history"][0], r["history"][-1]
    name = k.esc(r["name"])

    def above(n: int, top: bool) -> str:
        if n == 0:
            return "最高額" if top else "最低額"
        return f"{n}円低い" if top else f"{n}円高い"

    def avg_gap(n: int) -> str:
        return "同額" if n == 0 else (f"{n}円高い" if n > 0 else f"{-n}円低い")
    rows = [
        ["最低賃金", k.yen(h0["amount"]), k.yen(h1["amount"])],
        ["全国順位", f"{h0['rank']}位", f"{h1['rank']}位"],
        ["最高額の都道府県との差", above(f["to_top_first"], True), above(f["to_top_last"], True)],
        ["最低額の都道府県との差", above(f["to_bottom_first"], False), above(f["to_bottom_last"], False)],
        ["全国加重平均との差", avg_gap(f["to_avg_first"]), avg_gap(f["to_avg_last"])],
    ]
    if f["best"] == f["worst"]:
        rank_text = f"全国順位は、調べた期間を通して{f['best']}位でした。"
    else:
        rank_text = (f"全国順位が最も高かったのは{f['best']}位で、{k.esc(_labels(f['best_labels']))}です。"
                     f"最も低かったのは{f['worst']}位で、{k.esc(_labels(f['worst_labels']))}です。")
    if f["reached"]:
        top = f["reached"][-1]
        ms_text = (f"{name}の最低賃金が{top['t']:,}円以上になったのは{k.esc(top['label'])}です。"
                   f"{top['t']:,}円以上に届いたのは{top['of']}都道府県で、{name}は早い方から{top['order']}番目です。")
    else:
        ms_text = f"{name}は、{k.esc(h1['label'])}までに800円に届いていません。"
    zero = f"引上げ額が0円の年度は{f['raises_zero']}回ありました。" if f["raises_zero"] else "毎年、前の年度より額が上がっています。"
    ms_rows = [[f"{x['t']:,}円", k.esc(x["label"]), f"{x['order']}番目(届いた{x['of']}都道府県のうち)"] for x in f["reached"]]
    return f"""<h2>{name}の{k.esc(h0['label'])}から{k.esc(h1['label'])}までを数字で見る</h2>
<p>{ms_text}{rank_text}{zero}</p>
{_table(["項目", k.esc(h0["label"]), k.esc(h1["label"])], rows)}
<h3>節目に届いた年度</h3>
{_table(["節目", "届いた年度", "届いた順(同じ年度は同順)"], ms_rows)}
<p>ほかの都道府県との比べ方は、<a href="/analysis/">最低賃金の分析</a>(<a href="/analysis/milestones/">節目を超えた年度</a>・<a href="/analysis/ranks/">順位の動き</a>)にあります。</p>
"""


def region_block(d: dict, rname: str, members: list[dict], k) -> str:
    f = region_facts(d, members)
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    h0, h1 = members[0]["history"][0], members[0]["history"][-1]
    (lo0, hi0, m0), (lo1, hi1, m1) = f["first"], f["last"]
    ups = f["ups"]
    rows = [
        ["最も低い額", k.yen(lo0), k.yen(lo1)],
        ["最も高い額", k.yen(hi0), k.yen(hi1)],
        ["最高額と最低額の差", f"{hi0 - lo0}円", f"{hi1 - lo1}円"],
        ["単純平均", k.yen(round(m0)), k.yen(round(m1))],
        ["全国加重平均", k.yen(round(avg[h0["fy"]])), k.yen(round(avg[h1["fy"]]))],
    ]
    up_rows = [[_link(m), k.yen(m["history"][0]["amount"]), k.yen(m["history"][-1]["amount"]), f"+{u:,}円"] for u, m in ups]
    return f"""<h2>{k.esc(rname)}の{k.esc(h0['label'])}から{k.esc(h1['label'])}までを数字で見る</h2>
<p>{k.esc(h0['label'])}から{k.esc(h1['label'])}までに、{k.esc(rname)}で最も上がったのは{k.esc(ups[0][1]['name'])}の+{ups[0][0]:,}円、最も上がり方が小さかったのは{k.esc(ups[-1][1]['name'])}の+{ups[-1][0]:,}円です。
地方内の最高額と最低額の差は、{hi0 - lo0}円から{hi1 - lo1}円になりました。</p>
{_table(["項目", k.esc(h0["label"]), k.esc(h1["label"])], rows)}
<h3>都道府県別に上がった額</h3>
{_table(["都道府県", k.esc(h0["label"]), k.esc(h1["label"]), "上がった額"], up_rows)}
<p>全国の比べ方は、<a href="/analysis/gap/">地域差の分析</a>と<a href="/analysis/ranks/">順位の動き</a>にあります。</p>
"""
