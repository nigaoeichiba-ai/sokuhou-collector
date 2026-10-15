import tempfile
import unittest
from pathlib import Path

from sokuhou import sitekit

CFG = {"site_url": "https://example.test", "site_name": "テスト", "adsense_pub_id": None}
_ASSETS = tempfile.TemporaryDirectory()
(Path(_ASSETS.name) / "style.css").write_text("body{}", encoding="utf-8")
SITE = {"nav": [("トップ", "/", "/")], "glyph": "", "assets": Path(_ASSETS.name), "source_html": ""}
LARGE = '<meta name="googlebot" content="max-image-preview:large">'


def page(preview=False, og_image="/og.png"):
    return sitekit.layout(SITE, CFG, preview, path="/", title="t", description="d", body="<p>x</p>", og_image=og_image)


class DiscoverTagTest(unittest.TestCase):
    def test_large_preview_tag_with_a_share_picture(self):
        self.assertIn(LARGE, page())

    def test_no_tag_without_a_share_picture(self):
        self.assertNotIn(LARGE, page(og_image=None))   # negative: a page with no 1200px picture must not claim large previews

    def test_no_tag_on_a_preview_and_noindex_stays_alone(self):
        html = page(preview=True)
        self.assertNotIn("max-image-preview", html)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', html)

    def test_tag_does_not_use_the_robots_name(self):
        # kuma/atomou add noindex only when no name="robots" tag exists yet
        self.assertNotIn('name="robots"', page())


if __name__ == "__main__":
    unittest.main()
