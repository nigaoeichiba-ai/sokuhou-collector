#!/usr/bin/env python3
"""2026-11-25: Jalan net link on the USJ article (with the affiliate notice at the top, a condition of the programme) and
Expedia link on the Yorunoyo article (VC MyLink codes issued by the desk, A8_PROGRAMS.md).  Safe to run twice."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")


def vc(pid, vc_url, text):
    return ('<p><a href="https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788020&amp;pid=%s&amp;vc_url=%s" '
            'rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3788020&amp;pid=%s" height="1" width="0" border="0" alt=""></p>'
            % (pid, vc_url, text, pid))


JALAN = vc("892757567", "https%3A%2F%2Fwww.jalan.net%2F", "じゃらんnetで宿を探す")
EXPEDIA = vc("892757568", "https%3A%2F%2Fwww.expedia.co.jp%2F%3Feapid%3D0-28%26affcid%3Djp.network.valuecommerce.general_mylink.",
             "エクスペディアで宿を探す")
NOTICE = '<p class="pr-note"><strong>#アフィリエイト広告</strong> このページには、広告（アフィリエイト）のリンクがあります。</p>'


def edit(slug, fn):
    p = os.path.join(CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    before = json.dumps(d, ensure_ascii=False)
    fn(d)
    if json.dumps(d, ensure_ascii=False) != before:
        open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        print("changed", slug)


def usj(d):
    secs = d["sections"]
    for s in secs:
        if "paras" in s:
            s["paras"] = [x.replace("楽天トラベルなどの宿泊予約サイト", "楽天トラベルやじゃらんnetなどの宿泊予約サイト") for x in s["paras"]]
    if not any("pid=892757567" in s.get("html", "") for s in secs):
        i = next(i for i, s in enumerate(secs) if "travel.rakuten.co.jp" in s.get("html", ""))
        secs.insert(i + 1, {"html": JALAN})
    if not any(s.get("html") == NOTICE for s in secs):
        secs.insert(1, {"html": NOTICE})


def yorunoyo(d):
    secs = d["sections"]
    if not any("pid=892757568" in s.get("html", "") for s in secs):
        i = next(i for i, s in enumerate(secs) if "pid=892749522" in s.get("html", ""))
        secs.insert(i + 1, {"html": EXPEDIA})


if __name__ == "__main__":
    edit("trend-usj-winter-kids-free", usj)
    edit("trend-yorunoyo-2026", yorunoyo)
