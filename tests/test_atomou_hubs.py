"""atomou: the hub robot takes dated lines from schedule pages, obeys robots.txt, and never visits a page that is switched off."""
import io
import json
import sys
import unittest
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import hubs  # noqa: E402

TODAY = date(2026, 10, 10)
NOW = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)


class Resp:
    def __init__(self, body, ct="text/html; charset=utf-8"):
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = {"Content-Type": ct}
        self.status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1): return self.body


def hub(i="h1", url="https://x.example/cal/{YYYYMM}", monthly=True, enabled=True):
    return {"id": i, "name": i, "kind": "official", "genre": "trip", "url": url, "monthly": monthly, "enabled": enabled}


PAGE = """<html><body><table>
<tr><td>2026年10月13日</td><td>企業物価指数(9月)の公表</td></tr>
<tr><td>2026年9月1日</td><td>もう過ぎた会合のお知らせ</td></tr>
<tr><td>2029年1月1日</td><td>ずっと先の記念行事のご案内</td></tr>
</table>
<h3>11月3日(火)</h3><ul><li>文化の日の無料開放イベント</li><li>市民マラソン大会</li></ul>
<h3>11月4日(水)</h3><ul><li>秋の味覚フェスティバル</li></ul>
<script>var d = "2026年10月20日 スクリプトの中の日付";</script>
</body></html>"""


class Reading(unittest.TestCase):
    def test_a_row_with_a_coming_date_and_the_lines_under_a_date_heading_are_taken(self):
        cs = hubs.candidates_from(PAGE, TODAY, hub(), "https://x.example/p")
        got = {(c["date"], c["title"]) for c in cs}
        self.assertIn(("2026-10-13", "企業物価指数(9月)の公表"), got)
        self.assertIn(("2026-11-03", "文化の日の無料開放イベント"), got)
        self.assertIn(("2026-11-03", "市民マラソン大会"), got)
        self.assertIn(("2026-11-04", "秋の味覚フェスティバル"), got)
        self.assertFalse(any(c["date"] == "2026-09-01" for c in cs))        # the past is left
        self.assertFalse(any(c["date"].startswith("2029") for c in cs))     # so is what is beyond 120 days
        self.assertFalse(any("スクリプト" in c["title"] for c in cs))        # nothing from scripts
        self.assertFalse(any(c["title"].startswith("(") and len(c["title"]) < 6 for c in cs))

    def test_a_bare_weekday_is_not_a_headline(self):
        cs = hubs.candidates_from("<ul><li>11月1日 (日曜)</li></ul>", TODAY, hub(), "u")
        self.assertEqual(cs, [])

    def test_a_shift_jis_page_is_decoded_by_the_header_or_by_trying(self):
        body = "<p>2026年10月13日 企業物価指数の公表</p>".encode("cp932")
        self.assertIn("企業物価指数", hubs.decode(body, "text/html; charset=Shift_JIS"))
        self.assertIn("企業物価指数", hubs.decode(body, "text/html"))                      # no charset anywhere: not UTF-8, so Shift_JIS
        self.assertIn("企業物価指数", hubs.decode("<p>企業物価指数</p>".encode("utf-8"), ""))

    def test_the_months_asked_for(self):
        self.assertEqual(hubs.urls_for(hub(), date(2026, 11, 20), 3), ["https://x.example/cal/202611", "https://x.example/cal/202612", "https://x.example/cal/202701"])
        self.assertEqual(hubs.urls_for(hub(url="https://x.example/{Y}/{M}/{Y1}/{YYMM}", monthly=False), TODAY, 4), ["https://x.example/2026/10/2027/2610"])


class Running(unittest.TestCase):
    def opener(self, calls, robots="User-agent: *\nDisallow: /private/\n"):
        def op(req, timeout=0):
            calls.append(req.full_url)
            if req.full_url.endswith("/robots.txt"):
                return Resp(robots, "text/plain")
            if "private" in req.full_url:
                return Resp("<p>2026年10月20日 見に行ってはいけないページ</p>")
            return Resp(PAGE)
        return op

    def test_robots_is_obeyed_a_switched_off_hub_is_not_visited_and_one_run_marks_what_is_new(self):
        calls = []
        hs = {"months": 1, "hubs": [hub("a", "https://x.example/cal/{YYYYMM}"), hub("b", "https://x.example/private/{YYYYMM}"), hub("c", "https://y.example/{YYYYMM}", enabled=False)]}
        pub, st, rep = hubs.run(hs, {}, TODAY, NOW, opener=self.opener(calls), pause=0)
        self.assertNotIn("https://x.example/private/202610", calls)           # robots.txt says no
        self.assertFalse(any("y.example" in c for c in calls))               # switched off
        self.assertEqual({s["id"]: s["result"] for s in rep["hubs"]}, {"a": "ok", "b": "robots-no"})
        self.assertTrue(rep["candidates"] >= 4 and rep["new"] == rep["candidates"])
        pub2, st2, rep2 = hubs.run(hs, st, TODAY, NOW, opener=self.opener([]), pause=0)
        self.assertEqual((rep2["candidates"], rep2["new"]), (rep["candidates"], 0))   # the same lines are not new the next day
        self.assertFalse(any(c["new"] for c in pub2["candidates"]))

    def test_a_missing_robots_file_forbids_nothing_and_a_forbidding_one_forbids_all(self):
        def op_404(req, timeout=0):
            if req.full_url.endswith("/robots.txt"):
                raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b""))
            return Resp(PAGE)
        _, _, rep = hubs.run({"months": 1, "hubs": [hub("a")]}, {}, TODAY, NOW, opener=op_404, pause=0)
        self.assertEqual(rep["hubs"][0]["result"], "ok")
        def op_403(req, timeout=0):
            if req.full_url.endswith("/robots.txt"):
                raise urllib.error.HTTPError(req.full_url, 403, "no", {}, io.BytesIO(b""))
            return Resp(PAGE)
        _, _, rep = hubs.run({"months": 1, "hubs": [hub("a")]}, {}, TODAY, NOW, opener=op_403, pause=0)
        self.assertEqual(rep["hubs"][0]["result"], "robots-no")             # the careful reading: a forbidden robots.txt is "no"

    def test_the_most_pages_a_run(self):
        calls = []
        hs = {"months": 4, "hubs": [hub("a")]}
        _, _, rep = hubs.run(hs, {}, TODAY, NOW, max_pages=2, opener=self.opener(calls), pause=0)
        self.assertEqual(rep["pages"], 2)


class Registry(unittest.TestCase):
    def test_the_list_has_no_aggregator_switched_on_and_every_template_fills(self):
        data = hubs.load_hubs()
        ids = set()
        for h in data["hubs"]:
            self.assertNotIn(h["id"], ids)
            ids.add(h["id"])
            if h["kind"] == "aggregator":
                self.assertFalse(h["enabled"], h["id"])                      # until its terms have been read
            for u in hubs.urls_for(h, TODAY, 2):
                self.assertTrue(u.startswith("https://") and "{" not in u, u)
            self.assertTrue(h["terms"], h["id"])
        self.assertGreaterEqual(sum(1 for h in data["hubs"] if h["enabled"]), 5)


if __name__ == "__main__":
    unittest.main()
