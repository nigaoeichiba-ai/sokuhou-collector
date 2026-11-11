"""kurashi-calendar.com (sites/kurashi) neon-white design (2026-11-11): the rules of the design that a later change could break without anyone noticing.

* flat: no blur, glow, shadow or gradient anywhere in the stylesheet;
* the yellow is a fill only (never a text colour, border or line), and the text colours on each neon fill follow the contrast table of the spec (pink: dark or white,
  cyan / lime / yellow: dark only, violet: white only);
* the top page carries one month table and one Gantt chart built from the same seven deadlines, and every deadline's date is the catalog's;
* a month page has its month table and a panel for each deadline of the month; an article that has a deadline starts with the deadline box.
"""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sokuhou import newsite
from sites.kurashi.gen import deadlines

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kurashi"
CSS = (SITE / "assets" / "style.css").read_text(encoding="utf-8")


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def build(day: str = "2026-11-11") -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "out"
    old = os.environ.get("KURASHI_TODAY")
    os.environ["KURASHI_TODAY"] = day
    try:
        newsite.main_build(SITE, ["--out", str(out), "--release", "--strict-seo"])
    finally:
        if old is None:
            os.environ.pop("KURASHI_TODAY")
        else:
            os.environ["KURASHI_TODAY"] = old
    return tmp, out


class Rules(unittest.TestCase):
    def test_flat(self):
        body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
        for bad in ("box-shadow", "text-shadow", "filter:", "backdrop-filter", "gradient(", "drop-shadow"):
            self.assertNotIn(bad, body, f"the design is flat: {bad}")

    def test_yellow_is_a_fill_only(self):
        body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
        for decl in re.findall(r"([\w-]+)\s*:\s*[^;{}]*(?:var\(--yel\)|#FFDF00)", body, flags=re.I):
            self.assertIn(decl, ("--yel", "background", "background-color"), f"yellow is only a fill, not {decl}")
        self.assertFalse(re.search(r"(?<![-\w])color\s*:\s*(?:var\(--yel\)|#FFDF00)", body, flags=re.I))

    def test_text_on_fill_contrast(self):
        ink, white = "#1F2430", "#FFFFFF"
        self.assertGreaterEqual(contrast(ink, white), 15)
        for fill in ("#00CFFF", "#64D900", "#FFDF00", "#FF2E9E"):
            self.assertGreaterEqual(contrast(ink, fill), 4.5, fill)
        self.assertGreaterEqual(contrast(white, "#7B2FFF"), 4.5)
        for fill in ("#00CFFF", "#64D900", "#FFDF00"):
            self.assertLess(contrast(white, fill), 3, f"white text on {fill} is not allowed")
        self.assertLess(contrast(ink, "#7B2FFF"), 4.5)
        # the stylesheet pairs: lime / cyan / yellow rows carry dark text, the violet one carries white
        self.assertRegex(CSS, r'body\[data-cat="violet"\]\s*\{\s*--cat:var\(--vio\);\s*--on-cat:#fff;')
        self.assertRegex(CSS, r"\.dc\.dr \{[^}]*background:var\(--lime\)[^}]*color:var\(--ink\)")
        self.assertRegex(CSS, r"\.dc\.dh \{[^}]*background:var\(--vio\)[^}]*color:#fff")
        self.assertRegex(CSS, r"\.btn \{[^}]*background:var\(--cyan\)[^}]*color:var\(--ink\)")


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, rel: str) -> str:
        return (self.out / rel).read_text(encoding="utf-8")

    def test_home_has_both_views_from_the_same_deadlines(self):
        h = self.page("index.html")
        ids = deadlines.BY_PAGE["/"]
        cat = {c["id"]: c for c in deadlines.catalog_json()}
        self.assertEqual(h.count('class="sw-b"'), 2)
        self.assertIn('class="mt-g"', h)
        self.assertIn('class="gantt"', h)
        gantt = h[h.index('class="gantt"'):]
        for i in ids:
            if date.fromisoformat(cat[i]["date"]) >= date(2026, 11, 11):
                self.assertIn(cat[i]["name"], gantt, i)
        for iso in re.findall(r'data-day="(\d{4}-\d\d-\d\d)"', h):
            self.assertIn(iso, [c["date"] for c in cat.values()])

    def test_month_page_has_table_and_panels(self):
        h = self.page("month/12/index.html")
        self.assertIn("2026年12月", h)
        self.assertEqual(h.count('class="dpanel"') + h.count('class="dpanel" data-on'), len(re.findall(r'<div class="dpanel"', h)))
        self.assertGreaterEqual(len(re.findall(r'<div class="dpanel"', h)), 4)
        self.assertIn("month-12.ics", h)

    def test_article_starts_with_the_deadline_box(self):
        h = self.page("nengajo/index.html")
        self.assertIn('class="dbox', h)
        self.assertLess(h.index('class="dbox'), h.index("<h2>"))
        self.assertIn("nengajo-hikiuke.ics", h[h.index('class="dbox'):h.index("<h2>")])

    def test_body_category_and_icons(self):
        self.assertIn('<body data-cat="violet">', self.page("life/birth/index.html"))
        self.assertIn('<body data-cat="pink">', self.page("index.html"))
        for rel in ("index.html", "about/index.html"):
            h = self.page(rel)
            for f in ("favicon-16.png", "favicon-32.png", "favicon-48.png"):
                self.assertIn(f"/assets/{f}", h)

    def test_the_favicon_is_the_chosen_one(self):
        from PIL import Image
        self.assertEqual(Image.open(self.out / "assets" / "favicon-16.png").size, (16, 16))
        self.assertEqual(Image.open(self.out / "apple-touch-icon.png").size, (180, 180))
        self.assertEqual((self.out / "favicon.ico").read_bytes(), (SITE / "assets" / "favicon.ico").read_bytes())

    def test_print_drops_the_decoration(self):
        printed = CSS[CSS.index("@media print"):]
        self.assertRegex(printed, r"\.kv,[^{]*\.dbox \{ display:none")


if __name__ == "__main__":
    unittest.main()
