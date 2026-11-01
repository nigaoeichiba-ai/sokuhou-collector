import unittest
from datetime import date

from sites.atomou import results_queue


class NotHeldTest(unittest.TestCase):
    def _entry(self, **extra):
        e = {"title": "試合", "date": "2026-10-29", "date_end": None, "precision": "day", "quiet": False, "kind": "開催",
             "group": "スポーツ", "place": "", "keep": True}
        e.update(extra)
        return e

    def test_held_day_waits_for_a_result(self):
        rows = results_queue.queue([self._entry()], date(2026, 11, 2))
        self.assertEqual(len(rows), 1)

    def test_day_that_was_not_held_is_not_waiting(self):
        rows = results_queue.queue([self._entry(not_held=True)], date(2026, 11, 2))
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
