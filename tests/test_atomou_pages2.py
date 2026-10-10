"""atomou: 今日は何の日 (/kyou/), 新着・人気 (/new/), the badge / change log / correction link / structured data of a day's page, and the server's popular-days script."""
import ast
import json
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, server_pop  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 10)


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rel = build.build_pages(CFG, release=True, today=TODAY)
        cls.entries, _ = catalog.build_catalog(TODAY)


class KyouTest(Built):
    def test_index_and_dates(self):
        idx = self.rel["kyou/index.html"]
        self.assertIn("<h1>今日は何の日</h1>", idx)
        self.assertIn('id="kyou-today"', idx)
        days = build.kyou_days(self.entries)
        self.assertGreater(len(days), 100)
        for md in list(days)[:5]:
            self.assertIn(f"kyou/{md}/index.html", self.rel)
            self.assertIn(f'href="/kyou/{md}/"', idx)

    def test_a_date_with_one_day_stays_out_of_search_results_and_the_sitemap(self):
        days = build.kyou_days(self.entries)
        sitemap = self.rel["sitemap.xml"]
        thin = [md for md, v in days.items() if len(v) < 2]
        rich = [md for md, v in days.items() if len(v) >= 2]
        self.assertTrue(thin and rich)
        for md in thin[:5]:
            self.assertIn("noindex", self.rel[f"kyou/{md}/index.html"], md)
            self.assertNotIn(f"/kyou/{md}/", sitemap, md)
        for md in rich[:5]:
            self.assertNotIn('content="noindex', self.rel[f"kyou/{md}/index.html"], md)
            self.assertIn(f"/kyou/{md}/", sitemap, md)

    def test_a_date_with_a_quiet_day_has_no_ads_and_no_cards_for_it(self):
        quiet = [e for e in self.entries if e["quiet"] and e["precision"] == "day" and not e.get("estimated")]
        self.assertTrue(quiet)
        for e in quiet[:8]:
            html = self.rel[f"kyou/{e['date'][5:]}/index.html"]
            self.assertNotIn("adsbygoogle", html)
            self.assertNotIn(f'data-key="c:{e["id"]}"', html)       # the quiet day is a plain link, never a card with buttons
            self.assertIn(f'href="/e/{e["id"]}/"', html)

    def test_history_dates_are_listed_under_their_own_month_and_day(self):
        h = [e for e in self.entries if e.get("history")]
        self.assertTrue(h)
        e = h[0]
        old = e["history"][0]
        self.assertIn(f'href="/e/{e["id"]}/"', self.rel[f"kyou/{old[5:]}/index.html"])


class NewPageTest(Built):
    def test_new_and_popular(self):
        html = self.rel["new/index.html"]
        self.assertIn("<h1>新着・人気の日</h1>", html)
        self.assertIn('id="pop-grid"', html)
        self.assertIn("に載せた日", html)
        self.assertIn("/new/", self.rel["sitemap.xml"])
        self.assertIn('href="/new/"', self.rel["index.html"])
        self.assertIn('href="/kyou/"', self.rel["index.html"])

    def test_the_popular_file_is_not_cached_hard(self):
        self.assertIn("(live|recheck|pop)\\.v1\\.json", self.rel[".htaccess"])


class DayPageTest(Built):
    def page(self, e):
        return self.rel[f"e/{e['id']}/index.html"]

    def ld(self, html):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertTrue(m)
        return json.loads(m.group(1))["@graph"]

    def test_badge_sentence_and_log(self):
        ok = next(e for e in self.entries if not e.get("estimated") and not e.get("corrected_on") and e["status"] != "old_checked")
        self.assertIn('vb-ok" data-vbadge>確認済', self.page(ok))
        est = next(e for e in self.entries if e.get("estimated"))
        self.assertIn('vb-pending" data-vbadge>未発表', self.page(est))
        self.assertIn("<dt>掲載</dt>", self.page(ok))

    def test_the_four_states(self):
        base = next(e for e in self.entries if not e.get("estimated"))
        self.assertEqual(build.verify_badge({**base, "corrected_on": "", "status": "active"})[0], "ok")
        self.assertEqual(build.verify_badge({**base, "corrected_on": "2026-10-09", "status": "active"})[0], "fixed")
        self.assertEqual(build.verify_badge({**base, "corrected_on": "", "status": "old_checked"})[0], "old")
        self.assertEqual(build.verify_badge({**base, "estimated": True})[0], "pending")

    def test_the_correction_link_brings_the_page_address(self):
        e = self.entries[0]
        self.assertIn(f'href="/contact/?kind=date&amp;page=https%3A%2F%2Fatomou.com%2Fe%2F{e["id"]}%2F"', self.page(e))
        app = (ROOT / "sites/atomou/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("form.cf", app)
        self.assertIn("日付の間違い", app)
        self.assertIn("日付の間違い", " ".join(CFG["contact_kinds"]))       # the option the link selects exists

    def test_structured_data(self):
        for e in self.entries[:60]:
            g = self.ld(self.page(e))
            self.assertEqual(g[0]["@type"], "WebPage")
            self.assertEqual(g[0]["dateModified"], e.get("corrected_on") or e["checked_on"])
            self.assertEqual(g[0]["datePublished"], e["added"])
            if e["quiet"] or e.get("estimated"):
                self.assertEqual(len(g), 1, e["title"])               # no event markup for a quiet day or an estimate
        events = [e for e in self.entries if not e["quiet"] and not e.get("estimated") and e["kind"] in build.EVENT_LD_KINDS and (e.get("place") or "") not in ("", "全国", "地域")]
        self.assertTrue(events)
        g = self.ld(self.page(events[0]))
        self.assertEqual(g[1]["@type"], "Event")
        self.assertEqual(g[1]["startDate"], events[0]["date"])
        self.assertIn("location", g[1])

    def test_change_log_is_cleaned(self):
        out = catalog._changes([{"on": "2026-10-09", "text": "開催日が変わった"}, {"on": "bad", "text": "x"}, {"on": "2026-10-11", "text": " "}, {"on": "2026-10-11", "text": "あ" * 90}, "x"])
        self.assertEqual([c["on"] for c in out], ["2026-10-11", "2026-10-09"])
        self.assertEqual(len(out[0]["text"]), 60)
        self.assertEqual(catalog._day_or_empty("2026-02-31"), "")


class PopularScriptTest(unittest.TestCase):
    def make(self, tmp, name, data):
        (Path(tmp) / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")

    def test_order_threshold_window_and_no_numbers(self):
        today = date(2026, 10, 10)
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, (today - timedelta(days=1)).isoformat(), {"act:pop:aaaaaaaaaa": 2, "act:pop:bbbbbbbbbb": 5, "act:save": 9, "skin:basic": 4})
            self.make(tmp, (today - timedelta(days=5)).isoformat(), {"act:pop:aaaaaaaaaa": 2, "act:pop:cccccccccc": 2})
            self.make(tmp, (today - timedelta(days=40)).isoformat(), {"act:pop:cccccccccc": 99})           # too old
            self.make(tmp, (today - timedelta(days=2)).isoformat(), {"act:pop:zz": 50, "act:pop:dddddddddd": "x"})   # not an id / not a number
            (Path(tmp) / "rate-20261009-abc").write_text("x")
            out = server_pop.popular(tmp, today=today)
        self.assertEqual([i["id"] for i in out["items"]], ["bbbbbbbbbb", "aaaaaaaaaa"])      # cccccccccc has 2 (< 3), the old one does not count
        self.assertNotIn("n", out["items"][0])
        self.assertEqual(set(out["items"][0]), {"id"})

    def test_no_stats_folder_gives_an_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pop.json"
            self.assertEqual(server_pop.main([str(Path(tmp) / "none"), str(target)]), 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["items"], [])

    def test_runs_on_the_servers_python_3_6_and_the_cron_calls_it(self):
        ast.parse((ROOT / "sites/atomou/server_pop.py").read_text(encoding="utf-8"), feature_version=(3, 6))
        sh = (ROOT / "sites/atomou/server_live.sh").read_text(encoding="utf-8")
        self.assertIn("sites/atomou/server_pop.py", sh)
        self.assertIn("pop.v1.json", sh)
        wf = (ROOT / ".github/workflows/atomou-server-live.yml").read_text(encoding="utf-8")
        self.assertIn("server_pop.py", wf)


if __name__ == "__main__":
    unittest.main()
