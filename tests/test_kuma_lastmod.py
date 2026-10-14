"""The bear site's sitemap: every page carries the day its own data last changed (not the build date), and static pages carry the day their text changed."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build, lastmod
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from tests.test_kuma_build import AKITA, CFG, COUNTS_META, HAVE_PYPDF, _counts_raw, _yamaguchi
from tests.test_kuma_cite import make_raw, miyagi_rows

TODAY = date(2026, 10, 7)
BUILD_DAY = date(2026, 10, 12)           # a build day later than every data date of the fixtures


def sitemap_dates(out: Path) -> dict[str, str]:
    s = (out / "sitemap.xml").read_text(encoding="utf-8")
    return {p: d for p, d in re.findall(r"<loc>https://kuma-sokuho.com([^<]*)</loc><lastmod>([^<]+)</lastmod>", s)}


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class SitemapDatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = make_raw()
        cls.prefs = {"miyagi": miyagi_rows(), "akita": AKITA, "yamaguchi": _yamaguchi(), "fukushima": _counts_raw()}
        cls.out = Path(cls.tmp.name) / "site"
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}), mock.patch.object(live_mod, "INDEX_CITY_ROWS", live_mod.MIN_CITY_ROWS):      # the fixtures' municipalities are all small: index them, so their dates can be checked
            cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs=cls.prefs, today=BUILD_DAY)
        cls.dates = sitemap_dates(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_page_of_the_site_is_in_the_sitemap_with_a_valid_date_and_the_checker_passes(self):
        urls = {"/" + f[: -len("index.html")] for f in self.files if f.endswith("index.html")}
        self.assertEqual(set(self.dates), urls)
        for d in self.dates.values():
            self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")
            date.fromisoformat(d)
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])

    def test_the_dates_are_not_all_the_build_date(self):
        data_pages = {u: d for u, d in self.dates.items() if not lastmod.is_static(u.strip("/") + "/index.html")}
        self.assertNotIn(BUILD_DAY.isoformat(), set(data_pages.values()))        # no data page is dated the build day (the data is older)
        self.assertGreater(len(set(self.dates.values())), 4)

    def test_ministry_pages_carry_the_ministrys_dates(self):
        d = build.prepare(self.raw)
        self.assertEqual(self.dates["/season/"], d["sight_updated"])
        self.assertEqual(self.dates["/ranking/sightings/"], d["sight_updated"])
        self.assertEqual(self.dates["/ranking/injuries/"], d["inj_updated"])
        self.assertEqual(self.dates["/trend/"], max(d["sight_updated"], d["inj_updated"]))
        self.assertEqual(self.dates["/emergency/"], d["emergency"][d["cur"]]["updated"])

    def test_a_municipal_page_carries_the_newest_record_of_its_own_source_or_city(self):
        self.assertEqual(self.dates["/live/miyagi/"], "2026-10-05")                 # the Oct-29 row of the fixture is after the source's as-of date: not shown, not dated
        self.assertEqual(self.dates["/live/akita/"], "2026-08-31")
        self.assertEqual(self.dates["/live/fukushima/"], "2026-10-03")             # a counts-only source: the latest date of its municipalities
        city = next(u for u in self.dates if re.fullmatch(r"/live/miyagi/m-[0-9a-f]{6}/", u))
        self.assertIn(self.dates[city], {"2026-10-05", "2026-10-04"})                # 大和町 (Oct 5) or 富谷市 (Oct 4)
        self.assertEqual(self.dates["/live/"], max(self.dates["/live/miyagi/"], self.dates["/live/akita/"], self.dates["/live/yamaguchi/"], self.dates["/live/fukushima/"]))
        self.assertEqual(self.dates["/map/"], self.dates["/live/"])

    def test_a_prefecture_page_is_dated_by_the_ministry_or_its_own_live_data_whichever_is_newer(self):
        d = build.prepare(self.raw)
        self.assertEqual(self.dates["/miyagi/"], max(lastmod.ministry_date(d), "2026-10-05"))
        self.assertEqual(self.dates["/tokyo/"], lastmod.ministry_date(d))

    def test_static_pages_without_a_stored_hash_get_the_build_day(self):
        for u in ("/guide/prepare/", "/about/", "/privacy/", "/contact/", "/notify/"):
            self.assertEqual(self.dates[u], BUILD_DAY.isoformat(), u)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class StaticHashTest(unittest.TestCase):
    def test_a_stored_matching_hash_keeps_its_date_and_a_changed_text_gets_the_build_day(self):
        raw = make_raw()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a"
            build.render_site(raw, CFG, out, release=True, prefs={"miyagi": miyagi_rows()}, today=BUILD_DAY)
            html = (out / "guide/prepare/index.html").read_text(encoding="utf-8")
            stored = {"guide/prepare/index.html": {"hash": lastmod.main_hash(html), "date": "2026-09-01"},
                      "guide/spray/index.html": {"hash": "0000000000000000", "date": "2026-09-02"}}
            pages = {f: (out / f).read_text(encoding="utf-8") for f in ("guide/prepare/index.html", "guide/spray/index.html", "index.html")}
            d = build.prepare(raw)
            dates, changed = lastmod.compute(pages, d, None, BUILD_DAY, stored)
            self.assertEqual(dates["/guide/prepare/"], "2026-09-01")
            self.assertEqual(dates["/guide/spray/"], BUILD_DAY.isoformat())
            self.assertEqual(changed, ["guide/spray/index.html"])

    def test_main_hash_ignores_the_menu_and_the_footer_and_spacing(self):
        a = "<nav>A</nav><main class='x'><p>本文  です</p></main><footer>F1</footer>"
        b = "<nav>B</nav><main class='x'><p>本文 です</p></main><footer>F2</footer>"
        c = "<nav>A</nav><main class='x'><p>本文が違います</p></main><footer>F1</footer>"
        self.assertEqual(lastmod.main_hash(a), lastmod.main_hash(b))
        self.assertNotEqual(lastmod.main_hash(a), lastmod.main_hash(c))

    def test_update_static_stores_hashes_and_dates_only_for_changed_pages(self):
        pages = {"guide/a/index.html": "<main>A</main>", "guide/b/index.html": "<main>B</main>", "live/index.html": "<main>X</main>", "about/index.html": "<main>Y</main>"}
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "s.json"
            self.assertEqual(lastmod.update_static(pages, date(2026, 10, 1), f), ["about/index.html", "guide/a/index.html", "guide/b/index.html"])
            first = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(set(first), {"about/index.html", "guide/a/index.html", "guide/b/index.html"})       # live/ is not a static page
            pages["guide/b/index.html"] = "<main>B changed</main>"
            self.assertEqual(lastmod.update_static(pages, date(2026, 10, 5), f), ["guide/b/index.html"])
            second = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(second["guide/a/index.html"]["date"], "2026-10-01")
            self.assertEqual(second["guide/b/index.html"]["date"], "2026-10-05")

    def test_apply_rewrites_only_the_known_pages(self):
        sm = '<urlset><url><loc>https://x.example/a/</loc><lastmod>2026-01-01</lastmod></url>\n<url><loc>https://x.example/b/</loc><lastmod>2026-01-01</lastmod></url>\n</urlset>'
        got = lastmod.apply(sm, {"/a/": "2026-02-02"}, "https://x.example")
        self.assertIn("<loc>https://x.example/a/</loc><lastmod>2026-02-02</lastmod>", got)
        self.assertIn("<loc>https://x.example/b/</loc><lastmod>2026-01-01</lastmod>", got)

    def test_the_committed_file_covers_the_static_pages_and_holds_valid_dates(self):
        stored = json.loads(lastmod.STATIC_FILE.read_text(encoding="utf-8"))
        for rel, rec in stored.items():
            self.assertTrue(lastmod.is_static(rel), rel)
            self.assertRegex(rec["hash"], r"^[0-9a-f]{16}$")
            date.fromisoformat(rec["date"])
        for rel in ("about/index.html", "privacy/index.html", "contact/index.html", "notify/index.html", "guide/index.html", "guide/prepare/index.html"):
            self.assertIn(rel, stored)


class IsStaticTest(unittest.TestCase):
    def test_paths(self):
        for rel in ("about/index.html", "guide/spray/index.html", "guide/index.html", "goods/index.html"):
            self.assertTrue(lastmod.is_static(rel), rel)
        for rel in ("live/index.html", "index.html", "season/index.html", "digest/2026-W15/index.html", "akita/index.html"):
            self.assertFalse(lastmod.is_static(rel), rel)


if __name__ == "__main__":
    unittest.main()
