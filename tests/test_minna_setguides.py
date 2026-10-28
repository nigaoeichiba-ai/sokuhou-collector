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


class SeriesPageThickness(unittest.TestCase):
    """2026-10-29 (owner): a set is published with a thick page from the start.  Every featured set page has 800+ characters of sentences (tables and data boxes not counted), the numbers in the
    sentences are measured, and no placeholder is left."""

    def test_every_featured_set_page_has_800_characters_of_sentences_and_no_open_placeholder(self):
        from sites.minna import build
        out, _ = shared_site()
        short = {}
        for slug in setguides.GUIDES:
            html = (out / "series" / slug / "index.html").read_text(encoding="utf-8")
            n = build.prose_chars(html)
            if n < 800:
                short[slug] = n
            main = re.search(r"<main.*?</main>", html, re.S).group(0)
            text = re.sub(r"<script.*?</script>|<style.*?</style>", "", main, flags=re.S)
            text = re.sub(r"<[^>]+>", "", text)
            self.assertNotRegex(text, r"\{[a-z_0-9]+\}", slug)
            self.assertNotIn("None", text, slug)
        self.assertEqual(short, {})

    def test_the_eleven_featured_sets_are_the_four_first_and_the_seven_of_2026_10_29(self):
        self.assertEqual(len(setguides.GUIDES), 11)
        for slug in ("tropical-fruits-flat", "animals-undokai-kawaii", "newyear-eve-cool-sumi", "office-worker-middleaged-flat", "animal-nametags-kawaii", "oshogatsu-sumi-cool", "realistic-zoo-field-guide"):
            self.assertIn(slug, setguides.GUIDES)
            self.assertEqual(len(setguides.GUIDES[slug]["examples"]), 2, slug)
            self.assertGreaterEqual(len(setguides.GUIDES[slug]["points"]), 4, slug)

    def test_the_name_tag_numbers_written_in_the_text_are_the_measured_ones(self):
        lib = Path(setguides.HERE) / "library" / "animal-nametags-kawaii"
        sizes = {}
        for f in lib.glob("*.webp"):
            b = setguides.blank_box(Image.open(f), "cream")
            self.assertIsNotNone(b, f.name)
            sizes[f.stem.replace("animal-nametags-kawaii-", "")] = (b[2] - b[0] + 1, b[3] - b[1] + 1)
        self.assertEqual(len(sizes), 12)
        self.assertEqual(min(sizes, key=lambda k: sizes[k][0] * sizes[k][1]), "dog")
        self.assertEqual(max(sizes, key=lambda k: sizes[k][0] * sizes[k][1]), "bear")
        self.assertEqual(sizes["dog"], (185, 84))
        self.assertEqual(sizes["bear"], (309, 122))
        for k, (w, h) in sizes.items():           # only the rabbit holds the tag above the middle of the picture
            im = Image.open(lib / f"animal-nametags-kawaii-{k}.webp")
            b = setguides.blank_box(im, "cream")
            high = (b[1] + b[3]) / 2 / im.height < 0.5
            self.assertEqual(high, k == "rabbit", k)

    def test_the_blank_box_finds_a_tag_and_nothing_in_a_picture_without_one(self):
        im = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
        for x in range(40, 160):
            for y in range(60, 110):
                im.putpixel((x, y), (255, 246, 220, 255))
        self.assertEqual(setguides.blank_box(im, "cream"), (40, 60, 159, 109))
        self.assertIsNone(setguides.blank_box(Image.new("RGBA", (200, 160), (200, 0, 0, 255)), "cream"))


if __name__ == "__main__":
    unittest.main()
