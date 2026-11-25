"""The year-end equipment page for sole proprietors (manuscript consult/year-end-expenses.md, written by Codex, 2026-11-25).

The manuscript is Markdown: `#` title, an opening paragraph, the hero image, `## この記事の要点` as a list, then sections with
paragraphs, `-` lists (`**x**` is bold), one table, the schedule picture, `〔アフィリ設置箇所：…〕` (editing marks: nothing of them is shown) and the date line.
"""
from html import escape
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parent / "consult" / "year-end-expenses.md"
SLUG = "case-year-end-expenses"
CHECKED = "2026-11-25"
IMAGE = re.compile(r"^!\[(.*)\]\((.*)\)$")


def _inline(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(text))


def _table(rows):
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    head, body = cells[0], cells[2:]        # the second row is the |---| rule
    thead = "".join(f'<th scope="col">{_inline(c)}</th>' for c in head)
    tbody = "".join('<tr><th scope="row">' + _inline(r[0]) + "</th>" + "".join(f"<td>{_inline(c)}</td>" for c in r[1:]) + "</tr>" for r in body)
    return (f'<div class="table-scroll tablewrap year-table" tabindex="0" role="region" aria-label="取得価額ごとの扱いの表">'
            f'<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')


def parse(text=None):
    text = text if text is not None else SOURCE.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.split("\n")]
    title = next(line[2:] for line in lines if line.startswith("# "))
    lead, points, sections, foot, items, rows = [], [], [], "", [], []
    cur = None

    def flush():
        nonlocal items, rows
        if items:
            if cur and cur["h"] == "この記事の要点":
                points.extend(items)
            else:
                cur["html"].append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
            items = []
        if rows:
            cur["html"].append(_table(rows))
            rows = []

    for line in lines:
        if line.startswith("- "):
            items.append(line[2:]); continue
        if line.startswith("|"):
            rows.append(line); continue
        flush()
        if not line or line.startswith("# ") or line.startswith("〔アフィリ設置箇所："):
            continue
        if line.startswith("## "):
            cur = {"h": line[3:], "html": []}
            if cur["h"] != "この記事の要点":
                sections.append(cur)
        elif line.startswith("制度の確認日"):
            foot = line
        elif IMAGE.match(line):
            alt, name = IMAGE.match(line).groups()
            if cur is None:
                hero_alt = alt                      # the picture of the top of the article
            else:
                cur["html"].append(f'<figure class="schedule-figure"><img src="assets/{name}" alt="{escape(alt, quote=True)}" '
                                   'width="1240" height="948" loading="lazy"></figure>')
        elif cur is None:
            lead.append(line)
        else:
            cur["html"].append(f"<p>{_inline(line)}</p>")
    flush()
    return {"title": title, "lead": "".join(lead), "hero_alt": hero_alt, "points": points, "sections": sections, "foot": foot}


def build():
    d = parse()
    toc = "".join(f'<li><a href="#part-{i}">{escape(s["h"])}</a></li>' for i, s in enumerate(d["sections"], 1))
    body = "".join(f'<section class="guide-section consult-section" id="part-{i}"><h2>{escape(s["h"])}</h2>{"".join(s["html"])}</section>'
                   for i, s in enumerate(d["sections"], 1))
    return {
        "slug": SLUG, "image": "hero-year-end-expenses-card", "theme": "仕事・事業", "household": "個人事業主", "tag": "個人事業主の年末の備品",
        "title": d["title"], "lead": d["lead"], "checked": CHECKED, "alt": d["hero_alt"], "hero": "hero-year-end-expenses",
        "hero_alt": d["hero_alt"], "amount": "年300万円まで（青色申告者の特例の上限）",
        "condition": "2026年4月1日以後に取得した10万円以上40万円未満の備品で、要件を満たす場合",
        "points": tuple(d["points"]), "sections": (), "consult": True, "kind": "計算・比較型", "toc_html": toc,
        "body_html": body + f'<p class="consult-footnote">{escape(d["foot"])}</p>',
        "related": (("tools.html#savings", "買い替え資金の毎月の準備額を計算する"), ("basics-household.html", "年に数回の支出を家計に入れる"),
                    ("basics-savings.html", "手元に残すお金を口座で分ける")),
    }
