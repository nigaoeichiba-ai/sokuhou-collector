#!/usr/bin/env python3
"""2026-11-24: add the Christmas market comparison article (Nippon Travel VC MyLink, trend pid 892749522). Safe to run twice."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123b as m  # noqa: E402
from apply_shinkansen_20261124 import NTA  # noqa: E402

if __name__ == "__main__":
    slug = "trend-christmas-market-2026-nyujoryo"
    m.yahoo_link = lambda *a, **k: NTA
    cat = json.load(open(os.path.join(m.CONTENT, "trend-shichigosan.json"), encoding="utf-8"))["category"]
    m.image("card_クリスマスマーケット.webp", slug)
    m.add(slug, "記事最終稿_クリスマスマーケット_2026-11-24.md", "", "クリスマスマーケットの入場料", "クリスマスマーケット",
          "東京・横浜のクリスマスマーケットは、会期がどこも12月25日までで、入場料の決まりは会場でまったく違います。",
          "クリスマスマーケット2026の入場料は会場でバラバラ。東京の新豊洲・芝公園、横浜赤レンガ倉庫、麻布台ヒルズの期間と料金、優先入場の違いを早見表で比べます。",
          "会期はどこも12月25日まで。入場料と優先入場は会場ごとに違うので、日付を決めて公式で確認する",
          "各会場の主催者・施設の公式案内（2026年11月24日確認）",
          ["trend-xmas-cake-hayawari", "trend-usj-winter-kids-free", "trend-nenmatsu-shinkansen-hatsubai-2026"], cat)
    p = os.path.join(m.CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["published"] = d["updated"] = "2026-11-24"
    d["data_basis"] = "2026年11月24日現在"
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("added", slug)
