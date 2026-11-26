#!/usr/bin/env python3
"""2026-11-26: affiliate links where an affiliated advertiser is named but not linked (Yahoo!Shopping on two Black Friday
pages, Nippon Travel on three pages), and the two stale rows of the price article's date table.  Safe to run twice."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")


def vc(pid, vc_url, lead, text):
    return ('<p>%s<a href="https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788020&amp;pid=%s&amp;vc_url=%s" '
            'rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3788020&amp;pid=%s" height="1" width="1" border="0" alt=""></p>'
            % (lead, pid, vc_url, text, pid))


YAHOO_URL = "https%3A%2F%2Fshopping.yahoo.co.jp%2F"
NTA_JR = "https%3A%2F%2Fwww.nta.co.jp%2Fjr%2Fshinkansen%2F"
NTA_BF = "https%3A%2F%2Fwww.nta.co.jp%2Fcpn%2Fcampaign%2Fblack-friday%2F"

# slug: (the section to put the link after: a text found in it, the html)
LINKS = {
    "trend-blackfriday-hajimari-bara": ("pc=https%3A%2F%2Fevent.rakuten.co.jp", vc(
        "892755274", YAHOO_URL,
        "Yahoo!ショッピングは11月30日1時59分までなので、これから買う方は終わる時刻に気をつけて比べてみてください。",
        "Yahoo!ショッピングで探す")),
    "trend-blackfriday-price": ("amazonmacs-22", vc(
        "892755274", YAHOO_URL,
        "記録した価格をYahoo!ショッピングでも比べたい方は、11月30日1時59分までのうちにチェックしておきましょう。",
        "Yahoo!ショッピングで探す")),
    "trend-nozomi-zensekishitei": ("amazonmacs-22", vc(
        "892749522", NTA_JR,
        "宿もこれから取る方は、新幹線などのJRと宿泊を組み合わせたプランなら、移動と宿をまとめて比べられます。",
        "日本旅行のJRセットプランを見る")),
    "trend-cathay-blackfriday": ("travel.rakuten.co.jp", vc(
        "892749522", NTA_JR,
        "出発する空港の近くまで新幹線で向かって前泊する方は、JRと宿泊のセットプランも比較の候補になります。",
        "日本旅行のJRセットプランを見る")),
    "trend-rakuten-blackfriday": ("pid=892755274", vc(
        "892749522", NTA_BF,
        "旅行の予約がこれからの方向けに、日本旅行のブラックフライデーは11月30日14時59分までクーポンを配っています。",
        "日本旅行のブラックフライデーを見る")),
}

PRICE_FIX = [("11月22日〜11月29日", "11月22日〜11月30日1時59分"),
             ("11月6日時点で未発表", "11月19日20時〜11月25日1時59分（終了）"),
             ("楽天市場も、11月6日時点では日程が発表されていません。", "楽天市場は11月19日20時に始まり、11月25日1時59分で終了しました。")]


def run():
    for slug, (anchor, html) in LINKS.items():
        p = os.path.join(CONTENT, slug + ".json")
        d = json.load(open(p, encoding="utf-8"))
        before = json.dumps(d, ensure_ascii=False)
        secs = d["sections"]
        if not any(s.get("html") == html for s in secs):
            i = next(i for i, s in enumerate(secs) if anchor in s.get("html", ""))
            secs.insert(i + 1, {"html": html})
        if slug == "trend-blackfriday-price":
            raw = json.dumps(d, ensure_ascii=False)
            for a, b in PRICE_FIX:
                raw = raw.replace(a, b)
            d = json.loads(raw)
        if json.dumps(d, ensure_ascii=False) != before:
            d["updated"] = "2026-11-26"
            open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
            print("changed", slug)


if __name__ == "__main__":
    run()
