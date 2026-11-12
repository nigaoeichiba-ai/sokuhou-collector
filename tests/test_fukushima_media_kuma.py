"""Fukushima: what Fukushima City's page and Fukushima TV both hold (the prefecture's own data is not read at all).

Negative tests: nothing from the prefecture is fetched, a sighting that only one medium holds is never stored, a second line is needed for a second sighting."""
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from sites.kuma import build
from sites.kuma import live as live_mod
from sokuhou import run
from sokuhou.sources import corroborated as co
from sokuhou.sources import fukushima_media_kuma as fm
from sokuhou.sources import kumalib
from tests.test_kuma_build import CFG, HAVE_PYPDF, _yamaguchi
from tests.test_kuma_cite import make_raw

TODAY = date(2026, 11, 12)
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=kumalib.JST)
CITY_PAGE = """<html><table><tr><th>No</th><th>日時</th><th>場所</th><th>備考</th></tr>
<tr><td>140</td><td>令和8年11月1日(日曜日) 6時00分</td><td>飯坂町字A地内 (獣マップへリンク)</td><td></td></tr>
<tr><td>139</td><td>令和8年10月20日(火曜日) 6時00分</td><td>松川町字B地内 (獣マップへリンク)</td><td></td></tr>
<tr><td>138</td><td>令和8年10月20日(火曜日) 9時00分</td><td>平石字C地内 (獣マップへリンク)</td><td>クマの足跡</td></tr>
<tr><td>137</td><td>令和8年10月19日(月曜日) 9時00分</td><td>茂庭字D地内 (獣マップへリンク)</td><td></td></tr>
<tr><td>120</td><td>令和8年6月3日(水曜日) 9時00分</td><td>桜本字E地内 (獣マップへリンク)</td><td></td></tr></table></html>"""
DAY_LIST = '<html><a href="https://www.fukushima-tv.co.jp/localnews/2026/11/2026111100000001.html"><span>【熊出没】10月20日(火)福島県のクマ目撃情報</span></a></html>'
# one story of 10-20 with ONE line for 福島市, plus a municipality only the television has
STORY = """<html><body><div>【熊出没】10月20日（火）福島県のクマ目撃情報 福島市など</div>
<p>【福島市】</p><p>・松川町 午前6時ごろ 道路上のクマ1頭</p>
<p>【白河市】</p><p>・関辺 午前7時ごろ クマ1頭</p></body></html>"""


def make_fetch(log):
    def fetch(url):
        log.append(url)
        if url == co.FUKUSHIMA_CITY_PAGE:
            return CITY_PAGE.encode("utf-8")
        if url.endswith("/2026/11/11/"):
            return DAY_LIST.encode("utf-8")
        if url.endswith("2026111100000001.html"):
            return STORY.encode("utf-8")
        return b"<html></html>"
    return fetch


def collect(log=None):
    return fm.collect(fetch=make_fetch([] if log is None else log), sleep=lambda s: None, now=NOW)


class PairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = []
        cls.out = collect(cls.log)

    def test_only_the_sighting_both_media_hold_is_stored_with_its_place(self):
        recs = self.out["corroborated"]
        self.assertEqual(len(recs), 1)
        self.assertEqual((recs[0]["observed_at"], recs[0]["city"], recs[0]["place"]), ("2026-10-20", "福島市", "松川町字B地内"))

    def test_a_sighting_only_one_medium_holds_is_not_stored(self):
        places = {r["place"] for r in self.out["corroborated"]}
        self.assertNotIn("飯坂町字A地内", places)      # the city page only (no television line that day)
        self.assertNotIn("茂庭字D地内", places)
        self.assertNotIn("桜本字E地内", places)        # before the television's period
        self.assertNotIn("白河市", {r["city"] for r in self.out["corroborated"]})        # the television only
        self.assertEqual(set(self.out["municipalities"]), {"福島市"})
        self.assertEqual(self.out["total_fy"], 1)

    def test_two_sightings_on_one_day_need_two_lines_on_each_side(self):
        city = co.parse_fukushima_city(CITY_PAGE)
        tv = co.parse_ftv_article(STORY, "https://www.fukushima-tv.co.jp/localnews/2026/11/2026111100000001.html")
        kept, st = fm.pair(city, tv)
        self.assertEqual(len(kept), 1)
        self.assertEqual((st["city_only"], st["tv_only"]), (4, 1))
        kept2, _ = fm.pair(city, tv + [dict(tv[0])])      # a second television line for the same city and day confirms the second city row
        self.assertEqual(len(kept2), 2)

    def test_the_prefectures_data_is_never_asked_for(self):
        for u in self.log:
            host = urlparse(u).hostname or ""
            self.assertNotIn("pref.fukushima", host, u)
            self.assertNotIn("arcgis", host, u)
            self.assertTrue(host.endswith(("city.fukushima.fukushima.jp", "fukushima-tv.co.jp")), u)
        src = Path(fm.__file__).read_text(encoding="utf-8")
        self.assertNotIn("arcgis_counts", src)
        self.assertNotIn("WEBMAP", src)

    def test_the_stored_file_has_the_counts_shape_and_only_the_five_fields(self):
        self.assertEqual((self.out["mode"], self.out["source"]), ("counts", "fukushima_media"))
        self.assertEqual({tuple(sorted(r)) for r in self.out["corroborated"]}, {("city", "count", "kind", "observed_at", "place")})
        run.check_counts_bear(None, self.out)
        self.assertNotIn("pref.fukushima", str(self.out["source_page"]))

    def test_nothing_in_common_stores_nothing(self):
        def fetch(url):
            return CITY_PAGE.encode("utf-8") if url == co.FUKUSHIMA_CITY_PAGE else b"<html></html>"
        with self.assertRaises(fm.FukushimaMediaSourceError):
            fm.collect(fetch=fetch, sleep=lambda s: None, now=NOW)

    def test_an_unreadable_city_page_stores_nothing(self):
        def fetch(url):
            raise OSError("down")
        with self.assertRaises(OSError):
            fm.collect(fetch=fetch, sleep=lambda s: None, now=NOW)

    def test_the_confirmed_ones_of_earlier_runs_stay_and_the_year_before_does_not(self):
        old = fm.package([{"observed_at": "2026-09-01", "city": "福島市", "place": "X", "kind": "目撃", "count": None},
                          {"observed_at": "2026-02-01", "city": "福島市", "place": "Y", "kind": "目撃", "count": None}], date(2026, 10, 1))
        merged = fm.accumulate(old, self.out)
        self.assertEqual(sorted(r["place"] for r in merged["corroborated"]), sorted(["X", self.out["corroborated"][0]["place"]]))
        self.assertEqual(merged["total_fy"], 2)
        self.assertEqual(fm.accumulate(None, self.out), self.out)

    def test_registered_in_the_kuma_group_with_the_counts_check_and_no_licence(self):
        src = {s.name: s for s in run.GROUPS["kuma"]}["fukushima_media_kuma"]
        self.assertIs(src.check, run.check_counts_bear)
        meta = live_mod.LIVE_SOURCES["fukushima_media"]
        self.assertEqual(meta["pref"], "福島")
        self.assertNotIn("license", meta)


@unittest.skipUnless(HAVE_PYPDF, "needs the PDF fixtures")
class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "s"
        cls.files = build.render_site(make_raw(), CFG, cls.out, release=True, prefs={"fukushima_media": collect(), "yamaguchi": _yamaguchi()}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def text(self, rel):
        return re.sub(r"<[^>]+>", " ", (self.out / rel).read_text(encoding="utf-8"))

    def test_the_count_page_is_built_and_says_the_prefecture_data_is_not_used(self):
        self.assertIn("live/fukushima/index.html", self.files)
        t = self.text("live/fukushima/index.html")
        self.assertIn("県の許可が得られていない", t)
        self.assertIn("別の出どころで2つの公開情報が一致した目撃だけ", t)
        self.assertIn("松川町字B地内", t)
        self.assertNotIn("福島県が公表している件数", t)
        self.assertNotIn("福島県が公表している最新の目撃情報", t)

    def test_no_source_or_link_is_named_for_the_confirmed_sightings(self):
        html = (self.out / "live/fukushima/index.html").read_text(encoding="utf-8")
        for word in ("fukushima-tv", "city.fukushima.fukushima.jp", "arcgis", "pref.fukushima"):
            self.assertNotIn(word, html)
        self.assertNotIn("福島テレビ", self.text("live/fukushima/index.html").split("場所まで確認できた最新の目撃")[1])

    def test_the_prefecture_page_keeps_the_refusal_and_links_to_the_confirmed_ones(self):
        t = self.text("fukushima/index.html")
        self.assertIn("福島県は、県の許可が得られていないため、県が公表しているクマの目撃情報(市町村別の件数など)を載せていません", t)
        self.assertIn("複数の公開情報で一致を確認できた目撃", t)
        self.assertNotIn("福島県が公表している件数", t)
        self.assertIn('href="/live/fukushima/"', (self.out / "fukushima/index.html").read_text(encoding="utf-8"))

    def test_the_site_checker_passes(self):
        from sokuhou import sitecheck
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])


if __name__ == "__main__":
    unittest.main()
