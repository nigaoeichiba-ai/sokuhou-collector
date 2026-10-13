"""Sales and campaigns of the shops (楽天市場 お買い物マラソン, Amazon プライム感謝祭 ...): a calendar of the ones the shops have ANNOUNCED, and the banner that
tells a visitor "on now" / "starts on ..." with the shop's own event page behind an affiliate link.

content/sales.json holds only events whose dates were read on the shop's official page (`source`, `verified`); a guess from earlier years is never shown as a date.
The banner is made twice from the same data and the same sentences: here (what a crawler and a visitor without scripts get, as of the build) and in assets/sale.js
(what a visitor gets, as of the minute of the visit: a page built in the morning says "on now" in the evening).  A test runs both and compares the sentences.

Words: no percentage, no "最安", no "今だけ" without a date: the banner says what the shop announced, that it needs an entry / membership when it does, and where to read the terms.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sokuhou.sitekit import esc

HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
STORE = {"rakuten": "楽天市場", "amazon": "Amazon"}
ALLOWED_HOSTS = {"rakuten": ("event.rakuten.co.jp", "www.rakuten.co.jp"), "amazon": ("www.amazon.co.jp",)}
WEEKDAY = "月火水木金土日"
SOON_DAYS = 14        # "starts on ..., choose before" from this many days ahead
AHEAD_DAYS = 30       # a quieter line from this many days ahead
FIELDS = ("id", "store", "name", "start", "end", "url", "note", "source", "verified")


class SalesError(ValueError):
    pass


def _dt(s: str) -> datetime:
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        raise SalesError(f"{s}: a time needs its offset (+09:00)")
    return t.astimezone(JST)


def load(path: Path | None = None) -> list[dict]:
    """The events of content/sales.json, checked (a bad file stops the build instead of publishing a wrong date)."""
    p = path or HERE / "content" / "sales.json"
    if not p.exists():
        return []
    events = json.loads(p.read_text(encoding="utf-8")).get("events", [])
    seen = set()
    for e in events:
        for f in FIELDS:
            if not e.get(f):
                raise SalesError(f"{e.get('id', '?')}: missing {f}")
        if e["id"] in seen:
            raise SalesError(f"{e['id']}: twice")
        seen.add(e["id"])
        if e["store"] not in STORE:
            raise SalesError(f"{e['id']}: unknown store")
        host = e["url"].split("/")[2] if e["url"].startswith("https://") else ""
        if host not in ALLOWED_HOSTS[e["store"]]:
            raise SalesError(f"{e['id']}: the link has to be the shop's own page ({', '.join(ALLOWED_HOSTS[e['store']])})")
        if not e["source"].startswith("https://"):
            raise SalesError(f"{e['id']}: source has to be the page the dates were read on")
        s, t = _dt(e["start"]), _dt(e["end"])
        if not s < t:
            raise SalesError(f"{e['id']}: ends before it starts")
        if e.get("entry_start") and not _dt(e["entry_start"]) <= s:
            raise SalesError(f"{e['id']}: the entry cannot start after the event")
    return sorted(events, key=lambda e: _dt(e["start"]))


def label(t: datetime) -> str:
    """'10月14日(水)20時' / '10月17日(土)9時59分' (Japan time, as the shops write it)."""
    t = t.astimezone(JST)
    return f"{t.month}月{t.day}日({WEEKDAY[t.weekday()]}){t.hour}時" + (f"{t.minute}分" if t.minute else "")


def phase(e: dict, now: datetime) -> str | None:
    """live / entry / soon / ahead, or None (over, or too far off to mention)."""
    now = now.astimezone(JST)
    s, t = _dt(e["start"]), _dt(e["end"])
    if s <= now <= t:
        return "live"
    if now > t:
        return None
    if e.get("entry_start") and _dt(e["entry_start"]) <= now < s:
        return "entry"
    days = (s.date() - now.date()).days
    if days <= SOON_DAYS:
        return "soon"
    if days <= AHEAD_DAYS:
        return "ahead"
    return None


def message(e: dict, now: datetime) -> dict | None:
    """{'phase', 'tag', 'text', 'cta'} of one event at `now` (None when it is not to be mentioned).  assets/sale.js makes the same sentences."""
    ph = phase(e, now)
    if ph is None:
        return None
    now = now.astimezone(JST)
    store, name = STORE[e["store"]], e["name"]
    s, t = _dt(e["start"]), _dt(e["end"])
    after = f"{e['after']}" if e.get("after") else ""
    if ph == "live":
        return {"phase": ph, "tag": "開催中", "short": f"{name} {label(t)}まで", "text": f"{store}で{name}を開催中です({label(t)}まで)。プレゼントを買うなら、今がおすすめです。{after}", "cta": f"{store}の{name}を見る"}
    days = (s.date() - now.date()).days
    tag = "きょう" if days == 0 else "あす" if days == 1 else f"{days}日後"
    short = f"{label(s)}から {name}"
    if ph == "entry":
        return {"phase": ph, "tag": tag, "short": short, "text": f"{label(s)}から{store}の{name}です。エントリーは受付中です。それまでに贈り物を選んでおくとお得なタイミングで買えます。{after}",
                "cta": f"{name}の詳細を見る"}
    if ph == "soon":
        return {"phase": ph, "tag": tag, "short": short, "text": f"{label(s)}から{store}の{name}を開催します。それまでに贈り物を選んでおくとお得なタイミングで買えます。{after}", "cta": f"{name}の詳細を見る"}
    return {"phase": ph, "tag": "開催予定", "short": short, "text": f"{label(s)}から{store}の{name}を開催します。日付が決まっている贈り物はその日に合わせて買うのも一案です。{after}", "cta": f"{name}の詳細を見る"}


ORDER = {"live": 0, "entry": 1, "soon": 2, "ahead": 3}


def choose(events: list[dict], now: datetime, limit: int = 2) -> list[tuple[dict, dict]]:
    """The events to show, at most one per shop: the one on now (the earliest to end), else the nearest coming one."""
    best: dict[str, tuple[tuple, dict, dict]] = {}
    for e in events:
        m = message(e, now)
        if not m:
            continue
        key = (ORDER[m["phase"]], _dt(e["end"] if m["phase"] == "live" else e["start"]))
        if e["store"] not in best or key < best[e["store"]][0]:
            best[e["store"]] = (key, e, m)
    return [(e, m) for _, e, m in sorted(best.values(), key=lambda x: x[0])][:limit]


def js_data(events: list[dict], href: dict[str, str]) -> str:
    """The events the script needs (only those not over), as JSON for the data attribute; `href` maps an event id to its affiliate link."""
    rows = [{"id": e["id"], "store": e["store"], "name": e["name"], "start": e["start"], "end": e["end"], "entry": e.get("entry_start", ""), "after": e.get("after", ""),
             "href": href[e["id"]]} for e in events]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def _item(e: dict, m: dict, href: str) -> str:
    return (f'<p class="sale-item sale-{m["phase"]}" data-id="{esc(e["id"])}"><span class="sale-tag">{esc(m["tag"])}</span><span class="sale-short">{esc(m["short"])}</span><span class="sale-text">{esc(m["text"])}</span>'
            f'<a class="btn sale-btn" href="{esc(href)}" rel="sponsored nofollow noopener" target="_blank">{esc(m["cta"])}</a></p>')


def bar(events: list[dict], now: datetime, href: dict[str, str]) -> str:
    """The slim bar under the header (on the pages that carry a PR label).  Empty (no element at all) when nothing is on or near at the build; the events not over are in
    the data attribute so the script can change what the bar says as time passes (an event that starts or ends after the page was built)."""
    shown = choose(events, now)
    if not shown:
        return ""
    live = [e for e in events if _dt(e["end"]) >= now.astimezone(JST)]
    items = "".join(_item(e, m, href[e["id"]]) for e, m in shown)
    return (f'<aside class="sale-bar" id="sale-bar" aria-label="セール情報" data-sales="{esc(js_data(live, href))}">'
            f'<div class="sale-in"><span class="pr-chip" title="広告を含みます" aria-label="広告を含みます">PR</span><div class="sale-items">{items}</div><a class="sale-more" href="/sale/">日程</a></div></aside>')


# ---------------------------------------------------------------- the page /sale/

def _b():
    from sites.yorokobu import build
    return build


def event_href(cfg: dict, e: dict) -> str | None:
    """The affiliate link to the shop's event page (None for an Amazon event when there is no Associates ID: no Amazon link without it)."""
    B = _b()
    if e["store"] == "rakuten":
        return B.rakuten_link(cfg, e["url"])
    if not cfg.get("amazon_tracking_id"):
        return None
    from urllib.parse import quote
    return f"{e['url']}{'&' if '?' in e['url'] else '?'}tag={quote(cfg['amazon_tracking_id'], safe='')}"


def hrefs(cfg: dict, events: list[dict]) -> tuple[list[dict], dict[str, str]]:
    out, href = [], {}
    for e in events:
        h = event_href(cfg, e)
        if h:
            out.append(e)
            href[e["id"]] = h
    return out, href


def _range(e: dict) -> str:
    s, t = _dt(e["start"]), _dt(e["end"])
    return f"{label(s)} から {label(t)} まで"


MIN_POINT_ITEMS = 4
HERO = {"autumn": "秋の窓辺の机にギフトの箱と壁のカレンダー、開いたノートが並んでいる(イメージ)",
        "winter": "雪の夜、机の上でギフトを包んでいる人と壁のカレンダー(イメージ)"}


def hero(now: datetime) -> str:
    """The picture at the top of /sale/ (drawn for the page; no logo, no shop's banner, no text in it): the winter one from November to February."""
    kind = "winter" if now.astimezone(JST).month in (11, 12, 1, 2) else "autumn"
    base = f"/assets/sale/{kind}"
    return (f'<figure class="sale-hero"><img src="{base}-1200.webp" srcset="{base}-640.webp 640w, {base}-1200.webp 1200w" sizes="(max-width: 1140px) 100vw, 1100px" '
            f'alt="{esc(HERO[kind])}" width="1200" height="800" loading="eager" fetchpriority="high" decoding="async"></figure>')


def points_section(d: dict, cfg: dict) -> str:
    """The gifts of the site that carry a shop's point multiplier right now (the number and the end are what Rakuten shows for the item; none is invented): four or more, else nothing."""
    B = _b()
    from sites.yorokobu import dataroom
    items = [i for i in dataroom.all_products(d) if B.point_end(i) and i.get("available", True)]
    if len(items) < MIN_POINT_ITEMS:
        return ""
    items.sort(key=lambda i: (-float(i["point_rate"]), -B.score(i), i["code"]))
    cards = "".join(B.item_card(cfg, i) for i in items[:12])
    return (f'<section class="block"><div class="sec-head"><span class="eyebrow">Point up</span><h2>いまポイント倍率が付いている贈り物</h2>'
            f'<p class="sec-lead">当サイトで取り上げた商品のうち、楽天市場が倍率と終了の日時を表示しているものです({esc(d["fetched_label"])}時点)。'
            f'倍率の対象になる条件やポイントの上限は商品ページで確かめてください。エントリーが必要な場合があります。</p></div>'
            f'<ul class="items">{cards}</ul>{B.freshness(d)}</section>')


def sale_page(d: dict, cfg: dict, preview: bool, events: list[dict], href: dict[str, str], now: datetime) -> str:
    B = _b()
    open_ = [e for e in events if _dt(e["end"]) >= now.astimezone(JST)]
    cards = ""
    for e in open_:
        m = message(e, now)
        ph = m["phase"] if m else "ahead"
        tag = m["tag"] if m else "開催予定"
        entry = f'<dt>エントリー</dt><dd>{esc(label(_dt(e["entry_start"])))} から</dd>' if e.get("entry_start") else ""
        cards += (f'<article class="sale-card sale-{ph}"><header><span class="sale-tag">{esc(tag)}</span><h3>{esc(STORE[e["store"]])} {esc(e["name"])}</h3></header>'
                  f'<dl class="sale-dl"><dt>期間</dt><dd>{esc(_range(e))}</dd>{entry}</dl><p>{esc(e["note"])}</p>'
                  f'<p class="more"><a class="btn" href="{esc(href[e["id"]])}" rel="sponsored nofollow noopener" target="_blank">{esc(STORE[e["store"]])}の公式ページを見る</a></p>'
                  f'<p class="sale-src">日程は、{esc(STORE[e["store"]])}の発表で確かめました(確認日 {esc(e["verified"])})。</p></article>')
    latest = (d["c"].get("daily") or [None])[0]
    pick_link = f'<li><a href="/picks/{latest["date"]}/">今日のおすすめギフト</a>で候補を先に選んでおく</li>' if latest else ""
    steps = (
        "<ol class='sale-steps'>"
        "<li><b>贈る日から逆算する。</b>セール中は注文が集まり、届くまでに日数がかかる店もあります。贈る日の1週間前までに届くように注文の日を決めます。</li>"
        "<li><b>先に候補を選んでおく。</b>始まってから探すと時間が足りません。<a href='/for/'>相手から</a>や<a href='/occasion/'>イベントから</a>探して気になるものをリストに入れておきます。</li>"
        "<li><b>エントリーと条件を確かめる。</b>ポイントアップはエントリーが必要な場合があります。対象の条件と上限は各店の公式ページに書かれています。</li>"
        "<li><b>のし・ラッピング・日付指定を確かめる。</b>店ごとに違います。商品ページで先に見ておきます。</li></ol>")
    body = f"""{B.head_band("yellow", "", "セールの日程と贈り物を買うタイミング", "楽天市場とAmazonが発表した、お得に買える日をまとめています。始まる前に候補を選んでおくとその日に迷わず注文できます。", single=True)}
{hero(now)}
<div class="crumbs-wrap">{B.crumbs([("トップ", "/"), ("セールの日程", None)])}</div>
{B.pr_quiet(cfg)}
<section class="block"><div class="sec-head"><h2>いまとこれからのセール</h2></div>{f'<div class="sale-cards">{cards}</div>' if cards else '<p class="notice">いま発表されているセールはありません。決まりしだい、ここに載せます。</p>'}</section>
{points_section(d, cfg)}
<section class="block"><div class="sec-head"><h2>プレゼントをセールで買うときの順番</h2></div>{steps}
<ul class="plain sale-links">{pick_link}<li><a href="/memo/">贈る日を登録して忘れないようにする(たいせつな日メモ)</a></li></ul></section>
<section class="block"><p class="notice">日程は各店が発表した内容です。変更になることがあるため、購入の前に各店の公式ページで確かめてください。当サイトは各店の公式ページへのリンクを紹介し、購入されると報酬が支払われることがあります。</p></section>"""
    return B.page(cfg, preview, path="/sale/", title=f"セールの日程と贈り物を買うタイミング | {cfg['site_name']}", description="楽天市場のお買い物マラソン、Amazonのプライム感謝祭など、お得に買える日とプレゼントを選ぶ順番をまとめました。", body=body, amazon_links=any(e["store"] == "amazon" for e in open_), sale=False)


def build_pages(d: dict, cfg: dict, preview: bool, events: list[dict], href: dict[str, str], now: datetime) -> dict[str, str]:
    if not events:                                           # no event was ever announced here: no page (once there is one, the page stays: its address is not to flip between 200 and 404)
        return {}
    return {"sale/index.html": sale_page(d, cfg, preview, events, href, now)}
