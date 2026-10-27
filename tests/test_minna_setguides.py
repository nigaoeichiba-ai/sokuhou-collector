"""みんなのイラスト: the 使い分けのガイド of the featured sets (/series/<slug>/): every picture of the set has its line, the numbers are measured, the examples are in the build at their real size,
and the other sets do not get the section.  (Why: 2026-10-27, AdSense "low value content"; a set page was a grid of pictures and a stock list.)"""
import re
import unittest
from pathlib import Path

from PIL import Image

from sites.minna import setguides
from tests.test_minna_sitecache import shared_site


class InnerBox(unittest.TestCase):
    def test_the_empty_middle_of_a_frame_is_found(self):
        im = Image.new("RGBA", (100, 80), (200, 0, 0, 255))
        for x in range(20, 80):
            for y in range(10, 70):
                im.putpixel((x, y), (0, 0, 0, 0))
        self.assertEqual(setguides.inner_box(im), (20, 10, 80, 70))

    def test_a_picture_with_a_filled_middle_has_no_empty_part(self):
        im = Image.new("RGBA", (100, 80), (200, 0, 0, 255))
        x0, y0, x1, y1 = setguides.inner_box(im)
        self.assertEqual((x1 - x0, y1 - y0), (0, 0))

    def test_print_size_is_pixels_over_dpi(self):
        self.assertEqual(setguides.mm(300, 300), 25)
        self.assertEqual(setguides.mm(591, 150), 100)


class FeaturedSets(unittest.TestCase):
    def page(self, slug: str) -> str:
        out, _ = shared_site()
        return (out / "series" / slug / "index.html").read_text(encoding="utf-8")

    def test_every_featured_set_has_the_section_with_one_row_per_picture_and_measured_sizes(self):
        for slug, g in setguides.GUIDES.items():
            html = self.page(slug)
            self.assertIn("このセットの使い分け", html, slug)
            self.assertEqual(len(re.findall(r"<tr><td><a href=\"/illust/", html)), len(g["picks"]), slug)
            self.assertRegex(html, r"約\d+×\d+mm", slug)
            self.assertIn("このセットだけで作った例", html, slug)
            self.assertIn('href="/license/"', html, slug)

    def test_a_frame_set_shows_the_empty_part_and_the_others_do_not(self):
        self.assertIn("中の空き(px)", self.page("event-frames-flat"))
        self.assertNotIn("中の空き(px)", self.page("eto-lineup-kawaii"))

    def test_the_examples_are_in_the_build_and_the_page_gives_their_real_size(self):
        out, _ = shared_site()
        for slug, g in setguides.GUIDES.items():
            html = self.page(slug)
            for name, caption, uses, _label in g["examples"]:
                f = out / "assets" / "examples" / f"{name}.webp"
                self.assertTrue(f.exists(), name)
                w, h = Image.open(f).size
                self.assertIn(f'src="/assets/examples/{name}.webp"', html)
                self.assertIn(f'width="{w}" height="{h}"', html)
                self.assertIn(f"{w}×{h}px", html)
                self.assertIn("文面は例です。", html)
                self.assertTrue(uses, name)

    def test_the_other_sets_do_not_get_the_section(self):
        out, _ = shared_site()
        others = [p for p in (out / "series").iterdir() if p.name not in setguides.GUIDES][:20]
        self.assertGreater(len(others), 10)
        for p in others:
            self.assertNotIn("このセットの使い分け", (p / "index.html").read_text(encoding="utf-8"), p.name)

    def test_a_set_with_a_picture_without_a_line_stops_the_build(self):
        slug = "event-frames-flat"
        its = [{"id": f"{slug}-undokai", "title": "x", "w": 1, "h": 1, "path": Path("x")}]
        with self.assertRaises(AssertionError):
            setguides.set_guide_html({"slug": slug, "items": its})

    def test_no_example_is_larger_than_it_needs_to_be_and_none_is_empty(self):
        for f in (Path(setguides.EXAMPLES_DIR)).glob("*.webp"):
            w, h = Image.open(f).size
            self.assertGreaterEqual(min(w, h), 500, f.name)
            self.assertLessEqual(f.stat().st_size, 250 * 1024, f.name)


if __name__ == "__main__":
    unittest.main()
