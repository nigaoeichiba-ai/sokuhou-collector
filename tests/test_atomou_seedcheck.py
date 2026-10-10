"""atomou: the seed checker accepts a card only when its official page shows the quote; the past and month-only dates are allowed; a page whose date is put there by a script is read in a browser."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import seedcheck  # noqa: E402

TODAY = date(2026, 10, 10)


def cand(**kw):
    c = {"title": "テストの映画 公開", "date": "2026-11-06", "kind": "開始", "group": "エンタメ・音楽・賞", "category": "映画", "subject": "テスト映画", "what": "映画の全国公開日",
         "place": "全国", "source_url": "https://official.example/film", "source_quote": "2026年11月6日(金)公開"}
    c.update(kw)
    return c


PAGES = {"https://official.example/film": "<p>テストの映画は 2026年11月6日(金)公開 です</p>".replace("<p>", "").replace("</p>", ""),
         "https://official.example/month": "放送は 2027年7月 より開始します", "https://official.example/past": "2026年10月9日(金)公開", "https://official.example/js": "読み込み中..."}


def run(cands, rendered=None):
    return seedcheck.check(cands, TODAY, existing=set(), page_of=PAGES.get, render_of=(lambda u: (rendered or {}).get(u, "")))


class Checking(unittest.TestCase):
    def test_a_quote_on_the_page_passes_and_the_item_is_complete(self):
        ok, bad = run([cand()])
        self.assertEqual((len(ok), bad), (1, []))
        self.assertTrue(ok[0]["verified"] and ok[0]["precision"] == "day" and ok[0]["ad_ok"] is True)

    def test_the_past_is_taken_too_a_film_that_opened_yesterday_counts_the_days_since(self):
        ok, bad = run([cand(title="昨日公開の映画", date="2026-10-09", source_url="https://official.example/past", source_quote="2026年10月9日(金)公開")])
        self.assertEqual((len(ok), bad), (1, []))
        _, bad = seedcheck.check([cand(date="2020-01-01")], TODAY, existing=set(), page_of=PAGES.get, render_of=lambda u: "")
        self.assertEqual(bad[0][1], "date outside window")      # but not without a limit

    def test_a_month_only_date_makes_a_card_of_month_precision(self):
        ok, bad = run([cand(title="来年のアニメ 放送開始", date="2027-07-01", precision="month", source_url="https://official.example/month", source_quote="2027年7月 より開始")])
        self.assertEqual((len(ok), bad), (1, []))
        self.assertEqual(ok[0]["precision"], "month")
        ok, bad = run([cand(title="月の違うアニメ", date="2027-08-01", precision="month", source_url="https://official.example/month", source_quote="2027年7月 より開始")])
        self.assertEqual(bad[0][1], "the quote does not contain the date")     # the month in the quote must be the card's month

    def test_a_quote_the_page_does_not_have_is_refused_unless_a_browser_shows_it(self):
        c = cand(title="スクリプトの映画", source_url="https://official.example/js", source_quote="2026年11月6日(金)公開")
        ok, bad = run([c])
        self.assertEqual((ok, bad[0][1]), ([], "quote not on the page"))
        ok, bad = run([c], rendered={"https://official.example/js": "公開日 2026年11月6日(金)公開 全国の劇場で"})
        self.assertEqual((len(ok), bad), (1, []))
        self.assertIn("ブラウザ", ok[0]["note"])

    def test_labels_and_groups_are_checked_like_the_catalogue_tests_do(self):
        self.assertEqual(run([cand(subject="とても長い題名のシリーズ名です")])[1][0][1], "subject must be 2-10 characters")
        self.assertEqual(run([cand(what="短い")])[1][0][1], "what must be 4-16 characters")
        self.assertEqual(run([cand(group="なんでも")])[1][0][1], "bad group")
        self.assertEqual(run([cand(precision="week")])[1][0][1], "bad precision")

    def test_the_same_title_and_day_is_taken_once(self):
        ok, bad = run([cand(), cand()])
        self.assertEqual((len(ok), bad[0][1]), (1, "duplicate"))


if __name__ == "__main__":
    unittest.main()
