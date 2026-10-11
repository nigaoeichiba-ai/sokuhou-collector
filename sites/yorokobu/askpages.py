"""The pages of the 「それとなく聞く」アンケート (/ask/, /ask/r/, /ask/mine/) and of the 診断ドック (/dock/), and the data files their scripts read.

  /ask/        a person chooses how to ask (the question is for a present and says so / the question is for a surprise and does not), and gets a link and a QR code
  /ask/r/ and /ask/s/   the page the other person opens (open / secret mode): the questions (options only), sent to api/ask.php.  Each has only its own mode's words;
               the secret one has no site name and no gift word, in its text or its address.
  /ask/mine/   the person's results: the answers added up per question, a reading of them, and products to match (ask/rec.json)
  /dock/       the 診断ドック: the person describes whom they want to give to; the report (grade, a line per item, three kinds to look for, notes) is made in the browser
  ask/rec.json    per interest group: the best products of the site that are of that kind, the price range of all of them, and the Rakuten / Amazon searches
  dock/data.json  per occasion: the price range of its products, its next dates, the survey board if there is one; per interest group: its price range and its risk

The scripts (assets/ask.js, rec.js, dock.js) run in the browser: what a visitor chooses never leaves the device, except the answers of a survey (option ids, to
api/ask.php) and counters (option ids, no link to a person; dock.js).
"""
from __future__ import annotations

import json
from datetime import date

from sites.yorokobu import giftcal, relevance
from sites.yorokobu.askserver import ask_php
from sokuhou.sitekit import crumbs, esc

REC_ITEMS = 12          # products kept per interest group in ask/rec.json
REC_NG = ("おむつ", "ペットボトル", "業務用", "ケース販売", "まとめ買い", "24本", "48本")      # bulk drinks and the like: not gifts
MIN_REC_ITEMS = 3       # a group with fewer products than this is shown with its searches only
MIN_POOL = 8            # fewer products than this in a group (or an occasion): no price range is given for it

# How risky a kind of gift is to get wrong (a share, 0-1): the thing that goes wrong with it is named.  An editors' estimate, shown as such, never as a statistic.
RISK = {
    "coffee_tea": (0.15, "好みの豆・茶葉が分かれる"), "sweets": (0.20, "甘さの好みと、食物アレルギー"), "gourmet": (0.25, "味の好みと、食物アレルギー"),
    "alcohol": (0.30, "飲むかどうかで大きく分かれる"), "bath_care": (0.30, "香りの好みが分かれる"), "beauty": (0.50, "肌に合うか、色や香りの好み"),
    "cozy_home": (0.25, "色と手ざわりの好み"), "kitchen": (0.20, "すでに持っている可能性"), "stationery": (0.20, "筆記具や手帳のこだわり"),
    "fashion_small": (0.35, "色とデザインの好み"), "accessory": (0.50, "デザインとサイズの好み"), "gadget": (0.40, "すでに持っている・機種が合わない"),
    "outdoor": (0.45, "やる人かどうか"), "sports": (0.45, "やる人かどうか、サイズ"), "craft": (0.35, "道具のこだわり"), "plants": (0.30, "世話ができるか、アレルギー"),
    "health_sleep": (0.30, "体質と好み"), "hobby_play": (0.50, "持っているものと重ならないか"),
}
# What each of the eight types of the 診断 tends to like (weights 1-2): an estimate by the editors, shown as such.
TYPE_WEIGHTS = {
    "practical-steady": {"kitchen": 2, "stationery": 1, "fashion_small": 1, "gadget": 1, "cozy_home": 1},
    "modest-caregiver": {"bath_care": 2, "health_sleep": 2, "sweets": 1, "kitchen": 1},
    "conversation-spark": {"gourmet": 2, "coffee_tea": 1, "hobby_play": 1, "accessory": 1},
    "memory-keeper": {"stationery": 2, "accessory": 1, "plants": 1, "sweets": 1},
    "alone-time": {"coffee_tea": 2, "bath_care": 2, "cozy_home": 2, "stationery": 1},
    "taste-curator": {"accessory": 2, "fashion_small": 2, "beauty": 1, "coffee_tea": 1, "plants": 1},
    "new-adventurer": {"outdoor": 2, "gadget": 2, "sports": 1, "hobby_play": 1},
    "food-explorer": {"gourmet": 2, "sweets": 2, "coffee_tea": 1, "alcohol": 1},
}
BANDS = (("b2000", "under3000", 2000), ("b5000", "3000-5000", 5000), ("b10000", "5000-10000", 10000), ("b20000", "10000-20000", 20000), ("bmore", "over20000", None))


def _b():
    from sites.yorokobu import build
    return build


def quartiles(xs: list[int]) -> dict | None:
    from sites.yorokobu import dataroom
    if len(xs) < MIN_POOL:
        return None
    a, m, b = dataroom.quartiles(xs)
    return {"n": len(xs), "p25": round(a), "med": round(m), "p75": round(b)}


def gender_mark(name: str) -> str:
    """'f' for a title made for women, 'm' for one made for men, '' for the rest (unisex titles included)."""
    if any(w in name for w in relevance.UNISEX):
        return ""
    if any(w in name for w in relevance.FOR_WOMEN):
        return "f"
    if any(w in name for w in relevance.FOR_MEN):
        return "m"
    return ""


# ---------------------------------------------------------------- data files

def rec_data(d: dict, cfg: dict) -> dict | None:
    """ask/rec.json: for each interest group, the site's best products of that kind (a title that has one of the group's words), and the price range of all of them."""
    from sites.yorokobu import dataroom, picking
    ask = d["c"].get("ask")
    if not ask:
        return None
    B = _b()
    pool = [i for i in dataroom.all_products(d) if not any(w in i["name"] for w in REC_NG)]
    # a product belongs to one group: the one whose word comes first in its title (a "抹茶 生チョコ" sweet is not also a tea)
    owner: dict[str, str] = {}
    for it in pool:
        best = None
        for n, (gid, spec) in enumerate(ask["interests"].items()):
            pos = relevance.head_position(it["name"], spec["must"])
            if pos is not None and (best is None or (pos, n) < best[:2]):
                best = (pos, n, gid)
        if best:
            owner[it["code"]] = best[2]
    groups = {}
    for gid, spec in ask["interests"].items():
        xs = sorted((i for i in pool if owner.get(i["code"]) == gid), key=lambda i: (-picking.score(i), i["code"]))
        items, shops = [], {}
        for it in xs:
            if shops.get(it["shop_code"], 0) >= 2:
                continue
            shops[it["shop_code"]] = shops.get(it["shop_code"], 0) + 1
            name = B.rakuten.clean_title(it["name"])
            items.append({"n": B.short(name, 60), "p": it["price"], "i": it["image"], "u": B.rakuten_link(cfg, B.rakuten.clean_item_url(it["url"])),
                          "a": B.amazon_url(cfg, B.amazon_query(name)) if cfg.get("amazon_tracking_id") else "", "g": gender_mark(it["name"])})
            if len(items) >= REC_ITEMS:
                break
        groups[gid] = {"label": spec["label"], "kind": spec["kind"], "items": items if len(items) >= MIN_REC_ITEMS else [], "range": quartiles([i["price"] for i in xs]),
                       "q": spec["queries"][0], "r": B.search_link(cfg, spec["queries"][0]),
                       "a": B.amazon_url(cfg, spec["queries"][0]) if cfg.get("amazon_tracking_id") else ""}
    tiers = [t["slug"] for t, _ in B.budget_tiers(d)]
    return {"fresh": d["fetched_label"], "groups": groups, "tiers": tiers, "bands": [[b, t, hi] for b, t, hi in BANDS]}


def dock_data(d: dict, cfg: dict, rec: dict | None, today: date) -> dict | None:
    """dock/data.json: what the report of the 診断ドック quotes (all of it from this build's own numbers)."""
    from sites.yorokobu import dataroom
    c = d["c"]
    ask = c.get("ask")
    if not ask or not c.get("persona"):
        return None
    occs = []
    boards = {b["occasion"]: b for b in (c.get("surveys") or {}).get("boards", []) if b.get("occasion")}
    for o in c["occasions"]:
        xs = [i["price"] for i in dataroom.products_of_occasion(d, o["slug"])]
        nxt = [g["date"].isoformat() for y in (today.year, today.year + 1) for g in giftcal.gift_days(y) if g["slug"] == o["slug"]]
        b = boards.get(o["slug"])
        path = f'/data/{b["slug"]}/' if b else ("/data/mothers-day-budget/" if o["slug"] == "mothers-day" and (c.get("surveys") or {}).get("mothers_day_extra") else "")
        src = b or ((c.get("surveys") or {}).get("mothers_day_extra") if path else None)
        occs.append({"slug": o["slug"], "name": o["name"], "range": quartiles(xs), "dates": nxt, "board": path if path in {r[0] for r in dataroom.results(d)} else "",
                     "facts": [f'{h["label"]}: {h["value"]}' for h in (src or {}).get("headline", [])[:3]] if path else []})
    groups = {gid: {"label": g["label"], "kind": g["kind"], "range": g["range"], "risk": RISK[gid][0], "risk_note": RISK[gid][1]} for gid, g in (rec or {}).get("groups", {}).items()}
    types = [{"slug": p["slug"], "name": p["name"], "tagline": p["tagline"], "w": TYPE_WEIGHTS.get(p["slug"], {})} for p in c["persona"]["personas"]]
    return {"fresh": d["fetched_label"], "occasions": occs, "groups": groups, "types": types, "today": today.isoformat()}


# ---------------------------------------------------------------- pages

def _json(data) -> str:
    return esc(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _public_questions(ask: dict, with_weights: bool, mode: str = "") -> list[dict]:
    """The questions for a page.  With `mode` ("open" or "secret") only that wording goes into the page, so that the page of the secret mode carries no word of the other."""
    out = []
    for q in ask["questions"]:
        item = {"id": q["id"], "key": q["key"], "multi": bool(q.get("multi")), "max": q.get("max") or 1,
                "options": [({"id": o["id"], "label": o["label"], "w": o.get("w") or {}} if with_weights else {"id": o["id"], "label": o["label"]}) for o in q["options"]]}
        if mode:
            item["text"] = q[mode]
        else:
            item["open"], item["secret"] = q["open"], q["secret"]
        out.append(item)
    return out


def ask_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    ask = d["c"]["ask"]
    data = {"q": _public_questions(ask, False), "intro": ask["intro"], "base": cfg["site_url"].rstrip("/")}
    lead = "好みや、ほしいものを、それとなく聞くためのアンケートを作ります。リンクを送るだけ。答えは選ぶだけで、送ったあと、結果とおすすめがここで見られます。"
    qs = "".join(f'<li>{esc(q["open"])}</li>' for q in ask["questions"])
    body = f"""{B.head_band("sky", "", "それとなく、<wbr>ほしいものを聞く", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("ほしいものを聞く", None)])}</div>
<section class="ask-make" id="ask-make" data-json="{_json(data)}">
<h2><span class="scribble">1. どちらで聞きますか</span></h2>
<div class="ask-modes" role="radiogroup" aria-label="聞き方">
<label class="ask-mode"><input type="radio" name="mode" value="o" checked><span><b>プレゼントのために、と伝えて聞く</b><small>「プレゼントを選ぶ参考にしたい」と伝えて、好みを聞きます。相手に頼んで答えてもらう、ふつうの聞き方です。</small></span></label>
<label class="ask-mode"><input type="radio" name="mode" value="s"><span><b>サプライズにしたい。好みの調査として聞く</b><small>贈り物とは書かず、「最近の好み」を聞くアンケートにします。うそは書きません。ただ、リンクのアドレスには、このサイトの名前(present)が見えます。</small></span></label>
</div>
<h2 style="margin-top:28px"><span class="scribble">2. リンクを作る</span></h2>
<p><button type="button" class="btn big" data-make>アンケートのリンクを作る</button></p>
<p class="ask-msg" role="status" aria-live="polite" hidden></p>
<div class="ask-out" hidden>
<p class="ask-lab">相手に送るリンク</p>
<p><input class="ask-link" type="text" readonly aria-label="アンケートのリンク"></p>
<div class="share"><button type="button" class="share-btn copy-link">リンクをコピー</button><a class="share-btn line" target="_blank" rel="noopener" data-line>LINEで送る</a><a class="share-btn mail" data-mail>メールで送る</a><button type="button" class="share-btn native" hidden data-native>共有する</button><button type="button" class="share-btn" data-qr>QRコード</button></div>
<p class="ask-note ask-secret" hidden>サプライズにするときの注意: リンクのアドレスや、LINEで見える表示には、「yorokobu-present.com」と出ます。「present」の文字から、気づかれることがあります。</p>
<p class="ask-lab" style="margin-top:18px">添える一言の例</p>
<p class="ask-say"></p>
<p class="more"><a class="btn" data-mine href="/ask/mine/">回答を見る(結果ページ)</a></p>
<p class="ask-note">回答が届いたら知らせてほしいときは、結果ページで「この端末で通知を受け取る」を押してください。結果ページのアドレスをスマホに送っておくと、スマホでも見られます。</p>
</div>
</section>
<section class="data-notes"><h2>聞く内容(9つ)</h2><ol class="ask-qlist">{qs}</ol><p class="chart-note">どれも、選ぶだけです。答えたくない質問は、とばせます。自由に書く欄はありません。</p></section>
<section class="data-notes"><h2>取り扱い</h2><ul>
<li>聞く相手の名前や連絡先は、入力しません。相手が答えるのは、選択肢のどれを選んだか、だけです。</li>
<li>回答は、作った人が持つ「鍵」を使ったときだけ読めます。鍵は、この端末のブラウザに保存されます。</li>
<li>1つのアンケートに届くのは、40人の回答までです。作ってから120日たつと、回答といっしょに自動で消えます。</li>
<li>くわしくは、<a href="/privacy/#ask">プライバシーポリシー</a>に書いています。</li></ul></section>
<p class="notice" style="margin-top:34px">回答の読み取りと、おすすめの表示は、このページを作った端末のブラウザで行います。</p>"""
    return B.page(cfg, preview, path="/ask/", title=f"それとなく、ほしいものを聞く | {cfg['site_name']}", description=lead, body=body, amazon_links=bool(cfg.get("amazon_tracking_id")),
                  head_extra=f'{B.FONTS}<script src="/assets/ask.js" defer></script>')


def respond_page(d: dict, cfg: dict, mode: str) -> str:
    """The page the other person opens (mode "open": /ask/r/, "secret": /ask/s/).  Its own small page, without the site's header, and with only its own mode's words in it:
    the secret one shows nothing of what it is for, in its text or in its address."""
    ask = d["c"]["ask"]
    data = {"q": _public_questions(ask, False, mode), "intro": ask["intro"][mode]}
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
<title>かんたんなアンケート</title>
<meta name="description" content="選ぶだけの、かんたんなアンケートです。">
<link rel="icon" href="data:,">
<link rel="stylesheet" href="/assets/style.css">
<script src="/assets/ask.js" defer></script>
</head>
<body class="ask-body">
<main class="ask-wrap" id="ask-respond" data-mode="{mode}" data-json="{_json(data)}">
<h1 class="ask-h1">かんたんなアンケート</h1>
<p class="ask-lead" data-lead>読み込んでいます…</p>
<form class="ask-form" hidden></form>
<p class="ask-msg" role="status" aria-live="polite" hidden></p>
<noscript><p class="notice">このアンケートは、JavaScript が使える環境でお使いください。</p></noscript>
<p class="ask-foot"><a href="/privacy/#ask">回答の取り扱いについて</a></p>
</main>
</body>
</html>
"""


def mine_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    ask = d["c"]["ask"]
    data = {"q": _public_questions(ask, True), "interests": {k: v["label"] for k, v in ask["interests"].items()}, "base": cfg["site_url"].rstrip("/"),
            "vapid": cfg.get("vapid_public") or ""}
    lead = "作ったアンケートの回答が、ここに集まります。質問ごとの集計と、回答に合わせたおすすめの商品を見られます。"
    body = f"""{B.head_band("mint", "", "アンケートの結果を見る", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("ほしいものを聞く", "/ask/"), ("結果を見る", None)])}</div>
{B.pr_quiet(cfg)}
<section class="ask-mine" id="ask-mine" data-json="{_json(data)}" data-rec="/ask/rec.json">
<p class="ask-msg" role="status" aria-live="polite">読み込んでいます…</p>
<div class="ask-list"></div>
<div class="ask-detail" hidden></div>
<noscript><p class="notice">このページは、JavaScript が使える環境でお使いください。</p></noscript>
</section>
<section class="data-notes"><h2>見かたの注意</h2><p>回答が少ないうちは、1人の答えが集計を大きく動かします。参考として見てください。表示する商品は、当サイトで取り上げている楽天市場の商品です(価格・在庫は取得した時点のもので、{esc(d["fetched_label"])}時点)。</p></section>
<p class="more"><a class="btn btn-sub" href="/ask/">新しいアンケートを作る</a></p>"""
    html = B.page(cfg, preview, path="/ask/mine/", title=f"アンケートの結果 | {cfg['site_name']}", description=lead, body=body, amazon_links=bool(cfg.get("amazon_tracking_id")),
                  head_extra=f'{B.FONTS}<script src="/assets/rec.js" defer></script><script src="/assets/ask.js" defer></script>')
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow">', 1)


def dock_page(d: dict, cfg: dict, preview: bool, data: dict) -> str:
    B = _b()
    c = d["c"]
    occ = "".join(f'<option value="{esc(o["slug"])}">{esc(o["name"])}</option>' for o in c["occasions"])
    types = "".join(f'<label class="chk"><input type="checkbox" name="type" value="{esc(t["slug"])}"> {esc(t["name"])}<small>{esc(t["tagline"])}</small></label>' for t in data["types"])
    ints = "".join(f'<label class="chk"><input type="checkbox" name="int" value="{esc(k)}"> {esc(g["label"])}</label>' for k, g in data["groups"].items())
    lead = "贈りたい相手のことを、わかる範囲で入力してください。健康診断の結果票のように、項目ごとの数値と評価、総合評価、おすすめの種類と理由を、お返しします。"
    avoid = "".join(f'<label class="chk"><input type="checkbox" name="avoid" value="{k}"> {lab}</label>' for k, lab in
                    (("scent", "香りが強いもの"), ("sweet", "甘いもの"), ("alcohol", "お酒"), ("allergy", "食物アレルギーがある"), ("bulky", "場所をとるもの"), ("flashy", "派手なデザイン")))
    body = f"""{B.head_band("pink", "", "贈り物ドック", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("診断・ツール", "/tool/"), ("贈り物ドック", None)])}</div>
{B.pr_quiet(cfg)}
<section class="dock" id="dock" data-src="/dock/data.json" data-rec="/ask/rec.json">
<form class="dock-form" onsubmit="return false">
<fieldset><legend>1. 贈る場面</legend>
<label>贈る目的<select name="occ"><option value="">特に決まっていない</option>{occ}</select></label>
<label>渡したい日(わかれば)<input type="date" name="date"></label></fieldset>
<fieldset><legend>2. 相手について</legend>
<label>性別<select name="gender"><option value="">答えない・どちらでもない</option><option value="f">女性</option><option value="m">男性</option></select></label>
<label>年代(おおよそ)<select name="age"><option value="">わからない</option><option value="u20">10代以下</option><option value="20s">20代</option><option value="30s">30代</option><option value="40s">40代</option><option value="50s">50代</option><option value="60s">60代</option><option value="70s">70代以上</option></select></label>
<div class="dock-group"><b>性格・雰囲気に近いもの(2つまで)</b><div class="dock-checks">{types}</div></div></fieldset>
<fieldset><legend>3. 好み</legend>
<div class="dock-group"><b>興味があるもの(5つまで)</b><div class="dock-checks">{ints}</div></div>
<div class="dock-group"><b>苦手・避けたいもの</b><div class="dock-checks">{avoid}</div></div></fieldset>
<fieldset><legend>4. 予算と、そのほか</legend>
<label>予算(円)<input type="number" name="budget" min="500" max="500000" step="100" inputmode="numeric" placeholder="例: 5000"></label>
<label>そのほか、気になること(この端末の中だけで使い、結果票に写します)<input type="text" name="memo" maxlength="80" placeholder="例: 引っ越したばかり"></label></fieldset>
<p><label class="chk dock-count"><input type="checkbox" name="count" checked> 選んだ項目を、回数だけ数えて、サイトの改善に使ってもよい(だれの回答か分かりません。入力した文字や日付は、送りません。外すこともできます)</label></p>
<p><button type="submit" class="btn big">診断する</button></p>
</form>
<div class="dock-report" hidden></div>
<noscript><p class="notice">この診断は、JavaScript を使います。</p></noscript>
</section>
<section class="data-notes"><h2>診断のしくみ</h2><p>点数は、次の5項目の加重平均です。予算(25%)・時期(20%)・相手についての情報量(20%)・好みの手がかり(20%)・外しにくさ(15%)。予算は、当サイトの商品の価格や、調査の数字と比べます。「外しにくさ」と、性格タイプの好みは、編集部の目安で、統計ではありません。入力は、この端末の中で計算し、サーバーへは送りません。サイトの改善のために、選んだ項目の「回数だけ」を、だれの回答か分からない形で数えています(結果票の下に説明があります)。</p></section>"""
    return B.page(cfg, preview, path="/dock/", title=f"贈り物ドック 相手のことを入力して、おすすめを診断 | {cfg['site_name']}", description=lead[:110], body=body,
                  amazon_links=bool(cfg.get("amazon_tracking_id")), head_extra=f'{B.FONTS}<script src="/assets/rec.js" defer></script><script src="/assets/dock.js" defer></script>')


def build_files(d: dict, cfg: dict, preview: bool, today: date) -> tuple[dict, dict]:
    """(pages that are found by searching, pages that are not: the other person's page and the results) as {path: content}; the data files and api/ask.php are in the first."""
    if not d["c"].get("ask"):
        return {}, {}
    rec = rec_data(d, cfg)
    pages: dict[str, str] = {"ask/index.html": ask_page(d, cfg, preview), "api/ask.php": ask_php(cfg, d["c"]["ask"])}
    quiet: dict[str, str] = {"ask/r/index.html": respond_page(d, cfg, "open"), "ask/s/index.html": respond_page(d, cfg, "secret"), "ask/mine/index.html": mine_page(d, cfg, preview)}
    if rec:
        pages["ask/rec.json"] = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        dd = dock_data(d, cfg, rec, today)
        if dd:
            pages["dock/index.html"] = dock_page(d, cfg, preview, dd)
            pages["dock/data.json"] = json.dumps(dd, ensure_ascii=False, separators=(",", ":"))
    return pages, quiet


ASK_PRIVACY = (
    '<h2 id="ask">アンケート機能(ほしいものを聞く・贈り物ドック)</h2>'
    '<p>「ほしいものを聞く」では、アンケートを作った人のブラウザで作った、アンケートの番号と、結果を読むための鍵を使います。鍵は、作った人のブラウザにだけ保存されます。サーバーには、鍵を一方向に変換した値だけが残り、鍵そのものは残りません。</p>'
    '<p>回答する人が送るのは、選んだ選択肢の番号と、送信した日時だけです。名前・連絡先・自由に書く欄は、ありません。回答は、鍵を持つ人(アンケートを作った人)だけが読めます。アンケートと回答は、作ってから120日たつと消えます(消去は、新しいアンケートが作られるときに行うため、少し遅れることがあります)。作った人は、結果ページから、いつでも消せます。</p>'
    '<p>回答が届いたときの通知は、結果ページで「この端末で通知を受け取る」を押したときだけ使います。このとき、ブラウザが作った通知の宛先(購読情報)と、アンケートの番号を、サーバーに保存します。通知には、回答の内容を含みません。通知を止める、または、アンケートを消すと、削除します。通知の送信は、GitHub Actions(GitHub, Inc.)の送信プログラムが、サーバーの購読情報を読んで行います。</p>'
    '<p>不正な大量送信を防ぐため、送信元のアドレスから作った、その日だけ有効な値(アドレスそのものではありません)を、一時的に保存します。</p>'
    '<p>「贈り物ドック」に入力した内容は、お使いの端末の中だけで計算し、送りません。結果の前のチェックボックスにチェックがあるときだけ、選んだ項目の名前(たとえば「興味: コーヒー・お茶」)ごとの回数を、だれのものか分からない形で数えます。入力した文字、メモ、日付は、送りません。数えた回数は、質問や診断の改善に使い、匿名の集計として、データ室に載せることがあります。</p>'
)
