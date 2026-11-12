"""kurashi-calendar.com: pages whose topic has something to buy carry Rakuten / Amazon search links with PR, rel and target; no URL as link text."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sites.kurashi.gen.shop_links import SHOP_PAGES
from tests.test_trend_affiliate import problems

CONTENT = Path(__file__).resolve().parents[1] / "sites" / "kurashi" / "content"


def html_of(path: str) -> str:
    name = "home" if path == "/" else path.strip("/").replace("/", "-")
    d = json.loads((CONTENT / f"{name}.json").read_text(encoding="utf-8"))
    return " ".join(s.get("html", "") for s in d["sections"])


class KurashiAffiliate(unittest.TestCase):
    def test_topic_pages_have_links(self):
        for path, (_h2, _intro, rk, am) in SHOP_PAGES.items():
            h = html_of(path)
            self.assertIn("hb.afl.rakuten.co.jp/hgc/", h, path)
            if am:
                self.assertIn("amazon.co.jp/s?k=", h, path)
            self.assertEqual(problems(h), [], path)

    def test_missing_link_is_caught(self):
        self.assertNotIn("hb.afl.rakuten.co.jp/hgc/", "<p>年賀状</p>")
        self.assertTrue(problems('<a href="https://hb.afl.rakuten.co.jp/hgc/I/?pc=x">https://hb.afl.rakuten.co.jp/</a>（PR）'))


if __name__ == "__main__":
    unittest.main()
