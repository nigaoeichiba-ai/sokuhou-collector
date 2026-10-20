"""The AdSense tag stays off the pages with nothing of their own to read (forms, the 404, the search, link lists) - kuma had it on every page, saichin already had the rule
(sites/saichin NO_ADS_PATHS).  `no_ads_paths` is a site setting read by sokuhou.sitekit.layout."""
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build
from sokuhou import sitekit
from tests.test_kuma_build import CFG, HAVE_PYPDF, LINKS, raw_data

TAG = "adsbygoogle"
ADS_CFG = {**CFG, "adsense_pub_id": "ca-pub-1234567890"}


class LayoutSettingTest(unittest.TestCase):
    SITE = {"assets": Path(__file__).parent, "nav": [], "glyph": "x", "source_html": "", "no_ads_paths": frozenset({"/contact/", "/live/"})}

    def html(self, path, site=None):
        return sitekit.layout(site or self.SITE, ADS_CFG, False, path=path, title="t", description="d", body="<h1>t</h1>")

    def test_a_listed_path_loads_no_tag_and_every_other_path_does(self):
        self.assertNotIn(TAG, self.html("/contact/"))
        self.assertIn(TAG, self.html("/about/"))

    def test_the_path_must_match_exactly_so_the_pages_below_a_hub_keep_the_tag(self):
        self.assertNotIn(TAG, self.html("/live/"))                       # the hub of links
        self.assertIn(TAG, self.html("/live/miyagi/"))                   # a prefecture's page and a municipality's page are content
        self.assertIn(TAG, self.html("/live/miyagi/m-a6154e/"))

    def test_a_site_without_the_setting_keeps_the_tag_everywhere(self):
        site = {k: v for k, v in self.SITE.items() if k != "no_ads_paths"}
        self.assertIn(TAG, self.html("/contact/", site))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class KumaBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(raw_data(), ADS_CFG, cls.out, release=True, links=LINKS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_forms_notice_and_404_have_no_tag_and_the_content_pages_keep_it(self):
        for rel in ("contact/index.html", "404.html", "notify/index.html"):
            self.assertNotIn(TAG, (self.out / rel).read_text(encoding="utf-8"), rel)
        for rel in ("index.html", "ranking/sightings/index.html", "about/index.html"):
            self.assertIn(TAG, (self.out / rel).read_text(encoding="utf-8"), rel)


if __name__ == "__main__":
    unittest.main()
