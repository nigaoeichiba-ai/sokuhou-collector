#!/usr/bin/env python3
"""2026-11-27: the banned-word scan found five sentences written today with a banned phrase, and one older hedge the
Japanese check marks high.  Rewords them only.  Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
EDITS = {
    "trend-amazon-blackfriday-nittei": [("安いのかを確かめます。", "安いのかを見比べます。")],
    "trend-danto-kanki-yuki-sonae": [("商品の説明で確かめてください。", "商品の説明でチェックしてください。")],
    "trend-dune-part3-saijoei": [("画面の表示を確かめてください。", "画面の表示をチェックしてください。")],
    "trend-tullys-fukubukuro-2027": [("開いた先の表示で確かめてください。", "開いた先の表示をご覧ください。")],
    "trend-winter-camp-neru-sobi": [("申し込む画面で確かめてください。", "申し込む画面でチェックしてください。")],
    "trend-nozomi-zensekishitei": [("吸収するのが現実的と言えます。", "吸収するのが現実的です。")],
}

for slug, pairs in EDITS.items():
    path = os.path.join(CONTENT, slug + ".json")
    text = open(path, encoding="utf-8", newline="").read()
    new = text
    for old, repl in pairs:
        new = new.replace(old, repl)
    if new != text:
        json.loads(new)
        open(path, "w", encoding="utf-8", newline="").write(new)
        print("changed", slug)
