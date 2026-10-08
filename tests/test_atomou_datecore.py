"""atomou: the date arithmetic (sites/atomou/datecore.py) against the hand-verified vectors, plus the properties that must always hold."""
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import datecore as dc  # noqa: E402

VECTORS = json.loads((ROOT / "tests" / "fixtures" / "atomou" / "date_vectors.json").read_text(encoding="utf-8"))


def d(s: str) -> date:
    y, m, dd = s.split("-")
    return date(int(y), int(m), int(dd))


class DateVectors(unittest.TestCase):
    def test_ymd_and_total(self):
        for c in VECTORS["ymd"]:
            with self.subTest(c=c):
                a, b = d(c["a"]), d(c["b"])
                self.assertEqual(dc.ymd(a, b), (c["y"], c["m"], c["d"]))
                self.assertEqual(dc.total_days(a, b), c["total"])

    def test_countdown(self):
        for c in VECTORS["countdown"]:
            with self.subTest(c=c):
                r = dc.countdown(d(c["target"]), d(c["today"]))
                self.assertEqual((r["dir"], r["big"], r["sub"]), (c["dir"], c["big"], c["sub"]))

    def test_countdown_precision(self):
        for c in VECTORS["countdown_precision"]:
            with self.subTest(c=c):
                r = dc.countdown(d(c["target"]), d(c["today"]), c["precision"])
                self.assertEqual((r["dir"], r["big"]), (c["dir"], c["big"]))
                self.assertTrue(r["approx"])

    def test_day_of_year_and_fiscal_year(self):
        for c in VECTORS["day_of_year"]:
            self.assertEqual(dc.day_of_year(d(c["d"])), (c["n"], c["left"]))
        for c in VECTORS["fiscal_year"]:
            self.assertEqual(dc.fiscal_year(d(c["d"])), (c["start"], c["n"], c["left"]))

    def test_next_thousand(self):
        for c in VECTORS["next_thousand"]:
            n, when = dc.next_thousand(d(c["start"]), d(c["today"]))
            self.assertEqual((n, when.isoformat()), (c["days"], c["date"]))

    def test_wareki(self):
        for c in VECTORS["wareki"]:
            self.assertEqual(dc.wareki_to_year(c["era"], c["n"]), c["y"])


class DateProperties(unittest.TestCase):
    def test_symmetric_and_consistent(self):
        """The breakdown does not depend on the order of the two dates, and adding it back to the earlier date never overshoots the later one."""
        for a in (date(2024, 2, 29), date(2026, 1, 31), date(2026, 12, 31), date(2000, 3, 1), date(1999, 12, 31)):
            for off in (0, 1, 27, 28, 29, 30, 31, 59, 365, 366, 1000, 20899):
                b = a + timedelta(days=off)
                y, m, dd = dc.ymd(a, b)
                self.assertEqual(dc.ymd(b, a), (y, m, dd))
                base = dc.add_months(a, y * 12 + m)
                self.assertLessEqual(base, b)
                self.assertEqual((b - base).days, dd)
                self.assertLess(dd, 32)

    def test_countdown_direction_matches_total(self):
        today = date(2026, 10, 8)
        for off in (-400, -100, -99, -1, 0, 1, 99, 100, 400):
            r = dc.countdown(today + timedelta(days=off), today)
            self.assertEqual(r["total"], off)
            self.assertEqual(r["dir"], "today" if off == 0 else ("ato" if off > 0 else "mou"))
            self.assertEqual(bool(r["sub"]), abs(off) > dc.SHORT_DAYS)  # the total shows next to the years/months/days only


if __name__ == "__main__":
    unittest.main()
