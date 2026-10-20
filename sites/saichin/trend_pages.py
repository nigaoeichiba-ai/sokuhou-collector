"""The "trend" sections: one prefecture's whole series (Showa 52 to now) and the national one, as text, charts and a table.

The numbers come from long_history (the Ministry's 2003 document joined to the current workbook).  `k` is the build module (esc, yen, jp_date, charts).
Sentences state computed facts only.
"""
from __future__ import annotations

from sites.saichin.analysis import short_label
from sites.saichin.long_history import yen_text


def _s(label: str) -> str:
    return short_label(label.replace("昭和", "S"))


def _signed(v: float | None, suffix: str = "円") -> str:
    if v is None:
        return "-"
    n = f"{abs(v):,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{abs(int(v)):,}"
    return f"{'+' if v > 0 else '-' if v < 0 else '±'}{n}{suffix}"


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.1f}%"


def pref_summary(r: dict, k) -> str:
    s = r["long"]
    first = next(e for e in s if e["amount"] is not None)
    last = s[-1]
    n = last["fy"] - first["fy"]
    up = last["amount"] - first["amount"]
    name = k.esc(r["name"])
    rises = [e for e in s if e["raise"] is not None and e["raise"] > 0]
    top = sorted(rises, key=lambda e: (-e["raise"], -e["fy"]))[:3]
    best_pct = max((e for e in s if e["raise_pct"] is not None), key=lambda e: (e["raise_pct"], e["fy"]))
    zero = [e for e in s[1:] if e["raise"] == 0]
    gaps = [e["avg_gap"] for e in s if e["avg_gap"] is not None]
    higher, lower, same = sum(1 for g in gaps if g > 0), sum(1 for g in gaps if g < 0), sum(1 for g in gaps if g == 0)
    avg_first = next(e for e in s if e["avg"] is not None)
    ten = last["fy"] - 10
    a10 = next(e for e in s if e["fy"] == ten)
    b10 = next(e for e in s if e["fy"] == ten - 10)
    out = [
        f"{name}の最低賃金は、{k.esc(first['label'])}の{yen_text(first['amount'])}から、{k.esc(last['label'])}の{yen_text(last['amount'])}(決まった額)まで、"
        f"{n}年間で{yen_text(up)}(約{last['amount'] / first['amount']:.1f}倍)上がりました。1年あたりの平均は約{up / n:.0f}円です。",
        f"1年の引上げ額が最も大きかったのは{k.esc(top[0]['label'])}の+{yen_text(top[0]['raise'])}、引上げ率が最も大きかったのは{k.esc(best_pct['label'])}の{best_pct['raise_pct']:.1f}%です。",
        f"{k.esc(a10['label'])}から{k.esc(last['label'])}までの10年間は+{yen_text(last['amount'] - a10['amount'])}、その前の10年間は+{yen_text(a10['amount'] - b10['amount'])}でした。",
    ]
    if zero:
        out.append(f"前の年度と同じ額だった(引上げ額0円の)年度は{len(zero)}回あります。")
    out.append(
        f"全国加重平均は、{k.esc(avg_first['label'])}の{round(avg_first['avg']):,}円から{k.esc(last['label'])}の{round(last['avg']):,}円になりました。"
        f"年度ごとに全国加重平均と比べると、{name}の額が上回ったのは{higher}回、下回ったのは{lower}回{f'、同額は{same}回' if same else ''}です。")
    return "".join(out)


def pref_charts(r: dict, k) -> str:
    s = r["long"]
    xs = [_s(e["label"]) for e in s]
    line = k.charts.compare(
        xs, [{"name": r["name"], "values": [e["amount"] for e in s], "cls": ""},
             {"name": "全国加重平均", "values": [None if e["avg"] is None else round(e["avg"]) for e in s], "cls": "s2"}],
        title=f"{r['name']}の最低賃金と全国加重平均の推移",
        desc=f"{s[0]['label']}から{s[-1]['label']}までの、{r['name']}の最低賃金と全国加重平均(円)の推移", label_every=6)
    bars = k.charts.bars(
        [(xs[i], None if e["raise"] is None else e["raise"]) for i, e in enumerate(s)][1:],
        title=f"{r['name']}の最低賃金の、前の年度からの引上げ額",
        desc=f"{s[1]['label']}から{s[-1]['label']}までの、{r['name']}の最低賃金の前の年度からの引上げ額(円)", label_every=6)
    return line + "\n<p class=\"chart-note\">実線が" + k.esc(r["name"]) + "、点線が全国加重平均です。縦軸は0から始まっていません。</p>\n" + bars + "\n<p class=\"chart-note\">棒の高さは、前の年度からの引上げ額です(縦軸は0から)。</p>"


def pref_table(r: dict, k) -> str:
    rows = []
    hist = {h["fy"]: h for h in r["history"]}
    for e in reversed(r["long"]):
        if e["amount"] is None:
            sp = e["split"]
            amount = f"南部 {yen_text(sp['south'])}・北部 {yen_text(sp['north'])}"
        else:
            amount = yen_text(e["amount"])
        h = hist.get(e["fy"])
        date = "-"
        if h and h["effective_date"]:
            date = k.jp_date(h["effective_date"]) + ("※" if h.get("date_fixed_from") else "")
        rank = "-" if e["rank"] is None else f"{e['rank']}位" + ("※2" if 1979 <= e["fy"] <= 1989 else "")
        avg = "-" if e["avg"] is None else f"{round(e['avg']):,}円"
        rows.append(
            f"<tr><td>{k.esc(e['label'])}</td><td>{amount}</td><td>{_signed(e['raise'])}</td><td>{_pct(e['raise_pct'])}</td>"
            f"<td>{avg}</td><td>{_signed(e['avg_gap'])}</td><td>{rank}</td><td>{date}</td></tr>")
    return ('<div class="tablewrap"><table><thead><tr><th>年度</th><th>最低賃金</th><th>前年度から</th><th>上がり率</th><th>全国加重平均</th><th>全国との差</th>'
            f'<th>全国順位</th><th>発効日</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def pref_notes(r: dict, k, fixed_note: str) -> str:
    out = [fixed_note]
    out.append('<p class="notice">昭和52年度から平成13年度までの額は、厚生労働省の審議会資料(2003年)「<a href="https://www.mhlw.go.jp/shingi/2003/12/s1202-3h.html" rel="noopener" target="_blank">地域別最低賃金に関するデータ(時間額)</a>」の表の値です。'
               '平成14年度以降は、厚生労働省「地域別最低賃金の全国一覧」の値です。平成14年度と平成15年度は、2つの資料の額が、47都道府県すべてで一致しています。'
               '発効日は、平成14年度以降だけ載せています。</p>')
    has_frac = any(e["amount"] is not None and e["amount"] != int(e["amount"]) for e in r["long"])
    if has_frac:
        out.append('<p class="notice">小数のある額は、出典の表のとおりです。</p>')
    kyoto = ("この期間の京都府の額は「南部・北部」で示し、全国順位は付けていません。" if r["short"] == "京都"
             else "この期間の全国順位は、京都府を除く46都道府県の中で数えています。")
    out.append(f'<p class="notice">※2 京都府は、昭和54年度から平成元年度まで、南部と北部で別の額でした。{kyoto}</p>')
    return "".join(out)


def pref_trend(r: dict, k, fixed_note: str) -> str:
    first = next(e for e in r["long"] if e["amount"] is not None)
    last = r["long"][-1]
    return (f"<h2>{k.esc(r['name'])}の最低賃金の推移({k.esc(first['label'])}から{k.esc(last['label'])}まで)</h2>\n"
            f"<p>{pref_summary(r, k)}</p>\n{pref_charts(r, k)}\n"
            f"<h2>{k.esc(r['name'])}の最低賃金 年度別の一覧</h2>\n{pref_table(r, k)}\n{pref_notes(r, k, fixed_note)}")


# ---------------------------------------------------------------- the national series
def national_trend(d: dict, k) -> str:
    ys = d["long_years"]
    with_avg = [y for y in ys if y["avg"] is not None]
    first, last = with_avg[0], ys[-1]
    ups = [y for y in ys if y["avg_up"] is not None]
    top_yen = sorted(ups, key=lambda y: (-y["avg_up"], -y["fy"]))[:10]
    top_pct = sorted(ups, key=lambda y: (-y["avg_pct"], -y["fy"]))[:10]
    peak = top_yen[0]
    gaps_first, gaps_last = ys[0], ys[-1]
    n = last["fy"] - first["fy"]
    xs = [_s(y["label"]) for y in ys]
    chart_avg = k.charts.compare(
        [_s(y["label"]) for y in with_avg], [{"name": "全国加重平均", "values": [round(y["avg"]) for y in with_avg], "cls": ""}],
        title="全国加重平均の最低賃金の推移", desc=f"{first['label']}から{last['label']}までの、全国加重平均の最低賃金(円)の推移", label_every=6)
    chart_range = k.charts.compare(
        xs, [{"name": "最高額", "values": [y["max"] for y in ys], "cls": ""}, {"name": "最低額", "values": [y["min"] for y in ys], "cls": "s2"}],
        title="都道府県の最低賃金の最高額と最低額の推移", desc=f"{ys[0]['label']}から{last['label']}までの、最も高い都道府県と最も低い都道府県の最低賃金(円)", label_every=6)
    chart_up = k.charts.bars(
        [(_s(y["label"]), y["avg_up"]) for y in ups], title="全国加重平均の前の年度からの引上げ額", desc=f"{ups[0]['label']}から{last['label']}までの、全国加重平均の前の年度からの引上げ額(円)", label_every=6)

    full = {r["short"]: r["name"] for r in d["rows"]}
    full.update({"京都(南)": "京都府南部", "京都(北)": "京都府北部"})

    def names_of(rows):
        return "・".join(full[n] for n in rows[:2]) + ("ほか" if len(rows) > 2 else "")
    rows = []
    for y in reversed(ys):
        avg_txt = "-" if y["avg"] is None else f"{round(y['avg']):,}円"
        rows.append(
            f"<tr><td>{k.esc(y['label'])}</td><td>{avg_txt}</td><td>{_signed(y['avg_up'])}</td><td>{_pct(y['avg_pct'])}</td>"
            f"<td>{k.yen(y['max'])}({k.esc(names_of(y['max_names']))})</td><td>{k.yen(y['min'])}({k.esc(names_of(y['min_names']))})</td><td>{k.yen(y['max'] - y['min'])}</td></tr>")
    rank_rows = [f"<tr><td>{i}</td><td>{k.esc(y['label'])}</td><td>+{y['avg_up']}円</td><td>{y['avg_pct']:.1f}%</td></tr>" for i, y in enumerate(top_yen, 1)]
    pct_rows = [f"<tr><td>{i}</td><td>{k.esc(y['label'])}</td><td>{y['avg_pct']:.1f}%</td><td>+{y['avg_up']}円</td></tr>" for i, y in enumerate(top_pct, 1)]
    return f"""<h2>全国加重平均の歴代の推移(グラフ)</h2>
<p>{k.esc(first['label'])}から{k.esc(last['label'])}までの{n}年間で、全国加重平均は{round(last['avg']) - round(first['avg']):,}円(約{last['avg'] / first['avg']:.1f}倍)上がりました。
1年の引上げ額が最も大きかったのは{k.esc(peak['label'])}の+{peak['avg_up']}円です。</p>
{chart_avg}
<p class="chart-note">縦軸は0から始まっていません。</p>
<h2>最高額と最低額の推移</h2>
<p>最低賃金が最も高い都道府県と最も低い都道府県の差は、{k.esc(gaps_first['label'])}の{k.yen(gaps_first['max'] - gaps_first['min'])}から、{k.esc(gaps_last['label'])}の{k.yen(gaps_last['max'] - gaps_last['min'])}になりました。詳しくは<a href="/analysis/gap/">地域差の分析</a>をご覧ください。</p>
{chart_range}
<p class="chart-note">実線が最高額、点線が最低額です。縦軸は0から始まっていません。</p>
<h2>引上げ額の推移</h2>
{chart_up}
<p class="chart-note">棒の高さは、全国加重平均の前の年度からの引上げ額です(縦軸は0から)。</p>
<h2>年度別の一覧(全国加重平均・最高額・最低額)</h2>
<div class="tablewrap"><table><thead><tr><th>年度</th><th>全国加重平均</th><th>前年度から</th><th>上がり率</th><th>最高額(都道府県)</th><th>最低額(都道府県)</th><th>最高と最低の差</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<h2>歴代の引上げ額ランキング(全国加重平均)</h2>
<div class="rank-grid">
<div class="rank-box"><h3>引上げ額が大きい年度</h3><div class="tablewrap"><table><thead><tr><th>順位</th><th>年度</th><th>引上げ額</th><th>上がり率</th></tr></thead><tbody>{"".join(rank_rows)}</tbody></table></div></div>
<div class="rank-box"><h3>上がり率が大きい年度</h3><div class="tablewrap"><table><thead><tr><th>順位</th><th>年度</th><th>上がり率</th><th>引上げ額</th></tr></thead><tbody>{"".join(pct_rows)}</tbody></table></div></div>
</div>
<p class="notice">昭和52年度から平成13年度までの額は、厚生労働省の審議会資料(2003年)「<a href="https://www.mhlw.go.jp/shingi/2003/12/s1202-3h.html" rel="noopener" target="_blank">地域別最低賃金に関するデータ(時間額)</a>」の表の値、平成14年度以降は「地域別最低賃金の全国一覧」の値です。全国加重平均は、昭和53年度から載っています(昭和52年度の値は、この資料にありません)。
平成14年度の全国加重平均は、2つの資料で1円違います(この資料は664円、全国一覧は663円)。このサイトでは、平成14年度以降を全国一覧の値にしています。</p>
"""
