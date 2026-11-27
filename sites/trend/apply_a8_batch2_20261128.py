#!/usr/bin/env python3
"""2026-11-28: the two programmes added for the last two articles (A8_PROGRAMS.md, 07:5x): インク革命.com (A8) on the
New Year card article and レコチョク (ValueCommerce) on the music show article.  Issued codes; only rel / target,
an empty alt and the PR mark are added.  Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")

INK = ('<p><a href="https://px.a8.net/svt/ejp?a8mat=4BGVY1+BMJWGA+34XA+5YJRM" rel="nofollow sponsored noopener" '
       'target="_blank">【インク革命.com】</a>（PR）<img border="0" width="1" height="1" '
       'src="https://www10.a8.net/0.gif?a8mat=4BGVY1+BMJWGA+34XA+5YJRM" alt=""></p>')
# the same form as the other ValueCommerce links on this site (apply_jalan_expedia_20261125.vc): https, the counter
# picture right after the anchor; the ids are the issued ones
RECOCHOKU = ('<p><a href="https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788020&amp;pid=892760476" '
             'rel="nofollow sponsored noopener" target="_blank">レコチョク</a>（PR）'
             '<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3788020&amp;pid=892760476" height="1" '
             'width="0" border="0" alt=""></p>')

# (page, text of the link paragraph to follow, lead sentence, link paragraph)
ADD = [
    ("trend-nengajo-toukan-2027", "年賀状 プリンター インク",
     "互換品も含めて選びたい場合は、インクの専門通販も候補です。メーカー純正ではない商品は、型番の対応とプリンターの保証の扱いを先に読んでおきましょう。",
     INK),
    ("trend-mste-superlive-2026", "Mrs. GREEN APPLE アルバム",
     "聴きたい曲だけを手元に入れたい場合は、音楽の配信サービスで買う方法もあります。出演者の曲の取り扱いは配信の画面で調べてください。",
     RECOCHOKU),
]


def main():
    for slug, after, lead, link in ADD:
        p = os.path.join(CONTENT, slug + ".json")
        d = json.load(open(p, encoding="utf-8"))
        if any(s.get("html") == link for s in d["sections"]):
            print("already there:", slug)
            continue
        i = next(i for i, s in enumerate(d["sections"]) if after in s.get("html", "")) + 1
        d["sections"][i:i] = [{"paras": [lead]}, {"html": link}]
        open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        print("added:", slug)


if __name__ == "__main__":
    main()
