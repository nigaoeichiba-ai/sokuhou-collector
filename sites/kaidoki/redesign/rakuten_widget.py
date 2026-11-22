"""Rakuten motion widget (owner 2026-11-22, docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md): at most three blocks per page, put in by wrap() for every page but the 404.

Places: after the lead (before the 2nd content block), in the middle of a long page, and before the related-article list (or at the end).
Each block is alone (no other mall's link inside), with a large 'PR' above it. No product data is stored here: the widget draws its own."""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"          # a public tag, not a secret
SCRIPT = ('<script type="text/javascript">rakuten_design="slide";rakuten_affiliateId="' + AFFILIATE_ID + '";rakuten_items="ctsmatch";rakuten_genreId="0";'
          'rakuten_size="300x250";rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";'
          'rakuten_recommend="on";rakuten_ts="1795331642284";</script>'
          '<script type="text/javascript" src="https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"></script>')
BLOCK = ('<aside class="rk-widget" aria-label="広告(楽天市場)"><p class="rk-pr"><span class="pr-chip">PR</span>楽天市場のおすすめ(広告)</p>'
         '<div class="rk-frame">' + SCRIPT + '</div></aside>')

CANDIDATE = re.compile(r'<section class="(?:content-block|section)[ "]')
RELATED = re.compile(r'<h2[^>]*>[^<]*</h2>\s*<div class="article-links"')
CREDIT = re.compile(r'<p class="credit">')
MIN_FOR_MIDDLE = 7


def inject(body: str) -> str:
    cands = [m.start() for m in CANDIDATE.finditer(body)]
    pos: list[int] = []
    if len(cands) >= 2:
        pos.append(cands[1])
    else:
        c = CREDIT.search(body)
        pos.append(c.start() if c else len(body))
    if len(cands) >= MIN_FOR_MIDDLE:
        pos.append(cands[len(cands) // 2])
    rel = RELATED.search(body)
    if rel:
        end = rel.start()
    elif len(cands) >= MIN_FOR_MIDDLE and 'class="section' in body[cands[0]:cands[0] + 40]:
        end = cands[-2]                       # the home page: before its second-last section
    else:
        c = CREDIT.search(body)
        end = c.start() if c else len(body)
    pos.append(end)
    keep: list[int] = []
    for p in pos:                             # in order, one block per place
        if not keep or p > keep[-1]:
            keep.append(p)
    for p in reversed(keep):
        body = body[:p] + BLOCK + body[p:]
    return body
