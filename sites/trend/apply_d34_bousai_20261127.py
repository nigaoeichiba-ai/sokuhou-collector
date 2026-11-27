#!/usr/bin/env python3
"""D34, the five disaster pages left over (their names do not start with trend-): the bottom line gives the kind of
material and date only.  The licence line of the weather agency data stays.  Safe to run twice."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def edit(rel, pairs):
    p = os.path.join(HERE, rel)
    text = open(p, encoding="utf-8", newline="").read()
    new = text
    for old, repl in pairs:
        new = new.replace(old, repl)
    if new != text:
        open(p, "w", encoding="utf-8", newline="").write(new)
        print("changed", rel)


edit("content/bousai-denchi-juden.json", [("パナソニック『使用推奨期限の意味』『防災用の懐中電灯の場合、乾電池はどのように保管すればよいか』、エレコムの公表値、政府広報オンライン『災害に事前に備える』をもとに作成",
                                          "メーカーの利用者向け案内と公表値、公的な防災の広報")])
edit("content/bousai-keitai-toilet.json", [("広報東京都2025年9月号『もしもの時に困らないトイレの備蓄』、政府広報オンライン『災害に事前に備える』をもとに作成",
                                           "自治体の広報（2025年9月号）、公的な防災の広報")])
edit("content/bousai-light.json", [("政府広報オンライン『災害に事前に備える』、パナソニック『防災用の懐中電灯の場合、乾電池はどのように保管すればよいか』をもとに作成",
                                    "公的な防災の広報、メーカーの利用者向け案内")])
edit("content/bousai-mizu-shokuryo.json", [("農林水産省『災害時に備えた食品ストックガイド』、政府広報オンライン『災害に事前に備える』『ローリングストックの始め方』をもとに作成",
                                            "公的な食品備蓄の手引き、公的な防災の広報")])
edit("content/bousai.json", [("そこで、政府広報オンラインの備えの一覧をもとに、", "そこで、公的な備えの一覧をもとに、")])
edit("site.json", [("防災庁『事前防災徹底のための緊急要請』(2026年11月2日)をもとに作成", "公的機関の要請文（2026年11月2日）")])
