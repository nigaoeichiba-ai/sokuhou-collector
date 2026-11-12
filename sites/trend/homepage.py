"""The top page of trend-sokuho.com in the approved prototype's design (owner instruction 2026-11-11: the CSS is the prototype's, verbatim, in assets/home.css;
the old top design is replaced, not mixed in).  The wording is the confirmed wording of content/home.json and the articles; nothing is written here except the
little labels of the design.  The typhoon chip is worked out from the typhoon article's status numbers, so it always agrees with that page.

hooks.post() calls apply() for the top page only: it swaps the stylesheet of the head and the whole body."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import statuspanel

HERE = Path(__file__).resolve().parent
PARTS = json.loads((HERE / "home_parts.json").read_text(encoding="utf-8"))
CAT_TILE_ARTICLE = {"/cat/kakei/": "/trend-rice-price/", "/cat/bousai/": "/trend-fire-alarm/", "/cat/tenki/": "/trend-influenza-44/", "/cat/kurashi/": "/trend-nengajo-print/"}
FONT_LINKS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
              '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@500;700;900&display=swap" rel="stylesheet">\n')
STATUS_LABELS = [(8, "バッチリ準備OK！", "high"), (6, "あと一歩でカンペキ！", "mid"), (5, "最低限はクリア！", "mid"), (4, "半分くらい。まずは水と食料から！", "mid"), (0, "まずは水と食料から始めよう", "low")]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _section(home: dict, key: str) -> dict:
    for s in home["sections"]:
        if key in (s.get("html") or ""):
            return s
    raise SystemExit(f"top page: no section with {key!r} in content/home.json")


def ja_date(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(y)}年{int(m)}月{int(dd)}日"


TODAY = None                # tests set a day; the build uses the JST day
CHIP_MAX_AGE_DAYS = 2       # the typhoon chip is hidden when its "as of" day is older than this (a status panel that stops at last week misleads)


def _chip_fresh(asof_day: str, updated: str, today) -> bool:
    m = re.match(r"(\d+)日", asof_day)
    if not m:
        return False
    y, mo, _ = (int(x) for x in updated.split("-"))
    from datetime import date
    return (today - date(y, mo, int(m.group(1)))).days <= CHIP_MAX_AGE_DAYS


def typhoon_chip(content: list[dict], today=None) -> str:
    """The chip under the flash list: the typhoon page's own numbers (statuspanel works out the class and the danger level from the wind)."""
    ty = next(p for p in content if p["path"] == "/trend-typhoon32/")
    st = ty["status_typhoon"]
    today = today or TODAY
    if today is None:
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone(timedelta(hours=9))).date()
    if st.get("extratropical"):      # the typhoon is over (an extratropical low): no class and no danger level, so no chip
        return ""
    if not _chip_fresh(st["asof"], ty["updated"], today):
        return ""
    level, _ = statuspanel.danger(st["wind"])
    cls = statuspanel.LADDER[statuspanel.klass(st["wind"])][1]
    month = int(ty["updated"].split("-")[1])
    asof = f'{month}月{st["asof"]}'
    name = re.sub(r"^(台風\d+号).*$", r"\1", st["label"])
    segs = "".join('<span class="seg%s"></span>' % (" on-%d" % i if i <= level else "") for i in range(1, 6))
    # the park name (チャンパカ) is the article's own wording: the flash item and the h1 of the typhoon page
    para = re.search(r"[（(]([^）)]+)[）)]", ty["h1"])
    paren = f' <span>（{esc(para.group(1))}）</span>' if para else ""
    return (f'<div class="typhoon-chip" aria-label="{esc(name)}のステータス">'
            f'<span class="t-name"><a href="{ty["path"]}">{esc(name)}{paren}</a></span>'
            f'<span class="gauge" role="img" aria-label="危険度 5段階の{level}">{segs}</span>'
            f'<span class="gauge-label"><b>{esc(cls)}</b>・{esc(st["pressure"])}hPa</span>'
            f'<p class="t-meta">危険度は5段階の{level}｜{esc(asof)}</p></div>')


def newest_first(arts: list[dict]) -> list[dict]:
    return sorted(arts, key=lambda p: (p["published"], p.get("seq", 0), p["path"]), reverse=True)


def body(home: dict, content: list[dict], spec: dict, cfg: dict, slug_of, card_w: int, card_h: int, cat_path: dict, n_latest: int) -> str:
    by = {p["path"]: p for p in content}
    arts = newest_first([p for p in content if p.get("category")])
    hero = home["hero"]
    h1 = home["h1"]
    assert h1 == "速報ニュースを、どこよりも深掘りする。", h1
    band_r, band_k = h1.split("、", 1)
    band_k_html = esc(band_k).replace("深掘り", '<span class="yel">深掘り</span>', 1)

    # ---- header
    nav = "".join(f'<li><a href="{esc(path)}">{esc(label)}</a></li>' for label, path, *_ in spec["nav"])
    header = (f'<header class="site-header"><div class="wrap header-inner"><a class="brand" href="/" aria-label="今日の話題 速報×深掘り">'
              f'<img class="brand-logo" src="/assets/img/logo.png" width="385" height="160" alt="今日の話題 速報×深掘り"></a>'
              f'<nav class="main-nav" aria-label="カテゴリ"><ul>{nav}</ul></nav></div></header>')

    # ---- hero (the bands and the lead share one panel on the picture) + the flash panel
    flash_sec = _section(home, 'class="flash"')
    # the three flash items are the three newest articles (2026-11-13: the hand-written list in home.json stayed at 11/10 while 15 new articles went up); the heading is home.json's
    flash = [(f'{int(a["published"][5:7])}/{int(a["published"][8:10])}', a["path"], esc(a["h1"])) for a in arts[:3]]
    assert len(flash) == 3, flash
    items = "".join(f'<li><a href="{h}"><span class="b-date">{d}</span><span class="b-title">{t}</span></a></li>' for d, h, t in flash)
    hero_html = (f'<div class="hero"><div class="hero-visual">'
                 f'<img src="{esc(hero["img"])}" width="{hero["width"]}" height="{hero["height"]}" alt="{esc(hero["alt"])}" fetchpriority="high">'
                 f'<div class="hero-overlay"><div class="hero-panel"><h1 class="hero-title"><span class="band band-red">{esc(band_r)}、</span><br>'
                 f'<span class="band band-black">{band_k_html}</span></h1><p class="hero-line">{esc(home["answer"])}</p></div></div></div>'
                 f'<div class="wrap breaking-wrap"><div class="breaking" aria-labelledby="breakingTitle"><div class="breaking-head"><span class="live">速報</span>'
                 f'<h2 id="breakingTitle">{esc(flash_sec["h2"])}</h2></div><ul class="breaking-list">{items}</ul>{typhoon_chip(content)}</div></div></div>')

    # ---- 今日やること
    todo_sec = _section(home, 'class="todo"')
    todo = re.findall(r'<li><span class="badge">(.*?)</span><h3><a href="(.*?)">(.*?)</a></h3><p>(.*?)</p></li>', todo_sec["html"])
    assert len(todo) == 3, todo
    kinds = [("red", ""), ("navy", " soft"), ("yellow", " soft")]
    cards = "".join(f'<li class="action-card"><span class="action-icon {k}" aria-hidden="true">{PARTS["action_icons"][i]}</span><h3><a href="{h}">{t}</a></h3><p>{p}</p>'
                    f'<span class="deadline{soft}">{b}</span></li>' for i, ((b, h, t, p), (k, soft)) in enumerate(zip(todo, kinds)))
    paras = "".join(f"<p>{x}</p>" for x in todo_sec.get("paras", []))
    today = (f'<section class="block wrap" aria-labelledby="todayTitle"><div class="sec-head"><h2 id="todayTitle">{esc(todo_sec["h2"])}</h2>{paras}</div>'
             f'<ul class="actions">{cards}</ul></section>')

    # ---- 3つのこだわり (the prototype's "3つの約束": same design, the text is the confirmed one; no 「実例」 links)
    feat_sec = _section(home, 'class="feature-grid"')
    feats = re.findall(r'<h3><small>(\d+)</small><br>(.*?)</h3><p>(.*?)</p>', feat_sec["html"])
    assert len(feats) == 3, feats
    prom = "".join(f'<li class="promise"><div class="promise-visual" aria-hidden="true">{PARTS["promise_visuals"][i]}</div><div class="promise-body">'
                   f'<span class="promise-num">{n}</span><h3>{t}</h3><p>{p}</p></div></li>' for i, (n, t, p) in enumerate(feats))
    promise = (f'<section class="block wrap" aria-labelledby="promiseTitle"><div class="sec-head"><h2 id="promiseTitle">{esc(feat_sec["h2"])}</h2></div>'
               f'<ul class="promises">{prom}</ul></section>')

    # ---- 解説記事 (the 13 newest, newest first)
    lat_sec = next(s for s in home["sections"] if s.get("h2") == "注目の解説記事ラインナップ")
    lis = []
    for a in arts[:n_latest]:
        lead = a.get("top_lead") or a["_sum"]
        lis.append(f'<li><a class="article-card" href="{a["path"]}"><img class="a-img" src="/assets/img/card/{slug_of(a["path"])}.webp" width="{card_w}" height="{card_h}" '
                   f'alt="{esc(a["h1"])}" loading="lazy"><span class="a-body"><span class="a-meta"><span class="cat-chip">{esc(a["category"])}</span>'
                   f'<time datetime="{a["published"]}">{ja_date(a["published"])}</time></span><span class="a-title">{esc(a["h1"])}</span>'
                   f'<span class="a-lead">{esc(lead)}</span></span></a></li>')
    articles = (f'<section class="block wrap" aria-labelledby="articlesTitle"><div class="sec-head"><h2 id="articlesTitle">{esc(lat_sec["h2"])}</h2></div>'
                f'<ul class="articles">{"".join(lis)}</ul></section>')

    # ---- カテゴリ
    cat_sec = _section(home, 'class="links"')
    cats = re.findall(r'<li><a href="(.*?)">(.*?)</a>：(.*?)</li>', cat_sec["html"])
    assert len(cats) == 4, cats
    tiles = []
    for href, name, desc in cats:
        a = by[CAT_TILE_ARTICLE[href]]
        tiles.append(f'<li><a class="cat-tile" href="{href}"><img class="cat-img" src="/assets/img/card/{slug_of(a["path"])}.webp" width="{card_w}" height="{card_h}" '
                     f'alt="{esc(a["h1"])}" loading="lazy"><span class="cat-body"><h3>{name}</h3><p>{desc}</p></span></a></li>')
    category = (f'<section class="block wrap" id="category" aria-labelledby="catTitle"><div class="sec-head"><h2 id="catTitle">{esc(cat_sec["h2"])}</h2></div>'
                f'<ul class="categories">{"".join(tiles)}</ul></section>')

    # ---- 防災パネル
    bt_sec = _section(home, 'id="bt"')
    bt = bt_sec["html"]
    lead = re.search(r'<p class="bt-lead">(.*?)</p>', bt).group(1)
    m = re.match(r"(.*?)（※(.*?)）$", lead)
    lead_main, note = (m.group(1), m.group(2)) if m else (lead, "")
    rows = re.findall(r'<tr class="(?:on|)"><th scope="row"><a href="(.*?)">(.*?)</a></th><td>(.*?)(?:<span class="bt-sub">（(.*?)）</span>)?</td>.*?aria-pressed="(true|false)">(.*?)</button>', bt)
    assert len(rows) == 8, rows
    on_label = "✓ " + rows[0][5]
    lis = []
    for i, (href, name, std, extra, pressed, label) in enumerate(rows):
        ex = f'<br><span class="extra">{extra}</span>' if extra else ""
        lis.append(f'<tr class="bousai-item"><td class="cell-icon" aria-hidden="true"><span class="b-icon">{PARTS["bousai_icons"][i]}</span></td>'
                   f'<th scope="row" class="b-text"><span class="name"><a href="{href}">{name}</a></span><br><span class="std">{std}</span>{ex}</th>'
                   f'<td class="cell-act"><button type="button" class="toggle" aria-pressed="{pressed}">{on_label if pressed == "true" else label}</button></td></tr>')
    n = sum(1 for r in rows if r[4] == "true")
    start = next(t for lo, t, _ in STATUS_LABELS if n >= lo)
    labels_js = json.dumps([[lo, t] for lo, t, _ in STATUS_LABELS], ensure_ascii=False)
    bousai = (f'<section class="block wrap" id="bousai" aria-labelledby="bousaiTitle"><div class="sec-head"><h2 id="bousaiTitle">{esc(bt_sec["h2"])}</h2></div>'
              f'<div class="bousai"><div class="bousai-head"><p>{lead_main}</p></div>'
              f'<div class="bousai-status" aria-live="polite"><span class="status-num"><span id="doneCount">{n}</span><small> / 8 項目達成！</small></span>'
              f'<span class="progress" role="img" aria-label="備えの進み具合"><span class="fill" id="progressFill" style="width:{n / 8 * 100:g}%"></span></span>'
              f'<span class="status-label" id="statusLabel">{esc(start)}</span></div><div class="tablewrap"><table class="bousai-list" id="bousaiList"><thead class="sr-only"><tr><th aria-hidden="true"></th><th scope="col">項目と目安</th><th scope="col">チェック</th></tr></thead><tbody>{"".join(lis)}</tbody></table></div>'
              + (f'<p class="bousai-note">※ {note}</p>' if note else "") + '</div></section>'
              '<script>\n(function () {\nvar toggles = document.querySelectorAll("#bousaiList .toggle");\nvar doneCount = document.getElementById("doneCount");\n'
              'var fill = document.getElementById("progressFill");\nvar label = document.getElementById("statusLabel");\n'
              f'var on = {json.dumps(on_label, ensure_ascii=False)}, off = {json.dumps(rows[0][5], ensure_ascii=False)};\nvar LABELS = {labels_js};\n'
              'function labelFor(n) { for (var i = 0; i < LABELS.length; i++) { if (n >= LABELS[i][0]) return LABELS[i][1]; } return LABELS[LABELS.length - 1][1]; }\n'
              'function refresh() {\n  var n = 0;\n  toggles.forEach(function (t) { if (t.getAttribute("aria-pressed") === "true") n++; });\n  doneCount.textContent = n;\n'
              '  fill.style.width = (n / 8 * 100) + "%";\n  label.textContent = labelFor(n);\n}\n'
              'toggles.forEach(function (t) {\n  t.addEventListener("click", function () {\n    var p = t.getAttribute("aria-pressed") === "true";\n'
              '    t.setAttribute("aria-pressed", p ? "false" : "true");\n    t.textContent = p ? off : on;\n    refresh();\n  });\n});\nrefresh();\n})();\n</script>')

    # ---- 編集部のこだわり (the prototype's 取材・執筆基準)
    std_sec = _section(home, "<ul><li>")
    lis_ = re.findall(r"<li>(.*?)</li>", std_sec["html"])
    closing = re.search(r"</ul><p>(.*?)</p>", std_sec["html"]).group(1)
    assert len(lis_) == 3, lis_
    stds = "".join(f'<li class="standard">{PARTS["standard_icons"][i]}<p>{t}</p></li>' for i, t in enumerate(lis_))
    standards = (f'<section class="block wrap" aria-labelledby="stdTitle"><div class="sec-head"><h2 id="stdTitle">{esc(std_sec["h2"])}</h2></div>'
                 f'<ul class="standards">{stds}</ul><p class="sec-closing">{closing}</p></section>')

    # ---- footer
    cat_links = "".join(f'<li><a href="{esc(path)}">{esc(label)}</a></li>' for label, path, *_ in spec["nav"])
    legal = '<li><a href="/about/">運営者情報</a></li><li><a href="/privacy/">プライバシーポリシー</a></li><li><a href="/contact/">お問い合わせ</a></li>'
    footer = ('<footer><div class="wrap footer-inner"><div class="footer-brand"><img class="footer-logo" src="/assets/img/logo.png" width="385" height="160" '
              'alt="今日の話題 速報×深掘り" loading="lazy"></div>'
              f'<ul class="footer-nav">{cat_links}</ul><ul class="footer-nav">{legal}</ul>'
              '<p class="footer-meta">「今日の話題」は、気になる速報ニュースをどこよりも深く、多角的に読み解くメディアです。<br>'
              f'最終更新：{ja_date(home["updated"])}<br>&copy; 今日の話題 速報×深掘り All Rights Reserved.<br>'
              '<a href="https://developers.rakuten.com/" target="_blank">Supported by Rakuten Developers</a></p></div></footer>')

    return f"{header}\n<main>\n{hero_html}\n{today}\n{promise}\n{articles}\n{category}\n{bousai}\n{standards}\n</main>\n{footer}\n"


def apply(t: str, home: dict, content: list[dict], spec: dict, cfg: dict, site_dir: Path, slug_of, card_w: int, card_h: int, cat_path: dict, n_latest: int) -> str:
    css = (site_dir / "assets" / "home.css").read_text(encoding="utf-8")
    ver = hashlib.sha1(css.encode()).hexdigest()[:8]
    new_link = f'<meta name="color-scheme" content="light dark">\n{FONT_LINKS}<link rel="stylesheet" href="/assets/home.css?v={ver}">'
    t, n = re.subn(r'<link rel="stylesheet" href="/assets/style\.css\?v=[0-9a-f]+">', lambda m: new_link, t, count=1)
    assert n == 1, "top page: the stylesheet link was not found"
    i, j = t.index("<body>") + len("<body>"), t.index("</body>")
    return t[:i] + "\n" + body(home, content, spec, cfg, slug_of, card_w, card_h, cat_path, n_latest) + t[j:]
