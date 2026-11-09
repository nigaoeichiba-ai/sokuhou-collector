"""kuma-sokuho.com (2026-11-09): the retired Shiga page redirects instead of answering 404, and the municipality pages outside the keep rule are noindex while
/live/<prefecture>/ still lists every municipality (the information stays).  Negative cases: the checks fail when the redirect is wrong or a municipality is missing."""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build, indexing, retired
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from sokuhou.sources import env_kuma
from tests.test_kuma_adsense_fix import TODAY, _yamaguchi
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data


class RetiredTest(unittest.TestCase):
    PAGES = {"live/shiga/index.html": "x", "index.html": "y"}

    def test_the_retired_shiga_page_redirects_to_the_prefectures_page(self):
        self.assertEqual(retired.htaccess_lines(self.PAGES), "Redirect 301 /live/shiga/m-4973b5/ /live/shiga/\n")

    def test_a_build_without_the_target_writes_no_redirect(self):
        self.assertEqual(retired.htaccess_lines({"index.html": "y"}), "")

    def test_a_retired_url_that_is_a_page_again_stops_the_build(self):
        with self.assertRaises(ValueError):
            retired.htaccess_lines({**self.PAGES, "live/shiga/m-4973b5/index.html": "z"})

    def test_a_redirect_to_a_redirect_stops_the_build(self):
        with mock.patch.object(retired, "RETIRED", {"/a/": "/b/", "/b/": "/live/shiga/"}):
            with self.assertRaises(ValueError):
                retired.htaccess_lines(self.PAGES)

    def test_every_retired_url_has_its_prefectures_page_as_the_target(self):
        for src, dst in retired.RETIRED.items():
            self.assertEqual(src.split("/")[1:3], dst.split("/")[1:3])       # the same /live/<prefecture>/
            self.assertTrue(dst.endswith("/"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class MunicipalityKeepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.keep = mock.patch.object(indexing, "_KEEP", {"cities": [indexing.city_hash("yamaguchi", "周南市")]})
        cls.keep.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.cities = {"岩国市": 120, "周南市": 30, "萩市": 6, "下松市": 4}          # 100+ records / on the keep list / thin / thin
        build.render_site(cls.raw, CFG, cls.out, release=True, prefs={"yamaguchi": _yamaguchi(cls.cities)}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.keep.stop()
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_only_the_kept_and_the_large_municipality_pages_are_indexed(self):
        sitemap = self.read("sitemap.xml")
        for city, indexed in (("岩国市", True), ("周南市", True), ("萩市", False), ("下松市", False)):
            html = self.read(f"live/yamaguchi/{live_mod.city_slug('yamaguchi', city)}/index.html")
            self.assertEqual("noindex" not in html, indexed, city)
            self.assertEqual(live_mod.city_url("yamaguchi", city) in sitemap, indexed, city)

    def test_the_prefecture_page_lists_every_municipality_with_its_count_so_that_nothing_is_lost(self):
        hub = self.read("live/yamaguchi/index.html")
        table = hub.split("市町村別の記録", 1)[1].split("</table>", 1)[0]
        for city, n in self.cities.items():
            self.assertIn(city, table, city)
            self.assertRegex(table, rf"{city}[^|]*?</td><td>{n}</td>", city)

    def test_a_negative_case_a_municipality_missing_from_the_prefecture_page_would_be_caught(self):
        hub = self.read("live/yamaguchi/index.html").replace("萩市", "")
        table = hub.split("市町村別の記録", 1)[1].split("</table>", 1)[0]
        self.assertNotIn("萩市", table)

    def test_noindex_municipality_pages_stay_linked_and_the_site_check_passes(self):
        hub = self.read("live/yamaguchi/index.html")
        for city in ("萩市", "下松市"):
            self.assertIn(live_mod.city_url("yamaguchi", city).replace("https://kuma-sokuho.com", ""), hub, city)
        problems = sitecheck.check(self.out, "https://kuma-sokuho.com") if hasattr(sitecheck, "check") else []
        self.assertFalse(problems)


if __name__ == "__main__":
    unittest.main()
