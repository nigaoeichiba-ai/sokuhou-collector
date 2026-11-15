"""trend's own rules of the linkage gate (sokuhou/linkage.py calls check()).  What only this site knows: the top page agrees with the articles.
  home-date    the top page's 最終更新 is the newest day any article was published or changed (it was a hand-written date and stayed at 11/11 while articles went up until 11/15)
  home-cards   the article cards on the top page are the newest articles: no article that is left out is newer than one that is shown"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _days(info) -> list[str]:
    out = []
    for b in info.pg.ld:
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Article":
            out.append((d.get("datePublished") or "", d.get("dateModified") or d.get("datePublished") or ""))
    return out


def check(root: Path, base: str, pages: dict) -> list[str]:
    out = []
    home = pages.get("/")
    if home is None:
        return ["home-date|/|no home page"]
    arts = {p: _days(i)[0] for p, i in pages.items() if _days(i) and not i.pg.noindex}
    newest = max((m for _, m in arts.values()), default="")
    m = re.search(r"最終更新：(\d+)年(\d+)月(\d+)日", home.html)
    if not m:
        out.append("home-date|/|the top page shows no 最終更新 date")
    else:
        shown = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        if newest and shown < newest:
            out.append(f"home-date|/|最終更新 is {shown} but the newest article change is {newest}")
    cards = set(re.findall(r'class="article-card" href="([^"]+)"', home.html))     # the 解説記事 cards, not every link of the top page
    shown_arts = [p for p in arts if p in cards]
    left = [p for p in arts if p not in cards]
    if not cards:
        out.append("home-cards|/|the top page has no article cards")
    if shown_arts and left:
        oldest_shown = min(arts[p][0] for p in shown_arts)
        for p in left:
            if arts[p][0] > oldest_shown:
                out.append(f"home-cards|{p}|published {arts[p][0]} is newer than a card on the top page ({oldest_shown}) but has no card")
    return out
