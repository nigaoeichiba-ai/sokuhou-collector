"""Rakuten Ichiba sales ranking by age and sex: a daily snapshot, a short history, and what changed since yesterday.

    python -m sites.yorokobu.ranking --out data/yorokobu_ranking.json     (needs RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY)

The file keeps, per segment (age 10-50 x sex), today's top places in full and a compact history (date -> product codes in rank order) of the last
HISTORY_DAYS days.  The site build only READS this file (no network at build time): the pages show the latest snapshot with its date, and what moved
(risers, new entries, how many days in a row a product has stayed) is computed from the history, so every sentence is a fact from the data.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sites.yorokobu import relevance
from sokuhou import rakuten

HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
HISTORY_DAYS = 45
PLACES = 30                      # places per API page
REQUEST_GAP = 2.5                # seconds between requests: the deploy fetches from the same application ID at the same time (limit about 1 request/s)
PAGES = 4                        # pages fetched per segment: the top 120 (gift-like products are rare near the top of a sales ranking)

AGES = (10, 20, 30, 40, 50)
SEXES = ((1, "f", "女性"), (0, "m", "男性"))


def segments() -> list[dict]:
    """The ten age x sex segments, in the order the site lists them."""
    out = []
    for sex, letter, word in SEXES:
        for age in AGES:
            label = f"{age}代以上{word}" if age == 50 else f"{age}代{word}"
            out.append({"slug": f"{letter}{age}", "age": age, "sex": sex, "label": label})
    return out


# Genres whose sales ranking is a good place to look for a gift.  Ids are Rakuten's own and were read from ranking.rakuten.co.jp/daily/<id>/ on 2026-10-07
# (the sub-genre tree is on each genre's page); a genre is asked for alone (the API does not allow genreId together with age or sex).
# (slug, genre id, label, strict, recipient).  `recipient` (default none = an adult) is the person the genre is for: the fit rules in relevance.py drop titles
# that say ベビー/キッズ/赤ちゃん from an adult's list, so the baby and children's genres name "baby" / "child".  strict=False marks a genre that Rakuten itself makes for presents (出産祝い・ギフト, カタログギフト ...): there the title
# need not say "gift"; in every other genre a product is shown only when its title says it is a gift (GIFT_HINTS).
GENRES = [
    # made for presents
    ("baby-gift", 508445, "出産祝い・ギフト", False, "baby"), ("catalog", 566732, "カタログギフト", False), ("ecatalog", 568914, "eカタログギフト", False),
    ("sweets-set", 568410, "各種スイーツ・お菓子セット", False), ("hatsu-sekku", 566487, "雛祭り・端午の節句", False, "baby"),
    ("jewelry-pair", 301966, "ペアアクセサリー", False), ("bridal", 551853, "ブライダルジュエリー・アクセサリー", False), ("watch-pair", 302123, "ペアウォッチ", False),
    # everyday genres where gifts sit among the sales: only products whose title says gift
    ("sweets", 551167, "スイーツ・お菓子"), ("cookies", 201153, "クッキー・焼き菓子"), ("chocolate", 201136, "チョコレート"), ("wagashi", 509708, "和菓子"),
    ("flower", 113084, "花・観葉植物"), ("jewelry", 216129, "ジュエリー・アクセサリー"), ("watch", 558929, "腕時計"), ("bag", 216131, "バッグ・小物・ブランド雑貨"),
    ("scarf", 560100, "マフラー・スカーフ"), ("handkerchief", 502464, "ハンカチ・ハンドタオル"), ("perfume", 111120, "香水・フレグランス"), ("beauty", 100939, "美容・コスメ・香水"),
    ("tableware", 566114, "食器・カトラリー・グラス"), ("coffee-tea", 566115, "コーヒー・お茶用品"), ("kitchen", 558944, "キッチン用品・食器・調理器具"),
    ("towel", 100664, "タオル"), ("bedding", 215566, "寝具"), ("decor", 100863, "インテリア小物・置物"), ("interior", 100804, "インテリア・寝具・収納"),
    ("sake", 510901, "日本酒・焼酎"), ("wine", 100317, "ワイン"), ("whisky", 100330, "ウイスキー"),
    ("plush", 566384, "ぬいぐるみ・人形"), ("baby-toy", 201591, "ベビー向けおもちゃ", True, "baby"), ("edu-toy", 201603, "知育玩具・学習玩具", True, "child"),
]
# Left out after reading real data (2026-10-07): the top level of fashion, hobby, toys and baby goods (everyday clothes, seasonal decoration, nappies whose titles merely
# contain the word プレゼント), and beer & spirits (its gift-like places are the same wines as in ワイン).  A first version also dropped the baby genre because
# the first 30 places were nappies; that was wrong: Rakuten has 出産祝い・ギフト, which is now fetched.


def genre_segments() -> list[dict]:
    return [{"slug": f"g-{g[0]}", "genre": g[1], "label": g[2], "kind": "genre", "strict": g[3] if len(g) > 3 else True,
             "recipient": g[4] if len(g) > 4 else None} for g in GENRES]


def all_segments() -> list[dict]:
    """Genres first (the better source of gifts), then the ten age x sex lists."""
    return genre_segments() + [{**s, "kind": "people"} for s in segments()]


SEGMENTS = {s["slug"]: s for s in all_segments()}


def _item(raw: dict, place: int) -> dict | None:
    """The fields the pages need, in the same shape as the other product lists; None when the item cannot be shown."""
    base = rakuten.normalize(raw)
    if not base:
        return None
    base["rank"] = int(rakuten._num(raw.get("rank") or raw.get("Item", {}).get("rank"), place)) or place
    return base


def snapshot_segment(client: rakuten.Client, seg: dict, pages: int = PAGES) -> list[dict]:
    """The top places of one segment (PLACES per page, `pages` pages; fewer when the ranking ends sooner)."""
    out: list[dict] = []
    for page in range(1, pages + 1):
        raw = (client.ranking(genreId=seg["genre"], page=page) if seg.get("kind") == "genre"
               else client.ranking(age=seg["age"], sex=seg["sex"], page=page))
        for i, r in enumerate(raw[:PLACES]):
            it = _item(r, (page - 1) * PLACES + i + 1)
            if it:
                out.append(it)
        if len(raw) < PLACES:
            break
    return out


def _ranked(entry: list) -> dict[str, int]:
    """One history entry as {code: place}.  New entries are [[code, place], ...]; the first snapshots stored only [code, ...] in rank order."""
    out: dict[str, int] = {}
    for i, e in enumerate(entry):
        if isinstance(e, (list, tuple)):
            out[e[0]] = int(e[1])
        else:
            out[e] = i + 1
    return out


def update(store: dict | None, fresh: dict[str, list[dict]], today: date, keep=None, depth: int = PAGES * PLACES) -> dict:
    """Merge today's snapshots into the store.  `keep` (a function of the segment slug and one item) decides which products are stored at all: the site only ever shows
    gift-like products (shown()), so only those are kept, each with its real Rakuten place, and the history holds [code, place] pairs of them.
    A segment that failed to fetch today (absent from `fresh`) keeps its previous data untouched."""
    store = dict(store or {})
    segs = {k: v for k, v in (store.get("segments") or {}).items() if k in SEGMENTS}      # a segment that is no longer fetched is dropped
    for slug, raw_items in fresh.items():
        if not raw_items:                       # the fetch failed or came back empty: keep what we had
            continue
        items = [it for it in raw_items if keep is None or keep(slug, it)]
        old = segs.get(slug, {})
        history = dict(old.get("history") or {})
        ordered = sorted(items, key=lambda i: i["rank"])
        history[today.isoformat()] = [[it["code"], it["rank"]] for it in ordered]
        cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
        history = {d: codes for d, codes in sorted(history.items()) if d >= cutoff}
        segs[slug] = {"label": SEGMENTS[slug]["label"], "kind": SEGMENTS[slug]["kind"], "date": today.isoformat(), "depth": depth, "items": ordered, "history": history}
    return {"version": 2, "updated": today.isoformat(), "segments": segs}


def movers(seg: dict) -> dict:
    """What changed in one segment between the two latest dates of its history (empty lists when there is only one day).
    risers: (code, places gained in Rakuten's own ranking) sorted by gain; entered: codes that were not in the previous day's stored list;
    stay: code -> consecutive days present up to the latest."""
    hist = {d: _ranked(e) for d, e in (seg.get("history") or {}).items()}
    days = sorted(hist)
    latest = hist[days[-1]] if days else {}
    out = {"days": len(days), "risers": [], "entered": [], "stay": {}}
    if days:
        out["stay"] = {code: next((k for k, d in enumerate(reversed(days)) if code not in hist[d]), len(days)) for code in latest}
    if len(days) >= 2:
        prev = hist[days[-2]]
        for code, place in sorted(latest.items(), key=lambda kv: kv[1]):
            if code in prev:
                if prev[code] - place > 0:
                    out["risers"].append((code, prev[code] - place))
            else:
                out["entered"].append(code)
        out["risers"].sort(key=lambda t: (-t[1], latest[t[0]]))
    return out


def price_facts(items: list[dict]) -> dict | None:
    """Plain numbers about a list of products (median price, how many are 3,000 yen or less / 10,000 yen or more)."""
    prices = [it["price"] for it in items if it.get("price")]
    if len(prices) < 5:
        return None
    return {"n": len(prices), "median": int(statistics.median(prices)), "min": min(prices), "max": max(prices),
            "le3000": sum(p <= 3000 for p in prices), "ge10000": sum(p >= 10000 for p in prices)}


# Daily necessities and consumables sell the most but are not what this site is about; the page says they are left out.
DAILY = ("トイレットペーパー", "ティッシュ", "ボックスティッシュ", "洗剤", "柔軟剤", "詰め替え", "詰替", "おむつ", "オムツ", "マスク", "ミネラルウォーター", "天然水",
         "炭酸水", "お米", "無洗米", "ペットボトル", "ゴミ袋", "ごみ袋", "キッチンペーパー", "生理用品", "ナプキン", "歯ブラシ", "電池", "サプリ", "プロテイン",
         "ペットフード", "ドッグフード", "キャットフード", "猫砂", "目薬", "湿布", "カイロ", "乾電池", "水 2L", "水2L", "2L×", "ケース販売",
         # contact lenses and medical supplies, discs and concert editions, diapers, staples and bulk food, supplements, shop-lottery and office goods
         "コンタクト", "カラコン", "ワンデー", "2week", "ツーウィーク", "1day", "Blu-ray", "DVD", "初回盤", "初回限定盤", "通常盤", "初回生産", "初回仕様",
         "メリーズ", "ムーニー", "パンパース", "グーン", "マミーポコ", "オムツ", "白米", "無洗米", "ブレンド米", "玄米", "雑穀米", "ミックスナッツ", "アーモンド 1kg",
         "福袋", "おせち", "業務用", "冷凍食品", "骨取り", "切り身", "切身", "クレアチン", "ペットシーツ", "ロイヤルカナン", "浄水", "カートリッジ", "洗濯洗剤",
         "ガチャ", "パーティション", "AED", "ゴミ収集", "コピー用紙", "コーヒー豆", "ドライフルーツ", "スーパードライ", "ミルクティー", "お茶 500ml",
         "牛丼の具", "牛めしの具", "ハイボール", "エクオール", "ピックアップ", "予約", "再販", "お一人様", "1人1点", "一人様",
         # seasonal decoration and costumes
         "クリスマスツリー", "ツリー", "オーナメント", "イルミネーション", "コスプレ", "ハロウィン", "仮装", "衣装", "ワークパンツ", "チノパン", "ワイシャツ", "スーツケース")


# The ranking says what SELLS, not what is given as a present (the first real snapshot showed cases of cheap shochu, solar garden lights, work shirts).
# The API carries no gift flag, so a product is shown only when its own title says it is meant as a gift: one of these words must appear in it.
GIFT_HINTS = ("ギフト", "プレゼント", "贈り物", "贈答", "内祝", "お祝い", "祝い", "母の日", "父の日", "敬老", "結婚祝", "出産祝", "退職", "のし", "熨斗",
              "名入れ", "お返し", "詰め合わせ", "詰合せ", "詰め合せ", "アソート", "花束", "ブーケ", "アレンジメント", "ラッピング", "贈る", "お礼", "手土産", "化粧箱",
              "ペア", "ホワイトデー", "お歳暮", "お中元", "お見舞い", "引き出物", "ご挨拶")
# (「誕生日」「クリスマス」「バレンタイン」だけでは、贈り物と判定しない: 商品名に季節の語を詰め込んだ、飾りや衣装や普段使いの品が混ざるため)
# bulk packs of drink are not presents even when the title says ギフト
BULK = ("1ケース", "ケース販売", "ケース(", "紙パック", "パック 1.8L", "パック 1800ml", "1.8Lパック", "1800mlパック", "×6本", "×12本", "×24本", "×48本", "24本入", "48本")
MAX_PRICE = 30000


def shown(item: dict, filters: dict, strict: bool = True, recipient: str | None = None) -> bool:
    """A ranked product the page may show: for sale, above the site's minimum and below MAX_PRICE, none of the site's ng words, not a daily
    necessity or a bulk pack, a title that says it is a gift (GIFT_HINTS), and passing the same memorial / adult-only rules as the gift pages."""
    if not item.get("available", True) or not filters.get("min_price", 0) <= item.get("price", 0) <= MAX_PRICE:
        return False
    name = item["name"]
    if any(w and w in name for w in filters.get("ng_words", [])) or any(w in name for w in DAILY) or any(w in name for w in BULK):
        return False
    if strict and not any(w in name for w in GIFT_HINTS):
        return False
    return relevance.fits(name, recipient)


def view(store: dict | None, filters: dict, min_items: int = 8) -> dict | None:
    """What the pages need: per segment the shown products (with their real Rakuten place), the price facts, and today's movers; plus the
    biggest risers of all segments.  None when there is no usable data (the site then has no ranking pages)."""
    if not store:
        return None
    segs: dict[str, dict] = {}
    for slug, s in (store.get("segments") or {}).items():
        if slug not in SEGMENTS:
            continue
        strict = SEGMENTS[slug].get("strict", True)
        items = [it for it in s.get("items", []) if shown(it, filters, strict, SEGMENTS[slug].get("recipient"))]
        if len(items) < min_items:
            continue
        mv = movers(s)
        ok = {it["code"]: it for it in items}
        segs[slug] = {
            "slug": slug, "label": SEGMENTS[slug]["label"], "kind": SEGMENTS[slug]["kind"], "date": s.get("date") or store.get("updated"), "items": items, "facts": price_facts(items),
            "depth": int(s.get("depth") or PLACES),
            "days": mv["days"],
            "risers": [(ok[c], g) for c, g in mv["risers"] if c in ok][:6],
            "entered": [ok[c] for c in mv["entered"] if c in ok][:6] if mv["days"] >= 2 else [],
            "stay": sorted(((ok[c], n) for c, n in mv["stay"].items() if c in ok and n >= 3), key=lambda t: (-t[1], t[0]["rank"]))[:6],
        }
    if not segs:
        return None
    allr = sorted(((sg["label"], sg["slug"], it, g) for sg in segs.values() for it, g in sg["risers"]), key=lambda t: (-t[3], t[2]["rank"]))
    seen, top = set(), []
    for lab, slug, it, g in allr:       # one product once, even when it rises in several segments
        if it["code"] not in seen:
            seen.add(it["code"])
            top.append((lab, slug, it, g))
    date_ = max(sg["date"] for sg in segs.values())
    return {"date": date_, "segments": segs, "risers": top[:8], "order": [sg["slug"] for sg in all_segments() if sg["slug"] in segs]}


def date_label(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.year}年{d.month}月{d.day}日"


def load(path: Path | None = None) -> dict | None:
    path = path or HERE.parents[1] / "data" / "yorokobu_ranking.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("segments") else None


def collect(client: rakuten.Client, now: datetime | None = None) -> dict[str, list[dict]]:
    fresh: dict[str, list[dict]] = {}
    for seg in all_segments():
        try:
            fresh[seg["slug"]] = snapshot_segment(client, seg)
        except rakuten.RakutenError as e:
            print(f"ranking {seg['slug']} failed: {e}", file=sys.stderr)
    return fresh


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parents[1] / "data" / "yorokobu_ranking.json"))
    a = ap.parse_args()
    app, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app and key):
        sys.exit("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY are not set")
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    client = rakuten.Client(app, key, cfg["site_url"].rstrip("/") + "/", affiliate_id=None, min_interval=REQUEST_GAP)
    now = datetime.now(JST)
    fresh = collect(client, now)
    if not any(fresh.values()):
        sys.exit("no ranking could be fetched; the file is left unchanged")
    out = Path(a.out)
    from sites.yorokobu import content as ct
    filters = ct.load()["filters"]
    store = update(load(out), fresh, now.date(), keep=lambda slug, it: shown(it, filters, SEGMENTS[slug].get("strict", True), SEGMENTS[slug].get("recipient")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kept = {k: len(v["items"]) for k, v in store["segments"].items()}
    print(f"ranking: {sum(1 for v in fresh.values() if v)} of {len(SEGMENTS)} segments fetched, {client.calls} calls; gift-like products kept: {kept} -> {out}")


if __name__ == "__main__":
    main()
