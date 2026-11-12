"""SALEカレンダー: 毎日の取得。Yahoo!ショッピングの割引中の商品を、店ごとに集計して、サーバーの非公開フォルダに置く(workflow kaidoki-sale-daily.yml が動かす)。

    python -m sites.kaidoki.tools.yahoo_shops [--store] [--pages 3]

守ること(オーナー厳命 2026-10-17。リポジトリ・ログ・成果物・キャッシュは公開):
  - ログに出すのは、ジャンル名(当サイトの語)と件数だけ。店名・店のURL・商品名・価格・画像は、ログにも標準出力にも出さない。
  - 集計(店ごとの件数・割引率・終了日・店の評価)は、サーバーの非公開フォルダ ~/kaidoki-private/yahoo_shops.json にだけ置く(SSH)。ファイルを作業フォルダに書かない。
  - 鍵(YAHOO_CLIENT_ID)は環境変数から読むだけで、出さない。
  - 1件も取れなかった日は置かない(古いファイルは、取得日が古いので、PHP が自分で隠す)。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from sites.kaidoki import shops as S
from sites.kaidoki.tools import sale_probe as P


def log(*a) -> None:
    print(*a, flush=True)


def fetch_genre(y: P.Yahoo, words: list[str], pages: int, label: str, page_size: int = 100) -> list[dict]:
    hits: list[dict] = []
    for kw in words:
        for p in range(pages):
            try:
                r = y.search(query=kw, is_discounted="true", in_stock="true", sort="-review_count", results=page_size, start=1 + p * page_size)
            except P.YahooError as e:
                log(f"[{label}] 検索語{words.index(kw) + 1}・ページ{p + 1}で失敗: {e}")        # 例外の文には URL も本文も入らない
                break
            hs = r.get("hits") or []
            hits += hs
            if len(hs) < page_size:
                break
    return hits


def run(cid: str, pages: int = 3, client: P.Yahoo | None = None, now: int | None = None) -> dict:
    y = client or P.Yahoo(cid)
    now = now or int(time.time())
    today = datetime.fromtimestamp(now, S.JST).strftime("%Y-%m-%d")
    by_genre: dict[str, list[dict]] = {}
    for slug, label, words in S.GENRES:
        by_genre[slug] = fetch_genre(y, words, pages, label)
        log(f"[{label}] 割引中の商品 {len(by_genre[slug])}件を確認")
    db = S.aggregate(by_genre, now, today)
    log("店の集計(評価 %d件以上・%.1f以上の店だけ): " % (S.MIN_SHOP_REVIEWS, S.MIN_SHOP_RATE) + ", ".join(f"{S.LABELS[g]}={len(r)}店" for g, r in db["genres"].items()))
    log(f"Yahoo! 呼び出し回数: {y.calls}")
    return db


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="store_true", help="集計をサーバーの非公開フォルダに置く")
    ap.add_argument("--pages", type=int, default=3)
    a = ap.parse_args(argv)
    cid = os.environ.get("YAHOO_CLIENT_ID")
    if not cid:
        log("YAHOO_CLIENT_ID が無い。何もしない")
        return 1
    db = run(cid, pages=a.pages)
    shops = sum(len(r) for r in db["genres"].values())
    if not shops:
        log("店が1つも集計できなかった。置かない(古いファイルは、取得日が古くなって、欄が隠れる)")
        return 1
    if not a.store:
        log(f"保存しない(--store なし)。ジャンル {len(db['genres'])}・店 {shops}")
        return 0
    return P.push_private({S.DB_NAME: db})


if __name__ == "__main__":
    sys.exit(main())
