"""/notices/: the bear notices of the municipalities' own RSS feeds."""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build, notices
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from tests.test_kuma_build import CFG, COUNTS_META, HAVE_PYPDF, _counts_raw, _yamaguchi
from tests.test_kuma_cite import make_raw

TODAY = date(2026, 10, 13)


def item(title, link, d, summary=""):
    return {"title": title, "link": link, "date": d, "summary": summary}


FEEDS = {"fetched_at": "2026-10-13T06:30:00+09:00", "feeds": [
    {"id": "a", "name": "秩父市", "site": "https://c.example/", "feed": "https://c.example/rss", "title": "", "ok": True,
     "items": [item("クマ目撃等情報(荒川地区)", "https://c.example/item/1.html#itemid1", "2026-10-09"), item("ごみ収集日の変更", "https://c.example/item/2.html", "2026-10-12"),
               item("クマ対策の入札公告", "https://c.example/item/3.html", "2026-10-11")]},
    {"id": "b", "name": "秩父市", "site": "https://c.example/", "feed": "https://c.example/rss2", "title": "", "ok": True,
     "items": [item("クマ目撃等情報(荒川地区)", "https://c.example/item/1.html", "2026-10-09")]},
    {"id": "c", "name": "新潟県庁", "site": "https://p.example/", "feed": "https://p.example/rss", "title": "", "ok": True,
     "items": [item("ツキノワグマの出没にご注意ください", "https://p.example/a", "2026-10-13"), item("令和8年熊本地震の支援", "https://p.example/b", "2026-10-13"),
               item("クマ春期管理捕獲効果検証業務委託(プロポーザル)", "https://p.example/c", "2026-10-09"), item("日付なしの熊の話", "https://p.example/d", None)]},
    {"id": "d", "name": "ない市", "site": "https://n.example/", "feed": "https://n.example/rss", "title": "", "ok": False,
     "items": [item("クマが出ました", "https://n.example/a", "2026-10-13")]}]}


class SelectTest(unittest.TestCase):
    def test_only_bear_notices_once_each_newest_first_without_tenders_or_place_names(self):
        got = [(x["date"], x["publisher"], x["title"]) for x in notices.bear_notices(FEEDS)]
        self.assertEqual(got, [("2026-10-13", "新潟県庁", "ツキノワグマの出没にご注意ください"), ("2026-10-09", "秩父市", "クマ目撃等情報(荒川地区)")])

    def test_a_feed_that_could_not_be_read_today_adds_nothing_and_no_feeds_is_no_notices(self):
        self.assertNotIn("ない市", {x["publisher"] for x in notices.bear_notices(FEEDS)})
        self.assertEqual(notices.bear_notices(None), [])
        self.assertEqual(notices.bear_notices({"feeds": []}), [])

    def test_the_lead_counts_what_was_read(self):
        self.assertEqual(notices.feed_counts(FEEDS), (3, 2))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.empty = Path(cls.tmp.name) / "empty"
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            cls.files = build.render_site(make_raw(), CFG, cls.out, release=True, prefs={"fukushima": _counts_raw(), "yamaguchi": _yamaguchi()}, today=TODAY, feeds=FEEDS)
            build.render_site(make_raw(), CFG, cls.empty, release=True, prefs={"fukushima": _counts_raw(), "yamaguchi": _yamaguchi()}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel, root=None):
        return ((root or self.out) / rel).read_text(encoding="utf-8")

    def test_the_page_lists_the_notices_with_links_to_the_publishers_and_passes_the_checker(self):
        html = self.read("notices/index.html")
        self.assertIn("2件", re.sub(r"<[^>]+>", "", html))
        self.assertIn('<a href="https://p.example/a" rel="noopener" target="_blank">ツキノワグマの出没にご注意ください</a>', html)
        self.assertIn("10月13日・新潟県庁", html)
        self.assertNotIn("熊本地震", html)
        self.assertNotIn("入札", re.sub(r"入札や委託などのお知らせは、載せていません", "", html))
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])

    def test_the_home_and_news_pages_link_to_it_and_the_sitemap_date_is_the_newest_notice(self):
        self.assertIn('href="/notices/"', self.read("index.html"))
        self.assertIn('href="/notices/"', self.read("news/index.html"))
        self.assertRegex(self.read("sitemap.xml"), r"<loc>https://kuma-sokuho.com/notices/</loc><lastmod>2026-10-13</lastmod>")

    def test_without_feeds_there_is_no_page_and_no_link(self):
        self.assertNotIn("notices/index.html", build.render_site(make_raw(), CFG, Path(self.tmp.name) / "e2", release=True, today=TODAY))
        self.assertNotIn('href="/notices/"', self.read("index.html", self.empty))
        self.assertNotIn('href="/notices/"', self.read("news/index.html", self.empty))


if __name__ == "__main__":
    unittest.main()
