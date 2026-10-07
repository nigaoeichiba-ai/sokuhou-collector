import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build
from sites.minna.catalog import CATEGORIES

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト運営", "contact_form_url": "https://example.com/form",
       "adsense_pub_id": None, "indexnow_key": "0123456789abcdef0123456789abcdef"}


class MinnaBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(CFG, cls.out, release=True, today=date(2026, 10, 7))
        cls.items = build.load_catalog()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

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

    def test_downloads_are_transparent_pngs_of_the_stated_size(self):
        from PIL import Image
        it = self.items[0]
        im = Image.open(self.out / "files" / f"{it['id']}.png")
        self.assertEqual(im.size, (it["w"], it["h"]))
        self.assertEqual(im.mode, "RGBA")
        self.assertLess(im.getpixel((0, 0))[3], 255)       # the corner is transparent

    def test_detail_page_has_downloads_licence_ai_note_and_image_markup(self):
        html = self.read("illust/season-christmas/index.html")
        for needle in ('download="season-christmas.png"', "ずっと無料・商用OK・クレジット不要", "AIで生成し、人が選んで、整えたもの", '"@type": "ImageObject"',
                       '"license": "https://minna-no-illust.com/license/"', "/files/season-christmas.png", 'class="bgsw"'):
            self.assertIn(needle, html)

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

    def test_every_internal_link_resolves(self):
        bad = []
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            for href in re.findall(r'(?:href|src)="(/[^"#?]*)', self.read(rel)):
                tgt = href.lstrip("/") + ("index.html" if href.endswith("/") else "")
                if tgt and not (self.out / tgt).exists():
                    bad.append((rel, href))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
