"""楽天モーションウィジェット(複数商品が並ぶ型)を、トップ・カテゴリ・記事の全ページに共通で入れる(オーナー指示 2026-11-22。計画 docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md)。
置き場所: ①リード直後 ②本文の中ほど(h2が6つ以上の長いページだけ) ③最後・関連記事の前。1ページ最大3つ。『PR』を真上に大きめに出す。ポップアップ・固定の帯は使わない。
ウィジェットは楽天のスクリプトが商品を出す。商品情報はリポジトリにも出力にも保存しない(アフィリエイトIDは公開されるタグ)。ページごとの手書きはせず、hooks.post() がここを呼ぶ。"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
RAKUTEN_TS = "1795398997582"
MARK = 'class="rk-ad"'
MAX_PER_PAGE = 3
MIDDLE_MIN_H2 = 6

# 2026-11-23(オーナー指示): 複数商品が一度に並ぶ型。画面幅で切り替える(760px以上=728x200 横3枠、480〜759=468x160 横3枠、480未満=200x600 縦3枠)。
# スマホの1つ目(リード直後)だけ、最初の画面を埋めないよう300x250のまま。リンクタイプは、最後=ranking、ほか=ctsmatch。
# 表示する型のスクリプトだけを document.write で出す(隠した型は読み込まない)。
_JS = (r"""(function(){var w=window.innerWidth||document.documentElement.clientWidth||375,m="%(m)s",s=w>=760?"728x200":(w>=480?"468x160":"%(small)s");"""
       r"""var c='<scr'+'ipt type="text/javascript">rakuten_design="slide";rakuten_affiliateId="%(id)s";rakuten_items="'+m+'";rakuten_genreId="0";rakuten_size="'+s+'";"""
       r"""rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";rakuten_ts="%(ts)s";</scr'+'ipt>"""
       r"""<scr'+'ipt type="text/javascript" src="https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"></scr'+'ipt>';document.write(c);})();""")

_STYLE = ('<style>.rk-ad{margin:28px auto;max-width:728px;text-align:center}.rk-ad .rk-pr{margin:0 0 6px;font-size:1.05rem;font-weight:700;letter-spacing:.12em;color:#444}'
          '.rk-box{display:flex;justify-content:center;overflow:hidden;height:600px}.rk-box.rk-first{height:250px}'
          '@media(min-width:480px){.rk-box,.rk-box.rk-first{height:160px}}@media(min-width:760px){.rk-box,.rk-box.rk-first{height:200px}}'
          '@media(max-width:339px){.rk-box.rk-first>div{transform:scale(.85);transform-origin:top center}.rk-box.rk-first{height:213px}}</style>')


def block(first: bool, kind: str = "ctsmatch", top: bool | None = None) -> str:
    """first: the style tag goes with this block.  top: the lead one (300x250 on a phone).  kind: ctsmatch (page match) or ranking."""
    top = first if top is None else top
    js = _JS % {"m": kind, "small": "300x250" if top else "200x600", "id": AFFILIATE_ID, "ts": RAKUTEN_TS}
    cls = "rk-box rk-first" if top else "rk-box"
    return (_STYLE if first else "") + f'<aside {MARK} aria-label="広告"><p class="rk-pr">PR</p><div class="{cls}"><div><script>{js}</script></div></div></aside>'


def _slots(rel: str, t: str) -> list[int]:
    """Character offsets in t where a widget goes, in page order (at most MAX_PER_PAGE)."""
    m_end = t.find("</main>")
    if m_end < 0:
        m_end = t.find("<footer")
    if rel == "index.html":
        pos = [t.find('<section class="block wrap" aria-labelledby="todayTitle">'), t.find('<section class="block wrap" aria-labelledby="articlesTitle">'),
               t.find('<section class="block wrap" aria-labelledby="stdTitle">')]
        return [p for p in pos if p > 0]
    main = t.find("<main")
    h1 = t.find("</h1>", main)
    if h1 < 0:
        return []
    h2s = [m.start() for m in re.finditer(r"<h2[^>]*>", t[h1:m_end])]
    h2s = [h1 + p for p in h2s]
    if rel.startswith("cat/"):
        cards = t.find('<div class="cards">', h1)
        return [p for p in (cards, h2s[0] if h2s else -1) if p > 0]
    if not h2s:
        return []
    related = next((p for p in h2s if t.startswith("<h2>関連するページ</h2>", p)), None)
    last = related if related is not None else (t.find('<p class="credit"', h1) if t.find('<p class="credit"', h1) > 0 else m_end)
    body = [p for p in h2s if p < last]
    pos = [body[0]] if body else []
    if len(body) >= MIDDLE_MIN_H2:
        pos.append(body[len(body) // 2])
    pos.append(last)
    return sorted(set(pos))[:MAX_PER_PAGE]


def add(rel: str, t: str) -> str:
    if MARK in t:
        return t
    slots = _slots(rel, t)
    n = len(slots)
    for i in range(n - 1, -1, -1):                   # from the back, so earlier offsets stay valid
        kind = "ranking" if (i == n - 1 and n > 1) or (n == 1) else "ctsmatch"
        t = t[:slots[i]] + block(first=(i == 0), kind=kind, top=(i == 0)) + t[slots[i]:]
    return t
