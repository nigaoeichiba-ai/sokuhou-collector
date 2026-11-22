"""楽天モーションウィジェットを、全ページに共通の位置で入れる(2026-11-22 オーナー指示。計画: sokuhou-sites/docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md)。

置き場所は <main> の直下のブロックの切れ目だけ(ブロックの中には入れない。絵・ダウンロードボタン・埋め込みコードの邪魔をしない):
  1. 最初の答え(h1 を含むブロック、そのあとの lead 段落・利用条件の枠)の直後
  2. 長いページだけ、残りのブロックの中ほど
  3. 最後のブロック(関連記事)の前
1ページ最大3つ。どれも『PR』の表示つきで、部品は単独のブロック(他モールのリンクは混ぜない)。
楽天の商品情報はウィジェットが閲覧時に出す。このリポジトリにも出力にも、商品の情報は入れない(アフィリエイトID は公開されるタグ)。
"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
WIDGET_SRC = "https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"
MAX_PER_PAGE = 3
SKIP = {"404.html", "contact/thanks.html"}      # nothing to read there

# the widget's own code (motion widget, page match, image + text, 300x250, rotation on, 2026-11-22)
WIDGET_JS = (f'rakuten_design="slide";rakuten_affiliateId="{AFFILIATE_ID}";rakuten_items="ctsmatch";rakuten_genreId="0";rakuten_size="300x250";'
             'rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";'
             'rakuten_ts="1795331642284";')

MARK = 'class="rk-ad"'


def widget_block(n: int) -> str:
    label = "楽天市場のおすすめ" if n == 0 else "楽天市場でさがす"
    return (f'<aside class="rk-ad" aria-label="広告(楽天市場)"><p class="rk-pr"><b>PR</b><span>{label}</span></p>'
            f'<div class="rk-box"><script type="text/javascript">{WIDGET_JS}</script>'
            f'<script type="text/javascript" src="{WIDGET_SRC}"></script></div></aside>\n')


_TAG = re.compile(r"<!--.*?-->|<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>", re.S)
_VOID = {"img", "br", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "embed", "param", "track"}
_RAW = {"script", "style", "textarea"}
_TAIL_CLASS = {"pager", "prevnext", "share"}


def top_blocks(inner: str) -> list[tuple[int, int, str, str]]:
    """The elements that sit directly in <main>: (start, end, tag, opening tag text)."""
    out, depth, start, tag0, open0, pos = [], 0, 0, "", "", 0
    while True:
        m = _TAG.search(inner, pos)
        if not m:
            break
        pos = m.end()
        if m.group(2) is None:                                   # a comment
            continue
        closing, tag = m.group(1) == "/", m.group(2).lower()
        if not closing and tag in _RAW:
            end = re.compile(rf"</{tag}\s*>", re.I).search(inner, pos)
            pos = end.end() if end else len(inner)
            if depth == 0:
                out.append((m.start(), pos, tag, m.group(0)))
            continue
        if tag in _VOID:
            if depth == 0 and not closing:
                out.append((m.start(), m.end(), tag, m.group(0)))
            continue
        if closing:
            depth = max(0, depth - 1)
            if depth == 0:
                out.append((start, m.end(), tag0, open0))
        else:
            if depth == 0:
                start, tag0, open0 = m.start(), tag, m.group(0)
            depth += 1
    return out


def insertion_points(inner: str) -> list[int]:
    """Offsets in the text of <main> where a widget goes (0 to 3 of them, ascending)."""
    blocks = top_blocks(inner)
    if not blocks:
        return []
    h1 = next((i for i, b in enumerate(blocks) if "<h1" in inner[b[0]:b[1]]), None)
    if h1 is None:
        return []
    j = h1
    for _ in range(2):                                           # the lead paragraph and the licence strip belong to the first answer
        if j + 1 < len(blocks) and (('class="lead"' in blocks[j + 1][3] and blocks[j + 1][2] == "p") or 'licence-box' in blocks[j + 1][3]):
            j += 1
    points = [blocks[j][1]]
    rest = blocks[j + 1:]
    body = list(rest)
    while body and (body[-1][2] in ("script", "style") or _TAIL_CLASS & set(re.findall(r'class="([^"]*)"', body[-1][3])[0].split() if 'class=' in body[-1][3] else [])):
        body.pop()                                               # trailing structured data, page links and the share strip are not content
    if len(body) >= 2:
        last = body[-1]
        points.append(last[0] if last[2] in ("section", "aside") else last[1])
    if len(body) >= 7:
        mid = body[len(body) // 2]
        if points[0] < mid[0] < points[-1]:
            points.insert(1, mid[0])
    return sorted(set(points))[:MAX_PER_PAGE]


def add_widgets(html: str) -> str:
    if MARK in html:
        return html
    m = re.search(r"(<main\b[^>]*>)(.*?)(</main>)", html, re.S)
    if not m:
        return html
    inner = m.group(2)
    pts = insertion_points(inner)
    if not pts:
        return html
    out, last = [], 0
    for n, p in enumerate(pts):
        out.append(inner[last:p])
        out.append(("\n" if inner[p - 1:p] != "\n" else "") + widget_block(n))
        last = p
    out.append(inner[last:])
    return html[:m.start(2)] + "".join(out) + html[m.end(2):]


def add_to_pages(pages: dict) -> int:
    """Put the widgets into every built HTML page (before the sitemap is made; thin and noindex pages included). Returns the number of pages changed."""
    n = 0
    for rel, text in list(pages.items()):
        if isinstance(text, str) and rel.endswith(".html") and rel not in SKIP:
            new = add_widgets(text)
            if new != text:
                pages[rel] = new
                n += 1
    return n
