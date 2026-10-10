"""atomou: the checking robot flags a day whose official page no longer says it, and never edits a date."""
import sys
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import recheck  # noqa: E402

TODAY = date(2026, 10, 10)
NOW = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)


def entry(i, title, day, url, quote="", status="active"):
    return {"id": i, "title": title, "date": day, "source_url": url, "source_quote": quote, "status": status}


class Resp:
    def __init__(self, text, ct="text/html; charset=utf-8"):
        self.body, self.headers = text.encode("utf-8"), {"Content-Type": ct}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1): return self.body


class Reading(unittest.TestCase):
    def test_the_quote_or_the_title_and_the_date_close_together(self):
        e = entry("a", "全日本剣道選手権大会", "2026-11-03", "https://x.example/a", "全日本剣道選手権大会 11月3日(火)")
        self.assertTrue(recheck.still_there(e, "<p>全日本剣道選手権大会　11月3日(火)　日本武道館</p>"))
        e2 = entry("b", "全日本剣道選手権大会", "2026-11-03", "https://x.example/a", "古い書き方の引用")
        self.assertTrue(recheck.still_there(e2, "<td>全日本剣道選手権大会</td><td>2026年11月3日</td>"))       # the page was written again: the title and the date still stand together
        self.assertFalse(recheck.still_there(e2, "<td>全日本剣道選手権大会</td><td>2026年11月10日</td>"))      # the date moved
        self.assertFalse(recheck.still_there(e2, "<p>まったく別のページ</p>"))

    def test_nearer_days_are_checked_more_often(self):
        self.assertEqual(recheck.interval_days("2026-10-15", TODAY), 0.2)
        self.assertEqual(recheck.interval_days("2026-10-30", TODAY), 1)
        self.assertEqual(recheck.interval_days("2027-03-01", TODAY), 7)


class Running(unittest.TestCase):
    def test_a_moved_date_is_flagged_an_unreachable_page_is_not_and_one_page_is_fetched_once(self):
        es = [entry("a", "全日本剣道選手権大会", "2026-11-03", "https://x.example/kendo", "全日本剣道選手権大会 11月3日"),
              entry("b", "全日本剣道選手権大会 女子", "2026-11-03", "https://x.example/kendo", "全日本剣道選手権大会 女子 11月3日"),
              entry("c", "春の大会", "2026-11-05", "https://y.example/down", "春の大会 11月5日"),
              entry("d", "秋の祭り", "2026-11-06", "https://z.example/moved", "秋の祭り 11月6日"),
              entry("e", "もう終わった日", "2026-09-01", "https://w.example/old", "x", status="ended")]
        calls = []
        def opener(req, timeout=0):
            calls.append(req.full_url)
            if "down" in req.full_url:
                raise urllib.error.URLError("down")
            if "kendo" in req.full_url:
                return Resp("全日本剣道選手権大会 11月3日 開催。 全日本剣道選手権大会 女子 11月3日")
            return Resp("秋の祭りは 11月13日 に変わりました")
        pub, st, rep = recheck.run(es, {}, TODAY, NOW, opener=opener, pause=0)
        self.assertEqual(sorted(calls), ["https://x.example/kendo", "https://y.example/down", "https://z.example/moved"])   # two days, one fetch; the ended day is not checked
        self.assertEqual(pub["changed"], ["d"])
        self.assertEqual((rep["unreadable"], rep["checked"]), (1, 3))
        self.assertEqual(st["https://y.example/down"]["fail"], 1)

    def test_a_page_is_not_asked_again_before_its_time_and_the_nearest_day_goes_first(self):
        es = [entry("far", "遠い日", "2027-06-01", "https://far.example/", "遠い日 6月1日"), entry("near", "近い日", "2026-10-12", "https://near.example/", "近い日 10月12日")]
        order = []
        def opener(req, timeout=0):
            order.append(req.full_url)
            return Resp("近い日 10月12日 / 遠い日 6月1日")
        pub, st, rep = recheck.run(es, {}, TODAY, NOW, opener=opener, pause=0)
        self.assertEqual(order, ["https://near.example/", "https://far.example/"])
        order.clear()
        recheck.run(es, st, TODAY, NOW + timedelta(hours=1), opener=opener, pause=0)
        self.assertEqual(order, [])                                                          # an hour later: nothing is due
        recheck.run(es, st, TODAY, NOW + timedelta(hours=6), opener=opener, pause=0)
        self.assertEqual(order, ["https://near.example/"])                                   # the near day again after about 5 hours; the far one rests a week

    def test_a_page_that_no_longer_speaks_of_the_event_is_only_listed_not_flagged(self):
        es = [entry("gone", "夏の花火大会", "2026-10-20", "https://g.example/", "夏の花火大会 10月20日")]
        pub, st, rep = recheck.run(es, {}, TODAY, NOW, opener=lambda req, timeout=0: Resp("<p>別のお知らせです</p>"), pause=0)
        self.assertEqual(pub["changed"], [])                                                 # not shown on the day
        self.assertEqual([x["id"] for x in rep["lost"]], ["gone"])                           # but the report says so
        self.assertEqual(recheck.verdict(es[0], "<script>var x=1</script><p>夏の花火大会 10月20日</p>"), "ok")
        self.assertEqual(recheck.verdict(es[0], "夏の花火大会のお知らせ 10月27日に延期"), "changed")

    def test_the_most_pages_a_run_and_nothing_written_to_the_data(self):
        es = [entry(str(i), f"日{i}", "2026-10-20", f"https://h{i}.example/", f"日{i} 10月20日") for i in range(5)]
        n = []
        def opener(req, timeout=0):
            n.append(1)
            return Resp("none")
        recheck.run(es, {}, TODAY, NOW, max_pages=2, opener=opener, pause=0)
        self.assertEqual(len(n), 2)


if __name__ == "__main__":
    unittest.main()
