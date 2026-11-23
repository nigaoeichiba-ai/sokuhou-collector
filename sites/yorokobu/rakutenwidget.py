"""Rakuten motion widget (owner's order 2026-11-22, plan docs/office/RAKUTEN_WIDGET_PLAN_2026-11-22.md): one common block put into every page by build.page().

The widget draws its own products (names, prices, images) inside Rakuten's iframe: nothing of it is stored in this repository or in the output.
The affiliate ID is a public tag.  Each widget is a block of its own (no other mall's link inside it), headed by a visible "PR" chip.  No pop-up, no fixed bar.
At most MAX_WIDGETS per page: after the lead, in the middle of a long page, and at the end (before the related links when the page has such a section).
"""
import re

MAX_WIDGETS = 3
AFFILIATE_ID = "0fbf5187.c5400194.0fbf5188.09a2b95f"
WIDGET_JS = "https://xml.affiliate.rakuten.co.jp/widget/js/rakuten_widget.js?20230106"
# 2026-11-23 (owner): a type that shows several products at once, chosen by the screen width when the page loads (the widget writes itself with document.write, so the size has to be
# known before it is written).  PC (760px and wider): 728x200, three side by side; 520-759px: 468x160, three side by side; under 520px: 200x600, three in a column (the first one of a
# page stays 300x250 there, so the first screen of a phone is not taken by an advertisement; plan: 480px, raised to 520 because a 468px widget is wider than the text column at 480-519).
# The link type: the first and the second follow the page (ctsmatch), the last one (before the related links) is the popularity ranking.
SIZES = {"lead": ("ctsmatch", "300x250"), "mid": ("ctsmatch", "200x600"), "end": ("ranking", "200x600")}
CODE = r"""<script>(function(){var w=window.innerWidth||document.documentElement.clientWidth||375,m="__M__",s=w>=760?"728x200":(w>=520?"468x160":"__N__");var c='<scr'+'ipt type="text/javascript">rakuten_design="slide";rakuten_affiliateId="__ID__";rakuten_items="'+m+'";rakuten_genreId="0";rakuten_size="'+s+'";rakuten_target="_blank";rakuten_theme="gray";rakuten_border="off";rakuten_auto_mode="on";rakuten_genre_title="off";rakuten_recommend="on";rakuten_ts="1795398997582";</scr'+'ipt><scr'+'ipt type="text/javascript" src="__JS__"></scr'+'ipt>';document.write(c);})();</script>"""

# pages with a form or a visitor's own list, and the error page: no widget
SKIP_PATHS = frozenset({"/404.html", "/contact/", "/contact/thanks.html", "/ask/", "/dock/", "/memo/", "/history/", "/favorites/", "/list/"})
SKIP_PREFIXES = ("/ask/",)
MID_MIN_CHARS = 14000          # a page shorter than this gets no middle widget
RELATED_H2 = re.compile(r"関連|ほかの|あわせて|こちらも|次に")
SECTION = re.compile(r"<section\b")


def block(position: str) -> str:
    m, narrow = SIZES[position]
    return ('<aside class="rk-widget" data-pos="' + position + '" aria-label="広告"><p class="rk-pr"><span class="pr-chip">PR</span>'
            '<span class="rk-pr-text">楽天市場のおすすめ</span></p><div class="rk-box">' + CODE.replace("__M__", m).replace("__N__", narrow).replace("__ID__", AFFILIATE_ID).replace("__JS__", WIDGET_JS) + '</div></aside>')


def eligible(path: str) -> bool:
    return path not in SKIP_PATHS and not path.startswith(SKIP_PREFIXES)


def insert(body: str, path: str) -> str:
    """The page body with up to MAX_WIDGETS widgets in it (unchanged for the pages that take none, and when it already has one)."""
    if not eligible(path) or "rk-widget" in body:
        return body
    h1 = body.find("</h1>")
    secs = [m.start() for m in SECTION.finditer(body) if m.start() > h1] if h1 >= 0 else []
    spots: list[tuple[int, str]] = []
    if secs:
        spots.append((secs[0], "lead"))                                      # right after the lead: before the first section that follows the heading
    else:
        lead = re.search(r'<p class="lead">.*?</p>', body, re.S)
        spots.append(((lead.end() if lead else (h1 + 5 if h1 >= 0 else 0)), "lead"))
    if len(body) >= MID_MIN_CHARS and len(secs) >= 5:
        spots.append((secs[len(secs) // 2], "mid"))
    last = len(body)
    if len(secs) >= 3:
        tail = body[secs[-1]:]
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", tail, re.S)
        if h2 and RELATED_H2.search(re.sub(r"<[^>]+>", "", h2.group(1))) and secs[-1] > spots[-1][0]:
            last = secs[-1]                                                   # before the related links
    spots.append((last, "end"))
    for pos, name in sorted(spots[:MAX_WIDGETS], key=lambda s: -s[0]):
        body = body[:pos] + block(name) + body[pos:]
    return body
