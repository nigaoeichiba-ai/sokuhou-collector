"""atomou: the links that point at a place inside a page ("/my/#notice") must reach a place that is there, and a button that says it finds dates must find some.
sitecheck looks at the pages the links name, not at the place inside them (a link to a missing place lands at the top of the page, or in the middle of nowhere)."""
import re
import sys
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, usecases  # noqa: E402
from tests.test_atomou_build import CFG, TODAY  # noqa: E402

PLAIN = re.compile(r"[A-Za-z][\w:.-]*")   # "#notice" is a place; "#m=…" and "#from=c:…" are read by the page's script, not places


def page_ids(html: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', html)) | set(re.findall(r'<a[^>]*\bname="([^"]+)"', html))


def broken_places(pages: dict) -> list[str]:
    """['<page> -> <link>', ...] for every link to "/path/#place" (or "#place" in the same page) whose page has no such place."""
    pages = {k: v for k, v in pages.items() if isinstance(v, str) and k.endswith(".html")}
    ids = {k: page_ids(v) for k, v in pages.items()}
    out = []
    for key, html in pages.items():
        here = "/" + key[: -len("index.html")] if key.endswith("index.html") else "/" + key
        for href in re.findall(r'<a\b[^>]*\bhref="([^"]+)"', html):
            href = href.replace("&amp;", "&")
            base, frag = urldefrag(href)
            if not frag or not PLAIN.fullmatch(frag) or re.match(r"[a-z]+:", base) or base.startswith("//"):
                continue
            path = urlparse(base).path or here
            tkey = path.lstrip("/") + ("index.html" if path.endswith("/") or not path else "")
            if tkey not in pages:
                continue   # a page that is not built here (the checker of pages names it)
            if frag not in ids[tkey]:
                out.append(f"{key} -> {href}")
    return out


class Links(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)
        cls.live = build.live_entries(catalog.build_catalog(TODAY)[0], TODAY)

    def test_every_link_to_a_place_in_a_page_reaches_it(self):
        self.assertEqual(broken_places(self.pages), [])

    def test_the_check_finds_a_link_to_a_place_that_is_not_there(self):   # the negative test: the way the owner met it ("公式の日付を見る" landing in the wrong place)
        pages = {"a/index.html": '<a href="/b/#gone">x</a><a href="#top2">y</a><a href="/b/#here">z</a><a href="/b/#m=1">k</a>',
                 "b/index.html": '<h2 id="here">h</h2>'}
        self.assertEqual(sorted(broken_places(pages)), ["a/index.html -> #top2", "a/index.html -> /b/#gone"])

    def test_the_my_page_index_and_its_places(self):
        my = self.pages["my/index.html"]
        for place in ("cards", "notice", "move", "settings", "wipe-h", "backup-h", "feat-list"):
            self.assertIn(f'id="{place}"', my, place)

    def test_a_use_case_button_that_looks_for_dates_finds_dates(self):
        n = 0
        for u in usecases.USECASES:
            html = self.pages.get(f"use/{u['slug']}/index.html", "")
            for href in re.findall(r'<a class="btn ghost" href="([^"]+)">日付をさがす</a>', html):
                n += 1
                if href.startswith("/search/"):
                    q = parse_qs(urlparse(href).query)["q"][0]
                    hay = [build._hay(e) for e in self.live]
                    words = build._norm(q).split(" ")
                    self.assertTrue(any(all(w in h for w in words) for h in hay), f"{u['slug']}: nothing found for {q!r}")
                else:
                    self.assertIn(href.lstrip("/") + "index.html", self.pages, u["slug"])
        self.assertGreater(n, 5)
        for k, v in self.pages.items():
            if isinstance(v, str):
                self.assertNotIn("公式の日付を見る", v, k)
                self.assertNotIn("公式の日付をさがす", v, k)


if __name__ == "__main__":
    unittest.main()
