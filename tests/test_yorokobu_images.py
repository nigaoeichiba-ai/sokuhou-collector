"""How fast the pictures come (2026-10-12: "the pictures take a long time to appear"): small copies for small places, the first pictures not lazy, the rest lazy and async,
a connection opened early to the shop-picture host, and a soft block where a picture will be."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, make_mood_small
from tests.yorokobu_data import rich_boyfriend, with_musts

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}


class FilesTest(unittest.TestCase):
    def test_every_mood_picture_has_a_480_px_copy_that_is_much_smaller(self):
        for p in sorted(make_mood_small.MOOD.glob("*.webp")):
            if p.stem.endswith("-480"):
                continue
            small = make_mood_small.small_name(p)
            self.assertTrue(small.exists(), f"{small.name}: run python -m sites.yorokobu.make_mood_small")
            self.assertLessEqual(small.stat().st_size, p.stat().st_size * 0.45, small.name)
            self.assertLessEqual(small.stat().st_size, 30 * 1024, small.name)
            from PIL import Image
            with Image.open(small) as im:
                self.assertEqual(im.width, 480)


class HelperTest(unittest.TestCase):
    def test_a_mood_picture_offers_both_sizes_and_says_how_big_it_is_drawn(self):
        h = build.mood_img("food-1", "x", "(max-width: 640px) 100vw, 360px")
        self.assertIn('src="/assets/mood/food-1-480.webp"', h)
        self.assertIn('srcset="/assets/mood/food-1-480.webp 480w, /assets/mood/food-1.webp 960w"', h)
        self.assertIn('sizes="(max-width: 640px) 100vw, 360px"', h)
        self.assertIn('width="480" height="320"', h)                                   # the room is kept: nothing jumps when it arrives
        self.assertIn('loading="lazy" decoding="async"', h)
        self.assertIn('fetchpriority="high"', build.mood_img("food-1", "x", "100vw", "eager", high=True))

    def test_the_rakuten_picture_is_asked_for_in_the_size_a_small_place_needs(self):
        url = "https://thumbnail.image.rakuten.co.jp/@0_mall/s/cabinet/a.jpg?_ex=300x300"
        self.assertEqual(build.thumb(url, 128), url.replace("300x300", "128x128"))
        self.assertEqual(build.thumb("https://example.com/a.jpg?_ex=300x300", 128), "https://example.com/a.jpg?_ex=300x300")      # only that host takes the parameter


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8"))), cls.c)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 13))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def imgs(self, html, within=None):
        if within:
            m = re.search(within, html, re.S)
            html = m.group(0) if m else ""
        return re.findall(r"<img [^>]*>", html)

    def test_the_first_two_of_a_pages_first_products_are_not_lazy_and_the_rest_are(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        top = self.imgs(html, r'<section class="top-picks".*?</section>')
        self.assertGreaterEqual(len(top), 3)
        self.assertTrue(all('loading="eager"' in i and 'fetchpriority="high"' in i for i in top[:2]), top[:2])
        self.assertTrue(all('loading="lazy"' in i for i in top[2:]), top[2:])
        everything = [i for i in self.imgs(html) if "thumbnail.image.rakuten" in i or "item.rakuten" in i or "image.rakuten" in i]
        self.assertTrue(all("decoding=\"async\"" in i for i in everything))

    def test_the_connection_to_the_picture_host_is_opened_early_on_pages_with_products(self):
        self.assertIn('<link rel="preconnect" href="https://thumbnail.image.rakuten.co.jp">', self.read("gift/birthday-boyfriend/index.html"))
        self.assertNotIn("preconnect\" href=\"https://thumbnail", self.read("about/index.html"))

    def test_the_home_collage_takes_the_small_copies_and_keeps_two_of_them_first_in_line(self):
        home = self.read("index.html")
        cg = self.imgs(home, r'<div class="collage".*?</div>')
        self.assertEqual(len(cg), 6)
        self.assertTrue(all("-480.webp" in i and "srcset" in i for i in cg))
        self.assertEqual(sum('fetchpriority="high"' in i for i in cg), 2)

    def test_a_pick_card_takes_the_small_mood_copy_and_the_tiles_the_smallest_pictures(self):
        day = self.read("picks/2026-10-12/index.html")
        moods = self.imgs(day, r'<section class="block" id="amazon".*?</section>')
        self.assertTrue(moods and all("srcset=" in i and "-480.webp" in i and 'loading="lazy"' in i for i in moods), moods[:1])
        tiles = self.imgs(day, r'<ul class="pick-hls">.*?</ul>')
        self.assertTrue(tiles)
        self.assertFalse(any("_ex=300x300" in i for i in tiles))                    # the 84-px tiles do not carry the 300-px pictures
        self.assertTrue(all('loading="eager"' in i for i in tiles))
        first = self.imgs(day, r'<div class="pick-list">.*?</article>')[0]
        self.assertIn("fetchpriority", first)                                        # the first product of the day is what the page opens with

    def test_the_feature_page_loads_its_product_picture_first_and_its_drawings_late(self):
        f = self.c["features"][0]
        html = self.read(f"pick/{f['slug']}/index.html")
        hero = self.imgs(html, r'<a class="feat-photo.*?</a>')[0]
        self.assertIn('fetchpriority="high"', hero)
        mg = self.imgs(html, r'<div class="mg".*?</div>')
        self.assertEqual(len(mg), 4)
        self.assertTrue(all('loading="lazy"' in i and 'decoding="async"' in i for i in mg))

    def test_every_picture_says_its_size_so_that_nothing_jumps(self):
        for rel in ("index.html", "gift/birthday-boyfriend/index.html", "picks/2026-10-12/index.html"):
            for i in self.imgs(self.read(rel)):
                if "ic duo" in i:
                    continue
                self.assertRegex(i, r'width="\d+"', f"{rel}: {i[:80]}")
                self.assertRegex(i, r'height="\d+"', f"{rel}: {i[:80]}")


if __name__ == "__main__":
    unittest.main()
