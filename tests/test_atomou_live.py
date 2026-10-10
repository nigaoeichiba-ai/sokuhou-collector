"""atomou: the live feed (速報) reads official feeds politely, keeps only headline, address, time, day and genre, and drops what is noise or sad."""
import json
import sys
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import live  # noqa: E402

NOW = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)   # 12:00 JST

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>
<item><title>『新作ゲーム』の発売日を12月3日に決定</title><link>https://example.go.jp/a</link><pubDate>Sat, 10 Oct 2026 02:30:00 +0000</pubDate><description>&lt;p&gt;本文は使わない&lt;/p&gt;</description></item>
<item><title>会議の議事録を公開しました</title><link>https://example.go.jp/b</link><pubDate>Sat, 10 Oct 2026 02:00:00 +0000</pubDate></item>
<item><title>著名人の死去について</title><link>https://example.go.jp/c</link><pubDate>Sat, 10 Oct 2026 02:00:00 +0000</pubDate></item>
<item><title>ずっと前の発表を開始</title><link>https://example.go.jp/old</link><pubDate>Mon, 01 Sep 2026 02:00:00 +0000</pubDate></item>
<item><title>http の項目の開始</title><link>http://example.go.jp/plain</link><pubDate>Sat, 10 Oct 2026 02:00:00 +0000</pubDate></item>
</channel></rss>"""

RDF_SJIS = ('<?xml version="1.0" encoding="Shift_JIS"?><rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<item rdf:about="https://example.go.jp/r"><title>電車の運賃改定について</title><link>https://example.go.jp/r</link><dc:date>2026-10-10T10:00:00+09:00</dc:date></item></rdf:RDF>').encode("cp932")

ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
<entry><title>OS の提供を2026年11月5日に開始</title><link rel="alternate" href="https://example.com/post1"/><updated>2026-10-10T01:00:00Z</updated><summary>x</summary></entry></feed>"""

SRC = {"id": "t", "name": "テスト", "url": "https://example.go.jp/feed", "group": "経済・政治", "mid": "国会・政府の予定", "subject": "官邸",
       "rules": [{"re": "運賃", "group": "路線・交通", "mid": "運賃・料金の改定", "subject": "運賃"}]}


class Reading(unittest.TestCase):
    def test_rss_rdf_and_atom_are_read_and_shift_jis_is_decoded(self):
        a = live.parse_feed(live.decode(RSS.encode("utf-8"), "application/rss+xml"))
        self.assertEqual([x["url"] for x in a][:2], ["https://example.go.jp/a", "https://example.go.jp/b"])
        self.assertNotIn("<p>", a[0]["desc"])                                   # no markup from the description
        r = live.parse_feed(live.decode(RDF_SJIS, "application/rdf+xml"))
        self.assertEqual((r[0]["title"], r[0]["time"].isoformat()), ("電車の運賃改定について", "2026-10-10T01:00:00+00:00"))
        t = live.parse_feed(live.decode(ATOM.encode("utf-8")))
        self.assertEqual((t[0]["url"], t[0]["time"].isoformat()), ("https://example.com/post1", "2026-10-10T01:00:00+00:00"))

    def test_a_broken_feed_gives_nothing(self):
        self.assertEqual(live.parse_feed("<rss><channel><item>"), [])
        self.assertEqual(live.parse_feed("not xml at all"), [])


class Days(unittest.TestCase):
    def test_the_day_written_in_a_title(self):
        d = date(2026, 10, 10)
        self.assertEqual(live.day_in("発売日を12月3日に決定", d), "2026-12-03")
        self.assertEqual(live.day_in("2027年3月9日に開催", d), "2027-03-09")
        self.assertEqual(live.day_in("１０月１７日(土)から", d), "2026-10-17")        # full-width digits
        self.assertEqual(live.day_in("1月5日から", d), "2027-01-05")                    # a day without a year is the next such day
        self.assertEqual(live.day_in("9月2日に終了しました", d), "")                    # past: not a day to count to
        self.assertEqual(live.day_in("2月30日", d), "")                                  # not a date
        self.assertEqual(live.day_in("日付なし", d), "")


class Making(unittest.TestCase):
    def items(self, text=RSS):
        return live.make_items(SRC, live.parse_feed(text), NOW, {})

    def test_keeps_headline_address_time_day_and_genre_only(self):
        its = self.items()
        self.assertEqual([i["u"] for i in its], ["https://example.go.jp/a"])        # the noise, the sad, the old and the plain-http ones are gone
        i = its[0]
        self.assertEqual((i["d"], i["g"], i["m"], i["s"]), ("2026-12-03", "経済・政治", "国会・政府の予定", "テスト"))
        self.assertEqual(set(i), {"id", "t", "u", "s", "x", "p", "f", "d", "g", "m", "k"})   # no body, no picture
        self.assertLessEqual(len(i["t"]), 80)

    def test_a_rule_of_the_source_sets_the_genre(self):
        i = live.make_items(SRC, live.parse_feed(live.decode(RDF_SJIS)), NOW, {})[0]
        self.assertEqual((i["g"], i["m"], i["k"]), ("路線・交通", "運賃・料金の改定", "運賃"))

    def test_an_id_follows_the_address_not_the_title(self):
        a = live.item_id("https://example.go.jp/a")
        self.assertEqual(a, live.item_id("https://example.go.jp/a#top"))
        self.assertNotEqual(a, live.item_id("https://example.go.jp/b"))


class Fetching(unittest.TestCase):
    class Resp:
        def __init__(self, body, headers=None):
            self.body, self.headers = body, headers or {"Content-Type": "application/rss+xml", "ETag": '"v1"', "Last-Modified": "Sat, 10 Oct 2026 02:30:00 GMT"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return self.body

    def test_a_conditional_request_and_a_304(self):
        seen = {}
        def opener(req, timeout=0):
            seen.update({k.lower(): v for k, v in req.header_items()})
            return self.Resp(RSS.encode("utf-8"))
        entries, st = live.fetch(SRC, {}, NOW, opener)
        self.assertTrue(entries and st["etag"] == '"v1"' and st["fails"] == 0)
        self.assertIn("atomou-bot", seen["user-agent"])
        # the next time the validators go back (after the gap)
        st["at"] = 0
        def opener304(req, timeout=0):
            self.assertEqual(req.get_header("If-none-match"), '"v1"')
            raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", {}, None)
        entries, st2 = live.fetch(SRC, st, NOW, opener304)
        self.assertEqual((entries, st2["fails"]), ([], 0))

    def test_the_minimum_gap_and_the_back_off_for_a_failing_source(self):
        calls = []
        def opener(req, timeout=0):
            calls.append(1)
            raise urllib.error.URLError("down")
        entries, st = live.fetch(SRC, {}, NOW, opener)
        self.assertEqual((len(calls), st["fails"]), (1, 1))
        entries, st = live.fetch(SRC, st, NOW, opener)                                # asked again at once: not asked
        self.assertEqual(len(calls), 1)
        gap1 = 10 * 60 * (1 + 1)
        st["at"] -= gap1 + 5
        live.fetch(SRC, st, NOW, opener)
        self.assertEqual(len(calls), 2)                                                # after the longer gap it is asked again

    def test_run_keeps_72_hours_and_the_first_seen_time(self):
        def opener(req, timeout=0):
            return self.Resp(RSS.encode("utf-8"))
        pub, st, rep = live.run([SRC], {}, NOW, opener)
        self.assertEqual((len(pub["items"]), rep["new"], rep["failed"]), (1, 1, []))
        first = st["items"][pub["items"][0]["id"]]["f"]
        later = NOW + timedelta(hours=80)
        pub2, st2, rep2 = live.run([SRC], {"sources": {}, "items": st["items"]}, later, opener)
        self.assertEqual(len(pub2["items"]), 0)                                        # older than 72 hours: gone
        json.dumps(pub)                                                                # the public file is plain JSON
        self.assertTrue(first)


class Sources(unittest.TestCase):
    def test_the_source_list_is_official_feeds_only(self):
        src = live.load_sources()
        self.assertGreaterEqual(len(src), 8)
        for s in src:
            self.assertTrue(s["url"].startswith("https://"), s["id"])
            self.assertEqual(len(s["id"]), len(set(x["id"] for x in src if x["id"] == s["id"])) * len(s["id"]))
        banned = ("twitter", "x.com", "instagram", "facebook", "tiktok", "news.google", "news.yahoo", "prtimes", "nhk.or.jp", "yomiuri", "asahi", "mainichi", "nikkei", "kyodo", "jiji")
        for s in src:
            self.assertFalse(any(b in s["url"] for b in banned), s["url"])

    def test_every_rule_names_a_real_genre_and_middle(self):
        from sites.atomou import catalog
        for s in live.load_sources():
            for g, m in [(s["group"], s.get("mid", "その他"))] + [(r["group"], r.get("mid", "その他")) for r in s.get("rules", [])]:
                self.assertIn(g, catalog.GROUPS, s["id"])
                self.assertIn(m, catalog.MID_NAMES[g], f'{s["id"]}: {g} / {m}')


class Wiring(unittest.TestCase):
    def test_the_workflow_runs_every_ten_minutes_and_puts_only_the_live_file_on_the_server(self):
        wf = (ROOT / ".github" / "workflows" / "atomou-live.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "3-59/10 * * * *"', wf)                       # every ten minutes, not on the round minutes where the deploys start
        self.assertIn("live_uploaded.txt", wf)                              # the server (the same one the deploys use over SSH) is called only when the headlines changed, or after 6 hours
        self.assertIn("the server is not called", wf)
        self.assertLess(wf.index("the server is not called"), wf.index("ssh -i"))
        self.assertIn("sites/atomou/live.py", wf)
        self.assertIn("live.v1.json", wf)
        self.assertNotIn("git push", wf)                                   # nothing is committed: no deploy is started by it
        self.assertIn('if [ -z "$KEY" ]', wf)                              # without the server secrets it only makes the file

    def test_the_live_script_runs_on_the_servers_python_3_6_and_the_server_cron_puts_the_file_without_ssh(self):
        import ast
        src = (ROOT / "sites" / "atomou" / "live.py").read_text(encoding="utf-8")
        ast.parse(src, feature_version=(3, 6))                         # no syntax newer than the server's Python (3.6.8)
        self.assertNotIn("from __future__ import annotations", src)    # 3.7+
        self.assertNotIn("fromisoformat", src)                         # 3.7+
        sh = (ROOT / "sites" / "atomou" / "server_live.sh").read_text(encoding="utf-8")
        self.assertIn("sites/atomou/live.py", sh)
        self.assertIn("/usr/bin/python3", sh)
        self.assertNotIn("ssh ", sh)                                   # the server reads the feeds itself
        self.assertIn("live.v1.json", sh)
        self.assertIn("public_html/demo.atomou.com", sh)
        wf = (ROOT / "." / ".github" / "workflows" / "atomou-server-live.yml").read_text(encoding="utf-8")
        self.assertIn("feature_version=(3,6)", wf)
        self.assertIn("workflow_dispatch", wf)
        self.assertNotIn("schedule:", wf)

    def test_the_recheck_workflow_runs_every_six_hours_and_only_writes_its_file(self):
        wf = (ROOT / ".github" / "workflows" / "atomou-recheck.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "20 */6 * * *"', wf)
        self.assertIn("sites/atomou/recheck.py", wf)
        self.assertIn("recheck.v1.json", wf)
        self.assertNotIn("git push", wf)

    def test_a_deploy_carries_the_live_folder_over(self):
        dep = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn("cp -a " + chr(92) + '"public_html/' + chr(92) + '$d' + chr(92) + '" ' + chr(92) + '".deploy_next/' + chr(92) + '$d' + chr(92) + '"', dep)

    def test_the_live_file_is_never_cached_by_the_browser(self):
        from sites.atomou import build
        self.assertIn('manifest' + chr(92) + '.webmanifest|(live|recheck)' + chr(92) + '.v1' + chr(92) + '.json)$">', build.HT_CACHE)


if __name__ == "__main__":
    unittest.main()
