"""SALEカレンダー: 「割引中の個別商品」を API から取れるかの試行(使い捨て。workflow kaidoki-sale-probe.yml が動かす)。

    python -m sites.kaidoki.tools.sale_probe --yahoo --rakuten [--store]

守ること(オーナー厳命 2026-10-17。リポジトリ・ログ・成果物は公開):
  - ログに出すのは、ジャンル名(当サイトの語)・件数・割合・フィールド名・有無だけ。商品名・価格・画像URL・商品URL・店名・アフィリエイトURLは、ログにも標準出力にも出さない。
  - 商品データ(--store のとき)は、サーバーの非公開フォルダ ~/kaidoki-private/ にだけ置く(SSH。XSERVER_SSH_KEY / XSERVER_HOST / XSERVER_USER)。リポジトリ・Actions の成果物・キャッシュには入れない。
  - 鍵(YAHOO_CLIENT_ID / RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY)は、環境変数から読むだけで、出さない。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out" / "kaidoki_private"                 # out/ は .gitignore。ここは作業用で、ここからサーバーの非公開フォルダへ送る
JST = timezone(timedelta(hours=9))
REMOTE_DIR = "kaidoki-private"
YAHOO_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
YAHOO_GAP = 2.2                                         # 1分30回まで
REFERERS = ("https://sale-calendar.com/", "https://yorokobu-present.com/")      # 楽天は、アプリに登録したドメインの Referer が要る

# (slug, SALEカレンダーでの呼び名, 検索語)。呼び名は当サイトの語なので、ログに出してよい
GENRES = [
    ("phone", "スマホ", "スマートフォン"),
    ("pc", "パソコン", "ノートパソコン"),
    ("tv", "テレビ", "液晶テレビ"),
    ("kaden", "生活家電", "掃除機"),
    ("kitchen", "キッチン家電", "炊飯器"),
    ("beauty", "美容", "化粧水"),
    ("game", "ゲーム", "ゲームソフト"),
    ("camera", "カメラ", "ミラーレスカメラ"),
    ("daily", "日用品", "洗剤"),
    ("food", "食品", "米 5kg"),
]


def log(*a) -> None:
    print(*a, flush=True)


def _num(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def to_seconds(ts) -> int:
    """UNIX 時刻。ミリ秒で来ても秒にそろえる(桁で見分ける)。"""
    t = int(_num(ts))
    return t // 1000 if t > 10**11 else t


def paths(obj, prefix="") -> set[str]:
    """フィールド名の一覧(値は見ない)。リストは [] でまとめる。"""
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            out |= paths(v, p)
    elif isinstance(obj, list):
        for v in obj[:1]:
            out |= paths(v, prefix + "[]")
    return out


# ------------------------------------------------------------------ Yahoo!
class YahooError(RuntimeError):
    pass


class Yahoo:
    def __init__(self, client_id: str, gap: float = YAHOO_GAP, wait429: float = 65):
        self.cid, self.gap, self.wait429 = client_id, gap, wait429
        self.calls = 0
        self._last = 0.0

    def search(self, **params) -> dict:
        q = {"appid": self.cid, **{k: v for k, v in params.items() if v is not None}}
        url = YAHOO_URL + "?" + urllib.parse.urlencode(q)
        for attempt in (1, 2):
            wait = self._last + self.gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            req = urllib.request.Request(url, headers={"User-Agent": "sale-calendar.com research (contact via the site)"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt == 1:
                    time.sleep(self.wait429)
                    continue
                raise YahooError(f"HTTP {e.code}") from None          # 本文もURLも持たせない(ID・商品が混ざらない)
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                raise YahooError(type(e).__name__) from None
        raise YahooError("gave up")


def yahoo_sale_view(h: dict, now: int) -> dict:
    """1商品の、セール判定に使う項目だけ(名前・URL・画像は入れない)。"""
    pl = h.get("priceLabel") or {}
    default, disc = int(_num(pl.get("defaultPrice"))), int(_num(pl.get("discountedPrice")))
    start, end = to_seconds(pl.get("periodStart")), to_seconds(pl.get("periodEnd"))
    seller = h.get("seller") or {}
    srev = seller.get("review") or {}
    rev = h.get("review") or {}
    return {
        "has_label": 0 < disc < default,
        "pct": round(100 * (default - disc) / default) if 0 < disc < default else 0,
        "has_period": start > 0 and end > 0,
        "active": start > 0 and end > 0 and start <= now <= end,
        "ends_3d": end > 0 and now <= end <= now + 3 * 86400,
        "seller": seller.get("sellerId") or "",
        "seller_good": int(_num(srev.get("count"))) >= 100 and _num(srev.get("rate")) >= 4.0,
        "best": bool(seller.get("isBestSeller")),
        "item_good": int(_num(rev.get("count"))) >= 10 and _num(rev.get("rate")) >= 4.0,
    }


def yahoo_stats(hits: list[dict], now: int) -> dict:
    v = [yahoo_sale_view(h, now) for h in hits]
    n = len(v) or 1
    pct = Counter()
    for x in v:
        if x["has_label"]:
            pct["<10" if x["pct"] < 10 else "10-29" if x["pct"] < 30 else "30-49" if x["pct"] < 50 else "50+"] += 1
    return {
        "got": len(v), "label": sum(x["has_label"] for x in v), "period": sum(x["has_period"] for x in v), "active_now": sum(x["active"] for x in v),
        "ends_3d": sum(x["ends_3d"] for x in v), "pct": dict(pct), "shops": len({x["seller"] for x in v if x["seller"]}),
        "good_shop_items": sum(x["seller_good"] for x in v), "good_shops": len({x["seller"] for x in v if x["seller_good"] and x["seller"]}),
        "best_shop_items": sum(x["best"] for x in v), "good_item": sum(x["item_good"] for x in v),
        "label_share": round(sum(x["has_label"] for x in v) / n, 2),
    }


def yahoo_store_row(h: dict) -> dict:
    """サーバーの非公開フォルダに置く行。公開しない(ログ・リポジトリに出さない)。"""
    pl, seller, rev = h.get("priceLabel") or {}, h.get("seller") or {}, h.get("review") or {}
    return {
        "code": h.get("code"), "name": h.get("name"), "url": h.get("url"), "image": (h.get("image") or {}).get("medium"),
        "price": h.get("price"), "default_price": pl.get("defaultPrice"), "discounted_price": pl.get("discountedPrice"),
        "period_start": pl.get("periodStart"), "period_end": pl.get("periodEnd"),
        "review_count": rev.get("count"), "review_rate": rev.get("rate"),
        "shop": seller.get("name"), "shop_id": seller.get("sellerId"), "shop_review_count": (seller.get("review") or {}).get("count"),
        "shop_review_rate": (seller.get("review") or {}).get("rate"), "best_seller": seller.get("isBestSeller"),
        "genre": (h.get("genreCategory") or {}).get("name"),
    }


def run_yahoo(cid: str, store: dict | None, pages: int = 3, client: Yahoo | None = None, now: int | None = None) -> dict:
    y = client or Yahoo(cid)
    now = now or int(time.time())
    log("== Yahoo!ショッピング v3 itemSearch (is_discounted=true) ==")
    field_count: Counter = Counter()
    total_hits = 0
    summary: dict = {}
    page_size = 100
    for slug, label, kw in GENRES:
        hits: list[dict] = []
        avail = None
        for p in range(pages):
            try:
                r = y.search(query=kw, is_discounted="true", in_stock="true", sort="-review_count", results=page_size, start=1 + p * page_size)
            except YahooError as e:
                if p == 0 and page_size == 100:
                    log(f"[{label}] results=100 は {e}。50件で試し直す")
                    page_size = 50
                    try:
                        r = y.search(query=kw, is_discounted="true", in_stock="true", sort="-review_count", results=page_size, start=1)
                    except YahooError as e2:
                        log(f"[{label}] 失敗: {e2}")
                        break
                else:
                    log(f"[{label}] ページ{p + 1}で失敗: {e}")
                    break
            if avail is None:
                avail = r.get("totalResultsAvailable")
            hs = r.get("hits") or []
            hits += hs
            for h in hs:
                field_count.update(paths(h))
            if len(hs) < page_size:
                break
        total_hits += len(hits)
        st = yahoo_stats(hits, now)
        st["total_available"] = avail
        # 期間つきで絞る(開始・終了のフィルタが効くか): 今日から3日以内に終わる割引
        try:
            r2 = y.search(query=kw, is_discounted="true", in_stock="true", sale_end_from=now, sale_end_to=now + 3 * 86400, results=1)
            st["total_ending_within_3d_filter"] = r2.get("totalResultsAvailable")
        except YahooError as e:
            st["total_ending_within_3d_filter"] = f"error {e}"
        # 比較: is_discounted なしの上位100件のうち、priceLabel で割引と読める割合
        try:
            r3 = y.search(query=kw, in_stock="true", sort="-review_count", results=100)
            st["control_label_share"] = yahoo_stats(r3.get("hits") or [], now)["label_share"]
        except YahooError as e:
            st["control_label_share"] = f"error {e}"
        summary[slug] = st
        log(f"[{label}] " + json.dumps(st, ensure_ascii=False, sort_keys=True))
        if store is not None:
            seen = {}
            for h in hits:
                v = yahoo_sale_view(h, now)
                if v["has_label"] and h.get("code"):
                    seen.setdefault(h["code"], yahoo_store_row(h))
            store.setdefault("genres", {})[slug] = {"label": label, "query": kw, "items": list(seen.values())}
    # ジャンル指定なし(全カテゴリ)で割引だけ: query 無しで通るか
    try:
        r = y.search(genre_category_id=1, is_discounted="true", in_stock="true", sort="-review_count", results=1)
        log(f"[全カテゴリ genre_category_id=1] total_available={r.get('totalResultsAvailable')}")
    except YahooError as e:
        log(f"[全カテゴリ genre_category_id=1] {e}")
    log("フィールド名(出現数/取得総数 %d):" % total_hits)
    for k, c in sorted(field_count.items()):
        log(f"  {k}: {c}")
    log(f"Yahoo! 呼び出し回数: {y.calls}")
    return summary


# ------------------------------------------------------------------ 楽天
def rakuten_view(it: dict, now: int) -> dict:
    it = it.get("Item", it)
    rate = _num(it.get("pointRate"), 1)
    end = str(it.get("pointRateEndTime") or "")
    start = str(it.get("pointRateStartTime") or "")
    end_t = None
    if end:
        try:
            end_t = int(datetime.strptime(end[:16], "%Y-%m-%d %H:%M").replace(tzinfo=JST).timestamp())
        except ValueError:
            end_t = None
    return {"up": rate >= 2, "up_with_end": rate >= 2 and bool(end), "rate": rate, "start": bool(start),
            "ends_3d": end_t is not None and now <= end_t <= now + 3 * 86400, "active": end_t is not None and end_t >= now,
            "shop": it.get("shopCode") or "", "item_good": int(_num(it.get("reviewCount"))) >= 10 and _num(it.get("reviewAverage")) >= 4.0}


def rakuten_stats(items: list[dict], now: int) -> dict:
    v = [rakuten_view(i, now) for i in items]
    rates = Counter()
    for x in v:
        if x["up"]:
            rates["2-4" if x["rate"] < 5 else "5-9" if x["rate"] < 10 else "10+"] += 1
    return {"got": len(v), "point_up": sum(x["up"] for x in v), "point_up_with_end": sum(x["up_with_end"] for x in v), "with_start": sum(x["start"] for x in v),
            "active_now": sum(x["active"] for x in v), "ends_3d": sum(x["ends_3d"] for x in v), "rates": dict(rates),
            "shops": len({x["shop"] for x in v if x["shop"]}), "good_item": sum(x["item_good"] for x in v)}


def rakuten_store_row(it: dict) -> dict:
    it = it.get("Item", it)
    return {k: it.get(k) for k in ("itemCode", "itemName", "itemUrl", "affiliateUrl", "itemPrice", "pointRate", "pointRateStartTime", "pointRateEndTime",
                                   "reviewCount", "reviewAverage", "shopName", "shopCode")} | {"image": (it.get("mediumImageUrls") or [None])[0]}


def run_rakuten(app: str, key: str, store: dict | None, aff: str | None, now: int | None = None, make_client=None) -> dict:
    from sokuhou import rakuten as R
    now = now or int(time.time())
    log("== 楽天 Ichiba Item Search ==")
    last: dict = {}

    def capture(url: str, headers: dict) -> bytes:
        body = R._urllib_transport(url, headers)
        try:
            last["count"] = json.loads(body.decode("utf-8")).get("count")
        except ValueError:
            last["count"] = None
        return body

    client = None
    for ref in REFERERS:
        c = (make_client or (lambda r: R.Client(app_id=app, access_key=key, referer=r, affiliate_id=aff, min_interval=1.2, transport=capture)))(ref)
        try:
            c.search(keyword="洗剤", hits=1)
            client = c
            log(f"楽天: Referer {urllib.parse.urlsplit(ref).netloc} で通った")
            break
        except R.RakutenError as e:
            m = re.search(r"HTTP (\d+)", str(e))
            log(f"楽天: Referer {urllib.parse.urlsplit(ref).netloc} は通らない({'HTTP ' + m.group(1) if m else 'エラー'})")
    if client is None:
        log("楽天: どの Referer でも通らなかった。ここで止める")
        return {}
    summary: dict = {}
    fields: Counter = Counter()
    for slug, label, kw in GENRES:
        st: dict = {}
        for name, extra in (("base", {}), ("flag", {"pointRateFlag": 1})):
            items: list = []
            for page in (1, 2, 3):
                try:
                    got = client.search(keyword=kw, hits=30, page=page, availability=1, sort="standard", **extra)
                except R.RakutenError as e:
                    m = re.search(r"HTTP (\d+)", str(e))
                    st[name + "_error"] = ("HTTP " + m.group(1)) if m else "error"
                    break
                total = last.get("count")
                items += got
                for it in got:
                    fields.update(paths(it.get("Item", it)))
                if len(got) < 30:
                    break
            st[name] = {"total_available": last.get("count"), **rakuten_stats(items, now)}
            if store is not None and name == "flag":
                rows = {}
                for it in items:
                    v = rakuten_view(it, now)
                    if v["up_with_end"]:
                        rows.setdefault(it.get("Item", it).get("itemCode"), rakuten_store_row(it))
                store.setdefault("genres", {})[slug] = {"label": label, "query": kw, "items": list(rows.values())}
        summary[slug] = st
        log(f"[{label}] " + json.dumps(st, ensure_ascii=False, sort_keys=True))
    log("フィールド名(出現数):")
    for k, c in sorted(fields.items()):
        log(f"  {k}: {c}")
    log(f"楽天 呼び出し回数: {client.calls}")
    return summary


# ------------------------------------------------------------------ サーバーの非公開フォルダへ
def push_private(files: dict[str, dict]) -> int:
    key, host, user = (os.environ.get(k, "") for k in ("XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER"))
    if not (key and host and user):
        log("非公開フォルダ: SSH の秘密が無い。保存しない(件数だけ報告)")
        return 0
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tf:
        for name, data in files.items():
            b = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size = len(b)
            tf.addfile(ti, io.BytesIO(b))
    with tempfile.TemporaryDirectory() as td:
        kf, kh = Path(td) / "key", Path(td) / "known_hosts"
        kf.write_text(key.strip() + "\n", encoding="utf-8")
        kf.chmod(0o600)
        ssh = ["ssh", "-i", str(kf), "-p", os.environ.get("SSH_PORT", "10022"), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
               "-o", f"UserKnownHostsFile={kh}", "-o", "ConnectTimeout=20", f"{user}@{host}"]
        d = f"~/{REMOTE_DIR}"
        remote = f"mkdir -p {d} && chmod 700 {d} && cd {d} && rm -rf .in && mkdir .in && cd .in && tar xf - && chmod 600 * && mv -f * .. && cd .. && rmdir .in && ls -l | wc -l"
        for wait in (0, 10, 30):
            time.sleep(wait)
            p = subprocess.run(ssh + [remote], input=buf.getvalue(), capture_output=True)
            if p.returncode == 0:
                log(f"非公開フォルダ ~/{REMOTE_DIR}/ に {len(files)} ファイルを置いた(合計 {len(buf.getvalue()) // 1024} KB)")
                return 0
            log(f"非公開フォルダ: 接続に失敗({p.returncode})")
    return 1


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--yahoo", action="store_true")
    ap.add_argument("--rakuten", action="store_true")
    ap.add_argument("--store", action="store_true", help="商品データをサーバーの非公開フォルダに置く")
    ap.add_argument("--pages", type=int, default=3)
    a = ap.parse_args(argv)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    files: dict[str, dict] = {}
    rc = 0
    if a.yahoo:
        cid = os.environ.get("YAHOO_CLIENT_ID")
        if not cid:
            log("YAHOO_CLIENT_ID が無い。Yahoo! は試さない")
            rc = 1
        else:
            store = {"source": "yahoo itemSearch is_discounted", "date": today} if a.store else None
            run_yahoo(cid, store, pages=a.pages)
            if store is not None:
                files[f"kaidoki_sale_yahoo_{today}.json"] = store
                log("Yahoo! 取得: " + ", ".join(f"{g['label']}={len(g['items'])}" for g in store["genres"].values()))
    if a.rakuten:
        app, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
        if not (app and key):
            log("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が無い。楽天は試さない")
            rc = 1
        else:
            cfg = json.loads((ROOT / "sites" / "kaidoki" / "config.json").read_text(encoding="utf-8"))
            store = {"source": "rakuten Item Search pointRateFlag=1", "date": today} if a.store else None
            run_rakuten(app, key, store, cfg.get("rakuten_affiliate_id"))
            if store is not None:
                files[f"kaidoki_sale_rakuten_{today}.json"] = store
                log("楽天 取得(ポイント変倍・終了時刻つき): " + ", ".join(f"{g['label']}={len(g['items'])}" for g in store.get("genres", {}).values()))
    if files:
        rc = max(rc, push_private(files))
    return rc


if __name__ == "__main__":
    sys.exit(main())
