"""みんなのイラスト: the extra section of a picture people search for by itself (content/item_guides.json; 2026-11-04: 千歳飴の袋).  The numbers are computed from the file,
the examples exist at the size the page says, no placeholder is left open, and other pictures do not get the section."""
import re
import unittest
from pathlib import Path

from PIL import Image

from sites.minna import itemguides
from tests.test_minna_sitecache import shared_site

ID = "shichigosan-items-flat-chitose"


class ItemGuideText(unittest.TestCase):
    def test_every_placeholder_is_a_known_number(self):
        it = {"id": ID, "w": 224, "h": 499}
        st = itemguides.stats(it)
        for g in itemguides.GUIDES.values():
            for p in g["paragraphs"]:
                p.format(**st)

    def test_print_sizes_are_pixels_over_dpi(self):
        st = itemguides.stats({"w": 224, "h": 499})
        self.assertEqual(st["mm300"], "約19×42mm")
        self.assertEqual(st["mm100"], "約57×127mm")
        self.assertEqual((st["a4_cols"], st["a4_rows"], st["a4_n"]), (11, 7, 77))

    def test_the_examples_have_a_spec_and_a_file(self):
        for g in itemguides.GUIDES.values():
            self.assertGreaterEqual(len(g["examples"]), 2)
            for ex in g["examples"]:
                self.assertTrue((itemguides.EXAMPLES_DIR / f"{ex['name']}.webp").exists(), ex["name"])
                self.assertTrue(ex["uses"])


class ItemGuidePage(unittest.TestCase):
    def page(self, item_id):
        out, _ = shared_site()
        return (out / "illust" / item_id / "index.html").read_text(encoding="utf-8")

    def test_the_chitose_bag_page_has_the_section_the_numbers_and_the_examples(self):
        html = self.page(ID)
        self.assertIn("千歳飴の袋の大きさと印刷のしかた", html)
        self.assertIn("幅224px、高さ499px", html)
        self.assertIn("約19×42mm", html)
        self.assertIn("型紙(展開図)ではありません", html)
        for ex in itemguides.GUIDES[ID]["examples"]:
            w, h = Image.open(itemguides.EXAMPLES_DIR / f"{ex['name']}.webp").size
            self.assertIn(f'src="/assets/examples/{ex["name"]}.webp"', html)
            self.assertIn(f'width="{w}" height="{h}"', html)
        self.assertIn("<title>千歳飴の袋イラスト 無料ダウンロード", html)
        main = re.search(r"<main.*?</main>", html, re.S).group(0)
        text = re.sub(r"<[^>]+>", "", re.sub(r"<script.*?</script>", "", main, flags=re.S))
        self.assertNotRegex(text, r"\{[a-z_0-9]+\}")

    def test_the_example_images_are_in_the_build(self):
        out, _ = shared_site()
        for ex in itemguides.GUIDES[ID]["examples"]:
            self.assertTrue((out / "assets" / "examples" / f"{ex['name']}.webp").exists(), ex["name"])

    def test_the_other_pictures_do_not_get_the_section(self):
        html = self.page("shichigosan-items-flat-zori")
        self.assertNotIn("千歳飴の袋の大きさと印刷のしかた", html)
        self.assertIn("無料・商用OKのイラスト |", html)


if __name__ == "__main__":
    unittest.main()
