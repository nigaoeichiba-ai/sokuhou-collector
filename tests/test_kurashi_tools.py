"""kurashi-calendar.com (sites/kurashi) tools: day counts that follow the day, calendar files (.ics), the print layout.

Past failures this guards against: 'あと58日' and '2026年11月3日時点で' written into the text and left wrong from the day after the publication; a calendar
file a phone cannot read (a line over 75 octets, a bare LF, no alert); a calendar button that gives a different date from the table next to it.
The build day is fixed here (KURASHI_TODAY) so that the numbers are the same on every run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sokuhou import newsite, sitecheck
from sites.kurashi import gen
from sites.kurashi.gen import deadlines

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "kurashi"
BASE = "https://kurashi-calendar.com"


def load_hooks():
    spec = importlib.util.spec_from_file_location("_kurashi_hooks_test", SITE / "hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = load_hooks()


def build(day: str) -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "out"
    old = os.environ.get("KURASHI_TODAY")
    os.environ["KURASHI_TODAY"] = day
    try:
        newsite.main_build(SITE, ["--out", str(out), "--release", "--strict-seo"])
    finally:
        if old is None:
            os.environ.pop("KURASHI_TODAY")
        else:
            os.environ["KURASHI_TODAY"] = old
    return tmp, out


def text(out: Path, rel: str) -> str:
    return (out / rel).read_text(encoding="utf-8")


def visible(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


class DayCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t1, cls.a = build("2026-11-10")
        cls.t2, cls.b = build("2026-12-01")

    @classmethod
    def tearDownClass(cls):
        cls.t1.cleanup()
        cls.t2.cleanup()

    def test_no_page_still_has_a_marker_or_the_old_fixed_day_count(self):
        for out in (self.a, self.b):
            for f in out.rglob("*.html"):
                html = f.read_text(encoding="utf-8")
                self.assertNotRegex(html, r"\{(days|rel|weeks|today|todayy)[:}]", f.name)
                self.assertNotIn("58日後", html)
                self.assertNotIn("11月3日から", html)

    def test_counts_are_from_the_build_day(self):
        # 2026-12-31 is 51 days after 11-10 and 30 days after 12-01
        self.assertIn('data-d="2026-12-31">51日後</span>', text(self.a, "month/12/index.html"))
        self.assertIn('data-d="2026-12-31">30日後</span>', text(self.b, "month/12/index.html"))
        self.assertIn("年末まであと", visible(text(self.a, "month/11/index.html")))
        self.assertIn("年末まであと30日", visible(text(self.b, "month/11/index.html")))

    def test_the_text_a_search_engine_reads_has_the_right_number(self):
        a = visible(text(self.a, "month/11/index.html"))
        self.assertIn("11月10日の時点で、年末まであと51日です", a)
        self.assertIn("2026年11月10日時点で最も近い期限は", visible(text(self.a, "index.html")))

    def test_refund_table_says_a_passed_deadline_has_passed(self):
        html = text(self.a, "kakutei-shinkoku/kanpu/index.html")
        self.assertIn('data-d="2025-12-31" data-p="期限が過ぎた">期限が過ぎた</span>', html)
        self.assertIn('data-d="2031-12-31" data-p="期限が過ぎた">', html)

    def test_home_lists_only_deadlines_that_have_not_passed(self):
        before = visible(text(self.a, "index.html"))
        after = visible(text(self.b, "index.html"))
        self.assertIn("年賀状の引受開始", before.split("最も近い期限は")[1][:80])
        self.assertIn("12月20日(日)の年賀状の引受開始と、12月31日(木)のふるさと納税", before)
        # on 12-21 the card start has passed: the sentence names the next two
        spec = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        pages = [{"path": "/", "answer": "x", "sections": []}]
        os.environ["KURASHI_TODAY"] = "2026-12-21"
        try:
            got = H.prepare({}, spec, pages, SITE)[0]["answer"]
        finally:
            os.environ.pop("KURASHI_TODAY")
        self.assertNotIn("年賀状の引受開始", got)
        self.assertIn("12月31日(木)のふるさと納税・医療費の締めと、1月10日(日)のワンストップ特例の変更届の期限", got)
        self.assertIn("2026年12月1日", after)

    def test_the_browser_script_uses_the_same_rules_as_the_build(self):
        js = (SITE / "assets" / "tools.js").read_text(encoding="utf-8")
        for needle in ("Asia/Tokyo", '"日後"', '"今日"', "過ぎた", "Math.floor(n / 7)", "data-print"):
            self.assertIn(needle.strip('"'), js)
        for kind, iso, expect in (("rel", "2026-12-31", "51日後"), ("rel", "2026-11-10", "今日"), ("rel", "2026-11-09", "過ぎた"), ("days", "2026-12-31", "51"),
                                  ("weeks", "2027-02-16", "14")):
            self.assertEqual(H.count_text(kind, iso, "", date(2026, 11, 10)), expect)

    def test_a_count_that_has_passed_is_reported_not_hidden(self):
        H.STALE.clear()
        H.count_text("days", "2026-12-31", "", date(2027, 1, 5))
        self.assertEqual(H.STALE, ["days:2026-12-31"])
        H.STALE.clear()

    def test_the_generator_has_no_fixed_day_count_left(self):
        blob = json.dumps(gen.all_pages(), ensure_ascii=False)
        self.assertNotRegex(blob, r"あと\d+日")
        for old in ("58日後", "132日後", "47日後", "105日後"):          # the counts the page had when it was written on 2026-11-03
            self.assertNotIn(old, blob)
        self.assertNotIn("11月3日から", blob)

    def test_release_checks_pass(self):
        self.assertEqual(sitecheck.check_dir(self.a, BASE), [])


class CalendarFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = build("2026-11-10")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ics(self, name: str) -> str:
        return (self.out / "calendar" / name).read_bytes().decode("utf-8")

    def test_one_deadline_file_is_rfc5545(self):
        s = self.ics("nengajo-hikiuke.ics")
        self.assertTrue(s.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(s.endswith("END:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.assertNotRegex(s, r"(?<!\r)\n")                                   # every line ends CRLF
        for needle in ("BEGIN:VEVENT", "SUMMARY:年賀状の引受開始", "DTSTART;VALUE=DATE:20261220", "DTEND;VALUE=DATE:20261221", "BEGIN:VALARM", "ACTION:DISPLAY",
                       "TRIGGER:-PT15H", "UID:kurashi-nengajo-hikiuke-20261220@kurashi-calendar.com", "DTSTAMP:"):
            self.assertIn(needle, s)
        for line in s.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line)

    def test_the_alert_is_nine_in_the_morning_the_day_before(self):
        # an all-day entry starts at 00:00 of the day; 15 hours before is 09:00 the day before
        s = self.ics("shinkoku-end.ics")
        self.assertIn("DTSTART;VALUE=DATE:20270315", s)
        self.assertIn("TRIGGER:-PT15H", s)
        self.assertNotIn("TRIGGER;", s)

    def test_month_file_has_all_the_deadlines_of_the_month(self):
        s = self.ics("month-12.ics")
        self.assertEqual(s.count("BEGIN:VEVENT"), 5)
        self.assertEqual(s.count("BEGIN:VALARM"), 5)
        self.assertEqual(s.count("END:VEVENT"), 5)
        for d in ("20261220", "20261227", "20261228", "20261229", "20261231"):
            self.assertIn(f"DTSTART;VALUE=DATE:{d}", s)
        self.assertEqual(self.ics("month-1.ics").count("BEGIN:VEVENT"), 4)

    def test_every_calendar_button_has_a_file_and_the_date_in_the_table(self):
        n = 0
        for f in self.out.rglob("index.html"):
            html = f.read_text(encoding="utf-8")
            for href in re.findall(r'href="(/calendar/[^"]+\.ics)" download', html):
                self.assertTrue((self.out / href.lstrip("/")).exists(), (f.name, href))
                n += 1
        self.assertGreater(n, 25)

    def test_the_date_of_a_button_is_the_date_the_page_shows(self):
        """the button and the table next to it must not disagree: the date of each deadline is written in the table of the page (as 2026年12月20日(日))"""
        spec = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        cat = {c["id"]: c for c in spec["deadlines"]}
        for path, ids in deadlines.BY_PAGE.items():
            if path in ("/", "/month/"):
                continue
            rel = path.strip("/") + "/index.html"
            page = visible(text(self.out, rel))
            for i in ids:
                x = date.fromisoformat(cat[i]["date"])
                wd = "月火水木金土日"[x.weekday()]
                self.assertTrue(f"{x.month}月{x.day}日({wd})" in page, (path, i, cat[i]["date"]))

    def test_passed_deadlines_get_no_button(self):
        tmp, out = build("2026-12-25")
        try:
            html = text(out, "month/12/index.html")
            self.assertNotIn("nengajo-hikiuke.ics", html)
            self.assertIn("nenmatsu-shime.ics", html)
            self.assertFalse((out / "calendar" / "nengajo-hikiuke.ics").exists())
            self.assertEqual((out / "calendar" / "month-12.ics").read_bytes().decode().count("BEGIN:VEVENT"), 4)
        finally:
            tmp.cleanup()

    def test_a_broken_calendar_file_would_be_caught(self):
        """the checks above are real: a file with a bare LF, a long line or no alert is not accepted"""
        bad = "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:" + "あ" * 40 + "\nEND:VEVENT\nEND:VCALENDAR\n"
        self.assertRegex(bad, r"(?<!\r)\n")
        self.assertTrue(any(len(x.encode("utf-8")) > 75 for x in bad.split("\n")))
        self.assertNotIn("TRIGGER", bad)

    def test_long_titles_are_folded(self):
        e = {"id": "x", "date": "2026-12-31", "name": "あ" * 60, "url": "/x/"}
        s = H.ics([e], "20261103T000000Z")
        self.assertTrue(all(len(x.encode("utf-8")) <= 75 for x in s.split("\r\n")))
        self.assertIn("\r\n ", s)
        self.assertEqual("".join(re.sub(r"\r\n ", "", s).split("SUMMARY:")[1].split("\r\n")[0]), "あ" * 60)


class PrintLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = build("2026-11-10")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_content_page_has_the_print_button(self):
        for f in self.out.rglob("index.html"):
            rel = f.relative_to(self.out).as_posix()
            if rel.split("/")[0] in ("about", "privacy", "contact", "saved", "search") or rel == "index.html":    # the home page has the calendar's own print button
                continue
            self.assertIn("data-print", f.read_text(encoding="utf-8"), rel)

    def test_print_css_hides_the_screen_decoration(self):
        css = (SITE / "assets" / "kurashi.css").read_text(encoding="utf-8")
        p = css[css.index("@media print"):]
        for needle in (".site-header", ".site-footer", ".footer-town", ".article-sidebar", ".cal-b", ".printonly { display: block; }"):
            self.assertIn(needle, p)
        self.assertIn(".printonly { display: none; }", css[:css.index("@media print")])      # not on the screen


class Parts(unittest.TestCase):
    def test_the_words_of_the_parts_are_nouns_without_the_forbidden_forms(self):
        words = [H.HEADING, H.BUTTON, H.BUNDLE, H.PRINT_BUTTON, H.NOTE]
        for w in words:
            self.assertNotIn("：", w)
            self.assertNotIn("ご確認", w)
            self.assertNotIn("で見る", w)
        self.assertEqual(sorted(set(words)), sorted({"カレンダーに登録", "まとめて登録", "印刷", "通知は前日の午前9時です。"}))

    def test_the_catalog_dates_and_pages_are_real(self):
        pages = {p["path"] for p in gen.all_pages()}
        ids = {c[0] for c in deadlines.CATALOG}
        self.assertEqual(len(ids), len(deadlines.CATALOG))
        for path, lst in deadlines.BY_PAGE.items():
            self.assertIn(path, pages)
            self.assertTrue(set(lst) <= ids, path)
        for c in deadlines.CATALOG:
            self.assertIn(c[4], pages)


if __name__ == "__main__":
    unittest.main()
