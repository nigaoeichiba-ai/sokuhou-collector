"""2026-11-13: a short 'search for it' section (Rakuten / Amazon search pages, PR) on the pages whose topic has something to buy.
No product names, prices or images.  Used by gen/__init__.py (all_pages) and by tests/test_kurashi_affiliate.py."""
from urllib.parse import quote

RID = "583f273a.77c989b6.583f273b.0a6a5fff"
TAG = "amazonmacs-22"
REL = 'rel="nofollow sponsored noopener" target="_blank"'

# path -> (heading, one sentence, search words for Rakuten, search words for Amazon ([] = none))
SHOP_PAGES = {
    "/nengajo/": ("年賀状の印刷と用品を探すなら", "年賀状の印刷や用品は、検索ページから探せます。", ["年賀状 印刷"], ["年賀状 印刷"]),
    "/kakutei-shinkoku/": ("確定申告の本を探すなら", "書き方の本は、検索ページから探せます。", ["確定申告 書き方 本"], ["確定申告 書き方 本"]),
    "/furusato/one-stop/": ("ふるさと納税の返礼品を探すなら", "返礼品は、楽天市場の検索ページから探せます。", ["ふるさと納税"], []),
    "/furusato/deadline/": ("ふるさと納税の返礼品を探すなら", "返礼品は、楽天市場の検索ページから探せます。", ["ふるさと納税"], []),
    "/kakutei-shinkoku/furusato/": ("ふるさと納税の返礼品を探すなら", "返礼品は、楽天市場の検索ページから探せます。", ["ふるさと納税"], []),
    "/kafun/": ("花粉の対策グッズを探すなら", "マスクや空気清浄機は、検索ページから探せます。", ["花粉 マスク", "空気清浄機 花粉"], ["花粉 マスク", "空気清浄機 花粉"]),
    "/moving/": ("引っ越しの用品を探すなら", "段ボールや養生テープは、検索ページから探せます。", ["引越し 段ボール", "引越し 養生テープ"], ["引越し 段ボール", "引越し 養生テープ"]),
    "/moving/tenshutsu/": ("引っ越しの用品を探すなら", "段ボールや梱包材は、検索ページから探せます。", ["引越し 段ボール", "梱包 緩衝材"], ["引越し 段ボール", "梱包 緩衝材"]),
    "/shin-seikatsu/": ("新生活の用品を探すなら", "新生活の家電や日用品は、検索ページから探せます。", ["新生活 家電セット", "新生活 日用品 セット"], ["新生活 家電セット", "新生活 日用品 セット"]),
    "/life/birth/": ("出産前後の用品を探すなら", "出産準備の用品は、検索ページから探せます。", ["出産準備 セット"], ["出産準備 セット"]),
}


def rakuten(kw: str) -> str:
    inner = quote("https://search.rakuten.co.jp/search/mall/" + quote(kw) + "/", safe="")
    return f'<a href="https://hb.afl.rakuten.co.jp/hgc/{RID}/?pc={inner}" {REL}>楽天市場で「{kw}」を探す</a>（PR）'


def amazon(kw: str) -> str:
    return f'<a href="https://www.amazon.co.jp/s?k={quote(kw)}&amp;tag={TAG}" {REL}>Amazonで「{kw}」を探す</a>（PR）'


def section(path: str) -> dict:
    h2, intro, rk, am = SHOP_PAGES[path]
    ul = lambda f, ks: "<ul>" + "".join(f"<li>{f(k)}</li>" for k in ks) + "</ul>"
    html = "<p>楽天市場の検索ページ</p>" + ul(rakuten, rk)
    if am:
        html += "<p>Amazonの検索ページ</p>" + ul(amazon, am)
    return {"h2": h2, "paras": [intro], "html": html}
