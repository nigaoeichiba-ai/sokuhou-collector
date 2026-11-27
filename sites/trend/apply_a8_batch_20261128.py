#!/usr/bin/env python3
"""2026-11-28: the A8 programmes approved this morning (A8_PROGRAMS.md, 07:4x) on today's articles.  The links are
the issued codes; only rel / target and the PR mark are added.  VIVANT gets no manga link (no matching book).
Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")


def a8(mat, host, text):
    return ('<a href="https://px.a8.net/svt/ejp?a8mat=%s" rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img border="0" width="1" height="1" src="https://%s.a8.net/0.gif?a8mat=%s" alt="">' % (mat, text, host, mat))


# (page, text of the link paragraph to follow, lead sentence, link)
ADD = [
    ("trend-christmas-coffret-2026", "ハンドクリーム ギフトを探す",
     "手に塗る品やボディケアの品は、ブランドの直営通販から選ぶ方法もあります。上の表の限定品とは別の店なので、扱っている商品は通販の画面で調べておきましょう。",
     a8("4BGVY1+AJ9AIY+5KAA+5YRHE", "www18", "【ハウスオブローゼ】")),
    ("trend-mos-fukubukuro-2027", "ハイキュー コミックを楽天市場で探す",
     "巻数をまとめてそろえたい場合は、漫画の全巻セットを扱う専門の通販も候補です。在庫と巻の範囲は商品ページで見てから注文しましょう。",
     a8("4BGVY1+AKG5QI+1892+631SY", "www14", "漫画全巻ドットコム")),
    ("trend-savas-nesage-1201", "ザバス ホエイプロテイン 粉末を探す",
     "別の国内ブランドの粉末と比べてから決める手もあります。ザバスとは別の会社の商品なので、内容量と原材料の表示を見比べてください。",
     a8("4BGVY1+ALN0Y2+4NL2+5YJRM", "www11", "国産高品質、プロテインブランド【ULTORA（ウルトラ）】")),
    ("trend-christmas-toy-2026", "知育玩具 3歳を楽天市場で探す",
     "知育系のおもちゃにしぼって眺めたい場合は、専門の通販店もあります。対象年齢の表示は商品ごとに見比べましょう。",
     a8("4BGVY1+ANFBRE+5TXI+BX3J6", "www14", "【知育玩具名品館】")),
    ("trend-christmas-toy-2026", "おもちゃ 収納ボックスを探す",
     "置き場所が心配な家庭には、買わずに借りて遊ぶレンタルという道もあります。対象の年齢と返し方、料金は案内のページで先に読んでおきましょう。",
     a8("4BGVY1+AV5YMI+56OA+5YJRM", "www11", "おもちゃのレンタルなら【And TOYBOX】")),
]
# audiobook.jp goes at the end of the "paper or e-book" section
KONOMYS = ("trend-konomys-2027", "帰省の移動で読むなら",
           "目がふさがる移動や家事の時間には、本を耳で聴くサービスという選択肢もあります。読みたい作品があるかは、聴き放題の案内で先に調べてください。",
           a8("4BGVY1+AM8GJU+3CJQ+5YJRM", "www12", "忙しいあなたも、耳は意外とヒマしてる - audiobook.jp"))


def edit(slug, lead, link, at):
    p = os.path.join(CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    mat = link.split("a8mat=")[1].split('"')[0]
    if mat in json.dumps(d, ensure_ascii=False):
        return print("already there:", slug, mat)
    i = at(d["sections"])
    d["sections"][i:i] = [{"paras": [lead]}, {"html": "<p>" + link + "</p>"}]
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("added:", slug, mat)


def main():
    for slug, after, lead, link in ADD:
        edit(slug, lead, link, lambda secs: next(i for i, s in enumerate(secs) if after in s.get("html", "")) + 1)
    slug, before, lead, link = KONOMYS
    edit(slug, lead, link, lambda secs: next(i for i, s in enumerate(secs) if s.get("h2") == before))


if __name__ == "__main__":
    main()
