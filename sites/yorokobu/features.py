"""深掘り: one product, one page (/pick/<slug>/) — an editorial read of a product the site has picked, for the visitor who has to decide.

The text is content/features/<slug>.json (written by the editors from the product page, the maker's public information and the site's own product data; nothing
is quoted from a shop or from buyers).  What the page adds to the daily card: a conclusion in 30 seconds, who it suits and who it does not, the specification read
one fact at a time, where its price and reviews stand among the products of its kind that the site has (drawn from the site's own data, with the number of products
behind it), how to hand it over, a made-up scene and a four-panel drawing of it (said to be made up), the alternatives, and the questions people ask.

What it never does: write "I tried it" (the editors have not), show stars or ratings as the site's own (no Review / AggregateRating data; the Rakuten numbers are shown as
Rakuten's, with the date), quote a shop or buyers, give a price or picture of an Amazon product, or state a number that is not in the specification, the product data or
the page's own statistics.  `problems` is the gate (run when a feature is merged, and at every build).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from sites.yorokobu import content as ct
from sites.yorokobu import dailypicks as dp
from sites.yorokobu import commas, quality, relevance
from sokuhou.sitekit import BuildError, crumbs, esc

HERE = Path(__file__).resolve().parent
DIR = HERE / "content" / "features"
IMG_DIR = HERE / "assets" / "features"
MIN_POOL = 8                       # products behind a chart; fewer and the chart says nothing
MIN_TEXT = 2300                    # characters of editorial text for a page to be indexed (with the light 読点 of the wording pass, 2400 was about 2300)
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# what an editor who has not used the product must not write (a made-up use is a made-up review), besides dailypicks.BANNED
EXPERIENCE = ["使ってみ", "試してみ", "試した", "食べてみ", "飲んでみ", "着てみ", "買ってみ", "購入してみ", "開けてみ", "実際に使", "実際に食べ", "実際に飲", "私は", "わたしは", "我が家", "うちでは", "編集部で試", "検証した"]
PANELS = 4                        # at most; an article may carry 1-4 pictures (a single illustration or mood image, a pair, a strip of three, or four panels)
MAX_COMMAS = 3.9                  # 読点 per 100 characters of the editorial text (natural writing is about 2.5-3.5; the first drafts had 4-5)


def _b():
    from sites.yorokobu import build
    return build


# ---------------------------------------------------------------- loading and the gate

def load(dir: Path | None = None) -> list[dict]:
    d = dir or DIR
    out = []
    if d.exists():
        for p in sorted(d.glob("*.json")):
            f = json.loads(p.read_text(encoding="utf-8"))
            if f.get("slug") != p.stem:
                raise BuildError(f"{p.name}: the slug has to be the file name")
            out.append(f)
    return sorted(out, key=lambda f: (f["date"], f["slug"]), reverse=True)


def prose(f: dict) -> list[str]:
    """Every sentence the editors wrote (what the number check and the length gate look at)."""
    out = [f["catch"], *f["verdict"], *f["who"]["yes"], *f["who"]["no"], *f["good"], *f["care"], *f["give"], f["scene"]["text"], f["scene"]["reaction"]]
    out += [x for r in f["reading"] for x in (r["h"], r["p"])]
    out += [x for q in f["faq"] for x in (q["q"], q["a"])]
    out += [p["cap"] for p in f["manga"]["panels"]]
    return out


def problems(f: dict, entry: dict | None, img_dir: Path | None = None) -> list[str]:
    """Everything wrong with one feature (empty = it can be published).  `entry` is the daily entry it is about."""
    slug = f.get("slug", "?")
    out: list[str] = []
    need = ("slug", "date", "ref", "title", "catch", "verdict", "who", "specs", "reading", "good", "care", "give", "scene", "manga", "compare", "faq", "alts", "evidence", "verified")
    miss = [k for k in need if not f.get(k)]
    if miss:
        return [f"{slug}: missing {', '.join(miss)}"]
    if not SLUG.fullmatch(slug):
        out.append(f"{slug}: slug has to be lowercase ascii with hyphens")
    try:
        date.fromisoformat(f["date"])
        date.fromisoformat(f["verified"])
    except ValueError:
        return out + [f"{slug}: bad date"]
    if entry is None:
        return out + [f"{slug}: {f['ref']} is not an entry of {f['date']}"]
    if not 20 <= len(f["title"]) <= 52:
        out.append(f"{slug}: title is {len(f['title'])} characters (need 20-52)")
    if not 12 <= len(f["catch"]) <= 44:
        out.append(f"{slug}: catch is {len(f['catch'])} characters (need 12-44)")
    if len(f["verdict"]) != 3 or any(not 30 <= len(x) <= 120 for x in f["verdict"]):
        out.append(f"{slug}: verdict needs exactly 3 sentences of 30-120 characters")
    for k in ("yes", "no"):
        if not 2 <= len(f["who"].get(k, [])) <= 4 or any(not 8 <= len(x) <= 70 for x in f["who"][k]):
            out.append(f"{slug}: who.{k} needs 2-4 phrases of 8-70 characters")
    if not 4 <= len(f["specs"]) <= 9 or any(not (r.get("k") and r.get("v")) for r in f["specs"]):
        out.append(f"{slug}: specs needs 4-9 rows of {{k, v}}")
    if not 3 <= len(f["reading"]) <= 5 or any(not (14 <= len(r.get("h", "")) <= 34 and 140 <= len(r.get("p", "")) <= 520) for r in f["reading"]):
        out.append(f"{slug}: reading needs 3-5 blocks (heading 14-34, text 140-520 characters)")
    for k, lo, hi in (("good", 3, 4), ("care", 3, 4)):
        if not lo <= len(f[k]) <= hi or any(not 30 <= len(x) <= 140 for x in f[k]):
            out.append(f"{slug}: {k} needs {lo}-{hi} sentences of 30-140 characters")
    if not 3 <= len(f["give"]) <= 5 or any(not 20 <= len(x) <= 120 for x in f["give"]):
        out.append(f"{slug}: give needs 3-5 steps of 20-120 characters")
    sc = f["scene"]
    if not (sc.get("label") and 120 <= len(sc.get("text", "")) <= 480 and 40 <= len(sc.get("reaction", "")) <= 220) or "つくった" not in sc["label"] + sc["text"] and "想定" not in sc["label"]:
        out.append(f"{slug}: scene needs a label that says it is made up (想定), text 120-480 and reaction 40-220 characters")
    m = f["manga"]
    if not 1 <= len(m.get("panels", [])) <= PANELS or any(not (p.get("img") and 20 <= len(p.get("alt", "")) <= 90 and 6 <= len(p.get("cap", "")) <= 44) for p in m["panels"]):
        out.append(f"{slug}: manga needs 1-{PANELS} pictures (img, alt 20-90, cap 6-44 characters)")
    else:
        base = (img_dir or IMG_DIR) / slug
        for p in m["panels"]:
            path = base / p["img"]
            if not path.exists():
                out.append(f"{slug}: panel image {p['img']} is missing")
                continue
            try:
                from PIL import Image
                with Image.open(path) as im:
                    if im.width < 512 or im.height < 512:
                        out.append(f"{slug}: panel {p['img']} is {im.width}x{im.height} (need at least 512x512)")
            except Exception:                                   # no Pillow here: the size is not checked
                pass
        if sum((base / p["img"]).stat().st_size for p in m["panels"] if (base / p["img"]).exists()) > 1_000_000:
            out.append(f"{slug}: the pictures are over 1 MB together")
    c = f["compare"]
    if not (c.get("words") and c.get("label")):
        out.append(f"{slug}: compare needs words and a label")
    if not 3 <= len(f["faq"]) <= 5 or any(not (10 <= len(q.get("q", "")) <= 60 and 40 <= len(q.get("a", "")) <= 260) for q in f["faq"]):
        out.append(f"{slug}: faq needs 3-5 questions (10-60) with answers (40-260 characters)")
    if not 2 <= len(f["alts"]) <= 4:
        out.append(f"{slug}: alts needs 2-4 refs")
    if not f["evidence"] or any(not e.get("label") or (e.get("url") and not str(e["url"]).startswith("https://")) for e in f["evidence"]):
        out.append(f"{slug}: evidence needs labels (the pages the specification was read on), each with an https link where the page is not a shop's product page")
    if any(dp.MALL_URL.search(str(e.get("url", ""))) for e in f["evidence"]):
        out.append(f"{slug}: evidence must not link a shop's product page (the repository is public; a mall URL is the shop's data): give the label only")
    text = "".join(prose(f))
    if len(text) < MIN_TEXT:
        out.append(f"{slug}: {len(text)} characters of text (need {MIN_TEXT}; a thin page is not published)")
    for w in dp.BANNED + EXPERIENCE:
        if w in text:
            out.append(f"{slug}: banned word {w} (an advertisement's claim, or a made-up use)")
    if commas.density("".join(prose(f))) > MAX_COMMAS:
        out.append(f"{slug}: too many 読点 ({commas.density(''.join(prose(f))):.1f} per 100 characters; the limit is {MAX_COMMAS}): python -m sites.yorokobu.commas apply <file>")
    for s in prose(f):                                            # each item on its own (they are not one run of text)
        out += [x for x in quality.language_problems(s, slug) if "too many" not in x]
    if "".join(prose(f)).count("やすい") > quality.MAX_YASUI * 2:
        out.append(f"{slug}: too many 〜やすい ({''.join(prose(f)).count('やすい')}); name the concrete reason instead")
    # a number the page states has to be in the specification, the product's name or entry, or the page's own statistics (a typed-over number cannot slip in)
    allowed = ct._numbers(ct._plain_json([f["specs"], f["title"], f["verified"], f["date"], entry.get("name", ""), entry.get("check", []), entry.get("summary", ""), entry.get("good", ""),
                                          entry.get("care", ""), f.get("facts", [])]))
    for s in prose(f):
        for q in re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?(?=\s*(?:%|円|cm|mm|g|ml|ミリ|度|日|時間|枚|本|個|袋|点|種|人|歳|倍|L|kg|ポイント))", s):
            if q.replace(",", "") not in allowed:
                out.append(f"{slug}: '{s[:24]}…' states {q}, which is not in the specification or the entry")
    return out


# ---------------------------------------------------------------- the product's place among the site's products

def kind_of(d: dict) -> dict[str, str]:
    """{item code: kind of gift} from the ideas the pages show (the kind an editor gave the idea)."""
    B = _b()
    out: dict[str, str] = {}
    for key in d["pairs"]:
        for idea in B.pair_items(d, key)[0]:
            for it in idea["items"]:
                out.setdefault(it["code"], idea["type"])
    return out


def pool(d: dict, f: dict, kind: str) -> tuple[list[dict], str]:
    """The products of this kind that the site has (by the words of the feature, at the head of the title; else the whole kind) and how the pool was made."""
    from sites.yorokobu import dataroom
    allp = dataroom.all_products(d)
    by_words = [p for p in allp if relevance.fits_head(p["name"], f["compare"]["words"])]
    if len(by_words) >= MIN_POOL:
        return by_words, f"「{f['compare']['label']}」と名前に書かれた商品"
    kinds = kind_of(d)
    by_kind = [p for p in allp if kinds.get(p["code"]) == kind]
    return by_kind, f"種類が「{kind}」の商品"


def stats(items: list[dict], me: dict | None) -> dict | None:
    """The numbers of the pool and where `me` (a Rakuten product with its live price) stands; None when the pool is too small."""
    from sites.yorokobu import dataroom
    if len(items) < MIN_POOL:
        return None
    prices = sorted(i["price"] for i in items)
    q1, med, q3 = dataroom.quartiles(prices)
    out = {"n": len(items), "min": prices[0], "q1": q1, "median": med, "q3": q3, "max": prices[-1],
           "ship": sum(1 for i in items if i["free_shipping"]) / len(items) * 100, "gift": sum(1 for i in items if i.get("gift")) / len(items) * 100,
           "rating": dataroom.median(i["rating"] for i in items if i["reviews"]) if any(i["reviews"] for i in items) else None,
           "reviews": dataroom.median(i["reviews"] for i in items)}
    if me:
        out["below"] = sum(1 for p in prices if p < me["price"]) / len(prices) * 100
        out["me"] = me
    return out


def bands(items: list[dict], price: int | None) -> list[tuple[str, int, bool]]:
    """Price bands of the pool, edges at multiples of 500 yen, about five of them: (label, count, whether the product is in it)."""
    prices = sorted(i["price"] for i in items)
    lo, hi = prices[0] // 500 * 500, prices[-1]
    step = max(500, round((hi - lo) / 5 / 500) * 500)
    edges = [lo]
    while edges[-1] <= hi:
        edges.append(edges[-1] + step)
    return [(f"{x:,}〜{y:,}円", sum(1 for p in prices if x <= p < y), price is not None and x <= price < y) for x, y in zip(edges, edges[1:])]


# ---------------------------------------------------------------- the page

def path(f: dict) -> str:
    return f"/pick/{f['slug']}/"


def entry_of(day: dict | None, ref: str) -> dict | None:
    if not day:
        return None
    rows = {f"r{i}": e for i, e in enumerate(day["rakuten"], 1)} | {f"a{i}": e for i, e in enumerate(day["amazon"], 1)}
    return rows.get(ref)


def _list(items: list[str], cls: str = "") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def _chart_price(d: dict, f: dict, pl: list[dict], how: str, st: dict) -> str:
    from sites.yorokobu import dataroom
    price = st["me"]["price"] if st.get("me") else None
    rows = bands(pl, price)
    top = max(n for _, n, _ in rows) or 1
    body = "".join(f'<div class="hb-row{" me" if me else ""}"><span class="hb-l">{esc(lab)}</span><span class="hb-track"><i class="hb-fill {"s2" if me else "s1"}" style="width:{n / top * 100:.1f}%"></i></span>'
                   f'<span class="hb-v">{n}点{"　← この商品" if me else ""}</span></div>' for lab, n, me in rows)
    where = f"、この商品は{dataroom.yen(price)}で安いほうから数えて約{round(st['below'])}%の位置です" if price else ""
    cap = (f"{how}({st['n']}点、{d['fetched_label']}時点)の価格の分布。中央値は{dataroom.yen(st['median'])}、真ん中の半分は{dataroom.yen(st['q1'])}〜{dataroom.yen(st['q3'])}です{where}。"
           f"当サイトが取り上げた商品の数字で楽天市場の全体ではありません。")
    return dataroom.figure(d, "同じ種類の商品の価格の位置", f'<div class="hb">{body}</div>', esc(cap),
                           dataroom.table(["価格帯", "商品数"], [[lab, str(n)] for lab, n, _ in rows]))


def _chart_facts(d: dict, f: dict, st: dict) -> str:
    from sites.yorokobu import dataroom
    me = st.get("me")
    rows = [("送料無料の商品", st["ship"], f"{st['ship']:.0f}%"), ("ギフト対応の商品", st["gift"], f"{st['gift']:.0f}%")]
    note = ""
    if me:
        mine = [f"送料無料: {'はい' if me['free_shipping'] else 'いいえ'}", f"ギフト対応: {'はい' if me.get('gift') else '表示なし'}",
                f"楽天の評価 {me['rating']:.2f}({me['reviews']:,}件)" if me["reviews"] else "楽天のレビュー: まだありません"]
        note = f' この商品は、{"、".join(mine)}(楽天市場の表示。{d["fetched_label"]}時点)。'
    cap = f"同じ種類の{st['n']}点のうち送料無料・ギフト対応の割合。レビュー件数の中央値は{st['reviews']:,.0f}件" + (f"、評価の中央値は{st['rating']:.2f}" if st["rating"] else "") + f"です。{note}"
    return dataroom.figure(d, "送料とギフト対応", dataroom.hbars(rows, top=100), esc(cap))


def _manga(f: dict) -> str:
    m = f["manga"]
    cells = "".join(f'<figure class="mg-cell"><img src="/assets/features/{esc(f["slug"])}/{esc(p["img"])}" alt="{esc(p["alt"])}" width="768" height="768" loading="lazy" decoding="async"><figcaption>{esc(p["cap"])}</figcaption></figure>'
                    for p in m["panels"])
    return f'<div class="mg mg-n{len(m["panels"])}" role="group" aria-label="{esc(m["title"])}">{cells}</div>'


def _alts(cfg: dict, d: dict, day: dict, refs: list[str]) -> str:
    from sites.yorokobu import picksite
    cards = ""
    for ref in refs:
        e = entry_of(day, ref)
        if not e:
            continue
        c = picksite.rakuten_card(cfg, d, e, ref, 1) if ref.startswith("r") else picksite.amazon_card(cfg, d, e, ref, 1)
        if c:
            cards += c
    return f'<div class="pick-list feat-alts">{cards}</div>' if cards else ""


def feature_page(d: dict, cfg: dict, preview: bool, f: dict, day: dict, entry: dict, others: list[dict]) -> str:
    from sites.yorokobu import dataroom
    B = _b()
    live = d.get("daily_items", {}).get(entry.get("code", "")) if f["ref"].startswith("r") else None
    unavailable = bool(live is not None and not live.get("available", True))
    if f["ref"].startswith("r"):
        url = live["url"]                                                                  # the shop's data is today's API answer only (a feature whose product the API does not find is not built: see build.py)
        href = B.rakuten_link(cfg, url)
        img = live["image"]                                                                # the picture as the API gave it; its size on the page is the CSS's
        line = B.blurb_line(live)
        buy = f'<span class="btn big"><a href="{esc(href)}" target="_blank" rel="nofollow sponsored noopener">楽天市場で見る</a></span>'
        other_btn = ""                                                                    # a Rakuten product part carries Rakuten's link only (terms Article 8)
        stars = f'<span class="stars">★{live["rating"]:.1f}</span>({live["reviews"]:,}件・楽天市場のレビュー)' if live["reviews"] else ""
        price = (f'<p class="pick-price">{B.yen(live["price"])}<small>{stars}{"・送料無料" if live["free_shipping"] else ""}<br>楽天市場の{esc(d["fetched_label"])}時点の情報</small></p>')
        B.SEEN[entry["code"]] = {"n": line, "p": live["price"], "i": live["image"], "u": href}
        me = live
        pl, how = pool(d, f, entry["kind"])
        st = stats(pl, me)
        photo = (f'<div class="imgbox"><div class="feat-photo"><a href="{esc(href)}" target="_blank" rel="nofollow sponsored noopener"><img src="{esc(img)}" alt="{esc(line or "楽天市場の商品ページ")}"></a></div>'
                 f'{B.fav_button(entry["code"], line or "気になる品", live["price"], url)}</div>')
    else:
        href = B.amazon_dp(cfg, entry["asin"])
        buy = f'<span class="btn big"><a href="{esc(href)}" target="_blank" rel="nofollow sponsored noopener">Amazonで見る</a></span>'
        other_btn = f'<span class="btn btn-sub"><a href="{esc(B.search_link(cfg, B.amazon_query(entry["name"])))}" target="_blank" rel="nofollow sponsored noopener">楽天市場で探す</a></span>'
        price = '<p class="pick-price"><small>価格・在庫・購入者の評価はAmazonのページでご確認ください。</small></p>'
        pl, how = pool(d, f, entry["kind"])
        st = stats(pl, None)
        photo = (f'<div class="imgbox mood"><div class="feat-photo mood"><a href="{esc(href)}" target="_blank" rel="nofollow sponsored noopener">{B.mood_img(entry["mood"], entry["name"] + "の商品写真ではなく、贈る場面を表したイメージ", "(max-width: 760px) 100vw, 480px", "eager", high=True)}'
                 f'<span class="img-note">イメージ画像</span></a></div>{B.fav_button("a:" + entry["asin"], B.short(entry["name"], 40), None, href)}</div>')
    charts = ""
    if st:
        charts = f'<section class="block" id="position"><div class="sec-head"><h2>同じ種類の中での位置</h2></div>{_chart_price(d, f, pl, how, st)}{_chart_facts(d, f, st)}</section>'
    alts = _alts(cfg, d, day, f["alts"])                                              # none of the alternatives found by the API today: no heading either
    notice = '<p class="notice">この商品はいま販売ページで取り扱いがないと表示されています。下の「代わりの候補」をご覧ください。</p>' if unavailable else ""
    specs = "".join(f"<tr><th>{esc(r['k'])}</th><td>{esc(r['v'])}</td></tr>" for r in f["specs"])
    reading = "".join(f"<h3>{esc(r['h'])}</h3><p>{esc(r['p'])}</p>" for r in f["reading"])
    faq = "".join(f"<details class='faq'><summary>{esc(q['q'])}</summary><p>{esc(q['a'])}</p></details>" for q in f["faq"])
    ev = "".join((f'<li><a href="{esc(e["url"])}" rel="noopener nofollow" target="_blank">{esc(e["label"])}</a></li>' if e.get("url") else f'<li>{esc(e["label"])}</li>') for e in f["evidence"])
    more = "".join(f'<li><a href="{path(o)}">{esc(o["title"])}</a></li>' for o in others[:4])
    url_abs = cfg["site_url"].rstrip("/") + path(f)
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": f["title"], "datePublished": f["date"], "dateModified": f["verified"], "inLanguage": "ja",
                     "author": {"@type": "Organization", "name": cfg["operator_name"]}, "mainEntityOfPage": url_abs}, ensure_ascii=False)
    body = f"""{B.head_band("yellow", "", esc(f["title"]), f["catch"], single=True)}
<div class="crumbs-wrap">{crumbs([("トップ", "/"), ("毎日のおすすめ", "/picks/"), (dp_label(f["date"]), f"/picks/{f['date']}/"), ("注目の商品", None)])}</div>
{B.pr_quiet(cfg)}
{notice}
<section class="feat-top"><div class="feat-hero">{photo}<div class="feat-sum"><p class="eyebrow">30秒でわかる結論</p>{_list(f["verdict"], "feat-verdict")}{price}<div class="item-btns">{buy}{other_btn}</div></div></div></section>
<section class="block"><div class="sec-head"><h2>合う相手と避けたい相手</h2></div><div class="cols feat-who"><div><h3>合う相手</h3>{_list(f["who"]["yes"], "feat-yes")}</div><div><h3>避けたい相手・場面</h3>{_list(f["who"]["no"], "feat-no")}</div></div></section>
<section class="block"><div class="sec-head"><h2>仕様を一つずつ読む</h2></div><div class="tablewrap"><table class="feat-specs"><tbody>{specs}</tbody></table></div>
<p class="sec-lead">仕様は商品ページとメーカーの公開情報で、{esc(f["verified"].replace("-", "年", 1).replace("-", "月", 1) + "日")}に確かめました。</p>{reading}</section>
<section class="block"><div class="sec-head"><h2>良い点と気になる点</h2></div><div class="cols"><div><h3>よい点</h3>{_list(f["good"], "feat-yes")}</div><div><h3>気になる点</h3>{_list(f["care"], "feat-no")}</div></div></section>
{charts}
<section class="block"><div class="sec-head"><h2>渡し方</h2></div><ol class="feat-give">{"".join(f"<li>{esc(x)}</li>" for x in f["give"])}</ol></section>
<section class="block feat-scene"><div class="sec-head"><span class="eyebrow">{esc(f["scene"]["label"])}</span><h2>渡す場面を思い浮かべる</h2></div>{_manga(f)}<p>{esc(f["scene"]["text"])}</p><p class="feat-react"><b>想定される反応</b>{esc(f["scene"]["reaction"])}</p>
<p class="sec-lead">この場面と漫画は読む人が想像しやすいように編集部がつくった例です。実際の贈り物の感想や購入者の声ではありません。</p></section>
{f'<section class="block"><div class="sec-head"><h2>代わりの候補</h2></div>{alts}</section>' if alts else ""}
<section class="block"><div class="sec-head"><h2>よくある質問</h2></div>{faq}</section>
<section class="block feat-cta"><p class="more">{buy}{other_btn}<a class="btn btn-sub" href="/memo/">贈る日を登録する</a></p></section>
{B.share_bar(cfg, path(f), f"{f['title']}: {f['catch']}", "このページをだれかに・自分に送る", hint=True)}
<section class="block"><div class="sec-head"><h2>この記事について</h2></div><p class="notice">商品の仕様、メーカーなどの公開情報、当サイトが集めた商品のデータをもとに編集部が、贈り物としての選びやすさを読み解いています。価格・在庫は販売ページでご確認ください。</p><ul class="plain feat-ev">{ev}</ul></section>
{f'<section class="related" style="margin-top:40px"><h2><span class="scribble">ほかの注目の商品</span></h2><ul class="plain">{more}</ul></section>' if more else ""}
<script type="application/ld+json">{ld}</script>"""
    return B.page(cfg, preview, path=path(f), title=f"{f['title']} | {cfg['site_name']}", description=f["catch"] + " " + f["verdict"][0][:70], body=body, og_image=B.og_for(f"pick/{f['slug']}"),
                  amazon_links=bool(cfg.get("amazon_tracking_id")))


def dp_label(iso: str) -> str:
    from sites.yorokobu import picksite
    return picksite.date_label(iso)


def teaser(cfg: dict, d: dict, feats: list[dict], day_iso: str | None = None, limit: int = 3) -> str:
    """The block 「注目の商品」 on the picks pages: the newest features."""
    shown = [f for f in feats if day_iso is None or f["date"] == day_iso][:limit]
    if not shown:
        return ""
    cells = "".join(f'<li><a class="tile wide" href="{path(f)}"><span><b>{esc(f["title"])}</b><small>{esc(f["catch"])}</small></span></a></li>' for f in shown)
    return f'<section class="block"><div class="sec-head"><span class="eyebrow">Read more</span><h2>注目の商品</h2><p class="sec-lead">気になる商品をくわしく調べました。</p></div><ul class="tiles wide">{cells}</ul></section>'


def build_pages(d: dict, cfg: dict, preview: bool) -> dict[str, str]:
    feats = d["c"].get("features") or []
    days = {x["date"]: x for x in (d["c"].get("daily") or [])}
    out: dict[str, str] = {}
    for f in feats:
        day = days.get(f["date"])
        entry = entry_of(day, f["ref"])
        errs = problems(f, entry)
        if errs:
            raise BuildError("; ".join(errs[:4]))
        if f["ref"].startswith("r") and day and d.get("daily_items", {}).get(entry["code"]) is not None and not d["daily_items"][entry["code"]].get("available", True):
            pass                                                         # kept: the page says the product is not on sale now and offers the alternatives
        out[f"pick/{f['slug']}/index.html"] = feature_page(d, cfg, preview, f, day, entry, [o for o in feats if o["slug"] != f["slug"]])
    return out


def feed_entries(d: dict, cfg: dict) -> list[tuple[str, str, str, str]]:
    base = cfg["site_url"].rstrip("/")
    return [(f["date"], f["title"], f"{base}{path(f)}", f["catch"]) for f in (d["c"].get("features") or [])]


# ---------------------------------------------------------------- tools

def ingest(src: Path, mapping: dict[str, str], size: int = 768, quality: int = 80) -> list[str]:
    """Panels Codex drew (<prefix>-<n>.png, n = 1..4) as 768 px WebP files in assets/features/<slug>/<n>.webp.  Returns what was written."""
    from PIL import Image
    done = []
    for prefix, slug in mapping.items():
        for n in range(1, PANELS + 1):
            p = src / f"{prefix}-{n}.png"
            if not p.exists():
                continue
            out = IMG_DIR / slug / f"{n}.webp"
            out.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(p) as im:
                im = im.convert("RGB")
                side = min(im.size)                                   # a square from the middle (the order asks for squares)
                left, top = (im.width - side) // 2, (im.height - side) // 2
                im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS).save(out, "WEBP", quality=quality, method=6)
            done.append(f"{slug}/{n}.webp {out.stat().st_size // 1024} KB")
    return done


def _data() -> dict:
    """The build's data (content + the stored Rakuten items), for the commands that look at the pools."""
    B = _b()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    # the day's products are fetched on the deploy server; here the newest stored copy in out/ is enough to see the pools (the live prices of the day are not needed for the pool)
    stored = sorted((B.ROOT / "out").glob("yorokobu_items*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return B.prepare(ct.load(), json.loads(stored[0].read_text(encoding="utf-8")) if stored else None, cfg)


def candidates(d: dict, day_iso: str | None = None) -> list[str]:
    """The Rakuten products of a day's picks that have no article yet, with how many products of the same kind the site has (a chart needs MIN_POOL)."""
    days = sorted((d["c"].get("daily") or []), key=lambda x: x["date"], reverse=True)
    day = next((x for x in days if day_iso in (None, x["date"])), None)
    if not day:
        return ["no daily page for that date"]
    done = {(f["date"], f["ref"]) for f in d["c"].get("features") or []}
    used = {entry_of(next((x for x in days if x["date"] == f["date"]), None), f["ref"]).get("code") for f in d["c"].get("features") or []
            if entry_of(next((x for x in days if x["date"] == f["date"]), None), f["ref"])}
    kinds = kind_of(d)
    from sites.yorokobu import dataroom
    allp = dataroom.all_products(d)
    out = [f"day {day['date']} (theme: {day['theme']})"]
    for n, e in enumerate(day["rakuten"], 1):
        ref = f"r{n}"
        live = d.get("daily_items", {}).get(e["code"])
        pool_n = sum(1 for p in allp if kinds.get(p["code"]) == e["kind"])
        flags = []
        if (day["date"], ref) in done or e["code"] in used:
            flags.append("ALREADY HAS AN ARTICLE")
        if live is not None and not live.get("available", True):
            flags.append("not on sale now")
        if pool_n < MIN_POOL:
            flags.append(f"kind pool {pool_n} < {MIN_POOL}: only a compare-words pool can give a chart")
        out.append(f"{ref}  {e['code']}  kind={e['kind']}  kind-pool={pool_n}" + (f"   [{'; '.join(flags)}]" if flags else ""))
    return out


def chart_report(d: dict, f: dict) -> str:
    day = next((x for x in d["c"].get("daily") or [] if x["date"] == f["date"]), None)
    entry = entry_of(day, f["ref"])
    if not entry:
        return "no entry"
    pl, how = pool(d, f, entry["kind"])
    st = stats(pl, d.get("daily_items", {}).get(entry.get("code", "")) if f["ref"].startswith("r") else None)
    return f"chart: {'yes' if st else 'NO (too few products)'}, {len(pl)} products ({how})"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("--src", type=Path, required=True)
    i.add_argument("--map", nargs="+", required=True, help="prefix=slug ...")
    sub.add_parser("check")
    cd = sub.add_parser("candidates")
    cd.add_argument("--day", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "ingest":
        for line in ingest(a.src, dict(m.split("=", 1) for m in a.map)):
            print(line)
        return 0
    if a.cmd == "candidates":
        print("\n".join(candidates(_data(), a.day)))
        return 0
    d = _data()
    c = d["c"]
    days = {x["date"]: x for x in (c.get("daily") or [])}
    bad = 0
    for f in c["features"]:
        errs = problems(f, entry_of(days.get(f["date"]), f["ref"]))
        rep = chart_report(d, f)
        if "NO" in rep:
            errs.append(f"{f['slug']}: {rep}; change compare.words or choose another product")
        print(f"{f['slug']}: {len(''.join(prose(f)))} characters, {rep}" + (", OK" if not errs else ""))
        for e in errs:
            print("  -", e)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
