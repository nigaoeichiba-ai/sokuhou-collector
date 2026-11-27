#!/usr/bin/env python3
"""2026-11-28: add the day's articles from their final drafts (Drive).  Same page shape and link markers as the
earlier batches, plus the A8 / AccessTrade programme markers used today.  An article is built only when its card
image is back and its alt text (what is lettered on the card, written after looking at it) is filled in.
The per-article data is in batch_20261128.json next to this file.  Safe to run twice.
Usage: apply_batch_20261128.py slug [slug ...]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_batch_20261127 as day27  # noqa: E402

day26 = day27.day26
prev = day27.prev
TODAY = "2026-11-28"
DATA_BASIS = "2026年11月28日現在"


def a8(mat, host, text):
    return ('<p><a href="https://px.a8.net/svt/ejp?a8mat=%s" rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img border="0" width="1" height="1" src="https://%s.a8.net/0.gif?a8mat=%s" alt=""></p>' % (mat, text, host, mat))


PROGRAMS = {
    "年賀状スクエア（PR）": a8("4BGH3G+CRMT6Y+33J0+15OK2A", "www11", "当日出荷☆喪中・年賀状印刷は年賀状スクウェアで"),
    "ブルーボトルコーヒー公式オンラインストア（PR）": a8("4BGV5X+8QYH6Y+5UFU+5YJRM", "www17", "ブルーボトルコーヒー公式オンラインストア"),
    "珈琲きゃろっと（PR）": a8("4BGV5X+92V5AI+2CG0+5YJRM", "www16", "珈琲きゃろっと"),
    "ケーキ専門の通販サイトを見る（PR）": (
        '<p><a href="https://h.accesstrade.net/sp/cc?rk=0100ofdg00p2yp" rel="nofollow sponsored noopener" target="_blank">'
        'ケーキ専門の通販サイトを見る</a>（PR）<img src="https://h.accesstrade.net/sp/rr?rk=0100ofdg00p2yp" width="1" height="1" '
        'alt="" border="0"></p>'),
}

_day27_link = day27.link_html


def link_html(label):
    return PROGRAMS[label] if label in PROGRAMS else _day27_link(label)


with open(os.path.join(HERE, "batch_20261128.json"), encoding="utf-8") as fh:
    DATA = json.load(fh)


def build(slug):
    r = DATA[slug]
    articles = {k: ("記事最終稿_%s_2026-11-28.md" % v["name"], "card_%s.webp" % v["name"], v["crumb"], v["kw"],
                    v["related"], v["catfrom"]) for k, v in DATA.items()}
    # day27.build reads these module globals and hands them to day26
    day27.ARTICLES, day27.TODAY, day27.DATA_BASIS = articles, TODAY, DATA_BASIS
    day27.ALT = {k: v.get("alt", "") for k, v in DATA.items()}
    day27.TODO = {k: tuple(v["todo"]) for k, v in DATA.items() if v.get("todo")}
    day26.link_html = link_html
    day27.build(slug)


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        name = DATA[slug]["name"]
        if os.path.exists(os.path.join(prev.CONTENT, slug + ".json")):
            print("skip (already added):", slug)
        elif not os.path.exists(prev.base.DRIVE + "card_%s.webp" % name):
            print("skip (image not back):", slug)
        elif not DATA[slug].get("alt"):
            print("skip (alt not written):", slug)
        else:
            build(slug)
            print("built", slug)
