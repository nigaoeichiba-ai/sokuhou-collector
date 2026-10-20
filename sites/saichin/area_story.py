"""What is particular about one region (関東, 四国 ...): sentences chosen by computed facts, and a table that sets the seven regions side by side.

Search Console shows people typing "関東 最低賃金" and "四国 最低賃金"; the page answers with the region's own numbers: where it stands among the regions, how wide
its inside is, which border between neighbours has the biggest step, how the raise and the dates differ inside.
"""
from __future__ import annotations

from datetime import date

from sites.saichin.adjacency import NEIGHBOURS
from sites.saichin.long_history import yen_text
from sites.saichin.places import PLACES


def _mean(rows: list[dict]) -> float:
    return sum(r["amount"] for r in rows) / len(rows)


def region_table(d: dict, k, current: str) -> str:
    stats = []
    for slug, rname, shorts in k.REGIONS:
        m = [r for r in d["rows"] if r["short"] in shorts]
        stats.append((slug, rname, _mean(m), min(r["amount"] for r in m), max(r["amount"] for r in m), len(m)))
    stats.sort(key=lambda t: (-t[2], t[1]))
    rows = "".join(
        f'<tr{" class=\'on\'" if s == current else ""}><td>{k.esc(n)}</td><td>{k.yen(round(mean))}</td><td>{k.yen(lo)}</td><td>{k.yen(hi)}</td><td>{hi - lo}円</td><td>{c}</td></tr>'
        for s, n, mean, lo, hi, c in stats)
    return ('<div class="tablewrap"><table><thead><tr><th>地方</th><th>単純平均</th><th>最も低い額</th><th>最も高い額</th><th>差</th><th>都道府県数</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


def position_story(d: dict, rname: str, members: list[dict], k) -> list[str]:
    means = sorted(((_mean([r for r in d["rows"] if r["short"] in shorts]), n) for _, n, shorts in k.REGIONS), reverse=True)
    mine = _mean(members)
    rank = 1 + sum(1 for m, _ in means if m > mine)
    nat = round(d["avg"])
    out = []
    if rank == 1:
        out.append(f"7つの地方のうち、単純平均が最も高い地方です。")
    elif rank == len(means):
        out.append(f"7つの地方のうち、単純平均が最も低い地方です。")
    else:
        out.append(f"7つの地方を単純平均の高い順に並べると、{rank}番目です。")
    diff = round(mine) - nat
    if diff:
        out.append(f"単純平均{k.yen(round(mine))}は、全国加重平均の{k.yen(nat)}より{abs(diff)}円{'高く' if diff > 0 else '低く'}なっています。"
                   "全国加重平均は、労働者数で重みを付けた平均です。")
    top10 = [r for r in members if r["rank"] <= 10]
    bottom10 = [r for r in members if r["rank"] >= 38]
    if top10 and len(top10) == len(members):
        out.append("全国の上位10位に、すべての都道府県が入っています。")
    elif top10:
        out.append(f"全国の上位10位に入るのは、{'・'.join(r['name'] for r in top10)}です。")
    if bottom10 and len(bottom10) == len(members):
        out.append("全国の下位10位に、すべての都道府県が入っています。")
    elif bottom10:
        out.append(f"全国の下位10位に入るのは、{'・'.join(r['name'] for r in bottom10)}です。")
    n1100 = sum(1 for r in members if r["amount"] >= 1100)
    if n1100 == len(members):
        out.append("全都道府県が1,100円以上です。")
    elif n1100 == 0:
        out.append("1,100円以上の都道府県は、まだありません。")
    else:
        out.append(f"1,100円以上は{n1100}都道府県、届いていないのは{len(members) - n1100}都道府県です。")
    return [x for x in out if x]


def border_story(d: dict, members: list[dict], k) -> list[str]:
    short_of = {r["short"]: r for r in members}
    edges = []
    for a in short_of:
        for b in NEIGHBOURS[a]:
            if b in short_of and a < b:
                edges.append((abs(short_of[a]["amount"] - short_of[b]["amount"]), short_of[a], short_of[b]))
    if not edges:
        return [f"この地方の都道府県は、地方の中で陸続きに接していません。" if len(members) > 1 else ""]
    edges.sort(key=lambda t: (-t[0], t[1]["name"]))
    big, small = edges[0], edges[-1]
    hi, lo = (big[1], big[2]) if big[1]["amount"] > big[2]["amount"] else (big[2], big[1])
    out = [f"県境をはさんで最も差が大きいのは、{k.esc(hi['name'])}と{k.esc(lo['name'])}の{big[0]}円です。"]
    if small[0] != big[0]:
        s_hi, s_lo = (small[1], small[2]) if small[1]["amount"] >= small[2]["amount"] else (small[2], small[1])
        same = "同額" if small[0] == 0 else f"{small[0]}円の差"
        out.append(f"最も小さいのは、{k.esc(s_hi['name'])}と{k.esc(s_lo['name'])}の{same}です。")
    return out


def raise_story(d: dict, rname: str, members: list[dict], k) -> list[str]:
    ups = sorted(members, key=lambda r: (-r["raise"], r["name"]))
    nat = round(d["avg"]) - round(d["avg_prev"])
    mean_up = sum(r["raise"] for r in members) / len(members)
    out = []
    if ups[0]["raise"] == ups[-1]["raise"]:
        out.append(f"{k.esc(d['label'])}の引上げ額は、どの都道府県も+{ups[0]['raise']}円です。")
    else:
        out.append(f"{k.esc(d['label'])}の引上げ額が最も大きいのは{k.esc(ups[0]['name'])}の+{ups[0]['raise']}円、最も小さいのは{k.esc(ups[-1]['name'])}の+{ups[-1]['raise']}円で、{ups[0]['raise'] - ups[-1]['raise']}円の開きがあります。")
    diff = round(mean_up) - nat
    if diff > 0:
        out.append(f"地方内の引上げ額の平均(+{mean_up:.1f}円)は、全国加重平均の+{nat}円を上回っています。")
    elif diff < 0:
        out.append(f"地方内の引上げ額の平均(+{mean_up:.1f}円)は、全国加重平均の+{nat}円を下回っています。")
    return out


def date_story(d: dict, rname: str, members: list[dict], k) -> list[str]:
    dates = sorted(r["effective_date"] for r in members)
    first, last = dates[0], dates[-1]
    oct1 = sum(1 for x in dates if x == "2026-10-01" or date.fromisoformat(x) <= date(date.fromisoformat(x).year, 10, 1))
    if first == last:
        return [f"発効日は、どの都道府県も{k.jp_date(first)}です。"]
    n_last = dates.count(last)
    last_names = "・".join(r["name"] for r in members if r["effective_date"] == last)
    first_names = "・".join(r["name"] for r in members if r["effective_date"] == first)
    return [f"発効日が最も早いのは{k.jp_date(first)}の{k.esc(first_names)}、最も遅いのは{k.jp_date(last)}の{k.esc(last_names)}で、"
            f"{(date.fromisoformat(last) - date.fromisoformat(first)).days}日の幅があります。"]


def history_story(d: dict, rname: str, members: list[dict], k) -> list[str]:
    years = [e["fy"] for e in members[0]["long"]]
    gaps = []
    for fy in years:
        vals = [next(e for e in m["long"] if e["fy"] == fy)["amount"] for m in members]
        vals = [v for v in vals if v is not None]
        if len(vals) == len(members):
            gaps.append((max(vals) - min(vals), fy))
    big = max(gaps, key=lambda t: (t[0], t[1]))
    label = next(e["label"] for e in members[0]["long"] if e["fy"] == big[1])
    now = gaps[-1][0]
    if big[1] == gaps[-1][1]:
        return [f"地方内の最高額と最低額の差は、{k.esc(label)}の{big[0]}円が、{k.esc(members[0]['long'][0]['label'])}以降で最大です。"]
    return [f"地方内の最高額と最低額の差が最も大きかったのは{k.esc(label)}の{yen_text(big[0])}で、いまの{now}円は、それより{yen_text(big[0] - now)}小さくなっています。"]


def places_story(d: dict, rname: str, members: list[dict], k) -> list[str]:
    """The cities of the region that people search by (three per prefecture, the capital first), as a list; the amount of each is its prefecture's."""
    parts = []
    for r in members:
        parts.append("、".join(PLACES[r["short"]]) + f"({k.esc(r['name'])})")
    return [f"{k.esc(rname)}の主な市と区は、{'、'.join(parts)}です。どの市区も、その都道府県の最低賃金が適用されます。"]


def members_list(d: dict, members: list[dict], k) -> str:
    """One row per prefecture (a table): its national rank, how the rank moved in ten years and when it passed 1,000 yen."""
    rows = []
    for r in members:
        sr = [e for e in r["long"] if e["rank"] is not None]
        last = sr[-1]
        ten = next(e for e in sr if e["fy"] == last["fy"] - 10)
        diff = ten["rank"] - last["rank"]
        move = (f"{diff}位上がった" if diff >= 1 else f"{-diff}位下がった" if diff <= -1 else "変わらず")
        y1000 = next((e["label"] for e in r["long"] if e["amount"] is not None and e["amount"] >= 1000), None)
        rows.append(f'<tr><td><a href="/{r["slug"]}/">{k.esc(r["name"])}</a></td><td>{last["rank"]}位</td><td>{ten["rank"]}位({move})</td><td>{k.esc(y1000) if y1000 else "まだ届いていません"}</td></tr>')
    return ('<h3>都道府県ごとの動き</h3>\n<div class="tablewrap"><table><thead><tr><th>都道府県</th><th>全国順位</th><th>10年前の順位</th><th>1,000円以上になった年度</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>\n')


def industry_block(d: dict, rname: str, members: list[dict], k) -> str:
    """The industries whose own (higher) minimum wage applies in the prefectures of the region, from the Ministry's table (industry_view)."""
    if not d.get("industry"):
        return ""
    by = d["industry"]["by_pref"]
    count: dict[str, list[str]] = {}
    for r in members:
        for x in by[r["short"]]:
            if not x["regional_applies"]:
                count.setdefault(x["industry"], []).append(r["name"])
    most = sorted(count.items(), key=lambda t: (-len(t[1]), t[0]))
    n_with = sum(1 for r in members if any(not x["regional_applies"] for x in by[r["short"]]))
    rows = []
    for r in members:
        applying = [x for x in by[r["short"]] if not x["regional_applies"]]
        top = applying[0] if applying else None
        rows.append(f'<tr><td><a href="/{r["slug"]}/">{k.esc(r["name"])}</a></td><td>{len(by[r["short"]])}</td><td>{len(applying)}</td>'
                    f'<td>{k.esc(top["industry"]) + "(" + k.yen(top["hourly"]) + ")" if top else "-"}</td></tr>')
    if most:
        listed = "、".join(f"{k.esc(name)}({len(prefs)}都道府県)" for name, prefs in most[:4])
        lead = (f"<p>{k.esc(rname)}の{len(members)}都道府県のうち、特定(産業別)最低賃金の額が適用される産業が1つ以上あるのは{n_with}都道府県です。"
                f"複数の都道府県にまたがる産業は、{listed}です。</p>" if len(most[0][1]) > 1 else
                f"<p>{k.esc(rname)}の{len(members)}都道府県のうち、特定(産業別)最低賃金の額が適用される産業が1つ以上あるのは{n_with}都道府県です。同じ産業が2つ以上の都道府県で適用されることは、ありません。</p>")
    else:
        lead = f"<p>{k.esc(rname)}の{len(members)}都道府県には、特定(産業別)最低賃金の額が適用される産業が、ありません。</p>"
    return (f"<h2>{k.esc(rname)}の特定(産業別)最低賃金</h2>\n{lead}\n<div class=\"tablewrap\"><table><thead><tr><th>都道府県</th><th>特定最低賃金のある産業</th><th>うち特定の額が適用される産業</th><th>適用される最も高い額</th></tr></thead>"
            f'<tbody>{"".join(rows)}</tbody><tfoot><tr><td colspan="4">厚生労働省「特定(産業別)最低賃金全国一覧」({k.esc(d["industry"].get("table_label") or "")})。「特定の額が適用される」は、同じ表で「※」が付いていない額です。</td></tr></tfoot></table></div>\n')


def story_block(d: dict, slug: str, rname: str, members: list[dict], k) -> str:
    parts = [f"<h2>{k.esc(rname)}の最低賃金の特徴</h2>"]
    for head, sentences in (
        ("ほかの地方と比べると", position_story(d, rname, members, k)),
        ("県境をはさんだ差", border_story(d, members, k)),
        ("引上げ額と発効日", raise_story(d, rname, members, k) + date_story(d, rname, members, k)),
        ("地方内の差の推移", history_story(d, rname, members, k)),
        ("地方内の主な市", places_story(d, rname, members, k)),
    ):
        s = [x for x in sentences if x]
        if s:
            parts.append(f"<h3>{head}</h3>\n<p>{''.join(s)}</p>")
    parts.append(members_list(d, members, k))
    parts.append(industry_block(d, rname, members, k))
    parts.append(region_table(d, k, slug))
    return "\n".join(parts) + "\n"
