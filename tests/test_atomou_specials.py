"""atomou: the three 特集 pages under /kyou/ - the holiday rules against the lists of the Cabinet Office (2024-2027), the equinoxes and solar terms against the Observatory's figures,
the runs of days off, the pages themselves, and that a wrong rule is caught."""
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, calendar_data as cal  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))

# the days off the Cabinet Office lists for each year (holidays, substitute holidays, the sandwiched day), month-day
OFFICIAL = {
    2024: "01-01 01-08 02-11 02-12 02-23 03-20 04-29 05-03 05-04 05-05 05-06 07-15 08-11 08-12 09-16 09-22 09-23 10-14 11-03 11-04 11-23",
    2025: "01-01 01-13 02-11 02-23 02-24 03-20 04-29 05-03 05-04 05-05 05-06 07-21 08-11 09-15 09-23 10-13 11-03 11-23 11-24",
    2026: "01-01 01-12 02-11 02-23 03-20 04-29 05-03 05-04 05-05 05-06 07-20 08-11 09-21 09-22 09-23 10-12 11-03 11-23",
    2027: "01-01 01-11 02-11 02-23 03-21 03-22 04-29 05-03 05-04 05-05 07-19 08-11 09-20 09-23 10-11 11-03 11-23",
}


def listed(y):
    return [d.strftime("%m-%d") for d in cal.holidays(y)]


class Holidays(unittest.TestCase):
    def test_the_rules_give_the_official_lists(self):
        for y, text in OFFICIAL.items():
            self.assertEqual(listed(y), text.split(), y)

    def test_special_cases(self):
        h = cal.holidays(2026)
        self.assertEqual(h[date(2026, 9, 22)], "国民の休日")        # between the Respect for the Aged Day and the autumn equinox
        self.assertEqual(h[date(2026, 5, 6)], "振替休日")
        self.assertEqual(cal.holidays(2027)[date(2027, 3, 22)], "振替休日")
        self.assertEqual(cal.holidays(2020)[date(2020, 7, 24)], "スポーツの日")     # the Olympic year
        self.assertEqual(cal.holidays(2021)[date(2021, 8, 9)], "振替休日")
        with self.assertRaises(ValueError):
            cal.holidays(2019)

    def test_equinoxes_match_the_observatory(self):
        self.assertEqual(cal.equinoxes(2026), (20, 23))
        self.assertEqual(cal.equinoxes(2027), (21, 23))
        t = {y: {x["name"]: x["date"] for x in cal.terms_of(y)} for y in (2026, 2027)}
        for y in (2026, 2027):
            self.assertEqual((t[y]["春分"].day, t[y]["秋分"].day), cal.equinoxes(y))

    def test_runs_and_bridges_of_2027(self):
        r = cal.runs(2027, 3)
        self.assertEqual([(x["start"].isoformat(), x["days"]) for x in r][:2], [("2027-01-01", 3), ("2027-01-09", 3)])
        gw = [x for x in r if x["start"] == date(2027, 5, 1)][0]
        self.assertEqual((gw["end"], gw["days"]), (date(2027, 5, 5), 5))
        b = cal.bridges(2027)
        self.assertEqual([(x["take"].isoformat(), x["days"]) for x in b], [("2027-04-30", 7)])      # the Friday between the Showa Day and the weekend

    def test_a_wrong_rule_is_caught(self):
        with mock.patch.object(cal, "_nth_monday", lambda y, m, n: date(y, m, 1)):
            self.assertNotEqual(listed(2027), OFFICIAL[2027].split())
        with mock.patch.object(cal, "equinoxes", lambda y: (20, 22)):
            self.assertNotEqual(listed(2027), OFFICIAL[2027].split())


class SolarTerms(unittest.TestCase):
    def test_the_file_is_whole_and_in_order(self):
        data = cal.solar_terms()
        for y in ("2026", "2027"):
            rows = data["years"][y]
            self.assertEqual(len(rows), 24)
            ds = [date(int(y), int(md[:2]), int(md[3:])) for _, md, _ in rows]
            self.assertEqual(ds, sorted(ds))
            self.assertEqual([n for n, _, _ in rows], list(cal.TERM_MEANING))                    # the 24 names, in the order of the year
            for a, b in zip(ds, ds[1:]):
                self.assertIn((b - a).days, (14, 15, 16), (a, b))                               # a term every 14-16 days
        self.assertIn("rekiyou", data["pages"]["2027"])

    def test_official_values(self):
        t = {x["name"]: x for x in cal.terms_of(2027)}
        self.assertEqual((t["立秋"]["date"], t["立秋"]["time"]), (date(2027, 8, 8), "02:27"))
        self.assertEqual(t["霜降"]["date"], date(2027, 10, 24))
        self.assertEqual({x["name"]: x["date"] for x in cal.terms_of(2026)}["立冬"], date(2026, 11, 7))

    def test_span(self):
        cur, nxt = cal.term_span(date(2026, 10, 11))
        self.assertEqual((cur["name"], nxt["name"]), ("寒露", "霜降"))
        cur, nxt = cal.term_span(date(2026, 10, 23))
        self.assertEqual(cur["name"], "霜降")
        self.assertEqual(cal.terms_of(2030), [])


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rel = build.build_pages(CFG, release=True, today=date(2026, 10, 11))

    def test_the_three_pages_exist_and_are_linked_from_kyou(self):
        for p in ("kyou/holidays-2026/index.html", "kyou/holidays-2027/index.html", "kyou/season/index.html", "kyou/december/index.html"):
            self.assertIn(p, self.rel)
            self.assertIn("/" + p.replace("index.html", ""), self.rel["sitemap.xml"])
        idx = self.rel["kyou/index.html"]
        for href in ("/kyou/holidays-2027/", "/kyou/season/", "/kyou/december/"):
            self.assertIn(f'href="{href}"', idx)
        self.assertNotIn("/kyou/season/", self.rel["index.html"])                  # not in the home page's menu: the owner's decision

    def test_holiday_page(self):
        h = self.rel["kyou/holidays-2027/index.html"]
        self.assertIn("<h1>2027年の祝日と連休</h1>", h)
        self.assertIn("<b>17</b><span>日の休み", h)
        self.assertIn("4月30日(金)を休むと、4月29日(木)〜5月5日(水)の<b>7連休</b>", h)
        self.assertIn("5月1日(土)〜5月5日(水)</b> 5連休", h)
        self.assertIn("www8.cao.go.jp/chosei/shukujitsu", h)
        self.assertIn("数え直し", h)
        self.assertIn('data-cd="2027-01-01"', h)
        self.assertEqual(len(re.findall(r"<tr><th scope=\"row\">\d+年</th>", h)), 8)    # 2020-2027

    def test_season_page(self):
        s = self.rel["kyou/season/index.html"]
        self.assertIn('data-d="2026-10-23"', s)
        self.assertIn("rekiyou272", s)
        self.assertIn("説明の文は、当サイトで書いたもの", s)
        self.assertNotIn('data-d="2026-07-', s)          # a term more than 60 days behind the build day is not listed
        self.assertIn('id="season-now"', s)
        self.assertNotIn(">冬至(二十四節気)<", s.split('data-d="2026-12-22"')[1].split("</article>")[0])    # the term's own day is not listed as "a day near it"

    def test_december_page(self):
        d = self.rel["kyou/december/index.html"]
        self.assertEqual(d.count('<article class="day"'), 31)
        self.assertIn('data-d="2026-12-22"', d)
        self.assertIn("冬至", d)
        quiet = [e for e in build.catalog.build_catalog(date(2026, 10, 11))[0] if e["quiet"] and e["date"].startswith("2026-12")]
        for e in quiet:
            self.assertNotIn(f'href="/e/{e["id"]}/"', d)       # a quiet day is not turned over like a page of a calendar

    def test_the_pages_do_not_pass_on_the_sources_files(self):
        for p in ("kyou/holidays-2027/index.html", "kyou/season/index.html"):
            self.assertNotIn("syukujitsu", self.rel[p])


if __name__ == "__main__":
    unittest.main()
