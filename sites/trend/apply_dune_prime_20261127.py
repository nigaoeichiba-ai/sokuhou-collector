#!/usr/bin/env python3
"""2026-11-27: the Dune article read as if PART2 could be streamed up to the 12/18 release.  Amazon's own work page
showed today that PART2's Prime inclusion ends soon (the end date is not written: it was not identified), the first film
showed no such notice.  Adds the official Prime Video sign-up page (a fixed service page) with the associate tag, and a
search link for PART2.  The two work pages are item URLs, which the public repository must not carry (CLAUDE.md), so
they are not used.  Safe to run twice."""
import json
import os
import urllib.parse

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "trend-dune-part3-saijoei.json")
NOTICE = '<p class="pr-note"><strong>#アフィリエイト広告</strong> このページには、広告（アフィリエイト）のリンクがあります。</p>'
REL = 'rel="nofollow sponsored noopener" target="_blank"'
SEARCH = ('<p><a href="https://www.amazon.co.jp/s?k=%s&amp;tag=amazonmacs-22" %s>Amazonで「デューン 砂の惑星PART2」を探す</a>（PR）</p>'
          % (urllib.parse.quote("デューン 砂の惑星PART2"), REL))
SIGNUP = ('<p><a href="https://www.amazon.co.jp/gp/video/primesignup?tag=amazonmacs-22" %s>Prime Videoの登録ページで無料体験の条件を見る</a>（PR）</p>'
          % REL)

d = json.load(open(PATH, encoding="utf-8"))
s = d["sections"]
if not any("primesignup" in x.get("html", "") for x in s):
    old_cell = "Prime Videoで11月2日から見放題配信が開始。会員条件と配信状況は変わることがある"
    table = next(x["table"] for x in s if "table" in x and any(old_cell in r for r in x["table"]["rows"]))
    for r in table["rows"]:
        if old_cell in r:
            r[r.index(old_cell)] = "Prime VideoのPART2は、11月27日時点で見放題の終了が近いという表示。条件は変わることがある"

    for x in s:
        if "html" in x:
            x["html"] = x["html"].replace(
                "<li>劇場に行けなくても、配信や原作で予習できます。</li>",
                "<li>劇場に行けなくても配信や原作で予習できます。ただし配信のPART2は見放題の終了が近い表示です（11月27日確認）。</li>")
            x["html"] = x["html"].replace(
                "<li><strong>予習の方法を選ぶ。</strong> 再上映、配信、原作から無理のないものを。</li>",
                "<li><strong>予習の方法を選ぶ。</strong> 再上映、配信、原作から無理のないものを。配信でPART2を観るつもりなら、作品の表示を確かめて早めに。</li>")

    i = next(i for i, x in enumerate(s) if "paras" in x and x["paras"][0].startswith("第3作のもとになったのは"))
    s[i:i] = [
        {"html": "<h3>配信で観るならPART2はお早めに！</h3>"},
        {"paras": ["11月27日に作品ページを見ると、『デューン 砂の惑星PART2』には「まもなく配信終了」の表示が出ていました。12月18日の公開直前まで見放題で待てるとは考えないほうが安全です。第1作の『DUNE/デューン 砂の惑星』には、この日の時点で同じ表示は見当たりませんでした。配信の条件は変わることがあるので、再生する前に画面の表示を確かめてください。"]},
        {"html": SEARCH},
        {"paras": ["Prime Videoをまだ使っていない場合、対象になる方には無料体験が用意されています。体験期間のあとは有料の会員に自動で切り替わる仕組みなので、申し込む画面で条件を読んでから進みましょう。"]},
        {"html": SIGNUP},
        {"html": "<h3>原作や映像ソフトでおさらいする手も</h3>"},
    ]
    if not any(x.get("html") == NOTICE for x in s):
        s.insert(1, {"html": NOTICE})
    d["credit"] += "、配信サービスの作品ページと登録ページ（2026年11月27日確認）"
    open(PATH, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed")
