"""/favorites/ (お気に入り and 最近チェックした商品, drawn in the browser from what this browser kept: assets/mine.js) and the block 「当サイトで、よく押されている商品」.

The block is made from the counters of the pressed shop buttons (api/ask.php op "stat", keys pop.r.<rakuten item code> / pop.a.<ASIN>, merged into
data/yorokobu_ask_stats.json by the daily workflow).  It is shown only when there is enough behind it: a few presses are one person's curiosity, not a ranking.
Nothing in the counters says who pressed; the page says what the number is (presses of the shop button, not purchases).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sokuhou.sitekit import crumbs, esc

ROOT = Path(__file__).resolve().parents[2]
STATS_FILE = ROOT / "data" / "yorokobu_ask_stats.json"
MIN_TOTAL = 60        # presses behind the block, all products together
MIN_EACH = 3          # presses of a product for it to be listed
MIN_PRODUCTS = 4      # products that reach MIN_EACH
SHOWN = 8
POP = re.compile(r"^pop\.r\.(.+)$")


def _b():
    from sites.yorokobu import build
    return build


def load_stats(path: Path | None = None) -> dict:
    try:
        d = json.loads((path or STATS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def ranking(stats: dict, products: dict[str, dict]) -> list[dict]:
    """The products (of those still on the site, `products`: item code -> product) by presses; [] when there is not enough behind the numbers."""
    total = stats.get("total", {}) if isinstance(stats, dict) else {}
    counts = {}
    for k, v in total.items():
        m = POP.match(str(k))
        if m and isinstance(v, int) and v > 0:
            counts[m.group(1)] = v
    if sum(counts.values()) < MIN_TOTAL or sum(1 for v in counts.values() if v >= MIN_EACH) < MIN_PRODUCTS:
        return []
    rows = [(v, products[c]) for c, v in counts.items() if v >= MIN_EACH and c in products]
    rows.sort(key=lambda r: (-r[0], r[1]["code"]))
    return [p for _, p in rows[:SHOWN]] if len(rows) >= MIN_PRODUCTS else []


def products_of(d: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key in d["pairs"]:
        for it in _b().pair_items(d, key)[2]:
            out.setdefault(it["code"], it)
    return out


def section(d: dict, cfg: dict, stats: dict | None = None) -> str:
    """The block, or "" when the counters are too few to say anything."""
    B = _b()
    items = ranking(stats if stats is not None else d.get("popstats") or {}, products_of(d))
    if not items:
        return ""
    cards = "".join(B.item_card(cfg, it) for it in items)
    return ('<section class="block pop-block"><div class="sec-head"><span class="eyebrow">Pressed most</span><h2>当サイトで、よく押されている商品</h2>'
            '<p class="sec-lead">商品のショップへのボタンが、当サイトで多く押された順です。購入された数や、品質を表すものではありません。'
            '誰が押したかは記録せず、同じ人の1日の重複は数えないようにしていますが、目安として見てください。</p></div>'
            f'<ul class="items">{cards}</ul>{B.freshness(d)}</section>')


def favorites_page(d: dict, cfg: dict, preview: bool) -> str:
    B = _b()
    latest = (d["c"].get("daily") or [None])[0]
    starts = (f'<a class="btn" href="/picks/{latest["date"]}/">今日のおすすめを見る</a>' if latest else "") + '<a class="btn btn-sub" href="/for/">相手から探す</a>'
    lead = "気になった商品を、あとで見直せます。このブラウザの中だけに保存され、当サイトのサーバーには送りません。"
    body = f"""{B.head_band("sky", "", "お気に入りと、最近チェックした商品", lead, single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("お気に入り", None)])}</div>
{B.pr_quiet(cfg)}
<div id="myitems" data-src="/list/items.json">
<section class="block"><div class="sec-head"><h2>気になるリスト(<span id="my-favs-n">0</span>点)</h2></div>
<div id="my-favs-empty"><p>まだ、入っていません。商品カードの「♡」を押すと、ここに入ります。</p><p class="more">{starts}</p></div>
<div id="my-favs-wrap" hidden><ul class="items" id="my-favs" aria-live="polite"></ul>
<p class="more"><button type="button" class="btn" id="my-send">このリストを送る</button><a class="btn btn-sub" href="/memo/">贈る日を登録する</a></p>
<p class="fav-note">別のスマホやパソコンで見るときは、「このリストを送る」で作ったリンクを、自分に送ってください。価格と在庫は、販売ページでご確認ください。</p></div></section>
<section class="block"><div class="sec-head"><h2>最近チェックした商品</h2></div>
<p id="my-recent-empty">商品のボタンを押すと、ここに最近の10点ほどが並びます。</p>
<div id="my-recent-wrap" hidden><ul class="items" id="my-recent" aria-live="polite"></ul><p class="more"><button type="button" class="btn btn-sub" id="my-recent-clear">履歴を消す</button></p></div></section>
</div>
{section(d, cfg)}
<noscript><p class="notice">このページは、JavaScript が使える環境でお使いください。</p></noscript>
<p class="notice">保存した内容は、このブラウザにだけあります。ブラウザのデータを消すと、なくなります。</p>"""
    html = B.page(cfg, preview, path="/favorites/", title=f"お気に入りと、最近チェックした商品 | {cfg['site_name']}", description=lead, body=body,
                  amazon_links=bool(cfg.get("amazon_tracking_id")))
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex,follow">', 1)         # a page of one browser's own: not for the search results


COUNT_PRIVACY = ("<h2>商品のボタンが押された回数</h2>"
                 "<p>商品のショップへのボタンが押されると、その商品が押された回数を、1つ数えます。数えるのは、商品ごとの回数だけです。押した人、ブラウザ、IPアドレス、時刻は記録しません。"
                 "同じブラウザでは、1つの商品につき1日1回までです。ブラウザの「トラッキングしない」設定がオンのときは、数えません。"
                 "この回数は、当サイトで多く押された商品を紹介するときと、サイトの改善に使います。"
                 "また、最近チェックした商品と、気になるリストは、お使いのブラウザの中にだけ保存され、サーバーには送りません。</p>")
