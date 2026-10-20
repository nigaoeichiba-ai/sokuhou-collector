"""The trend sections (one prefecture's whole series, Showa 52 to now; the national series) and the old document behind them.

Every number on the pages is recomputed here from the saved old page and the workbook fixture, by a separate calculation."""
import copy
import re
import unittest
from datetime import date
from pathlib import Path

from sites.saichin import build, charts, history_old, long_history
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401

PAGE = Path(__file__).parent / "fixtures" / "mhlw_2003_s1202-3h.html"
YEARS = list(range(1977, 2027))


def label(fy):
    if fy <= 1988:
        return f"昭和{fy - 1925}年度"
    if fy == 1989:
        return "平成元年度"
    if fy <= 2018:
        return f"平成{fy - 1988}年度"
    return "令和元年度" if fy == 2019 else f"令和{fy - 2018}年度"


def money(v):
    return "-" if v is None else (f"{int(v):,}円" if v == int(v) else f"{v:,.2f}".rstrip("0").rstrip(".") + "円")


def signed(v):
    if v is None:
        return "-"
    body = money(abs(v))
    return f"+{body}" if v > 0 else (f"-{body}" if v < 0 else "±0円")


def all_series(raw, old):
    """{short name: {fy: amount or None}} from Showa 52 to Reiwa 8, plus Kyoto's split rates {fy: (south, north)}."""
    out = {}
    for p in raw["prefectures"]:
        s = {fy: old["prefectures"][p["name"]].get(str(fy)) for fy in range(1977, 2002)}
        s.update({fy: p["history"][str(fy)]["amount"] for fy in range(2002, 2027)})
        out[p["name"]] = s
    split = {int(y): (old["kyoto_split"]["south"][y], old["kyoto_split"]["north"][y]) for y in old["kyoto_split"]["south"]}
    return out, split


def rows_of(page, after):
    section = page.split(after, 1)[1]
    table = re.search(r"<table>.*?</table>", section, re.S).group(0)
    table = re.sub(r"<tfoot>.*?</tfoot>", "", table, flags=re.S)                    # the notes of the table are not rows of data
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[dh]>(.*?)</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S)]


class OldDocumentTest(unittest.TestCase):
    def test_the_snapshot_is_exactly_what_the_saved_page_parses_to(self):
        self.assertEqual(history_old.parse(PAGE.read_bytes()), history_old.load())

    def test_the_old_document_has_27_years_for_47_prefectures_and_two_rates_for_kyoto(self):
        old = history_old.load()
        self.assertEqual(len(old["prefectures"]), 47)
        for name, s in old["prefectures"].items():
            expected = [y for y in range(1977, 2004) if not (name == "京都" and 1979 <= y <= 1989)]
            self.assertEqual(sorted(int(y) for y in s), expected, name)
        self.assertEqual(sorted(int(y) for y in old["kyoto_split"]["south"]), list(range(1979, 1990)))
        self.assertEqual(sorted(int(y) for y in old["kyoto_split"]["north"]), list(range(1979, 1990)))
        self.assertEqual(sorted(int(y) for y in old["national_weighted_average"]), list(range(1978, 2004)))

    def test_known_values_of_the_page(self):
        old = history_old.load()
        self.assertEqual(old["prefectures"]["東京"]["1977"], 345)
        self.assertEqual(old["prefectures"]["兵庫"]["1977"], 296)
        self.assertEqual(old["prefectures"]["愛知"]["1978"], 320.88)
        self.assertEqual(old["kyoto_split"]["south"]["1979"], 342.5)
        self.assertEqual(old["kyoto_split"]["north"]["1989"], 495)
        self.assertEqual(old["national_weighted_average"]["1978"], 315)
        self.assertEqual(old["national_weighted_average"]["2001"], 664)

    def test_the_old_document_and_the_workbook_agree_in_heisei_14_and_15_for_all_47(self):
        raw, old = _raw(), history_old.load()
        for p in raw["prefectures"]:
            for y in ("2002", "2003"):
                self.assertEqual(old["prefectures"][p["name"]][y], p["history"][y]["amount"], (p["name"], y))
        long_history.check(raw, old)

    def refuses(self, mutate, text):
        raw, old = _raw(), copy.deepcopy(history_old.load())
        mutate(raw, old)
        with self.assertRaises(long_history.LongHistoryError) as cm:
            long_history.check(raw, old)
        self.assertIn(text, str(cm.exception))

    def test_a_different_amount_in_the_overlap_is_refused(self):
        self.refuses(lambda raw, old: old["prefectures"]["東京"].__setitem__("2002", 709), "東京 2002")

    def test_a_missing_year_is_refused(self):
        self.refuses(lambda raw, old: old["prefectures"]["大阪"].pop("1990"), "大阪: the old document has gaps")

    def test_an_amount_that_falls_is_refused(self):
        self.refuses(lambda raw, old: old["prefectures"]["広島"].__setitem__("1995", 500), "広島: an old amount falls")

    def test_a_missing_prefecture_is_refused(self):
        self.refuses(lambda raw, old: old["prefectures"].pop("沖縄"), "do not list the same prefectures")

    def test_kyoto_split_rates_that_fall_are_refused(self):
        self.refuses(lambda raw, old: old["kyoto_split"]["north"].__setitem__("1985", 100), "Kyoto north")

    def test_a_national_average_outside_the_range_is_refused(self):
        self.refuses(lambda raw, old: old["national_weighted_average"].__setitem__("1990", 900), "outside the prefectures' range")

    def test_a_national_average_that_disagrees_with_the_workbook_by_more_than_a_yen_is_refused(self):
        self.refuses(lambda raw, old: old["national_weighted_average"].__setitem__("2003", 667), "does not fit the workbook")


class ChartTest(unittest.TestCase):
    def test_the_axis_values_are_round_and_inside_the_range(self):
        for lo, hi in ((250, 1250), (600, 1200), (0, 66), (900, 1010)):
            ticks = charts._ticks(lo, hi)
            self.assertTrue(2 <= len(ticks) <= 6, (lo, hi, ticks))
            self.assertTrue(all(lo <= t <= hi for t in ticks), (lo, hi, ticks))
            self.assertTrue(all(t % 10 == 0 for t in ticks), ticks)

    def test_a_gap_breaks_the_line_in_two(self):
        svg = charts.compare(["a", "b", "c", "d", "e"], [{"name": "x", "values": [1, 2, None, 4, 5], "cls": ""}], title="t", desc="d", label_every=1)
        self.assertEqual(svg.count("<polyline"), 2)

    def test_every_chart_has_a_title_and_a_description(self):
        for svg in (charts.compare(["a", "b"], [{"name": "x", "values": [1, 2], "cls": ""}], title="T1", desc="D1"),
                    charts.bars([("a", 3), ("b", 5)], title="T2", desc="D2")):
            self.assertRegex(svg, r"<title[^>]*>T\d</title><desc[^>]*>D\d</desc>")

    def test_the_biggest_bar_and_a_distant_last_one_carry_their_value(self):
        svg = charts.bars([("a", 3), ("b", 9), ("c", 4), ("d", 2), ("e", 2), ("f", 5)], title="t", desc="d", label_every=1)
        self.assertEqual(svg.count('class="bar hot"'), 1)
        self.assertIn(">9円<", svg)
        self.assertIn(">5円<", svg)

    def test_a_last_bar_next_to_the_biggest_one_is_not_labelled_on_top_of_it(self):
        svg = charts.bars([("a", 3), ("b", 9), ("c", 4)], title="t", desc="d", label_every=1)
        self.assertIn(">9円<", svg)
        self.assertNotIn(">4円<", svg)

    def test_a_regular_x_label_never_sits_on_the_last_one(self):
        xs = [str(i) for i in range(20)]
        svg = charts.compare(xs, [{"name": "x", "values": list(range(20)), "cls": ""}], title="t", desc="d", label_every=6)
        labels = re.findall(r'class="lab"[^>]*>(\d+)<', svg)
        self.assertEqual(labels, ["0", "6", "12", "19"])           # 18 would touch 19


class PrefectureTrendTest(SiteFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raw, cls.old = _raw(), history_old.load()
        cls.series, cls.split = all_series(cls.raw, cls.old)

    def rank(self, short, fy):
        mine = self.series[short][fy]
        return 1 + sum(1 for s in self.series.values() if s[fy] is not None and s[fy] > mine)

    def avg(self, fy):
        if fy < 2002:
            return self.old["national_weighted_average"].get(str(fy))
        return self.raw["national_weighted_average"][str(fy)]

    def test_every_prefecture_page_has_one_row_per_fiscal_year_from_showa_52_with_every_figure_recomputed(self):
        for r in self.d["rows"]:
            short = r["short"]
            page = self.read(f"{r['slug']}/index.html")
            rows = rows_of(page, f"<h2>{r['name']}の最低賃金 年度別の一覧</h2>")
            self.assertEqual(rows[0], ["年度", "最低賃金", "前年度から", "上がり率", "全国加重平均", "全国との差", "全国順位", "発効日"], short)
            body = {row[0]: row for row in rows[1:]}
            self.assertEqual(len(rows) - 1, 50, short)
            prev = None
            raw_p = next(p for p in self.raw["prefectures"] if p["name"] == short)
            for fy in YEARS:
                a = self.series[short][fy]
                row = body[label(fy)]
                if a is None:
                    south, north = self.split[fy]
                    self.assertEqual(row[1], f"南部 {money(south)}・北部 {money(north)}", (short, fy))
                    self.assertEqual(row[2:4] + row[5:7], ["-", "-", "-", "-"], (short, fy))
                else:
                    self.assertEqual(row[1], money(a), (short, fy))
                    rise = None if prev is None else round(a - prev, 2)
                    self.assertEqual(row[2], signed(rise), (short, fy))
                    self.assertEqual(row[3], "-" if rise is None else f"{rise / prev * 100:.1f}%", (short, fy))
                    avg = self.avg(fy)
                    self.assertEqual(row[4], "-" if avg is None else f"{round(avg):,}円", (short, fy))
                    self.assertEqual(row[5], "-" if avg is None else signed(round(a - round(avg), 2)), (short, fy))
                    self.assertEqual(row[6], f"{self.rank(short, fy)}位" + ("※2" if 1979 <= fy <= 1989 else ""), (short, fy))
                if fy >= 2002:
                    eff = raw_p["history"][str(fy)]["effective_date"]
                    changed = a != self.series[short][fy - 1] if fy > 2002 else False
                    if changed:
                        eff = build.plausible_effective(short, fy, eff)[0]
                    self.assertTrue(row[7].startswith(f"{date.fromisoformat(eff).year}年{date.fromisoformat(eff).month}月{date.fromisoformat(eff).day}日"), (short, fy, row[7]))
                else:
                    self.assertEqual(row[7], "-", (short, fy))
                prev = a

    def test_the_summary_sentences_use_the_workbook_numbers(self):
        for short in ("兵庫", "東京", "沖縄", "京都"):
            r = next(x for x in self.d["rows"] if x["short"] == short)
            page = self.read(f"{r['slug']}/index.html")
            s = self.series[short]
            first, last = s[1977], s[2026]
            self.assertIn(f"{r['name']}の最低賃金は、昭和52年度の{money(first)}から、令和8年度の{money(last)}(決まった額)まで、49年間で{money(last - first)}(約{last / first:.1f}倍)上がりました", page)
            self.assertIn(f"1年あたりの平均は約{(last - first) / 49:.0f}円です", page)
            rises = {fy: round(s[fy] - s[fy - 1], 2) for fy in YEARS[1:] if s[fy] is not None and s[fy - 1] is not None}
            top = max(rises, key=lambda fy: (rises[fy], fy))
            self.assertIn(f"1年の引上げ額が最も大きかったのは{label(top)}の+{money(rises[top])}、", page)
            pct = {fy: rises[fy] / s[fy - 1] * 100 for fy in rises}
            best = max(pct, key=lambda fy: (pct[fy], fy))
            self.assertIn(f"引上げ率が最も大きかったのは{label(best)}の{pct[best]:.1f}%です。", page)
            self.assertIn(f"{label(2016)}から令和8年度までの10年間は+{money(s[2026] - s[2016])}、その前の10年間は+{money(s[2016] - s[2006])}でした。", page)

    def test_the_title_the_heading_and_the_description_follow_the_search_pattern(self):
        for r in self.d["rows"]:
            page = self.read(f"{r['slug']}/index.html")
            self.assertIn(f"<title>{r['name']}の最低賃金の推移(年度別の一覧・グラフ) {r['amount']:,}円(令和8年度)</title>", page, r["slug"])
            self.assertIn(f"<h1>{r['name']}の最低賃金の推移(年度別の一覧・グラフ)</h1>", page, r["slug"])
            self.assertIn("昭和52年度から令和8年度まで50年度分、一覧表とグラフで掲載", re.search(r'<meta name="description" content="([^"]*)"', page).group(1), r["slug"])

    def test_the_page_has_two_charts_with_the_numbers_also_in_the_text_and_the_table(self):
        page = self.read("hyogo/index.html")
        self.assertEqual(page.count('<svg class="chart"'), 2)
        self.assertIn("実線が兵庫県、点線が全国加重平均です。縦軸は0から始まっていません。", page)
        self.assertIn("棒の高さは、前の年度からの引上げ額です(縦軸は0から)。", page)
        self.assertIn("<polyline", page)
        self.assertIn("<td>1,172円</td>", page)

    def test_kyoto_has_two_rates_from_showa_54_to_heisei_1(self):
        page = self.read("kyoto/index.html")
        for fy in range(1979, 1990):
            south, north = self.split[fy]
            self.assertIn(f"<td>{label(fy)}</td><td>南部 {money(south)}・北部 {money(north)}</td>", page, fy)
        self.assertIn("昭和54年度から平成元年度までは、南部と北部で額が分かれていました。この期間の表は、2つの額を並べています。", page)
        for slug in ("kyoto", "hyogo"):
            self.assertIn("※2 昭和54〜平成元年度の順位は、南部と北部で額が分かれていた京都府を除く、46都道府県の中の順位です。", self.read(f"{slug}/index.html"))
        self.assertNotIn("南部と北部で額が分かれていました", self.read("hyogo/index.html"))
        # a year with Kyoto missing is ranked among 46: Tokyo is 1st in 1985, a prefecture below it is ranked against 46
        self.assertEqual(self.rank("東京", 1985), 1)
        self.assertEqual(sum(1 for s in self.series.values() if s[1985] is not None), 46)

    def test_the_old_figures_are_credited_to_the_2003_document_and_decimals_are_explained(self):
        page = self.read("aichi/index.html")
        self.assertIn("https://www.mhlw.go.jp/shingi/2003/12/s1202-3h.html", page)
        self.assertIn("平成14年度と平成15年度の額は、上の「全国一覧」と47都道府県すべてで一致することを", self.read("cite/index.html"))
        self.assertIn("<td>昭和53年度</td><td>320.88円</td>", page)
        self.assertIn("昭和53年度などの額に小数があるのは、出典の表のとおりです。", page)
        self.assertNotIn("に小数があるのは", self.read("hokkaido/index.html"))


class NationalTrendTest(SiteFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raw, cls.old = _raw(), history_old.load()
        cls.series, cls.split = all_series(cls.raw, cls.old)

    def test_the_national_table_has_a_row_for_every_year_with_recomputed_figures(self):
        page = self.read("history/index.html")
        rows = rows_of(page, "<h2>年度別の一覧(全国加重平均・最高額・最低額)</h2>")
        self.assertEqual(len(rows) - 1, 50)
        body = {r[0]: r for r in rows[1:]}
        prev = None
        for fy in YEARS:
            avg = self.old["national_weighted_average"].get(str(fy)) if fy < 2002 else self.raw["national_weighted_average"][str(fy)]
            vals = [s[fy] for s in self.series.values() if s[fy] is not None] + (list(self.split[fy]) if fy in self.split else [])
            hi, lo = max(vals), min(vals)
            row = body[label(fy)]
            self.assertEqual(row[1], "-" if avg is None else f"{round(avg):,}円", fy)
            up = None if avg is None or prev is None else round(avg) - round(prev)
            self.assertEqual(row[2], signed(up), fy)
            self.assertEqual(row[3], "-" if up is None else f"{up / round(prev) * 100:.1f}%", fy)
            self.assertTrue(row[4].startswith(f"{hi:,}円"), (fy, row[4]))
            self.assertTrue(row[5].startswith(f"{lo:,}円"), (fy, row[5]))
            self.assertEqual(row[6], f"{hi - lo:,}円" if (hi - lo) == int(hi - lo) else money(hi - lo), fy)
            prev = avg if avg is not None else prev

    def test_the_title_and_the_headings_answer_the_search_words(self):
        page = self.read("history/index.html")
        self.assertIn("<title>最低賃金の推移 全国加重平均の歴代一覧とグラフ(昭和52年度〜令和8年度)</title>", page)
        for heading in ("全国加重平均の歴代の推移(グラフ)", "歴代の引上げ額ランキング(全国加重平均)", "最高額と最低額の推移"):
            self.assertIn(f"<h2>{heading}</h2>", page)
        self.assertEqual(page.count('<svg class="chart"'), 3)

    def test_the_rankings_of_the_years_are_the_biggest_rises(self):
        page = self.read("history/index.html")
        avg = {fy: (self.old["national_weighted_average"][str(fy)] if fy < 2002 else self.raw["national_weighted_average"][str(fy)]) for fy in range(1978, 2027)}
        ups = {fy: round(avg[fy]) - round(avg[fy - 1]) for fy in range(1979, 2027)}
        best = sorted(ups, key=lambda fy: (-ups[fy], -fy))[:10]
        rank_rows = rows_of(page, "<h3>引上げ額が大きい年度</h3>")
        self.assertEqual([row[1] for row in rank_rows[1:]], [label(fy) for fy in best])
        self.assertEqual([row[2] for row in rank_rows[1:]], [f"+{ups[fy]}円" for fy in best])
        pct = {fy: ups[fy] / round(avg[fy - 1]) * 100 for fy in ups}
        best_pct = sorted(pct, key=lambda fy: (-pct[fy], -fy))[:10]
        pct_rows = rows_of(page, "<h3>上がり率が大きい年度</h3>")
        self.assertEqual([row[1] for row in pct_rows[1:]], [label(fy) for fy in best_pct])

    def test_the_one_yen_difference_in_heisei_14_is_stated(self):
        page = self.read("history/index.html")
        self.assertIn("平成14年度の全国加重平均は、2つの資料で1円違います(この資料は664円、全国一覧は663円)", page)
        self.assertEqual(self.old["national_weighted_average"]["2002"], 664)
        self.assertEqual(round(self.raw["national_weighted_average"]["2002"]), 663)

    def test_kyoto_never_holds_the_highest_or_the_lowest_amount(self):
        ys = long_history.build(self.raw, self.old, 2026)[1]
        for y in ys:
            self.assertNotIn("京都(南)", y["max_names"] + y["min_names"], y["fy"])
            self.assertNotIn("京都(北)", y["max_names"] + y["min_names"], y["fy"])


if __name__ == "__main__":
    unittest.main()
