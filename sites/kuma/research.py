"""/research/ -- research notes: one analysis of the site's own records a day, in the form of a page nobody else has.

A note is one JSON file in sites/kuma/research/ (the numbers in it are written by the script named in "script", never typed by hand):

  slug, date (the day it was written), data_as_of (the newest record it counts), title, h1, description, lead,
  findings [str]            the two to four things the analysis found
  sections [{h2, paragraphs [str], table {head, rows}, chart {kind "bars"|"lines", ...}}]
  method [str], caveats [str]   how it was counted, and what it does not show
  credits [str]             the credit lines of the data sources, exactly as the stored data files give them
  script                    the path of the script that computed the numbers (kept in the repository so anybody can recompute them)
  related [{label, href}]   pages of this site to read next

`[[label|/path/]]` in a paragraph is a link to a page of this site.  Nothing here states a cause, and nothing says a place is safe or dangerous.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from sites.kuma import charts
from sites.kuma.fmt import jp_date, md, table
from sokuhou.sitekit import BuildError, crumbs, esc

DIR = Path(__file__).resolve().parent / "research"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LINK = re.compile(r"\[\[([^\]|]+)\|(/[^\]\s]*)\]\]")
BANNED = re.compile(r"必ず|絶対|100%|安全です|危険です|日本一|No\.1|ナンバーワン|最も危険|最も安全")
MIN_LEAD, MAX_DESC = 40, 160


def load(directory: Path | None = None) -> list[dict]:
    """Every note, newest first (the day it was written, then the name)."""
    docs = []
    for p in sorted((directory or DIR).glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["_file"] = p.name
        docs.append(doc)
    return sorted(docs, key=lambda x: (x["date"], x["slug"]), reverse=True)


def problems(doc: dict, repo_root: Path | None = None) -> list[str]:
    """Everything wrong with one note (empty when it can be published)."""
    out: list[str] = []
    for k in ("slug", "date", "data_as_of", "title", "h1", "description", "lead", "findings", "sections", "method", "caveats", "credits", "script"):
        if not doc.get(k):
            out.append(f"missing {k}")
    if out:
        return out
    if not SLUG.fullmatch(doc["slug"]):
        out.append("slug must be lower-case ascii words joined by '-'")
    for k in ("date", "data_as_of"):
        try:
            date.fromisoformat(doc[k])
        except ValueError:
            out.append(f"{k} is not an ISO date")
    if len(doc["description"]) > MAX_DESC:
        out.append("description is longer than 160 characters")
    if len(doc["lead"]) < MIN_LEAD:
        out.append("lead is too short")
    if not 2 <= len(doc["findings"]) <= 4:
        out.append("findings must be two to four sentences")
    if len(doc["sections"]) < 2:
        out.append("two sections at least")
    for i, s in enumerate(doc["sections"]):
        if not s.get("h2") or not (s.get("paragraphs") or s.get("table") or s.get("chart")):
            out.append(f"section {i}: needs h2 and a paragraph, table or chart")
        t = s.get("table")
        if t and (not t.get("head") or not t.get("rows") or any(len(r) != len(t["head"]) for r in t["rows"])):
            out.append(f"section {i}: table rows do not match the head")
        c = s.get("chart")
        if c:
            if c.get("kind") == "bars":
                if not c.get("labels") or len(c["labels"]) != len(c.get("values", [])) or not c.get("title") or not c.get("desc"):
                    out.append(f"section {i}: bar chart needs labels, values of the same length, title and desc")
            elif c.get("kind") == "lines":
                if not c.get("x_labels") or not c.get("series") or any(len(x["values"]) != len(c["x_labels"]) for x in c["series"]) or not c.get("title") or not c.get("desc"):
                    out.append(f"section {i}: line chart needs x_labels, series of the same length, title and desc")
            else:
                out.append(f"section {i}: unknown chart kind")
    texts = [doc["title"], doc["h1"], doc["description"], doc["lead"]] + doc["findings"] + doc["method"] + doc["caveats"]
    for s in doc["sections"]:
        texts += s.get("paragraphs", [])
    for t in texts:
        if BANNED.search(t):
            out.append(f"claim not allowed: {BANNED.search(t).group(0)}")
        for _, href in LINK.findall(t):
            if not href.endswith("/") and "?" not in href:
                out.append(f"internal link must end with '/': {href}")
    if not any(c.strip().startswith("出典") or "CC BY" in c or "オープンデータ" in c for c in doc["credits"]):
        out.append("credits must name the data sources")
    if repo_root is not None and not (repo_root / doc["script"]).is_file():
        out.append(f"script not found: {doc['script']}")
    return out


def check(docs: list[dict], repo_root: Path | None = None) -> None:
    seen: set[str] = set()
    for doc in docs:
        bad = problems(doc, repo_root)
        if doc.get("slug") in seen:
            bad.append("duplicate slug")
        seen.add(doc.get("slug", ""))
        if bad:
            raise BuildError(f"research note {doc.get('_file', doc.get('slug'))}: " + "; ".join(bad))


def inline(text: str) -> str:
    """Escaped text with [[label|/path/]] turned into links to this site."""
    out, pos = "", 0
    for m in LINK.finditer(text):
        out += esc(text[pos:m.start()]) + f'<a href="{esc(m.group(2))}">{esc(m.group(1))}</a>'
        pos = m.end()
    return out + esc(text[pos:])


def chart_html(c: dict, uid: str) -> str:
    if c["kind"] == "bars":
        return charts.bars(c["labels"], c["values"], title=c["title"], desc=c["desc"], uid=uid)
    return charts.lines([{"label": s["label"], "values": s["values"], "cls": s.get("cls", f"c{(i % 4) + 1}")} for i, s in enumerate(c["series"])], c["x_labels"],
                        title=c["title"], desc=c["desc"], uid=uid)


def research_page(page, doc: dict, docs: list[dict]) -> str:
    sections = ""
    for i, s in enumerate(doc["sections"]):
        sections += f"<h2>{esc(s['h2'])}</h2>\n"
        sections += "".join(f"<p>{inline(p)}</p>\n" for p in s.get("paragraphs", []))
        if s.get("chart"):
            sections += chart_html(s["chart"], f"r{i}") + "\n"
        if s.get("table"):
            t = s["table"]
            sections += table([esc(h) for h in t["head"]], [[esc(str(c)) for c in r] for r in t["rows"]]) + "\n"
            if t.get("note"):
                sections += f'<p class="notice">{inline(t["note"])}</p>\n'
    others = [x for x in docs if x["slug"] != doc["slug"]][:5]
    more = ("<h2>ほかの研究ノート</h2>\n<ul class=\"link-list\">" + "".join(f'<li><a href="/research/{x["slug"]}/">{esc(x["h1"])}</a><b>{md(x["date"])}</b></li>' for x in others) + "</ul>\n") if others else ""
    related = ("<ul class=\"link-list\">" + "".join(f'<li><a href="{esc(r["href"])}">{esc(r["label"])}</a></li>' for r in doc.get("related", [])) + "</ul>\n") if doc.get("related") else ""
    body = f"""{crumbs([("全国", "/"), ("研究ノート", "/research/"), (doc["h1"], None)])}
<h1>{esc(doc["h1"])}</h1>
<p class="lead">{inline(doc["lead"])}</p>
<p class="notice">{jp_date(doc["date"])}の研究ノートです。使った記録は、{jp_date(doc["data_as_of"])}までのものです。</p>
<h2>わかったこと</h2>
<ul>
{"".join(f"<li>{inline(f)}</li>" + chr(10) for f in doc["findings"])}</ul>
{sections}<h2>数え方</h2>
<ul>
{"".join(f"<li>{inline(m)}</li>" + chr(10) for m in doc["method"])}</ul>
<h2>この分析で言えないこと</h2>
<ul>
{"".join(f"<li>{inline(c)}</li>" + chr(10) for c in doc["caveats"])}</ul>
{('<h2>あわせて読む</h2>' + chr(10) + related) if related else ''}{more}<p class="notice">{" ".join(esc(c) + "。" if not c.endswith("。") else esc(c) for c in doc["credits"])} 計算に使ったスクリプト: <code>{esc(doc["script"])}</code>(公開リポジトリ)。</p>"""
    return page(path=f"/research/{doc['slug']}/", title=doc["title"], description=doc["description"], body=body)


def hub_page(page, docs: list[dict], has_live: bool = True, has_digest: bool = True) -> str:
    items = "".join(f'<li><a href="/research/{x["slug"]}/">{esc(x["h1"])}</a><b>{md(x["date"])}</b><br><small>{esc(x["description"])}</small></li>' for x in docs)
    tail = ("最新の記録は" + ('<a href="/live/">最新の目撃情報</a>' if has_live else "各都道府県のページ") + "、"
            + ('週ごとの動きは<a href="/digest/">週ごとのまとめ</a>へ。' if has_digest else "ほかのデータは各ページへ。"))
    body = f"""{crumbs([("全国", "/"), ("研究ノート", None)])}
<h1>熊(クマ)出没の研究ノート</h1>
<p class="lead">このサイトが集めた自治体の目撃記録を、数えて分かったことを、1日1本ずつ書いています。時間帯、曜日、季節の進み、地区ごとのくり返しなど、公式の一覧表だけでは見えない見方です。いま{len(docs)}本あります。</p>
<ul class="link-list">{items}</ul>
<p class="notice">どのノートも、数え方と、言えないことを、書いています。件数の大小は、自治体ごとに数える対象が違うため、そのまま比べられません。{tail}</p>"""
    return page(path="/research/", title=f"熊(クマ)出没の研究ノート({len(docs)}本・自治体の記録を数えて分かったこと)",
                description="自治体が公表している熊(クマ)の目撃記録を数えて分かったことを、1日1本ずつ書いています。時間帯・曜日・季節の進みなど。数え方と限界つき。", body=body)


def home_block(docs: list[dict], limit: int = 3) -> str:
    if not docs:
        return ""
    items = "".join(f'<li><a href="/research/{x["slug"]}/">{esc(x["h1"])}</a><b>{md(x["date"])}</b></li>' for x in docs[:limit])
    return f'<h2>研究ノート(記録を数えて分かったこと)</h2>\n<ul class="link-list">{items}</ul>\n<p><a href="/research/">研究ノートの一覧</a></p>\n'


def newest_date(docs: list[dict]) -> str | None:
    return max((x["date"] for x in docs), default=None)
