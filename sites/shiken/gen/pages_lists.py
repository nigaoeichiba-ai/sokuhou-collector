"""The lists (/deadlines/, /schedule/) in cards, over the tables they already have, and a 'not confirmed' row in /fees/ (spec 4.6)."""
from __future__ import annotations

from . import ui
from .model import deadline_events, examination_events, EVENT_LIST
from .pages_v2 import data_blob, esc

GROUP = {"語学": "語学・教養", "語学・教養": "語学・教養", "大学入試": "入試"}


def group(cat: str) -> str:
    return GROUP.get(cat, "資格")


def restyle(p: dict) -> dict:
    path = p["path"]
    if path == "/deadlines/":
        cards = "".join(ui.card(e) for e in deadline_events())
        p["sections"] = [{"h2": "一覧", "html": f'<p class="sec-sub">締切が近い順です。締切の時刻がある試験は、同じ日の中で先に表示されます。</p><div class="cards">{cards}</div>'}] + p["sections"] + [{"html": data_blob([])}]
    elif path == "/schedule/":
        evs = examination_events()
        chips = ('<div class="viewswitch" role="group" aria-label="分野で絞り込む">' + "".join(
            f'<button type="button" data-chip="{k}" aria-pressed="{"true" if k == "all" else "false"}">{t}</button>' for k, t in (("all", "すべて"), ("資格", "資格"), ("語学・教養", "語学・教養"), ("入試", "入試"))) + "</div>")
        cards = "".join(f'<div data-cat="{esc(group(e["cat"]))}" style="display:contents">{ui.card(e)}</div>' for e in evs)
        p["sections"] = [{"h2": "一覧", "html": f'<p class="sec-sub">今後の試験日です。分野で絞り込めます。</p>{chips}<div class="cards">{cards}</div>'}] + p["sections"] + [{"html": data_blob([])}]
    return p
