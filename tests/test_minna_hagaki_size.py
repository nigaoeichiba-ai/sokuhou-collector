"""みんなのイラスト: the postcard size guide (2026-10-28).  Its pixel table is recomputed here a second way (inches first) and must match the page; the figures that come from the post office's
own pages are pinned."""
import json
import re
import unittest
from pathlib import Path

from tests.test_minna_sitecache import shared_site

GUIDES = Path(__file__).resolve().parents[1] / "sites" / "minna" / "content" / "guides.json"


class HagakiSize(unittest.TestCase):
    def page(self) -> str:
        out, _ = shared_site()
        return (out / "guide" / "hagaki-size-ichiran" / "index.html").read_text(encoding="utf-8")

    def test_pixel_table_matches_an_independent_calculation(self):
        html = self.page()
        for w, h in ((90, 140), (100, 148), (107, 154)):
            for dpi in (300, 350):
                pw = round(w / 25.4 * dpi)
                ph = round(h / 25.4 * dpi)
                self.assertIn(f"{pw:,}×{ph:,}px", html, (w, h, dpi))

    def test_the_card_size_matches_the_makers_export(self):
        self.assertIn("1,181×1,748px", self.page())
        from sites.minna import build
        self.assertEqual(build.PDF_SIZES["hagaki"][:2], (1181, 1748))

    def test_official_figures_and_sources(self):
        html = self.page()
        for t in ("14〜15.4cm", "9〜10.7cm", "2g以上6g以内", "85円", "170円", "4〜12g", "post.japanpost.jp/service/create/guideline/01.html"):
            self.assertIn(t, html)

    def test_no_claim_about_the_address_side_layout(self):
        g = [x for x in json.loads(GUIDES.read_text(encoding="utf-8"))["guides"] if x["slug"] == "hagaki-size-ichiran"][0]
        self.assertNotIn("郵便番号枠", json.dumps(g, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
