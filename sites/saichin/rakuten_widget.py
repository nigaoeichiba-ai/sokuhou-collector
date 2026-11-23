"""楽天モーションウィジェットを、saichin の全ページ(広告を出さないページを除く)に共通で入れる(オーナー指示 2026-11-22。2026-11-23 に、複数商品が一度に並ぶ型へ変更。
計画 docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md の末尾「2026-11-23 変更」)。
型は画面幅で切り替える(表示する型のスクリプトだけを document.write で出す): 800px以上=728x200(横3枠)、540〜799px=468x160(横3枠)(本文の枠は画面幅-32px、スクロールバーでさらに狭くなるため。kaidoki と同じ切替幅)、
540px未満=200x600(縦3枠)。ただしスマホの1つ目(リード直後)は、最初の画面を広告で埋めないよう300x250のまま。
リンクタイプ: 1つ目・2つ目=ページマッチ(ctsmatch)、最後(関連の前)=人気ランキング(ranking)。
置き場所: ①リード直後 ②本文の中ほど(h2が6つ以上の長いページだけ) ③最後・関連ページの前。1ページ最大3つ。『PR』を真上に大きめに出す。ポップアップ・固定の帯なし。
商品情報はリポジトリにも出力にも保存しない(楽天のスクリプトが出す。アフィリエイトIDは公開されるタグ)。layout() が本文(body)に対して呼ぶ。
AdSense のコードと ads.txt には触らない。広告を出さないページ(NO_ADS_PATHS と運営者情報・プライバシー)にはウィジェットも出さない。CSS は assets/style.css の .rk-ad。"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
MARK = 'class="rk-ad"'
MAX_PER_PAGE = 3
MIDDLE_MIN_H2 = 6
# 広告(AdSense・楽天)を出さないページ。build.NO_ADS_PATHS に加えて、法的な固定ページ。
EXTRA_SKIP = {"/about/", "/privacy/"}
# 型(幅×高さ)と、確保する最小の高さ(読み込み後のずれを小さくする)
HEIGHTS = {"728x200": 200, "468x160": 160, "200x600": 600, "300x250": 250}
# 画面幅ごとの型: (800px以上, 540〜799px, 540px未満)
SIZES = {"first": ("728x200", "468x160", "300x250"), "middle": ("728x200", "468x160", "200x600"), "last": ("728x200", "468x160", "200x600")}
ITEMS = {"first": "ctsmatch", "middle": "ctsmatch", "last": "ranking"}

# 楽天の部品の呼び出しを、画面幅で選んだ型の1組だけ document.write で出す。タグを分けて書くのは、ブラウザが外側の script を早く閉じないため。
_JS = (
    '<script type="text/javascript">(function(){var w=window.innerWidth||document.documentElement.clientWidth||375,'
    'm="%(item)s",s=w>=800?"%(wide)s":(w>=540?"%(mid)s":"%(narrow)s"),H=%(heights)s;'
    "var c='<div class=\"rk-in rk-'+s+'\" style=\"min-height:'+H[s]+'px\"><scr'+'ipt type=\"text/javascript\">rakuten_design=\"slide\";rakuten_affiliateId=\"%(id)s\";"
    "rakuten_items=\"'+m+'\";rakuten_genreId=\"0\";rakuten_size=\"'+s+'\";rakuten_target=\"_blank\";rakuten_theme=\"gray\";rakuten_border=\"off\";"
    "rakuten_auto_mode=\"on\";rakuten_genre_title=\"off\";rakuten_recommend=\"on\";rakuten_ts=\"1795398997582\";</scr'+'ipt>"
    "<scr'+'ipt type=\"text/javascript\" src=\"https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106\"></scr'+'ipt></div>';"
    "document.write(c);})();</script>"
)


def widget_script(kind: str) -> str:
    wide, mid, narrow = SIZES[kind]
    heights = "{" + ",".join(f'"{k}":{v}' for k, v in HEIGHTS.items()) + "}"
    return _JS % {"item": ITEMS[kind], "wide": wide, "mid": mid, "narrow": narrow, "heights": heights, "id": AFFILIATE_ID}


def block(kind: str = "first") -> str:
    return f'<aside {MARK} aria-label="広告"><p class="rk-pr">PR</p><div class="rk-box">{widget_script(kind)}</div></aside>\n'


def _slots(t: str) -> list[int]:
    """Character offsets in body t where a widget goes, in page order (at most MAX_PER_PAGE)."""
    h1 = t.find("</h1>")
    start = h1 if h1 >= 0 else 0
    m = re.search(r'<p class="lead">.*?</p>', t[start:], re.S)
    if m:
        first = start + m.end()
        if t[first:first + 1] == "\n":
            first += 1
    elif h1 >= 0:
        first = h1 + len("</h1>")
    else:
        return []
    h2s = [first + x.start() for x in re.finditer(r"<h2[^>]*>", t[first:])]
    related = next((p for p in h2s if t.startswith("<h2>関連ページ</h2>", p)), None)
    last = related if related is not None else len(t)
    body_h2 = [p for p in h2s if p < last]
    pos = [first]
    if len(body_h2) >= MIDDLE_MIN_H2:
        pos.append(body_h2[len(body_h2) // 2])
    pos.append(last)
    return sorted(set(pos))[:MAX_PER_PAGE]


def applies(path: str, no_ads: set[str]) -> bool:
    return path not in no_ads and path not in EXTRA_SKIP


def add(path: str, body: str, no_ads: set[str]) -> str:
    """body with the widgets put in; unchanged if the page shows no ads or already has them."""
    if not applies(path, no_ads) or MARK in body:
        return body
    slots = _slots(body)
    for i in range(len(slots) - 1, -1, -1):           # from the back, so earlier offsets stay valid
        kind = "first" if i == 0 else ("last" if i == len(slots) - 1 else "middle")
        body = body[:slots[i]] + block(kind) + body[slots[i]:]
    return body
