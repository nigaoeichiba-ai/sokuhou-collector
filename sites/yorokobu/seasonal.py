"""季節とお祝いの早見表 (/oseibo/ /nenga/ /oiwai/ ...): one-page cheat sheets that can be printed, each fact tied to the department-store page it was read on.

Everything on these pages comes from the files content/seasonal/*.json, whose `sources` are the pages (三越伊勢丹, 高島屋, 大丸松坂屋, 松坂屋名古屋店) opened and read in a real browser on the file's `checked` date.  A section names the
sources it rests on; where the stores disagree (the months of お歳暮, 寒中御伺 or 寒中御見舞) the page shows each store's wording instead of picking one.  Nothing is written that the sources do
not say, and the page says that customs differ by region and family.  The pages carry the Rakuten and Amazon search buttons like the other gift pages; no price or picture of a product is shown.
"""
from __future__ import annotations

import json
from pathlib import Path

from sokuhou.sitekit import crumbs, esc

HERE = Path(__file__).resolve().parent


def _b():
    from sites.yorokobu import build
    return build


def load() -> dict:
    """Every file of content/seasonal/ merged: sources (an id may not repeat), pages (each page remembers the date its file was checked), hooks (occasion -> the block that leads to its sheets)."""
    out: dict = {"sources": {}, "pages": [], "hooks": {}, "checked": ""}
    for f in sorted((HERE / "content" / "seasonal").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for k, v in d.get("sources", {}).items():
            if k in out["sources"]:
                raise ValueError(f"seasonal content: source id {k} is in two files")
            out["sources"][k] = v
        for pg in d.get("pages", []):
            out["pages"].append({**pg, "checked": pg.get("checked") or d.get("checked", "")})
        for k, v in d.get("hooks", {}).items():
            if k in out["hooks"]:
                raise ValueError(f"seasonal content: hook {k} is in two files")
            out["hooks"][k] = v
        out["checked"] = max(out["checked"], d.get("checked", ""))
    return out


SOURCE_HOSTS = ("www.mistore.jp", "www.takashimaya.co.jp", "www.daimaru-matsuzakaya.jp", "www.matsuzakaya.co.jp")      # the stores whose pages were read; another host needs a human decision


def problems(data: dict) -> list[str]:
    """What must hold for the content (the build refuses to publish otherwise): every section says its sources, every source is a store page we read, tables are rectangular and without empty cells."""
    out: list[str] = []
    for pg in data.get("pages", []):
        if not pg.get("checked"):
            out.append(f"{pg.get('slug', '?')}: no `checked` date")
    paths_ = {pg.get("path") for pg in data.get("pages", [])}
    for occ, h in data.get("hooks", {}).items():
        if not (h.get("title") and h.get("text") and h.get("links")):
            out.append(f"hook {occ}: needs title, text and links")
        for u, _t in h.get("links", []):
            if u not in paths_:
                out.append(f"hook {occ}: links to {u}, which is not a sheet")
    srcs = data.get("sources", {})
    for k, v in srcs.items():
        host = v["url"].split("/")[2] if v.get("url", "").startswith("https://") else ""
        if host not in SOURCE_HOSTS:
            out.append(f"source {k}: host {host or v.get('url')!r} is not a store page that was read")
        if not v.get("name") or not v.get("short"):
            out.append(f"source {k}: no name")
    for pg in data.get("pages", []):
        for f in ("slug", "path", "title", "h1", "lead", "query", "sections", "related"):
            if not pg.get(f):
                out.append(f"{pg.get('slug', '?')}: missing {f}")
        for s in pg.get("sections", []):
            where = f"{pg.get('slug')}/{s.get('h')}"
            if not s.get("h"):
                out.append(f"{where}: no heading")
            if not s.get("src"):
                out.append(f"{where}: names no source")
            for k in s.get("src", []):
                if k not in srcs:
                    out.append(f"{where}: unknown source {k}")
            if not any(s.get(f) for f in ("p", "table", "list", "check")):
                out.append(f"{where}: empty section")
            t = s.get("table")
            if t:
                for r in t["rows"]:
                    if len(r) != len(t["head"]) or any(not str(c).strip() for c in r):
                        out.append(f"{where}: a table row with the wrong number of cells or an empty cell: {r}")
    return out


def paths() -> list[str]:
    return [p["path"] for p in load()["pages"]]


def _table(t: dict) -> str:
    head = "".join(f"<th scope=\"col\">{esc(h)}</th>" for h in t["head"])
    rows = "".join(f'<tr><th scope="row">{esc(r[0])}</th>' + "".join(f"<td>{esc(c)}</td>" for c in r[1:]) + "</tr>" for r in t["rows"])
    return f'<div class="tablewrap"><table class="seas-tbl"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def _section(s: dict, sources: dict) -> str:
    out = [f'<section class="g-sec"><h2><span class="scribble">{esc(s["h"])}</span></h2>']
    out += [f"<p>{esc(p)}</p>" for p in s.get("p", [])]
    if s.get("table"):
        out.append(_table(s["table"]))
    if s.get("list"):
        out.append('<ul class="seas-list">' + "".join(f"<li>{esc(x)}</li>" for x in s["list"]) + "</ul>")
    if s.get("check"):
        out.append('<ul class="checklist">' + "".join(f'<li><label><input type="checkbox"> {esc(x)}</label></li>' for x in s["check"]) + "</ul>")
    if s.get("note"):
        out.append(f'<p class="seas-note">{esc(s["note"])}</p>')
    out.append("</section>")
    return "".join(out)


SOURCE_NOTE = "しきたりには諸説があり、地域や家で違います。贈る相手の習慣が分かるときは、それに合わせてください。"


def sources_note(subject: str = "記事", own_view: bool = True) -> str:
    """The one notice at the foot of every page that rests on sources (the same words everywhere): what the page is, and that customs differ."""
    core = f"この{subject}は、出典先を要約・比較し、当サイトの考え方を足したものです。" if own_view else f"この{subject}は、出典先を要約・比較したものです。"
    return core + SOURCE_NOTE


def sources_block(items_html: str, checked: str, subject: str = "記事", own_view: bool = True) -> str:
    y, m, d = checked.split("-")
    return (f'<section class="g-sec seas-srcs"><h2><span class="scribble">出典(確認日 {int(y)}年{int(m)}月{int(d)}日)</span></h2><ul class="seas-list">{items_html}</ul>'
            f'<p class="seas-note">{esc(sources_note(subject, own_view))}</p></section>')


def _sources(data: dict, used: list[str], checked: str) -> str:
    items = "".join(
        f'<li><a href="{esc(data["sources"][k]["url"])}" rel="noopener nofollow" target="_blank">{esc(data["sources"][k]["name"])}</a>'
        + (f'({esc(data["sources"][k]["date"])})' if data["sources"][k]["date"] else "") + "</li>" for k in used)
    return sources_block(items, checked, "早見表", own_view=False)


def page(d: dict, cfg: dict, preview: bool, pg: dict, data: dict, known: set[str] | None = None) -> str:
    B = _b()
    used: list[str] = []
    for s in pg["sections"]:
        for k in s.get("src", []):
            if k not in used:
                used.append(k)
    secs = "".join(_section(s, data["sources"]) for s in pg["sections"])
    trail = [("トップ", "/")]
    if pg.get("parent"):                                                      # [path, name] of the page above this one
        trail.append((pg["parent"][1], pg["parent"][0]))
    trail.append((pg["h1"], None))
    print_btn = '<p class="seas-print"><button type="button" class="btn btn-sub" data-print hidden>この早見表を印刷する</button></p>' if pg.get("print") else ""
    own = {q["path"] for q in data["pages"]}
    related = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for u, t in pg["related"]
                      if known is None or u in own or u.strip("/") + "/index.html" in known)             # the site's other pages come and go with its products: a link only to a page this build has
    buttons = f'<a class="btn" href="{esc(B.search_link(cfg, pg["query"]))}" rel="sponsored nofollow noopener" target="_blank">楽天市場で{esc(pg["query"])}を探す</a>'
    if cfg.get("amazon_tracking_id"):
        buttons += f'<a class="btn" href="{esc(B.amazon_url(cfg, pg["query"] + " ギフト"))}" rel="sponsored nofollow noopener" target="_blank">Amazonで{esc(pg["query"])}を探す</a>'
    buttons += B.yahoo_btn(cfg, pg["query"] + " ギフト", f'Yahoo!ショッピングで{pg["query"]}を探す')
    body = f"""{B.head_band("sky", "", esc(pg["h1"]), pg["lead"], single=True)}
<div class="crumbs-wrap">{crumbs(trail)}</div>
{B.pr_with_amazon(cfg)}
<article class="guide seas">{print_btn}{secs}{_sources(data, used, pg["checked"])}</article>
<section class="related seas-more" style="margin-top:44px"><h2><span class="scribble">あわせて読む</span></h2><ul class="plain">{related}</ul>
<p class="item-btns" style="margin-top:18px">{buttons}</p></section>
<script src="/assets/seasonal.js" defer></script>"""
    return B.page(cfg, preview, path=pg["path"], title=f"{pg['title']} | {cfg['site_name']}", description=pg["lead"][:110], body=body, amazon_links=bool(cfg.get("amazon_tracking_id")))


def hook(occasion: str) -> str:
    """A short block on an occasion's own pages that leads to its sheets (empty when the occasion has none)."""
    h = load()["hooks"].get(occasion)
    if not h:
        return ""
    links = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for u, t in h["links"])
    return (f'<section class="seas-hook" style="margin-top:44px"><h2><span class="scribble">{esc(h["title"])}</span></h2><p>{esc(h["text"])}</p><ul class="plain">{links}</ul></section>')


def build_pages(d: dict, cfg: dict, preview: bool, known: dict | None = None) -> dict[str, str]:
    data = load()
    bad = problems(data)
    if bad:
        raise ValueError("seasonal content: " + "; ".join(bad))
    keys = set(known) if known is not None else None
    return {pg["path"].strip("/") + "/index.html": page(d, cfg, preview, pg, data, keys) for pg in data["pages"]}
