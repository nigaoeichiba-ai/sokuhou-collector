"""楽天モーションウィジェット(300x250)を、トップ・カテゴリ・記事の全ページに共通で入れる(オーナー指示 2026-11-22。計画 docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md)。
置き場所: ①リード直後 ②本文の中ほど(h2が6つ以上の長いページだけ) ③最後・関連記事の前。1ページ最大3つ。『PR』を真上に大きめに出す。ポップアップ・固定の帯は使わない。
ウィジェットは楽天のスクリプトが商品を出す。商品情報はリポジトリにも出力にも保存しない(アフィリエイトIDは公開されるタグ)。ページごとの手書きはせず、hooks.post() がここを呼ぶ。"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
WIDGET_SCRIPT = ('<script type="text/javascript">rakuten_design="slide";rakuten_affiliateId="%s";rakuten_items="ctsmatch";rakuten_genreId="0";rakuten_size="300x250";'
                 'rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";'
                 'rakuten_ts="1795331642284";</script><script type="text/javascript" src="https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"></script>') % AFFILIATE_ID
MARK = 'class="rk-ad"'
MAX_PER_PAGE = 3
MIDDLE_MIN_H2 = 6

_STYLE = ('<style>.rk-ad{margin:28px auto;max-width:340px;text-align:center}.rk-ad .rk-pr{margin:0 0 6px;font-size:1.05rem;font-weight:700;letter-spacing:.12em;color:#444}'
          '.rk-box{height:250px;overflow:hidden;display:flex;justify-content:center}.rk-in{flex:none;width:300px;height:250px}'
          '@media(max-width:339px){.rk-box{height:213px}.rk-in{transform:scale(.85);transform-origin:top center}}</style>\n')


def block(first: bool) -> str:
    return (_STYLE if first else "") + f'<aside {MARK} aria-label="広告"><p class="rk-pr">PR</p><div class="rk-box"><div class="rk-in">{WIDGET_SCRIPT}</div></div></aside>\n'


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
    for i, p in enumerate(reversed(slots)):          # from the back, so earlier offsets stay valid
        t = t[:p] + block(first=(i == len(slots) - 1)) + t[p:]
    return t
