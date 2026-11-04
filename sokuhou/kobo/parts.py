"""Parts made by machine from confirmed values, with no AI (the owner's goal, 2026-11-04: text that needs no AI to come out right).

table_intro      the sentence before a quick-reference table (slots: the people range, what the columns tell)
quick_table      a quick-reference table from rates x people x days (the numbers are computed, never typed)
calculator_html  a small page part: enter the number of people, get the amounts (same formula as the table)

A rate is a confirmed value of the material (e.g. water: 3 litres per person per day, 防災庁の要請). Nothing here invents a figure.
"""
from __future__ import annotations

import html


def table_intro(lo: int, hi: int, what: list[str], who: str = "いっしょに暮らす人数") -> str:
    """'早見表は、1人から5人までの人数別です。いっしょに暮らす人数の行を見ると、水、食料、携帯トイレの目安が分かります。'  (the owner changed 家の人数, 2026-11-04)"""
    return f"早見表は、{lo}人から{hi}人までの人数別です。{who}の行を見ると、{'、'.join(what)}の目安が分かります。"


def amount(people: int, per_person_day: float, days: int):
    v = people * per_person_day * days
    return int(v) if float(v).is_integer() else round(v, 1)


def quick_table(columns: list[dict], max_people: int = 5) -> str:
    """columns: [{"head": "水 3日分", "rate": 3, "days": 3, "unit": "L"}, ...] -> Markdown table, one row per number of people."""
    heads = ["人数"] + [c["head"] for c in columns]
    lines = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    for n in range(1, max_people + 1):
        lines.append("| " + " | ".join([f"{n}人"] + [f"{amount(n, c['rate'], c['days'])}{c.get('unit', '')}" for c in columns]) + " |")
    return "\n".join(lines)


def over_five_note(unit_row: str = "1人の行") -> str:
    return f"6人以上の家は、{unit_row}の数に人数をかけると出せます。"


def calculator_html(items: list[dict], days: list[int] = (3, 7), label: str = "いっしょに暮らす人数") -> str:
    """items: [{"name": "水", "rate": 3, "unit": "リットル"}, ...]. Returns a self-contained block (no external script)."""
    rows = "".join(
        f'<tr><th scope="row">{html.escape(i["name"])}</th>' + "".join(f'<td data-rate="{i["rate"]}" data-days="{d}" data-unit="{html.escape(i["unit"])}"></td>' for d in days) + "</tr>"
        for i in items)
    head = "".join(f"<th>{d}日分</th>" for d in days)
    return (f'<div class="kobo-calc"><label>{html.escape(label)}: <input type="number" min="1" max="99" value="4" inputmode="numeric"> 人</label>'
            f'<table><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table>'
            '<script>(function(){var b=document.currentScript.parentNode,i=b.querySelector("input");function f(){var n=parseInt(i.value,10)||0;'
            'b.querySelectorAll("td[data-rate]").forEach(function(td){var v=n*parseFloat(td.dataset.rate)*parseInt(td.dataset.days,10);'
            'td.textContent=(Math.round(v*10)/10)+td.dataset.unit;});}i.addEventListener("input",f);f();})();</script></div>')
