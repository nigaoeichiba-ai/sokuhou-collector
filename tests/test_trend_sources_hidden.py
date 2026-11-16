"""trend-sokuho.com: no link to an information source is shown on a page (owner 2026-11-15, D26).

Only ad links, the Rakuten API credit and the AdSense opt-out links of the privacy page may leave the site.  The bottom line of an article ('出典: 名前（公表日）をもとに作成', no link)
stays.  A page listed in PENDING is skipped (empty now: the 11/14 NEWT and Outlook articles were cleaned on 2026-11-15).
"""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
ALLOWED_HOSTS = ("hb.afl.rakuten.co.jp", "px.a8.net", "h.accesstrade.net", "www.amazon.co.jp", "af.moshimo.com", "ck.jp.ap.valuecommerce.com", "adssettings.google.com", "www.aboutads.info",
                 "developers.rakuten.com")
PENDING = ()


def source_links(html: str) -> list[str]:
    return [h for h in re.findall(r'<a [^>]*href="https?://([^/"]+)', html) if h not in ALLOWED_HOSTS and "trend-sokuho.com" not in h]


class SourcesHidden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "out"
        old = os.environ.get("TREND_NENGAJO_SIM")
        os.environ["TREND_NENGAJO_SIM"] = "1"
        try:
            newsite.main_build(SITE, ["--out", str(out), "--release"])
        finally:
            os.environ.pop("TREND_NENGAJO_SIM") if old is None else os.environ.__setitem__("TREND_NENGAJO_SIM", old)
        cls.pages = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*.html")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_page_links_to_a_source(self):
        for rel, html in self.pages.items():
            if rel in PENDING:
                continue
            self.assertEqual(source_links(html), [], rel)

    def test_the_check_catches_a_source_link_and_lets_an_ad_through(self):
        self.assertEqual(source_links('<a href="https://www.nta.go.jp/x.htm">国税庁</a>'), ["www.nta.go.jp"])
        self.assertEqual(source_links('<a href="https://px.a8.net/svt/ejp?a8mat=A" rel="nofollow sponsored">広告</a><a href="/x/">内</a>'), [])

    def test_the_price_simulator_does_not_link_to_the_companies(self):
        self.assertEqual(source_links(self.pages["trend-nengajo-hayawari/index.html"]), [])


if __name__ == "__main__":
    unittest.main()
