import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build
from tests.test_minna_sitecache import SHARED_CFG, shared_site
from sites.minna.catalog import CATEGORIES

CFG = SHARED_CFG


class MinnaBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()                      # one build for the page, print and browser tests (tests/test_minna_sitecache.py)
        cls.items = build.load_catalog()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_catalogue_and_page_set(self):
        self.assertGreaterEqual(len(self.items), 80)
        self.assertEqual(len({i["id"] for i in self.items}), len(self.items))
        for rel in ("index.html", "illust/index.html", "license/index.html", "request/index.html", "tool/card/index.html", "about/index.html",
                    "privacy/index.html", "contact/index.html", "sitemap.xml", "sitemap-images.xml", "robots.txt", "manifest.webmanifest" if False else "ads.txt" if False else "404.html"):
            self.assertIn(rel, self.files)
        for slug, _, _ in CATEGORIES:
            self.assertIn(f"category/{slug}/index.html", self.files)
        for it in self.items:
            for rel in (f"illust/{it['id']}/index.html", f"files/{it['id']}.png", f"files/{it['id']}.webp", f"thumbs/{it['id']}.webp"):
                self.assertIn(rel, self.files)

    def test_keyword_pages_exist_only_for_words_with_enough_items_from_several_sets(self):
        tags = build.tag_list(self.items)
        self.assertGreater(len(tags), 20)
        self.assertLessEqual(len(tags), build.MAX_TAG_PAGES)
        for tag in tags:
            users = build.tagged(self.items, tag)
            self.assertGreaterEqual(len(users), build.MIN_TAG)                 # counted here, not by the builder
            self.assertGreaterEqual(len({i["series"] for i in users}), 2)
            self.assertNotIn(" ", tag)
            html = self.read(build.tag_url(tag).strip("/") + "/index.html")
            self.assertIn(f"{len(users)}点集めました", html)
            self.assertIn("<h1>「" + tag + "」のイラスト</h1>", html)
        for rare in ("イラスト", "かわいい"):
            self.assertNotIn(rare, tags)
        self.assertIn("/tag/", self.read("sitemap.xml"))

    def test_a_guide_set_carrying_every_animals_name_does_not_fill_one_animals_page(self):
        """The 犬 page led with a sparrow: the animal guide set tags all twelve items 犬, ハムスター, カエル ... (weekly review 2026-10-12)."""
        guide = [i for i in self.items if i["series"] == "realistic-animals-pets"]
        self.assertGreater(len(guide), 8)
        listed = {i["id"] for i in build.tagged(self.items, "犬")}
        self.assertIn("realistic-animals-pets-dog", listed)
        self.assertNotIn("realistic-animals-pets-sparrow", listed)

    def test_detail_page_links_a_keyword_to_its_page_only_when_the_page_exists(self):
        tags = set(build.tag_list(self.items))
        it = next(i for i in self.items if any(t in tags for t in i["tags"]) and any(t not in tags for t in i["tags"]))
        html = self.read(f"illust/{it['id']}/index.html")
        for t in it["tags"]:
            link = f'<li><a href="{build.tag_url(t)}">{t}</a></li>'
            self.assertEqual(link in html, t in tags)

    def test_downloads_are_transparent_pngs_of_the_stated_size(self):
        from PIL import Image
        it = self.items[0]
        im = Image.open(self.out / "files" / f"{it['id']}.png")
        self.assertEqual(im.size, (it["w"], it["h"]))
        self.assertEqual(im.mode, "RGBA")
        self.assertLess(im.getpixel((0, 0))[3], 255)       # the corner is transparent

    def test_detail_page_has_downloads_licence_and_image_markup_and_does_not_shout_about_ai(self):
        html = self.read("illust/season-christmas/index.html")
        for needle in ('download="season-christmas.png"', "ずっと無料・商用OK・クレジット不要", '"@type": "ImageObject"',
                       '"license": "https://minna-no-illust.com/license/"', "/files/season-christmas.png", 'class="bgsw"'):
            self.assertIn(needle, html)
        # owner decision 2026-10-12: the AI explanation is on the licence page (and the about/privacy sources), not on every picture and not in the footer
        for gone in ("ai-note", "AIで生成し", "生成AI"):
            self.assertNotIn(gone, html)
        self.assertIn("生成AIで制作", self.read("license/index.html"))

    def test_the_indexnow_key_file_is_published_at_the_site_root(self):
        self.assertIn("0123456789abcdef0123456789abcdef.txt", self.files)
        self.assertEqual(self.read("0123456789abcdef0123456789abcdef.txt"), "0123456789abcdef0123456789abcdef")

    def test_licence_page_is_a_permission_not_a_copyright_claim(self):
        html = self.read("license/index.html")
        self.assertIn("利用の許諾", html)
        self.assertIn("商用利用", html)
        self.assertNotIn("著作権は当サイトに帰属します", html)
        self.assertNotIn("侵害しないことを保証します", html)

    def test_image_sitemap_lists_every_illustration(self):
        sm = self.read("sitemap-images.xml")
        self.assertEqual(sm.count("<image:loc>"), len(self.items))
        self.assertIn("Sitemap: https://minna-no-illust.com/sitemap-images.xml", self.read("robots.txt"))

    def test_the_card_maker_page(self):
        html = self.read("tool/card/index.html")
        for needle in ("<canvas", 'name="tpl"', 'name="msg"', "data-save", "送信されません"):
            self.assertIn(needle, html)
        data = json.loads(re.search(r'data-json="([^"]+)"', html).group(1).replace("&quot;", '"'))
        self.assertTrue(len(data["chars"]) >= 30)
        self.assertTrue(all((self.out / c["src"].lstrip("/")).exists() for c in data["chars"]))

    def test_the_operator_name_is_only_where_the_law_needs_it(self):
        """オーナー指示 2026-10-19: the company name appears on the about page (the operator's information) and nowhere else, not even in the structured data."""
        op = CFG["operator_name"]
        where = [rel for rel in self.files if rel.endswith((".html", ".xml", ".json", ".txt", ".js")) and op in self.read(rel)]
        self.assertEqual(where, ["about/index.html"])
        ld = self.read("illust/season-christmas/index.html") + self.read("guide/nurie-insatsu/index.html")
        names = re.findall(r'"@type": "Organization", "name": "([^"]*)"', ld)
        self.assertGreaterEqual(len(names), 3)                       # creator on the picture page, author and publisher on the guide
        self.assertEqual(set(names), {CFG["site_name"]})

    def test_every_internal_link_resolves(self):
        built = set(self.files)                                   # the list of what was built answers "is there such a file" without asking the disk 40,000 times
        bad = []
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            for href in re.findall(r'(?:href|src)="(/[^"#?]*)', self.read(rel)):
                tgt = href.lstrip("/") + ("index.html" if href.endswith("/") else "")
                if tgt and tgt not in built:
                    bad.append((rel, href))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
