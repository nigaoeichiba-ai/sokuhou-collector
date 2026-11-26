#!/usr/bin/env python3
"""2026-11-27: three A8 programmes completed this morning (codes issued by the desk, A8_PROGRAMS.md 11/27 08:4x) on three of
the day's articles.  Handling checked on the shops' own pages today: Hinata rental lists sleeping bags and mats, L-Breath
has sleeping bag, tent mat, glove and neck warmer categories (no winter-boot category was found, so the snow article only
speaks of warm accessories), Y's Road lists bicycle lights.  href, a8mat, link text and tracking image are as issued.
Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
NOTICE = '<p class="pr-note"><strong>#アフィリエイト広告</strong> このページには、広告（アフィリエイト）のリンクがあります。</p>'


def link(a8mat, host, text):
    return {"html": '<p><a href="https://px.a8.net/svt/ejp?a8mat=%s" rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
                    '<img border="0" width="1" height="1" src="https://%s.a8.net/0.gif?a8mat=%s" alt=""></p>' % (a8mat, text, host, a8mat)}


HINATA = link("4BGV5X+FW5QIY+4U5Q+5YJRM", "www11", "hinataレンタル")
LBREATH = link("4BGV5X+FT6KI2+4ABU+HXSGI", "www19", "アウトドア用品【L-Breath】")
YSROAD = link("4BGV5X+FSL4WA+4JDO+5YJRM", "www17", "【ワイズロードオンライン】")


def edit(slug, before_h2, blocks):
    path = os.path.join(CONTENT, slug + ".json")
    d = json.load(open(path, encoding="utf-8"))
    s = d["sections"]
    if blocks[1] in s:
        print("skip (already):", slug)
        return
    i = next(i for i, x in enumerate(s) if x.get("h2") == before_h2)
    s[i:i] = blocks
    if not any(x.get("html") == NOTICE for x in s):
        s.insert(1, {"html": NOTICE})
    open(path, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed", slug)


if __name__ == "__main__":
    edit("trend-winter-camp-neru-sobi", "湯たんぽと電気毛布はどう使う？", [
        {"paras": ["冬のキャンプがはじめてなら、寝袋やマットは買う前に借りて試す手もあります。借りられる品と日程は、申し込む画面で確かめてください。"]},
        HINATA,
        {"paras": ["自分の装備として買いそろえたい場合は、アウトドア用品の通販で寝袋やマットを比べられます。温度の表示とR値は、商品ごとの説明で確認しましょう。"]},
        LBREATH,
    ])
    edit("trend-danto-kanki-yuki-sonae", "雪かき道具は役割で分ける", [
        {"paras": ["寒気の日の外出には、手袋やネックウォーマーなど首と手の防寒も役立ちます。アウトドア用品の通販で扱っていますが、雪かき向きかどうかは別なので、防水や滑りにくさは商品の説明で確かめてください。"]},
        LBREATH,
    ])
    edit("trend-hinoiri-hayai-2026", "ここは誤解しないで", [
        {"paras": ["自転車用品の専門通販でも、前後のライトを比べられます。取り付けられる場所と明るさは、商品の説明で確認してから選びましょう。"]},
        YSROAD,
    ])
