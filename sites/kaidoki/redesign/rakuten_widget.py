"""Rakuten motion widget (owner 2026-11-22, 2026-11-23; docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md): at most three blocks per page, put in by wrap() for every page but the 404.

2026-11-23: several products at once. By screen width: 760px and up = 728x200 (3 across), 480-759px = 468x160 (3 across), under 480px = 300x250 for the first block and
200x600 (3 down) for the others. Only the size that is shown is loaded (document.write); the hidden sizes are never fetched.
Link type: 1st and 2nd block = page match (ctsmatch), the last block (before the related articles) = ranking.
Places: after the lead (before the 2nd content block), in the middle of a long page, and before the related-article list (or at the end).
Each block is alone (no other mall's link inside), with a large 'PR' above it. No product data is stored here: the widget draws its own."""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"          # a public tag, not a secret
SCRIPT_URL = "https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"
TS = "1795398997582"

_VARS = ('rakuten_design="slide";rakuten_affiliateId="' + AFFILIATE_ID + '";rakuten_items="\'+m+\'";rakuten_genreId="0";rakuten_size="\'+s+\'";rakuten_target="_blank";'
         'rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";rakuten_ts="' + TS + '";')
SCRIPT_TMPL = ('<script>(function(){var w=window.innerWidth||document.documentElement.clientWidth||375,m="__M__",s=w>=760?"728x200":(w>=480?"468x160":"__MOBILE__");'
               "var c='<scr'+'ipt type=\"text/javascript\">" + _VARS + "</scr'+'ipt><scr'+'ipt type=\"text/javascript\" src=\"" + SCRIPT_URL + "\"></scr'+'ipt>';"
               "document.write(c);})();</script>")

# (link type, size under 480px) for the first / a middle / the last block
FIRST = ("ctsmatch", "300x250")
MIDDLE = ("ctsmatch", "200x600")
LAST = ("ranking", "200x600")


def block(kind: str, mobile: str) -> str:
    script = SCRIPT_TMPL.replace("__M__", kind).replace("__MOBILE__", mobile)
    return ('<aside class="rk-widget" aria-label="広告(楽天市場)"><p class="rk-pr"><span class="pr-chip">PR</span>楽天市場のおすすめ(広告)</p>'
            f'<div class="rk-frame rk-m{mobile.split("x")[1]}">' + script + '</div></aside>')


CANDIDATE = re.compile(r'<section class="(?:content-block|section)[ "]')
RELATED = re.compile(r'<h2[^>]*>[^<]*</h2>\s*<div class="article-links"')
CREDIT = re.compile(r'<p class="credit">')
MIN_FOR_MIDDLE = 7


def inject(body: str) -> str:
    cands = [m.start() for m in CANDIDATE.finditer(body)]
    credit = CREDIT.search(body)
    tail = credit.start() if credit else len(body)
    pos: list[tuple[int, tuple[str, str]]] = []
    pos.append((cands[1] if len(cands) >= 2 else tail, FIRST))
    if len(cands) >= MIN_FOR_MIDDLE:
        pos.append((cands[len(cands) // 2], MIDDLE))
    rel = RELATED.search(body)
    if rel:
        end = rel.start()
    elif len(cands) >= MIN_FOR_MIDDLE and 'class="section' in body[cands[0]:cands[0] + 40]:
        end = cands[-2]                       # the home page: before its second-last section
    else:
        end = tail
    if end <= pos[-1][0]:                     # the credit line sits above the places already used: put the last block at the very end
        end = len(body)
    pos.append((end, LAST))
    keep: list[tuple[int, tuple[str, str]]] = []
    for p, spec in pos:                       # in order, one block per place
        if not keep or p > keep[-1][0]:
            keep.append((p, spec))
    for p, (kind, mobile) in reversed(keep):
        body = body[:p] + block(kind, mobile) + body[p:]
    return body
