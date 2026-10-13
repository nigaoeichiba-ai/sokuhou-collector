"""atomou: the RSS entrance for the daily research (sites/atomou/rssfeed.py).  Offline: feeds are fixtures, nothing is fetched.  A headline is only a clue: it is matched to a finished day only when it
is about it and not older than it, a feed that fails or that robots.txt forbids is skipped and named, and the list of feeds is well formed."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import rssfeed  # noqa: E402

RSS2 = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>x</title>
<item><title>ドジャース、ブルワーズに惜敗 第1戦は1－2</title><link>https://news.example.jp/a1</link><pubDate>Mon, 12 Oct 2026 05:30:00 +0900</pubDate><description>&lt;p&gt;リーグ優勝決定シリーズ&lt;/p&gt;</description></item>
<item><title>http only link</title><link>http://news.example.jp/a2</link><pubDate>Mon, 12 Oct 2026 05:30:00 +0900</pubDate></item>
<item><title></title><link>https://news.example.jp/a3</link></item>
<item><title>no link</title></item></channel></rss>"""
RDF = """<?xml version="1.0" encoding="UTF-8"?><rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">
<item><title>F1シンガポールGP フェルスタッペンが優勝</title><link>https://www.example.com/f1</link><dc:date>2026-10-11T22:50:00+09:00</dc:date></item></rdf:RDF>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>柔道世界選手権 日本が混合団体で優勝</title><link href="https://atom.example.org/j"/><updated>2026-10-12T08:33:00+09:00</updated></entry></feed>"""
SRC = {"id": "t", "company": "テスト社"}


class Parsing(unittest.TestCase):
    def test_the_three_kinds_of_feed_are_read_and_a_bad_item_is_dropped(self):
        a = rssfeed.parse_feed(RSS2, SRC)
        self.assertEqual([x["link"] for x in a], ["https://news.example.jp/a1", "https://news.example.jp/a2"])      # a plain http link is lifted to https; an empty title and a missing link are dropped
        self.assertEqual(a[0]["published"], "2026-10-12T05:30:00+09:00")
        self.assertNotIn("<p>", a[0]["summary"])
        self.assertEqual(rssfeed.parse_feed(RDF, SRC)[0]["published"], "2026-10-11T22:50:00+09:00")
        self.assertEqual(rssfeed.parse_feed(ATOM, SRC)[0]["link"], "https://atom.example.org/j")
        self.assertEqual(rssfeed.parse_feed("<rss><broken", SRC), [])
        self.assertEqual(rssfeed.parse_feed('<!DOCTYPE x [<!ENTITY a "b">]><rss><channel/></rss>', SRC), [])

    def test_a_feed_that_fails_or_is_forbidden_is_skipped_and_named_the_rest_is_kept(self):
        srcs = [{"id": "ok", "company": "A", "url": "https://a.example/rss"}, {"id": "down", "company": "B", "url": "https://b.example/rss"}, {"id": "no", "company": "C", "url": "https://c.example/rss"}]

        def get(u):
            if "b.example" in u:
                raise OSError("down")
            return RSS2
        items, failed = rssfeed.fetch_all(srcs, get=get, robots=lambda u: "c.example" not in u)
        self.assertEqual({i["source"] for i in items}, {"ok"})
        self.assertEqual(sorted(f[0] for f in failed), ["down", "no"])

    def test_robots_txt_is_asked(self):
        self.assertFalse(rssfeed.allowed("https://x.example/feed", fetch_text=lambda u: "User-agent: *\nDisallow: /feed"))
        self.assertTrue(rssfeed.allowed("https://x.example/feed", fetch_text=lambda u: "User-agent: *\nDisallow: /private"))
        self.assertTrue(rssfeed.allowed("https://x.example/feed", fetch_text=lambda u: (_ for _ in ()).throw(OSError("no robots.txt"))))

    def test_the_cache_keeps_two_weeks_and_never_twice_the_same_link(self):
        old = [{"link": "https://a/1", "published": "2026-09-01T00:00:00+09:00"}, {"link": "https://a/2", "published": "2026-10-10T00:00:00+09:00"}]
        new = [{"link": "https://a/2", "published": "2026-10-10T00:00:00+09:00"}, {"link": "https://a/3", "published": "2026-10-13T00:00:00+09:00"}]
        got = rssfeed.merge(old, new, date(2026, 10, 13))
        self.assertEqual(sorted(x["link"] for x in got), ["https://a/2", "https://a/3"])


ROW = {"title": "MLB ナ・リーグ優勝決定シリーズ 第1戦 ドジャース 対 ブルワーズ", "date": "2026-10-11", "date_end": None}
ITEMS = [
    {"source": "a", "company": "A社", "title": "ドジャース、ブルワーズに惜敗 第1戦は1－2", "link": "https://a/1", "published": "2026-10-12T05:30:00+09:00", "summary": "リーグ優勝決定シリーズ"},
    {"source": "b", "company": "B社", "title": "ブルワーズが先勝 ドジャースは打線が沈黙", "link": "https://b/1", "published": "2026-10-12T06:10:00+09:00", "summary": ""},
    {"source": "b2", "company": "B社", "title": "ブルワーズ制す ドジャース敗れる 第1戦", "link": "https://b/2", "published": "2026-10-12T07:00:00+09:00", "summary": ""},
    {"source": "c", "company": "C社", "title": "ドジャース、ブルワーズ戦に向け調整 第1戦の先発は", "link": "https://c/1", "published": "2026-10-10T11:00:00+09:00", "summary": ""},   # before the day: a preview
    {"source": "d", "company": "D社", "title": "気象予報士試験 合格発表", "link": "https://d/1", "published": "2026-10-12T09:00:00+09:00", "summary": ""},   # about something else
]


class Matching(unittest.TestCase):
    def test_a_result_headline_is_matched_a_preview_and_a_different_subject_are_not(self):
        got = rssfeed.match([ROW], ITEMS)[f"{ROW['date']} {ROW['title']}"]
        links = [i["link"] for i in got]
        self.assertIn("https://a/1", links)
        self.assertIn("https://b/1", links)
        self.assertNotIn("https://c/1", links)             # published before the day
        self.assertNotIn("https://d/1", links)             # not about it
        self.assertEqual(len({i["company"] for i in got[:2]}), 2)      # the first ones are of two companies (the second article of one company comes after)

    def test_a_headline_with_one_common_word_and_no_outcome_is_not_enough(self):
        row = {"title": "全国高等学校駅伝競走大会 男子", "date": "2026-10-11", "date_end": None}
        it = {"source": "a", "company": "A", "title": "駅伝の魅力を語る", "link": "https://a/9", "published": "2026-10-12T00:00:00+09:00", "summary": ""}
        self.assertEqual(rssfeed.match([row], [it])[f"{row['date']} {row['title']}"], [])
        self.assertEqual(rssfeed.score(row, it), 0)

    def test_leads_need_a_day_and_an_announcement_word(self):
        a = {"title": "新作ゲーム、12月5日に発売決定", "summary": "", "link": "https://a/1"}
        b = {"title": "新作ゲームが話題に", "summary": "12月5日", "link": "https://a/2"}
        c = {"title": "天気は晴れ", "summary": "", "link": "https://a/3"}
        self.assertEqual(rssfeed.leads([a, b, c]), [a])


class SourceList(unittest.TestCase):
    def test_the_list_of_feeds_is_https_unique_and_names_a_company(self):
        d = json.loads((ROOT / "data/atomou/rss_sources.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in d["sources"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 15)
        for s in d["sources"]:
            self.assertTrue(s["url"].startswith("https://"), s)
            self.assertTrue(s["company"] and s["kind"], s)
        self.assertEqual(len(rssfeed.load_sources()), len(ids))


if __name__ == "__main__":
    unittest.main()
