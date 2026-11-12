"""Affiliate links of the calendar (owner 2026-11-12: every entry of an affiliated advertiser or mall carries its affiliate link, with the PR mark).

Four kinds of links, each in the form its programme gave:
  rakuten  https://hb.afl.rakuten.co.jp/hgc/<id>/?pc=<url>          (the form of sokuhou/mallstore.affiliate_href, no m=)
  amazon   <official page>?tag=<tag>   or   https://www.amazon.co.jp/s?k=<term>&tag=<tag>      (tag only; never a price or an image)
  vc       the ValueCommerce MyLink of the site (sid), code of the tool: //ck.jp.ap.valuecommerce.com/servlet/referral?sid=&pid=&vc_url=  and its 1x1 counter inside the link
  a8       the A8.net text link of the site: https://px.a8.net/svt/ejp?a8mat=...  and its 1x1 pixel after the link
Nothing of a mall's catalogue is shown: no product name, price, image or rank.  A shop with no programme and no store in a mall has no link (NO_LINK says why).
The codes below were read from the pages of the programmes' own tools on 2026-11-12 (ValueCommerce site 3787704, A8.net site of this calendar); they are used as the tools gave them.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import quote

CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
SITE_NAME = json.loads((Path(__file__).resolve().parent / "site.json").read_text(encoding="utf-8"))["name"]       # the redesign's name (config.json still has the old one)
REL = "nofollow sponsored noopener"
VC_SID = "3787704"
VC_PID = {"yahoo": "892746613", "dhc": "892746566"}               # ValueCommerce MyLink ad of each programme (Yahoo!ショッピング / DHCオンラインショップ)
A8_MAT = {"xdomain": ("4BGJFW+4W8GGY+CO4+15ORS2", "www15"), "xserver": ("4BEHX9+1F7FFM+CO4+6AZAQ", "www16"), "xbiz": ("4BEHX9+1GEAN6+CO4+3SZMKY", "www14")}

YAHOO_GUIDE = "https://shopping.yahoo.co.jp/promotion/campaign/guide/"
RAKUTEN_EVENT = {"/rakuten/super-sale/": "https://event.rakuten.co.jp/campaign/supersale/", "/rakuten/marathon/": "https://event.rakuten.co.jp/campaign/point-up/marathon/",
                 "/rakuten/hatsuuri/": "https://event.rakuten.co.jp/newyear/", "/rakuten/pointday/": "https://event.rakuten.co.jp/card/pointday/"}
RAKUTEN_DEFAULT = "https://event.rakuten.co.jp/"
AMAZON_PAGE = {"/amazon/black-friday/": "https://www.amazon.co.jp/blackfriday", "/amazon/prime-day/": "https://www.amazon.co.jp/primeday", "/amazon/prime-day-early/": "https://www.amazon.co.jp/primeday"}
AMAZON_DEFAULT = "https://www.amazon.co.jp/gp/goldbox"
MALL_NAME = {"rakuten": "楽天市場", "amazon": "Amazon", "yahoo": "Yahoo!ショッピング"}
PROGRAMME = {"rakuten": "楽天アフィリエイト", "amazon": "Amazonアソシエイト", "vc": "バリューコマース", "a8": "A8.net"}

# A shop with no programme of the three ASPs: its stores in the malls (each opened in a browser on 2026-11-12: the store page opens and is the shop's own).  ("amazon_s" = a search page of Amazon.)
STORES = {
    "nitori": [("rakuten", "https://www.rakuten.co.jp/nitori/")],
    "dyson": [("rakuten", "https://www.rakuten.co.jp/dyson/"), ("yahoo", "https://store.shopping.yahoo.co.jp/dyson/"), ("amazon_s", "ダイソン")],
    "panasonic": [("rakuten", "https://www.rakuten.co.jp/panasonic-store/"), ("yahoo", "https://store.shopping.yahoo.co.jp/panasonic-store/"), ("amazon_s", "パナソニック")],
    "asus": [("rakuten", "https://www.rakuten.co.jp/asus-store/")],
    "nec": [("rakuten", "https://www.rakuten.co.jp/nec-direct/")],
    "zozo": [("yahoo", "https://store.shopping.yahoo.co.jp/zozo/")],
    "sharp": [("amazon_s", "シャープ")],
    "google": [("amazon_s", "Google Pixel")],
    "playstation": [("amazon_s", "PlayStation")],
}
# The shops of an ASP programme that is already ours (the programme's own landing page).
ASP = {"dhc": ("vc", "dhc", "https://www.dhc.co.jp/goods/campaign.jsp"), "xdomain": ("a8", "xdomain", ""), "xserver": ("a8", "xserver", "")}
ASP_BY_ID = {"c-xs-init": "xbiz"}                                  # エックスサーバー Business = the XServerビジネス programme
ASP_NAME = {"dhc": "DHC", "xdomain": "XServerドメイン", "xserver": "エックスサーバー", "xbiz": "XServerビジネス"}
MALLS = ("rakuten", "amazon", "yahoo")

# Shops with no link, and why (reported to the owner; the test pins that every shop of the calendar is here or has a link).
NO_LINK = {
    "yamada": "ヤマダウェブコム(yamada-denkiweb.com)は、3つのASPに案件がない(バリューコマースにあるのは別の店「ヤマダモール」ymall.jp)。楽天・Yahoo!の出店も、確認できたストアページがない",
    "sonystore": "3つのASPに案件がない。楽天市場・Yahoo!・Amazonの公式ストアは、開いて確かめられなかった",
    "lg": "3つのASPに案件がない。楽天市場・Yahoo!・Amazonの公式ストアは、開いて確かめられなかった",
    "uniqlo": "3つのASPに案件がない。楽天市場にもYahoo!ショッピングにも出店がない(ストアのページが開かなかった)",
    "stardomain": "A8.net・バリューコマース・アクセストレードの審査待ち。承認されたらリンクを付ける",
}


def rakuten_href(target: str) -> str:
    return f"https://hb.afl.rakuten.co.jp/hgc/{CFG['rakuten_affiliate_id']}/?pc={quote(target, safe='')}"


def amazon_href(target: str) -> str:
    return f"{target}?tag={CFG['amazon_tracking_id']}"


def amazon_search_href(term: str) -> str:
    return f"https://www.amazon.co.jp/s?k={quote(term, safe='')}&tag={CFG['amazon_tracking_id']}"


def vc_href(pid: str, url: str) -> str:
    return f"//ck.jp.ap.valuecommerce.com/servlet/referral?sid={VC_SID}&pid={pid}&vc_url={quote(url, safe='')}"


def vc_counter(pid: str) -> str:
    return f'<img src="//ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid={VC_SID}&amp;pid={pid}" height="1" width="0" border="0">'


def a8_href(key: str) -> str:
    return f"https://px.a8.net/svt/ejp?a8mat={A8_MAT[key][0]}"


def a8_pixel(key: str) -> str:
    mat, host = A8_MAT[key]
    return f'<img border="0" width="1" height="1" src="https://{host}.a8.net/0.gif?a8mat={mat}" alt="">'


def _link(kind: str, href: str, label: str, key: str = "") -> dict:
    return {"kind": kind, "href": href, "label": label, "key": key}


def links_for(it: dict) -> list[dict]:
    """The affiliate links of one calendar entry (a list: a shop with stores in several malls has one link per mall)."""
    mall, iid, page = it["mall"], it["id"].split("@")[0], it.get("href") or ""
    if mall == "rakuten":
        return [_link("rakuten", rakuten_href(RAKUTEN_EVENT.get(page, RAKUTEN_DEFAULT)), "楽天市場のページを見る")]
    if mall == "amazon":
        return [_link("amazon", amazon_href(AMAZON_PAGE.get(page, AMAZON_DEFAULT)), "Amazonのページを見る")]
    if mall == "yahoo":
        return [_link("vc", vc_href(VC_PID["yahoo"], YAHOO_GUIDE), "Yahoo!ショッピングのページを見る", "yahoo")]
    if mall in ASP:
        kind, key, url = ASP[mall]
        key = ASP_BY_ID.get(iid, key)
        name = ASP_NAME[key]
        if kind == "vc":
            return [_link("vc", vc_href(VC_PID[key], url), f"{name}のページを見る", key)]
        return [_link("a8", a8_href(key), f"{name}のサイトを見る", key)]
    out = []
    for kind, target in STORES.get(mall, []):
        name = ENT_NAME.get(mall, mall)
        if kind == "rakuten":
            out.append(_link("rakuten", rakuten_href(target), f"{name}の楽天市場ストアを見る"))
        elif kind == "yahoo":
            out.append(_link("vc", vc_href(VC_PID["yahoo"], target), f"{name}のYahoo!ショッピングストアを見る", "yahoo"))
        elif kind == "amazon_s":
            out.append(_link("amazon", amazon_search_href(target), f"Amazonで{target}を探す"))
    return out


ENT_NAME: dict[str, str] = {}      # filled by schedule.py (id -> name) so the labels name the shop


def anchor(l: dict, pixels: bool = True) -> str:
    """The link with its programme's 1x1 counter / pixel as given (the copy inside calendar.js's JSON, written into a day's detail by the script, has none: the lists in the page carry them)."""
    counter = vc_counter(VC_PID[l["key"]]) if l["kind"] == "vc" and pixels else ""
    pixel = a8_pixel(l["key"]) if l["kind"] == "a8" and pixels else ""
    return f'<a href="{escape(l["href"], quote=True)}" target="_blank" rel="{REL}">{escape(l["label"])}{counter}</a>{pixel}'


def lines(links: list[dict], cls: str = "aff-lines") -> str:
    """Each link on its own line with the PR mark (a mall's link never shares a line with another mall's)."""
    if not links:
        return ""
    return f'<div class="{cls}">' + "".join(f'<p class="aff-line"><span class="pr-chip">PR</span>{anchor(l)}</p>' for l in links) + "</div>"


def disclosure(links_present: set[str] | None = None) -> str:
    """The sentence near a heading: these links are advertisements."""
    amazon = f"Amazonのアソシエイトとして、{CFG.get('amazon_disclosure_name') or SITE_NAME}は適格販売により収入を得ています。"
    return (f'<p class="aff-disclose"><span class="pr-chip">PR</span>「PR」の付いたリンクは広告です(楽天アフィリエイト・Amazonアソシエイト・バリューコマース・A8.net)。'
            f'リンク先で購入や申し込みがあると、運営者に報酬が支払われることがあります。リンクの有無や報酬で、日程の内容を変えることはありません。{amazon}</p>')


AMAZON_PRODUCT_TERM = {"iphone-18-pro": "iPhone 18 Pro"}        # the search word of a product page's Amazon row (a search page, never a product, price or image)
PRODUCT_STORE_PROGRAMMES = ("Amazon",)                           # the rows of a product page that have a link: the store's name starts with one of these (Apple, 楽天モバイル, ソフトバンク: no programme)


def product_links(pr: dict, st: dict) -> list[dict]:
    if st["name"].startswith("Amazon"):
        term = AMAZON_PRODUCT_TERM.get(pr["slug"], pr["crumb"])
        return [_link("amazon", amazon_search_href(term), f"Amazonで{term}を探す")]
    return []
