"""D26 (owner decision 2026-11-15): the pages of minna show no source (no "参考にした情報" list, no link to a source).

The sources of a guide stay in content/guides.json (tests/test_minna_guides.py checks they are real URLs) but are not shown.
Allowed on a screen: advertising links (affiliate), share buttons, the link back to the site that the licence text offers ("出典リンクを付ける(任意)" is the credit for this site's pictures).
"""
import re
import unittest

from sites.minna import build

BASE = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト", "contact_own": True}
AFFILIATE = ("rakuten.co.jp", "amazon.co.jp", "valuecommerce.com", "a8.net", "accesstrade", "moshimo.com")
ALLOWED = ("minna-no-illust.com", "line.me", "twitter.com", "x.com", "adssettings.google.com", "www.aboutads.info")


def problems(html: str) -> list[str]:
    out = []
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", "", body)
    for w in ("参考にした情報", "情報源", "出どころ"):
        if w in text:
            out.append(f"word {w}")
    for m in re.finditer(r'<a\b[^>]*href="(https?://[^"]+)"', body):
        host = re.match(r"https?://([^/]+)", m.group(1)).group(1)
        if not (host.endswith(ALLOWED) or any(a in host for a in AFFILIATE)):
            out.append(f"link {host}")
    return out


class NoSourceOnScreenTest(unittest.TestCase):
    def test_the_check_finds_the_old_list(self):
        old = '<section class="art"><h2>参考にした情報</h2><ul><li><a href="https://www.post.japanpost.jp/x" rel="noopener nofollow">日本郵便</a></li></ul></section>'
        self.assertEqual(sorted(problems(old)), ["link www.post.japanpost.jp", "word 参考にした情報"])
        self.assertEqual(problems('<a href="https://hb.afl.rakuten.co.jp/hgc/x" rel="nofollow sponsored">楽天</a><a href="https://line.me/R/share">LINE</a>'), [])

    def test_no_guide_shows_its_sources(self):
        items, series = build.load_data()
        guides = build.load_guides()
        with_sources = [g for g in guides if g.get("sources")]
        self.assertGreaterEqual(len(with_sources), 20)               # the sources are still in the data
        for g in guides:
            html = build.guide_page(BASE, False, g, series)
            self.assertEqual(problems(html), [], g["slug"])


if __name__ == "__main__":
    unittest.main()
