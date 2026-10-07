"""Print versions (A4 coloring pages, postcard-size New Year items) are built, are real PDFs and are linked only where they make sense."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト運営", "contact_own": True, "adsense_pub_id": None}


class PrintablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(CFG, cls.out, release=True, today=date(2026, 10, 7))
        cls.items, _ = build.load_data()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pdf_kinds_follow_touch_and_genre(self):
        by = {i["id"]: i for i in self.items}
        self.assertEqual(build.pdf_kinds(by["coloring-newyear-lineart-daruma"]), ["a4"])
        self.assertEqual(build.pdf_kinds(by["eto-sheep-kawaii-kite"]), ["hagaki"])
        self.assertEqual(build.pdf_kinds(by["cat-pose-wave"]), [])            # an ordinary animal pose has no print version
        self.assertEqual(build.pdf_kinds(by["r-joy"]), [])

    def test_every_promised_pdf_exists_is_a_pdf_and_is_linked(self):
        n = 0
        for it in self.items:
            html = (self.out / "illust" / it["id"] / "index.html").read_text(encoding="utf-8")
            kinds = build.pdf_kinds(it)
            for k in kinds:
                rel = f"files/{it['id']}-{k}.pdf"
                self.assertIn(rel, self.files)
                self.assertIn(f"/{rel}", html)
                data = (self.out / rel).read_bytes()
                self.assertTrue(data.startswith(b"%PDF"), rel)
                self.assertLess(len(data), 900_000, f"{rel} is too heavy: {len(data)} bytes")
                n += 1
            if not kinds:
                self.assertNotIn("-a4.pdf", html)
                self.assertNotIn("-hagaki.pdf", html)
        self.assertGreater(n, 20)

    def test_the_a4_page_is_a4_in_proportion(self):
        import re
        data = (self.out / "files" / "coloring-newyear-lineart-daruma-a4.pdf").read_bytes()
        box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", data)
        self.assertTrue(box)
        w, h = float(box.group(1)), float(box.group(2))
        self.assertAlmostEqual(w / h, 210 / 297, delta=0.01)


if __name__ == "__main__":
    unittest.main()
