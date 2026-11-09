"""The live depth watch of trend-sokuho.com (sites/trend/tools/scan_depth_live.py): its judgement, run on the pages the build makes (no network).
Past failure reproduced on purpose: a thin article that is indexed must be RED, never counted as fine."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
spec = importlib.util.spec_from_file_location("scan_depth_live", SITE / "tools" / "scan_depth_live.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)
GF = set(newsite.site_hooks(SITE).DEEP_GRANDFATHERED)


class DepthScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages, _ = newsite.build_pages(SITE)

    def test_the_site_as_built_has_no_red_article(self):
        states = {}
        for rel, h in self.pages.items():
            if rel.endswith("index.html") and isinstance(h, str):
                path = "/" if rel == "index.html" else "/" + rel[: -len("index.html")]
                states[path] = scan.judge(path, h, GF)[0]
        self.assertNotIn("THIN", states.values())
        self.assertNotIn("NOT-DEEP", states.values())
        self.assertIn("review", states.values())          # the old articles below 2,000 are listed to review, never padded
        self.assertEqual(states["/cat/bousai/"], "not-article")

    def test_a_thin_indexed_article_is_red_and_a_new_short_one_is_not_deep(self):
        thin = '<meta property="og:type" content="article"><main><h1>薄い</h1><p>' + "短い文です。" * 20 + "</p></main>"
        self.assertEqual(scan.judge("/trend-old/", thin, GF)[0], "THIN")                       # below 1,200 and indexed: red even for an old article
        mid = '<meta property="og:type" content="article"><main><h1>中</h1><p>' + "ふつうの長さの文です。" * 150 + "</p></main>"
        self.assertEqual(scan.judge("/trend-new/", mid, GF)[0], "NOT-DEEP")                    # a new article: below 2,000 or no own table
        self.assertIn(scan.judge("/trend-typhoon32/", mid, GF)[0], ("review", "deep"))          # an old one is only reviewed
        noindexed = mid.replace("<main>", '<meta name="robots" content="noindex,follow"><main>')
        self.assertEqual(scan.judge("/trend-new/", noindexed, GF)[0], "deep")                  # a bridge page is not judged


if __name__ == "__main__":
    unittest.main()
