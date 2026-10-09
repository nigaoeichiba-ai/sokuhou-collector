"""No characters on the gift site (owner, 2026-10-09: "as long as the mascot is there, the childishness stays"), and every occasion and person has an icon."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, icons, ogimage

HERE = Path(__file__).parent
SITE = Path(__file__).resolve().parents[1] / "sites" / "yorokobu"


class NoMascotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
        cls.items = json.loads((HERE / "fixtures" / "yorokobu" / "items.json").read_text(encoding="utf-8"))
        cls.c = content.load()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, cls.items, cls.cfg, cls.out, release=True, today=date(2026, 10, 9))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def pages(self):
        return [(f.relative_to(self.out).as_posix(), f.read_text(encoding="utf-8")) for f in sorted(self.out.rglob("*.html"))]

    def test_no_page_shows_a_character_picture_or_names_one(self):
        for rel, html in self.pages():
            imgs = set(re.findall(r'src="(/assets/img/[^"]+)"', html))
            self.assertLessEqual(imgs, {"/assets/img/og.webp"}, rel)             # the only picture left is the default share image
            for word in ("シマエナガ", "head-mascot", "hero-art", "step-mascot", "concierge-bird", "pair-mini"):
                self.assertNotIn(word, html, f"{rel}: {word}")

    def test_the_picture_files_of_the_characters_are_not_published(self):
        left = sorted(p.relative_to(self.out).as_posix() for p in (self.out / "assets" / "img").rglob("*") if p.is_file())
        self.assertEqual(left, ["assets/img/og.webp"])

    def test_every_occasion_has_a_line_icon_and_every_person_a_badge(self):
        self.assertLessEqual(set(self.c["occ"]), set(icons.OCCASION), "an occasion without an icon")
        self.assertLessEqual(set(self.c["rec"]), set(icons.RECIPIENT), "a person without a badge")
        for ch in icons.RECIPIENT.values():
            self.assertLessEqual(len(ch), 2, ch)                                  # it has to fit in the circle

    def test_every_symbol_a_page_uses_is_defined_on_that_page(self):
        used_somewhere = 0
        for rel, html in self.pages():
            used = set(re.findall(r'<use href="#(o-[a-z\-]+)"', html))
            defined = set(re.findall(r'<symbol id="(o-[a-z\-]+)"', html))
            self.assertLessEqual(used, defined, rel)
            used_somewhere += bool(used)
        self.assertGreater(used_somewhere, 100)

    def test_the_share_cards_and_icons_are_drawn_without_a_character(self):
        if not ogimage.available():
            self.skipTest("Pillow or a Japanese font is missing")
        png = ogimage.card(title="母の日に母へ贈るプレゼント", tag="母 × 母の日", site="よろこぶプレゼント")
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertNotIn("bird", ogimage.card.__wrapped__.__code__.co_varnames)
        for name in ("favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png"):
            self.assertTrue((SITE / "assets" / name).exists(), name)

    def test_the_old_wording_that_belonged_to_the_characters_is_gone(self):
        for rel, html in self.pages():
            for word in ("ソムリエ", "ナビゲーター", "コンシェルジュ", "ギフトマップ"):
                self.assertNotIn(word, html, f"{rel}: {word}")


if __name__ == "__main__":
    unittest.main()
