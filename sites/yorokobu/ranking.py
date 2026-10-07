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
PLACES = 30                      # one API page
KEEP = 30                        # places kept per segment in the snapshot

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


# Genres whose sales ranking is a good place to look for a gift (genre ids checked against ranking.rakuten.co.jp/daily/<id>/ on 2026-10-07).
# A genre is asked for alone (the API does not allow genreId together with age or sex).
GENRES = [
    ("sweets", 551167, "スイーツ・お菓子"), ("flower", 100005, "花・ガーデン・DIY"), ("jewelry", 216129, "ジュエリー・アクセサリー"),
    ("bag", 216131, "バッグ・小物・ブランド雑貨"), ("watch", 558929, "腕時計"), ("beer", 510915, "ビール・洋酒"), ("sake", 510901, "日本酒・焼酎"),
    ("wine", 100317, "ワイン"), ("interior", 100804, "インテリア・寝具・収納"), ("kitchen", 558944, "キッチン用品・食器・調理器具"),
    ("beauty", 100939, "美容・コスメ・香水"), ("ladies", 100371, "レディースファッション"), ("mens", 551177, "メンズファッション"),
    ("hobby", 101164, "ホビー"), ("toy", 566382, "おもちゃ"), ("baby", 100533, "キッズ・ベビー・マタニティ"),
]


def genre_segments() -> list[dict]:
    return [{"slug": f"g-{slug}", "genre": gid, "label": label, "kind": "genre"} for slug, gid, label in GENRES]


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


def snapshot_segment(client: rakuten.Client, seg: dict) -> list[dict]:
    raw = client.ranking(genreId=seg["genre"], page=1) if seg.get("kind") == "genre" else client.ranking(age=seg["age"], sex=seg["sex"], page=1)
    out = []
    for i, r in enumerate(raw[:PLACES]):
        it = _item(r, i + 1)
        if it:
            out.append(it)
    return out


def update(store: dict | None, fresh: dict[str, list[dict]], today: date) -> dict:
    """Merge today's snapshots into the store: replace the latest items, add today's codes to the history, drop days older than HISTORY_DAYS.
    A segment that failed to fetch today (absent from `fresh`) keeps its previous data untouched."""
    store = dict(store or {})
    segs = dict(store.get("segments") or {})
    for slug, items in fresh.items():
        if not items:
            continue
        old = segs.get(slug, {})
        history = dict(old.get("history") or {})
        history[today.isoformat()] = [it["code"] for it in sorted(items, key=lambda i: i["rank"])][:KEEP]
        cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
        history = {d: codes for d, codes in sorted(history.items()) if d >= cutoff}
        segs[slug] = {"label": SEGMENTS[slug]["label"], "kind": SEGMENTS[slug]["kind"], "date": today.isoformat(), "items": sorted(items, key=lambda i: i["rank"])[:KEEP], "history": history}
    return {"version": 1, "updated": today.isoformat(), "segments": segs}


def movers(seg: dict) -> dict:
    """What changed in one segment between the two latest dates of its history (empty lists when there is only one day).
    risers: (code, places gained) sorted by gain; entered: codes not in the previous list; stay: code -> consecutive days present up to the latest."""
    hist = seg.get("history") or {}
    days = sorted(hist)
    latest = hist[days[-1]] if days else []
    out = {"days": len(days), "risers": [], "entered": [], "stay": {}}
    if days:
        run = {}
        for code in latest:
            n = 0
            for d in reversed(days):
                if code in hist[d]:
                    n += 1
                else:
                    break
            run[code] = n
        out["stay"] = run
    if len(days) >= 2:
        prev = hist[days[-2]]
        pos = {c: i + 1 for i, c in enumerate(prev)}
        for i, code in enumerate(latest):
            if code in pos:
                gain = pos[code] - (i + 1)
                if gain > 0:
                    out["risers"].append((code, gain))
            else:
                out["entered"].append(code)
        out["risers"].sort(key=lambda t: (-t[1], latest.index(t[0])))
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
         "牛丼の具", "牛めしの具", "ハイボール", "エクオール", "ピックアップ", "予約", "再販", "お一人様", "1人1点", "一人様")


def shown(item: dict, filters: dict) -> bool:
    """A ranked product the page may show: for sale, above the site's minimum price, none of the site's ng words, not a daily necessity,
    and passing the same memorial / adult-only rules as the gift pages (no recipient is assumed)."""
    if not item.get("available", True) or item.get("price", 0) < filters.get("min_price", 0):
        return False
    name = item["name"]
    if any(w and w in name for w in filters.get("ng_words", [])) or any(w in name for w in DAILY):
        return False
    return relevance.fits(name, None)


def view(store: dict | None, filters: dict, min_items: int = 8) -> dict | None:
    """What the pages need: per segment the shown products (with their real Rakuten place), the price facts, and today's movers; plus the
    biggest risers of all segments.  None when there is no usable data (the site then has no ranking pages)."""
    if not store:
        return None
    segs: dict[str, dict] = {}
    for slug, s in (store.get("segments") or {}).items():
        if slug not in SEGMENTS:
            continue
        items = [it for it in s.get("items", []) if shown(it, filters)]
        if len(items) < min_items:
            continue
        mv = movers(s)
        ok = {it["code"]: it for it in items}
        segs[slug] = {
            "slug": slug, "label": SEGMENTS[slug]["label"], "kind": SEGMENTS[slug]["kind"], "date": s.get("date") or store.get("updated"), "items": items, "facts": price_facts(items),
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
    client = rakuten.Client(app, key, cfg["site_url"].rstrip("/") + "/", affiliate_id=None)
    now = datetime.now(JST)
    fresh = collect(client, now)
    if not any(fresh.values()):
        sys.exit("no ranking could be fetched; the file is left unchanged")
    out = Path(a.out)
    store = update(load(out), fresh, now.date())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ranking: {sum(1 for v in fresh.values() if v)} of {len(SEGMENTS)} segments, {client.calls} calls -> {out}")


if __name__ == "__main__":
    main()
