#!/usr/bin/env python3
"""2026-11-27: two A8 programmes completed today (codes issued by the desk, A8_PROGRAMS.md 11/27 07:5x) on the Tully's
lucky bag article, in the part for readers looking for coffee at home.  The href, a8mat, link text and tracking image are
exactly as issued.  Safe to run twice."""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "trend-tullys-fukubukuro-2027.json")
NOTICE = '<p class="pr-note"><strong>#アフィリエイト広告</strong> このページには、広告（アフィリエイト）のリンクがあります。</p>'


def link(a8mat, host, text):
    return ('<p><a href="https://px.a8.net/svt/ejp?a8mat=%s" rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img border="0" width="1" height="1" src="https://%s.a8.net/0.gif?a8mat=%s" alt=""></p>' % (a8mat, text, host, a8mat))


ADD = [
    {"paras": ["コーヒー専門のお店から豆を取り寄せる手もあります。次の2つはタリーズとは別のお店で、福袋の代わりの商品ではありません。扱う品や値段は、開いた先の表示で確かめてください。"]},
    {"html": link("4BGV5X+8QYH6Y+5UFU+5YJRM", "www17", "ブルーボトルコーヒー公式オンラインストア")},
    {"html": link("4BGV5X+92V5AI+2CG0+5YJRM", "www16", "珈琲きゃろっと")},
]

d = json.load(open(PATH, encoding="utf-8"))
s = d["sections"]
if not any("4BGV5X+" in x.get("html", "") for x in s):
    i = next(i for i, x in enumerate(s) if x.get("h2") == "ここは誤解しないで")
    s[i:i] = ADD
    if not any(x.get("html") == NOTICE for x in s):
        s.insert(1, {"html": NOTICE})
    open(PATH, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed")
