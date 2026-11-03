"""The heading of the first four products (「種類の違う人気の4点」) was the same on every gift page, and the style dictionary once rewrote it with the words of one page for all of them.
Now the gift pages name their own occasion and person in it (build side, 2026-11-03); the theme pages, which have no occasion, keep the common heading."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from tests.test_yorokobu_card_kinds import DATA, FRIDGE, item
from tests.test_yorokobu_read_picks import CFG as C2, world
from tests.yorokobu_data import rich_boyfriend

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None, "adsense_pub_id": None}


def heading(html: str) -> str | None:
    m = re.search(r'<section class="top-picks">.*?<h2>(.*?)</h2>', html, re.S)
    return m.group(1) if m else None


class HeadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.c = content.load(FIX)
        items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        build.render_site(cls.c, items, CFG, cls.out, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_gift_page_with_the_block_names_its_own_page_in_the_heading(self):
        seen = 0
        for p in self.c["pairs"]:
            f = self.out / "gift" / build.ct.pair_key(p) / "index.html"
            if not f.exists():
                continue
            h = heading(f.read_text(encoding="utf-8"))
            if h is None:
                continue
            seen += 1
            label = p["title"].split(" ")[0]
            self.assertTrue(h.startswith(label + "、種類の違う人気の"), (build.ct.pair_key(p), h))
            others = [q["title"].split(" ")[0] for q in self.c["pairs"] if q["title"].split(" ")[0] != label]
            self.assertFalse(any(h.startswith(o) for o in others), (build.ct.pair_key(p), h))          # not the words of another page
        self.assertGreater(seen, 0, "the fixture built no gift page with the block")

    def test_a_theme_page_keeps_the_common_heading(self):
        for f in (self.out / "theme").glob("*/index.html"):
            h = heading(f.read_text(encoding="utf-8"))
            if h:
                self.assertRegex(h, r"^種類の違う人気の\d点$", f.parent.name)

    def test_the_label_is_escaped_and_optional(self):
        d = world()
        self.assertIn("<h2>種類の違う人気の", build.top_picks(C2, d, "k1"))
        html = build.top_picks(C2, d, "k1", label="先生<への>送別ギフト")
        self.assertIn("先生&lt;への&gt;送別ギフト、種類の違う人気の", html)

    def test_the_old_common_heading_on_a_gift_page_would_be_caught(self):           # negative: the heading without the page's words
        self.assertFalse(re.match(r"^先生への送別ギフト、種類の違う人気の", "種類の違う人気の4点"))
        self.assertTrue(re.match(r"^先生への送別ギフト、種類の違う人気の", "先生への送別ギフト、種類の違う人気の4点"))


if __name__ == "__main__":
    unittest.main()
