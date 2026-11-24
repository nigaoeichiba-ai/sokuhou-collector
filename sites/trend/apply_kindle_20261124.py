#!/usr/bin/env python3
"""2026-11-24: add the Kindle 4-model guide (Amazon search link, amazonmacs-22; no price). Safe to run twice."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123b as m  # noqa: E402

AMZ = ('<p><a href="https://www.amazon.co.jp/s?k=Kindle&amp;tag=amazonmacs-22" rel="nofollow sponsored noopener" target="_blank">AmazonでKindleを探す</a>（PR）</p>')

if __name__ == "__main__":
    slug = "trend-kindle-shingata-4model"
    m.yahoo_link = lambda *a, **k: AMZ
    cat = json.load(open(os.path.join(m.CONTENT, "trend-hobonichi-techo-2027.json"), encoding="utf-8"))["category"]
    m.image("card_Kindle新型4モデル.webp", slug)
    m.add(slug, "記事最終稿_Kindle新型4モデル_2026-11-24.md", "", "Kindle新型4モデル", "Kindle",
          "AmazonがKindleの新型4モデルを、日本で発表しました。16GBとシリーズ初の32GBの無印、Paperwhite、カラー表示のColorsoftがそろいます。",
          "Kindle新型は4モデル。無印の16GBと32GB、防水のPaperwhite、カラーのColorsoftを、防水・バッテリー・特徴の早見表で比べ、ブラックフライデー前に1台を選ぶ手順を整理します。",
          "防水ならPaperwhite、カラーならColorsoft、軽さなら無印。セール前に1台を決める",
          "企業の発表資料（2026年10月1日）、企業のセール案内（2026年11月）",
          ["trend-amazon-blackfriday-nittei", "trend-google-store-blackfriday", "trend-hobonichi-techo-2027"], cat)
    p = os.path.join(m.CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["published"] = d["updated"] = "2026-11-24"
    d["data_basis"] = "2026年11月24日現在"
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("added", slug)
