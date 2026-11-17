"""sale-calendar.com: what the SEO audit of 2026-11-17 found stays fixed (the ledger rows: 21 pages with one inbound link; two product pages that shared h1 and the title's head with their genre page).

Pinned here: every indexable page has at least 3 inbound links from other pages of the site; no two indexable pages share an h1, a title or the first 12 characters of a title
(a product page and its genre page are different searches); every product page carries Article data of its own; each has a '関連するページ' block that lists its neighbours and is listed by them.
"""
from __future__ import annotations

import collections
import os
import re
import unittest

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-17")

from tests.test_kaidoki_redesign import build  # noqa: E402

HEAD = 12
MIN_INBOUND = 3


def site_pages(pages: dict) -> dict[str, str]:
    out = {}
    for rel, html in pages.items():
        if isinstance(html, str) and rel.endswith(".html"):
            path = "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)
            out[path] = html
    return out


def indexable(pages: dict[str, str]) -> list[str]:
    return [p for p, h in pages.items() if not re.search(r'<meta[^>]+name="robots"[^>]+noindex', h) and not p.startswith("/google") and p != "/404.html"]


def inbound(pages: dict[str, str]) -> dict[str, set[str]]:
    inb: dict[str, set[str]] = collections.defaultdict(set)
    for p, h in pages.items():
        for m in re.finditer(r'<a [^>]*href="([^"#?]+)', h):
            u = m.group(1)
            if u.startswith("/") and u != p and u in pages:
                inb[u].add(p)
    return inb


def problems(pages: dict[str, str]) -> list[str]:
    bad = []
    idx = indexable(pages)
    inb = inbound(pages)
    for p in idx:
        if len(inb[p]) < MIN_INBOUND:
            bad.append(f"{p}: {len(inb[p])} inbound links (needs {MIN_INBOUND})")
    titles, h1s, heads = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for p in idx:
        h = pages[p]
        t = (re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1].strip()
        m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
        h1 = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        titles[t].append(p)
        h1s[h1].append(p)
        heads[t[:HEAD]].append(p)
    for what, d in (("title", titles), ("h1", h1s)):
        for k, v in d.items():
            if len(v) > 1:
                bad.append(f"same {what} {k[:30]!r}: {v}")
    for k, v in heads.items():
        if len(v) > 1 and not all(x.startswith(("/calendar/", "/yahoo/", "/rakuten/", "/amazon/")) for x in v):
            bad.append(f"same title head {k!r}: {v}")
    return bad


class SeoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = site_pages(build({"KAIDOKI_REDESIGN": "1"}))

    def test_the_audit_findings_stay_fixed(self):
        self.assertEqual(problems(self.pages), [])

    def test_every_product_page_has_its_own_article_data_and_a_symmetric_related_block(self):
        block = re.compile(r'<h2>関連するページ</h2>\s*<ul class="links">(.*?)</ul>', re.S)
        prod = {p: h for p, h in self.pages.items() if '"@type": "Article"' in h and p.count("/") == 3 and p.split("/")[1] in ("kaden", "food", "daily", "fashion", "beauty", "home", "hobby", "service") and h.count("class=\"store-row\"")}
        self.assertGreaterEqual(len(prod), 20)
        links = {p: set(re.findall(r'href="([^"]+)"', (block.search(h) or [None, ""])[1])) for p, h in prod.items()}
        for p, ls in links.items():
            self.assertTrue(ls, p)
            for q in ls:
                if q in prod:
                    self.assertIn(p, links[q], f"{q} does not list {p} back")

    def test_the_related_block_names_no_affiliated_advertiser(self):
        """The 2026-11-17 deploy was stopped by the linkage gate: the related links named other advertisers (お名前.com ...) on pages that carry no link for them."""
        import json
        from pathlib import Path
        ads = json.loads((Path(__file__).resolve().parents[1] / "data" / "linkage" / "advertisers.json").read_text(encoding="utf-8"))["advertisers"]
        names = [n for a in ads if "kaidoki" in a["sites"] for n in a["names"]]
        block = re.compile(r'<h2>関連するページ</h2>\s*<ul class="links">(.*?)</ul>', re.S)
        seen = 0
        for p, h in self.pages.items():
            m = block.search(h)
            if m and p.count("/") == 3 and "store-row" in h:
                texts = " ".join(re.findall(r">([^<]+)</a>", m.group(1)))
                seen += 1
                for n in names:
                    self.assertNotIn(n, texts, f"{p} names {n} in its related links")
        self.assertGreaterEqual(seen, 20)
        # negative: the titles as they were (the pages' own h1) do name advertisers, so the check above has something to catch
        self.assertTrue(any(n in "お名前.comのドメイン移管キャッシュバック" for n in names))

    def test_negative_each_finding_is_caught(self):
        dup = dict(self.pages)
        a, b = "/food/lohaco-food/", "/food/"
        dup[a] = re.sub(r"<h1[^>]*>.*?</h1>", re.search(r"<h1[^>]*>.*?</h1>", dup[b], re.S).group(0), dup[a], count=1, flags=re.S)
        self.assertTrue(any("same h1" in x for x in problems(dup)))
        one = dict(self.pages)
        for p in list(one):
            if p != "/kaden/iphone-18-pro/" and "/kaden/iphone-18-pro/" in one[p] and p != "/kaden/":
                one[p] = one[p].replace('href="/kaden/iphone-18-pro/"', 'href="/x/"')
        self.assertTrue(any("/kaden/iphone-18-pro/" in x and "inbound" in x for x in problems(one)))


if __name__ == "__main__":
    unittest.main()
