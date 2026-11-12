"""shiken-nittei.com: exam pages carry a study-book search section (Rakuten / Amazon search pages, PR, rel, target); no URL as link text."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sites.shiken.gen import SHOP_PAGES
from tests.test_trend_affiliate import problems

CONTENT = Path(__file__).resolve().parents[1] / "sites" / "shiken" / "content"


class ShikenAffiliate(unittest.TestCase):
    def test_exam_pages_have_both_malls(self):
        for path in SHOP_PAGES:
            d = json.loads((CONTENT / f"{path.strip('/')}.json").read_text(encoding="utf-8"))
            h = " ".join(s.get("html", "") + " ".join(s.get("paras", [])) for s in d["sections"])
            self.assertIn("hb.afl.rakuten.co.jp/hgc/", h, path)
            self.assertIn("amazon.co.jp/s?k=", h, path)
            self.assertEqual(problems(h), [], path)

    def test_every_page_is_clean(self):
        for f in CONTENT.glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            h = " ".join(s.get("html", "") + " ".join(s.get("paras", [])) for s in d.get("sections", []))
            self.assertEqual(problems(h), [], f.name)


if __name__ == "__main__":
    unittest.main()
