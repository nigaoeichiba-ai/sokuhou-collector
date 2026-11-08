"""shiken-nittei.com, the design of 2026-11-08: the model refuses wrong data, the calendar files are well formed, and the pages agree with the dates."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"


def unfold(text: str) -> list[str]:
    out = []
    for line in text.split("\r\n"):
        if line.startswith(" ") and out:
            out[-1] += line[1:]
        elif line:
            out.append(line)
    return out


class ModelTest(unittest.TestCase):
    def test_a_pass_rate_that_is_not_passed_over_examinees_is_refused(self):
        from sites.shiken.gen import model
        good = model.pass_rate_rows("takken", 14)
        self.assertEqual(len(good), 14)
        saved = model.RATES["takken"][0]["rate"]
        model.RATES["takken"][0]["rate"] = 19.7
        try:
            with self.assertRaises(ValueError):
                model.pass_rate_rows("takken", 5)
        finally:
            model.RATES["takken"][0]["rate"] = saved

    def test_the_rate_of_the_applicants_is_computed_not_stored(self):
        from sites.shiken.gen import model
        row = model.pass_rate_rows("takken", 1)[0]
        self.assertNotIn("applicant_rate", row)
        self.assertAlmostEqual(model.applicant_basis_rate(row), 45821 / 306099 * 100)
        self.assertEqual(f"{model.applicant_basis_rate(row):.1f}", "15.0")
        self.assertEqual(f"{model.sit_rate(row):.1f}", "80.2")

    def test_a_fee_being_checked_has_no_amount(self):
        from sites.shiken.gen import model
        rows = {r["exam"]: r for r in model.fee_records()}
        for k in ("日商簿記", "FP技能検定", "漢検", "TOEIC L&R"):
            self.assertIsNone(rows[k]["amount"])
            self.assertEqual(rows[k]["status"], "checking")
        self.assertEqual(rows["宅建士"]["amount"], 8200)

    def test_every_event_has_a_source_and_ids_are_unique(self):
        from sites.shiken.gen import model
        self.assertEqual(len({e["id"] for e in model.EVENT_LIST}), len(model.EVENT_LIST))
        self.assertTrue(all(e["source"] for e in model.EVENT_LIST))

    def test_the_deadline_cards_are_in_order_and_a_time_comes_before_no_time_on_the_same_day(self):
        from sites.shiken.gen import model, common
        cards = model.deadline_events(8)
        self.assertEqual(len(cards), 8)
        keys = [(e["iso"], 0 if e["time"] else 1, e["time"]) for e in cards]
        self.assertEqual(keys, sorted(keys))
        self.assertTrue(all(common.left(e["iso"]) >= 0 for e in cards))

    def test_on_the_day_of_the_prototype_the_eight_cards_are_the_ones_of_the_spec(self):
        from sites.shiken.gen import model, common
        before = common.TODAY
        try:
            common.set_today("2026-11-08")
            names = [(e["name"], e["iso"], e["time"]) for e in model.deadline_events(8)]
        finally:
            common.set_today(before.isoformat())
        self.assertEqual(names[0], ("TOEIC L&R 12月19日回", "2026-11-11", "15:00"))
        self.assertEqual([n[1] for n in names], ["2026-11-11", "2026-11-26", "2026-11-27", "2026-12-01", "2026-12-09", "2026-12-14", "2027-01-07", "2027-01-10"])
        self.assertEqual(names[3][2], "17:30")


class CalendarFileTest(unittest.TestCase):
    def test_every_file_is_well_formed(self):
        from sites.shiken.gen import ics, model
        files = ics.files()
        self.assertEqual(len(files), len(model.EVENT_LIST))
        for rel, text in files.items():
            self.assertTrue(re.fullmatch(r"ics/shiken-[a-z0-9-]+\.ics", rel), rel)          # no Japanese in a file name
            self.assertTrue(text.endswith("\r\n"))
            for raw in text.split("\r\n")[:-1]:
                self.assertLessEqual(len(raw.encode("utf-8")), 75, rel)
            lines = unfold(text)
            self.assertEqual(lines[0], "BEGIN:VCALENDAR")
            self.assertEqual(lines[-1], "END:VCALENDAR")
            self.assertIn("VERSION:2.0", lines)
            self.assertTrue(any(l.startswith("UID:") and l.endswith("@shiken-nittei.com") for l in lines), rel)
            begins = [l for l in lines if l.startswith("BEGIN:")]
            ends = [l for l in lines if l.startswith("END:")]
            self.assertEqual(sorted(b[6:] for b in begins), sorted(e[4:] for e in ends), rel)

    def test_a_timed_event_has_the_zone_and_a_whole_day_event_has_a_date(self):
        from sites.shiken.gen import ics, model
        lines = unfold(ics.ics(model.BY_ID["toeic-20261219-deadline"]))
        self.assertIn("DTSTART;TZID=Asia/Tokyo:20261111T150000", lines)
        self.assertIn("TZID:Asia/Tokyo", lines)
        self.assertEqual([l for l in lines if l.startswith("TRIGGER")], ["TRIGGER:-P7D", "TRIGGER:-P1D"])      # a deadline: 7 days and 1 day before
        lines = unfold(ics.ics(model.BY_ID["kangoshi-deadline"]))
        self.assertIn("DTSTART;VALUE=DATE:20261127", lines)
        self.assertIn("DTEND;VALUE=DATE:20261128", lines)
        self.assertEqual([l for l in lines if l.startswith("TRIGGER")], ["TRIGGER:-P7D", "TRIGGER:-P1D"])
        self.assertTrue(any(l.startswith("SUMMARY:［申込締切］") for l in lines))
        lines = unfold(ics.ics(model.BY_ID["takken-exam"]))
        self.assertIn("DTSTART;TZID=Asia/Tokyo:20261018T130000", lines)
        self.assertIn("DTEND;TZID=Asia/Tokyo:20261018T150000", lines)
        self.assertEqual([l for l in lines if l.startswith("TRIGGER")], ["TRIGGER:-P1D"])                   # an exam day: 1 day before

    def test_the_files_do_not_change_from_day_to_day(self):
        from sites.shiken.gen import ics, common
        a = ics.files()
        before = common.TODAY
        try:
            common.set_today("2027-03-01")
            b = ics.files()
        finally:
            common.set_today(before.isoformat())
        self.assertEqual(a, b)

    def test_the_google_calendar_link_has_the_time_in_japan(self):
        from sites.shiken.gen import ics, model
        url = ics.gcal(model.BY_ID["toeic-20261219-deadline"])
        self.assertTrue(url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE&text="))
        self.assertIn("dates=20261111T150000/20261111T153000", url)
        self.assertIn("ctz=Asia%2FTokyo", url)
        self.assertIn("details=", url)
        self.assertIn("dates=20261127/20261128", ics.gcal(model.BY_ID["kangoshi-deadline"]))


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.shiken import gen
        gen.write()
        cls.pages, _ = newsite.build_pages(SITE, release=True, strict_seo=True)
        cls.html = {k: v for k, v in cls.pages.items() if isinstance(v, str) and k.endswith(".html")}

    def test_the_urls_of_the_30_pages_stay_and_the_two_features_are_added(self):
        for path in ("", "schedule", "deadlines", "nyushi", "koko", "method", "corrections", "takken", "gyosei", "sharoshi", "boki", "fp", "eiken", "kaigo-fukushi", "kangoshi",
                     "kyotsu", "kyotsu-tsuishi", "kokkoritsu", "zenki-koki", "flow", "postmark", "boki-net", "cbt", "fees", "results", "yama", "komuin", "minkan", "goukaku-ritsu", "nendo"):
            self.assertIn((path + "/" if path else "") + "index.html", self.html, path)
        self.assertIn("yomimono/index.html", self.html)
        self.assertIn("tokushu-nyushi/index.html", self.html)

    def test_the_home_page_has_the_blocks_in_the_fixed_order(self):
        h = self.html["index.html"]
        order = ['id="q"'] + [f"<h2>{t}</h2>" for t in ("申込締切が近い順", "目的から探す", "マイ試験", "あなたはどの段階ですか", "今日の特集", "データで見る", "特集")]
        pos = [h.index(x) for x in order]
        self.assertEqual(pos, sorted(pos))
        self.assertEqual(h.count('<div class="pcard">'), 6)
        self.assertEqual(h.count('<article class="dcard'), 8)

    def test_the_three_views_draw_the_same_eight_deadlines(self):
        h = self.html["index.html"]
        self.assertEqual(h.count('<div class="tl-name">'), 8)
        self.assertEqual(len(re.findall(r'data-event="', h)), 8)
        ids = re.search(r'"cards":\[(.*?)\]', h).group(1).split(",")
        self.assertEqual(len(ids), 8)                                         # the month calendar reads these eight from the page's data

    def test_the_urgent_band_shows_only_when_a_deadline_is_within_7_days(self):
        from sites.shiken.gen import common, ui, model
        before = common.TODAY
        try:
            common.set_today("2026-11-08")
            self.assertIn("まもなく締切", ui.urgent_band(model.deadline_events(8)))
            common.set_today("2026-11-12")
            self.assertEqual(ui.urgent_band(model.deadline_events(8)), "")
        finally:
            common.set_today(before.isoformat())

    def test_the_counter_says_it_with_words_as_well_as_colour(self):
        from sites.shiken.gen import ui
        self.assertEqual(ui.state(3, "deadline")[:2], ("red", "まもなく締切"))
        self.assertEqual(ui.state(7, "deadline")[0], "red")
        self.assertEqual(ui.state(8, "deadline")[0], "yellow")
        self.assertEqual(ui.state(30, "deadline")[0], "yellow")
        self.assertEqual(ui.state(31, "deadline")[0], "blue")
        self.assertEqual(ui.state(0, "deadline")[2], "本日")
        self.assertEqual(ui.state(-2, "deadline")[2], "2日前に終了")

    def test_the_detail_page_has_no_block_without_data_and_no_invented_date(self):
        text = re.sub(r"<[^>]+>", "", self.html["takken/index.html"])
        self.assertIn("令和9年度：日程は未発表です", text)
        self.assertNotIn("賃貸不動産経営管理士", text)                         # no card without a date and a page behind it
        self.assertNotIn("PR", text)                                          # the affiliate boxes are not built before approval
        for needle in ("よくある失敗 3例", "総コスト計算機", "逆算プランナー"):
            self.assertIn(needle, text)

    def test_the_two_bases_of_the_pass_rate_are_on_the_feature_and_the_official_one_is_named(self):
        text = re.sub(r"<[^>]+>", "", self.html["goukaku-ritsu/index.html"])
        self.assertIn("45,821 ÷ 245,462", text)
        self.assertIn("45,821 ÷ 306,099", text)
        self.assertIn("18.7％", text)
        self.assertIn("約15.0％", text)
        self.assertIn("受験者基準（宅建の公式の合格率）", text)
        self.assertNotRegex(text, r"申込者基準[^。]{0,12}公式の合格率です")

    def test_the_fees_without_an_amount_say_so(self):
        import html as _html
        text = _html.unescape(re.sub(r"<[^>]+>", " ", self.html["fees/index.html"]))
        for k in ("日商簿記", "FP技能検定", "漢検", "TOEIC L&R"):
            self.assertRegex(text, k + r"\s+確認中")

    def test_a_table_does_not_scroll_sideways_on_a_phone_in_the_new_pages(self):
        self.assertIn('<table class="stack">', self.html["takken/index.html"])
        css = (SITE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIn("table.stack td::before", css)


if __name__ == "__main__":
    unittest.main()
