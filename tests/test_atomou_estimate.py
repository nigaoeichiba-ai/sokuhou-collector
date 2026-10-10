"""atomou: a yearly event whose day of this year is not official yet is shown as an estimate ("例年12月31日ごろ", "(予想)") with the days of the earlier years, and the estimate gives way when the official day is known."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, seedcheck  # noqa: E402

TODAY = date(2026, 10, 10)


def item(title, day, **kw):
    it = {"title": title, "date": day, "date_end": None, "precision": "day", "kind": "開催", "group": "エンタメ・音楽・賞", "category": "歌番組", "subject": "紅白歌合戦", "what": "年末の歌合戦",
          "place": "全国", "region": "全国", "source_url": "https://official.example/kouhaku", "source_quote": "2025年12月31日", "checked_on": "2026-10-10", "sensitivity": "none", "ad_ok": True,
          "son_toku": False, "note": "", "verified": True}
    it.update(kw)
    return it


def est(**kw):
    base = dict(estimated=True, typical="例年12月31日ごろ", series="kouhaku-2026", history=["2025-12-31", "2024-12-31", "2023-12-31"], keep=True)
    base.update(kw)
    return item("NHK紅白歌合戦(予想)", "2026-12-31", **base)


def built(items):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "seed_est_2026-10-10.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return catalog.build_catalog(TODAY, Path(d))


class Estimating(unittest.TestCase):
    def test_an_estimate_is_in_the_catalogue_with_its_history_newest_first(self):
        entries, _ = built([est()])
        e = entries[0]
        self.assertEqual((e["estimated"], e["typical"], e["series"]), (True, "例年12月31日ごろ", "kouhaku-2026"))
        self.assertEqual(e["history"], ["2025-12-31", "2024-12-31", "2023-12-31"])
        pub = catalog.public_json(entries)[0]
        self.assertTrue(pub["estimated"] and pub["typical"])

    def test_the_official_day_of_the_same_cycle_takes_the_place_of_the_estimate(self):
        entries, rejects = built([est(), item("NHK紅白歌合戦", "2026-12-31", series="kouhaku-2026", keep=True)])
        self.assertEqual([e["title"] for e in entries], ["NHK紅白歌合戦"])
        self.assertEqual(rejects["予想を確定の日で置き換え"], 1)
        entries, _ = built([est(), item("別の年の紅白", "2025-12-31", series="kouhaku-2025", keep=True)])
        self.assertEqual(len(entries), 2)                       # another cycle does not replace it

    def test_the_card_says_it_is_an_estimate_and_shows_the_usual_time_not_a_day(self):
        entries, _ = built([est()])
        html = build.card_html(entries[0])
        self.assertIn('data-est="1"', html)
        self.assertIn("(予想)", html)
        self.assertIn("例年12月31日ごろ", html)
        self.assertNotIn("2026年12月31日", html)
        plain = build.card_html(built([item("確定の行事", "2026-12-31")])[0][0])
        self.assertNotIn("data-est", plain)
        self.assertNotIn("(予想)", plain)


class Checking(unittest.TestCase):
    PAGES = {"https://official.example/kouhaku": "NHK紅白歌合戦は 2025年12月31日 に放送しました。2024年12月31日、2023年12月31日にも放送しました。"}

    def run_check(self, c):
        return seedcheck.check([c], TODAY, existing=set(), page_of=self.PAGES.get, render_of=lambda u: "")

    def cand(self, **kw):
        c = {"title": "NHK紅白歌合戦(予想)", "date": "2026-12-31", "kind": "開催", "group": "エンタメ・音楽・賞", "category": "歌番組", "subject": "紅白歌合戦", "what": "年末の歌合戦", "place": "全国",
             "source_url": "https://official.example/kouhaku", "source_quote": "2025年12月31日 に放送しました", "estimated": True, "typical": "例年12月31日ごろ", "series": "kouhaku-2026",
             "history": ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"], "keep": True}
        c.update(kw)
        return c

    def test_an_estimate_passes_when_the_page_shows_the_newest_earlier_day_and_keeps_only_the_days_it_shows(self):
        ok, bad = self.run_check(self.cand())
        self.assertEqual((len(ok), bad), (1, []))
        self.assertEqual(ok[0]["history"], ["2025-12-31", "2024-12-31", "2023-12-31"])        # 2022 is not on the page: it is not kept
        self.assertTrue(ok[0]["estimated"] and ok[0]["verified"])

    def test_an_estimate_without_history_or_in_the_past_or_with_a_wrong_quote_is_refused(self):
        self.assertEqual(self.run_check(self.cand(history=[]))[1][0][1], "an estimate needs typical, series and history")
        self.assertEqual(self.run_check(self.cand(date="2026-01-01"))[1][0][1], "an estimate must be a short phrase and a day to come")
        self.assertEqual(self.run_check(self.cand(source_quote="2024年12月31日、2023年12月31日にも放送しました", history=["2025-12-31"]))[1][0][1], "the quote does not contain the newest earlier day")


if __name__ == "__main__":
    unittest.main()
