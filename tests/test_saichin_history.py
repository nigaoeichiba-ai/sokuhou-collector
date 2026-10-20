"""The prefecture pages show the whole history of MHLW's workbook (Heisei 14 to the current year), with a summary computed from the same numbers."""
import json
import re

from sites.saichin import build, history_old
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401


class HistoryTest(SiteFixture):
    def raw_pref(self, short):
        return next(p for p in _raw()["prefectures"] if p["name"] == short)

    def test_every_prefecture_shows_every_year_from_heisei_14_with_a_rank(self):
        for r in self.d["rows"]:
            self.assertEqual([h["fy"] for h in r["history"]], list(range(2002, 2027)), r["name"])
            self.assertTrue(all(isinstance(h["rank"], int) and 1 <= h["rank"] <= 47 for h in r["history"]), r["name"])

    def test_a_workbook_without_the_years_the_old_document_overlaps_is_refused(self):
        """The old document (Showa 52 to Heisei 15) is joined to the workbook through Heisei 14 and 15; without them the join cannot be checked."""
        raw = _raw()
        for p in raw["prefectures"]:
            for y in ("2002", "2003", "2004"):
                del p["history"][y]
        for y in ("2002", "2003", "2004"):
            del raw["national_weighted_average"][y]
            del raw["fiscal_year_labels"][y]
        with self.assertRaises(build.BuildError):
            build.prepare(raw)


class AreaAndHistoryPagesTest(SiteFixture):
    def test_the_region_kinds_are_counted_from_the_real_member_names(self):
        kinds = {slug: build.member_kinds([r for r in self.d["rows"] if r["short"] in shorts]) for slug, _, shorts in build.REGIONS}
        self.assertEqual(kinds, {"hokkaido-tohoku": "1道6県", "kanto": "1都6県", "chubu": "9県", "kinki": "2府5県",
                                 "chugoku": "5県", "shikoku": "4県", "kyushu-okinawa": "8県"})

    def test_the_area_page_says_how_many_prefectures_and_ranks_each_of_them(self):
        page = self.read("area/kanto/index.html")
        self.assertIn("<title>関東の最低賃金一覧(1都6県)と順位(", page)
        self.assertIn("<h1>関東1都6県の最低賃金 一覧と順位(", page)
        self.assertIn("関東1都6県の最低賃金を高い順に並べました", re.search(r'<meta name="description" content="([^"]*)"', page).group(1))
        table = re.search(r"<th>都道府県</th><th>最低賃金</th><th>全国順位</th>.*?</table>", page, re.S).group(0)
        rows = re.findall(r'<tr><td><a href="/([a-z]+)/">[^<]*</a></td><td>[^<]*</td><td>(\d+)位</td>', table)
        by_slug = {r["slug"]: r["rank"] for r in self.d["rows"]}
        self.assertEqual(len(rows), 7)
        for slug, rank in rows:
            self.assertEqual(int(rank), by_slug[slug], slug)

    def test_the_history_page_lists_all_47_with_the_rise_since_showa_52_recomputed_independently(self):
        raw = _raw()
        old = history_old.load()
        page = self.read("history/index.html")
        section = page.split("<h2>都道府県別の推移(", 1)[1].split("</table>", 1)[0]
        rows = re.findall(r'<tr><td><a href="/([a-z]+)/">([^<]*)</a></td><td>([\d,.]+)円</td><td>([\d,.]+)円</td><td>\+([\d,.]+)円</td><td>([\d.]+)倍</td></tr>', section)
        self.assertEqual(len(rows), 47)
        ups = []
        for slug, name, a, b, up, ratio in rows:
            short = next(r["short"] for r in self.d["rows"] if r["slug"] == slug)
            p = next(x for x in raw["prefectures"] if x["name"] == short)
            first, last = old["prefectures"][short]["1977"], p["history"]["2026"]["amount"]
            self.assertEqual((float(a.replace(",", "")), float(b.replace(",", "")), round(float(up.replace(",", "")), 2)), (first, last, round(last - first, 2)), name)
            self.assertEqual(ratio, f"{last / first:.1f}", name)
            ups.append(last - first)
        self.assertEqual(ups, sorted(ups, reverse=True))                       # the biggest rise first

    def test_every_prefecture_page_is_linked_from_the_history_page(self):
        page = self.read("history/index.html")
        for r in self.d["rows"]:
            self.assertIn(f'href="/{r["slug"]}/"', page, r["slug"])


class HistoryChecksTest(SiteFixture):
    """build.check_history refuses data that breaks an invariant (the build fails, the live site stays as it was); real data passes."""
    def mutated(self, fn):
        raw = _raw()
        fn(raw)
        return raw

    def refuses(self, fn, message):
        with self.assertRaises(build.BuildError) as cm:
            build.prepare(self.mutated(fn))
        self.assertIn(message, str(cm.exception))

    def test_the_real_shape_passes(self):
        build.check_history(_raw())

    def test_a_gap_in_the_middle_of_the_history_is_refused(self):
        def gap(raw):
            del next(p for p in raw["prefectures"] if p["name"] == "東京")["history"]["2010"]
        self.refuses(gap, "東京: the history has no entry for fiscal year 2010")

    def test_an_amount_that_falls_is_refused(self):
        def drop(raw):
            p = next(p for p in raw["prefectures"] if p["name"] == "滋賀")
            p["history"]["2015"]["amount"] = p["history"]["2014"]["amount"] - 1
        self.refuses(drop, "滋賀: the amount fell")

    def test_a_cell_that_is_not_a_whole_number_of_yen_or_is_absurd_is_refused(self):
        for bad in (1136.5, "1136", 100, 100000, True):
            def put(raw, bad=bad):
                next(p for p in raw["prefectures"] if p["name"] == "沖縄")["history"]["2020"]["amount"] = bad
            self.refuses(put, "沖縄: implausible amount")

    def test_an_average_outside_the_prefectures_range_is_refused(self):
        def avg(raw):
            raw["national_weighted_average"]["2012"] = 5000
        self.refuses(avg, "fiscal year 2012: the weighted average 5000 is outside")

    def test_a_missing_average_is_refused(self):
        def miss(raw):
            del raw["national_weighted_average"]["2008"]
        self.refuses(miss, "no weighted national average for fiscal year 2008")

    def test_a_workbook_that_starts_later_passes_the_gap_check_but_the_join_with_the_old_document_refuses_it(self):
        raw = _raw()
        for p in raw["prefectures"]:
            for y in ("2002", "2003"):
                del p["history"][y]
        for y in ("2002", "2003"):
            del raw["national_weighted_average"][y]
            del raw["fiscal_year_labels"][y]
        build.check_history(raw)
        with self.assertRaises(build.BuildError):
            build.prepare(raw)


class DataVerificationTest(SiteFixture):
    def test_the_data_page_and_the_json_carry_the_dated_checks(self):
        page = self.read("data/index.html")
        self.assertIn("<h2>データの確認</h2>", page)
        self.assertIn("2026年10月15日: 令和8年度の47都道府県の最低賃金", page)
        self.assertIn("47都道府県すべて一致", page)
        self.assertIn("1つでも満たさなければ公開しません", page)
        data = json.loads((self.out / "data" / "minimum-wage.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verification"]["checks"][0]["date"], "2026-10-15")
        self.assertIn("公開しません", data["verification"]["every_build"])
