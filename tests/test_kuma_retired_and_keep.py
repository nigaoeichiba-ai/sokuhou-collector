"""kuma-sokuho.com (2026-11-09): a municipality has a page only when it is kept (keep rule B: a click or 50 impressions in Search Console, or 100 records);
the others are listed on /live/<prefecture>/ and their old URLs redirect (301) to it.  The retired Shiga page redirects too.

Negative cases: the checks fail when a redirect points at a missing page, a redirect source is still a page or is still linked, a municipality is missing from its
prefecture's table, or the rule cannot be rolled back."""
import re
import tempfile
import unittest
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
        self.assertEqual(retired.redirects(self.PAGES)["/live/shiga/m-4973b5/"], "/live/shiga/")
        self.assertIn("Redirect 301 /live/shiga/m-4973b5/ /live/shiga/\n", retired.htaccess_lines(self.PAGES))

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

    def test_a_known_municipality_url_without_a_page_redirects_to_its_prefecture_and_one_with_a_page_does_not(self):
        known = ["/live/miyagi/m-aaaaaa/", "/live/miyagi/m-bbbbbb/", "/live/akita/m-cccccc/"]
        pages = {"live/miyagi/index.html": "x", "live/miyagi/m-aaaaaa/index.html": "y"}        # akita has no prefecture page in this build
        with mock.patch.object(retired, "KNOWN", known):
            got = retired.redirects(pages)
        self.assertEqual(got.get("/live/miyagi/m-bbbbbb/"), "/live/miyagi/")
        self.assertNotIn("/live/miyagi/m-aaaaaa/", got)
        self.assertNotIn("/live/akita/m-cccccc/", got)                                          # a redirect to a page that does not exist is never written

    def test_the_known_urls_are_the_municipality_pages_that_existed(self):
        self.assertGreaterEqual(len(retired.KNOWN), 150)
        self.assertEqual(len(retired.KNOWN), len(set(retired.KNOWN)))
        for u in retired.KNOWN:
            self.assertRegex(u, r"^/live/[a-z]+/m-[0-9a-f]{6}/$")


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class MunicipalityKeepTest(unittest.TestCase):
    CITIES = {"岩国市": 120, "周南市": 30, "萩市": 6, "下松市": 4}          # 100+ records / on the keep list / not kept / not kept

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.keep = mock.patch.object(indexing, "_KEEP", {"cities": [indexing.city_hash("yamaguchi", "周南市")]})
        cls.keep.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs={"yamaguchi": _yamaguchi(cls.CITIES)}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.keep.stop()
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    @staticmethod
    def rel(city):
        return f"live/yamaguchi/{live_mod.city_slug('yamaguchi', city)}/index.html"

    def redirects(self):
        return dict(re.findall(r"^Redirect 301 (\S+) (\S+)$", self.read(".htaccess"), re.M))

    def test_only_the_kept_municipalities_have_a_page_and_it_is_indexed(self):
        sitemap = self.read("sitemap.xml")
        for city, kept in (("岩国市", True), ("周南市", True), ("萩市", False), ("下松市", False)):
            self.assertEqual(self.rel(city) in self.files, kept, city)
            if kept:
                self.assertNotIn("noindex", self.read(self.rel(city)), city)
            self.assertEqual(live_mod.city_url("yamaguchi", city) in sitemap, kept, city)

    def test_the_prefecture_page_lists_every_municipality_with_its_count_and_links_only_the_kept(self):
        hub = self.read("live/yamaguchi/index.html")
        table = hub.split("市町村別の記録", 1)[1].split("</table>", 1)[0]
        for city, k in self.CITIES.items():
            self.assertIn(city, table, city)
            self.assertRegex(table, rf"{city}[^|]*?</td><td>{k}</td>", city)
        for city, kept in (("岩国市", True), ("周南市", True), ("萩市", False), ("下松市", False)):
            self.assertEqual(f'href="{live_mod.city_url("yamaguchi", city)}"' in table, kept, city)

    def test_a_municipality_without_a_page_that_google_may_know_redirects_to_its_prefecture(self):
        red = self.redirects()
        for city in ("萩市", "下松市"):
            url = live_mod.city_url("yamaguchi", city)
            self.assertEqual(url in retired.KNOWN, url in red, city)                 # known to Google <-> redirected
            if url in red:
                self.assertEqual(red[url], "/live/yamaguchi/")
        for city in ("岩国市", "周南市"):
            self.assertNotIn(live_mod.city_url("yamaguchi", city), red, city)

    def test_every_redirect_target_is_a_page_in_the_sitemap_and_no_source_is_a_page_or_linked_or_a_target(self):
        red = self.redirects()
        sitemap = self.read("sitemap.xml")
        sources, targets = set(red), set(red.values())
        self.assertFalse(sources & targets)                                            # no chain
        for src, dst in red.items():
            self.assertIn(dst.strip("/") + "/index.html", self.files, (src, dst))
            self.assertIn(f"<loc>https://kuma-sokuho.com{dst}</loc>", sitemap, (src, dst))
            self.assertNotIn(src.strip("/") + "/index.html", self.files, src)
            self.assertNotIn(src, sitemap, src)
        for f in self.files:
            if f.endswith(".html"):
                body = self.read(f)
                for src in sources:
                    self.assertNotIn(f'href="{src}"', body, (f, src))

    def test_the_site_check_passes_with_the_municipalities_merged(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])

    def test_a_negative_case_a_municipality_missing_from_the_prefecture_page_would_be_caught(self):
        hub = self.read("live/yamaguchi/index.html").replace("萩市", "")
        table = hub.split("市町村別の記録", 1)[1].split("</table>", 1)[0]
        self.assertNotIn("萩市", table)

    def test_the_rule_can_be_rolled_back_all_pages_return_and_no_redirect_is_left(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(indexing, "KEEP_BY_RECORDS", live_mod.MIN_CITY_ROWS):
            files = build.render_site(self.raw, CFG, Path(tmp) / "s", release=True, prefs={"yamaguchi": _yamaguchi(self.CITIES)}, today=TODAY)
            self.assertTrue(all(self.rel(c) in files for c in self.CITIES))
            red = dict(re.findall(r"^Redirect 301 (\S+) (\S+)$", (Path(tmp) / "s" / ".htaccess").read_text(encoding="utf-8"), re.M))
            self.assertFalse([u for u in red if u in {live_mod.city_url("yamaguchi", c) for c in self.CITIES}])      # the four municipalities of the fixture have pages again, so nothing redirects for them


if __name__ == "__main__":
    unittest.main()
