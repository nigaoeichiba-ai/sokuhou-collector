"""Read-only watch of the depth bar on the REAL pages of trend-sokuho.com (desk's rule 2026-11-09).

Once a day it reads every page of the live sitemap and, for each article (og:type "article"), measures the readable characters and whether there is a table or
a chart.  It changes nothing.  Red (exit 1) when
  - an article that is indexed has fewer than 1,200 readable characters (thin: it must be thickened or made noindex),
  - an article published after the depth bar (not in hooks.DEEP_GRANDFATHERED) has fewer than 2,000 characters or no table / chart,
  - a page could not be read (never reported as fine).
Articles on DEEP_GRANDFATHERED below 2,000 characters are listed as "to review" (own view, own text, own content, research), never padded for a number.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from sokuhou import newsite, seokit                      # noqa: E402

SITE = ROOT / "sites" / "trend"
BASE = "https://trend-sokuho.com"
THIN_MIN, DEEP_MIN = 1200, 2000


def judge(path: str, html: str, grandfathered: set[str]) -> tuple[str, int, bool]:
    """(state, readable characters, has table or chart).  state: not-article / deep / review / THIN / NOT-DEEP."""
    if 'property="og:type" content="article"' not in html:
        return "not-article", 0, False
    info = seokit.read_main(html)
    own = bool(info["tables"] or info["charts"])
    indexed = not re.search(r'<meta name="robots" content="[^"]*noindex', html)
    if indexed and info["chars"] < THIN_MIN:
        return "THIN", info["chars"], own
    if path in grandfathered:
        return ("deep" if info["chars"] >= DEEP_MIN and own else "review"), info["chars"], own
    if indexed and (info["chars"] < DEEP_MIN or not own):
        return "NOT-DEEP", info["chars"], own
    return "deep", info["chars"], own


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "sokuhou-depth-watch"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main(out_path: str) -> int:
    grandfathered = set(newsite.site_hooks(SITE).DEEP_GRANDFATHERED)
    rows, unread = [], []
    try:
        urls = re.findall(r"<loc>([^<]+)</loc>", fetch(BASE + "/sitemap.xml"))
    except Exception as e:          # the sitemap itself could not be read
        Path(out_path).write_text(f"# trend depth watch\n\nthe sitemap could not be read: {e}\n", encoding="utf-8")
        return 1
    for u in urls:
        path = u.replace(BASE, "") or "/"
        try:
            rows.append((path, *judge(path, fetch(u), grandfathered)))
        except Exception as e:
            unread.append((path, str(e)))
    lines = ["# trend depth watch (read only)", "", f"{len(urls)} pages in the sitemap; articles: {sum(1 for r in rows if r[1] != 'not-article')}", "",
             "| page | state | readable characters | own table/chart |", "|---|---|---|---|"]
    bad = [r for r in rows if r[1] in ("THIN", "NOT-DEEP")]
    for p, st, ch, own in sorted(rows, key=lambda r: (r[1] == "not-article", r[2])):
        if st != "not-article":
            lines.append(f"| {p} | {st} | {ch} | {'yes' if own else 'NO'} |")
    if unread:
        lines += ["", "not read (never counted as fine):"] + [f"- {p}: {e}" for p, e in unread]
    if bad:
        lines += ["", f"RED: {len(bad)} article(s) below the bar: thicken with content of its own, or make noindex."]
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if (bad or unread) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "trend-depth-live-report.md"))
