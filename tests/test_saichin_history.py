"""The prefecture pages show the whole history of MHLW's workbook (Heisei 14 to the current year), with a summary computed from the same numbers."""
import json
import re

from sites.saichin import build
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401


class HistoryTest(SiteFixture):
    def raw_pref(self, short):
        return next(p for p in _raw()["prefectures"] if p["name"] == short)

    def test_every_prefecture_shows_every_year_from_heisei_14_with_a_rank(self):
        for r in self.d["rows"]:
            self.assertEqual([h["fy"] for h in r["history"]], list(range(2002, 2027)), r["name"])
            self.assertTrue(all(isinstance(h["rank"], int) and 1 <= h["rank"] <= 47 for h in r["history"]), r["name"])

    def test_the_page_has_one_table_row_per_year_and_the_range_in_the_heading_and_the_description(self):
        for slug, short in (("shiga", "滋賀"), ("tokyo", "東京"), ("okinawa", "沖縄")):
            page = self.read(f"{slug}/index.html")
            self.assertIn("(平成14年度から令和8年度まで)</h2>", page, slug)
            table = re.search(r"<th>年度</th>.*?</table>", page, re.S).group(0)
            self.assertEqual(table.count("<tr>"), 25, slug)                     # the match starts inside the header row, so these are the year rows
            self.assertIn("平成14年度から令和8年度まで年度別に掲載", re.search(r'<meta name="description" content="([^"]*)"', page).group(1), slug)
            self.assertIn('<svg class="chart"', page)

    def test_the_summary_numbers_are_recomputed_independently_from_the_workbook(self):
        raw = _raw()
        for slug, short in (("shiga", "滋賀"), ("tokyo", "東京"), ("hokkaido", "北海道")):
            p = self.raw_pref(short)
            first, last = p["history"]["2002"]["amount"], p["history"]["2026"]["amount"]
            up = last - first
            raises = {y: p["history"][str(y)]["amount"] - p["history"][str(y - 1)]["amount"] for y in range(2003, 2027)}
            top_fy = max(raises, key=lambda y: (raises[y], y))
            nat_first, nat_last = round(raw["national_weighted_average"]["2002"]), round(raw["national_weighted_average"]["2026"])
            text = re.search(r"<h2>最低賃金の推移\(.*?\)</h2>\n<p>(.*?)</p>", self.read(f"{slug}/index.html"), re.S).group(1)
            self.assertIn(f"平成14年度の{first:,}円から、令和8年度の{last:,}円(決まった額)まで、24年間で{up:,}円({up / first * 100:.1f}%)", text, slug)
            self.assertIn(f"1年あたりの平均は約{up / 24:.0f}円", text, slug)
            self.assertIn(f"+{raises[top_fy]}円です", text, slug)
            self.assertIn(self.d["years"][top_fy - 2002]["label"], text, slug)
            self.assertIn(f"全国加重平均は{nat_first:,}円から{nat_last:,}円へ、+{nat_last - nat_first:,}円", text, slug)

    def test_the_summary_never_mentions_a_year_that_is_not_in_the_table(self):
        for r in self.d["rows"]:
            labels = {h["label"] for h in r["history"]}
            text = build.history_summary(self.d, r)
            for label in re.findall(r"(?:平成|令和)(?:\d+|元)年度", text):
                self.assertIn(label, labels, r["name"])

    def test_a_workbook_with_fewer_years_still_builds_a_shorter_history(self):
        """Only the years the workbook has are shown (no invented rows): drop the first three years and the pages start at Heisei 17."""
        raw = _raw()
        for p in raw["prefectures"]:
            for y in ("2002", "2003", "2004"):
                del p["history"][y]
        for y in ("2002", "2003", "2004"):
            del raw["national_weighted_average"][y]
            del raw["fiscal_year_labels"][y]
        d = build.prepare(raw)
        tokyo = next(r for r in d["rows"] if r["short"] == "東京")
        self.assertEqual(tokyo["history"][0]["fy"], 2005)
        self.assertEqual(len(tokyo["history"]), 22)
        self.assertIn("平成17年度", build.history_summary(d, tokyo))


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

    def test_the_history_page_lists_all_47_with_the_rise_since_heisei_14_recomputed_independently(self):
        raw = _raw()
        page = self.read("history/index.html")
        section = page.split("<h2>都道府県別の推移(", 1)[1].split("</table>", 1)[0]
        rows = re.findall(r'<tr><td><a href="/([a-z]+)/">([^<]*)</a></td><td>([\d,]+)円</td><td>([\d,]+)円</td><td>\+([\d,]+)円</td><td>([\d.]+)%</td></tr>', section)
        self.assertEqual(len(rows), 47)
        ups = []
        for slug, name, a, b, up, pct in rows:
            short = next(r["short"] for r in self.d["rows"] if r["slug"] == slug)
            p = next(x for x in raw["prefectures"] if x["name"] == short)
            first, last = p["history"]["2002"]["amount"], p["history"]["2026"]["amount"]
            self.assertEqual((int(a.replace(",", "")), int(b.replace(",", "")), int(up.replace(",", ""))), (first, last, last - first), name)
            self.assertEqual(pct, f"{(last - first) / first * 100:.1f}", name)
            ups.append(last - first)
        self.assertEqual(ups, sorted(ups, reverse=True))                       # the biggest rise first
        years = self.d["years"]
        self.assertIn(f"最高額と最低額の差は、平成14年度の{years[0]['max'] - years[0]['min']:,}円から、令和8年度の{years[-1]['max'] - years[-1]['min']:,}円になりました", page)

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

    def test_a_workbook_that_starts_later_is_fine_if_it_has_no_gaps(self):
        raw = _raw()
        for p in raw["prefectures"]:
            for y in ("2002", "2003"):
                del p["history"][y]
        for y in ("2002", "2003"):
            del raw["national_weighted_average"][y]
            del raw["fiscal_year_labels"][y]
        build.check_history(raw)
        self.assertEqual(build.prepare(raw)["rows"][0]["history"][0]["fy"], 2004)


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
