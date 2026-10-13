"""特集: a long page for a big event, made from numbers and facts, with our own view marked as such (data/atomou/features/<slug>.json).

What a feature holds: a lead, the sections (a heading, paragraphs, a table, a bar chart, and whether the section is our view), a log of updates (the page is kept up to the day of the event),
the cards it belongs to (the cards link to it with one line), and the stage ("準備中" is not found by search engines; "公開" is).
The grounds are numbers and facts; what we make of them is marked "当サイトの見方" and shows how the figure was made.  The page says that it is made by the site from the numbers (not a
person's own opinion).  Nothing here is copied: the text is ours, the numbers are facts."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from sokuhou.sitekit import crumbs, esc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FEATURE_DIR = ROOT / "data" / "atomou" / "features"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,40}")
STAGES = ("準備中", "公開")


def load_features(directory: Path = FEATURE_DIR) -> list[dict]:
    out = []
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        f = json.loads(path.read_text(encoding="utf-8"))
        if valid(f):
            out.append(f)
    return out


def valid(f: dict) -> bool:
    """The form of a feature (the page is built only from one that has it): a slug, a title, a lead, a stage, sections that each have a heading and something to show."""
    if not isinstance(f, dict) or not SLUG.fullmatch(str(f.get("slug", ""))) or f.get("stage") not in STAGES:
        return False
    if not all(isinstance(f.get(k), str) and f[k].strip() for k in ("title", "lead", "method")):
        return False
    secs = f.get("sections")
    if not isinstance(secs, list) or not secs:
        return False
    for s in secs:
        if not isinstance(s, dict) or not str(s.get("h", "")).strip():
            return False
        if not (s.get("paras") or s.get("table") or s.get("chart")):
            return False
        t = s.get("table")
        if t and (not isinstance(t.get("head"), list) or not isinstance(t.get("rows"), list) or any(len(r) != len(t["head"]) for r in t["rows"])):
            return False
        ch = s.get("chart")
        if ch and (not isinstance(ch.get("rows"), list) or any(not (isinstance(r, list) and len(r) == 2 and isinstance(r[1], (int, float))) for r in ch["rows"])):
            return False
    return True


def indexable(f: dict) -> bool:
    return f.get("stage") == "公開"


def bar_svg(chart: dict) -> str:
    """A horizontal bar chart in plain SVG (no script): rows = [[label, number], ...]; the figure is written at the end of each bar."""
    rows = chart["rows"]
    hi = max(v for _, v in rows) or 1
    lo = min(0.0, min(v for _, v in rows))
    span = hi - lo or 1
    h = 38
    out = [f'<svg class="bars" role="img" aria-label="{esc(chart.get("title", ""))}" viewBox="0 0 640 {h * len(rows) + 8}" xmlns="http://www.w3.org/2000/svg">']
    for i, (label, v) in enumerate(rows):
        y = 4 + i * h
        w = max(2.0, (v - lo) / span * 250)
        out.append(f'<text x="0" y="{y + 24}" class="bl">{esc(label)}</text><rect x="250" y="{y + 6}" width="{w:.1f}" height="24" rx="3" class="bar"/>'
                   f'<text x="{256 + w:.1f}" y="{y + 24}" class="bv">{esc(_num(v))}{esc(chart.get("unit", ""))}</text>')
    out.append("</svg>")
    return "".join(out)


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def section_html(s: dict) -> str:
    h = [f'<section class="ft-sec{" ft-view" if s.get("view") else ""}"><h2>{esc(s["h"])}</h2>']
    if s.get("view"):
        h.append('<p class="ft-tag">当サイトの見方</p>')
    for p in s.get("paras") or []:
        h.append(f"<p>{esc(p)}</p>")
    t = s.get("table")
    if t:
        head = "".join(f"<th>{esc(c)}</th>" for c in t["head"])
        rows = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in t["rows"])
        h.append(f'<div class="tablewrap"><table class="info-table ft-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>')
        if t.get("note"):
            h.append(f'<p class="small muted">{esc(t["note"])}</p>')
    ch = s.get("chart")
    if ch:
        h.append(f'<figure class="ft-chart"><figcaption>{esc(ch.get("title", ""))}</figcaption>{bar_svg(ch)}</figure>')
    if s.get("how"):
        h.append(f'<p class="small muted ft-how">求め方: {esc(s["how"])}</p>')
    h.append("</section>")
    return "".join(h)


def feature_page(c, f: dict, name: str, top_card: str = "") -> tuple[str, bool]:
    """(the page, whether search engines may find it).  top_card: the card of the event (the count of days the page is about), shown under the heading."""
    log = "".join(f'<li><time datetime="{esc(x["on"])}">{esc(x["on"])}</time> {esc(x["text"])}</li>' for x in sorted(f.get("updates") or [], key=lambda x: x["on"], reverse=True))
    stage = f.get("stage")
    updated = max([x["on"] for x in f.get("updates") or []] or [""])
    body = crumbs([("トップ", "/"), ("特集", "/tokushu/"), (f["title"], None)]) + f"""
<h1>{esc(f["title"])}</h1>
<p class="ft-meta"><span class="vbadge vb-{"ok" if stage == "公開" else "pending"}">{esc(stage)}</span>{f' <span class="small muted">最終更新 {esc(updated)}</span>' if updated else ""}</p>
{f'<div class="cards ft-card">{top_card}</div>' if top_card else ""}
<p class="lead">{esc(f["lead"])}</p>
<p class="small muted">この特集は、公式の記録など数字と事実をもとに、当サイトが作った分析です。「当サイトの見方」の部分は当サイトの見解で、断定ではありません。{esc(f["method"])}</p>
{"".join(section_html(s) for s in f["sections"])}
{f'<h2>更新の記録</h2><ul class="changes">{log}</ul>' if log else ""}
<p class="small muted">カードの日付や数字は、間違っていることがあります。間違いに気づいたときは、<a href="/contact/?kind=date">お問い合わせ</a>からお知らせください。</p>"""
    desc = f["lead"][:110]
    return c.page(f"/tokushu/{f['slug']}/", f"{f['title']} | {name}", desc, body, "feature", noindex=not indexable(f)), indexable(f)


def features_index(c, feats: list[dict], name: str) -> str:
    cards = "".join(f'<a class="uc" href="/tokushu/{f["slug"]}/"><b>{esc(f["title"])}</b><span>{esc(f["lead"][:60])}</span></a>' for f in feats if indexable(f) or True)
    body = crumbs([("トップ", "/"), ("特集", None)]) + f"""
<h1>特集</h1>
<p class="lead muted">大きな行事を、数字から読む特集です。日付のカードから、くわしい分析のページへ進めます。</p>
<div class="uc-grid">{cards}</div>"""
    return c.page("/tokushu/", f"特集 | {name}", "大きな行事を、公式の記録など数字をもとに読む特集。日程・結果・過去の記録を、あと何日、もう何日とともに。", body, "feature", noindex=not any(indexable(f) for f in feats))


def card_link(feats: list[dict], title: str, day: str) -> str:
    """The one line a day's page shows when a feature is about it (the cards stay short; the long reading is on the feature's page)."""
    for f in feats:
        if any(str(x.get("title", "")).strip() == title.strip() and x.get("date") == day for x in f.get("cards") or []):
            return f'<p class="ev-feature"><a class="btn small" href="/tokushu/{f["slug"]}/">特集: {esc(f["title"])}</a></p>'
    return ""


def today_stage(f: dict, today: date) -> str:
    return f.get("stage", "")
