#!/usr/bin/env python3
"""2026-11-24: add the Sony WH-1000XM6 vs XM5 guide (Amazon search links, amazonmacs-22; no price). Safe to run twice."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123b as m  # noqa: E402

AMZ = ('<p><a href="https://www.amazon.co.jp/s?k=WH-1000XM6&amp;tag=amazonmacs-22" rel="nofollow sponsored noopener" target="_blank">AmazonでWH-1000XM6を探す</a>（PR）</p>'
       '<p><a href="https://www.amazon.co.jp/s?k=WH-1000XM5&amp;tag=amazonmacs-22" rel="nofollow sponsored noopener" target="_blank">AmazonでWH-1000XM5を探す</a>（PR）</p>')

if __name__ == "__main__":
    slug = "trend-sony-wh1000xm6-xm5"
    m.yahoo_link = lambda *a, **k: AMZ
    cat = json.load(open(os.path.join(m.CONTENT, "trend-hobonichi-techo-2027.json"), encoding="utf-8"))["category"]
    m.image("card_ソニーヘッドホンXM6とXM5.webp", slug)
    m.add(slug, "記事最終稿_ソニーヘッドホンXM6とXM5_2026-11-24.md", "", "ソニーのWH-1000XM6とXM5", "WH-1000XM6",
          "ソニーのノイズキャンセリングヘッドホンは、後継のWH-1000XM6と、前モデルのWH-1000XM5が、どちらもソニーストアの公式ページに載っています。",
          "ソニーのWH-1000XM6とXM5を、公式スペックの同じ項目で比較。バッテリーや充電時間は同じで、違いはプロセッサー、LC3対応、Bluetooth版です。ブラックフライデー前の選び方を整理します。",
          "バッテリー等は同じ。違いはQN3、LC3、Bluetooth 5.3。使う場面で選ぶ",
          "企業の公式製品ページ・スペック表（2026年11月24日確認）、企業の新製品発表資料（2025年5月16日）、企業のキャンペーン案内（2026年10月28日開始）",
          ["trend-amazon-blackfriday-nittei", "trend-kindle-shingata-4model", "trend-google-store-blackfriday"], cat)
    p = os.path.join(m.CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["published"] = d["updated"] = "2026-11-25"
    d["data_basis"] = "2026年11月25日現在"
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("added", slug)
