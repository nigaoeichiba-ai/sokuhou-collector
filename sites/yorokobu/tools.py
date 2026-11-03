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

    parts = [f'<svg class="gmap-svg" viewBox="0 0 {w} {h}" role="img" aria-label="この{len(shown)}つの提案を消えもの・残るもの、定番・個性的の二つの軸に置いた図">',
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
    return ('<section class="gmap"><div class="sec-title"><span class="tag">タイプ別マップ</span><h2>この提案はどんなタイプ？</h2></div>'
            '<p class="sec-lead">横は「食べて消える」から「ずっと残る」まで、縦は「定番・無難」から「個性的・意外」まで。番号をおすと提案に移動します。</p>'
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
    lead = "贈ろうと思っている品を入れると昔からの言い伝えやマナー上の注意が、あるかどうか分かります。気にしすぎなくてよいものもお伝えします。"
    body = f"""{B.head_band("sky", '', "贈る前に縁起・マナーチェック", lead, single=True, mascot="b-wink")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("縁起・マナーチェック", None)])}</div>
<section class="tbcheck" id="tbcheck"><div class="tb-form"><label>贈ろうと思っている品<input type="search" name="q" placeholder="例: くし、ハンカチ、靴、お茶" autocomplete="off"></label>
<label>贈る場面<select name="o"><option value="">指定しない</option>{opts}</select></label></div>
<p class="tb-msg" role="status" aria-live="polite">下のリストから品の名前でしぼりこめます。</p>
<ul class="tb-list">{"".join(cards)}</ul></section>
<p class="notice">ここに書いているのは一般に知られているマナーや言い伝えの目安です。地域や家庭によって考え方はさまざまなので、迷ったときは、年長の方や相手の事情にあわせてください。</p>"""
    return B.page(cfg, preview, path="/tool/taboo/", title=f"贈る前の縁起・マナーチェック | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- calculators

def calc_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    lead = "いただいたお祝いへのお返しの目安とみんなで贈るときの一人あたりの金額をすぐに計算できます。"
    body = f"""{B.head_band("yellow", '', "お返し・割り勘の計算", lead, single=True, mascot="r-wink")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("お返し・割り勘の計算", None)])}</div>
<div class="cols calc-cols" id="calc">
<section class="calc-card" data-calc="return"><h2><span class="scribble">お返しの目安</span></h2>
<label>いただいた金額・品物の金額(円)<input type="number" name="amount" min="0" step="500" value="10000" inputmode="numeric"></label>
<p class="calc-out" aria-live="polite"><b data-out="range"></b><small>一般にいただいた額の3分の1から半分ほどをお返しの目安にします。</small></p>
<p class="calc-links"><a href="/occasion/">イベントからお返しの贈り物を探す</a></p></section>
<section class="calc-card" data-calc="split"><h2><span class="scribble">みんなで贈る(連名)</span></h2>
<label>全体の予算(円)<input type="number" name="total" min="0" step="1000" value="15000" inputmode="numeric"></label>
<label>人数<input type="number" name="people" min="1" step="1" value="5" inputmode="numeric"></label>
<p class="calc-out" aria-live="polite"><b data-out="each"></b><small data-out="note"></small></p></section></div>
<p class="notice">お返しの金額は地域や関係によって考え方が違います。ここではよく言われる目安だけを計算しています。</p>"""
    return B.page(cfg, preview, path="/tool/calc/", title=f"お返し・割り勘の計算 | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- おまかせガチャ: one product at random for a recipient and a budget

GACHA_PER_COMBO = 12


def gacha_pool(d: dict, cfg: dict) -> dict:
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
            rows = [[B.blurb_line(i), i["price"], i["image"], B.item_href(cfg, i), i["reviews"], int(round(i["rating"] * 10))]
                    for i in union if B.in_tier(i["price"], t)][:GACHA_PER_COMBO]
            if rows:
                tiers[t["slug"]] = rows
        if tiers:
            out[r["slug"]] = {"name": r["name"], "tiers": tiers}
    return out


GACHA_PER_IDEA = 3        # products kept per idea and budget band, best first: the API picks one of them at random


def gacha_pairs(d: dict, cfg: dict) -> dict:
    """The private part of the three-product gacha: {pair key: {"tiers": {tier slug: [[idea no., kind no., one line, price, picture, link, reviews, rating x10], ...]}}} for the
    products already on the pairs' pages (occasion x recipient), per idea (kind of gift) and budget band.  The API (`?pk=&t=`) picks one row of three different ideas.
    Shop data: it goes to the private store only (yorokobu_gacha_db.json), never to a public file."""
    B = _b()
    c = d["c"]
    out: dict = {}
    for p in c["pairs"]:
        key = B.ct.pair_key(p)
        ideas = B.pair_items(d, key)[0]
        tiers: dict = {}
        for t in c["filters"]["tiers"]:
            rows = []
            for n, idea in enumerate(ideas):
                kind = B.TYPE_ORDER.index(idea["type"]) if idea["type"] in B.TYPE_ORDER else -1
                if kind < 0:
                    continue
                cand = [it for it in idea["items"] if it.get("available", True) and B.in_tier(it["price"], t) and not B.relevance.foreign_kind(it["name"], idea.get("must"))]
                cand.sort(key=lambda i: -B.score(i))
                for it in cand[:GACHA_PER_IDEA]:
                    rows.append([n, kind, B.blurb_line(it, must=idea.get("must")), it["price"], it["image"], B.item_href(cfg, it), it["reviews"], int(round(it["rating"] * 10))])
            if rows:
                tiers[t["slug"]] = rows
        if len({r[0] for rows in tiers.values() for r in rows}) >= 2:         # three different kinds need at least two ideas with something to show (the API fills a thin band from the nearest ones)
            out[key] = {"tiers": tiers}
    return out


def gacha_public(d: dict, pairs: dict) -> dict:
    """The public part: only the editors' own words (labels, reasons, search words) and names, for the pairs that have products: no product, price or link."""
    B = _b()
    c = d["c"]
    pub: dict = {"pairs": {}, "occ": {}, "rec": {}}
    for p in c["pairs"]:
        key = B.ct.pair_key(p)
        if key not in pairs:
            continue
        ideas = B.pair_items(d, key)[0]
        pub["pairs"][key] = {"o": p["occasion"], "r": p["recipient"], "i": [[i["label"], B.TYPE_ORDER.index(i["type"]) if i["type"] in B.TYPE_ORDER else -1, i["why"], i["query"], [w for w in (i.get("must") or []) if len(w) >= 2][:12]] for i in ideas]}
        pub["occ"][p["occasion"]] = c["occ"][p["occasion"]]["name"]
        pub["rec"][p["recipient"]] = c["rec"][p["recipient"]]["name"]
    used = {t for v in pairs.values() for t in v["tiers"]}
    pub["tiers"] = [{"slug": t["slug"], "label": t["label"]} for t in c["filters"]["tiers"] if t["slug"] in used]
    pub["types"] = list(B.TYPE_ORDER)
    return pub


def gacha_data(d: dict, cfg: dict) -> str | None:
    pool = gacha_pool(d, cfg)
    if len(pool) < 2:
        return None
    c = d["c"]
    tiers = [{"slug": t["slug"], "label": t["label"]} for t in c["filters"]["tiers"] if any(t["slug"] in v["tiers"] for v in pool.values())]
    return json.dumps({"rec": pool, "tiers": tiers, "order": [t["slug"] for t in c["filters"]["tiers"]], "pair": gacha_pairs(d, cfg)}, ensure_ascii=False, separators=(",", ":"))


def gacha_page(d: dict, cfg: dict, preview: bool, gp: dict) -> str:
    B = _b()
    pub = gacha_public(d, gp.get("pair") or {})
    lead = "贈る相手・場面・予算を選んでボタンを押すと、種類の違う商品を3点、理由つきで提案します。迷ったときのきっかけにしてください。"
    rec = "".join(f'<option value="{esc(s)}">{esc(n)}</option>' for s, n in pub["rec"].items())
    bud = "".join(f'<option value="{esc(t["slug"])}">{esc(t["label"])}</option>' for t in pub["tiers"])
    kinds = "".join(f'<option value="{n}">{esc(k)}</option>' for n, k in enumerate(pub["types"]))
    avoid = "".join(f'<label class="gacha-chk"><input type="checkbox" name="exc" value="{n}"> {esc(k)}</label>' for n, k in enumerate(pub["types"]))
    data = json.dumps(pub, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = f"""{B.head_band("sky", '', "条件を選んで<wbr>3点提案します", lead, single=True, mascot="b-joy")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("おまかせ提案", None)])}</div>
{B.pr_quiet(cfg)}
<section id="gacha" class="gacha" data-src="/api/items.php" data-aff="{esc(cfg["rakuten_affiliate_id"])}" data-amazon="{esc(cfg.get("amazon_tracking_id") or "")}">
<form class="gacha-form" onsubmit="return false"><label>贈る相手<select name="r">{rec}</select></label>
<label>場面<select name="o"></select></label>
<label>予算<select name="t">{bud}</select></label>
<label>好み・用途(任意)<input type="text" name="l" maxlength="40" autocomplete="off" placeholder="例: コーヒーが好き、出張が多い"></label>
<label>入れたい種類<select name="k"><option value="">指定しない</option>{kinds}</select></label>
<details class="gacha-avoid"><summary>避けたい種類</summary><div>{avoid}</div></details>
<button type="submit" class="btn big">3点、提案してもらう</button></form>
<p class="gacha-msg" role="status" aria-live="polite"></p>
<div class="gacha-out" aria-live="polite"></div>
<div class="gacha-amazon" aria-live="polite"></div>
<script type="application/json" id="gacha-pub">{data}</script>
<noscript><p class="notice">このページはJavaScript が使える環境でお使いください。使えない場合は、<a href="/for/">相手から探す</a>ページでも、おすすめを探せます。</p></noscript>
</section>
<p class="notice">好み・用途に書いた言葉は、この端末の中で種類の名前や商品の呼び名と照らすだけで、サイトには送りません。合う種類があれば、その種類を先に選びます。</p>
<p class="notice">選ぶ基準: 当サイトが取り上げた楽天市場の商品のうち、選んだ相手と場面のページにあり、予算の帯に入る商品から、種類(案)が重ならないように3点をランダムに選びます。理由の文は、その種類の案について当サイトが書いたものです。商品を使った感想ではありません。価格・在庫・レビューは取得した時点の情報です。</p>
{B.freshness(d)}"""
    return B.page(cfg, preview, path="/tool/gacha/", title=f"おまかせ提案 | {cfg['site_name']}", description=lead, body=body)


# ---------------------------------------------------------------- quiz and persona pages

def quiz_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]["persona"]
    data = esc(json.dumps({"questions": c["questions"], "slugs": [p["slug"] for p in c["personas"]]}, ensure_ascii=False, separators=(",", ":")))
    people = "".join(f'<li><a href="/diagnosis/{p["slug"]}/">{esc(p["name"])}</a></li>' for p in c["personas"])
    lead = "あの人のことを思い出しながら、6つの質問に答えてください。贈り物のヒントになる「タイプ」が分かります。"
    body = f"""{B.head_band("lilac", '', "あの人はどんなタイプ？", lead, single=True, mascot="r-sparkle")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("プレゼント診断", None)])}</div>
<section class="quiz" id="quiz" data-json="{data}"><noscript><p class="notice">この診断はJavaScriptを使います。下の一覧からタイプを見てみてください。</p></noscript>
<div class="quiz-card" hidden><p class="quiz-step"></p><h2 class="quiz-q"></h2><div class="quiz-opts"></div></div>
<p class="quiz-start"><button type="button" class="btn big" data-start>診断をはじめる</button></p></section>
<section style="margin-top:44px"><h2><span class="scribble">8つのタイプ</span></h2><ul class="plain cols2 chips">{people}</ul></section>"""
    return B.page(cfg, preview, path="/diagnosis/", title=f"あの人はどんなタイプ？ プレゼント診断 | {cfg['site_name']}", description=lead, body=body)


def result_row(cfg: dict, p: dict) -> str:
    """Under the share buttons of a result: the result as a picture (to keep, or to hand to the phone's share sheet where it can take a file)."""
    B = _b()
    base = cfg["site_url"].rstrip("/")
    img = f"/diagnosis/img/{p['slug']}.png"
    text = f"うちのあの人は『{p['name']}』だった!"
    return (f'<div class="chart-send"><span>この結果を画像で</span><a class="share-btn save" href="{img}" download="yorokobu-{esc(p["slug"])}.png">画像で保存</a>'
            f'<button type="button" class="share-btn native" hidden data-img="{img}" data-url="{esc(base)}/diagnosis/{esc(p["slug"])}/" data-text="{esc(text)}" data-name="yorokobu-{esc(p["slug"])}.png">画像を送る</button></div>')


def persona_page(d: dict, cfg: dict, preview: bool, p: dict) -> str:
    B = _b()
    c = d["c"]
    live = {t["slug"] for t in d["live_themes"]}
    themes = [c["theme"][s] for s in p["themes"] if s in live]
    links = "".join(f'<li><a href="/theme/{t["slug"]}/">{esc(t["title"])}</a></li>' for t in themes)
    others = "".join(f'<li><a href="/diagnosis/{x["slug"]}/">{esc(x["name"])}</a></li>' for x in c["persona"]["personas"] if x["slug"] != p["slug"])
    body = f"""{B.head_band("pink", '', esc(p["name"]), p["tagline"], single=True, mascot="b-joy")}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("プレゼント診断", "/diagnosis/"), (p["name"], None)])}</div>
{B.share_bar(cfg, f"/diagnosis/{p['slug']}/", f"うちのあの人は『{p['name']}』だった! あなたの周りの人は？", "この結果をだれかに送る")}
{result_row(cfg, p)}
<section style="margin-top:30px"><p class="persona-about">{esc(p["about"])}</p></section>
<section class="cols"><div><h2><span class="scribble">よろこびやすいもの</span></h2><ol class="panel-grid one">{"".join(f"<li>{esc(x)}</li>" for x in p["likes"])}</ol></div>
<div class="avoid"><h2><span class="scribble">ちょっと外しやすいもの</span></h2>{B.ul(p["avoid"], "warn")}</div></section>
<section style="margin-top:34px"><h2><span class="scribble">このタイプへの贈り方</span></h2>{f'<ul class="plain cols2 chips">{links}</ul>' if links else ""}
<p class="persona-line">渡すときのひとこと: 「{esc(p["line"])}」</p></section>
<p style="margin-top:34px"><a class="btn big" href="/diagnosis/">ほかの人も診断してみる</a></p>
<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかのタイプ</span></h2><ul class="plain cols2 chips">{others}</ul></section>"""
    return B.page(cfg, preview, path=f"/diagnosis/{p['slug']}/", title=f"{p['name']} プレゼント診断の結果 | {cfg['site_name']}", description=p["about"][:110], body=body,
                  og_image=B.og_for(f"diagnosis/{p['slug']}"))


def tools_hub_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    c = d["c"]
    cards = [("/diagnosis/", "sparkle", "あの人はどんなタイプ？", "6つの質問に答えると贈る相手の「タイプ」と合う贈り方が分かります。", c["persona"]),
             ("/tool/taboo/", "shield-check", "縁起・マナーチェック", "贈る前に気をつけたい言い伝えやマナーが、あるかどうか確かめます。", c["taboo"]),
             ("/dock/", "list-checks", "贈り物ドック", "相手のことを入力すると健康診断の結果票のように項目ごとの点数と評価、おすすめの種類を返します。", c.get("ask")),
             ("/ask/", "chat-circle-text", "ほしいものを聞く", "好みやほしいものをそれとなく聞くアンケートを作ってリンクで送ります。結果とおすすめも見られます。", c.get("ask")),
             ("/tool/gacha/", "dice-five", "おまかせ提案", "贈る相手・場面・予算を選ぶと、種類の違う商品を3点、理由つきで提案します。", d.get("gacha")),
             ("/compare/", "chart-bar", "商品比較", "同じ種類の商品を楽天市場のショップで並べて価格・ポイント・送料・レビューを比べます。", d.get("compare")),
             ("/tool/calc/", "currency-jpy", "お返し・割り勘の計算", "お返しの金額の目安と連名で贈るときの一人あたりの金額を計算します。", True),
             ("/memo/", "calendar-heart", "たいせつな日メモ", "誕生日や記念日を登録して贈りどきを逃さないようにします。", True),
             ("/calendar/", "calendar-check", "贈りどきカレンダー", "母の日、お歳暮など、一年の贈りどきをカレンダーに入れられます。", True)]
    tiles = "".join(f'<li><a class="tile wide tool-tile" href="{h}"><span class="ic-wrap">{icons.glyph(g, 30)}</span><span><b>{esc(n)}</b><small>{esc(t)}</small></span></a></li>'
                    for h, g, n, t, ok in cards if ok)
    lead = "プレゼント選びを楽にして楽しくするための道具をそろえています。"
    body = f"""{B.head_band("yellow", '', "診断・ツール", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", None)])}</div>
<section style="margin-top:34px"><ul class="tiles wide">{tiles}</ul></section>"""
    return B.page(cfg, preview, path="/tool/", title=f"診断・ツール | {cfg['site_name']}", description=lead, body=body)
