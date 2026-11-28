#!/usr/bin/env python3
"""2026-11-28: the 挨拶状ドットコム A8 programme (s00000007052003, approved today) on the New Year card early-order
article, after the price table.  A condition of the programme: the company / service name is not in <title> or any
<meta>, so the description no longer names the companies.  The desk gave the a8mat; the link text is ours.
Safe to run twice."""
import json
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "trend-nengajo-hayawari.json")
MAT = "4BGVY7+9LBL1M+1IEW+I52SY"
LEAD = ("表の8,429円は、挨拶状ドットコムの35％OFF（11月29日（日）24:00まで）を入れた金額です。この割引で頼むなら、"
        "期限の前に注文の画面で枚数と総額を確かめておきましょう。")
LINK = ('<p><a href="https://px.a8.net/svt/ejp?a8mat=%s" rel="nofollow sponsored noopener" target="_blank">'
        '挨拶状ドットコムで年賀状印刷を見る</a>（PR）<img border="0" width="1" height="1" '
        'src="https://www14.a8.net/0.gif?a8mat=%s" alt=""></p>' % (MAT, MAT))
DESCRIPTION = ("年賀状印刷の早割は、締切が11月29日と30日12:59の2段階。割引中の3社を、はがき代と宛名印刷、送料まで入れた"
               "30枚の総額でそろえ、締切の表と並べて比べられます。")
# the top page and the category list print these without a link, so they do not name the company either
SHORT = {
    "answer": ("年賀状印刷の早割は、年賀状スクエアの45％OFFを含む2社が11月29日（日）まで、しまうまプリントの12％OFFが"
               "30日（月）12:59まで。30枚・宛名印刷ありの総額は、割引中の3社のうち最安の年賀状スクエアが6,462円で、"
               "最も高い社との差は約2,000円です。"),
    "top_lead": "年賀状の早割は、割引中の2社が29日まで、しまうまプリント12％OFFが30日まで。総額で比べましょう。",
}
TODO_TEXT = ("年賀状スクエアの45％OFFなど2社の割引は29日まで。しまうまプリントの12％OFFは30日の12:59まで。"
             "出す枚数を数えてから注文しましょう。")
OLD_NOTE = "印刷サービスでリンクのある会社は、下の1社だけです。"
NEW_NOTE = "広告リンクがあるのは年賀状スクエアと挨拶状ドットコムの2社で、後者のリンクは総額の表の下に置いています。"


def main():
    d = json.load(open(P, encoding="utf-8"))
    d.update(SHORT)
    d["todo"]["text"] = TODO_TEXT
    if MAT in json.dumps(d, ensure_ascii=False):
        open(P, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        return print("link already there; short texts written")
    secs = d["sections"]
    note = next(s for s in secs if any(OLD_NOTE in x for x in s.get("paras", [])))
    note["paras"] = [x.replace(OLD_NOTE, NEW_NOTE) for x in note["paras"]]
    i = next(i for i, s in enumerate(secs) if s.get("h2") == "割引率だけ見ると損するワケ")
    secs[i:i] = [{"paras": [LEAD]}, {"html": LINK}]
    d["description"] = DESCRIPTION
    open(P, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed")


if __name__ == "__main__":
    main()
