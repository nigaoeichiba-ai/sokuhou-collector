"""wadai news collector (sokuhou/wadainews.py): polite, read-only, headline + date only.  No network: a fake transport stands in for it."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sokuhou import wadainews as n
from sokuhou import wadaipost as w

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>
<item><title>関東一部 5日朝に警報級大雨恐れ</title><link>https://example.com/secret-link-1</link><description>BODY-TEXT-ONE</description><pubDate>Tue, 03 Nov 2026 23:23:21 GMT</pubDate></item>
<item><title>アソビュー 1500万件超の情報流出</title><link>https://example.com/secret-link-2</link><description>BODY-TEXT-TWO</description><pubDate>Tue, 03 Nov 2026 14:59:10 GMT</pubDate></item>
</channel></rss>""".encode("utf-8")
RDF = """<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<item><title>米中間選挙、開票始まる</title><link>https://example.com/r1</link><dc:date>2026-11-04T09:00:00+09:00</dc:date></item></rdf:RDF>""".encode("utf-8")
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>台風解析・予報情報</title><updated>2026-11-04T00:45:00Z</updated></entry></feed>""".encode("utf-8")


class FakeNet:
    """A transport that answers from a table {url: (status, body)} and records the order of requests."""
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, url, headers, timeout=20.0):
        self.calls.append(url)
        return self.table.get(url, (404, b""))


class Clock:
    def __init__(self):
        self.t = 0.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def fetcher(table):
    c = Clock()
    return n.Fetcher(FakeNet(table), sleep=c.sleep, clock=c.now), c


class TestParse(unittest.TestCase):
    def test_three_feed_shapes(self):
        self.assertEqual([i["title"] for i in n.parse_feed(RSS)], ["関東一部 5日朝に警報級大雨恐れ", "アソビュー 1500万件超の情報流出"])
        self.assertEqual(n.parse_feed(RDF)[0]["date"], "2026-11-04T09:00:00+09:00")
        self.assertEqual(n.parse_feed(ATOM)[0]["title"], "台風解析・予報情報")

    def test_dtd_and_entities_are_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
        with self.assertRaises(ValueError):
            n.parse_feed(bomb)


class TestFetcher(unittest.TestCase):
    URL = "https://news.example/rss.xml"

    def test_robots_disallow_means_refused(self):
        f, _ = fetcher({"https://news.example/robots.txt": (200, b"User-agent: *\nDisallow: /\n"), self.URL: (200, RSS)})
        with self.assertRaises(n.Refused):
            f.get(self.URL)
        self.assertNotIn(self.URL, f.transport.calls)               # the feed itself was never requested

    def test_http_403_and_429_are_refused(self):
        for st in (401, 403, 429):
            f, _ = fetcher({"https://news.example/robots.txt": (404, b""), self.URL: (st, b"")})
            with self.assertRaises(n.Refused):
                f.get(self.URL)

    def test_no_robots_txt_allows_reading(self):
        f, _ = fetcher({self.URL: (200, RSS)})
        self.assertEqual(f.get(self.URL), RSS)

    def test_a_refused_robots_txt_closes_the_host(self):
        f, _ = fetcher({"https://news.example/robots.txt": (403, b""), self.URL: (200, RSS)})
        with self.assertRaises(n.Refused):
            f.get(self.URL)

    def test_gap_between_requests_to_the_same_host(self):
        f, c = fetcher({self.URL: (200, RSS), "https://news.example/b.xml": (200, RSS)})
        f.get(self.URL)
        f.get("https://news.example/b.xml")
        # robots.txt + feed + feed: the second and third requests each wait for at least the host gap
        self.assertGreaterEqual(len(c.slept), 2)
        self.assertTrue(all(s >= n.HOST_GAP - 1e-6 for s in c.slept[:2]))

    def test_hatena_asks_for_five_seconds(self):
        f, c = fetcher({"https://b.hatena.ne.jp/hotentry/all.rss": (200, RDF)})
        f.get("https://b.hatena.ne.jp/hotentry/all.rss")
        self.assertTrue(any(s >= 5.0 - 1e-6 for s in c.slept))

    def test_gap_between_different_hosts(self):
        f, c = fetcher({self.URL: (200, RSS), "https://other.example/x.xml": (200, RSS)})
        f.get(self.URL)
        f.get("https://other.example/x.xml")
        self.assertTrue(any(s >= n.ANY_GAP - 1e-6 for s in c.slept))

    def test_a_bad_user_agent_is_not_sent(self):
        seen = []

        def tr(url, headers, timeout=20.0):
            seen.append(headers.get("User-Agent", ""))
            return 200, RSS
        n.Fetcher(tr, sleep=lambda s: None, clock=Clock().now).get(self.URL)
        self.assertTrue(all(u.startswith("sokuhou-collector/") and "@" not in u for u in seen))     # an honest name; no personal e-mail address


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.private = n.private_dir(self.t.name)
        self.addCleanup(self.t.cleanup)

    def srcs(self):
        return {"ok": ("https://a.example/rss", "general"), "closed": ("https://b.example/rss", "general"), "broken": ("https://c.example/rss", "general")}

    def table(self):
        return {"https://a.example/rss": (200, RSS), "https://b.example/robots.txt": (200, b"User-agent: *\nDisallow: /\n"), "https://c.example/rss": (200, b"not xml")}

    def test_only_headline_date_and_source_are_kept(self):
        f, _ = fetcher(self.table())
        r = n.collect(self.private, f, "20261104", self.srcs())
        self.assertEqual(r["headlines"], 2)
        text = (self.private / "news" / "20261104.jsonl").read_text(encoding="utf-8")
        for secret in ("secret-link", "BODY-TEXT", "http"):
            self.assertNotIn(secret, text)                                    # no link, no body, no summary
        rows = [json.loads(l) for l in text.splitlines()]
        self.assertEqual({tuple(sorted(r)) for r in rows}, {("date", "source", "title")})

    def test_a_refused_source_is_dropped_for_good(self):
        f, _ = fetcher(self.table())
        r = n.collect(self.private, f, "20261104", self.srcs())
        self.assertIn("refused", r["status"]["closed"])
        self.assertIn("closed", n.load_refused(self.private))
        f2, _ = fetcher(self.table())
        r2 = n.collect(self.private, f2, "20261105", self.srcs())
        self.assertIn("skipped", r2["status"]["closed"])
        self.assertFalse(any("b.example" in u for u in f2.transport.calls))    # not even robots.txt is requested again

    def test_a_broken_feed_does_not_stop_the_others(self):
        f, _ = fetcher(self.table())
        r = n.collect(self.private, f, "20261104", self.srcs())
        self.assertTrue(r["status"]["broken"].startswith("error"))
        self.assertTrue(r["status"]["ok"].startswith("ok"))

    def test_the_private_folder_must_be_outside_the_repository(self):
        with self.assertRaises(ValueError):
            n.private_dir(n.REPO_ROOT / "wadai-private-test")
        self.assertFalse((n.REPO_ROOT / "wadai-private-test").exists())

    def test_aggregators_are_discovery_only_and_listed_as_such(self):
        agg = {k for k, (_u, kind) in n.SOURCES.items() if kind == "aggregator"}
        self.assertEqual(agg, {"livedoor", "hatena"})
        # a refused aggregator drops out like any other source
        f, _ = fetcher({"https://news.livedoor.com/robots.txt": (403, b"")})
        with tempfile.TemporaryDirectory() as t:
            private = n.private_dir(t)
            r = n.collect(private, f, "20261104", {"livedoor": n.SOURCES["livedoor"]})
            self.assertIn("refused", r["status"]["livedoor"])

    def test_default_sources_have_no_sports_or_entertainment_only_feed(self):
        self.assertFalse(any("sports" in u or "entertainment" in u for u, _k in n.SOURCES.values()))


class TestClassify(unittest.TestCase):
    CASES = [
        ("関東一部 5日朝に警報級大雨恐れ", "disaster_weather"),
        ("緊急要請 備蓄1週間分並べてみた", "disaster_weather"),
        ("アソビュー 1500万件超の情報流出", "leak_security"),
        ("1兆円盗難 バイナンスが手口公表", "leak_security"),
        ("[ITmedia Mobile] 外出時の充電機器をまとめたい人に適した「Anker Power Bank」がセールで26％オフの6690円に", "gadget_sale"),
        ("中継 米中間選挙の開票速報", "politics_world_finance"),
        ("東証、一時6万2千円割れ", "politics_world_finance"),
        ("異例抜擢 マリナーズ新監督に36歳", "sports_entertainment"),
        ("体臭に悩み におわなくても劣等感", "health"),
        ("路上に血を流した女性 搬送も重体", "incident"),
        ("安いもやし限界 5年で13社消える", "life_food"),
        ("米巨大IT5社とも増収 7～9月期", "it_company"),
        ("パーソナルトレ トラブル急増", "consumer_trouble"),
        ("ひと目でわかる今日の傘マップ 11月4日(水)", "disaster_weather"),
        ("5日の天気（東日本）", "disaster_weather"),
        ("通信障害", "disaster_weather"),
        ("GMOのサーバー「設計上の不備」", "leak_security"),
        ("もう何もかも漏れている……それでも「暗黒の10月」に焦らなかった筆者", "leak_security"),
        ("三菱電機「純正SDカード」生産中止へ　産業用メモリの“調達難”", "product_news"),
        ("離婚後極貧 50歳で教員免許を取得", "career_learning"),
        ("盤上に虫 藤井竜王思わず席を立つ", "sports_entertainment"),
        ("松井証券", "politics_world_finance"),
        ("Unreal Engine 6ではアクターやブループリントなどを撤廃", "it_company"),
        ("個別指導トレーニングトラブル増 強引な勧誘や高額契約「慎重に」", "consumer_trouble"),
        ("12月から変わるahamoの新料金を検証", "consumer_trouble"),
    ]

    def test_known_headlines(self):
        for title, cat in self.CASES:
            self.assertEqual(n.classify(title), cat, title)

    def test_agency_advisories_are_counted_apart(self):
        self.assertEqual(n.classify("Weekly Report: GitLabに複数の脆弱性", "jpcert"), "security_advisory")
        self.assertEqual(n.classify("Weekly Report: GitLabに複数の脆弱性", "itmedia"), "leak_security")
        self.assertTrue(n.is_candidate("security_advisory"))

    def test_candidates_are_only_the_product_linked_categories(self):
        self.assertTrue(n.is_candidate("disaster_weather") and n.is_candidate("leak_security") and n.is_candidate("life_food") and n.is_candidate("consumer_trouble"))
        for c in ("gadget_sale", "politics_world_finance", "sports_entertainment", "health", "incident", "it_company", "other"):
            self.assertFalse(n.is_candidate(c), c)

    def test_one_event_counts_once(self):
        cl = n.cluster(["アソビュー 1500万件超の情報流出", "アソビュー 1500万件超の情報流出が判明", "台風31号は再発達して強い勢力に"])
        self.assertEqual(sorted(len(c) for c in cl), [1, 2])

    def test_report_counts_and_keeps_titles_private(self):
        with tempfile.TemporaryDirectory() as t:
            private = n.private_dir(t)
            f, _ = fetcher({"https://a.example/rss": (200, RSS), "https://a.example/rdf": (200, RDF)})
            n.collect(private, f, "20261104", {"a": ("https://a.example/rss", "general"), "b": ("https://a.example/rdf", "general")})
            r = n.make_report(private, "20261104")
            self.assertEqual(r["headlines"], 3)
            self.assertEqual(r["counts"]["disaster_weather"], 1)
            self.assertEqual(r["counts"]["leak_security"], 1)
            self.assertEqual(r["counts"]["politics_world_finance"], 1)
            self.assertEqual(r["candidates"], 2)
            self.assertTrue(all(isinstance(v, int) for v in r["counts"].values()))        # the returned summary has counts, no text
            self.assertIn("警報級大雨", (private / "news" / "20261104_report.md").read_text(encoding="utf-8"))


TARGETS = [{"tropicalCyclone": "TC2637", "typhoonNumber": "2631", "category": "TY", "issue": "2026-11-04T09:45:00+09:00"}]
SPEC = [
    {"part": "title", "issue": {"JST": "2026-11-04T09:45:00+09:00"}, "typhoonNumber": "2631", "name": {"jp": "インファ", "en": "In-fa"}, "category": {"jp": "台風", "en": "TY"}},
    {"part": {"jp": "実況", "en": "Analysis"}, "maximumWind": {"sustained": {"m/s": "35", "kt": "65"}}, "intensity": "強い", "position": {"deg": [24.2, 138.5]}, "pressure": "970",
     "validtime": {"JST": "2026-11-04T09:00:00+09:00"}, "advancedHours": 0},
    {"part": {"jp": "予報", "en": "Forecast"}, "advancedHours": 24, "validtime": {"JST": "2026-11-05T09:00:00+09:00"}, "position": {"deg": [27.9, 139.5]}, "location": "父島の西北西約280km"},
    {"part": {"jp": "予報", "en": "Forecast"}, "advancedHours": 72, "validtime": {"JST": "2026-11-07T09:00:00+09:00"}, "position": {"deg": [48.7, 167.6]}},
]


class TestPrimary(unittest.TestCase):
    def test_typhoon_facts_from_the_jma_shape(self):
        out = n.typhoon_facts(TARGETS, {"TC2637": SPEC})
        self.assertEqual(len(out), 1)
        lines = out[0]["fact_lines"]
        self.assertEqual(lines[0], "気象庁は11月4日9時の解析で、台風第31号(インファ)を「強い」勢力としている。中心気圧は970ヘクトパスカル、最大風速は35メートル。")
        self.assertIn("11月5日9時に台風は父島の西北西約280kmにある", lines[1])
        self.assertIn("72時間先まで", lines[-1])
        self.assertEqual(out[0]["evidence_id"], "jma-typhoon-2631-20261104-0945")

    def test_forecast_without_a_place_name_falls_back_to_the_position(self):
        spec = [SPEC[0], SPEC[1], dict(SPEC[2], location=None)]
        spec[2].pop("location")
        lines = n.typhoon_facts(TARGETS, {"TC2637": spec})[0]["fact_lines"]
        self.assertIn("北緯27.9度、東経139.5度", lines[1])

    def test_a_target_without_data_is_skipped(self):
        self.assertEqual(n.typhoon_facts(TARGETS, {}), [])
        self.assertEqual(n.typhoon_facts(TARGETS, {"TC2637": [SPEC[0]]}), [])

    def test_bousai_notices(self):
        html = '<ul><li><a href="/juyou/emergency_request.html">令和8年11月2日　事前防災徹底のための緊急要請</a></li><li><a href="/x.html">サイトマップ</a></li></ul>'
        got = n.bousai_notices(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["path"], "/juyou/emergency_request.html")
        self.assertIn("緊急要請", got[0]["title"])

    def test_skeleton_has_gaps_until_the_editor_writes_them(self):
        lines = n.typhoon_facts(TARGETS, {"TC2637": SPEC})[0]["fact_lines"]
        info = n.typhoon_facts(TARGETS, {"TC2637": SPEC})[0]
        sk = n.article_skeleton("202611-taifu31", "台風31号", lines, info["ledger"])
        self.assertTrue(n.has_gap(sk))                      # a skeleton cannot be mistaken for a finished article
        found = w.check_article(sk, {"today": datetime.now().date().isoformat(), "allowed_terms": ["ヘクトパスカル", "メートル", "父島"]})
        self.assertFalse([f for f in found if f.code in ("A03", "A04", "A05", "A07", "A08")], [f.line() for f in found])    # the filled fact layer itself passes the fact checks
        sk["sections"][1]["paras"] = ["台風の進路で変わりそうだ。"]
        sk["sections"][2]["paras"] = ["灯りを選ぶ基準を挙げる。"]
        self.assertFalse(n.has_gap(sk))


class TestStopwatch(unittest.TestCase):
    def test_start_and_end_are_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            private = n.private_dir(t)
            times = iter([datetime(2026, 11, 4, 9, 0, 0), datetime(2026, 11, 4, 9, 7, 30)])
            sw = n.Stopwatch(private, clock=lambda: next(times))
            with sw.stage("collect"):
                pass
            row = json.loads((private / "news" / "timing.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual((row["stage"], row["start"], row["end"], row["seconds"], row["ok"]), ("collect", "2026-11-04T09:00:00", "2026-11-04T09:07:30", 450.0, True))

    def test_stage_object_carries_the_seconds_and_the_summary_has_no_text(self):
        with tempfile.TemporaryDirectory() as t:
            private = n.private_dir(t)
            times = iter([datetime(2026, 11, 4, 9, 0, 0), datetime(2026, 11, 4, 9, 2, 5)])
            sw = n.Stopwatch(private, clock=lambda: next(times))
            with sw.stage("collect") as st:
                pass
            self.assertEqual(st.seconds, 125.0)
            out = n.timing_summary(private)
            self.assertIn("collect: 2026-11-04T09:00:00 -> 2026-11-04T09:02:05 = 125.0s", out)
            self.assertIn("total (last 1 stages): 125.0s", out)

    def test_a_failed_stage_is_recorded_as_not_ok(self):
        with tempfile.TemporaryDirectory() as t:
            private = n.private_dir(t)
            sw = n.Stopwatch(private, clock=lambda: datetime(2026, 11, 4, 9, 0, 0))
            with self.assertRaises(RuntimeError):
                with sw.stage("bundle"):
                    raise RuntimeError("x")
            self.assertFalse(json.loads((private / "news" / "timing.jsonl").read_text(encoding="utf-8").splitlines()[0])["ok"])


class TestHygiene(unittest.TestCase):
    def test_no_news_or_private_files_in_the_repository(self):
        import subprocess
        out = subprocess.run(["git", "-C", str(n.REPO_ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8", "replace")
        for p in (x for x in out.split("\0") if x):
            self.assertNotIn("wadai-private", p)
            self.assertFalse(p.endswith("_bundle.json") or p.endswith("refused.json") or p.endswith("timing.jsonl"), p)


if __name__ == "__main__":
    unittest.main()
