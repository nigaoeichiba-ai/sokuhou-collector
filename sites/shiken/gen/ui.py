"""HTML pieces of the new design (cards, counters, bands, bars, tools).  Plain strings; the stylesheet is assets/style.css, the behaviour assets/shiken.js.

The urgency of a counter is told by the number (the colour) and by a word (the label): never by the colour alone.
"""
from __future__ import annotations

import html
import json

from . import ics
from .common import TODAY, d, left, jp, md, today_j
from .model import EVENT_LIST, TYPE_LABEL, application_start_of, when_text


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def a(href: str, text: str, cls: str = "") -> str:
    return f'<a{" class=" + chr(34) + cls + chr(34) if cls else ""} href="{esc(href)}">{text}</a>'


def state(n: int, kind: str = "deadline") -> tuple[str, str, str]:
    """(class, label, counter text) for n days left.  deadline: 7 days or less is red, 8-30 yellow, 31 or more blue; an exam day is blue/navy."""
    if n < 0:
        return "past", "終了", f"{-n}日前に終了"
    if n == 0:
        return ("today" if kind == "deadline" else "examday"), "本日", "本日"
    if kind == "deadline":
        cls = "red" if n <= 7 else "yellow" if n <= 30 else "blue"
        return cls, "まもなく締切" if n <= 7 else "", f"あと{n}日"
    return "blue", "", f"あと{n}日"


def counter(iso: str, kind: str = "deadline", big: bool = True) -> str:
    n = left(iso)
    cls, label, text = state(n, kind)
    if n > 0:
        inner = f'あと<b class="num">{n}</b>日'
    elif n == 0:
        inner = '<b class="num">本日</b>'
    else:
        inner = f'<span class="past-text">{-n}日前に終了</span>'
    lab = f'<span class="urgent-label">{esc(label)}</span>' if label and n >= 0 else ""
    return f'<div class="days {cls}{" big" if big else ""}" data-countdown="{esc(iso)}" data-kind="{kind}">{inner}{lab}</div>'


def when_line(e: dict) -> str:
    t = when_text(e)
    return f'<p class="when"><b>{esc(t)}</b>{"まで" if e["type"] == "application_deadline" and e["time"] else ""}</p>'


def card(e: dict, *, buttons: bool = True) -> str:
    n = left(e["iso"])
    cls = state(n, "deadline" if e["type"] == "application_deadline" else "exam")[0]
    lab = TYPE_LABEL[e["type"]]
    st = state(n, "deadline")[1] if e["type"] == "application_deadline" else ""
    top = f'<div class="top"><span class="cat">{esc(e["cat"])} ・ {lab}</span>{"<span class=" + chr(34) + "state" + chr(34) + ">" + esc(st) + "</span>" if st else ""}</div>'
    btns = ""
    if buttons:
        btns = (f'<div class="actions"><a class="btn solid" href="{esc(e["url"])}">詳細を見る</a>'
                f'<button type="button" class="btn js-my" data-exam="{esc(e["exam"])}" data-name="{esc(e["name"])}" data-url="{esc(e["url"])}" aria-pressed="false">マイ試験に追加</button>'
                f'<a class="btn" href="{esc(ics.gcal(e))}" target="_blank" rel="noopener">Googleカレンダー</a>'
                f'<a class="btn" href="/ics/{esc(ics.file_name(e))}" download>ICS保存</a></div>')
    return (f'<article class="dcard {cls}" data-name="{esc(e["name"])}" data-exam="{esc(e["exam"])}" data-event="{esc(e["id"])}">'
            f'{top}<h3><a href="{esc(e["url"])}">{esc(e["name"])}</a></h3>{when_line(e)}{counter(e["iso"])}{btns}</article>')


def urgent_band(events: list[dict]) -> str:
    near = [e for e in events if 0 <= left(e["iso"]) <= 7]
    if not near:
        return ""
    e = near[0]
    more = f'<a class="more" href="/deadlines/">ほか{len(near) - 1}件</a>' if len(near) > 1 else ""
    n = left(e["iso"])
    until = md(e["iso"]) + (" " + e["time"] if e["time"] else "")
    return (f'<div class="urgent" role="status" data-countdown="{esc(e["iso"])}" data-kind="band"><span class="u-badge">まもなく締切</span>'
            f'<a class="u-text" href="{esc(e["url"])}">{esc(e["name"])} 申込締切まで <b>あと{n}日</b>（{esc(until)} まで）</a>{more}</div>')


def bars(rows: list[dict], title: str, unit: str = "%") -> str:
    """A bar chart in HTML (0-based axis, the value on every bar) and, straight under it, the same numbers as a table.  rows: label, value."""
    top = max(r["value"] for r in rows)
    scale = 100 / max(top * 1.15, 1)
    cols = "".join(f'<div class="bar"><span class="val">{r["value"]:.1f}{unit}</span><span class="col" style="height:{r["value"] * scale:.1f}%"></span></div>' for r in rows)
    lbls = "".join(f'<div>{esc(r["label"])}</div>' for r in rows)
    return (f'<figure class="chart" role="img" aria-label="{esc(title)}。下の表に同じ数字があります。"><div class="bars" style="--n:{len(rows)}">{cols}</div>'
            f'<div class="bar-lbls" style="--n:{len(rows)}">{lbls}</div></figure>')


def table(cols: list[str], rows: list[list], caption: str = "", num: tuple[int, ...] = ()) -> str:
    head = "".join(f'<th{" class=num" if i in num else ""}>{esc(c)}</th>' for i, c in enumerate(cols))
    body = "".join("<tr>" + "".join(f'<td{" class=num" if i in num else ""} data-label="{esc(cols[i])}">{c if isinstance(c, str) and c.startswith("<") else esc(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return f'<div class="tablewrap"><table class="stack">{cap}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def steps(items: list[tuple[str, str, str]], now_index: int | None) -> str:
    """The progress band: (label, date text, class) per step.  The step the reader is at is marked in the words as well as in the colour."""
    out = []
    for i, (label, dt, extra) in enumerate(items):
        mark = "done" if now_index is not None and i < now_index else "now" if i == now_index else "future"
        here = '<span class="here">現在地</span>' if mark == "now" else ""
        out.append(f'<li class="seg {mark}"><b>{esc(label)}</b><span>{esc(dt)}</span>{here}{("<em>" + esc(extra) + "</em>") if extra else ""}</li>')
    return f'<ol class="progress">{"".join(out)}</ol>'


def cost_tool(fee: int, fee_note: str) -> str:
    return f'''<div class="tool" id="cost" data-fee="{fee}">
<div class="row"><label>受験料（公式の金額・固定）<output class="fixed">{fee:,}円（{esc(fee_note)}）</output></label></div>
<div class="row"><label>テキスト代（円）<input type="number" inputmode="numeric" min="0" step="1" value="0" data-cost></label>
<label>問題集代（円）<input type="number" inputmode="numeric" min="0" step="1" value="0" data-cost></label></div>
<div class="row"><label>模試代（円）<input type="number" inputmode="numeric" min="0" step="1" value="0" data-cost></label>
<label>その他（円）<input type="number" inputmode="numeric" min="0" step="1" value="0" data-cost></label></div>
<p class="total-line">合計（受験料込み）<span class="total"><b data-total>{fee:,}</b> 円</span></p>
<p class="warn-text" data-cost-warn role="alert" hidden>マイナスの金額や数字でない入力は、0円として計算しています。</p>
<p class="hint">受験料は公式の金額で、{esc(fee_note)}です。そのほかは、入力した金額の合計です。</p></div>'''


def planner_tool(fixed_date: str | None, hint: str) -> str:
    dt = (f'<label>目標日（試験日など）<input type="date" data-plan-date value="{esc(fixed_date)}"></label>' if fixed_date
          else '<label>目標日（試験日など）<input type="date" data-plan-date></label>')
    return f'''<div class="tool" id="planner" data-today="{TODAY.isoformat()}">
<div class="row">{dt}
<label>目標の総学習時間（時間）<input type="number" inputmode="decimal" min="1" step="1" data-plan-total></label></div>
<div class="row"><label>平日1日の学習時間（時間）<input type="number" inputmode="decimal" min="0" step="0.5" data-plan-weekday></label>
<label>休日1日の学習時間（時間・省略可）<input type="number" inputmode="decimal" min="0" step="0.5" data-plan-weekend></label></div>
<div class="plan-out" data-plan-out aria-live="polite"><p>目標日、総学習時間、平日の学習時間を入れると、勉強を始める日の目安が出ます。{esc(hint)}</p></div></div>'''


def json_script(id_: str, obj) -> str:
    return f'<script type="application/json" id="{id_}">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


SCRIPT = '<script src="/assets/shiken.js" defer></script>'


def event_data() -> dict:
    """What the page's script needs: the events (no source, no check day), and the deadline cards the views draw."""
    keys = ("id", "exam", "name", "cat", "type", "iso", "time", "end", "note", "url", "variant")
    return {"events": [{k: e[k] for k in keys} for e in EVENT_LIST]}
