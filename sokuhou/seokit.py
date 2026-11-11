"""The common SEO checks of the new sites (docs/new_sites/BATCH1_PROPOSAL.md 5-0, owner instruction 2026-10-20): thin and duplicate pages, one search term per page,
orphan pages, picture alt text.  Pure functions on a built site ({"path/index.html": html}); sokuhou/newsite.py calls them in every build.

    thin_reasons(pages, kinds)      why a page is too thin to be indexed (the bars of 5-0 (8); a page below them becomes noindex,follow and leaves the sitemap)
    similar_pairs(pages, kinds)     two pages of one type whose text overlaps by more than 0.6 (a build failure: a person decides which to merge or noindex)
    keyword_problems(metas)         the same main search term on two pages, no term, the term missing from title / h1 (a build failure)
    link_problems(pages, ...)       orphan pages and pages more than 3 clicks from the home page (a build failure)
    alt_problems(pages)             <img> without alt, or a linked picture with an empty alt

The bars are the first ones of the proposal; they are changed after the first real measurements, never lowered to let a page through.
"""
from __future__ import annotations

import random
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from urllib.parse import urlparse

# ---- the bars (5-0 (8)) ----------------------------------------------------------------------------------------------------------------------------------
HUB_TYPES = ("hub", "list", "analysis", "article")      # analysis pages and hubs
ITEM_TYPES = ("item",)                                  # one prefecture / disease / item / qualification
ALWAYS_NOINDEX = ("archive", "paged")                   # weekly / monthly archives and page 2 onwards of a list
HUB_MIN_CHARS, HUB_MIN_OWN_SENTENCES = 1200, 3
ITEM_MIN_CHARS, ITEM_MIN_OWN_SHARE, ITEM_MIN_NUMBERS = 700, 0.40, 10
SIMILAR_LIMIT = 0.6
SHINGLE = 5                                             # characters
MAX_DEPTH = 3                                           # clicks from the home page
TITLE_FULLWIDTH, DESC_RANGE, ANSWER_RANGE = 40, (80, 120), (40, 80)
INTENTS = (1, 2, 3, 4, 5)       # 1 latest number, 2 ranking, 3 trend / comparison with the past, 4 meaning / definition / cause, 5 calculation / check


# ---- reading a built page --------------------------------------------------------------------------------------------------------------------------------
class _Main(HTMLParser):
    """The readable parts of <main>: text, table cells, numbers in tables, charts, links, images.  Breadcrumbs are navigation, not content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth_main = 0
        self.skip = 0
        self.text: list[str] = []
        self.cells: list[str] = []
        self._cell = False
        self.charts = 0
        self.sentences: list[str] = []
        self._para: list[str] = []
        self._in_para = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.depth_main += 1
        if not self.depth_main:
            return
        if tag in ("script", "style") or (tag == "nav" and "crumbs" in (a.get("class") or "")):
            self.skip += 1
        if tag == "svg" and "chart" in (a.get("class") or ""):
            self.charts += 1
        if tag in ("td", "th"):
            self._cell = True
            self.cells.append("")
        if tag in ("p", "li", "dd"):
            self._in_para += 1

    def handle_endtag(self, tag):
        if tag == "main":
            self.depth_main = max(0, self.depth_main - 1)
        if not self.depth_main:
            return
        if tag in ("script", "style") or (tag == "nav" and self.skip):
            self.skip = max(0, self.skip - 1)
        if tag in ("td", "th"):
            self._cell = False
        if tag in ("p", "li", "dd") and self._in_para:
            self._in_para -= 1
            if not self._in_para:
                para = "".join(self._para)
                self._para = []
                self.sentences.extend(s.strip() + "。" for s in para.split("。") if len(s.strip()) >= 15)

    def handle_data(self, data):
        if not self.depth_main or self.skip:
            return
        self.text.append(data)
        if self._cell and self.cells:
            self.cells[-1] += data
        if self._in_para:
            self._para.append(data)


_NUMBER = re.compile(r"\d")


def read_main(html: str) -> dict:
    p = _Main()
    p.feed(html)
    text = re.sub(r"\s+", "", "".join(p.text))
    numeric = [c for c in p.cells if _NUMBER.search(c)]
    return {"text": text, "chars": len(text), "cells": len(p.cells), "numbers": len(numeric), "charts": p.charts, "sentences": p.sentences,
            "tables": html.count("<table")}


def visible_chars(html: str) -> int:
    """How many characters of a page's main content a visitor can read (the breadcrumb, tags, scripts and spaces left out)."""
    return read_main(html)["chars"]


def shingles(text: str, n: int = SHINGLE) -> set[str]:
    return {text[i:i + n] for i in range(max(0, len(text) - n + 1))}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---- thin pages ------------------------------------------------------------------------------------------------------------------------------------------
def _groups(kinds: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for rel, kind in kinds.items():
        out[kind].append(rel)
    return out


def thin_reasons(pages: dict, kinds: dict[str, str], min_chars: dict[str, int] | None = None) -> dict[str, list[str]]:
    """{page: [why it is thin]} for the pages that miss the bars of their type.  `kinds` maps a page to its type (hub / list / analysis / article / item / archive / paged);
    a page of any other type (about, privacy ...) is not judged.  The 'own share' of an item page is the part of its text that no other page of the same type has."""
    info = {rel: read_main(pages[rel]) for rel in kinds if isinstance(pages.get(rel), str)}
    shared: dict[str, Counter] = {}
    sh: dict[str, set] = {rel: shingles(i["text"]) for rel, i in info.items()}
    for kind, rels in _groups({r: kinds[r] for r in info}).items():
        c: Counter = Counter()
        for r in rels:
            c.update(sh[r])
        shared[kind] = c
    out: dict[str, list[str]] = {}
    for rel, i in info.items():
        kind, why = kinds[rel], []
        if kind in ALWAYS_NOINDEX:
            why.append(f"a {kind} page is always noindex,follow")
        elif kind in HUB_TYPES:
            need = (min_chars or {}).get(rel, HUB_MIN_CHARS)      # a site may lower the bar for named pages (config "thin_min_chars"); none by default
            if i["chars"] < need:
                why.append(f"{i['chars']} readable characters (a {kind} page needs {need})")
            if not (i["tables"] or i["charts"]):
                why.append("no table and no chart")
            own = sum(1 for s in i["sentences"] if _own_share(shingles(s), shared[kind]) >= 0.5)
            if own < HUB_MIN_OWN_SENTENCES:
                why.append(f"{own} sentences of its own (needs {HUB_MIN_OWN_SENTENCES})")
        elif kind in ITEM_TYPES:
            if i["chars"] < ITEM_MIN_CHARS:
                why.append(f"{i['chars']} readable characters (an item page needs {ITEM_MIN_CHARS})")
            share = _own_share(sh[rel], shared[kind])
            if share < ITEM_MIN_OWN_SHARE:
                why.append(f"only {share:.0%} of the text is its own (needs {ITEM_MIN_OWN_SHARE:.0%})")
            if i["numbers"] < ITEM_MIN_NUMBERS:
                why.append(f"{i['numbers']} numbers in tables (needs {ITEM_MIN_NUMBERS})")
        if why:
            out[rel] = why
    return out


def _own_share(mine: set, count: Counter) -> float:
    """The part of `mine` that no other page of the group has (count[x] == 1 means only this page)."""
    if not mine:
        return 0.0
    return sum(1 for s in mine if count.get(s, 0) <= 1) / len(mine)


def similar_pairs(pages: dict, kinds: dict[str, str], limit: float = SIMILAR_LIMIT, seed: int = 7) -> list[tuple[str, str, float]]:
    """Pairs of pages of one type whose text overlaps by more than `limit` (5-character pieces, Jaccard).  Large groups are compared with the neighbours in the
    file order and a fixed random sample, so a thousand-page type stays fast."""
    info = {rel: shingles(read_main(pages[rel])["text"]) for rel in kinds if isinstance(pages.get(rel), str) and kinds[rel] not in ALWAYS_NOINDEX}
    rng = random.Random(seed)
    out = []
    for rels in _groups({r: kinds[r] for r in info}).values():
        rels = sorted(rels)
        if len(rels) <= 300:
            pairs = [(a, b) for i, a in enumerate(rels) for b in rels[i + 1:]]
        else:
            pairs = set()
            for i, a in enumerate(rels):
                for j in [i + 1, i + 2, i + 3] + rng.sample(range(len(rels)), 12):
                    if j != i and j < len(rels):
                        pairs.add((min(a, rels[j]), max(a, rels[j])))
            pairs = sorted(pairs)
        for a, b in pairs:
            j = jaccard(info[a], info[b])
            if j > limit:
                out.append((a, b, round(j, 3)))
    return out


# ---- one search term per page ---------------------------------------------------------------------------------------------------------------------------
def keyword_problems(metas: list[dict]) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the pages that should rank: `metas` rows are {path, kind, primary_kw, secondary_kw, intent, title, h1, description, answer}.
    Errors: no main term, the same main term on two pages, a wrong intent, the term missing from title or h1.  Warnings: lengths of title, description and the lead sentence."""
    errors, warnings = [], []
    seen: dict[str, str] = {}
    for m in metas:
        p, kw = m["path"], (m.get("primary_kw") or "").strip()
        if not kw:
            errors.append(f"{p}: no primary_kw (one main search term per page, from a measured suggestion or Search Console)")
            continue
        key = re.sub(r"\s+", "", kw).lower()
        if key in seen:
            errors.append(f"{p}: the main search term {kw!r} is already the main term of {seen[key]} (two pages for one term compete)")
        seen[key] = p
        if m.get("intent") not in INTENTS:
            errors.append(f"{p}: intent must be one of {INTENTS} (1 latest number, 2 ranking, 3 trend, 4 meaning/cause, 5 calculation)")
        if len(m.get("secondary_kw") or []) > 3:
            errors.append(f"{p}: at most 3 secondary terms")
        squeezed = key
        if squeezed not in re.sub(r"\s+", "", m["title"]).lower():
            errors.append(f"{p}: the title does not contain the main term {kw!r}")
        if squeezed not in re.sub(r"\s+", "", m["h1"]).lower():
            errors.append(f"{p}: the h1 does not contain the main term {kw!r}")
        if _width(m["title"]) > TITLE_FULLWIDTH:
            warnings.append(f"{p}: title is {_width(m['title'])} full-width characters (about {TITLE_FULLWIDTH} at most)")
        d = len(m["description"])
        if not DESC_RANGE[0] <= d <= DESC_RANGE[1]:
            warnings.append(f"{p}: description is {d} characters (aim for {DESC_RANGE[0]}-{DESC_RANGE[1]})")
        a = len(m.get("answer") or "")
        if m.get("kind") != "archive" and not ANSWER_RANGE[0] <= a <= ANSWER_RANGE[1]:
            warnings.append(f"{p}: the lead answer is {a} characters (aim for {ANSWER_RANGE[0]}-{ANSWER_RANGE[1]})")
    return errors, warnings


def _width(s: str) -> float:
    return sum(1 if ord(c) > 0x2000 else 0.5 for c in s)


# ---- links -----------------------------------------------------------------------------------------------------------------------------------------------
_HREF = re.compile(r'<a\s[^>]*?href="([^"#]+)(?:#[^"]*)?"', re.S)


def _own_path(base_host: str, ref: str) -> str | None:
    u = urlparse(ref)
    if u.scheme in ("mailto", "tel", "javascript"):
        return None
    if u.netloc and u.netloc.lower() != base_host.lower():
        return None
    if not u.path.startswith("/"):
        return None
    return u.path


def _rel_of(path: str) -> str:
    return path.lstrip("/") + "index.html" if path.endswith("/") else path.lstrip("/")


def link_problems(pages: dict, indexable: set[str], base_host: str = "") -> list[str]:
    """Orphans (an indexable page no other page links to) and pages deeper than MAX_DEPTH clicks from the home page.  Links in the header navigation count
    (they are links on every page); the sitemap does not."""
    graph: dict[str, set[str]] = {}
    for rel, html in pages.items():
        if not (isinstance(html, str) and rel.endswith("index.html")):
            continue
        out = set()
        for ref in _HREF.findall(html):
            p = _own_path(base_host, ref)
            if p is not None:
                out.add(_rel_of(p))
        graph[rel] = out - {rel}
    inbound: Counter = Counter()
    for rel, outs in graph.items():
        for o in outs:
            inbound[o] += 1
    problems = []
    for rel in sorted(indexable):
        if rel == "index.html":
            continue
        if not inbound[rel]:
            problems.append(f"{rel}: orphan page (no page links to it)")
    depth = {"index.html": 0}
    queue = ["index.html"]
    while queue:
        cur = queue.pop(0)
        for o in graph.get(cur, ()):
            if o not in depth:
                depth[o] = depth[cur] + 1
                queue.append(o)
    for rel in sorted(indexable):
        if rel == "index.html" or not inbound[rel]:
            continue
        if rel not in depth:
            problems.append(f"{rel}: cannot be reached by clicking from the home page")
        elif depth[rel] > MAX_DEPTH:
            problems.append(f"{rel}: {depth[rel]} clicks from the home page (at most {MAX_DEPTH})")
    return problems


# ---- pictures --------------------------------------------------------------------------------------------------------------------------------------------
_IMG = re.compile(r"<img\b[^>]*>", re.S)
_ALT = re.compile(r'\balt="([^"]*)"')
_LINKED_IMG = re.compile(r"<a\b[^>]*>\s*(<img\b[^>]*>)\s*</a>", re.S)


def alt_problems(pages: dict) -> list[str]:
    """Every <img> has an alt attribute; a picture that is the only content of a link has words in it (a decorative picture has an empty alt, a linked one cannot)."""
    out = []
    for rel, html in sorted(pages.items()):
        if not (isinstance(html, str) and rel.endswith(".html")):
            continue
        for tag in _IMG.findall(html):
            if not _ALT.search(tag):
                out.append(f"{rel}: <img> without alt: {tag[:60]}")
        for tag in _LINKED_IMG.findall(html):
            m = _ALT.search(tag)
            if m is not None and not m.group(1).strip():
                out.append(f"{rel}: a linked picture with an empty alt (say what the link is): {tag[:60]}")
    return out
