"""みんなのイラスト: the partner (A8.net) box of a guide, content/partner_links.json.

A partner link is put on a page exactly as the programme generated it (owner decision 2026-10-17, AFFILIATE_RULES.md 3b: nothing added, nothing taken away, nothing rewritten); our own
words are only the box heading, the PR mark and the notice around it.  An entry is {"<guide slug>": {"heading": "...", "html": "<the code the programme gave, pasted as it is>"}}.
A page with no entry, or an entry whose html is empty, shows nothing at all: no empty frame, no PR mark, no notice at the top of the page.
Rules of the programme in use (年賀状スクエア, 2026-11-09): no coupons in our text, the page says it holds an advertisement (also at the top of the page), the URL of the page is given
to A8.net after publishing, and the programme's name words are not used in search advertising.
"""
from __future__ import annotations

import json
from pathlib import Path

from sokuhou.sitekit import esc

HERE = Path(__file__).resolve().parent


def load() -> dict[str, dict]:
    return json.loads((HERE / "content" / "partner_links.json").read_text(encoding="utf-8"))


LINKS: dict[str, dict] = load()


def entry(slug: str) -> dict | None:
    e = LINKS.get(slug)
    return e if e and e.get("html", "").strip() else None


def top_notice(slug: str) -> str:
    """A line near the top of the page (first view) saying the page holds an advertisement; empty when the page has no partner link."""
    if not entry(slug):
        return ""
    return '<p class="pr-top"><span class="pr-note">PR</span>このページには広告(A8.netの提携先へのリンク)が含まれます。</p>'


def box(slug: str) -> str:
    """The partner box: our heading, the programme's code exactly as given, our notice.  Empty when the page has no partner link."""
    e = entry(slug)
    if not e:
        return ""
    return (f'<aside class="pr-box pr-partner"><h2><span class="pr-note">PR</span>{esc(e["heading"])}</h2><div class="pr-partner-body">{e["html"]}</div>'
            '<p class="pr-small">このボックスには、広告(A8.net)のリンクが含まれます。リンク先で購入されると、運営者に報酬が支払われることがあります。</p></aside>')
