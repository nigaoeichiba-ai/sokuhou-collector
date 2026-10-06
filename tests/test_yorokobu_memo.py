import unittest
from datetime import date

from sites.yorokobu import giftcal


class GiftCalendarTest(unittest.TestCase):
    def test_dates_of_the_shared_gift_days(self):
        d = {g["slug"]: g["date"] for g in giftcal.gift_days(2027)}
        self.assertEqual(d["mothers-day"], date(2027, 5, 9))          # 2nd Sunday of May
        self.assertEqual(d["fathers-day"], date(2027, 6, 20))         # 3rd Sunday of June
        self.assertEqual(d["respect-for-aged-day"], date(2027, 9, 20))  # 3rd Monday of September
        self.assertEqual(d["coming-of-age"], date(2027, 1, 11))       # 2nd Monday of January
        self.assertEqual(d["christmas"], date(2027, 12, 25))

    def test_the_start_reminder_is_three_weeks_before(self):
        g = {x["slug"]: x for x in giftcal.gift_days(2027)}["mothers-day"]
        self.assertEqual((g["date"] - g["start"]).days, 21)

    def test_days_are_in_date_order(self):
        days = giftcal.gift_days(2027)
        self.assertEqual(days, sorted(days, key=lambda g: g["date"]))

    def test_the_ics_is_valid_enough_for_calendars(self):
        text = giftcal.ics("https://yorokobu-present.com", [2027, 2028], "20261006T000000Z")
        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(text.count("BEGIN:VEVENT"), text.count("END:VEVENT"))
        self.assertEqual(text.count("BEGIN:VEVENT"), 2 * len(giftcal.DAYS) * 2)       # a start reminder and the day, for two years
        uids = [l for l in text.split("\r\n") if l.startswith("UID:")]
        self.assertEqual(len(uids), len(set(uids)))
        self.assertIn("DTSTART;VALUE=DATE:20270509", text)
        self.assertIn("DTSTART;VALUE=DATE:20270418", text)                              # 21 days before Mother's Day
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)                         # folded
        unfolded = text.replace("\r\n ", "")
        self.assertIn("母の日まで3週間。贈り物を選びはじめよう", unfolded)
        self.assertIn("https://yorokobu-present.com/occasion/mothers-day/", unfolded)

    def test_commas_and_newlines_are_escaped(self):
        self.assertEqual(giftcal._esc("a,b;c" + chr(10) + "d"), "a" + chr(92) + ",b" + chr(92) + ";c" + chr(92) + "nd")


if __name__ == "__main__":
    unittest.main()
