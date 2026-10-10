"""/search/ of the bear site: a table of every municipality of the stored sources, narrowed by a small script while the visitor types.

The rows are checked against counts written by hand from the fixtures (the cite tests' Miyagi rows, the Yamaguchi rows and a counts-only source).
"""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build, finder
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from sokuhou.sources import kumalib
from tests.test_kuma_build import CFG, COUNTS_META, HAVE_PYPDF, _counts_raw, _yamaguchi
from tests.test_kuma_cite import make_raw, miyagi_rows

TODAY = date(2026, 10, 7)
ASSETS = Path(__file__).resolve().parents[1] / "sites" / "kuma" / "assets"


def counts_with_a_mountain():
    """Fukushima's counts plus a place name that is not a municipality (as Nara reports 大台ヶ原)."""
    rows = [{"observed_at": "2026-10-03", "city": "福島市"}, {"observed_at": "2026-09-20", "city": "福島市"}, {"observed_at": "2026-09-02", "city": "会津若松市"},
            {"observed_at": "2026-08-15", "city": "福島市"}, {"observed_at": "2026-09-30", "city": "大台ヶ原"}]
    return kumalib.package_counts(source="fukushima", credit="出典:福島県", update_note="県が更新します", as_of=date(2026, 10, 5), rows=rows,
                                  page="https://www.pref.fukushima.lg.jp/x.html", files=["https://www.pref.fukushima.lg.jp/x.html"])


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.split("<main", 1)[1].split("</main>", 1)[0]))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class FinderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = make_raw()
        cls.prefs = {"miyagi": miyagi_rows(), "yamaguchi": _yamaguchi(), "fukushima": counts_with_a_mountain()}
        cls.out = Path(cls.tmp.name) / "site"
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs=cls.prefs, today=TODAY)
            d = build.prepare(cls.raw)
            d["live_prefs"], d["live_counts"] = build.prepare_prefs(cls.prefs), live_mod.prepare_counts(cls.prefs)
            cls.lv = live_mod.prepare_live(d, TODAY)
            cls.d = d
        cls.html = (cls.out / "search/index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_page_exists_is_linked_and_passes_the_site_checker(self):
        self.assertIn("search/index.html", self.files)
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])
        for rel in ("index.html", "live/index.html"):
            self.assertIn('href="/search/"', (self.out / rel).read_text(encoding="utf-8"), rel)
        self.assertIn("finder.js", "".join(self.files))

    def test_the_rows_are_the_hand_counted_municipalities_newest_first(self):
        got = [(m["name"], m["pref"], m["mode"], m["total"], m["last30"], m["latest"]) for m in finder.municipalities(self.d, self.lv)]
        self.assertEqual(got, [
            ("萩市", "山口県", "records", 1, 1, "2026-10-06"),
            ("大和町", "宮城県", "records", 4, 1, "2026-10-05"),          # 3 in May + 1 in October
            ("富谷市", "宮城県", "records", 3, 1, "2026-10-04"),          # 2 in July + 1 in October
            ("岩国市", "山口県", "records", 4, 3, "2026-10-03"),          # Oct 3, Sep 30, Sep 20 are inside the last 30 days; 1 June is not
            ("福島市", "福島県", "counts", 3, None, "2026-10-03"),
            ("阿武町", "山口県", "records", 1, 1, "2026-09-15"),
            ("会津若松市", "福島県", "counts", 1, None, "2026-09-02"),
        ])

    def test_a_place_that_is_not_a_municipality_is_left_out(self):
        self.assertNotIn("大台ヶ原", self.html)
        self.assertIn("市町村ではない地名(山の名前など)で報告された分は、この表に入れていません", text_of(self.html))

    def test_the_table_has_one_searchable_row_per_municipality_and_the_right_links(self):
        rows = re.findall(r'<tr data-q="([^"]*)"><td><a href="([^"]*)">([^<]*)</a></td><td>([^<]*)</td><td>([^<]*)</td><td>([^<]*)</td><td>([^<]*)</td><td>([^<]*)</td></tr>', self.html)
        self.assertEqual(len(rows), 7)
        by_name = {r[2]: r for r in rows}
        self.assertEqual(by_name["大和町"][0], "大和町 宮城県")
        self.assertRegex(by_name["大和町"][1], r"^/live/miyagi/m-[0-9a-f]{6}/$")          # 4 records: its own page
        self.assertEqual(by_name["萩市"][1], "/live/yamaguchi/")                          # 1 record: the prefecture's page
        self.assertEqual(by_name["福島市"][1], "/live/fukushima/")
        self.assertEqual(by_name["福島市"][5], "-")                                      # counts only: no 30-day figure
        self.assertEqual(by_name["岩国市"][5], "3")
        self.assertIn("10月3日(4日前)", by_name["岩国市"][6] + by_name["福島市"][6])
        self.assertEqual(by_name["福島市"][7], "件数のみ")
        for _, href, *_ in rows:
            self.assertIn(href.strip("/") + "/index.html", self.files)

    def test_the_lead_counts_the_rows_and_says_not_listed_does_not_mean_safe(self):
        text = text_of(self.html)
        self.assertIn("7の市町村について", text)
        self.assertIn("「出没がない」「安全」という意味ではなく", text)
        self.assertIn('<form id="finder-tools" role="search" hidden>', self.html)         # hidden until the script runs: without it the page is just the list
        self.assertIn('id="finder-table"', self.html)

    def test_the_script_only_reads_text_and_toggles_rows(self):
        js = (ASSETS / "finder.js").read_text(encoding="utf-8")
        for bad in ("innerHTML", "outerHTML", "eval(", "document.write", "insertAdjacentHTML", "XMLHttpRequest", "fetch("):
            self.assertNotIn(bad, js)
        self.assertIn("tr.hidden", js)
        self.assertIn("NFKC", js)


class WithoutLiveDataTest(unittest.TestCase):
    @unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
    def test_no_live_source_means_no_search_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "n"
            files = build.render_site(make_raw(), CFG, out, release=True, today=TODAY)
            self.assertNotIn("search/index.html", files)
            self.assertNotIn('href="/search/"', (out / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
