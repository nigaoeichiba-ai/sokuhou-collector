"""A prefecture page's "what could next year's minimum wage be" table: three plain extrapolations of the prefecture's own recent raises.

Nothing here is a forecast of the real decision (the councils decide in summer each year).  Every number is computed from the prefecture's own series in
`r["long"]`: the same raise as the last year, the average raise of the last three years, and the average rate of the last three years.
"""
from __future__ import annotations

import math

from sites.saichin import work_pages


def _recent(r: dict) -> list[dict]:
    return [e for e in r["long"] if e.get("amount") is not None]


def scenarios(r: dict) -> dict | None:
    """The three extrapolations for the year after the latest one, or None when the series is too short.

    Returns {"fy", "base", "same_raise": (raise, amount), "avg3_raise": (raise, amount), "avg3_pct": (pct, amount), "to1500": (years, fy) or None}.
    """
    s = _recent(r)
    if len(s) < 5 or s[-1]["amount"] != r["amount"]:
        return None
    base = s[-1]["amount"]
    raises = [s[i]["amount"] - s[i - 1]["amount"] for i in range(len(s) - 3, len(s))]
    rates = [s[i]["amount"] / s[i - 1]["amount"] - 1 for i in range(len(s) - 3, len(s))]
    last = raises[-1]
    avg_raise = sum(raises) / 3
    avg_rate = sum(rates) / 3
    out = {
        "fy": s[-1]["fy"] + 1,
        "base": base,
        "raises": raises,
        "same_raise": (last, base + last),
        "avg3_raise": (round(avg_raise), base + round(avg_raise)),
        "avg3_pct": (avg_rate * 100, round(base * (1 + avg_rate))),
        "to1500": None,
    }
    if base < 1500 and round(avg_raise) > 0:
        years = math.ceil((1500 - base) / round(avg_raise))
        out["to1500"] = (years, s[-1]["fy"] + years)
    return out


def _fy_label(fy: int) -> str:
    return "令和元年度" if fy == 2019 else f"令和{fy - 2018}年度"


def first_1000(r: dict) -> dict | None:
    """The first year of the series whose amount is 1,000 yen or more (None if it never was)."""
    return next((e for e in _recent(r) if e["amount"] >= 1000), None)


def faq_1000(r: dict, k) -> str:
    """The question people type ("最低賃金 1000円 いつから"), answered from the prefecture's own series."""
    e = first_1000(r)
    if e is None:
        return ""
    name = k.esc(r["name"])
    before = [x for x in _recent(r) if x["fy"] < e["fy"]]
    prev = f"、その前の{k.esc(before[-1]['label'])}は{before[-1]['amount']:,.0f}円" if before else ""
    return (f"<h3>{name}の最低賃金は、いつから1,000円以上ですか</h3>"
            f"<p>{k.esc(e['label'])}からです。この年度の額は{e['amount']:,.0f}円{prev}でした。</p>")


def section(d: dict, r: dict, k) -> str:
    sc = scenarios(r)
    if sc is None:
        return ""
    name = k.esc(r["name"])
    nxt = _fy_label(sc["fy"])
    cur = _fy_label(sc["fy"] - 1)
    base = sc["base"]
    r1, a1 = sc["same_raise"]
    r2, a2 = sc["avg3_raise"]
    p3, a3 = sc["avg3_pct"]
    raises = "・".join(f"+{x}円" for x in sc["raises"])
    rows = (
        f'<tr><th scope="row">前の年度と同じ額だけ上がる</th><td>+{r1}円</td><td>{a1:,}円</td></tr>'
        f'<tr><th scope="row">直近3年度の引上げ額の平均だけ上がる</th><td>+{r2}円</td><td>{a2:,}円</td></tr>'
        f'<tr><th scope="row">直近3年度の平均の上がり率({p3:.2f}%)で上がる</th><td>+{a3 - base}円</td><td>{a3:,}円</td></tr>'
    )
    if sc["to1500"]:
        yrs, fy = sc["to1500"]
        rows += f'<tr><th scope="row">平均の引上げ額が続くと、1,500円に届く年度</th><td>{yrs}年後</td><td>{_fy_label(fy)}</td></tr>'
    foot = ("<tfoot><tr><td colspan=\"3\">過去の動きを延ばしただけの試算です。実際の額は、毎年夏に国の目安をふまえて、地方の審議会が決めます。"
            "引上げ額は年によって大きく変わります。</td></tr></tfoot>")
    return (
        f"<h2>{name}の最低賃金は、{nxt}にいくらになるか(試算)</h2>"
        f"<p>{cur}の{base:,}円と、直近3年度の引上げ額({raises})から計算した試算で、実際の額ではありません。</p>"
        '<div class="tablewrap"><table><thead><tr><th>計算のしかた</th><th>引上げ額</th><th>' + nxt + 'の額</th></tr></thead><tbody>'
        + rows + "</tbody>" + foot + "</table></div>"
        + faq_1000(r, k)
        + work_pages.jobs_block(f"{name}の最低賃金{base:,}円より高い時給の仕事を探すときの例です。")
    )
