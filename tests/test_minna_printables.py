"""Print versions (A4 coloring pages, postcard-size New Year items) are built, are real PDFs and are linked only where they make sense."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト運営", "contact_own": True, "adsense_pub_id": None}


class PrintablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(CFG, cls.out, release=True, today=date(2026, 10, 7))
        cls.items, _ = build.load_data()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pdf_kinds_follow_touch_and_genre(self):
        by = {i["id"]: i for i in self.items}
        self.assertEqual(build.pdf_kinds(by["coloring-newyear-lineart-daruma"]), ["a4"])
        self.assertEqual(build.pdf_kinds(by["eto-sheep-kawaii-kite"]), ["hagaki"])
        self.assertEqual(build.pdf_kinds(by["cat-pose-wave"]), [])            # an ordinary animal pose has no print version
        self.assertEqual(build.pdf_kinds(by["r-joy"]), [])

    def test_every_promised_pdf_exists_is_a_pdf_and_is_linked(self):
        n = 0
        for it in self.items:
            html = (self.out / "illust" / it["id"] / "index.html").read_text(encoding="utf-8")
            kinds = build.pdf_kinds(it)
            for k in kinds:
                rel = f"files/{it['id']}-{k}.pdf"
                self.assertIn(rel, self.files)
                self.assertIn(f"/{rel}", html)
                data = (self.out / rel).read_bytes()
                self.assertTrue(data.startswith(b"%PDF"), rel)
                self.assertLess(len(data), 900_000, f"{rel} is too heavy: {len(data)} bytes")
                n += 1
            if not kinds:
                self.assertNotIn("-a4.pdf", html)
                self.assertNotIn("-hagaki.pdf", html)
        self.assertGreater(n, 20)

    def test_the_a4_page_is_a4_in_proportion(self):
        import re
        data = (self.out / "files" / "coloring-newyear-lineart-daruma-a4.pdf").read_bytes()
        box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", data)
        self.assertTrue(box)
        w, h = float(box.group(1)), float(box.group(2))
        self.assertAlmostEqual(w / h, 210 / 297, delta=0.01)


class HolidayTest(unittest.TestCase):
    """The holidays are computed, so they are checked against years whose lists are well known (substitute and sandwiched holidays included)."""

    def md(self, year):
        from sites.minna import printables
        return {(d.month, d.day) for d in printables.holidays(year)}

    def test_2025_including_substitute_holidays(self):
        self.assertEqual(self.md(2025), {(1, 1), (1, 13), (2, 11), (2, 23), (2, 24), (3, 20), (4, 29), (5, 3), (5, 4), (5, 5), (5, 6), (7, 21), (8, 11), (9, 15), (9, 23), (10, 13), (11, 3), (11, 23), (11, 24)})

    def test_2026_including_the_sandwiched_national_holiday(self):
        self.assertEqual(self.md(2026), {(1, 1), (1, 12), (2, 11), (2, 23), (3, 20), (4, 29), (5, 3), (5, 4), (5, 5), (5, 6), (7, 20), (8, 11), (9, 21), (9, 22), (9, 23), (10, 12), (11, 3), (11, 23)})

    def test_2027_the_year_of_the_sheep(self):
        from sites.minna import printables
        h = printables.holidays(2027)
        self.assertEqual(len(h), 17)
        self.assertEqual(h[date(2027, 3, 22)], "振替休日")            # 21 March is a Sunday
        self.assertEqual(h[date(2027, 1, 11)], "成人の日")
        self.assertNotIn(date(2027, 9, 21), h)                        # not sandwiched: 20 Sep and 23 Sep are three days apart


class CalendarBuildTest(unittest.TestCase):
    def test_calendar_pages_and_pdfs_are_built_and_linked(self):
        from sites.minna import printables
        if not printables.find_font():
            self.skipTest("no Japanese font on this machine (CI installs one)")
        tmp = tempfile.TemporaryDirectory()
        try:
            out = Path(tmp.name) / "site"
            files = build.render_site(CFG, out, release=True, today=date(2026, 10, 7))
            self.assertIn("printables/calendar-2027/index.html", files)
            self.assertIn("printables/index.html", files)
            html = (out / "printables" / "calendar-2027" / "index.html").read_text(encoding="utf-8")
            for rel in ("files/calendar/2027-hitsuji-01.pdf", "files/calendar/2027-hitsuji-12.pdf", "files/calendar/2027-hitsuji-all.pdf", "files/calendar/2027-dobutsu-06.pdf"):
                self.assertIn(rel, files)
                self.assertIn("/" + rel, html)
                self.assertTrue((out / rel).read_bytes().startswith(b"%PDF"))
            self.assertGreater((out / "files/calendar/2027-hitsuji-all.pdf").stat().st_size, (out / "files/calendar/2027-hitsuji-01.pdf").stat().st_size * 6)
            # a different build date picks the right year: before September it is this year
            self.assertEqual(build.calendar_year(date(2026, 8, 31)), 2026)
            self.assertEqual(build.calendar_year(date(2026, 9, 1)), 2027)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
