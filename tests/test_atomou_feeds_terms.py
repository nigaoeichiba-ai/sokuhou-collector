"""atomou: what the calendar feeds (cal/*.ics) may carry, after the terms of the sources were read (2026-10-12, atomou/docs/terms_ics_feeds_2026-10-12.md): nothing from a site whose terms forbid
commercial use of its information (日本ラグビー協会, 日本卓球協会), no estimate (a guessed day looks fixed in a calendar), and the Cabinet Office is named where holidays are."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, feeds  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 12)


def day(**kw):
    e = {"id": "abcdef0123", "title": "テスト大会", "date": "2026-11-03", "precision": "day", "quiet": False, "estimated": False, "group": "スポーツ", "source_url": "https://example.jp/a"}
    e.update(kw)
    return e


class Feedable(unittest.TestCase):
    def test_an_ordinary_day_is_in(self):
        self.assertTrue(feeds.feedable(day()))

    def test_the_two_sites_whose_terms_forbid_commercial_use_are_out_with_their_subdomains(self):
        for url in ("https://www.rugby-japan.jp/news/1/", "https://rugby-japan.jp/x", "https://www.jtta.or.jp/schedule", "https://news.jtta.or.jp/a"):
            self.assertFalse(feeds.feedable(day(source_url=url)), url)
        for url in ("https://www.jfa.jp/x", "https://notrugby-japan.jp/x", "https://example.jp/jtta.or.jp"):
            self.assertTrue(feeds.feedable(day(source_url=url)), url)       # a similar name is not the site; the name in a path is not the host

    def test_an_estimate_a_quiet_day_and_a_month_are_out(self):
        self.assertFalse(feeds.feedable(day(estimated=True)))
        self.assertFalse(feeds.feedable(day(quiet=True)))
        self.assertFalse(feeds.feedable(day(precision="month")))


class InTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=True, today=TODAY)
        cls.entries, _ = catalog.build_catalog(TODAY)

    def test_no_event_of_the_two_sites_or_of_an_estimate_is_in_any_feed(self):
        bad = {e["id"] for e in self.entries if e.get("estimated") or any(d in (e.get("source_url") or "") for d in feeds.NO_FEED_DOMAINS)}
        self.assertTrue(bad)        # the catalogue does have such days: the check is not empty
        for k, v in self.pages.items():
            if k.startswith("cal/") and k.endswith(".ics"):
                for i in bad:
                    self.assertNotIn(f"UID:{i}@", v, k)

    def test_the_feed_with_holidays_names_the_cabinet_office(self):
        all_ics = self.pages["cal/all.ics"]
        self.assertIn("内閣府「国民の祝日について」", all_ics.replace("\r\n ", ""))
        self.assertIn("公共データ利用規約", all_ics.replace("\r\n ", ""))


if __name__ == "__main__":
    unittest.main()
