"""kuma: 楽天モーションウィジェット(300x250)を、広告を出すページすべてに共通で入れる(オーナー指示 2026-11-22。計画 docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md)。
置き場所: ①リード直後(最初の本文ブロックの前) ②本文の中ほど(h2が6つ以上のページだけ) ③最後・関連の前。1ページ最大3つ。『PR』を真上に大きめに出す。ポップアップ・固定の帯は使わない。
人身被害・死亡を主題にしたページ(題に 死亡・死者・人身・被害 などが入るページ)は、最初の画面には置かず、本文の最後に1つだけ。
最初の節が死亡事故の節の都道府県ページは、リード直後には置かず、中ほどと最後だけ。広告を出さないページ(連絡先・プライバシー等・noindex)には出さない。
ウィジェットは楽天のスクリプトが商品を出す。商品情報はリポジトリにも出力にも保存しない(アフィリエイトIDは公開されるタグ)。ページごとの手書きはせず、build.py がここを呼ぶ。"""
from __future__ import annotations

import re

AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
WIDGET_SCRIPT = ('<script type="text/javascript">rakuten_design="slide";rakuten_affiliateId="%s";rakuten_items="ctsmatch";rakuten_genreId="0";rakuten_size="300x250";'
                 'rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";'
                 'rakuten_ts="1795331642284";</script><script type="text/javascript" src="https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"></script>') % AFFILIATE_ID
MARK = 'class="rk-ad"'
MAX_PER_PAGE = 3
MIDDLE_MIN_H2 = 6

# pages that never get one (the same list as the pages without the AdSense tag, plus the reference pages and the legal pages)
EXCLUDED = frozenset({"about/index.html", "privacy/index.html", "contact/index.html", "contact/thanks.html", "404.html", "search/index.html", "notify/index.html",
                      "live/index.html", "official/index.html", "notices/index.html", "map/index.html", "cite/index.html", "data/index.html"})
HARM_H1 = re.compile(r"死亡|死者|人身|被害|負傷|けが|襲")
HARM_H2 = re.compile(r"死亡|死者|人身被害")

_STYLE = ('<style>.rk-ad{margin:28px auto;max-width:340px;text-align:center}.rk-ad .rk-pr{margin:0 0 6px;font-size:1.05rem;font-weight:700;letter-spacing:.12em;color:#444}'
          '.rk-box{height:250px;overflow:hidden;display:flex;justify-content:center}.rk-in{flex:none;width:300px;height:250px}'
          '@media(max-width:339px){.rk-box{height:213px}.rk-in{transform:scale(.85);transform-origin:top center}}</style>\n')
_LEAD = re.compile(r'<h2[\s>]|<div class="(?:tabs|tablewrap|stats|chart-box)"|<ul class="(?:link-list|mini-list)"')
_TAGS = re.compile(r"<[^>]+>")


def block(first: bool) -> str:
    return (_STYLE if first else "") + f'<aside {MARK} aria-label="広告"><p class="rk-pr">PR</p><div class="rk-box"><div class="rk-in">{WIDGET_SCRIPT}</div></div></aside>\n'


def page_kind(t: str) -> str:
    """'harm' = the page is about deaths / injuries (the end only); 'harm_first' = a page whose first section is about deaths (no widget before the middle); else 'normal'."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    if h1 and HARM_H1.search(_TAGS.sub("", h1.group(1))):
        return "harm"
    m = re.search(r"<h2[^>]*>(.*?)</h2>", t[t.find("</h1>"):], re.S) if "</h1>" in t else None
    if m and HARM_H2.search(_TAGS.sub("", m.group(1))):
        return "harm_first"
    return "normal"


def eligible(rel: str, t: str) -> bool:
    return (rel.endswith(".html") and rel not in EXCLUDED and "<main" in t and "</h1>" in t and "noindex" not in t[: t.find("</head>")] and MARK not in t)


def _slots(rel: str, t: str) -> list[int]:
    """Character offsets in t where a widget goes, in page order (at most MAX_PER_PAGE)."""
    m_end = t.find("</main>")
    if m_end < 0:
        return []
    h1 = t.find("</h1>", t.find("<main"))
    if h1 < 0 or h1 > m_end:
        return []
    kind = page_kind(t)
    if rel == "index.html" and kind == "normal":      # the top page opens with the death counts: nothing before the middle
        kind = "harm_first"
    h2s = [h1 + m.start() for m in re.finditer(r"<h2[^>]*>", t[h1:m_end])]
    related = next((p for p in reversed(h2s) if re.match(r"<h2[^>]*>(?:<[^>]+>)*(?:関連|ほかの|他の)", t[p:p + 120])), None)
    last = related if related is not None else m_end
    pos: list[int] = []
    if kind == "normal":
        lead = _LEAD.search(t, h1 + 5, m_end)
        if lead and lead.start() < last:
            pos.append(lead.start())
    if kind in ("normal", "harm_first"):
        body = [p for p in h2s if p < last]
        if len(body) >= MIDDLE_MIN_H2:
            pos.append(body[len(body) // 2])
    pos.append(last)
    return sorted(set(pos))[:MAX_PER_PAGE]


def add(rel: str, t: str) -> str:
    if not eligible(rel, t):
        return t
    slots = _slots(rel, t)
    for i, p in enumerate(reversed(slots)):          # from the back, so earlier offsets stay valid
        t = t[:p] + block(first=(i == len(slots) - 1)) + t[p:]
    return t


def add_all(pages: dict) -> int:
    """Put the widgets into every eligible page of a built site (a dict rel -> html); returns how many pages changed."""
    n = 0
    for rel, t in pages.items():
        if isinstance(t, str):
            new = add(rel, t)
            if new != t:
                pages[rel] = new
                n += 1
    return n
