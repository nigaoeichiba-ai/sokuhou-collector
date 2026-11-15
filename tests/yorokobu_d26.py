"""D26 (owner decision 2026-11-15): a source (name, note, list, link) is never shown on a page of yorokobu.

Shown: the check date, the generic sentence in the footer, advertising links (mall affiliate), share buttons, the prescribed API credits,
the privacy page's ad-settings links.  Not shown: "出典" notes, source names given as a source, links to the sources.
`problems(html)` returns what a page shows that it must not; tests call it on their built pages, and test_yorokobu_d26.py proves
that it finds the old forms (negative tests).
"""
from __future__ import annotations

import re

# hosts whose links are allowed on a screen: share buttons, the prescribed credits, the calendar add button, the privacy page's opt-out pages
ALLOWED_HOSTS = ("line.me", "twitter.com", "x.com", "developers.rakuten.com", "developer.yahoo.co.jp", "calendar.google.com",
                 "adssettings.google.com", "www.aboutads.info", "yorokobu-present.com")
AFFILIATE = ("ap.valuecommerce.com", "rakuten.co.jp", "amazon.co.jp", "amzn.to", "shopping.yahoo.co.jp", "valuecommerce.com", "a8.net", "accesstrade", "moshimo.com")
WORDS = ("出典", "情報源", "参考にした", "出どころ", "出所")
_A = re.compile(r'<a\s([^>]*?)href="((?:https?:)?//[^"]+)"([^>]*)>', re.I)


def visible_text(html: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", "", body)


def problems(html: str) -> list[str]:
    out = []
    text = visible_text(html)
    for w in WORDS:
        if w in text:
            out.append(f"word {w}")
    for m in _A.finditer(re.sub(r"<script.*?</script>", "", html, flags=re.S)):
        url = m.group(2)
        host = re.match(r"(?:https?:)?//([^/]+)", url).group(1)
        if host.endswith(ALLOWED_HOSTS):
            continue
        if any(a in host for a in AFFILIATE):
            attrs = m.group(1) + m.group(3)
            if 'target="_blank"' not in attrs or "sponsored" not in attrs:       # an advertising link carries target and rel (2026-11-15)
                out.append(f"affiliate link without target/rel {host}")
            continue
        out.append(f"link {host}")
    return out
