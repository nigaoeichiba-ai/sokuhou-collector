"""wadaiconv: turns the output of the writing workshop (article-opus.md + article-opus.json + materials/<id>.json) into one HTML page the owner can open.

The text is never changed: the markdown body is the text, line for line.  The marker lines the workshop leaves where a table, a map, a check list, a poll or a product
card belongs ("[表: 人数別の早見表]", "[チェックリスト]", ...) are replaced by the real parts; the parts' data come from the materials (parts[].content) and from a
private config (polls, the map, links to the child pages, the hero picture).  Nothing but this code is in the repository: the config, the pictures and the pages stay in the
private Dropbox folder.

    python -m sokuhou.wadaiconv --kobo <work/kobo> --config <components.json> --out <folder> [--shots <folder>] [id ...]

Always reads the latest output of the workshop (run it again after the text is rewritten).
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import zlib
from pathlib import Path

from sokuhou import wadaipage as pg

E = html.escape
MARK_RE = re.compile(r"^\[([^\]]+)\]$")

CALC_CSS = """
.calc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin:14px 0}
.calc label{font-weight:700}.calc input[type=number]{font:inherit;width:5.5em;padding:4px 8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.calc .res{margin:10px 0 0}.calc .res table{margin:0}
td.in input{font:inherit;width:100%;min-width:5em;padding:4px 6px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.costcalc th[scope=row]{min-width:7.5em;font-size:14px}td.out{font-weight:700}.countbar{background:var(--accbg);border-radius:12px;padding:8px 14px;margin:6px 0 14px;font-weight:700}
.toc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 18px;margin:18px 0}.toc h2{font-size:17px;margin:0 0 4px}.toc ol{margin:0;padding-left:1.4em}.toc a{color:var(--acc)}
.kids{list-style:none;padding:0}.kids li{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:10px 14px}.kids a{color:var(--acc);font-weight:700}.kids .sub{display:block;font-size:14px;color:var(--muted)}
.slot b{display:block;color:var(--fg);margin-bottom:4px}
"""

CALC_JS = """
(function(){
  function num(s){var m=String(s).replace(/,/g,"").match(/-?\\d+(\\.\\d+)?/);return m?parseFloat(m[0]):null}
  function unit(s){return String(s).replace(/,/g,"").replace(/-?\\d+(\\.\\d+)?/,"").trim()}
  function fmt(n){return (Math.round(n*100)/100).toLocaleString("ja-JP")}
  Array.prototype.forEach.call(document.querySelectorAll(".calc[data-pp]"),function(c){
    var pp=JSON.parse(c.dataset.pp),inp=c.querySelector("input"),res=c.querySelector(".res");
    function paint(){var n=parseInt(inp.value,10);if(!(n>=1&&n<=99)){res.textContent="1から99までの人数を入れてください。";return}
      var h="<table><thead><tr><th scope=col>項目</th><th scope=col>"+n+"人分</th></tr></thead><tbody>";
      pp.forEach(function(r){h+="<tr><td>"+r[0]+"</td><td>"+fmt(r[1]*n)+r[2]+"</td></tr>"});res.innerHTML=h+"</tbody></table>"}
    inp.addEventListener("input",paint);paint()});
  Array.prototype.forEach.call(document.querySelectorAll("table.costcalc"),function(t){
    function val(el){var v=parseFloat(el.value);return isNaN(v)?0:v}
    function paint(){var cols=t.querySelectorAll("thead th").length-1;
      for(var c=0;c<cols;c++){var get=function(k){var e=t.querySelectorAll("[data-k='"+k+"']")[c];return e};
        var price=val(t.querySelectorAll("[data-k='price']")[c]),times=val(t.querySelectorAll("[data-k='times']")[c]);
        var total=price*times+val(get("fee"))+val(get("goods"))+val(get("other"));
        get("total").textContent=total?fmt(total)+"円":"";
        get("per").textContent=(total&&times)?fmt(total/times)+"円":""}}
    t.addEventListener("input",paint);paint()});
  Array.prototype.forEach.call(document.querySelectorAll(".countable"),function(box){
    var out=document.getElementById(box.dataset.out);function paint(){var all=box.querySelectorAll("input[type=checkbox]");var n=0;Array.prototype.forEach.call(all,function(x){if(x.checked)n++});out.textContent="いま、"+n+"個にチェックが入っています(全部で"+all.length+"個)"}
    box.addEventListener("change",paint);paint()});
})();
"""


# ---- parsing the workshop's markdown --------------------------------------------------------------------------------------------------------------
def parse_md(text: str) -> dict:
    """{title, lead, tldr[], toc[], sections[{heading, blocks[{t: p|ul|mark|box, ...}]}]}.  The first paragraph under the title is the lead."""
    lines = text.replace("\r\n", "\n").split("\n")
    out = {"title": "", "lead": "", "tldr": [], "toc": [], "sections": []}
    cur = None
    para: list[str] = []
    quote: list[str] = []
    bullets: list[str] = []
    mode = "lead"          # lead | tldr | toc | body

    def target():
        return cur["blocks"] if cur is not None else None

    def flush():
        nonlocal para, quote, bullets
        if para:
            t = "".join(para)
            if mode == "lead" and not out["lead"]:
                out["lead"] = t
            elif target() is not None:
                target().append({"t": "p", "text": t})
            para = []
        if bullets:
            if mode == "tldr":
                out["tldr"] += bullets
            elif mode == "toc":
                out["toc"] += bullets
            elif target() is not None:
                target().append({"t": "ul", "items": bullets})
            bullets = []
        if quote:
            head = quote[0]
            m = re.match(r"(ライフハック|豆知識)\s*[:：]\s*(.*)", head)
            if m and target() is not None:
                target().append({"t": "box", "kind": "hack" if m.group(1) == "ライフハック" else "tip", "title": m.group(2).strip(), "text": "".join(quote[1:]).strip()})
            elif target() is not None:
                target().append({"t": "p", "text": "".join(quote)})
            quote = []

    for ln in lines:
        s = ln.rstrip()
        if s.startswith("# ") and not out["title"]:
            flush()
            out["title"] = s[2:].strip()
        elif s.startswith("## "):
            flush()
            head = s[3:].strip()
            if head in ("3行まとめ", "3行でまとめ"):
                mode, cur = "tldr", None
            elif head == "目次":
                mode, cur = "toc", None
            else:
                mode = "body"
                cur = {"heading": re.sub(r"^■\s*", "", head), "blocks": []}
                out["sections"].append(cur)
        elif not s.strip():
            flush()
        elif s.startswith("- ") and not para:
            if quote:
                flush()
            bullets.append(s[2:].strip())
        elif s.startswith(">"):
            if para or bullets:
                flush()
            quote.append(s.lstrip(">").strip())
        elif MARK_RE.match(s.strip()) and not para:
            flush()
            if target() is not None:
                target().append({"t": "mark", "mark": s.strip()})
        else:
            if bullets or quote:
                flush()
            para.append(s.strip())
    flush()
    return out


def parse_table(md: str) -> tuple[list[str], list[list[str]]]:
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in md.strip().split("\n") if r.strip().startswith("|")]
    rows = [r for r in rows if not all(re.fullmatch(r"-+", c) for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


def parse_check(content: str) -> list[str]:
    parts = re.split(r"□", content)
    return [p.strip() for p in parts if p.strip()]


# ---- parts ---------------------------------------------------------------------------------------------------------------------------------------
def table_part(title: str, md: str, kind: str = "") -> str:
    head, rows = parse_table(md)
    if not head:
        return ""
    if kind == "cost":
        return cost_table(title, head, rows)
    out = pg.table_html({"title": title, "headers": head, "rows": rows})
    # a table of rows "1人 ... 5人": an input that works out the numbers for any number of people
    if rows and re.fullmatch(r"\d+人", rows[0][0]):
        pp = []
        for h, cell in zip(head[1:], rows[0][1:]):
            m = re.match(r"\s*([\d,.]+)\s*(.*)", cell)
            if m:
                pp.append([h, float(m.group(1).replace(",", "")), m.group(2)])
        if pp:
            out += ('<div class="calc" data-pp="' + E(json.dumps(pp, ensure_ascii=False)) + '"><label for="n-' + _h(title) + '">人数を入れると、その人数の分が出ます</label> '
                    '<input id="n-' + _h(title) + '" type="number" min="1" max="99" value="6" inputmode="numeric"> 人<div class="res" aria-live="polite"></div></div>')
    return out


def cost_table(title: str, head: list[str], rows: list[list[str]]) -> str:
    """The table of the total cost: the empty cells are input fields; the total and the cost per visit work themselves out."""
    cols = len(head) - 1
    body = []
    for r in rows:
        label = r[0]
        cells = []
        if "回数" in label and "×" in label:
            key = None
            for c in range(cols):
                cells.append(f'<td class="in"><label>1回の料金<input type="number" min="0" inputmode="numeric" data-k="price"></label><label>回数<input type="number" min="0" inputmode="numeric" data-k="times"></label></td>')
        elif label.startswith("入会金"):
            cells = ['<td class="in"><input type="number" min="0" inputmode="numeric" data-k="fee" aria-label="入会金"></td>'] * cols
        elif "勧められた" in label:
            cells = ['<td class="in"><input type="number" min="0" inputmode="numeric" data-k="goods" aria-label="勧められた商品・サービス"></td>'] * cols
        elif label.startswith("そのほか"):
            cells = ['<td class="in"><input type="number" min="0" inputmode="numeric" data-k="other" aria-label="そのほか"></td>'] * cols
        elif label.startswith("総額") and "÷" in label:
            cells = ['<td class="out" data-k="per"></td>'] * cols
        elif label.startswith("総額"):
            cells = ['<td class="out" data-k="total"></td>'] * cols
        else:
            cells = ['<td class="in"><input type="number" min="0" inputmode="numeric" data-k="exit" aria-label="途中でやめたときに請求される額"></td>'] * cols
        body.append(f"<tr><th scope=\"row\">{E(label)}</th>{''.join(cells)}</tr>")
    thead = "<th scope=\"col\">項目</th>" + "".join(f'<th scope="col">{E(h)}</th>' for h in head[1:])
    return (f'<div class="tablewrap"><table class="costcalc"><caption>{E(title)}(数字を入れると、下の行に合計が出ます)</caption><thead><tr>{thead}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def check_part(items: list[str], idx: int) -> str:
    oid = f"count{idx}"
    lis = "".join(f'<li><label><input type="checkbox"> {E(x)}</label></li>' for x in items)
    return f'<div class="countable" data-out="{oid}"><ul class="check">{lis}</ul><p class="countbar" id="{oid}" aria-live="polite"></p></div>'


def children_part(children: list[dict], base_dir: Path | None) -> str:
    li = []
    for c in children:
        href = c.get("href", "")
        title = E(c["title"])
        sub = f'<span class="sub">{E(c["sub"])}</span>' if c.get("sub") else ""
        li.append(f'<li><a href="{E(href)}">{title}</a>{sub}</li>' if href else f"<li>{title}{sub}</li>")
    return '<ul class="kids">' + "".join(li) + "</ul>"


def _h(s: str) -> str:
    return str(zlib.crc32(s.encode("utf-8")) % 100000)


def _slug(h: str) -> str:
    return "h-" + _h(h)


# ---- the page -----------------------------------------------------------------------------------------------------------------------------------
def build_page(pid: str, kobo: Path, cfg: dict, base_dir: Path) -> tuple[str, dict]:
    out_dir = kobo / "out" / pid
    md = parse_md((out_dir / "article-opus.md").read_text(encoding="utf-8"))
    meta = json.loads((out_dir / "article-opus.json").read_text(encoding="utf-8")) if (out_dir / "article-opus.json").exists() else {}
    mat_path = kobo / "materials" / f"{pid}.json"
    mat = json.loads(mat_path.read_text(encoding="utf-8")) if mat_path.exists() else {}
    parts = {p["mark"]: p for p in mat.get("parts", [])}
    pc = {**cfg.get("default", {}), **cfg.get("pages", {}).get(pid, {})}
    used = {"table": 0, "map": 0, "check": 0, "poll": 0, "cards": 0, "kids": 0}
    unresolved = []

    def render_mark(mark: str, idx: int) -> str:
        inner = mark.strip("[]")
        if inner.startswith("表"):
            title = inner.split(":", 1)[-1].strip().lstrip("：")
            p = parts.get(mark) or {}
            kind = pc.get("table_kinds", {}).get(mark, "")
            if p.get("content"):
                used["table"] += 1
                return table_part(title, p["content"], kind)
        elif inner.startswith("図"):
            fig = pc.get("figures", {}).get(mark)
            if fig:
                used["map"] += 1
                return pg.figure_html(fig)
        elif inner.startswith("チェックリスト"):
            items = pc.get("checklists", {}).get(mark) or (parse_check(parts[mark]["content"]) if mark in parts and parts[mark].get("content") else None)
            if items:
                used["check"] += 1
                return check_part(items, idx)
        elif inner.startswith("アンケート"):
            polls = pc.get("polls")
            if polls:
                used["poll"] += len(polls)
                return "".join(pg.poll_html_one({**po, "note": po.get("note", "答えは任意です。答えなくても、このまま読み進められます。名前や連絡先は聞きません。")}, i) for i, po in enumerate(polls))
        elif inner.startswith("子ページの案内"):
            kids = pc.get("children")
            if kids:
                used["kids"] += 1
                return children_part(kids, base_dir)
        elif inner.startswith("商品カード"):
            used["cards"] += 1
            return '<div class="slot" aria-label="商品カードの位置"><b>商品カードの枠</b>商品が入ると、ここにカードが並びます。広告を含む案内は、カードのすぐ近くにだけ表示します。</div>'
        unresolved.append(mark)
        return f'<p class="slot">(部品がまだありません: {E(mark)})</p>'

    toc_items = [s["heading"] for s in md["sections"]]
    sec_html = []
    for si, sec in enumerate(md["sections"]):
        part = [f'<section><h2 id="{_slug(sec["heading"])}">{E(sec["heading"])}</h2>']
        for bi, b in enumerate(sec["blocks"]):
            if b["t"] == "p":
                part.append(f"<p>{E(b['text'])}</p>")
            elif b["t"] == "ul":
                part.append("<ul>" + "".join(f"<li>{E(x)}</li>" for x in b["items"]) + "</ul>")
            elif b["t"] == "box":
                part.append(pg.box_html(b))
            elif b["t"] == "mark":
                part.append(render_mark(b["mark"], si * 10 + bi))
        part.append("</section>")
        sec_html.append("".join(part))
    toc = ""
    if md["toc"] or toc_items:
        toc = '<nav class="toc" aria-label="目次"><h2>目次</h2><ol>' + "".join(f'<li><a href="#{_slug(h)}">{E(h)}</a></li>' for h in toc_items) + "</ol></nav>"
    tl = "".join(f"<li>{E(x)}</li>" for x in md["tldr"])
    hero = ""
    if pc.get("hero"):
        img = (base_dir / pc["hero"])
        if img.exists():
            data = base64.b64encode(img.read_bytes()).decode()
            hero = f'<figure class="fig fig-image"><img src="data:image/webp;base64,{data}" alt="{E(pc.get("hero_alt", ""))}"></figure>'
    series_name = pc.get("series", "ニュースから備える手帖")
    parent = pc.get("parent_href", "")
    series = f'<p class="series">シリーズ「{f"<a href={chr(34)}{E(parent)}{chr(34)}>{E(series_name)}</a>" if parent else E(series_name)}」</p>'
    nxt = ""
    if pc.get("next"):
        nxt = '<div class="next"><h2 class="h-sm">次に読む</h2><ul>' + "".join(f'<li><a href="{E(n.get("href", ""))}">{E(n["title"])}</a></li>' for n in pc["next"]) + "</ul></div>"
    title = md["title"]
    share = pg.share_html(title, pc.get("path", f"/{pid}/"), pc.get("base", "https://kaimono-wadai.example"))
    updated = meta.get("updated", "")
    foot = f'<footer><p>最終更新 {E(updated)} ／ 編集部</p></footer>' if updated else ""
    page = ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{E(title)}</title><meta name=\"description\" content=\"{E(md['lead'][:110])}\"><meta name=\"robots\" content=\"noindex\">"
            f"<style>{pg.CSS}{CALC_CSS}</style></head><body><div class=\"wrap\">{series}<h1>{E(title)}</h1><p class=\"lead\">{E(md['lead'])}</p>"
            f"<div class=\"tldr\"><h2>3行でまとめ</h2><ol>{tl}</ol></div>{hero}{toc}{''.join(sec_html)}{share}{nxt}{foot}</div>"
            f"<script>{pg.JS}{CALC_JS}</script></body></html>")
    return page, {"id": pid, "title": title, "parts": used, "unresolved": unresolved, "sections": len(md["sections"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="workshop output -> one HTML page per article (text untouched)")
    ap.add_argument("--kobo", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args(argv)
    kobo, out = Path(a.kobo), Path(a.out)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ids = a.ids or [d.name for d in sorted((kobo / "out").iterdir()) if d.is_dir() and not d.name.startswith("_") and (d / "article-opus.md").exists()]
    out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for pid in ids:
        page, info = build_page(pid, kobo, cfg, out)
        (out / f"kobo_{pid}.html").write_text(page, encoding="utf-8")
        flag = "  UNRESOLVED " + ", ".join(info["unresolved"]) if info["unresolved"] else ""
        print(f"{pid}: {info['sections']} sections, parts {info['parts']}{flag}")
        rc = 1 if info["unresolved"] else rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
