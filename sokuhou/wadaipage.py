"""wadai: the reading edition of an article -> one self-contained HTML page (a sample / the template of the site's page).

Input: the article JSON of sokuhou/wadaipost.py in its "reading" format (format: "reading"):
  title, lead, tldr[3], reader_memo, series{name, parent, children[{path,title,kind}]}, hero{image}, sections[{layer, heading, summary, paras, bullets, boxes[{kind: tip|hack, title, text}],
  figures[{kind: chart|table|diagram|image, pos: before|after, ...}], slot}], poll{id, question, options}, next[{path,title}], updated, ads.
Output: HTML with inline CSS and a little inline JavaScript: no external file, no tracker, no cookie; the page shows no source links (owner 2026-11-04).  The only outside links are the two share
buttons (X and LINE, ordinary links that the reader clicks).
Charts are drawn here as inline SVG with a title and a description; every chart also carries its numbers in a table ("数字で見る") because a phone shrinks the drawing.  Escaping is done for every text.
The poll asks one question, takes a choice only, keeps nothing about the reader; the choice is counted on the server side as a number (api/poll.php, to be built) and shown in the next article.
Favourites are kept in the reader's own browser (localStorage); nothing is sent.  The share buttons are plain links (copy / X / LINE); clicks are counted by the site's cookie-less measure.
"""
from __future__ import annotations

import html
import json
import urllib.parse

E = html.escape


def _e(s) -> str:
    return E(str(s), quote=True)


# ---- charts (inline SVG) ---------------------------------------------------------------------------------------------------------------------
W, H, PADL, PADR, PADT, PADB = 520, 340, 76, 30, 28, 48


def _scale(v, lo, hi, a, b):
    return a + (v - lo) / ((hi - lo) or 1) * (b - a)


def _nice_hi(v: float) -> float:
    """The top of a bar chart: four equal steps of a round size (1, 2, 2.5, 4, 5, 8 times a power of ten), at least 5% above the biggest bar."""
    import math
    need = v * 1.05 / 4
    mag = 10 ** math.floor(math.log10(need))
    for m in (1, 2, 2.5, 4, 5, 8, 10):
        if m * mag >= need:
            return 4 * m * mag
    return 4 * 10 * mag


def _axes(lo, hi, unit) -> str:
    o = [f'<line class="axis" x1="{PADL}" y1="{H - PADB}" x2="{W - PADR}" y2="{H - PADB}"/><line class="axis" x1="{PADL}" y1="{PADT}" x2="{PADL}" y2="{H - PADB}"/>']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = _scale(v, lo, hi, H - PADB, PADT)
        o.append(f'<line class="grid" x1="{PADL}" y1="{y:.1f}" x2="{W - PADR}" y2="{y:.1f}"/><text class="lab" x="{PADL - 6}" y="{y + 4:.1f}" text-anchor="end">{v:,.0f}</text>')
    if unit:
        o.append(f'<text class="lab" x="{PADL}" y="{PADT - 10}">{_e(unit)}</text>')
    return "".join(o)


def _map_svg(fig: dict) -> str:
    """A map of the north-west Pacific with real coastlines (Natural Earth, public domain; sokuhou/wadaimap.py) and a track drawn on it.
    fig: points[{x: east longitude, y: north latitude, label, name, obs, dx, dy}], marks[{x, y, label, dx, dy}], extent (optional)."""
    import math
    from sokuhou import wadaimap
    x0, x1, y0, y1 = fig.get("extent", wadaimap.EXTENT)
    k = math.cos(math.radians((y0 + y1) / 2))
    MW = 520
    MH = round(MW * (y1 - y0) / ((x1 - x0) * k))

    def px(lon, lat):
        return (lon - x0) / (x1 - x0) * MW, (y1 - lat) / (y1 - y0) * MH
    sid = id(fig)
    o = [f'<svg viewBox="0 0 {MW} {MH}" role="img" aria-labelledby="t{sid} d{sid}" class="chart map"><title id="t{sid}">{_e(fig["title"])}</title><desc id="d{sid}">{_e(fig.get("desc", fig["title"]))}</desc>',
         f'<defs><clipPath id="c{sid}"><rect width="{MW}" height="{MH}"/></clipPath></defs><rect class="sea" width="{MW}" height="{MH}"/><g clip-path="url(#c{sid})">']
    for gx in range(int(x0 // 10 * 10 + 10), int(x1) + 1, 10):
        a, _ = px(gx, y0)
        o.append(f'<line class="grid" x1="{a:.1f}" y1="0" x2="{a:.1f}" y2="{MH}"/><text class="lab" x="{a + 3:.1f}" y="{MH - 5}">東経{gx}度</text>')
    for gy in range(int(y0 // 10 * 10 + 10), int(y1), 10):
        _, b = px(x0, gy)
        o.append(f'<line class="grid" x1="0" y1="{b:.1f}" x2="{MW}" y2="{b:.1f}"/><text class="lab" x="4" y="{b - 4:.1f}">北緯{gy}度</text>')
    for ring in wadaimap.rings():
        o.append('<path class="land" d="M' + " L".join(f"{px(lo, la)[0]:.1f},{px(lo, la)[1]:.1f}" for lo, la in ring) + ' Z"/>')
    pts = fig["points"]
    P = [px(p["x"], p["y"]) for p in pts]
    o.append('<polyline class="ln" fill="none" stroke-dasharray="7 5" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in P) + '"/>')
    for m in fig.get("marks", []):
        x, y = px(m["x"], m["y"])
        o.append(f'<rect class="mk" x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8"/><text class="lab mkl" x="{x + m.get("dx", 8):.1f}" y="{y + m.get("dy", 4):.1f}">{_e(m["label"])}</text>')
    for (x, y), p in zip(P, pts):
        o.append(f'<circle class="{"pt" if p.get("obs") else "pt fc"}" cx="{x:.1f}" cy="{y:.1f}" r="5.5"/>')
        if p.get("label"):
            o.append(f'<text class="val" x="{x + p.get("dx", 9):.1f}" y="{y + p.get("dy", -8):.1f}">{_e(p["label"])}</text>')
    o.append("</g></svg>")
    return "".join(o)


def chart_svg(fig: dict) -> str:
    kind = fig["type"]
    if kind == "map":
        return _map_svg(fig)
    title, desc = fig["title"], fig.get("desc", fig["title"])
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="t{id(fig)} d{id(fig)}" class="chart"><title id="t{id(fig)}">{_e(title)}</title><desc id="d{id(fig)}">{_e(desc)}</desc>']
    if kind == "bar":
        labels, vals = fig["labels"], fig["values"]
        hi = _nice_hi(max(vals))
        out.append(_axes(0, hi, fig.get("unit", "")))
        bw = (W - PADL - PADR) / len(vals)
        for i, (lab, v) in enumerate(zip(labels, vals)):
            x = PADL + i * bw + bw * 0.15
            y = _scale(v, 0, hi, H - PADB, PADT)
            cls = "bar partial" if i in fig.get("partial", []) else ("bar hl" if fig.get("highlight") == i else "bar")      # a partial period is hollow with a dashed edge: never read it as a full year
            out.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw * 0.7:.1f}" height="{H - PADB - y:.1f}" rx="3"/>')
            out.append(f'<text class="val" x="{x + bw * 0.35:.1f}" y="{y - 6:.1f}" text-anchor="middle">{_e(fig.get("fmt", "{:,}").format(v))}</text>')
            out.append(f'<text class="lab" x="{x + bw * 0.35:.1f}" y="{H - PADB + 18}" text-anchor="middle">{_e(lab)}</text>')
    elif kind == "line":
        labels, vals = fig["labels"], fig["values"]
        lo, hi = fig.get("min", min(vals) - 5), fig.get("max", max(vals) + 5)
        out.append(_axes(lo, hi, fig.get("unit", "")))
        step = (W - PADL - PADR - 30) / (len(vals) - 1)               # keep the last label inside the frame
        pts = [(PADL + 10 + i * step, _scale(v, lo, hi, H - PADB, PADT)) for i, v in enumerate(vals)]
        out.append('<polyline class="ln" fill="none" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>')
        for (x, y), lab, v in zip(pts, labels, vals):
            out.append(f'<circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="5"/><text class="val" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle">{_e(v)}</text>')
            out.append(f'<text class="lab" x="{x:.1f}" y="{H - PADB + 18}" text-anchor="middle">{_e(lab)}</text>')
    elif kind == "xy":
        # a position chart: x = east longitude, y = north latitude; points joined in order by a helper line; "obs" points are filled, forecast points hollow; fixed marks are squares
        pts, marks = fig["points"], fig.get("marks", [])
        xs = [p["x"] for p in pts + marks]
        ys = [p["y"] for p in pts + marks]
        x0, x1 = min(xs) - 4, max(xs) + 4
        y0, y1 = min(ys) - 3, max(ys) + 3
        out.append(f'<rect class="plot" x="{PADL}" y="{PADT}" width="{W - PADL - PADR}" height="{H - PADT - PADB}"/>')
        for gx in range(int(x0 // 10 * 10 + 10), int(x1) + 1, 10):
            px = _scale(gx, x0, x1, PADL, W - PADR)
            out.append(f'<line class="grid" x1="{px:.1f}" y1="{PADT}" x2="{px:.1f}" y2="{H - PADB}"/><text class="lab" x="{px:.1f}" y="{H - PADB + 18}" text-anchor="middle">東経{gx}度</text>')
        for gy in range(int(y0 // 10 * 10 + 10), int(y1) + 1, 10):
            py = _scale(gy, y0, y1, H - PADB, PADT)
            out.append(f'<line class="grid" x1="{PADL}" y1="{py:.1f}" x2="{W - PADR}" y2="{py:.1f}"/><text class="lab" x="{PADL - 6}" y="{py + 4:.1f}" text-anchor="end">北緯{gy}度</text>')
        P = [(_scale(p["x"], x0, x1, PADL, W - PADR), _scale(p["y"], y0, y1, H - PADB, PADT)) for p in pts]
        out.append('<polyline class="ln" fill="none" stroke-dasharray="6 5" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in P) + '"/>')
        for (x, y), p in zip(P, pts):
            lab = f'<text class="val" x="{x + p.get("dx", 10):.1f}" y="{y + p.get("dy", -8):.1f}">{_e(p["label"])}</text>' if p.get("label") else ""
            out.append(f'<circle class="{"pt" if p.get("obs") else "pt fc"}" cx="{x:.1f}" cy="{y:.1f}" r="6"/>{lab}')
        for m in marks:
            x = _scale(m["x"], x0, x1, PADL, W - PADR)
            y = _scale(m["y"], y0, y1, H - PADB, PADT)
            out.append(f'<rect class="mk" x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10"/><text class="lab" x="{x + 9:.1f}" y="{y + 4:.1f}">{_e(m["label"])}</text>')
    else:
        raise ValueError("unknown chart type " + kind)
    out.append("</svg>")
    return "".join(out)


def chart_data_table(fig: dict) -> str:
    """The numbers of a chart as a table (opened with 数字で見る): a phone shrinks the drawing, a screen reader cannot see it."""
    k = fig["type"]
    if k in ("bar", "line"):
        unit = fig.get("unit", "")
        rows = [[lab, f"{v}{unit}"] for lab, v in zip(fig["labels"], fig["values"])]
        head = ["項目", "値"]
    else:
        rows = [[p.get("name") or p.get("label") or "", f"北緯{p['y']}度、東経{p['x']}度"] for p in fig["points"]]
        head = ["時刻", "位置"]
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return ('<details class="data"><summary>数字で見る</summary><div class="tablewrap"><table><thead><tr>' + "".join(f'<th scope="col">{_e(h)}</th>' for h in head)
            + f"</tr></thead><tbody>{body}</tbody></table></div></details>")


def table_html(fig: dict) -> str:
    head = "".join(f'<th scope="col">{_e(h)}</th>' for h in fig["headers"])
    rows = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in fig["rows"])
    return f'<div class="tablewrap"><table><caption>{_e(fig["title"])}</caption><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def steps_html(fig: dict) -> str:
    items = "".join(f'<li><span class="n">{i}</span><span>{_e(s)}</span></li>' for i, s in enumerate(fig["steps"], 1))
    return f'<ol class="steps" aria-label="{_e(fig["title"])}">{items}</ol>'


def figure_html(fig: dict) -> str:
    k = fig["kind"]
    extra = ""
    if k == "chart":
        inner = chart_svg(fig)
        extra = chart_data_table(fig)
    elif k == "table":
        inner = table_html(fig)
    elif k == "diagram":
        inner = steps_html(fig)
    elif k == "image":
        inner = f'<img src="{_e(fig["src"])}" alt="{_e(fig["alt"])}" loading="lazy">'
    else:
        raise ValueError("unknown figure kind " + k)
    cap = f'<figcaption>{_e(fig["caption"])}</figcaption>' if fig.get("caption") else ""
    return f'<figure class="fig fig-{k}">{inner}{extra}{cap}</figure>'


def box_html(b: dict) -> str:
    label = {"tip": "豆知識", "hack": "ライフハック"}[b["kind"]]
    return f'<aside class="box {b["kind"]}"><p class="box-h"><span class="tag">{label}</span> {_e(b["title"])}</p><p>{_e(b["text"])}</p></aside>'


def check_list_html(items) -> str:
    """A check list the reader can tick on the screen (nothing is saved)."""
    return '<ul class="check">' + "".join(f'<li><label><input type="checkbox"> {_e(x)}</label></li>' for x in items) + "</ul>"


# ---- page --------------------------------------------------------------------------------------------------------------------------------------
CSS = """
:root{--bg:#fbfaf7;--fg:#222;--muted:#666;--card:#fff;--line:#e4e0d8;--acc:#2f6f8f;--accbg:#e8f2f7;--tip:#fff6dc;--hack:#e9f6ec;--bar:#7aa7bf;--hl:#d9822b;--warn:#8a5a00;--sea:#e3eef5;--land:#efe9da;--coast:#a99f86;--mapgrid:#b9cad6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181b;--fg:#e9e7e2;--muted:#a8a69f;--card:#1d2226;--line:#2d343a;--acc:#7fc0e0;--accbg:#1c2d37;--tip:#3a331c;--hack:#1c3324;--bar:#4d7a92;--hl:#e8a050;--warn:#e8c070;--sea:#16262f;--land:#2b2f26;--coast:#6f6a58;--mapgrid:#2f4553}}
:root[data-theme="dark"]{--bg:#15181b;--fg:#e9e7e2;--muted:#a8a69f;--card:#1d2226;--line:#2d343a;--acc:#7fc0e0;--accbg:#1c2d37;--tip:#3a331c;--hack:#1c3324;--bar:#4d7a92;--hl:#e8a050;--warn:#e8c070;--sea:#16262f;--land:#2b2f26;--coast:#6f6a58;--mapgrid:#2f4553}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.85 "Hiragino Sans","Yu Gothic UI","Noto Sans JP",system-ui,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:16px 16px 72px}
.series{font-size:14px;color:var(--muted);margin:8px 0 0}.series a{color:var(--acc)}
h1{font-size:28px;line-height:1.4;margin:6px 0 12px}h2{font-size:22px;line-height:1.5;margin:40px 0 6px}h2.h-sm{font-size:20px;margin:28px 0 6px}
.lead{font-size:19px;line-height:1.8}
.tldr{background:var(--accbg);border-radius:14px;padding:14px 18px;margin:20px 0}.tldr h2{font-size:18px;margin:0 0 6px}.tldr ol{margin:0;padding-left:1.4em}
.sec-sum{color:var(--muted);font-size:15px;margin:0 0 12px}.sec-sum b{color:var(--acc)}
p{margin:0 0 14px}
.fig{margin:22px 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px}.fig svg{width:100%;height:auto;display:block}.fig img{width:100%;height:auto;border-radius:10px;display:block}
.fig figcaption{font-size:13px;color:var(--muted);margin-top:6px}
details.data{margin-top:6px;font-size:14px}details.data summary{cursor:pointer;color:var(--acc)}
.chart .axis{stroke:var(--muted);stroke-width:1}.chart .grid{stroke:var(--line);stroke-width:1}.chart .plot{fill:none;stroke:var(--line)}.chart .bar{fill:var(--bar)}.chart .bar.hl{fill:var(--hl)}.chart .bar.partial{fill:var(--card);stroke:var(--bar);stroke-width:2;stroke-dasharray:5 3}
.chart .ln{stroke:var(--hl);stroke-width:3}.chart .pt{fill:var(--hl);stroke:var(--card);stroke-width:2}.chart .pt.fc{fill:var(--card);stroke:var(--hl);stroke-width:3}.chart .mk{fill:var(--acc)}.chart .sea{fill:var(--sea)}.chart .land{fill:var(--land);stroke:var(--coast);stroke-width:.8}.chart.map .grid{stroke:var(--mapgrid);stroke-dasharray:2 4}.chart .mkl{font-size:13px}
.chart text{fill:var(--fg);font-size:14px}.chart .lab{fill:var(--muted)}.chart .val{font-weight:700}
.box{border-radius:14px;padding:12px 16px;margin:20px 0}.box.tip{background:var(--tip)}.box.hack{background:var(--hack)}.box p{margin:0 0 6px}.box-h{font-weight:700}.tag{display:inline-block;font-size:12px;border:1px solid currentColor;border-radius:999px;padding:0 8px;margin-right:6px}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:15px}caption{text-align:left;font-weight:700;padding-bottom:6px}th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}th{background:var(--accbg)}
.steps{list-style:none;margin:0;padding:0}.steps li{display:flex;gap:12px;align-items:flex-start;padding:8px 0}.steps .n{flex:none;width:28px;height:28px;border-radius:50%;background:var(--acc);color:var(--bg);display:inline-flex;align-items:center;justify-content:center;font-weight:700}
ul.check{list-style:none;padding:0}ul.check li{padding:4px 0}ul.check label{display:flex;gap:10px;align-items:flex-start;cursor:pointer}ul.check input{margin-top:.55em;width:18px;height:18px;accent-color:var(--acc)}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.btn{font:inherit;font-size:15px;border:1px solid var(--acc);color:var(--acc);background:transparent;border-radius:999px;padding:6px 16px;cursor:pointer;text-decoration:none;display:inline-block}.btn:hover,.btn[aria-pressed="true"]{background:var(--acc);color:var(--bg)}
.btn:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--hl);outline-offset:2px}
.act-note{font-size:13px;color:var(--muted);margin:0 0 6px}
.poll{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:28px 0}.poll legend{font-weight:700}.poll label{display:block;padding:4px 0;cursor:pointer}.poll .done{color:var(--acc);font-weight:700}.poll .err{color:var(--warn)}
.next,.series-nav{margin:28px 0}.next a,.series-nav a{color:var(--acc)}.next li,.series-nav li{margin:6px 0}
.slot{border:2px dashed var(--line);border-radius:14px;padding:18px;margin:20px 0;color:var(--muted);text-align:center;font-size:14px}
.urlbox{word-break:break-all;font-size:13px}
footer{margin-top:40px;font-size:13px;color:var(--muted)}.adnote{font-size:13px;color:var(--warn)}
"""
JS = """
(function(){
  function get(k,d){try{var v=JSON.parse(localStorage.getItem(k)||"null");return v===null?d:v}catch(e){return d}}
  function put(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true}catch(e){return false}}
  var fav=document.getElementById("fav");
  if(fav){var list=get("wadai:fav",[]);var msg=document.getElementById("favmsg");
    var has=function(){return list.some(function(x){return x.path===fav.dataset.path})};
    var paint=function(){fav.setAttribute("aria-pressed",has()?"true":"false");fav.textContent=has()?"お気に入りに入れた":"お気に入りに入れる"};paint();
    fav.addEventListener("click",function(){var before=list.slice();
      if(has()){list=list.filter(function(x){return x.path!==fav.dataset.path})}else{list.push({path:fav.dataset.path,title:fav.dataset.title})}
      if(put("wadai:fav",list)){msg.textContent=""}else{list=before;msg.textContent="この端末には保存できませんでした。"}paint()})}
  var copy=document.getElementById("copy");
  if(copy){var label=copy.textContent;var back=function(){setTimeout(function(){copy.textContent=label},2000)};
    copy.addEventListener("click",function(){var u=copy.dataset.url;
      if(navigator.clipboard){navigator.clipboard.writeText(u).then(function(){copy.textContent="コピーしました";back()}).catch(function(){copy.textContent="コピーできませんでした";back()})}
      else{var o=document.getElementById("urlbox");o.hidden=false;o.textContent=u}})}
  var share=document.getElementById("share");
  if(share){var u=share.dataset.url,t=share.dataset.title;
    document.getElementById("sx").href="https://twitter.com/intent/tweet?text="+encodeURIComponent(t)+"&url="+encodeURIComponent(u);
    document.getElementById("sl").href="https://line.me/R/msg/text/?"+encodeURIComponent(t+" "+u)}
  var poll=document.getElementById("poll");
  if(poll){var key="wadai:poll:"+poll.dataset.id;var form=poll.querySelector("form"),done=poll.querySelector(".done"),err=poll.querySelector(".err");
    var show=function(){form.hidden=true;done.hidden=false;done.textContent="ありがとうございます。集まった結果は、次の記事でお見せします。";done.focus()};
    if(get(key,null)!==null){form.hidden=true;done.hidden=false;done.textContent="答えてくれてありがとうございます。"}
    form.addEventListener("submit",function(ev){ev.preventDefault();var c=poll.querySelector("input:checked");
      if(!c){err.hidden=false;err.textContent="どれかを選んでください。";return}
      err.hidden=true;put(key,c.value);show();
      try{var x=new XMLHttpRequest();x.open("POST","/api/poll.php");x.setRequestHeader("Content-Type","application/json");x.send(JSON.stringify({id:poll.dataset.id,choice:c.value}))}catch(e){}})}
})();
"""


def _jsonld(a: dict) -> str:
    d = {"@context": "https://schema.org", "@type": "Article", "headline": a["title"], "dateModified": a["updated"], "description": a["lead"][:110],
         "isPartOf": {"@type": "CreativeWorkSeries", "name": a["series"]["name"]}}
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def render_article(a: dict, *, path: str = "/", base: str = "https://example.invalid") -> str:
    s = a["series"]
    secs = []
    for sec in a["sections"]:
        if sec["layer"] == "history":
            continue
        parts = [f'<section><h2>{_e(sec["heading"])}</h2>']
        if sec.get("summary"):
            parts.append(f'<p class="sec-sum"><b>ひとことで</b> {_e(sec["summary"])}</p>')
        for fig in [f for f in sec.get("figures", []) if f.get("pos", "before") == "before"]:
            parts.append(figure_html(fig))
        for p in sec.get("paras", []):
            parts.append(f"<p>{_e(p)}</p>")
        if sec.get("bullets"):
            if sec.get("ordered"):
                parts.append("<ol>" + "".join(f"<li>{_e(b)}</li>" for b in sec["bullets"]) + "</ol>")
            elif sec["layer"] == "prep":
                parts.append(check_list_html(sec["bullets"]))
            else:
                parts.append("<ul>" + "".join(f"<li>{_e(b)}</li>" for b in sec["bullets"]) + "</ul>")
        for p in sec.get("paras_after", []):          # paragraphs that come after the list
            parts.append(f"<p>{_e(p)}</p>")
        for fig in [f for f in sec.get("figures", []) if f.get("pos") == "after"]:
            parts.append(figure_html(fig))
        for b in sec.get("boxes", []):
            parts.append(box_html(b))
        if sec.get("slot"):
            parts.append('<div class="slot" aria-label="商品カードの位置">' + _e(sec["slot"]) + "</div>")
        if sec.get("cards"):      # product cards (filled at run time): the note goes with them
            parts.append('<p class="adnote">下の案内には広告が含まれます。</p>')
        parts.append("</section>")
        secs.append("".join(parts))
    hist = next((x for x in a["sections"] if x["layer"] == "history"), None)
    poll = a.get("poll")
    poll_html = ""
    if poll:
        opts = "".join(f'<label><input type="radio" name="c" value="{_e(o)}"> {_e(o)}</label>' for o in poll["options"])
        poll_html = (f'<div class="poll" id="poll" data-id="{_e(poll["id"])}"><form><fieldset style="border:0;padding:0;margin:0"><legend>{_e(poll["question"])}</legend>{opts}'
                     f'</fieldset><p class="err" role="alert" hidden></p><p style="margin:8px 0 0"><button class="btn" type="submit">これで答える</button> <small>選んだ項目だけを送ります。名前や連絡先の入力はありません。</small></p></form>'
                     f'<p class="done" role="status" aria-live="polite" tabindex="-1" hidden></p></div>')
    url = base + path
    q = urllib.parse.quote
    share = (f'<div id="share" data-url="{_e(url)}" data-title="{_e(a["title"])}"><p class="act-note">友だちにも教えたいときは、こちらから。お気に入りは、この端末のブラウザーにだけ保存します。</p>'
             f'<div class="actions"><button class="btn" id="copy" type="button" data-url="{_e(url)}">リンクをコピー</button>'
             f'<a class="btn" id="sx" rel="noopener" target="_blank" href="https://twitter.com/intent/tweet?text={q(a["title"])}&amp;url={q(url, safe="")}">Xで共有</a>'
             f'<a class="btn" id="sl" rel="noopener" target="_blank" href="https://line.me/R/msg/text/?{q(a["title"] + " " + url, safe="")}">LINEで送る</a>'
             f'<button class="btn" id="fav" type="button" aria-pressed="false" data-path="{_e(path)}" data-title="{_e(a["title"])}">お気に入りに入れる</button></div>'
             f'<p id="favmsg" class="act-note" role="status" aria-live="polite"></p><p id="urlbox" class="urlbox" hidden></p></div>')
    kids = "".join(f'<li><a href="{_e(c["path"])}">{_e(c["title"])}</a>({_e(c["kind"])})</li>' for c in s.get("children", []))
    nxt = "".join(f'<li><a href="{_e(n["path"])}">{_e(n["title"])}</a></li>' for n in a.get("next", []))
    tl = "".join(f"<li>{_e(x)}</li>" for x in a["tldr"])
    ad_top = ""      # the advertising note sits next to the product cards only (see the slot); never on a page without cards
    hist_html = ""
    if hist:
        hist_html = "<footer><p><b>更新履歴</b></p><ul>" + "".join(f"<li>{_e(b)}</li>" for b in hist.get("bullets", [])) + f"</ul><p>最終更新 {_e(a['updated'])} ／ 編集部</p></footer>"
    hero = figure_html(a["hero"]) if a.get("hero") else ""
    return ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{_e(a['title'])}</title><meta name=\"description\" content=\"{_e(a['lead'][:110])}\"><meta name=\"robots\" content=\"noindex\">"
            f"<style>{CSS}</style>{_jsonld(a)}</head><body><div class=\"wrap\">"
            f"<p class=\"series\">シリーズ「<a href=\"{_e(s['parent'])}\">{_e(s['name'])}</a>」</p><h1>{_e(a['title'])}</h1><p class=\"lead\">{_e(a['lead'])}</p>{ad_top}"
            f"<div class=\"tldr\"><h2>3行でまとめ</h2><ol>{tl}</ol></div>{hero}{''.join(secs)}{poll_html}{share}"
            f"{'<div class=\"series-nav\"><h2 class=\"h-sm\">このシリーズの続き</h2><ul>' + kids + '</ul></div>' if kids else ''}"
            f"<div class=\"next\"><h2 class=\"h-sm\">次に読む</h2><ul>{nxt}</ul></div>{hist_html}</div><script>{JS}</script></body></html>")


def render_child(page: dict, series: dict, *, parent_title: str, path: str = "/", base: str = "https://example.invalid") -> str:
    """A child page: a checklist / Q&A / scenes / quick table.  page: {title, lead, kind, blocks:[{type: para|h2|check|qa|table|box|figure}], next}."""
    body = []
    for b in page["blocks"]:
        t = b["type"]
        if t == "para":
            body.append(f"<p>{_e(b['text'])}</p>")
        elif t == "h2":
            body.append(f"<h2 class=\"h-sm\">{_e(b['text'])}</h2>")
        elif t == "check":
            body.append(check_list_html(b["items"]))
        elif t == "qa":
            body.append("".join(f"<details><summary><b>Q. {_e(q['q'])}</b></summary><p>A. {_e(q['a'])}</p></details>" for q in b["items"]))
        elif t == "table":
            body.append(table_html(b))
        elif t == "box":
            body.append(box_html(b))
        elif t == "figure":
            body.append(figure_html(b["figure"]))
    nxt = "".join(f'<li><a href="{_e(n["path"])}">{_e(n["title"])}</a></li>' for n in page.get("next", []))
    return ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{_e(page['title'])}</title><meta name=\"robots\" content=\"noindex\"><style>{CSS}details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:10px 0}}summary{{cursor:pointer}}</style></head><body><div class=\"wrap\">"
            f"<p class=\"series\">シリーズ「<a href=\"{_e(series['parent'])}\">{_e(series['name'])}</a>」の{_e(page['kind'])}</p><h1>{_e(page['title'])}</h1><p class=\"lead\">{_e(page['lead'])}</p>"
            f"{''.join(body)}<div class=\"next\"><h2 class=\"h-sm\">次に読む</h2><ul><li><a href=\"{_e(series['parent'])}\">{_e(parent_title)}(親ページ)</a></li>{nxt}</ul></div></div></body></html>")
