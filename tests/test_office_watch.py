"""The cloud watchdog must notice each kind of stop (negative tests) and stay quiet when everything is fine."""
import datetime as dt
import unittest

from sokuhou import office_watch as w

NOW = dt.datetime(2026, 10, 15, 3, 0, tzinfo=dt.timezone.utc)  # 12:00 JST on 2026-10-15
GOOD_TOP = "<html><h1>x</h1></html>"


def sitemap(day):
    return f"<urlset><url><loc>https://x/</loc><lastmod>{day}</lastmod></url></urlset>"


def make_get(sitemap_day="2026-10-15", picks_day="2026年10月15日", top=GOOD_TOP, broken=()):
    def get(url, headers=None, tries=2):
        if any(b in url for b in broken):
            raise OSError("boom")
        if url.endswith("/sitemap.xml"):
            return sitemap(sitemap_day)
        if url.endswith("/picks/"):
            return f"<p>{picks_day}</p>"
        return top
    return get


HUMAN = [{"author": "nigaoeichiba-ai", "time": NOW - dt.timedelta(hours=5)}]


class OfficeWatchTest(unittest.TestCase):
    def test_everything_fine_has_no_problem(self):
        r = w.check(NOW, get=make_get(), commits=HUMAN)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["unverified"], [])

    def test_stale_sitemap_is_a_problem(self):
        r = w.check(NOW, get=make_get(sitemap_day="2026-10-10"), commits=HUMAN)
        self.assertTrue(any("sitemap" in p for p in r["problems"]))

    def test_stale_picks_page_means_pc_stopped(self):
        r = w.check(NOW, get=make_get(picks_day="2026年10月12日"), commits=HUMAN)
        self.assertTrue(any("パソコン側" in p and "picks" in p for p in r["problems"]))

    def test_picks_of_yesterday_are_fine(self):
        r = w.check(NOW, get=make_get(picks_day="2026年10月14日"), commits=HUMAN)
        self.assertEqual(r["problems"], [])

    def test_no_commit_by_the_owner_account_is_a_problem(self):
        bot_only = [{"author": "sokuhou-bot", "time": NOW - dt.timedelta(hours=1)}]
        r = w.check(NOW, get=make_get(), commits=bot_only)
        self.assertTrue(any("コミットがありません" in p for p in r["problems"]))

    def test_site_down_is_a_problem(self):
        r = w.check(NOW, get=make_get(broken=("kuma-sokuho.com/",)), commits=HUMAN)
        self.assertTrue(any(p.startswith("kuma-sokuho.com") and "開きません" in p for p in r["problems"]))

    def test_page_without_h1_is_a_problem(self):
        r = w.check(NOW, get=make_get(top="<html>error</html>"), commits=HUMAN)
        self.assertEqual(len([p for p in r["problems"] if "h1" in p]), 4)

    def test_unreadable_things_are_never_counted_as_fine(self):
        r = w.check(NOW, get=make_get(broken=("/sitemap.xml", "/picks/")), commits=None)
        self.assertEqual(r["problems"], [])
        self.assertEqual(len(r["unverified"]), 6)  # 4 sitemaps + picks + commit list

    def test_dates(self):
        self.assertEqual(w.newest_lastmod(sitemap("2026-10-15") + sitemap("2026-10-09")), dt.date(2026, 10, 15))
        self.assertEqual(w.newest_japanese_date("2026年10月11日 2026年10月15日 2026年2月30日"), dt.date(2026, 10, 15))
        self.assertIsNone(w.newest_japanese_date("no date"))

    def test_report_lists_problems_and_the_test_note(self):
        r = w.check(NOW, get=make_get(sitemap_day="2026-10-01"), commits=HUMAN)
        text = w.report(r, NOW, test=True)
        self.assertIn("おかしいところ", text)
        self.assertIn("通知のテスト", text)


if __name__ == "__main__":
    unittest.main()
