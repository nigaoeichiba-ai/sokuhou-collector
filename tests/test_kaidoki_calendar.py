"""sale-calendar.com: the schedule calendars (all shops in one calendar, one calendar per mall; sites/kaidoki/redesign/schedule.py).

Pinned here: the weekday written in every sentence is the real weekday; an expected entry always carries the past dates it rests on and says "ごろ" or names a month;
an entry is never told apart by colour alone (a word and a symbol in every mark and every list line); every shop of the data is on the all-shops page, every mall on its own page;
the lists of all months are in the HTML (the page reads without a script); "開催中 / あとN日" is not written into the build; the monthly days follow their rules; the new pages have their own
title, description and h1; no price of a product and no commission is written."""
from __future__ import annotations

import os
import re
import unittest
from datetime import date

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")

from sites.kaidoki.redesign import schedule as S  # noqa: E402
from tests.test_kaidoki_redesign import build  # noqa: E402

WD = "月火水木金土日"


def _weekday_problems(items) -> list[str]:
    bad = []
    for it in items:
        if it["kind"] == "regular":
            continue
        ref = it.get("s") or (it.get("mo") or "2026-01") + "-01"
        for m, dd, w in re.findall(r"(\d+)月(\d+)日\((.)\)", it["when"]):
            y = int(ref[:4])
            if it.get("s") and int(m) < int(ref[5:7]):
                y += 1
            if WD[date(y, int(m), int(dd)).weekday()] != w:
                bad.append(f"{it['id']}: {m}月{dd}日 is not ({w})")
    return bad


class DataTest(unittest.TestCase):
    items = S.all_items()

    def test_weekdays_in_the_sentences_are_computed_right(self):
        self.assertEqual(_weekday_problems(self.items), [])

    def test_expected_entries_have_their_past_and_are_hedged(self):
        exp = [i for i in self.items if i["kind"] == "expected"]
        self.assertGreaterEqual(len(exp), 10)
        for it in exp:
            self.assertTrue(it["basis"], it["id"])
            self.assertTrue(it["src"], it["id"])
            self.assertTrue(it.get("s") or it.get("mo"), it["id"])
            self.assertRegex(it["when"], r"ごろ|月|未発表", it["id"])
            self.assertTrue(any(re.search(r"20\d\d年", b) for b in it["basis"]), it["id"])      # a past year is named

    def test_every_entry_has_a_source_kind_a_check_day_and_a_known_shop(self):
        for it in self.items:
            self.assertIn(it["kind"], S.KINDS, it["id"])
            self.assertIn(it["mall"], S.ENT, it["id"])
            self.assertTrue(it["src"] and it["checked"], it["id"])
            if it["kind"] in ("confirmed", "notice", "expected") and it.get("s"):
                self.assertLessEqual(it["s"], it["e"], it["id"])
        self.assertEqual(len({i["id"] for i in self.items}), len(self.items))

    def test_monthly_days_follow_their_rules(self):
        by = {i["id"]: i for i in self.items}
        self.assertEqual([x for x in by["r-rak-50"]["days"] if x.startswith("2026-12")], [f"2026-12-{n:02d}" for n in (5, 10, 15, 20, 25, 30)])
        self.assertNotIn("2026-11-25", by["r-yah-5"]["days"])                 # the Black Friday month: the official guide says no
        self.assertIn("2026-12-25", by["r-yah-5"]["days"])
        self.assertEqual([x for x in by["r-rak-w"]["days"] if x.startswith("2027-02")], ["2027-02-01"])
        self.assertNotIn("2026-10-05", by["r-rak-50"]["days"])               # the months before the check are not listed as monthly days
        self.assertEqual(by["r-yah-kan"]["days"], ["2026-12-11", "2026-12-22"])

    def test_no_price_of_a_product_no_commission(self):
        for it in self.items:
            self.assertNotRegex(it["title"] + it["when"] + it["note"] + "".join(it["basis"]), r"[¥￥]\s?\d|\d円|\d+%OFF")
            self.assertNotRegex(it["note"], r"報酬|成果|アフィリエイト")


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "0", "KAIDOKI_NOW": "2026-11-12T10:00"}, products=[])

    def test_all_shops_page_lists_every_shop_and_every_kind(self):
        h = self.pages["calendar/index.html"]
        for key, (name, letter, seg) in S.ENT.items():
            self.assertIn(name, h, key)
        for label, sym, _ in S.KINDS.values():
            self.assertIn(label, h)
            self.assertIn(sym, h)
        for seg in S.SEGMENTS.values():
            self.assertIn(seg, h)

    def test_each_mall_has_its_own_page_with_its_own_head(self):
        heads = set()
        for m, path in S.CAL_PATH.items():
            h = self.pages[path.strip("/") + "/index.html"]
            title = re.search(r"<title>(.*?)</title>", h).group(1)
            desc = re.search(r'<meta name="description" content="([^"]*)"', h).group(1)
            self.assertEqual(h.count("<h1"), 1)
            self.assertIn(S.MALLS[m][0], title)
            heads.add((title, desc))
            self.assertIn(f'data-mall="{m}"', h)
            self.assertNotRegex(h, r'<li class="cal-item[^>]*data-mall="(?!%s")' % m)          # only this mall's entries
            self.assertIn(f"<loc>https://sale-calendar.com{path}</loc>", self.pages["sitemap.xml"])
        self.assertEqual(len(heads), 3)

    def test_the_page_reads_without_a_script(self):
        h = self.pages["calendar/index.html"]
        for ym in S.months():
            self.assertIn(f'id="m-{ym}"', h)                       # the list of every month is in the HTML
        self.assertEqual(h.count('<table class="cal-grid">'), 1)    # the first month's grid is in the HTML too
        self.assertIn("2026年11月のカレンダー", h)
        self.assertNotRegex(h, r"開催中</span><span class=\"cal-live|あと\d+日</span>")      # "開催中" / "あとN日" is written by the visitor's clock, not by the build
        self.assertIn("calendar.js", h)

    def test_a_kind_is_never_told_by_colour_alone(self):
        h = self.pages["calendar/index.html"]
        for kind, (label, sym, _) in S.KINDS.items():
            marks = re.findall(r'<li class="cal-mk k-%s"[^>]*>(.*?)</li>' % kind, h, re.S)
            for m in marks:
                self.assertIn(sym, m)
                self.assertIn(label, m)                              # the screen-reader text names the kind
            items = re.findall(r'<span class="cal-badge k-%s">(.*?)</span>' % kind, h)
            self.assertTrue(items, kind)
            self.assertTrue(all(sym in x and label in x for x in items), kind)

    def test_the_mall_pages_and_top_link_to_the_calendars(self):
        for path in ("rakuten/index.html", "amazon/sale-calendar/index.html", "yahoo/index.html", "malls/index.html", "index.html"):
            self.assertRegex(self.pages[path], r'href="/calendar/(rakuten/|amazon/|yahoo/)?"', path)
        self.assertIn('href="/calendar/rakuten/"', self.pages["rakuten/index.html"])
        self.assertIn('href="/calendar/yahoo/"', self.pages["yahoo/index.html"])

    def test_negative_the_weekday_check_catches_a_wrong_weekday(self):
        bad = dict(S.all_items()[0], kind="expected", s="2026-12-04", when="12月4日(土)20時ごろ", id="neg")
        self.assertTrue(_weekday_problems([bad]))
        self.assertFalse(_weekday_problems([dict(bad, when="12月4日(金)20時ごろ")]))


if __name__ == "__main__":
    unittest.main()
