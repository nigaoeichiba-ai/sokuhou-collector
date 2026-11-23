#!/usr/bin/env python3
"""2026-11-23 (2): add the Super PayPay Matsuri article (and the Yahoo! Black Friday one when its card image is back),
with the Yahoo! Shopping ValueCommerce MyLink (trend 3788020, pid 892755274). Safe to run twice."""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from apply_20261123 import CONTENT, DRIVE, md_sections  # noqa: E402

PID = "892755274"


def yahoo_link(vc_url="https://shopping.yahoo.co.jp/", text="Yahoo!ショッピングで探す"):
    import urllib.parse
    return ('<p><a href="https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788020&amp;pid=%s&amp;vc_url=%s" '
            'rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）'
            '<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3788020&amp;pid=%s" height="1" width="1" border="0" alt=""></p>'
            % (PID, urllib.parse.quote(vc_url, safe=""), text, PID))


def add(slug, final, card, crumb, kw, top_lead, description, answer, credit, related_slugs, category, vc_url="https://shopping.yahoo.co.jp/"):
    p = os.path.join(CONTENT, slug + ".json")
    md = open(DRIVE + final, encoding="utf-8").read()
    title = re.match(r"# (.+)", md).group(1).strip()
    secs = md_sections(md, yahoo_link(vc_url))
    secs.insert(0, {"html": f'<p class="eyecatch"><img src="/assets/img/eye-{slug}.webp" width="1280" alt="{title}" fetchpriority="high"></p>'})
    related = []
    for r in related_slugs:
        d = json.load(open(os.path.join(CONTENT, r + ".json"), encoding="utf-8"))
        related.append({"path": f"/{r}/", "text": d["h1"]})
    seq = max(json.load(open(f, encoding="utf-8")).get("seq", 0) for f in glob.glob(os.path.join(CONTENT, "trend-*.json"))) + 1
    page = {"updated": "2026-11-23", "data_basis": "2026年11月23日現在", "sources": [], "credit": credit, "path": f"/{slug}/",
            "top_lead": top_lead, "kind": "article", "parent": "/", "title": title, "h1": title, "category": category,
            "published": "2026-11-23", "seq": seq, "crumb": crumb, "primary_kw": kw, "secondary_kw": [], "intent": 1,
            "description": description, "answer": answer, "related": related, "sections": secs}
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(page, ensure_ascii=False, indent=1) + "\n")
    for r in related:
        rp = os.path.join(CONTENT, r["path"].strip("/") + ".json")
        d = json.load(open(rp, encoding="utf-8"))
        if not any(x["path"] == page["path"] for x in d["related"]):
            d["related"].append({"path": page["path"], "text": title})
            open(rp, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    return page


def image(card, slug):
    from PIL import Image
    Image.open(DRIVE + card).convert("RGB").resize((1280, 720), Image.LANCZOS).save(
        os.path.join(HERE, "assets", "img", f"eye-{slug}.webp"), "WEBP", quality=82)


if __name__ == "__main__":
    cat = json.load(open(os.path.join(CONTENT, "trend-aupay-blackfriday.json"), encoding="utf-8"))["category"]
    slug = "trend-super-paypay-matsuri-scratch"
    image("card_超PayPay祭.webp", slug)
    add(slug, "記事最終稿_超PayPay祭_2026-11-23.md", "card_超PayPay祭.webp", "超PayPay祭のスクラッチくじ", "超PayPay祭",
        "超PayPay祭のスクラッチくじは、2026年11月20日から12月27日まで。",
        "超PayPay祭のスクラッチくじは11月20日から12月27日まで。1回200円以上の決済で引け、当たる確率は払い方で変わります。条件と確率の早見表で、選び方を整理します。",
        "200円以上の決済で引ける。必ず当たるのは条件を満たした対象の決済だけ",
        "企業の公式発表・キャンペーン案内（2026年11月20日時点）",
        ["trend-aupay-blackfriday", "trend-rakuten-blackfriday", "trend-newt-blackfriday"], cat)
    print("added", slug)


def yahoo_bf():
    slug = "trend-yahoo-blackfriday-2026"
    cat = json.load(open(os.path.join(CONTENT, "trend-rakuten-blackfriday.json"), encoding="utf-8"))["category"]
    image("card_YahooブラックフライデーBF.webp", slug)
    add(slug, "記事最終稿_YahooブラックフライデーBF_2026-11-23.md", "card_YahooブラックフライデーBF.webp", "Yahoo!ショッピングのブラックフライデー", "Yahoo!ショッピング",
        "Yahoo!ショッピングのブラックフライデーは、2026年11月22日0時から11月30日の1時59分まで、8日間の開催です。",
        "Yahoo!ショッピングのブラックフライデーは11月22日0時から11月30日1時59分まで。PayPayポイントは最大23%と案内されていますが、条件を重ねたときの上限です。買う前に決めたいことを整理します。",
        "期間は11月30日1時59分まで。最大23%は条件つきなので、買う物と払い方を先に決める",
        "企業の発表資料（2026年11月）、業界メディアの報道（2026年11月5日）",
        ["trend-rakuten-blackfriday", "trend-aupay-blackfriday", "trend-super-paypay-matsuri-scratch"], cat)
    print("added", slug)
