"""Municipal RSS / Atom feeds: discovery on a top page, parsing of the three feed dialects, the daily collection and its fallbacks."""
import unittest
from datetime import datetime

from sokuhou import feedscan, run
from sokuhou.sources import kumalib

RSS2 = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>酒田市</title>
<item><title>クマの目撃について(注意)</title><link>https://city.example/a1.html</link><pubDate>Tue, 13 Oct 2026 09:00:00 +0900</pubDate><description>&lt;p&gt;市内で&lt;b&gt;クマ&lt;/b&gt;が目撃されました。&lt;/p&gt;</description></item>
<item><title>入札・契約</title><link>https://city.example/a2.html</link><pubDate>Mon, 12 Oct 2026 15:30:00 +0000</pubDate></item>
<item><title>リンクのない項目</title></item></channel></rss>"""

RDF = """<?xml version="1.0" encoding="UTF-8"?><rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="x"><title>秩父市</title></channel>
<item rdf:about="https://town.example/b1.html"><title>ごみ収集日の変更</title><link>https://town.example/b1.html</link><dc:date>2026-10-13T08:00:00+09:00</dc:date></item></rdf:RDF>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>大津市</title>
<entry><title>子育て講座のお知らせ</title><link href="https://otsu.example/c1.html"/><updated>2026-10-12T23:30:00Z</updated><summary>10月20日に開催します</summary></entry></feed>"""

TOP = """<html><head><link rel="alternate" type="application/rss+xml" title="新着" href="/rss_news.xml">
<link rel="stylesheet" href="/a.css"><link rel="alternate" type="application/atom+xml" href="https://other.example/x.xml"></head>
<body><a href="/rss/10/list1.xml">新着情報</a> <a href="/about/">案内</a> <a href="/info/">RSS配信について</a> <a href="/rss_news.xml">RSS</a></body></html>"""


class ParseTest(unittest.TestCase):
    def test_rss2_reads_title_link_date_and_a_clean_summary_and_leaves_out_an_item_without_a_link(self):
        f = feedscan.parse_feed(RSS2.encode("utf-8"))
        self.assertEqual(f["title"], "酒田市")
        self.assertEqual([(i["date"], i["title"]) for i in f["items"]], [("2026-10-13", "クマの目撃について(注意)"), ("2026-10-13", "入札・契約")])    # +0000 15:30 is 00:30 the next day in Japan
        self.assertEqual(f["items"][0]["summary"], "市内でクマが目撃されました。")

    def test_rdf_with_dublin_core_dates_and_atom_with_href_links(self):
        self.assertEqual(feedscan.parse_feed(RDF.encode("utf-8"))["items"], [{"title": "ごみ収集日の変更", "link": "https://town.example/b1.html", "date": "2026-10-13", "summary": ""}])
        a = feedscan.parse_feed(ATOM.encode("utf-8"))["items"][0]
        self.assertEqual((a["link"], a["date"], a["summary"]), ("https://otsu.example/c1.html", "2026-10-13", "10月20日に開催します"))

    def test_html_and_broken_xml_are_not_feeds(self):
        for body in (b"<html><body>404</body></html>", b"<rss><channel>", b"", "<?xml version='1.0'?><sitemap/>".encode()):
            with self.assertRaises(feedscan.FeedError):
                feedscan.parse_feed(body)

    def test_dates_in_the_formats_the_publishers_use(self):
        for text, want in (("Tue, 13 Oct 2026 09:00:00 +0900", "2026-10-13"), ("2026-10-13", "2026-10-13"), ("2026/10/13 10:00", "2026-10-13"),
                           ("2026-10-12T16:00:00Z", "2026-10-13"), ("昨日", None), ("", None), ("2026-02-31", None)):
            self.assertEqual(feedscan.parse_date(text), want, text)

    def test_bear_items_are_found_by_title_or_summary(self):
        self.assertTrue(feedscan.is_bear({"title": "クマの出没について", "summary": ""}))
        self.assertTrue(feedscan.is_bear({"title": "注意喚起", "summary": "ツキノワグマが目撃されました"}))
        self.assertFalse(feedscan.is_bear({"title": "ごみ収集日の変更", "summary": ""}))
        self.assertTrue(feedscan.is_bear({"title": "熊の出没にご注意ください", "summary": ""}))
        for place in ("令和8年熊本地震に係る特設ページ", "熊谷市の催し", "熊野古道の通行止め", "熊取町の広報"):
            self.assertFalse(feedscan.is_bear({"title": place, "summary": ""}), place)


class DiscoverTest(unittest.TestCase):
    def test_link_tags_come_first_then_links_that_look_like_feeds_on_the_same_host_only(self):
        got = feedscan.discover(TOP, "https://city.example/")
        self.assertEqual(got, ["https://city.example/rss_news.xml", "https://city.example/rss/10/list1.xml"])
        self.assertNotIn("https://other.example/x.xml", got)

    def test_scan_keeps_only_candidates_that_parse_and_reports_the_newest_date(self):
        pages = {"https://city.example/": TOP.encode(), "https://city.example/rss_news.xml": RSS2.encode("utf-8"),
                 "https://city.example/rss/10/list1.xml": b"<html>404</html>", "https://city.example/zzz": b""}
        got = feedscan.scan([{"name": "酒田市", "url": "https://city.example/"}, {"name": "ない市", "url": "https://none.example/"}], pages.__getitem__, sleep=lambda s: None)
        self.assertEqual(got, [{"name": "酒田市", "site": "https://city.example/", "feed": "https://city.example/rss_news.xml", "title": "酒田市", "items": 2, "newest": "2026-10-13"}])


NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)
REG = [{"id": "a", "name": "酒田市", "site": "https://c.example/", "feed": "https://c.example/rss.xml", "title": "酒田市"},
       {"id": "b", "name": "秩父市", "site": "https://town.example/", "feed": "https://t.example/rdf.xml", "title": ""}]


class CollectTest(unittest.TestCase):
    def test_only_recent_items_are_kept_newest_first_and_capped(self):
        many = "".join(f"<item><title>お知らせ{i}</title><link>https://c.example/{i}</link><pubDate>Tue, {13 - i % 13:02d} Oct 2026 09:00:00 +0900</pubDate></item>" for i in range(40))
        old = "<item><title>古い</title><link>https://c.example/old</link><pubDate>Mon, 01 Jun 2026 09:00:00 +0900</pubDate></item>"
        body = f'<rss version="2.0"><channel><title>x</title>{many}{old}</channel></rss>'.encode()
        out = feedscan.collect_feeds(REG[:1], lambda u: body, NOW, sleep=lambda s: None)
        items = out["feeds"][0]["items"]
        self.assertEqual(len(items), feedscan.KEEP_ITEMS)
        self.assertEqual([i["date"] for i in items], sorted((i["date"] for i in items), reverse=True))
        self.assertNotIn("古い", [i["title"] for i in items])

    def test_an_intranet_or_foreign_link_is_dropped_from_the_stored_items(self):
        self.assertTrue(feedscan.link_ok("https://www.town.shirataka.lg.jp/item/7345.htm", "https://www.town.shirataka.lg.jp/"))
        self.assertTrue(feedscan.link_ok("https://sub.city.example/a", "https://city.example/"))
        for bad in ("http://192.168.0.201/item/7345.htm#itemid7345", "http://localhost/x", "https://evil.example/a", "ftp://city.example/a", "https://notcity.example/a", ""):
            self.assertFalse(feedscan.link_ok(bad, "https://city.example/"), bad)
        body = ('<rss version="2.0"><channel><title>x</title><item><title>内部</title><link>http://192.168.0.201/a</link><pubDate>Tue, 13 Oct 2026 09:00:00 +0900</pubDate></item>'
                '<item><title>外部に出せる</title><link>https://c.example/b</link><pubDate>Tue, 13 Oct 2026 09:00:00 +0900</pubDate></item></channel></rss>').encode()
        out = feedscan.collect_feeds(REG[:1], lambda u: body, NOW, sleep=lambda s: None)
        self.assertEqual([i["title"] for i in out["feeds"][0]["items"]], ["外部に出せる"])

    def test_a_feed_that_fails_is_listed_without_items_and_merge_fills_it_from_the_last_run(self):
        good = RDF.encode("utf-8")

        def fetch(url):
            if "c.example" in url:
                raise OSError("down")
            return good
        new = feedscan.collect_feeds(REG, fetch, NOW, sleep=lambda s: None)
        self.assertEqual([(f["id"], f["ok"], len(f["items"])) for f in new["feeds"]], [("a", False, 0), ("b", True, 1)])
        old = {"feeds": [{**REG[0], "ok": True, "items": [{"title": "前回", "link": "https://c.example/1", "date": "2026-10-12", "summary": ""}]}]}
        merged = feedscan.merge_feeds(old, new)
        self.assertEqual([(f["id"], f["ok"], [i["title"] for i in f["items"]]) for f in merged["feeds"]], [("a", False, ["前回"]), ("b", True, ["ごみ収集日の変更"])])
        self.assertEqual(feedscan.merge_feeds(None, new), new)

    def test_most_feeds_failing_means_nothing_is_stored(self):
        with self.assertRaises(feedscan.FeedError):
            feedscan.collect_feeds(REG, lambda u: (_ for _ in ()).throw(OSError("offline")), NOW, sleep=lambda s: None)
        with self.assertRaises(feedscan.FeedError):
            feedscan.check_feeds(None, {"feeds": [{"ok": True, "items": []}]})

    def test_the_registry_in_the_repository_is_valid_and_the_source_is_registered(self):
        import json
        reg = json.loads(feedscan._registry_path().read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(reg), 50)
        self.assertEqual(len({r["id"] for r in reg}), len(reg))
        for r in reg:
            self.assertEqual(r["id"], feedscan.feed_id(r["feed"]))
            self.assertTrue(r["feed"].startswith("https://") and r["name"])
        self.assertIn("muni_feeds", [s.name for s in run.GROUPS["kuma"]])


if __name__ == "__main__":
    unittest.main()
