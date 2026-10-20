"""How much of a site is the same page with other names in it (shadow warning of sitecheck; the AdSense answer "有用性の低いコンテンツ" on saichin, 2026-10-19).

    python -m sokuhou.sametype <built folder>

Method (docs/growth/ADSENSE_PATH_2026-10-20.md, appendix; the numbers are those of the live saichin in the research):
  - only indexable pages (no noindex), the prose of <main>: p, li, h2, h3 - tables, navigation, scripts and pictures left out;
  - digits and the 47 prefecture names are masked ("愛知県の最低賃金は1,195円" and "兵庫県の最低賃金は1,172円" become the same text);
  - the text is cut into 8-character pieces; the overlap of two pages is the shared pieces / the smaller page's pieces;
  - pages are grouped by their folder (/live/miyagi/<市>/ pages are one group, /live/<県>/ pages another) and, for pages one level below the root,
    by the pattern of the title (@の最低賃金の推移...);
  - a page is "same-type" when its median overlap with up to 8 other pages of its group is 0.8 or more.
A site is warned about when more than 60 % of its indexable pages are same-type.  The warning never stops a deploy (shadow, decided with the report desk).
"""
from __future__ import annotations

import re
import statistics
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

from sokuhou.prefectures import SHORT

OVERLAP = 0.8          # a page whose median overlap with its group is at least this is "same-type"
SHARE = 0.6            # warn above this share of the indexable pages
PIECE = 8              # characters
REFS = 8               # other pages of the group a page is compared with
MIN_PIECES = 20        # a page with less prose than this is not compared (nothing to be the same)
_SKIP = {"table", "script", "style", "nav", "footer", "header", "svg", "figure"}
_PROSE = {"p", "li", "h2", "h3"}


class _Prose(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.noindex = False
        self.title = ""
        self.out: list[str] = []
        self._main = 0
        self._skip = 0
        self._cur: list[str] | None = None
        self._title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title" and not self.title:
            self._title = True
        if tag == "meta" and (a.get("name") or "").lower() == "robots" and "noindex" in (a.get("content") or "").lower():
            self.noindex = True
        if tag == "main":
            self._main += 1
        if self._main and tag in _SKIP:
            self._skip += 1
        if self._main and not self._skip and tag in _PROSE:
            self._cur = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        if tag == "main":
            self._main = max(0, self._main - 1)
        if self._main and tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        if tag in _PROSE and self._cur is not None:
            self.out.append("".join(self._cur))
            self._cur = None

    def handle_data(self, data):
        if self._title:
            self.title += data
        if self._cur is not None and not self._skip:
            self._cur.append(data)


def mask(text: str) -> str:
    text = re.sub(r"[0-9,.+\-−％%]+", "#", text)
    for name in sorted(SHORT, key=len, reverse=True):
        text = text.replace(name, "@")
    return re.sub(r"\s+", "", text)


def pieces(text: str) -> set[str]:
    return {text[i:i + PIECE] for i in range(len(text) - PIECE + 1)}


def group_key(rel: str, title: str) -> str:
    parts = rel.split("/")[:-1]
    if len(parts) > 1:
        return "/".join(parts[:-1]) + "/*"       # the pages of one folder (/live/miyagi/*): across folders the pages differ by the folder's own facts, within one they are one text
    return "title:" + re.sub(r"[県都府]", "", mask(title))[:8]


def measure(root: Path) -> dict:
    """{'indexable': n, 'same': n, 'share': 0..1, 'groups': [(key, pages, same pages)]} for a built folder."""
    root = Path(root)
    pages: dict[str, set[str]] = {}
    keys: dict[str, str] = {}
    for f in sorted(root.rglob("index.html")):
        p = _Prose()
        p.feed(f.read_text(encoding="utf-8", errors="replace"))
        if p.noindex:
            continue
        rel = f.relative_to(root).as_posix()
        pages[rel] = pieces(mask("".join(p.out)))
        keys[rel] = group_key(rel, p.title)
    groups: dict[str, list[str]] = defaultdict(list)
    for rel in pages:
        groups[keys[rel]].append(rel)
    detail = []
    same_total = 0
    for key, rels in groups.items():
        n_same = 0
        if len(rels) > 1:
            step = max(1, len(rels) // REFS)
            refs = rels[::step][:REFS]
            for rel in rels:
                a = pages[rel]
                if len(a) < MIN_PIECES:
                    continue
                vals = [len(a & pages[q]) / min(len(a), len(pages[q])) for q in refs if q != rel and len(pages[q]) >= MIN_PIECES]
                if vals and statistics.median(vals) >= OVERLAP:
                    n_same += 1
        same_total += n_same
        detail.append((key, len(rels), n_same))
    total = len(pages)
    return {"indexable": total, "same": same_total, "share": same_total / total if total else 0.0,
            "groups": sorted(detail, key=lambda g: -g[2])}


def warning(result: dict) -> str:
    """One line when the share is over the limit, otherwise ''."""
    if result["share"] <= SHARE:
        return ""
    top = ", ".join(f"{k} {s}/{n}" for k, n, s in result["groups"][:3] if s)
    return (f"WARNING [same-type]: {result['same']} of {result['indexable']} indexable pages ({result['share']:.0%}) are the same text with other names in it "
            f"(limit {SHARE:.0%}; largest groups: {top}). Not a failure; see sokuhou/sametype.py")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m sokuhou.sametype <built folder>")
        return 2
    r = measure(Path(args[0]))
    print(f"same-type pages: {r['same']} of {r['indexable']} indexable ({r['share']:.0%})")
    for key, n, s in r["groups"][:8]:
        if s:
            print(f"  {key}: {s} of {n}")
    w = warning(r)
    if w:
        print(w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
