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

from sites.kaidoki.gen import facts  # noqa: E402
from sites.kaidoki.gen.common import REVERIFIED  # noqa: E402
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


def home_problems(html: str, today: date) -> list[str]:
    """What the top page must agree with in the data: the check day of every tile, the entry to the calendars, the two weeks it lists."""
    bad = []
    days = set(re.findall(r"確認日 (\d{4}/\d{2}/\d{2})", html))
    if days != {REVERIFIED.replace("-", "/")}:
        bad.append(f"check days on the top page {sorted(days)} are not the data's {REVERIFIED}")
    for path in ("/calendar/", "/calendar/rakuten/", "/calendar/amazon/", "/calendar/yahoo/"):
        if f'href="{path}"' not in html:
            bad.append(f"no link to {path}")
    if "data-fortnight" not in html:
        return bad + ["no two-week block"]
    shown = re.findall(r'<li class="cal-item[^>]*data-id="([^"]*)"(?![^>]*hidden)', html)
    items = S.all_items()
    want = S.home_choose(S.home_pool(items, today), today)
    if shown != want:
        bad.append(f"two weeks shown {shown} differ from the data {want}")
    slides = re.findall(r'<li class="hs-slide[^>]*data-id="([^"]*)"', html)
    want_slides = [i["id"] for i in S.hero_slides(items, today)]
    if slides != want_slides:
        bad.append(f"hero slides {slides} differ from the data {want_slides}")
    big = [i for i in S.hero_slides(items, today) if S.ENT[i["mall"]][2] == "mall"]
    if len(big) >= 2 and len([x for x in slides if x in {i["id"] for i in big}]) < len(big):
        bad.append("the hero shows fewer big sales than the data has")
    for name, mall, why in facts.UNANNOUNCED:
        if name == "Amazon ブラックフライデー 2026" and "11月19日" in why and "11月19日" not in html:
            bad.append("the Amazon Black Friday state (11/19) of the data is not on the top page")
    return bad


class HomeTest(unittest.TestCase):
    TODAY = date(2026, 11, 12)

    @classmethod
    def setUpClass(cls):
        cls.pages = build({"KAIDOKI_REDESIGN": "1", "KAIDOKI_REDESIGN_DEMO": "0", "KAIDOKI_NOW": "2026-11-12T10:00"}, products=[])

    def test_the_top_page_agrees_with_the_data(self):
        self.assertEqual(home_problems(self.pages["index.html"], self.TODAY), [])

    def test_the_two_weeks_come_from_the_data_with_the_kinds_and_the_links(self):
        h = self.pages["index.html"]
        self.assertIn("これから2週間の日程", h)
        self.assertIn("月間カレンダーを見る", h)
        ids = S.home_choose(S.home_pool(S.all_items(), self.TODAY), self.TODAY)
        self.assertTrue(3 <= len(ids) <= S.HOME_MAX)
        kinds = {i.split("@")[0][0] for i in ids}
        self.assertIn("n", kinds)                                  # the announcement days (Yahoo! 11/16, Amazon 11/19) are in the two weeks
        self.assertIn('data-kind="regular"', h)
        self.assertNotIn("開催中</span>", h.split("home-cal")[1][:4000])      # "開催中" / "あとN日" are written by the visitor's clock

    def test_hero_slides_hold_every_coming_big_sale_of_the_malls_then_other_shops(self):
        h = self.pages["index.html"]
        sl = S.hero_slides(S.all_items(), self.TODAY)
        mall = [i for i in sl if S.ENT[i["mall"]][2] == "mall"]
        self.assertGreaterEqual(len(mall), 4)
        self.assertEqual({S.hero_kind(i) for i in mall}, {"confirmed", "announced", "expected"})      # the three kinds, each told apart
        self.assertEqual([S.ENT[i["mall"]][2] for i in sl], sorted([S.ENT[i["mall"]][2] for i in sl], key=lambda x: x != "mall"))      # the malls first
        names = " ".join(i["title"] for i in sl)
        for w in ("Yahoo!ショッピング ブラックフライデー 2026", "Amazon ブラックフライデー 2026", "楽天ブラックフライデー 2026", "楽天スーパーSALE 2026年12月", "Googleストア"):
            self.assertIn(w, names)
        self.assertEqual(h.count('<li class="hs-slide'), len(sl))                      # without the script every card is in the HTML (a column)
        for badge in ("● 確定", "▲ 開催は発表済み・詳細待ち", "◇ 例年の予想"):
            self.assertIn(badge, h)
        self.assertLessEqual(len(sl) - len(mall), S.HERO_OTHERS)
        self.assertIn('aria-roledescription="カルーセル"', h)
        js = (S.__file__.replace("schedule.py", "static/scripts/calendar.js"))
        src = open(js, encoding="utf-8").read()
        for w in ("prefers-reduced-motion", "mouseenter", "focusin", "touchstart", "5500", "hs-prev", "hs-next", "hs-dot"):
            self.assertIn(w, src)

    def test_the_headline_frame_agrees_with_the_data(self):
        import json
        from pathlib import Path
        hero = json.loads((Path(S.__file__).parent / "hero.json").read_text(encoding="utf-8"))
        yb = facts.BY_ID["ybf-2026"]
        for h in hero["scheduled"]:
            if "Y" in h["eyebrow"] and "BLACK FRIDAY" in h["eyebrow"]:
                m, dd = int(yb["start"][5:7]), int(yb["start"][8:10])
                self.assertIn(f"{m}月{dd}日", h["h1"])
                self.assertEqual(h["until"][:10], yb["start"])

    def test_the_calendar_pages_are_linked_from_the_top_the_lists_and_the_category(self):
        for path in ("/calendar/rakuten/", "/calendar/amazon/", "/calendar/yahoo/"):
            linkers = [rel for rel, h in self.pages.items() if isinstance(h, str) and rel.endswith("index.html") and f'href="{path}"' in h and rel != path.strip("/") + "/index.html"]
            for need in ("index.html", "calendar/index.html", "malls/index.html"):
                self.assertIn(need, linkers, path)
            self.assertGreaterEqual(len(linkers), 4, path)
        self.assertIn('href="/calendar/"', self.pages["kaden/index.html"])

    def test_negative_hero_with_one_card_is_caught(self):
        h = self.pages["index.html"]
        cut = re.sub(r'<li class="hs-slide.*?</li>', "", h, count=3, flags=re.S)
        self.assertTrue(home_problems(cut, self.TODAY))
        self.assertTrue(home_problems(h.replace("2026/11/12", "2026/11/03", 1), self.TODAY))

    def test_negative_a_stale_top_page_is_caught(self):
        h = self.pages["index.html"]
        self.assertTrue(home_problems(h.replace(REVERIFIED.replace("-", "/"), "2026/11/03"), self.TODAY))      # the old check day (the report of the owner)
        self.assertTrue(home_problems(h.replace('href="/calendar/yahoo/"', 'href="/x/"'), self.TODAY))         # a missing entry to a mall calendar
        self.assertTrue(home_problems(h.replace("data-fortnight", "data-x"), self.TODAY))
        self.assertTrue(home_problems(h.replace('data-id="n-abf-2026"', 'data-id="n-abf-2026" hidden'), self.TODAY))      # the two weeks differ from the data


if __name__ == "__main__":
    unittest.main()
