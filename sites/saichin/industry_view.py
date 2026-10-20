"""The industry-specific minimum wages (特定(産業別)最低賃金) of a prefecture, from the Ministry's national table (sokuhou/sources/mhlw_industry.py).

Every statement is in the Ministry's table: the industry's name, the amount, the effective date and the mark "※" (the regional minimum wage applies to that amount).
Nothing is compared with the regional amount here, because the Ministry's mark already tells which of the two applies.
"""
from __future__ import annotations

from sokuhou.sources.mhlw_minwage import PREFECTURES


class IndustryError(ValueError):
    pass


def view(data: dict, d: dict) -> dict:
    """{prefecture short name: [rows]} with the rows of the Ministry's table sorted: the amounts that apply first (highest first), then the ones marked ※."""
    by: dict[str, list[dict]] = {s: [] for s in PREFECTURES}
    for r in data["rows"]:
        if r["pref"] not in by:
            raise IndustryError(f"unknown prefecture {r['pref']!r}")
        by[r["pref"]].append(r)
    missing = [s for s, rows in by.items() if not rows]
    if missing:
        raise IndustryError(f"no industry rows for {missing}")
    for rows in by.values():
        rows.sort(key=lambda r: (r["regional_applies"], -(r["hourly"] or 0), r["industry"]))
    return {"by_pref": by, "table_label": data.get("table_label"), "fetched_at": data["fetched_at"], "source": data["source"]}


def _amount(r: dict, k) -> str:
    return k.yen(r["hourly"]) if r["hourly"] is not None else "-"


def section(d: dict, r: dict, k) -> str:
    ind = d["industry"]
    rows = ind["by_pref"][r["short"]]
    name = k.esc(r["name"])
    applies = [x for x in rows if not x["regional_applies"]]
    marked = [x for x in rows if x["regional_applies"]]
    if applies:
        top = applies[0]
        names = "、".join(f"{k.esc(x['industry'])}({_amount(x, k)})" for x in applies)
        lead = (f"<p>{name}には、特定(産業別)最低賃金が{len(rows)}産業分あります。このうち{len(applies)}産業は、特定の額が適用されます。"
                f"最も高いのは、{k.esc(top['industry'])}の{_amount(top, k)}で、{k.jp_date(top['effective_date'])}に発効しました。</p>"
                f"<p>特定の額が適用されるのは、{names}です。</p>")
    else:
        lead = (f"<p>{name}には、特定(産業別)最低賃金が{len(rows)}産業分あります。いずれも、厚生労働省の表で「※」が付いていて、地域別最低賃金が適用される額です。</p>")
    if applies and marked:
        lead += f"<p>残りの{len(marked)}産業は、「※」が付いていて、地域別最低賃金が適用されます。</p>"
    body = "".join(
        f"<tr><td>{k.esc(x['industry'])}</td><td>{_amount(x, k)}</td><td>{k.yen(x['daily']) if x['daily'] is not None else '-'}</td>"
        f"<td>{k.jp_date(x['effective_date'])}</td><td>{'地域別(※)' if x['regional_applies'] else '特定の額'}</td></tr>" for x in rows)
    label = k.esc(ind.get("table_label") or "")
    return (f'<h2>{name}の特定(産業別)最低賃金</h2>\n{lead}\n<div class="tablewrap"><table><thead><tr><th>産業名</th><th>時間額</th><th>日額</th><th>発効日</th><th>適用される額</th></tr></thead>'
            f'<tbody>{body}</tbody><tfoot><tr><td colspan="5">厚生労働省「特定(産業別)最低賃金全国一覧」({label})。データの取得日: {k.jp_date(ind["fetched_at"][:10])}。'
            f'地域別最低賃金と特定(産業別)最低賃金の両方が当てはまるときは、高い方が適用されます(最低賃金法第6条第1項)。仕組みは<a href="/guide/what-is/">最低賃金とは?</a>に書いています。</td></tr></tfoot></table></div>\n')
