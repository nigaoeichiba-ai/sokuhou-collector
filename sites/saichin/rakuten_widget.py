"""楽天モーションウィジェット(300x250)を、saichin の全ページ(広告を出さないページを除く)に共通で入れる(オーナー指示 2026-11-22。計画 docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md)。
置き場所: ①リード直後 ②本文の中ほど(h2が6つ以上の長いページだけ) ③最後・関連ページの前。1ページ最大3つ。『PR』を真上に大きめに出す。ポップアップ・固定の帯は使わない。
ウィジェットは楽天のスクリプトが商品を出す。商品情報はリポジトリにも出力にも保存しない(アフィリエイトIDは公開されるタグ)。
layout() が本文(body)に対して呼ぶ。AdSense のコードと ads.txt には触らない。広告を出さないページ(NO_ADS_PATHS と運営者情報・プライバシー)にはウィジェットも出さない。
CSS は assets/style.css の .rk-ad。"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
WIDGET_SCRIPT = ('<script type="text/javascript">rakuten_design="slide";rakuten_affiliateId="%s";rakuten_items="ctsmatch";rakuten_genreId="0";rakuten_size="300x250";'
                 'rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";'
                 'rakuten_ts="1795331642284";</script><script type="text/javascript" src="https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"></script>') % AFFILIATE_ID
MARK = 'class="rk-ad"'
MAX_PER_PAGE = 3
MIDDLE_MIN_H2 = 6
# 広告(AdSense・楽天)を出さないページ。build.NO_ADS_PATHS に加えて、法的な固定ページ。
EXTRA_SKIP = {"/about/", "/privacy/"}


def block() -> str:
    return f'<aside {MARK} aria-label="広告"><p class="rk-pr">PR</p><div class="rk-box"><div class="rk-in">{WIDGET_SCRIPT}</div></div></aside>\n'


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
    for p in reversed(_slots(body)):                  # from the back, so earlier offsets stay valid
        body = body[:p] + block() + body[p:]
    return body
