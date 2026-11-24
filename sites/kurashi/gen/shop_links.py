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
    "/iryouhi-koujo/": ("領収書の整理用品を探すなら", "領収書をとじておくファイルは、検索ページから探せます。", ["領収書 整理 ファイル"], ["領収書 整理 ファイル"]),
    "/kakutei-shinkoku/junbi/": ("書類の整理用品を探すなら", "源泉徴収票や控除証明書をまとめるファイルは、検索ページから探せます。", ["書類 整理 ファイル"], ["書類 整理 ファイル"]),
    "/nenmatsu-chosei/": ("年末調整の書き方の本を探すなら", "年末調整の入門書は、検索ページから探せます。", ["年末調整 書き方 本"], ["年末調整 書き方 本"]),
    "/life/kaigo/": ("介護保険の入門書を探すなら", "介護保険の入門書は、検索ページから探せます。", ["介護保険 入門 本"], ["介護保険 入門 本"]),
    "/life/shibo/": ("死亡後の手続きの本を探すなら", "手続きの流れを書いた本は、検索ページから探せます。", ["死亡後の手続き 本"], ["死亡後の手続き 本"]),
    "/life/taishoku/": ("退職後の手続きの本を探すなら", "退職後の保険と年金の手続きの本は、検索ページから探せます。", ["退職 手続き 本"], ["退職 手続き 本"]),
    "/life/kekkon/": ("結婚の手続きの本を探すなら", "結婚の手続きを書いた本は、検索ページから探せます。", ["結婚 手続き 本"], ["結婚 手続き 本"]),
    "/month/2/": ("確定申告の書き方の本を探すなら", "申告書の書き方の本は、検索ページから探せます。", ["確定申告 書き方 本"], ["確定申告 書き方 本"]),
    "/month/11/": ("年末調整の書き方の本を探すなら", "年末調整の入門書は、検索ページから探せます。", ["年末調整 書き方 本"], ["年末調整 書き方 本"]),
    "/kakutei-shinkoku/hitsuyo/": ("確定申告の書き方の本を探すなら", "申告が必要とわかったあとの書き方の本は、検索ページから探せます。", ["確定申告 書き方 本"], ["確定申告 書き方 本"]),
    "/kakutei-shinkoku/kanpu/": ("還付申告の書類を整理するなら", "源泉徴収票や領収書をまとめるファイルは、検索ページから探せます。", ["書類 整理 ファイル"], ["書類 整理 ファイル"]),
    "/moving/menkyo-sha/": ("引っ越しの用品を探すなら", "引っ越しの荷造りの用品は、検索ページから探せます。", ["引越し 段ボール"], ["引越し 段ボール"]),
    "/month/3/": ("3月の引っ越しの用品を探すなら", "段ボールや養生テープは、検索ページから探せます。", ["引越し 段ボール", "引越し 養生テープ"], ["引越し 段ボール", "引越し 養生テープ"]),
    "/month/1/": ("ふるさと納税の返礼品を探すなら", "返礼品は、楽天市場の検索ページから探せます。", ["ふるさと納税"], []),
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


# 2026-11-13: an A8.net programme (年賀状スクウェア / しまうまプリント) on /nengajo/.  The code is the text link of the SALEカレンダー media (007):
# kurashi has no media of its own at A8 yet, so replace the code (and the pixel host) once the media is registered.  Words and form as A8 gave them (a8mat only), PR note first.
A8_SECTIONS = {
    "/nengajo/": ("ネットで注文するなら【PR】", "年賀状を自分で作る時間がないなら、印刷をネットで頼む手もあります。締切は会社ごとに違います。引受開始の12月20日以降に出す日程から逆算して、注文の日を決めます。",
                  "4BGH3G+CRMUQI+33J0+15OK2A", "www15", "喪中・年賀状印刷は年賀状スクウェアで"),
    "/nenmatsu-nenshi/": ("年賀状の準備をネットで済ませるなら【PR】", "年末年始は、役所や銀行の窓口が閉まる期間と、年賀状の差し出しの日程が重なります。印刷をネットで頼むなら、引受開始の12月20日以降に出す日から逆算して、注文の日を決めます。締切は会社ごとに違うので、注文画面の案内に従います。",
                         "4BGH3G+CRMUQI+33J0+15OK2A", "www15", "喪中・年賀状印刷は年賀状スクウェアで"),
    "/month/12/": ("年賀状をネットで注文するなら【PR】", "12月は年賀状の準備の月です。印刷をネットで頼むなら、引受開始の12月20日以降に出す日から逆算して、注文の日を決めます。締切は会社ごとに違います。",
                   "4BGH3G+CRMUQI+33J0+15OK2A", "www15", "喪中・年賀状印刷は年賀状スクウェアで"),
}


def a8_section(path: str) -> dict:
    h2, intro, mat, host, label = A8_SECTIONS[path]
    html = ('<p class="pr-note"><strong>【PR】</strong>このリンクは広告（アフィリエイト）です。</p>'
            f'<p><a href="https://px.a8.net/svt/ejp?a8mat={mat}" {REL}>{label}</a>\n'
            f'<img border="0" width="1" height="1" src="https://{host}.a8.net/0.gif?a8mat={mat}" alt=""></p>')
    return {"h2": h2, "paras": [intro], "html": html}


# 2026-11-25: AccessTrade programmes of this site (media 1170205), joined 11/25.  href, rk and the 1x1 image are as issued (the terms forbid changing them);
# the link words are the issued words.  Conditions: docs/office/A8_PROGRAMS.md (BIGLOBE: PR shown, no price unless the tax-included total, no copy of the official site).
AT_REL = 'rel="nofollow sponsored noopener" referrerpolicy="no-referrer-when-downgrade" target="_blank"'
AT_PORTA = ("引っ越し業者を手配するなら【PR】", "引っ越しの日が決まったら、業者の手配に進みます。サービスの内容と条件は、申し込み先の画面に書かれています。",
            "0100q8vc00p2xp", "引っ越しポルタ")
AT_BIGLOBE = ("引っ越し先のネット回線を申し込むなら【PR】", "光回線は申し込みから開通まで日数がかかることがあるので、引っ越し日が決まったら早めに手配します。対応する地域と料金も、申し込み先の画面に書かれています。",
              "0100q7ix00p2xp", "【公式】BIGLOBE光プラス by auひかりプラス")
AT_SECTIONS = {path: [AT_PORTA, AT_BIGLOBE] for path in ("/moving/", "/moving/tenshutsu/", "/month/3/", "/shin-seikatsu/")}


def at_sections(path: str) -> list[dict]:
    out = []
    for h2, intro, rk, label in AT_SECTIONS[path]:
        html = ('<p class="pr-note"><strong>【PR】</strong>このリンクは広告（アフィリエイト）です。</p>'
                f'<p><a href="https://h.accesstrade.net/sp/cc?rk={rk}" {AT_REL}>{label}'
                f'<img src="https://h.accesstrade.net/sp/rr?rk={rk}" width="1" height="1" border="0" alt=""></a></p>')
        out.append({"h2": h2, "paras": [intro], "html": html})
    return out
