"""trend: the A8 advertiser 年賀状スクエア named in a category table cell (the 3-line summary of the 年賀状早割 article) carries its affiliate link
(PR, rel, target, the 1x1 pixel); the name is linked once per cell; a cell without the name, or a name that is already a link, is left alone."""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
sys.path.insert(0, str(SITE))
spec = importlib.util.spec_from_file_location("trend_hooks_nengajo", SITE / "hooks.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)


class CatNengajoLink(unittest.TestCase):
    def test_name_in_a_cell_gets_the_link_once(self):
        html = "<table><tr><td>年賀状スクエアの49％OFFと年賀状スクエアの別の話</td><td>その他の列</td></tr></table>"
        out = hooks.link_nengajo_in_cells(html)
        self.assertEqual(out.count("px.a8.net"), 1)
        for w in ('rel="nofollow sponsored noopener"', 'target="_blank"', "www11.a8.net/0.gif?a8mat=4BGH3G+CRMT6Y+33J0+15OK2A", "（PR）"):
            self.assertIn(w, out)
        self.assertEqual(out.count("年賀状スクエア"), 2)       # the text stays (the first one is the link text): only the first one gets the link

    def test_other_cells_and_linked_names_are_left_alone(self):
        self.assertEqual(hooks.link_nengajo_in_cells("<td>別の話</td>"), "<td>別の話</td>")
        linked = '<td><a href="/x/">年賀状スクエア</a>の話</td>'
        self.assertEqual(hooks.link_nengajo_in_cells(linked), linked)
        card = hooks.link_nengajo_in_cells('<p class="card-sum">年賀状スクエアの49％OFF</p>')     # the card summary is covered too
        self.assertIn("px.a8.net", card)
        self.assertNotIn("px.a8.net", hooks.link_nengajo_in_cells("<p>年賀状スクエアの本文の段落には付けない</p>"))

    def test_the_built_category_page_has_it(self):
        from sokuhou import newsite
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            newsite.main_build(SITE, ["--out", str(Path(d) / "out")])
            t = (Path(d) / "out" / "cat" / "kurashi" / "index.html").read_text(encoding="utf-8")
        cells = re.findall(r'(?:<td>|<p class="card-sum">)((?:(?!</td>|</p>).)*?)(?:</td>|</p>)', t, re.S)
        named = [c for c in cells if "年賀状スクエア" in c]
        self.assertTrue(named)
        for c in named:
            self.assertIn("px.a8.net", c)


if __name__ == "__main__":
    unittest.main()
