"""北海道(ひぐまっぷに参加する市町村): the public maps' lists are counted by month, one municipality at a time."""
import json
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from sites.kuma import build
from sites.kuma import live as live_mod
from sokuhou import run
from sokuhou.sources import higumap_kuma as kuma
from sokuhou import sitecheck
from sokuhou.sources import env_kuma, kumalib, sorachi_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data

NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)


def ms(y, m, d):
    return int(datetime(y, m, d, 0, 0, tzinfo=kumalib.JST).timestamp() * 1000)


def reports(*days, undated=0):
    return {"list": [{"id": i, "lat": 43.1, "lng": 142.3, "foundDt": ms(*d), "witnessFlg": 1, "captureFlg": 0, "popupLabel": "目撃"} for i, d in enumerate(days)]
            + [{"id": 900 + i, "lat": 43.1, "lng": 142.3, "foundDt": None, "witnessFlg": 1, "captureFlg": 0, "popupLabel": ""} for i in range(undated)]}


def page(cid, name):
    return f'<html><div id="map" data-city-id="{cid}" data-fiscal-year="2026" data-city-name="{name}"></div></html>'


SITE = {
    "/recent/pmCityList": json.dumps(["11", "12", "13", "14", "15"]),
    "/map/11/2026": page(1, "旭川市"), "/map/reportsJson?cityId=1&fiscalYear=2026": json.dumps(reports((2026, 4, 3), (2026, 4, 9), (2026, 10, 11), (2026, 6, 1))),
    "/map/12/2026": page(2, "鹿部町"), "/map/reportsJson?cityId=2&fiscalYear=2026": json.dumps(reports((2026, 10, 1), (2026, 10, 1))),
    "/map/13/2026": page(3, "美唄市"), "/map/reportsJson?cityId=3&fiscalYear=2026": json.dumps(reports((2026, 8, 26))),          # counted by sorachi_kuma
    "/map/14/2026": page(4, "南富良野町"), "/map/reportsJson?cityId=4&fiscalYear=2026": json.dumps(reports((2026, 5, 5), undated=6)),      # mostly without a date
    "/map/15/2026": page(5, "弟子屈町"), "/map/reportsJson?cityId=5&fiscalYear=2026": json.dumps(reports()),
}


def fetch_from(site, log=None):
    def fetch(url):
        if log is not None:
            log.append(url)
        return site[url.removeprefix(kuma.ROOT)].encode("utf-8")
    return fetch


def collect(site=None, **kw):
    with mock.patch.object(kuma, "MIN_ROWS", 1):
        return kuma.collect(NOW, fetch_fn=fetch_from(site or SITE, kw.pop("log", None)), pause=lambda: None, **kw)


class HigumapKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_each_municipality_is_counted_by_month_from_its_own_list(self):
        m = self.out["municipalities"]
        self.assertEqual(m["旭川市"], {"monthly": {"R08": {"4": 2, "6": 1, "10": 1}}, "latest": "2026-10-11"})
        self.assertEqual(m["鹿部町"]["monthly"]["R08"], {"10": 2})
        self.assertEqual((self.out["mode"], self.out["source"], self.out["fy_current"], self.out["total_fy"], self.out["as_of"]), ("counts", "higumap", "R08", 6, "2026-10-11"))

    def test_the_four_towns_sorachi_already_covers_and_the_undated_or_empty_ones_are_left_out(self):
        self.assertEqual(sorted(self.out["municipalities"]), ["旭川市", "鹿部町"])

    def test_a_municipality_whose_own_publication_could_not_be_confirmed_is_left_out(self):
        site = {**SITE, "/map/12/2026": page(2, "北斗市")}
        self.assertEqual(sorted(collect(site)["municipalities"]), ["旭川市"])

    def test_only_dates_are_kept_no_position_and_no_text(self):
        flat = json.dumps(self.out, ensure_ascii=False)
        for word in ('"lat"', '"lng"', "popupLabel", "witnessFlg", "sightings", "places"):
            self.assertNotIn(word, flat)
        run.check_counts_bear(None, self.out)

    def test_every_request_goes_to_the_public_pages_of_the_one_host(self):
        log = []
        collect(log=log)
        self.assertTrue(all(u.startswith("https://higumap.info/") for u in log))
        self.assertEqual(sum("reportsJson" in u for u in log), 4)       # the town sorachi covers is not asked for its list

    def test_a_changed_page_or_list_stores_nothing(self):
        with self.assertRaises(kuma.HigumapKumaSourceError):
            collect({**SITE, "/map/11/2026": "<html>no map</html>"})
        with self.assertRaises(kuma.HigumapKumaSourceError):
            collect({**SITE, "/map/reportsJson?cityId=1&fiscalYear=2026": json.dumps({"rows": []})})
        with self.assertRaises(kuma.HigumapKumaSourceError):
            collect({**SITE, "/recent/pmCityList": json.dumps({"a": 1})})
        with self.assertRaises(kuma.HigumapKumaSourceError):
            with mock.patch.object(kuma, "MIN_ROWS", 100):
                kuma.collect(NOW, fetch_fn=fetch_from(SITE), pause=lambda: None)

    def test_registration_and_the_page_scope(self):
        src = {s.name: s for s in run.GROUPS["kuma"]}["higumap_kuma"]
        self.assertIs(src.check, run.check_counts_bear)
        meta = live_mod.LIVE_SOURCES["higumap"]
        self.assertEqual(meta["pref"], "北海道")
        self.assertNotIn("license", meta)           # counts only: never in the CSV
        self.assertTrue(meta["scope"].endswith("のみ"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class HokkaidoPageTest(unittest.TestCase):
    """Hokkaido has a record source (the Sorachi bureau) and this counts-only one: one page, the counts as a section of it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        raw = raw_data()
        raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        prefs = {"sorachi": sorachi_kuma.parse_page((FIX / "sorachi_kuma.html").read_bytes()), "higumap": collect()}
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(raw, CFG, cls.out, release=True, prefs=prefs, today=date(2026, 10, 13))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def text(self, rel):
        return re.sub(r"<[^>]+>", " ", (self.out / rel).read_text(encoding="utf-8"))

    def test_the_record_page_carries_the_counts_with_their_source_and_the_scope_in_the_title(self):
        html = (self.out / "live/hokkaido/index.html").read_text(encoding="utf-8")
        self.assertIn("ひぐまっぷ", re.search(r"<title>(.*?)</title>", html).group(1))
        flat = self.text("live/hokkaido/index.html")
        for word in ("旭川市", "鹿部町", "北海道の市町村(ひぐまっぷ)の件数", "作成・保証したものではありません"):
            self.assertIn(word, flat)
        self.assertNotIn("南富良野町", flat)

    def test_there_is_no_second_page_for_the_same_address_and_the_ministrys_page_links_to_it(self):
        self.assertEqual([f for f in self.files if f.startswith("live/hokkaido/") and f.endswith("index.html") and f.count("/") == 2], ["live/hokkaido/index.html"])
        self.assertIn("北海道の市町村(ひぐまっぷ)が公表している件数", self.text("hokkaido/index.html"))

    def test_the_site_checker_passes(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])

    def test_the_page_says_why_hokkaido_and_chiba_have_no_ministry_count(self):
        self.assertIn("道全体の出没件数をまとめた表を、道のサイトに載せていません", self.text("hokkaido/index.html"))
        self.assertIn("千葉県を除く本州と四国の一部地域", self.text("chiba/index.html"))


if __name__ == "__main__":
    unittest.main()
