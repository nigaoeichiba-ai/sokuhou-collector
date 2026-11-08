"""The scaffold of a new site (stage 0 of docs/new_sites/BATCH1_PROPOSAL.md 7-4): one command makes the folder, one line in data/sites.json makes it publishable.

    python -m sokuhou.newsite init <name> --domain example.com --site-name "..." [--glyph 財] [--register]
    python -m sokuhou.newsite build sites/<name> [--release] [--out release] [--strict-seo] [--allow-example]
    python -m sokuhou.newsite seo-report sites/<name>
    python -m sokuhou.newsite seo-csv sites/<name> [--out docs/new_sites/seo/<name>.csv]

`init` writes sites/<name>/ : config.json (site_url, site_name, operator ...), site.json (navigation, sources, method, corrections), content/*.json (one file per page,
with a few EXAMPLE pages that a release refuses until they are replaced), assets/ (style.css and icons) and a 6-line build.py that calls build() here.
`--register` also appends the site's line to data/sites.json.  Read the warning it prints: deploy.yml's Gate step must know the site before the register is pushed.

A page (content/*.json) says what the page is, not how it looks:
    path, kind (hub | list | analysis | article | item | archive), parent (the page above it: breadcrumbs and the list of links on that page),
    primary_kw, secondary_kw[], intent (1-5), title, description, h1, answer (the 40-80 character answer under the h1),
    updated (the day the numbers or text really changed: it becomes <lastmod>), data_basis (shown: "2026年4月1日現在"),
    sections [{h2, paras[], table{caption, cols[], rows[[cell | {text, href}]], num_cols[]}, chart{kind bar|line, title, desc, labels[], values[], unit}, tilemap{...}, html}],
    related [{path, text}], sources [ids of site.json "sources"], dataset {csv, table_section, license}, noindex.

What the build adds (5-0 of the proposal): breadcrumbs, JSON-LD (WebSite, BreadcrumbList, Article, Dataset), canonical, a sitemap whose lastmod is the page's own `updated`,
thin pages made noindex,follow and left out of the sitemap, and a FAILED build for: the same main search term on two pages, a missing term in title / h1, two pages of one
type that overlap by more than 0.6, an orphan page, a page more than 3 clicks from the home page, a picture without alt, more than 3 tables on a page.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
from pathlib import Path

from sokuhou import measure, prefectures, seokit, sitekit, tilegrid
from sokuhou.sitekit import BuildError, esc

ROOT = Path(__file__).resolve().parents[1]
ASSETS_SRC = Path(__file__).with_name("newsite_assets")
KINDS = seokit.HUB_TYPES + seokit.ITEM_TYPES + seokit.ALWAYS_NOINDEX
SOURCE_STYLES = ("block", "credit", "none")
NAME = re.compile(r"[a-z][a-z0-9]*")
MAX_TABLES = 3
DEFAULT_KINDS = ["数字の誤りのご指摘", "ご意見・ご要望", "その他"]


# ---------------------------------------------------------------- reading a site folder
def site_hooks(site_dir: Path):
    """A site may ship hooks.py: prepare(cfg, spec, pages, site_dir) -> pages (before the pages are rendered: it may add pages and sections) and
    post(pages, content, cfg, spec, site_dir) -> pages (after: it may change the rendered files).  A site without hooks.py is built as before."""
    f = site_dir / "hooks.py"
    if not f.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_site_hooks_{site_dir.name}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_site(site_dir: Path) -> tuple[dict, dict, list[dict]]:
    """(config.json, site.json, the pages of content/*.json in file-name order)."""
    cfg = json.loads((site_dir / "config.json").read_text(encoding="utf-8"))
    spec = json.loads((site_dir / "site.json").read_text(encoding="utf-8"))
    pages = []
    for f in sorted((site_dir / "content").glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        p["_file"] = f.name
        pages.append(p)
    return cfg, spec, pages


def check_spec(spec: dict, pages: list[dict]) -> None:
    """The shape of the content, before anything is rendered: a mistake here is the author's, so it is named by file."""
    errors = []
    paths: dict[str, str] = {}
    for p in pages:
        f = p["_file"]
        path = p.get("path", "")
        if not (path.startswith("/") and path.endswith("/")):
            errors.append(f"{f}: path must start and end with '/', got {path!r}")
        if path in paths:
            errors.append(f"{f}: the path {path} is also the path of {paths[path]}")
        paths[path] = f
        if p.get("kind") not in KINDS:
            errors.append(f"{f}: kind must be one of {KINDS}")
        for k in ("title", "description", "h1"):
            if not p.get(k):
                errors.append(f"{f}: no {k}")
        tables = sum(1 for s in p.get("sections", []) if s.get("table"))
        if tables > MAX_TABLES:
            errors.append(f"{f}: {tables} tables (at most {MAX_TABLES} on a page: split a long table into pages)")
    if "/" not in paths:
        errors.append("no page with path '/' (the home page)")
    sources = spec.get("sources", {})
    style = spec.get("sources_style", "block")
    if style not in SOURCE_STYLES:
        errors.append(f"site.json sources_style must be one of {SOURCE_STYLES}, got {style!r}")
    for p in pages:
        f = p["_file"]
        if p.get("parent") and p["parent"] not in paths:
            errors.append(f"{f}: parent {p['parent']} is not a page")
        if p["path"] != "/" and not p.get("parent"):
            errors.append(f"{f}: no parent (every page except the home page hangs under one: the breadcrumb and the link to it come from that)")
        for r in p.get("related", []):
            if r["path"] not in paths:
                errors.append(f"{f}: related {r['path']} is not a page")
        for sid in p.get("sources", []):
            if sid not in sources:
                errors.append(f"{f}: source {sid!r} is not in site.json sources")
        if style == "block":
            if p.get("kind") != "archive" and p["path"] != "/" and not p.get("sources"):
                errors.append(f"{f}: no sources (every page ends with where its numbers come from)")
        elif has_numbers(p) and not credit_lines(p, spec):
            errors.append(f"{f}: numbers in a table / chart / map but no source declared (a page 'credit', a source with a 'credit', or the site's 'credits'; sources_style is {style!r})")
        ds = p.get("dataset")
        if ds:
            n = ds.get("table_section", 0)
            secs = p.get("sections", [])
            if not (0 <= n < len(secs) and secs[n].get("table")):
                errors.append(f"{f}: dataset.table_section {n} is not a section with a table")
    if errors:
        raise BuildError("the content is not valid:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------- parts of a page
def table_html(t: dict) -> str:
    num = set(t.get("num_cols", []))
    head = "".join(f'<th scope="col"{" class=\"num\"" if i in num else ""}>{esc(c)}</th>' for i, c in enumerate(t["cols"]))
    rows = []
    for r in t["rows"]:
        cells = []
        for i, c in enumerate(r):
            cls = ' class="num"' if i in num else ""
            if isinstance(c, dict):
                inner = f'<a href="{esc(c["href"])}">{esc(c["text"])}</a>' if c.get("href") else esc(c["text"])
            else:
                inner = esc(c)
            cells.append(f"<td{cls}>{inner}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    cap = f"<caption>{esc(t['caption'])}</caption>" if t.get("caption") else ""
    note = f'<p class="notice">{esc(t["note"])}</p>' if t.get("note") else ""
    return f'<div class="tablewrap"><table>{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{note}'


def _num(v) -> str:
    return f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.1f}"


def chart_svg(c: dict, uid: str) -> str:
    """A bar or line chart as text-readable SVG: <title> and <desc> say what it shows, and the page's own text carries the same numbers (5-0 (5))."""
    labels, values, unit = c["labels"], c["values"], c.get("unit", "")
    if len(labels) != len(values) or not values:
        raise BuildError(f"chart {c.get('title')!r}: labels and values must be lists of the same, non-zero length")
    tid, did = f"{uid}-t", f"{uid}-d"
    head = (f'<svg class="chart {c["kind"]}" viewBox="0 0 640 {{h}}" role="img" aria-labelledby="{tid} {did}">'
            f'<title id="{tid}">{esc(c["title"])}</title><desc id="{did}">{esc(c["desc"])}</desc>')
    if c["kind"] == "bar":
        row, left, right = 26, 150, 80
        h = row * len(values) + 12
        mx = max(values) or 1
        body = []
        for i, (lab, v) in enumerate(zip(labels, values)):
            y = 6 + i * row
            w = max(1, (640 - left - right) * v / mx)
            body.append(f'<text x="{left - 8}" y="{y + 15}" text-anchor="end">{esc(lab)}</text><rect class="bar" x="{left}" y="{y + 3}" width="{w:.1f}" height="{row - 8}" rx="3"/>'
                        f'<text x="{left + w + 6:.1f}" y="{y + 15}">{esc(_num(v))}{esc(unit)}</text>')
        return head.replace("{h}", str(h)) + "".join(body) + "</svg>"
    if c["kind"] == "line":
        h, pad_l, pad_r, pad_t, pad_b = 220, 52, 20, 16, 34
        lo, hi = min(values), max(values)
        span = (hi - lo) or 1
        n = len(values)
        pts = [(pad_l + (640 - pad_l - pad_r) * (i / max(1, n - 1)), pad_t + (h - pad_t - pad_b) * (1 - (v - lo) / span)) for i, v in enumerate(values)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        body = [f'<line class="axis" x1="{pad_l}" y1="{h - pad_b}" x2="{640 - pad_r}" y2="{h - pad_b}"/>',
                f'<text x="{pad_l - 6}" y="{pad_t + 10}" text-anchor="end">{esc(_num(hi))}</text><text x="{pad_l - 6}" y="{h - pad_b}" text-anchor="end">{esc(_num(lo))}</text>',
                f'<polyline class="line" points="{poly}"/>']
        for i in sorted({0, n - 1, values.index(hi), values.index(lo)}):
            x, y = pts[i]
            body.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3.5"/>')
        step = max(1, n // 6)
        for i in range(0, n, step):
            body.append(f'<text x="{pts[i][0]:.1f}" y="{h - 12}" text-anchor="middle">{esc(labels[i])}</text>')
        return head.replace("{h}", str(h)) + "".join(body) + "</svg>"
    raise BuildError(f"chart kind must be bar or line, got {c['kind']!r}")


def tile_map(t: dict, existing: set[str]) -> str:
    """The 47-prefecture tile map of tilegrid.py.  t = {title, values: {slug: number}, unit, href_prefix (e.g. "/pref/"; a tile links only to a page that exists)}."""
    values = t["values"]
    vs = sorted(values.values())
    cell, pad = 46, 2
    parts = []
    for slug, col, row in tilegrid.tiles():
        short = next(k for k, v in prefectures.SLUG.items() if v == slug)
        x, y = pad + col * cell, pad + row * cell
        v = values.get(slug)
        label = f'<text x="{x + (cell - 4) / 2}" y="{y + (cell - 4) / 2}">{esc(short[:2])}</text>'
        if v is None:
            parts.append(f'<g><title>{esc(prefectures.full(short))}: 数値なし</title><rect class="tile na" x="{x}" y="{y}" width="{cell - 4}" height="{cell - 4}" rx="7"/>{label}</g>')
            continue
        below = sum(1 for z in vs if z < v)
        cls = "t0" if v == 0 else f"t{1 + min(3, int(4 * below / len(vs)))}"
        tip = f'{prefectures.full(short)} {_num(v)}{t.get("unit", "")}'
        shape = f'<rect class="tile {cls}" x="{x}" y="{y}" width="{cell - 4}" height="{cell - 4}" rx="7"/>{label}'
        href = f'{t["href_prefix"]}{slug}/' if t.get("href_prefix") else ""
        if href and href in existing:
            parts.append(f'<a href="{esc(href)}" aria-label="{esc(tip)}"><title>{esc(tip)}</title>{shape}</a>')
        else:
            parts.append(f"<g><title>{esc(tip)}</title>{shape}</g>")
    w, h = tilegrid.GRID_COLS * cell + pad * 2, tilegrid.GRID_ROWS * cell + pad * 2
    legend = "".join(f'<i style="display:inline-block;width:14px;height:14px;border-radius:3px;margin:0 1px;background:var(--c{i})"></i>' for i in range(1, 5))
    return (f'<div class="tilemap-box"><svg class="tilemap" viewBox="0 0 {w} {h}" role="group" aria-label="{esc(t["title"])}">{"".join(parts)}</svg>'
            f'<div class="tile-legend"><b>{esc(t["title"])}</b> 少ない {legend} 多い</div></div>')


def has_numbers(page: dict) -> bool:
    return any(sec.get("table") or sec.get("chart") or sec.get("tilemap") for sec in page.get("sections", []))


def credit_lines(page: dict, spec: dict) -> list[str]:
    """The credit sentences of a page ('総務省統計局『家計調査』を加工して作成'): its own `credit`, else the `credit` of the sources it names, else the site's `credits`."""
    own = page.get("credit")
    if own:
        return [own] if isinstance(own, str) else list(own)
    named = [spec["sources"][sid]["credit"] for sid in page.get("sources", []) if sid in spec.get("sources", {}) and spec["sources"][sid].get("credit")]
    return named or list(spec.get("credits") or [])


def sources_block(page: dict, spec: dict) -> str:
    """The end of a page.  sources_style "block" (the default, as before): every source with its link, base day and day fetched.  "credit": the one credit line the licence
    needs and the page's day of update, no address, no per-source dates.  "none": nothing."""
    style = spec.get("sources_style", "block")
    if style == "none":
        return ""
    if style == "credit":
        lines = credit_lines(page, spec)
        credit = f'<p class="credit">出典: {esc("、".join(dict.fromkeys(lines)))}</p>\n' if lines else ""
        return f'{credit}<p class="stamp">最終更新日: {esc(page_updated(page, spec))}</p>'
    items = []
    for sid in page.get("sources", []):
        s = spec["sources"][sid]
        link = f'<a href="{esc(s["url"])}" rel="noopener" target="_blank">出典の公開ページ</a>' if s.get("url") else ""
        items.append(f"<li>{esc(s['org'])}「{esc(s['table'])}」({link}{'、' if link else ''}基準日 {esc(s['basis'])}、取得日 {esc(s['fetched'])})</li>")
    basis = f"データの基準日: {esc(page['data_basis'])} / " if page.get("data_basis") else ""
    ul = f'<ul class="sources">{"".join(items)}</ul>' if items else ""
    return f'<h2>出典と更新日</h2>\n{ul}\n<p class="stamp">{basis}最終更新日: {esc(page_updated(page, spec))}</p>'


def page_updated(page: dict, spec: dict) -> str:
    return page.get("updated") or spec["updated"]


def page_body(page: dict, spec: dict, by_path: dict, cfg: dict) -> str:
    existing = set(by_path)
    crumb_items: list[tuple[str, str | None]] = []
    p = page
    while p.get("parent"):
        p = by_path[p["parent"]]
        crumb_items.append((spec.get("home_label", "トップ") if p["path"] == "/" else p.get("crumb") or p["h1"], p["path"]))
    chain = list(reversed(crumb_items))
    crumbs = sitekit.crumbs(chain + [(page.get("crumb") or page["h1"], None)]) if chain else ""
    out = [crumbs, f"<h1>{esc(page['h1'])}</h1>"]
    if page.get("answer"):
        out.append(f'<p class="answer">{esc(page["answer"])}</p>')
    uid = re.sub(r"[^a-z0-9]+", "-", page["path"].strip("/") or "home")
    for n, s in enumerate(page.get("sections", [])):
        if s.get("h2"):
            out.append(f"<h2>{esc(s['h2'])}</h2>")
        out.extend(f"<p>{esc(t)}</p>" for t in s.get("paras", []))
        if s.get("table"):
            out.append(table_html(s["table"]))
        if s.get("chart"):
            out.append(chart_svg(s["chart"], f"{uid}-{n}"))
        if s.get("tilemap"):
            out.append(tile_map(s["tilemap"], existing))
        if s.get("html"):
            out.append(s["html"])
    if page.get("dataset"):
        out.append(f'<p><a class="btn" href="/{esc(page["dataset"]["csv"])}" download>このページの表をCSVでダウンロード</a></p>')
    kids = [c for c in by_path.values() if c.get("parent") == page["path"]]
    if kids and not page.get("hide_children"):          # a page whose children are already shown another way (cards) can say so
        out.append(f"<h2>{esc(page.get('children_h2') or page['h1'] + 'の各ページ')}</h2>\n<ul class=\"links\">"
                   + "".join(f'<li><a href="{esc(c["path"])}">{esc(c["h1"])}</a></li>' for c in kids) + "</ul>")
    if page.get("related"):
        out.append("<h2>関連するページ</h2>\n<ul class=\"links\">"
                   + "".join(f'<li><a href="{esc(r["path"])}">{esc(r["text"])}</a></li>' for r in page["related"]) + "</ul>")
    if page["path"] != "/" and page.get("kind") != "archive":
        out.append(sources_block(page, spec))
    return "\n".join(x for x in out if x)


def ld_script(d: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def page_ld(page: dict, spec: dict, cfg: dict) -> str:
    """Article for analysis / article pages, Dataset for a page that gives its table as CSV.  The author and publisher are the site (never the company: that is on /about/ only)."""
    base = cfg["site_url"].rstrip("/")
    org = {"@type": "Organization", "name": cfg["site_name"], "url": base + "/"}
    out = ""
    if page["kind"] in ("analysis", "article"):
        out += ld_script({"@context": "https://schema.org", "@type": "Article", "headline": page["h1"], "inLanguage": "ja", "mainEntityOfPage": base + page["path"],
                          "datePublished": page.get("published") or page_updated(page, spec), "dateModified": page_updated(page, spec), "author": org, "publisher": org})
    if page.get("dataset"):
        ds = page["dataset"]
        node = {"@context": "https://schema.org", "@type": "Dataset", "name": page["h1"], "description": page["description"], "url": base + page["path"], "inLanguage": "ja",
                "creator": org, "dateModified": page_updated(page, spec),
                "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{base}/{ds['csv']}"}]}
        if ds.get("license"):
            node["license"] = ds["license"]
        srcs = [spec["sources"][s] for s in page.get("sources", []) if spec["sources"][s].get("url")]
        if srcs:
            node["isBasedOn"] = [s["url"] for s in srcs]
        out += ld_script(node)
    return out


def csv_text(t: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(t["cols"])
    for r in t["rows"]:
        w.writerow([c["text"] if isinstance(c, dict) else c for c in r])
    return "\ufeff" + buf.getvalue()


# ---------------------------------------------------------------- the build
def build_pages(site_dir: Path, *, release: bool = False, allow_example: bool = False, strict_seo: bool = False) -> tuple[dict, dict]:
    """Every file of the site as {path: str | bytes}, and the report {thin: {page: [why]}, warnings: [...]}.  Raises BuildError for what must not be published."""
    cfg, spec, content = load_site(site_dir)
    hooks = site_hooks(site_dir)
    if hooks and hasattr(hooks, "prepare"):
        content = hooks.prepare(cfg, spec, content, site_dir)
    missing = sitekit.missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    examples = [p["_file"] for p in content if p.get("example")]
    if release and examples and not allow_example:
        raise BuildError("release build refused: example pages are still there (replace them, then delete them): " + ", ".join(examples))
    preview = bool(missing)
    check_spec(spec, content)
    by_path = {p["path"]: p for p in content}
    site = {"nav": [(n[0], n[1], n[2] if len(n) > 2 else n[1]) for n in spec["nav"]], "glyph": spec.get("glyph", cfg["site_name"][0]),
            "source_html": spec["footer_html"], "assets": site_dir / "assets"}

    errors, warnings = [], []
    measure_tag = (f'<script src="/assets/measure.js?v={hashlib.sha1(measure.MEASURE_JS.encode()).hexdigest()[:8]}" defer></script>\n'
                   if cfg.get("measure") and not preview else "")
    metas, kinds, pages, rel_of = [], {}, {}, {}
    for p in content:
        body = page_body(p, spec, by_path, cfg)
        rel = "index.html" if p["path"] == "/" else p["path"].strip("/") + "/index.html"
        pages[rel] = sitekit.layout(site, cfg, preview, path=p["path"], title=f"{p['title']} | {cfg['site_name']}", description=p["description"], body=body,
                                    head_extra=page_ld(p, spec, cfg) + measure_tag)
        kinds[rel] = p["kind"]
        rel_of[p["path"]] = rel
        metas.append({"path": p["path"], "kind": p["kind"], "primary_kw": p.get("primary_kw"), "secondary_kw": p.get("secondary_kw"), "intent": p.get("intent"),
                      "title": p["title"], "h1": p["h1"], "description": p["description"], "answer": p.get("answer")})
        if p.get("dataset"):
            pages[p["dataset"]["csv"]] = csv_text(p["sections"][p["dataset"].get("table_section", 0)]["table"])

    legal = sitekit.legal_pages(site, cfg, preview, purpose=esc(spec["purpose"]), sources_html=_sources_html(spec), update_text=esc(spec["update_text"]),
                                disclaimer_html=_disclaimer_html(spec), contact_notice="お返事には数日かかることがあります。内容によっては、お返事できないこともあります。")
    pages.update(legal)
    pages.update(sitekit.asset_pages(site["assets"]))
    if measure_tag:      # visits are counted without knowing who came (sokuhou/measure.py); the privacy page says so (sitekit.MEASURE_TEXT)
        pages["assets/measure.js"] = measure.MEASURE_JS
        pages["m/t.gif"] = measure.GIF
    if hooks and hasattr(hooks, "post"):
        pages = hooks.post(pages, content, cfg, spec, site_dir)

    kw_errors, kw_warnings = seokit.keyword_problems([m for m in metas if m["kind"] not in seokit.ALWAYS_NOINDEX or m.get("primary_kw")])
    errors += kw_errors
    warnings += kw_warnings
    for a, b, j in seokit.similar_pairs(pages, kinds):
        errors.append(f"{a} and {b}: the text overlaps by {j} (more than {seokit.SIMILAR_LIMIT}): merge them or make one of them noindex")
    errors += seokit.alt_problems(pages)

    thin = seokit.thin_reasons(pages, kinds)
    declared = {rel_of[p["path"]] for p in content if p.get("noindex")}
    for rel in set(thin) | declared:
        pages[rel] = _noindex(pages[rel])
    sitekit.drop_ads_from_noindex(pages)
    indexable = {rel for rel in pages if rel.endswith("index.html") and rel not in thin and rel not in declared and not _is_noindex(pages[rel])}
    errors += seokit.link_problems(pages, indexable | set(thin), cfg["site_url"].split("//")[-1].rstrip("/"))
    if strict_seo:
        errors += [f"{rel}: thin ({'; '.join(why)})" for rel, why in sorted(thin.items()) if kinds.get(rel) not in seokit.ALWAYS_NOINDEX]
    if errors:
        raise BuildError(f"{len(errors)} SEO / content problem(s):\n  " + "\n  ".join(errors[:80]))

    lastmod = {rel_of[p["path"]]: page_updated(p, spec) for p in content}
    pages.update(sitekit.standard_files(pages, cfg, preview, spec["updated"]))
    if measure_tag:
        pages[".htaccess"] += 'SetEnvIf Request_URI "^/m/" Ngx_Cache_NoCacheMode=on\n'      # the server cache must not answer the counting requests: they would never reach the access log
    pages["sitemap.xml"] = _sitemap(cfg, sorted(indexable), lastmod, spec["updated"])
    from sokuhou import mallstore                                 # a site with shelves.json ships the product shelves' files (api/shelf.php, assets/shelf.js); the products themselves are never in the build
    pages.update(mallstore.build_files(site_dir, cfg))
    return pages, {"thin": thin, "warnings": warnings, "pages": len(content), "indexable": len(indexable)}


def _is_noindex(html) -> bool:
    return isinstance(html, str) and bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))


def _noindex(html: str) -> str:
    if 'name="robots"' in html:
        return html
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex,follow">', 1)


def _sitemap(cfg: dict, rels: list[str], lastmod: dict, default: str) -> str:
    base = cfg["site_url"].rstrip("/")
    urls = sorted({"/" + r[: -len("index.html")] for r in rels}, key=lambda u: (u != "/", u))
    by_url = {"/" + r[: -len("index.html")]: lastmod.get(r, default) for r in rels}
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{by_url[u]}</lastmod></url>\n" for u in urls) + "</urlset>\n")


def _sources_html(spec: dict) -> str:
    style = spec.get("sources_style", "block")
    if style != "block":      # no addresses, no per-source dates on the site (owner 2026-11-03): the about page names who the figures come from, if the site says so
        lines = list(dict.fromkeys([*(spec.get("credits") or []), *(s["credit"] for s in spec.get("sources", {}).values() if s.get("credit"))])) if style == "credit" else []
        return f'<ul>{"".join("<li>" + esc(x) + "</li>" for x in lines)}</ul>' if lines else "公的機関などが公表している統計を、加工して掲載しています。"
    rows = []
    for s in spec.get("sources", {}).values():
        link = f'(<a href="{esc(s["url"])}" rel="noopener" target="_blank">公開ページ</a>)' if s.get("url") else ""
        rows.append(f"<li>{esc(s['org'])}「{esc(s['table'])}」{link}</li>")
    return f'<ul>{"".join(rows)}</ul>' if rows else "(未設定)"


def _disclaimer_html(spec: dict) -> str:
    corr = spec.get("corrections") or []
    hist = ("<ul>" + "".join(f"<li>{esc(c['date'])}: {esc(c['text'])}</li>" for c in corr) + "</ul>") if corr else "<p>これまでに、公開した数字を訂正したことはありません。</p>"
    method = "".join(f"<p>{esc(t)}</p>" for t in spec.get("method", []))
    return (f"{''.join('<p>' + esc(t) + '</p>' for t in spec.get('disclaimer', []))}\n<h2>数字の出し方</h2>\n{method}\n"
            "<h2>誤りを見つけたら</h2>\n<p><a href=\"/contact/\">お問い合わせ</a>からお知らせください。出典と照らして誤りと確認できたときは直し、直した日と内容を下の履歴に書きます。</p>\n"
            f"<h2>訂正の履歴</h2>\n{hist}")


def main_build(site_dir: Path, argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(site_dir / "dist"))
    ap.add_argument("--strict-seo", action="store_true", help="a thin page fails the build (before launch: every first page must pass the bars)")
    ap.add_argument("--allow-example", action="store_true", help="let a release build keep the example pages (tests only)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        pages, report = build_pages(site_dir, release=a.release, allow_example=a.allow_example, strict_seo=a.strict_seo)
    except BuildError as e:
        sys.exit(str(e))
    sitekit.write_pages(pages, Path(a.out))
    print(f"built {len(pages)} files into {a.out}: {report['pages']} content pages, {report['indexable']} indexable, {len(report['thin'])} thin (noindex,follow)")
    for rel, why in sorted(report["thin"].items()):
        print(f"  thin {rel}: {'; '.join(why)}")
    for w in report["warnings"]:
        print(f"  warning {w}")


# ---------------------------------------------------------------- init
def _icons(assets: Path, glyph: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    def make(size: int):
        im = Image.new("RGB", (size, size), (23, 96, 107))
        d = ImageDraw.Draw(im)
        font = None
        for f in (r"C:\Windows\Fonts\YuGothB.ttc", r"C:\Windows\Fonts\meiryob.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
            try:
                font = ImageFont.truetype(f, int(size * 0.6))
                break
            except OSError:
                continue
        if font is not None:
            d.text((size / 2, size / 2), glyph, fill="white", font=font, anchor="mm")
        else:
            d.ellipse((size * .3, size * .3, size * .7, size * .7), fill="white")
        return im
    make(32).save(assets / "favicon-32.png")
    make(180).save(assets / "apple-touch-icon.png")
    make(48).save(assets / "favicon.ico", sizes=[(48, 48)])


def _example_rows():
    """Fixed, obviously made-up numbers for the example pages (never published: a release refuses example pages)."""
    out = []
    for i, short in enumerate(prefectures.SHORT):
        out.append((short, prefectures.SLUG[short], 1000 + (i * 7919) % 5000))
    return out


def init_site(name: str, domain: str, site_name: str, glyph: str, sites_dir: Path, today: str) -> Path:
    if not NAME.fullmatch(name):
        raise BuildError(f"the name must be lowercase letters and digits starting with a letter, got {name!r}")
    d = sites_dir / name
    if d.exists():
        raise BuildError(f"{d} exists already; init never overwrites")
    (d / "assets").mkdir(parents=True)
    (d / "content").mkdir()
    shutil.copy(ASSETS_SRC / "style.css", d / "assets" / "style.css")
    _icons(d / "assets", glyph)
    cfg = {"site_url": f"https://{domain}", "site_name": site_name, "operator_name": "株式会社MACS", "contact_email": None, "contact_own": True, "contact_kinds": DEFAULT_KINDS, "measure": True}
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec = {
        "glyph": glyph, "updated": today, "home_label": "トップ",
        "nav": [["数字の一覧", "/list/", "/list/"], ["解説", "/guide/", "/guide/"]],
        "footer_html": "出典: (例)各ページの末尾に、機関名・表の名前・基準日・取得日を書いています。",
        "purpose": "(例)公的な統計を、ページごとに一つの問いへ答える形に整えて載せること。",
        "update_text": "(例)出典の表が更新されたら、数字を入れ替えて、各ページの最終更新日を書き換えます。",
        "disclaimer": ["(例)数字は出典の公表時点のものです。判断や手続きの前に、出典の公開ページで最新の内容を確かめてください。"],
        "method": ["(例)出典の表から数字をそのまま読み取り、順位と増減だけを当サイトで計算しています。計算の式は、各ページの本文に書きます。"],
        "corrections": [],
        "sources_style": "credit",
        "credits": [],
        "sources": {"example": {"org": "(例)出典の機関名", "table": "(例)表の名前", "credit": "(例)出典の機関名『表の名前』を加工して作成", "url": "", "basis": "2026年4月1日", "fetched": today}},
    }
    (d / "site.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for fname, page in _example_pages(today).items():
        (d / "content" / fname).write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d / "build.py").write_text(
        '"""Builds this site (the scaffold of sokuhou/newsite.py).  python sites/%s/build.py --release --out release"""\nfrom pathlib import Path\nimport sys\n\n'
        'sys.path.insert(0, str(Path(__file__).resolve().parents[2]))\nfrom sokuhou import newsite  # noqa: E402\n\nif __name__ == "__main__":\n    newsite.main_build(Path(__file__).resolve().parent)\n' % name,
        encoding="utf-8")
    (d / "__init__.py").write_text("", encoding="utf-8")
    return d


def _example_pages(today: str) -> dict[str, dict]:
    rows = _example_rows()
    ranked = sorted(rows, key=lambda r: -r[2])
    base = {"updated": today, "data_basis": "(例)2026年4月1日現在", "sources": ["example"], "example": True}
    pages = {
        "home.json": {**base, "path": "/", "kind": "hub", "title": "(例)トップの検索語とは", "h1": "(例)トップの検索語の最新の数字", "primary_kw": "(例)トップの検索語", "intent": 1,
                      "description": "(例)最新の数字を一文で書き、続けて範囲・更新日・出典の機関名を書きます。八十字から百二十字に収めます。広告めいた語は使いません。",
                      "answer": "(例)最新の数字を含む、四十字から八十字の答えの文をここに書きます。検索結果の抜粋になる文です。",
                      "sections": [{"h2": "(例)いま見てほしい数字", "paras": ["(例)ここに、結論を一、二文で書きます。"]}]},
        "list.json": {**base, "path": "/list/", "kind": "list", "parent": "/", "title": "(例)都道府県別の一覧", "h1": "(例)都道府県別の一覧", "primary_kw": "(例)都道府県別の一覧",
                      "intent": 2, "description": "(例)四十七都道府県の数字を高い順に並べた表です。最新の数字、範囲、更新日、出典の機関名をここに書きます。",
                      "answer": "(例)いちばん高いのは" + ranked[0][0] + "の" + str(ranked[0][2]) + "です。四十字から八十字で書きます。",
                      "dataset": {"csv": "data/list.csv", "table_section": 1},
                      "sections": [{"h2": "(例)地図で見る", "tilemap": {"title": "(例)都道府県別の数字", "values": {s: v for _, s, v in rows}, "unit": "", "href_prefix": "/pref/"}},
                                   {"h2": "(例)高い順の表", "table": {"caption": "(例)都道府県別の数字(高い順)", "cols": ["順位", "都道府県", "数字"], "num_cols": [0, 2],
                                                                 "rows": [[str(i + 1), {"text": short, "href": f"/pref/{slug}/"} if i < 3 else short, str(v)] for i, (short, slug, v) in enumerate(ranked)]}},
                                   {"h2": "(例)順位の分布", "chart": {"kind": "bar", "title": "(例)上位8都道府県", "desc": "(例)数字の高い順に8都道府県を並べた棒グラフです。",
                                                                "labels": [r[0] for r in ranked[:8]], "values": [r[2] for r in ranked[:8]]}}]},
        "guide.json": {**base, "path": "/guide/", "kind": "analysis", "parent": "/", "title": "(例)数字の見方", "h1": "(例)数字の見方", "primary_kw": "(例)数字の見方", "intent": 4,
                       "description": "(例)数字の意味、計算のしかた、読むときの注意を説明するページです。八十字から百二十字で書きます。",
                       "answer": "(例)この数字は、出典の表の値を並べ替えたものです。四十字から八十字で書きます。",
                       "sections": [{"h2": "(例)見出し", "paras": ["(例)本文を書きます。"]}],
                       "related": [{"path": "/list/", "text": "(例)都道府県別の一覧"}]},
    }
    for short, slug, v in ranked[:3]:
        pages[f"pref-{slug}.json"] = {**base, "path": f"/pref/{slug}/", "kind": "item", "parent": "/list/", "title": f"(例){short}の数字", "h1": f"(例){short}の数字",
                                      "primary_kw": f"(例){short}の数字", "intent": 3, "description": f"(例){short}の数字の推移と順位を示すページです。八十字から百二十字で書きます。",
                                      "answer": f"(例){short}の数字は{v}で、四十七都道府県のなかで上位です。",
                                      "sections": [{"h2": "(例)推移", "table": {"caption": f"(例){short}の推移", "cols": ["年", "数字", "前の年との差"], "num_cols": [0, 1, 2],
                                                    "rows": [[str(2014 + k), str(v - 40 + k * 7), str(7)] for k in range(12)]}}],
                                      "related": [{"path": "/list/", "text": "(例)都道府県別の一覧"}]}
    return pages


def preflight(site_dir: Path | None, domain: str, keys_file: Path | None = None, *, atomou_style: bool = False) -> list[str]:
    """What the first deploy of a site needs from the repository (deploy.yml, step by step): the IndexNow key of its host ('IndexNow key file'), a build.py ('Build'),
    and a config.json whose site_url is the registered domain ('Verify' looks for the site under that address).  Returns the problems; empty means the repository side is ready.
    What no file can say (the repository variable DEPLOY_<NAME>, the domain on the server, its public_html folder) is listed in SCAFFOLD_USAGE.md."""
    from sokuhou import indexnow
    problems = []
    try:
        keys = indexnow.load_keys(keys_file) if keys_file else indexnow.load_keys()
        if not atomou_style and domain not in keys:
            problems.append(f"no IndexNow key for {domain} in data/indexnow_keys.json (the deploy step 'IndexNow key file' would stop): python -m sokuhou.indexnow add-key {domain}")
    except (indexnow.IndexNowError, OSError, ValueError, KeyError) as e:
        problems.append(f"data/indexnow_keys.json cannot be read: {e}")
    if site_dir is not None:
        if not (site_dir / "build.py").exists():
            problems.append(f"{site_dir}/build.py is missing (the deploy step 'Build' runs it)")
        try:
            cfg = json.loads((site_dir / "config.json").read_text(encoding="utf-8"))
            if cfg["site_url"].split("//")[-1].rstrip("/") != domain:
                problems.append(f"config.json site_url ({cfg['site_url']}) is not https://{domain}")
        except (OSError, ValueError, KeyError) as e:
            problems.append(f"{site_dir}/config.json cannot be read: {e}")
    return problems


def register(name: str, domain: str, site_name: str, sites_json: Path, min_pages: int, site_dir: Path | None = None, keys_file: Path | None = None) -> None:
    """Append the site's entry to data/sites.json, keeping the file's layout (one entry per line).  Makes the IndexNow key of the domain first (the first deploy of kurashi stopped
    on its absence, 2026-11-04) and refuses, naming each missing piece, when the repository side of the first deploy is not ready."""
    from sokuhou import indexnow
    try:
        indexnow.ensure_key(domain, keys_file) if keys_file else indexnow.ensure_key(domain)
    except (indexnow.IndexNowError, OSError, ValueError, KeyError) as e:
        raise BuildError(f"cannot make the IndexNow key of {domain}: {e}") from e
    problems = preflight(site_dir, domain, keys_file)
    if problems:
        raise BuildError("not ready to register:\n  " + "\n  ".join(problems))
    text = sites_json.read_text(encoding="utf-8")
    data = json.loads(text)
    if any(s["name"] == name for s in data["sites"]):
        raise BuildError(f"{name} is already in {sites_json}")
    entry = json.dumps({"name": name, "domain": domain, "marker": site_name, "min_pages": min_pages, "needs_var": True}, ensure_ascii=False)
    i = text.rindex("]")
    head = text[:i].rstrip()
    sites_json.write_text(f"{head},\n    {entry}\n  " + text[i:], encoding="utf-8")
    json.loads(sites_json.read_text(encoding="utf-8"))   # still valid


def seo_rows(site_dir: Path) -> list[list[str]]:
    _, _, content = load_site(site_dir)
    rows = []
    for p in content:
        if p.get("primary_kw"):
            rows.append([p["path"], p["primary_kw"], " / ".join(p.get("secondary_kw") or []), str(p.get("intent", "")), p["title"], "", ""])
    return rows


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="newsite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("name")
    i.add_argument("--domain", required=True)
    i.add_argument("--site-name", required=True)
    i.add_argument("--glyph", default="")
    i.add_argument("--sites-dir", default=str(ROOT / "sites"))
    i.add_argument("--register", action="store_true", help="also append the site to data/sites.json")
    i.add_argument("--min-pages", type=int, default=10)
    g = sub.add_parser("register", help="add an existing sites/<name> to data/sites.json (after the deploy gate knows the name)")
    g.add_argument("site_dir")
    g.add_argument("--min-pages", type=int, default=10)
    b = sub.add_parser("build")
    b.add_argument("site_dir")
    b.add_argument("rest", nargs=argparse.REMAINDER)
    r = sub.add_parser("seo-report")
    r.add_argument("site_dir")
    c = sub.add_parser("seo-csv")
    c.add_argument("site_dir")
    c.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "init":
            from datetime import datetime, timedelta, timezone
            today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
            d = init_site(a.name, a.domain, a.site_name, a.glyph or a.site_name[0], Path(a.sites_dir), today)
            from sokuhou import indexnow
            key, created = indexnow.ensure_key(a.domain)
            print(f"IndexNow key for {a.domain}: {'made and added to data/indexnow_keys.json (commit it with the site)' if created else 'already in data/indexnow_keys.json'}")
            print(f"made {d}: edit config.json / site.json, replace the example pages in content/, then: python -m sokuhou.newsite build {d} --out out/{a.name}")
            if a.register:
                register(a.name, a.domain, a.site_name, ROOT / "data" / "sites.json", a.min_pages, site_dir=d)
                print(f"added {a.name} to data/sites.json.  BEFORE pushing: .github/workflows/deploy.yml's Gate step skips a site only by name (kuma, yorokobu, minna, atomou); "
                      f"a new name is published as soon as the server folder and the secrets exist.  Add its DEPLOY_{a.name.upper()} switch there first (the report desk's job).")
            else:
                print("not registered. The line for data/sites.json:  " + json.dumps({"name": a.name, "domain": a.domain, "marker": a.site_name, "min_pages": a.min_pages, "needs_var": True}, ensure_ascii=False))
            return 0
        site_dir = Path(a.site_dir)
        if a.cmd == "register":
            cfg = json.loads((site_dir / "config.json").read_text(encoding="utf-8"))
            register(site_dir.name, cfg["site_url"].split("//")[-1], cfg["site_name"], ROOT / "data" / "sites.json", a.min_pages, site_dir=site_dir)
            print(f"added {site_dir.name} to data/sites.json (check that deploy.yml's Gate and inbox.yml know the name first)")
            return 0
        if a.cmd == "build":
            main_build(site_dir, a.rest)
            return 0
        if a.cmd == "seo-report":
            _, report = build_pages(site_dir, allow_example=True)
            print(f"{report['pages']} content pages, {report['indexable']} indexable, {len(report['thin'])} thin")
            for rel, why in sorted(report["thin"].items()):
                print(f"  thin {rel}: {'; '.join(why)}")
            for w in report["warnings"]:
                print(f"  warning {w}")
            return 0
        if a.cmd == "seo-csv":
            out = Path(a.out) if a.out else None
            head = ["path", "primary_kw", "secondary_kw", "intent", "title", "target_rank", "priority"]
            rows = seo_rows(site_dir)
            if out:
                out.parent.mkdir(parents=True, exist_ok=True)
                with open(out, "w", encoding="utf-8-sig", newline="") as f:
                    csv.writer(f).writerows([head] + rows)
                print(f"wrote {len(rows)} rows to {out}")
            else:
                csv.writer(sys.stdout).writerows([head] + rows)
            return 0
    except BuildError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
