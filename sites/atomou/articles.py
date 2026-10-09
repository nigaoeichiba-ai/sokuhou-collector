"""The explanation on an event's detail page: what the day is, when and where, what to check, and the usual questions.

Everything that varies from event to event (date, place, kind, source, how long) is composed here from the catalog entry; what a *subject* is
(a marathon, a TOEIC sitting, a meteor shower ...) comes from data/atomou/guides.json, written once per subject and kept to facts that do not change.
A page without a guide for its subject gets no explanation block at all rather than a filler one: the build test requires every subject to have one.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sokuhou.sitekit import esc

ROOT = Path(__file__).resolve().parents[2]
GUIDES_FILE = ROOT / "data" / "atomou" / "guides.json"

# the verb after the date, for the day that is still to come and for the day that has passed
KIND_VERB = {
    "開催": ("に開催されます", "に開催されました"),
    "試験日": ("に実施されます", "に実施されました"),
    "開始": ("に始まります", "に始まりました"),
    "締切": ("が締切です", "が締切でした"),
    "改定": ("に改定されます", "に改定されました"),
    "発表": ("に発表されます", "に発表されました"),
    "極大": ("に極大を迎えます", "に極大を迎えました"),
    "終了": ("に終了します", "に終了しました"),
    "決勝": ("に行われます", "に行われました"),
    "施行": ("に施行されます", "に施行されました"),
    "発売": ("に発売されます", "に発売されました"),
    "衝": ("に衝を迎えます", "に衝を迎えました"),
}
KIND_ROW = {"開催": "開催", "試験日": "試験日", "開始": "開始日", "締切": "締切", "改定": "改定日", "発表": "発表日", "極大": "極大日", "終了": "終了日",
            "決勝": "決勝", "施行": "施行日", "発売": "発売日", "衝": "衝の日"}


def load_guides(path: Path = GUIDES_FILE) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {g["subject"]: g for g in data}


def _span(e: dict, fmt) -> tuple[str, str]:
    """('2026年10月30日(金)から11月3日(火)まで', '5日間') for a range, ('2027年3月5日(金)', '') for one day."""
    start = fmt(e["date"], e["precision"])
    if not e.get("date_end"):
        return start, ""
    a, b = date.fromisoformat(e["date"]), date.fromisoformat(e["date_end"])
    end = fmt(e["date_end"], e["precision"])
    if a.year == b.year:   # "11月3日(火)": the year is not repeated
        end = end.split("年", 1)[1] if "年" in end else end
    return f"{start}から{end}まで", f"{(b - a).days + 1}日間"


def when_text(e: dict, fmt, today: date) -> str:
    """The date as a phrase: '2026年10月30日(金)から11月3日(火)まで'. Past or future is not part of it."""
    return _span(e, fmt)[0]


DAY_KINDS = {"改定", "施行", "終了", "発表", "開始", "発売", "極大", "衝"}
AREA_KINDS = {"改定", "終了", "施行", "改正", "締切"}   # the place of these is the area they apply to, not a venue (the same set the cards use)


def _two_days(e: dict, fmt) -> str | None:
    """'2026年10月24日(土)・25日(日)' when a range is one or two days long inside one month, else None."""
    if not e.get("date_end") or e["precision"] != "day":
        return None
    a, b = date.fromisoformat(e["date"]), date.fromisoformat(e["date_end"])
    if (b - a).days not in (1, 2) or a.month != b.month or a.year != b.year:
        return None
    return fmt(e["date"], "day") + "・" + fmt(e["date_end"], "day").split("月", 1)[1]


def lead(e: dict, fmt, today: date) -> str:
    verb = KIND_VERB.get(e["kind"], ("に行われます", "に行われました"))
    last = date.fromisoformat(e.get("date_end") or e["date"])
    past = last < today
    when, _ = _span(e, fmt)
    i = 1 if past else 0
    short = _two_days(e, fmt)
    if e["kind"] in DAY_KINDS and e["precision"] != "day":     # "…の令和9年分への改定は、2027年1月ごろの予定です。" (a month is not a day)
        s = f"{e['title']}は、{when}{'でした' if past else 'の予定です'}。"
    elif e["kind"] in DAY_KINDS and not (e.get("date_end") and not short):
        # "2027年2月11日(木)は、「木星が衝(一晩中見える時期)」の日です。": these titles say what happens (it is a statement, or it repeats the kind), so the title is quoted instead of made the subject
        s = f"{when}は、{e['title']}です。" if e["title"].endswith("日") else f"{when}は、「{e['title']}」の日{'でした' if past else 'です'}。"
        s = s.replace("の日でした。", "の日でした。") if past else s
    elif e["kind"] in ("極大", "衝"):
        s = f"{when}は、「{e['title']}」の期間{'でした' if past else 'です'}。"
    elif e.get("date_end") and not short:
        if e["kind"] in ("開催", "試験日"):   # a range takes "まで" and no "に": 2026年10月17日(土)から2027年2月14日(日)まで開催されます
            s = f"{e['title']}は、{when}{verb[i][1:]}。"
        else:
            s = f"{e['title']}は、{when}{'でした' if past else 'です'}。"
    elif e["kind"] == "締切" and "締切" in e["title"]:     # "…申込締切は、2027年2月3日(水)です。" (not "…締切は、…が締切です")
        s = f"{e['title']}は、{when}{'でした' if past else 'です'}。"
    else:
        s = f"{e['title']}は、{short or when}{verb[i]}。"
    place = (e.get("place") or "").strip()
    if place and place not in ("全国", "地域"):
        s += f"{'対象地域' if e['kind'] in AREA_KINDS else '場所'}は{place}です。"
    return s


def facts(e: dict, fmt, host: str) -> list[tuple[str, str]]:
    when, length = _span(e, fmt)
    rows = [(KIND_ROW.get(e["kind"], "日付"), when + (f"({length})" if length else ""))]
    place = (e.get("place") or "").strip()
    if place and place not in ("地域",):
        rows.append(("場所", place))
    elif e.get("region"):
        rows.append(("地域", e["region"]))
    rows.append(("ジャンル", e["group"] + (f" / {e['subject']}" if e.get("subject") else "")))
    rows.append(("確認日", fmt(e["checked_on"], "day")))
    return rows


ASTRO_SUBJECTS = {"流星群", "月と土星", "満月", "火星と木星", "水星", "金星", "日食", "木星", "火星", "土星", "月食"}


def _change_note(e: dict) -> tuple[str, str]:
    """The question about changes, worded for the kind of day (a meteor shower, a system change and a festival do not change for the same reasons)."""
    if e["subject"] in ASTRO_SUBJECTS or e["kind"] in ("極大", "衝"):
        return ("日付が変わることはありますか。",
                "天体の動きから計算した日付なので、日付そのものはほとんど変わりません。見え方は、天候や場所、時刻によって変わります。時刻の詳細は、国立天文台などの公式ページでご確認ください。")
    if e["group"] == "締切・制度":
        return ("内容や日付が変わることはありますか。",
                "制度の内容や実施の時期は、今後の発表で変わることがあります。手続きの前に、出典の公式ページで最新の情報をご確認ください。")
    if e["group"] == "消費・セール":
        return ("日付が変わることはありますか。",
                "セールやサービスの内容と日付は、実施する会社の都合で変わることがあります。購入や申し込みの前に、公式ページでご確認ください。")
    return ("日程が変わることはありますか。",
            "主催者の都合や天候などで、日程が変わったり、中止になったりすることがあります。申し込みや参加の前に、公式ページで最新の情報をご確認ください。")


def faq(e: dict, fmt, today: date, guide: dict | None) -> list[tuple[str, str]]:
    when, _ = _span(e, fmt)
    last = date.fromisoformat(e.get("date_end") or e["date"])
    start = date.fromisoformat(e["date"])
    if e["precision"] != "day":
        left = f"{when}の予定です。"
    elif last < today:
        left = f"{when}でした。もう{(today - last).days}日が過ぎています。"
    elif start <= today <= last:
        left = f"{when}です。" + ("今日がその日です。" if start == last else "現在、期間中です。")
    else:
        left = f"{when}です。{today.year}年{today.month}月{today.day}日の時点で、あと{(start - today).days}日です。"
    name = f"「{e['title']}」" if e["kind"] in DAY_KINDS else e["title"]
    out = [(f"{name}はいつですか。", left)]
    place = (e.get("place") or "").strip()
    if place and place not in ("全国", "地域"):
        out.append(("どの地域が対象ですか。" if e["kind"] in AREA_KINDS else "場所はどこですか。", f"{place}です。"))
    out.append(_change_note(e))
    for q in (guide or {}).get("faq", [])[:2]:
        out.append((q["q"], q["a"]))
    return out


def article_html(e: dict, fmt, host: str, today: date, guide: dict | None) -> str:
    """The block under the card: 概要 / 日程と場所 / 日程の見方と準備 / よくある質問.  Empty when the subject has no guide."""
    if not guide:
        return ""
    rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts(e, fmt, host))
    tips = "".join(f"<li>{esc(t)}</li>" for t in guide["tips"])
    qa = "".join(f"<div class=\"qa\"><h3>{esc(q)}</h3><p>{esc(a)}</p></div>" for q, a in faq(e, fmt, today, guide))
    return f"""<section class="article" id="gaiyou">
<h2>{esc(e['title'])}の概要</h2>
<p>{esc(lead(e, fmt, today))}</p>
<p>{esc(guide['about'])}</p>
<h2>日付の詳細</h2>
<dl class="info">{rows}</dl>
<h2>{esc(e['subject'])}の日程の見方</h2>
<p>{esc(guide['when'])}</p>
<h2>確かめておきたいこと</h2>
<ul class="tips">{tips}</ul>
<h2>よくある質問</h2>
{qa}
</section>"""
