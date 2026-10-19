"""お正月の特集 (/shogatsu/ とその記事): a landing page and articles about greeting visits and gifts at the New Year, written from the department stores' own guidance and the Cabinet Office's list of holidays.

Everything is in content/shogatsu.json: `sources` (the pages that were opened and read, with the day they were checked), `hub` (the landing page) and `articles`.  The rules the build enforces
(`problems`) are the owner's rules for this kind of page:

  - a number, a date or an amount appears only in a section (or an answer) that names the sources it rests on: what cannot be checked is not written;
  - no sentence says that the site tried the thing itself (it did not) and none promises ("必ず", "絶対") or claims "最安";
  - every picture of a page exists in its three sizes (the page, a 480-px copy for phones, a 1200x630 share card) and every source is a page of a department store or the Cabinet Office.

The weekday of every date of the calendar table is made by the program from the year of the file (a hand-typed weekday is the kind of mistake that goes unseen), and a link to a page that this build does not have is
left out.  Run `python -m sites.yorokobu.seasonal_overlap`-style checks of the wording against the sources before a new article is committed (see docs/YOROKOBU_SHOGATSU.md).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from sokuhou.sitekit import crumbs, esc
from sites.yorokobu import seasonal

HERE = Path(__file__).resolve().parent
DATA = HERE / "content" / "shogatsu.json"
IMG = HERE / "assets" / "shogatsu"
PATH = "/shogatsu/"
ALLOWED_HOSTS = seasonal.SOURCE_HOSTS + ("www8.cao.go.jp", "trends.google.com", "www.nta.go.jp")      # the Cabinet Office (holidays), Google Trends (the site's own measurement of searches, read in a browser) and the National Tax Agency (gift tax)
WEEKDAY = "月火水木金土日"
DIGIT = re.compile(r"[0-9０-９]")
YEAR = re.compile(r"20\d\d年")
DAY_CELL = re.compile(r"^(\d{1,2})月(\d{1,2})日$")
RISKY = ("必ず", "絶対", "間違いなく", "最強", "最安", "一番おすすめ")
TRIED = ("試しました", "試してみ", "実際に使", "使ってみ", "食べてみ", "買ってみ", "渡してみ", "行ってみ", "筆者", "私は", "わたしは")


def _b():
    from sites.yorokobu import build
    return build


def load(path: Path | None = None) -> dict:
    return json.loads((path or DATA).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the rules

def _section_texts(s: dict) -> list[str]:
    out = [*s.get("p", []), *s.get("list", []), *s.get("check", [])]
    if s.get("note"):
        out.append(s["note"])
    t = s.get("table")
    if t:
        out += list(t["head"]) + [str(c) for r in t["rows"] for c in r]
    out += [k.get("note", "") for k in s.get("kinds", [])]
    return [str(x) for x in out]


def _check_text(where: str, texts: list[str], src: list[str], srcs: dict, out: list[str], digits_need_source: bool = True) -> None:
    joined = "".join(texts)
    if digits_need_source and not src and DIGIT.search(YEAR.sub("", joined)):
        out.append(f"{where}: a number or date without a source")
    for w in RISKY:
        if w in joined:
            out.append(f"{where}: the word {w!r}")
    for w in TRIED:
        if w in joined:
            out.append(f"{where}: says the site tried it itself ({w!r})")
    for k in src:
        if k not in srcs:
            out.append(f"{where}: unknown source {k}")


def _check_image(where: str, img: dict | None, out: list[str], img_dir: Path) -> None:
    if not img or not all(img.get(k) for k in ("file", "alt", "w", "h")):
        out.append(f"{where}: image needs file, alt, w, h")
        return
    for suffix in ("", "-480", "-og"):
        if not (img_dir / f"{img['file']}{suffix}.webp").exists():
            out.append(f"{where}: picture {img['file']}{suffix}.webp is missing")


def problems(data: dict, img_dir: Path = IMG) -> list[str]:
    out: list[str] = []
    for k in ("checked", "year", "sources", "hub", "articles"):
        if not data.get(k):
            out.append(f"missing {k}")
    if out:
        return out
    srcs = data["sources"]
    for k, v in srcs.items():
        host = v["url"].split("/")[2] if v.get("url", "").startswith("https://") else ""
        if host not in ALLOWED_HOSTS:
            out.append(f"source {k}: host {host or v.get('url')!r} is not a page that was read")
        if not v.get("name") or not v.get("short"):
            out.append(f"source {k}: no name")

    def blocks(label: str, pg: dict) -> None:
        for f in ("title", "h1", "lead", "sections"):
            if not pg.get(f):
                out.append(f"{label}: missing {f}")
        _check_image(label, pg.get("image"), out, img_dir)
        _check_text(f"{label}/head", [pg.get("title", ""), pg.get("h1", ""), pg.get("lead", "")], [], srcs, out, digits_need_source=False)
        for s in pg.get("sections", []):
            where = f"{label}/{s.get('h')}"
            if not s.get("h"):
                out.append(f"{where}: no heading")
            if not any(s.get(f) for f in ("p", "table", "list", "check", "kinds")):
                out.append(f"{where}: empty section")
            _check_text(where, _section_texts(s), s.get("src", []), srcs, out)
            t = s.get("table")
            if t:
                for r in t["rows"]:
                    if len(r) != len(t["head"]) or any(not str(c).strip() for c in r):
                        out.append(f"{where}: a table row with the wrong number of cells or an empty cell: {r}")
            if s.get("calendar"):
                if not t:
                    out.append(f"{where}: a calendar section needs a table")
                elif not s.get("src"):
                    out.append(f"{where}: a calendar names its sources")
        for i, f in enumerate(pg.get("faq", [])):
            where = f"{label}/faq{i + 1}"
            if not (f.get("q") and f.get("a")):
                out.append(f"{where}: needs q and a")
            _check_text(where, [f.get("q", ""), f.get("a", "")], f.get("src", []), srcs, out)

    blocks("hub", data["hub"])
    seen: set[str] = set()
    for a in data["articles"]:
        slug = a.get("slug", "")
        if not re.fullmatch(r"[a-z0-9-]+", slug) or slug in seen:
            out.append(f"article {slug!r}: slug must be unique lowercase letters, digits and hyphens")
        seen.add(slug)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.get("date", "")):
            out.append(f"article {slug}: date")
        if not a.get("query"):
            out.append(f"article {slug}: query (the search words of the buttons)")
        blocks(f"article {slug}", a)
    return out


# ---------------------------------------------------------------- pages

def _weekdays(t: dict, year: int) -> dict:
    """The table of a calendar section with the weekday of each plain date ("1月2日" -> "1月2日(土)") worked out for `year`."""
    rows = []
    for r in t["rows"]:
        m = DAY_CELL.match(str(r[0]))
        cell = f"{r[0]}({WEEKDAY[date(year, int(m.group(1)), int(m.group(2))).weekday()]})" if m else r[0]
        rows.append([cell, *r[1:]])
    return {**t, "rows": rows}


def _count(n: int) -> str:
    """A small number in the words of a sentence: 一つ ... 九つ, 十."""
    return {1: "一つ", 2: "二つ", 3: "三つ", 4: "四つ", 5: "五つ", 6: "六つ", 7: "七つ", 8: "八つ", 9: "九つ", 10: "十"}.get(n, str(n))


def _fig(img: dict, eager: bool = False) -> str:
    B = _b()
    f = img["file"]
    load = 'fetchpriority="high"' if eager else B.LAZY
    return (f'<figure class="shg-fig"><img src="/assets/shogatsu/{f}.webp" srcset="/assets/shogatsu/{f}-480.webp 480w, /assets/shogatsu/{f}.webp 1200w" '
            f'sizes="(max-width: 760px) 100vw, 720px" alt="{esc(img["alt"])}" width="{img["w"]}" height="{img["h"]}" {load}></figure>')


def _kinds(s: dict, known: set[str] | None) -> str:
    """A section that sends the reader to the comparison tables (/compare/<kind>/): only the kinds whose page exists; nothing at all when none does."""
    labels = {g["slug"]: g["label"] for g in json.loads((HERE / "content" / "compare.json").read_text(encoding="utf-8"))["groups"]}
    items = "".join(f'<li><a href="/compare/{esc(k["slug"])}/">{esc(labels[k["slug"]])}を比べる</a> {esc(k["note"])}</li>'
                    for k in s["kinds"] if known is None or f"compare/{k['slug']}/index.html" in known)
    if not items:
        return ""
    lead = "".join(f"<p>{esc(p)}</p>" for p in s.get("p", []))
    return f'<section class="g-sec"><h2><span class="scribble">{esc(s["h"])}</span></h2>{lead}<ul class="seas-list">{items}</ul></section>'


def _sections(pg: dict, data: dict, known: set[str] | None = None) -> str:
    out = []
    for s in pg["sections"]:
        if s.get("kinds"):
            out.append(_kinds(s, known))
            continue
        if s.get("calendar"):
            s = {**s, "table": _weekdays(s["table"], data["year"])}
        out.append(seasonal._section(s, data["sources"]))
    return "".join(out)


def _faq(pg: dict) -> tuple[str, str]:
    faqs = pg.get("faq", [])
    if not faqs:
        return "", ""
    html = '<section class="g-sec"><h2><span class="scribble">よくある質問</span></h2>' + "".join(
        f'<details class="faq"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>' for f in faqs) + "</section>"
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs]}, ensure_ascii=False)
    return html, f'<script type="application/ld+json">{ld}</script>'


def _sources(pg: dict, data: dict) -> str:
    used: list[str] = []
    for s in pg["sections"] + pg.get("faq", []):
        for k in s.get("src", []):
            if k not in used:
                used.append(k)
    return seasonal.sources_block(seasonal.source_items(used, data["sources"]), data["checked"], "記事", own_basis=pg.get("basis") == "own")


def _buttons(cfg: dict, query: str) -> str:
    B = _b()
    out = f'<span class="btn"><a href="{esc(B.search_link(cfg, query))}" target="_blank" rel="nofollow sponsored noopener">楽天市場で{esc(query)}を探す</a></span>'
    if cfg.get("amazon_tracking_id"):
        out += f'<span class="btn"><a href="{esc(B.amazon_url(cfg, query + " ギフト"))}" target="_blank" rel="nofollow sponsored noopener">Amazonで{esc(query)}を探す</a></span>'
    return out + B.yahoo_btn(cfg, query + " ギフト", f"Yahoo!ショッピングで{query}を探す")


def _related(items: list, own: set[str], known: set[str] | None) -> str:
    return "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for u, t in items if known is None or u in own or u.strip("/") + "/index.html" in known)


def _cards(data: dict, skip: str | None = None) -> str:
    cards = ""
    for a in data["articles"]:
        if a["slug"] == skip:
            continue
        f = a["image"]["file"]
        cards += (f'<li><a class="shg-card" href="{PATH}{a["slug"]}/"><img src="/assets/shogatsu/{f}-480.webp" alt="" width="480" height="320" {_b().LAZY}>'
                  f'<span><b>{esc(a["title"])}</b><small>{esc(a["lead"][:54])}…</small></span></a></li>')
    return f'<ul class="shg-cards">{cards}</ul>'


def _ld(cfg: dict, a: dict, path: str, data: dict) -> str:
    base = cfg["site_url"].rstrip("/")
    return json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": a["title"], "datePublished": a.get("date", data["checked"]),
                       "dateModified": data["checked"], "inLanguage": "ja", "image": f'{base}/assets/shogatsu/{a["image"]["file"]}-og.webp',
                       "mainEntityOfPage": base + path, "author": {"@type": "Organization", "name": cfg["site_name"]},
                       "publisher": {"@type": "Organization", "name": cfg["site_name"]}}, ensure_ascii=False)


def _meta(data: dict, a: dict | None = None) -> str:
    if not a:
        return ""
    py, pm, pd = a["date"].split("-")
    return f'<p class="shg-meta">{int(py)}年{int(pm)}月{int(pd)}日 公開</p>'


def article_page(d: dict, cfg: dict, preview: bool, a: dict, data: dict, known: set[str] | None) -> str:
    B = _b()
    path = f"{PATH}{a['slug']}/"
    own = {PATH} | {f"{PATH}{x['slug']}/" for x in data["articles"]}
    faq_html, faq_ld = _faq(a)
    related = _related(a.get("related", []), own, known)
    body = f"""{B.head_band("pink", "", esc(a["h1"]), a["lead"], single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("お正月の特集", PATH), (a["h1"], None)])}</div>
{B.pr_with_amazon(cfg)}
{_meta(data, a)}
{_fig(a["image"], eager=True)}
<article class="guide seas shg">{_sections(a, data, known)}{faq_html}{_sources(a, data)}</article>
{B.share_bar(cfg, path, a["title"], "この記事をだれかに送る")}
<section class="related seas-more" style="margin-top:44px"><h2><span class="scribble">お正月特集のほかの記事</span></h2>{_cards(data, a["slug"])}
<p style="margin-top:14px"><a class="btn btn-sub" href="{PATH}">お正月の特集のトップへ</a></p></section>
{f'<section class="related seas-more" style="margin-top:34px"><h2><span class="scribble">あわせて読む</span></h2><ul class="plain">{related}</ul></section>' if related else ""}
<section class="seas-more" style="margin-top:30px"><p class="item-btns">{_buttons(cfg, a["query"])}</p></section>
<script type="application/ld+json">{_ld(cfg, a, path, data)}</script>{faq_ld}"""
    return B.page(cfg, preview, path=path, title=f"{a['title']} | {cfg['site_name']}", description=a["lead"][:110], body=body,
                  og_image=f'/assets/shogatsu/{a["image"]["file"]}-og.webp', amazon_links=bool(cfg.get("amazon_tracking_id")))


def hub_page(d: dict, cfg: dict, preview: bool, data: dict, known: set[str] | None) -> str:
    B = _b()
    h = data["hub"]
    own = {PATH} | {f"{PATH}{x['slug']}/" for x in data["articles"]}
    finds = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a>{esc(" " + x) if x else ""}</li>' for u, t, x in
                    ((r[0], r[1], r[2] if len(r) > 2 else "") for r in h.get("finds", [])) if known is None or u in own or u.strip("/") + "/index.html" in known)
    faq_html, faq_ld = _faq(h)
    body = f"""{B.head_band("pink", "", esc(h["h1"]), h["lead"], single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("お正月の特集", None)])}</div>
{B.pr_with_amazon(cfg)}
{_meta(data)}
{_fig(h["image"], eager=True)}
<section class="block shg-pick"><div class="sec-head"><h2>場面から読む</h2><p class="sec-lead">お正月の訪問と贈り物について、場面ごとに{_count(len(data["articles"]))}の記事にまとめています。</p></div>{_cards(data)}</section>
<article class="guide seas shg">{_sections(h, data)}{faq_html}{_sources(h, data)}</article>
{f'<section class="related seas-more" style="margin-top:34px"><h2><span class="scribble">贈るものを探す</span></h2><ul class="plain">{finds}</ul></section>' if finds else ""}
<section class="seas-more" style="margin-top:30px"><p class="item-btns">{_buttons(cfg, h["query"])}</p></section>
{B.share_bar(cfg, PATH, h["title"], "この特集をだれかに送る")}
<script type="application/ld+json">{_ld(cfg, {**h, "date": data["checked"]}, PATH, data)}</script>{faq_ld}"""
    return B.page(cfg, preview, path=PATH, title=f"{h['title']} | {cfg['site_name']}", description=h["lead"][:110], body=body,
                  og_image=f'/assets/shogatsu/{h["image"]["file"]}-og.webp', amazon_links=bool(cfg.get("amazon_tracking_id")))


def build_pages(d: dict, cfg: dict, preview: bool, known: dict | None = None) -> dict[str, str]:
    data = load()
    bad = problems(data)
    if bad:
        raise ValueError("shogatsu content: " + "; ".join(bad))
    keys = set(known) if known is not None else None
    pages = {"shogatsu/index.html": hub_page(d, cfg, preview, data, keys)}
    for a in data["articles"]:
        pages[f"shogatsu/{a['slug']}/index.html"] = article_page(d, cfg, preview, a, data, keys)
    return pages


# ---------------------------------------------------------------- where the rest of the site meets it

def rows() -> list[tuple[str, str, str, str]]:
    """(date, path, title, lead) of the landing page and the articles, newest first (the 新着 strip and the feed)."""
    data = load()
    out = [(a["date"], f"{PATH}{a['slug']}/", a["title"], a["lead"]) for a in data["articles"]]
    out.append((data["hub"].get("date") or data["checked"], PATH, data["hub"]["title"], data["hub"]["lead"]))
    return sorted(out, reverse=True)


def hook(occasion: str, known: set[str] | None = None) -> str:
    """A short block on an occasion's own pages that leads to the New Year feature (empty for the other occasions)."""
    data = load()
    h = data.get("hooks", {}).get(occasion)
    if not h:
        return ""
    links = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for u, t in h["links"])
    return f'<section class="seas-hook" style="margin-top:44px"><h2><span class="scribble">{esc(h["title"])}</span></h2><p>{esc(h["text"])}</p><ul class="plain">{links}</ul></section>'


def hub_row() -> tuple[str, str, str, str]:
    """The landing page as a row of the 新着 strip: (date, path, title, kind)."""
    data = load()
    return (data["hub"].get("date") or data["checked"], PATH, data["hub"]["title"], "特集")


def home_band(today: date) -> str:
    """A block on the home page from the start of October to the middle of January (the season of the New Year feature); empty the rest of the year."""
    if not (today.month >= 10 or (today.month == 1 and today.day <= 15)):
        return ""
    data = load()
    h = data["hub"]
    f = h["image"]["file"]
    return (f'<section class="block shg-home"><div class="sec-head"><span class="eyebrow">Feature</span><h2>お正月の特集</h2></div>'
            f'<a class="shg-card shg-wide" href="{PATH}"><img src="/assets/shogatsu/{f}-480.webp" alt="" width="480" height="320" {_b().LAZY}>'
            f'<span><b>{esc(h["h1"])}</b><small>{esc(h["lead"][:84])}…</small></span></a></section>')
