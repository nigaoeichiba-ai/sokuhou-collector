"""Confirmed articles of the desk (Muse), poured into the site as they are: sites/shiken/articles/<slug>.md  ->  /<slug>/ (a 特集 page).

The text is never changed here: a heading, a paragraph, a list, a table, a picture and a link are only turned into HTML (the test compares the page text with the file).
The note at the top of the file (<!-- ... -->, for Claude Code) is not part of the page.  The pictures: sites/shiken/assets/articles/<slug>-*.webp (converted from the desk's PNG).
The footer after the last '---' is the note of the article (who made which number, the date); it is shown as a note under the article.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from .pages_v2 import esc, page, sec
from . import ui

ARTICLES_DIR = Path(__file__).resolve().parents[1] / "articles"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "articles"

# slug -> what only the page needs besides the text (meta, the keyword, the pictures' file names, the links back).  Nothing of this is article text.
META = {
    "takken-junbi": {
        "kw": "宅建は来年度に向けて",
        "title": "宅建は来年度に向けて、11月の今から始める準備｜申込者と合格率の推移・段取りの表",
        "description": "数字で見た宅建の今の姿と、来年度に向けた準備の段取りをまとめた特集です。申込者数と合格率の推移、出題の全体像、教材の比べ方、申込から逆算した段取りの表があります。",
        "secondary": ("宅建 勉強 いつから", "宅建 申込者 合格率 推移"),
        "images": {"chart-takken-trend.png": "takken-junbi-trend.webp", "chart-takken-radar.png": "takken-junbi-radar.webp"},
        "related": [{"path": "/takken/", "text": "宅建の試験日・申込期間・合格発表"}, {"path": "/goukaku-ritsu/", "text": "合格率の見方"},
                    {"path": "/postmark/", "text": "消印有効と必着の違い"}, {"path": "/flow/", "text": "申込から合格発表までの流れ"}],
    },
}


def _inline(text: str) -> str:
    """Escape, then [text](/path) -> a link.  Nothing else is interpreted (no emphasis: the desk's text has none)."""
    out, pos = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+)\)", text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        out.append(f'<a href="{esc(m.group(2))}">{html.escape(m.group(1), quote=False)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(md: str) -> dict:
    """The file -> {'title', 'blocks': [(kind, data)], 'footer'}.  kinds: h2, h3, p, ul, table, img."""
    md = re.sub(r"\A\s*<!--.*?-->\s*", "", md, flags=re.S)
    lines = md.split("\n")
    title, blocks, footer = None, [], []
    i, para = 0, []
    in_footer = False

    def flush():
        nonlocal para
        if para:
            (footer if in_footer else blocks).append(("p", " ".join(para)) if not in_footer else " ".join(para))
            para = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush(); i += 1; continue
        if ln.strip() == "---":
            flush(); in_footer = True; i += 1; continue
        if in_footer:
            para.append(ln.strip()); i += 1; continue
        if ln.startswith("# "):
            flush(); title = ln[2:].strip(); i += 1; continue
        if ln.startswith("### "):
            flush(); blocks.append(("h3", ln[4:].strip())); i += 1; continue
        if ln.startswith("## "):
            flush(); blocks.append(("h2", ln[3:].strip())); i += 1; continue
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", ln.strip())
        if m:
            flush(); blocks.append(("img", (m.group(1), m.group(2)))); i += 1; continue
        if ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i])); i += 1
            head, body = rows[0], [r for r in rows[2:]]      # rows[1] is the |---| line
            blocks.append(("table", (head, body))); continue
        if ln.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip()); i += 1
            blocks.append(("ul", items)); continue
        para.append(ln.strip()); i += 1
    flush()
    return {"title": title, "blocks": blocks, "footer": footer}


def render(parsed: dict, images: dict) -> tuple[str, str]:
    """-> (the lead paragraph as HTML text without tags, the body HTML).  The first paragraph is the lead of the page (shown once, as the answer)."""
    from PIL import Image
    blocks = list(parsed["blocks"])
    lead = ""
    if blocks and blocks[0][0] == "p":
        lead = blocks.pop(0)[1]
    out = []
    n = 0
    for kind, data in blocks:
        if kind == "h2":
            n += 1
            out.append(f'<h2 id="s{n}">{_inline(data)}</h2>')
        elif kind == "h3":
            out.append(f"<h3>{_inline(data)}</h3>")
        elif kind == "p":
            out.append(f"<p>{_inline(data)}</p>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in data) + "</ul>")
        elif kind == "table":
            head, body = data
            out.append(ui.table([html.unescape(_inline(c)) if False else c for c in head], [[("<span>" + _inline(c) + "</span>") if "](" in c else c for c in r] for r in body]))
        elif kind == "img":
            alt, src = data
            f = images.get(src)
            if not f:
                raise ValueError(f"picture {src!r} is not in META images")
            w, h = Image.open(ASSETS_DIR / f).size
            out.append(f'<figure class="article-fig"><img src="/assets/articles/{esc(f)}" alt="{esc(alt)}" width="{w}" height="{h}" loading="lazy"></figure>')
    return lead, "".join(out)


def build(slug: str) -> dict:
    meta = META[slug]
    parsed = parse((ARTICLES_DIR / f"{slug}.md").read_text(encoding="utf-8"))
    lead, body = render(parsed, meta["images"])
    foot = "".join(f'<p class="note">{_inline(p)}</p>' for p in parsed["footer"])
    nav = ('<nav class="toc" aria-label="目次"><b>目次</b><ol>' + "".join(f'<li><a href="#s{i}">{_inline(t)}</a></li>' for i, t in enumerate([d for k, d in parsed["blocks"] if k == "h2"], 1)) + "</ol></nav>")
    return page(f"/{slug}/", "article", "/yomimono/", meta["kw"], meta["title"], parsed["title"], meta["description"], lead,
                [sec(None, nav + body + foot)], meta["related"], secondary=meta["secondary"], intent=4)


def pages() -> list[dict]:
    return [build(p.stem) for p in sorted(ARTICLES_DIR.glob("*.md")) if p.stem in META]
