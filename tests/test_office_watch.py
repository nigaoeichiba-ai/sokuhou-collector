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


def served_all(sha="a" * 40):
    return {"saichin": sha, "kuma": sha, "yorokobu": sha, "minna": sha}


def commit(minutes_ago, *files):
    return {"sha": "c" * 40, "time": NOW - dt.timedelta(minutes=minutes_ago), "files": list(files)}


def run(status="completed", event="push", minutes_ago=10):
    return {"status": status, "event": event, "created": NOW - dt.timedelta(minutes=minutes_ago)}


class DeployLagTest(unittest.TestCase):
    def lag(self, commits, runs=(), served=None):
        return w.deploy_lag(NOW, served if served is not None else served_all(), lambda sha: commits, list(runs))

    def test_nothing_after_the_live_commit_is_fine(self):
        r = self.lag([])
        self.assertEqual((r["problems"], r["heal"]), ([], []))
        self.assertEqual(len(r["ok"]), 4)

    def test_a_young_change_is_a_normal_wait(self):
        r = self.lag([commit(30, "sites/minna/series.json")])
        self.assertEqual(r["problems"], [])

    def test_an_old_unpublished_change_is_reported_and_deployed_again(self):
        r = self.lag([commit(200, "sites/minna/series.json")])
        self.assertEqual(r["heal"], ["minna"])
        self.assertTrue(any("minna-no-illust.com" in p and "200 分前" in p for p in r["problems"]))

    def test_the_lost_update_of_2026_10_16(self):
        # minna's commit is 3 hours old; the newest commit (a few minutes old) touches only yorokobu: minna must be found and yorokobu must not be blamed
        r = self.lag([commit(180, "sites/minna/library/x/series.json"), commit(5, "sites/yorokobu/compare.py")])
        self.assertEqual(r["heal"], ["minna"])
        self.assertFalse(any("yorokobu-present.com" in p for p in r["problems"]))

    def test_other_sites_files_do_not_count_for_this_site(self):
        r = self.lag([commit(500, "sites/yorokobu/compare.py")])
        self.assertTrue(any("yorokobu-present.com" in p for p in r["problems"]))
        self.assertFalse(any("minna-no-illust.com" in p or "kuma-sokuho.com" in p for p in r["problems"]))
        self.assertEqual(r["heal"], ["yorokobu"])

    def test_a_shared_file_concerns_every_site(self):
        r = self.lag([commit(500, "sokuhou/sitekit.py")])
        self.assertEqual(sorted(r["heal"]), ["kuma", "minna", "saichin", "yorokobu"])

    def test_files_that_do_not_start_a_deploy_are_ignored(self):
        r = self.lag([commit(500, "docs/x.md", "README.md")])
        self.assertEqual((r["problems"], r["heal"]), ([], []))

    def test_no_new_deploy_while_one_is_running_or_waiting(self):
        r = self.lag([commit(200, "sites/minna/a")], runs=[run("in_progress", minutes_ago=40)])
        self.assertEqual(r["heal"], [])
        self.assertTrue(r["problems"])

    def test_no_new_deploy_right_after_a_manual_one(self):
        r = self.lag([commit(200, "sites/minna/a")], runs=[run("completed", "workflow_dispatch", minutes_ago=60)])
        self.assertEqual(r["heal"], [])
        self.assertTrue(r["problems"])

    def test_a_deploy_run_that_runs_too_long_is_reported(self):
        r = self.lag([], runs=[run("in_progress", minutes_ago=200)])
        self.assertTrue(any("deploy-sites の実行が 200 分" in p for p in r["problems"]))

    def test_unreadable_things_are_never_counted_as_fine(self):
        r = w.deploy_lag(NOW, {"saichin": None, "kuma": "b" * 40, "yorokobu": "b" * 40, "minna": "b" * 40}, lambda sha: None, [])
        self.assertEqual((r["problems"], r["heal"], r["ok"]), ([], [], []))
        self.assertEqual(len(r["unverified"]), 4)

    def test_the_report_names_the_sites_that_were_deployed_again(self):
        r = w.check(NOW, get=make_get(), commits=HUMAN, deploy=self.lag([commit(200, "sites/minna/a")]))
        self.assertEqual(r["heal"], ["minna"])
        self.assertIn("自動で再公開を依頼しました", w.report(r, NOW))


if __name__ == "__main__":
    unittest.main()
