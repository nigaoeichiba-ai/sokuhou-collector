"""The extra angles of よろこぶプレゼント: gift map, etiquette checker, calculators, "who is this person?" quiz and its result pages.

Everything here is data-driven (content/taboo.json, persona.json, map_tags.json) and works without scripts where it can; the quiz and the
calculators need a little JavaScript (assets/app.js).  Page helpers come from build.py, imported when a function runs (build imports this module).
"""
from __future__ import annotations

import json

from sokuhou.sitekit import crumbs, esc

LEVELS = {"care": ("気にする人が多い", "care"), "note": ("覚えておくと安心", "note"), "ok": ("たいていは大丈夫", "ok")}
DOT_COLORS = ["#ff4d6d", "#38bdf8", "#2fd09b", "#ffc93c"]


def _b():
    from sites.yorokobu import build
    return build


# ---------------------------------------------------------------- gift map: where the ideas of a page sit between "used up / kept" and "classic / unusual"

def gift_map(page_key: str, ideas: list[dict], tags: dict, shown: set[int] | None = None) -> str:
    """An inline SVG with one dot per idea.  x: 消えもの (left) to 残るもの (right), y: 定番・無難 (bottom) to 個性的・意外 (top).  Dots link to the idea cards."""
    dots = tags.get(page_key)
    if not dots or len(dots) != len(ideas):
        return ""
    shown = set(range(len(ideas))) if shown is None else shown
    if len(shown) < 2:
        return ""
    w, h, pad = 640, 400, 46
    cx, cy = w / 2, h / 2

    def pos(x: float, y: float) -> tuple[float, float]:
        return pad + (x + 2) / 4 * (w - 2 * pad), h - pad - (y + 2) / 4 * (h - 2 * pad)

    parts = [f'<svg class="gmap-svg" viewBox="0 0 {w} {h}" role="img" aria-label="この{len(shown)}つの提案を、消えもの・残るもの、定番・個性的の二つの軸に置いた図">',
             f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="22" class="gm-bg"/>',
             f'<line x1="{pad}" y1="{cy}" x2="{w - pad}" y2="{cy}" class="gm-axis"/><line x1="{cx}" y1="{pad}" x2="{cx}" y2="{h - pad}" class="gm-axis"/>',
             f'<text x="{pad}" y="{h - 12}" class="gm-end">← 消えもの</text><text x="{w - pad}" y="{h - 12}" class="gm-end" text-anchor="end">残るもの →</text>',
             f'<text x="{cx + 10}" y="{pad - 18}" class="gm-end">個性的・意外 ↑</text><text x="{cx + 10}" y="{h - pad + 24}" class="gm-end">↓ 定番・無難</text>']
    placed: list[tuple[float, float]] = []
    for i, (idea, (x, y)) in enumerate(zip(ideas, dots)):
        if i not in shown:
            continue
        px, py = pos(float(x), float(y))
        while any(abs(px - qx) < 34 and abs(py - qy) < 34 for qx, qy in placed):   # dots that would sit on each other are nudged apart
            px, py = px + 30, py - 18
        placed.append((px, py))
        color = DOT_COLORS[i % 4]
        anchor = "end" if px > w - 150 else "start"
        tx = px - 18 if anchor == "end" else px + 18
        parts.append(f'<a href="#idea-{i}" class="gm-dot"><circle cx="{px:.0f}" cy="{py:.0f}" r="15" fill="{color}" class="gm-c"/>'
                     f'<text x="{px:.0f}" y="{py + 5:.0f}" class="gm-n" text-anchor="middle">{i + 1}</text>'
                     f'<text x="{tx:.0f}" y="{py + 5:.0f}" class="gm-l" text-anchor="{anchor}">{esc(idea["label"])}</text></a>')
    parts.append("</svg>")
    return ('<section class="gmap"><div class="sec-title"><span class="tag">ギフトマップ</span><h2>この提案は、どんなタイプ?</h2></div>'
            '<p class="sec-lead">横は「食べて消える」から「ずっと残る」まで、縦は「定番・無難」から「個性的・意外」まで。番号をおすと、提案に移動します。</p>'
            + "".join(parts) + "</section>")


# ---------------------------------------------------------------- etiquette checker

def taboo_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    entries = d["c"]["taboo"]
    occasions = sorted({o for e in entries for o in e["avoid_for"]})
    opts = "".join(f'<option value="{esc(o)}">{esc(o)}</option>' for o in occasions)
    cards = []
    for e in entries:
        label, cls = LEVELS[e["level"]]
        alt = f'<p class="tb-alt"><b>かわりに</b>{esc("、".join(e["alternatives"]))}</p>' if e["alternatives"] else ""
        cards.append(f'<li class="tb {cls}" data-names="{esc(" ".join(e["names"]))}" data-occ="{esc(",".join(e["avoid_for"]))}">'
                     f'<span class="tb-level">{esc(label)}</span><h3>{esc(e["title"])}</h3><p>{esc(e["why"])}</p>'
                     f'<p class="tb-tip"><b>こうすると安心</b>{esc(e["tip"])}</p>{alt}</li>')
    lead = "贈ろうと思っている品を入れると、昔からの言い伝えやマナー上の注意が、あるかどうか分かります。気にしすぎなくてよいものも、お伝えします。"
    body = f"""{B.head_band("sky", '<img class="pair-mini" src="/assets/img/navi-map.webp" alt="" width="170" height="130">', "贈る前に、縁起・マナーチェック", lead, single=True, mascot="b-wink")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("縁起・マナーチェック", None)])}</div>
<section class="tbcheck" id="tbcheck"><div class="tb-form"><label>贈ろうと思っている品<input type="search" name="q" placeholder="例: くし、ハンカチ、靴、お茶" autocomplete="off"></label>
<label>贈る場面<select name="o"><option value="">指定しない</option>{opts}</select></label></div>
<p class="tb-msg" role="status" aria-live="polite">下のリストから、品の名前でしぼりこめます。</p>
<ul class="tb-list">{"".join(cards)}</ul></section>
<p class="notice">ここに書いているのは、一般に知られているマナーや言い伝えの目安です。地域や家庭によって考え方はさまざまなので、迷ったときは、年長の方や相手の事情にあわせてください。</p>"""
    return B.page(cfg, preview, path="/tool/taboo/", title=f"贈る前の縁起・マナーチェック | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- calculators

def calc_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    lead = "いただいたお祝いへのお返しの目安と、みんなで贈るときの一人あたりの金額を、すぐに計算できます。"
    body = f"""{B.head_band("yellow", '<img class="pair-mini" src="/assets/img/concierge-note.webp" alt="" width="170" height="130">', "お返し・割り勘の計算", lead, single=True, mascot="r-wink")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("お返し・割り勘の計算", None)])}</div>
<div class="cols calc-cols" id="calc">
<section class="calc-card" data-calc="return"><h2><span class="scribble">お返しの目安</span></h2>
<label>いただいた金額・品物の金額(円)<input type="number" name="amount" min="0" step="500" value="10000" inputmode="numeric"></label>
<p class="calc-out" aria-live="polite"><b data-out="range"></b><small>一般に、いただいた額の3分の1から半分ほどを、お返しの目安にします。</small></p>
<p class="calc-links"><a href="/occasion/">イベントから、お返しの贈り物を探す</a></p></section>
<section class="calc-card" data-calc="split"><h2><span class="scribble">みんなで贈る(連名)</span></h2>
<label>全体の予算(円)<input type="number" name="total" min="0" step="1000" value="15000" inputmode="numeric"></label>
<label>人数<input type="number" name="people" min="1" step="1" value="5" inputmode="numeric"></label>
<p class="calc-out" aria-live="polite"><b data-out="each"></b><small data-out="note"></small></p></section></div>
<p class="notice">お返しの金額は、地域や関係によって考え方が違います。ここでは、よく言われる目安だけを計算しています。</p>"""
    return B.page(cfg, preview, path="/tool/calc/", title=f"お返し・割り勘の計算 | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- quiz and persona pages

def quiz_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]["persona"]
    data = esc(json.dumps({"questions": c["questions"], "slugs": [p["slug"] for p in c["personas"]]}, ensure_ascii=False, separators=(",", ":")))
    people = "".join(f'<li><a href="/diagnosis/{p["slug"]}/">{esc(p["name"])}</a></li>' for p in c["personas"])
    lead = "あの人のことを思い出しながら、6つの質問に答えてください。1分で、贈り物のヒントになる「タイプ」が見つかります。"
    body = f"""{B.head_band("lilac", '<img class="pair-mini" src="/assets/img/b-sparkle.webp" alt="" width="170" height="155">', "あの人は、どんなタイプ?", lead, single=True, mascot="r-sparkle")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("プレゼント診断", None)])}</div>
<section class="quiz" id="quiz" data-json="{data}"><noscript><p class="notice">この診断は、JavaScriptを使います。下の一覧から、タイプを見てみてください。</p></noscript>
<div class="quiz-card" hidden><p class="quiz-step"></p><h2 class="quiz-q"></h2><div class="quiz-opts"></div></div>
<p class="quiz-start"><button type="button" class="btn big" data-start>診断をはじめる</button></p></section>
<section style="margin-top:44px"><h2><span class="scribble">8つのタイプ</span></h2><ul class="plain cols2 chips">{people}</ul></section>"""
    return B.page(cfg, preview, path="/diagnosis/", title=f"あの人はどんなタイプ? プレゼント診断 | {cfg['site_name']}", description=lead, body=body)


def persona_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    B = _b()
    c = d["c"]
    themes = [c["theme"][s] for s in p["themes"] if s in c["theme"]]
    links = "".join(f'<li><a href="/theme/{t["slug"]}/">{esc(t["title"])}</a></li>' for t in themes)
    others = "".join(f'<li><a href="/diagnosis/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in c["persona"]["personas"] if x["slug"] != p["slug"])
    body = f"""{B.head_band("pink", '<img class="pair-mini" src="/assets/img/r-joy.webp" alt="" width="170" height="155">', esc(p["name"]), p["tagline"], single=True, mascot="b-joy")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("プレゼント診断", "/diagnosis/"), (p["name"], None)])}</div>
{B.pr_quiet(cfg)}
{B.share_bar(cfg, f"/diagnosis/{p['slug']}/", f"うちのあの人は『{p['name']}』だった! あなたの周りの人は?", "この結果を、だれかに送る")}
<section style="margin-top:30px"><p class="persona-about">{esc(p["about"])}</p></section>
<section class="cols"><div><h2><span class="scribble">よろこびやすいもの</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["likes"])}</ol></div>
<div class="avoid"><h2><span class="scribble">ちょっと外しやすいもの</span></h2>{B.ul(p["avoid"], "warn")}</div></section>
<section style="margin-top:34px"><h2><span class="scribble">このタイプへの、贈り方</span></h2><ul class="plain cols2 chips">{links}</ul>
<p class="persona-line">渡すときのひとこと: 「{esc(p["line"])}」</p></section>
<p style="margin-top:34px"><a class="btn big" href="/diagnosis/">ほかの人も診断してみる</a></p>
<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかのタイプ</span></h2><ul class="plain cols2 chips">{others}</ul></section>"""
    return B.page(cfg, preview, path=f"/diagnosis/{p['slug']}/", title=f"{p['name']} プレゼント診断の結果 | {cfg['site_name']}", description=p["about"][:110], body=body,
                  og_image=B.og_for(f"diagnosis/{p['slug']}"))


def tools_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]
    cards = [("/diagnosis/", "あの人はどんなタイプ?", "6つの質問で、贈る相手の「タイプ」と、合う贈り方が分かります。", c["persona"]),
             ("/tool/taboo/", "縁起・マナーチェック", "贈る前に、気をつけたい言い伝えやマナーが、あるかどうか確かめます。", c["taboo"]),
             ("/tool/calc/", "お返し・割り勘の計算", "お返しの金額の目安と、連名で贈るときの一人あたりの金額を計算します。", True),
             ("/memo/", "たいせつな日メモ", "誕生日や記念日を登録して、贈りどきを逃さないようにします。", True),
             ("/calendar/", "贈りどきカレンダー", "母の日、お歳暮など、一年の贈りどきを、カレンダーに入れられます。", True)]
    tiles = "".join(f'<li><a class="tile wide tool-tile" href="{h}"><span><b>{esc(n)}</b><small>{esc(t)}</small></span></a></li>' for h, n, t, ok in cards if ok)
    lead = "プレゼント選びを、もっと楽にして、もっと楽しくするための道具を、そろえています。"
    body = f"""{B.head_band("yellow", '<img class="pair-mini" src="/assets/img/navi-scope.webp" alt="" width="170" height="130">', "診断・ツール", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", None)])}</div>
<section style="margin-top:34px"><ul class="tiles wide">{tiles}</ul></section>"""
    return B.page(cfg, preview, path="/tool/", title=f"診断・ツール | {cfg['site_name']}", description=lead, body=body)
