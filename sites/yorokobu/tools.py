"""The extra angles of よろこぶプレゼント: gift map, etiquette checker, calculators, "who is this person?" quiz and its result pages.

Everything here is data-driven (content/taboo.json, persona.json, map_tags.json) and works without scripts where it can; the quiz and the
calculators need a little JavaScript (assets/app.js).  Page helpers come from build.py, imported when a function runs (build imports this module).
"""
from __future__ import annotations

import json

from sites.yorokobu import icons
from sokuhou.sitekit import crumbs, esc

LEVELS = {"care": ("気にする人が多い", "care"), "note": ("覚えておくと安心", "note"), "ok": ("たいていは大丈夫", "ok")}
DOT_COLORS = ["#e8503f", "#4c8fa8", "#6e9b52", "#e2a93b"]


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
    return ('<section class="gmap"><div class="sec-title"><span class="tag">タイプ別マップ</span><h2>この提案は、どんなタイプ?</h2></div>'
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
    body = f"""{B.head_band("sky", '', "贈る前に、縁起・マナーチェック", lead, single=True, mascot="b-wink")}
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
    body = f"""{B.head_band("yellow", '', "お返し・割り勘の計算", lead, single=True, mascot="r-wink")}
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


# ---------------------------------------------------------------- おまかせガチャ: one product at random for a recipient and a budget

GACHA_PER_COMBO = 12


def gacha_pool(d: dict) -> dict:
    """{recipient slug: {"name", "tiers": {tier slug: [[name, price, image, item url, reviews, rating x10], ...]}}} from the products already on the pages;
    only recipient/budget combinations with products are kept, best-scored first, each product once per combination."""
    B = _b()
    c = d["c"]
    B.set_keep()
    out: dict = {}
    for r in c["recipients"]:
        union: list[dict] = []
        seen: set[str] = set()
        for p in c["pairs"]:
            if p["recipient"] != r["slug"]:
                continue
            for it in B.pair_items(d, B.ct.pair_key(p))[2]:
                if it["code"] not in seen and it.get("available", True):
                    seen.add(it["code"])
                    union.append(it)
        union.sort(key=lambda i: -B.score(i))
        tiers = {}
        for t in c["filters"]["tiers"]:
            rows = [[B.short(i["name"], 44), i["price"], i["image"], B.rakuten.clean_item_url(i["url"]), i["reviews"], int(round(i["rating"] * 10))]
                    for i in union if B.in_tier(i["price"], t)][:GACHA_PER_COMBO]
            if rows:
                tiers[t["slug"]] = rows
        if tiers:
            out[r["slug"]] = {"name": r["name"], "tiers": tiers}
    return out


def gacha_data(d: dict, cfg: dict) -> str | None:
    pool = gacha_pool(d)
    if len(pool) < 2:
        return None
    c = d["c"]
    tiers = [{"slug": t["slug"], "label": t["label"]} for t in c["filters"]["tiers"] if any(t["slug"] in v["tiers"] for v in pool.values())]
    return json.dumps({"rec": pool, "tiers": tiers}, ensure_ascii=False, separators=(",", ":"))


def gacha_page(d: dict, cfg: dict, preview: bool, pool: dict, tiers: list[dict]) -> str:
    B = _b()
    lead = "贈る相手と予算を選んでボタンを押すと、条件に合う商品を1点、提案します。迷ったときのきっかけにしてください。"
    rec = "".join(f'<option value="{esc(s)}">{esc(v["name"])}</option>' for s, v in pool.items())
    bud = "".join(f'<option value="{esc(t["slug"])}">{esc(t["label"])}</option>' for t in tiers)
    body = f"""{B.head_band("sky", '', "おまかせで、<wbr>1点提案します", lead, single=True, mascot="b-joy")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("おまかせ提案", None)])}</div>
{B.pr_quiet(cfg)}
<section id="gacha" class="gacha" data-src="/tool/gacha/items.json" data-aff="{esc(cfg["rakuten_affiliate_id"])}" data-trk="{esc(cfg.get("rakuten_tracking_id") or "")}">
<form class="gacha-form" onsubmit="return false"><label>贈る相手<select name="r">{rec}</select></label>
<label>予算<select name="t">{bud}</select></label>
<button type="submit" class="btn big">1点、提案してもらう</button></form>
<p class="gacha-msg" role="status" aria-live="polite"></p>
<div class="gacha-out" aria-live="polite"></div>
<noscript><p class="notice">このページは、JavaScript が使える環境でお使いください。使えない場合は、<a href="/for/">相手から探す</a>ページでも、おすすめを探せます。</p></noscript>
</section>
<p class="notice">表示される商品は、このサイトで紹介している商品から、ランダムに選んでいます。価格・在庫・レビューは、取得した時点の情報です。</p>
{B.freshness(d)}"""
    return B.page(cfg, preview, path="/tool/gacha/", title=f"おまかせ提案 | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- quiz and persona pages

def quiz_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]["persona"]
    data = esc(json.dumps({"questions": c["questions"], "slugs": [p["slug"] for p in c["personas"]]}, ensure_ascii=False, separators=(",", ":")))
    people = "".join(f'<li><a href="/diagnosis/{p["slug"]}/">{esc(p["name"])}</a></li>' for p in c["personas"])
    lead = "あの人のことを思い出しながら、6つの質問に答えてください。贈り物のヒントになる「タイプ」が分かります。"
    body = f"""{B.head_band("lilac", '', "あの人は、どんなタイプ?", lead, single=True, mascot="r-sparkle")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("プレゼント診断", None)])}</div>
<section class="quiz" id="quiz" data-json="{data}"><noscript><p class="notice">この診断は、JavaScriptを使います。下の一覧から、タイプを見てみてください。</p></noscript>
<div class="quiz-card" hidden><p class="quiz-step"></p><h2 class="quiz-q"></h2><div class="quiz-opts"></div></div>
<p class="quiz-start"><button type="button" class="btn big" data-start>診断をはじめる</button></p></section>
<section style="margin-top:44px"><h2><span class="scribble">8つのタイプ</span></h2><ul class="plain cols2 chips">{people}</ul></section>"""
    return B.page(cfg, preview, path="/diagnosis/", title=f"あの人はどんなタイプ? プレゼント診断 | {cfg['site_name']}", description=lead, body=body)


def persona_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    B = _b()
    c = d["c"]
    live = {t["slug"] for t in d["live_themes"]}
    themes = [c["theme"][s] for s in p["themes"] if s in live]
    links = "".join(f'<li><a href="/theme/{t["slug"]}/">{esc(t["title"])}</a></li>' for t in themes)
    others = "".join(f'<li><a href="/diagnosis/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in c["persona"]["personas"] if x["slug"] != p["slug"])
    body = f"""{B.head_band("pink", '', esc(p["name"]), p["tagline"], single=True, mascot="b-joy")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("プレゼント診断", "/diagnosis/"), (p["name"], None)])}</div>
{B.share_bar(cfg, f"/diagnosis/{p['slug']}/", f"うちのあの人は『{p['name']}』だった! あなたの周りの人は?", "この結果を、だれかに送る")}
<section style="margin-top:30px"><p class="persona-about">{esc(p["about"])}</p></section>
<section class="cols"><div><h2><span class="scribble">よろこびやすいもの</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["likes"])}</ol></div>
<div class="avoid"><h2><span class="scribble">ちょっと外しやすいもの</span></h2>{B.ul(p["avoid"], "warn")}</div></section>
<section style="margin-top:34px"><h2><span class="scribble">このタイプへの、贈り方</span></h2>{f'<ul class="plain cols2 chips">{links}</ul>' if links else ""}
<p class="persona-line">渡すときのひとこと: 「{esc(p["line"])}」</p></section>
<p style="margin-top:34px"><a class="btn big" href="/diagnosis/">ほかの人も診断してみる</a></p>
<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかのタイプ</span></h2><ul class="plain cols2 chips">{others}</ul></section>"""
    return B.page(cfg, preview, path=f"/diagnosis/{p['slug']}/", title=f"{p['name']} プレゼント診断の結果 | {cfg['site_name']}", description=p["about"][:110], body=body,
                  og_image=B.og_for(f"diagnosis/{p['slug']}"))


def tools_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]
    cards = [("/diagnosis/", "sparkle", "あの人はどんなタイプ?", "6つの質問に答えると、贈る相手の「タイプ」と合う贈り方が分かります。", c["persona"]),
             ("/tool/taboo/", "shield-check", "縁起・マナーチェック", "贈る前に、気をつけたい言い伝えやマナーが、あるかどうか確かめます。", c["taboo"]),
             ("/tool/gacha/", "dice-five", "おまかせ提案", "贈る相手と予算を選ぶと、条件に合う商品を1点、提案します。", d.get("gacha")),
             ("/tool/calc/", "currency-jpy", "お返し・割り勘の計算", "お返しの金額の目安と、連名で贈るときの一人あたりの金額を計算します。", True),
             ("/memo/", "calendar-heart", "たいせつな日メモ", "誕生日や記念日を登録して、贈りどきを逃さないようにします。", True),
             ("/calendar/", "calendar-check", "贈りどきカレンダー", "母の日、お歳暮など、一年の贈りどきをカレンダーに入れられます。", True)]
    tiles = "".join(f'<li><a class="tile wide tool-tile" href="{h}"><span class="ic-wrap">{icons.glyph(g, 30)}</span><span><b>{esc(n)}</b><small>{esc(t)}</small></span></a></li>'
                    for h, g, n, t, ok in cards if ok)
    lead = "プレゼント選びを楽にして、楽しくするための道具をそろえています。"
    body = f"""{B.head_band("yellow", '', "診断・ツール", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", None)])}</div>
<section style="margin-top:34px"><ul class="tiles wide">{tiles}</ul></section>"""
    return B.page(cfg, preview, path="/tool/", title=f"診断・ツール | {cfg['site_name']}", description=lead, body=body)
