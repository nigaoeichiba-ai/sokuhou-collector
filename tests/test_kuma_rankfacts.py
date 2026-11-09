"""kuma-sokuho.com ranking pages (2026-11-09): the columns and sentences added to the ministry's tables (sites/kuma/rankfacts.py, population.py).

The population is used only where the figure is counted on one national standard (injuries, deaths); never for sighting counts.
Each rule has a negative case.
"""
import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from sites.kuma import build, population, rankfacts
from sokuhou import prefectures as pf
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data


def _xlsx(rows: dict) -> bytes:
    """A minimal workbook with strings in the shared table, the shape population.parse reads: {row: {column: text}}."""
    strings, xml = [], []
    for r, cells in rows.items():
        cs = []
        for col, val in cells.items():
            if isinstance(val, int):
                cs.append(f'<c r="{col}{r}"><v>{val}</v></c>')
            else:
                strings.append(val)
                cs.append(f'<c r="{col}{r}" t="s"><v>{len(strings) - 1}</v></c>')
        xml.append(f'<row r="{r}">{"".join(cs)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml)}</sheetData></worksheet>')
    return buf.getvalue()


class PopulationTest(unittest.TestCase):
    def test_the_stored_table_has_the_47_prefectures_and_adds_up_to_the_national_total(self):
        p = population.load()
        self.assertEqual(set(p["population"]), set(population.NAMES))
        self.assertLessEqual(abs(sum(p["population"].values()) - 123802), 20)             # the national figure of the same table, in thousands (rounding of each row)
        self.assertEqual(p["as_of"], "2024-10-01")
        self.assertIn("総務省統計局「人口推計」", p["source"])
        self.assertTrue(p["table"].startswith("https://www.stat.go.jp/"))
        self.assertGreater(p["population"]["東京都"], p["population"]["鳥取県"] * 20)      # a sanity check that the thousands were not mixed up

    def test_parse_reads_the_name_column_with_its_katakana_reading_and_the_total_column(self):
        rows = {i + 1: {"C": name + "ヨミ", "E": 100 + i} for i, name in enumerate(population.NAMES)}
        got = population.parse(_xlsx(rows))
        self.assertEqual(got["北海道"], 100)
        self.assertEqual(got["沖縄県"], 146)

    def test_parse_refuses_a_table_with_a_prefecture_missing(self):
        rows = {i + 1: {"C": name, "E": 100} for i, name in enumerate(population.NAMES[:-1])}
        with self.assertRaises(ValueError):
            population.parse(_xlsx(rows))

    def test_per_million_divides_by_the_thousands_in_the_table(self):
        with mock.patch.object(rankfacts, "_POP", {"population": {"秋田県": 900}, "as_of": "2024-10-01", "source": "x"}):
            self.assertAlmostEqual(rankfacts.per_million(9, "秋田県"), 10.0)                # 9 people in 900,000 = 10 per million




class RankColumnsTest(unittest.TestCase):
    @staticmethod
    def make(totals, ytd, inj=None, years=("R04", "R05", "R06", "R07", "R08")):
        r = {"name": "テスト県", "has": True, "total": dict(zip(years, totals)), "ytd": {"R07": ytd[0], "R08": ytd[1]}, "inj": inj or {}}
        d = {"years": list(years), "cur": "R08", "done": "R07", "months": [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3], "latest_month": 8}
        return d, r

    def test_the_direction_of_each_year_and_of_this_years_period(self):
        d, r = self.make([100, 200, 300, 100, 0], (50, 80))
        self.assertEqual(rankfacts.directions(d, r), ["増", "減", "増"])
        d, r = self.make([100, 100, 100, 100, 0], (50, 50))
        self.assertEqual(rankfacts.directions(d, r), ["同", "同", "同"])

    def test_a_year_with_no_count_on_both_sides_is_a_dash_not_a_direction(self):
        d, r = self.make([0, 0, 0, 0, 0], (0, 0))
        self.assertEqual(rankfacts.directions(d, r), ["−", "−", "−"])
        d, r = self.make([None, 5, None, 5, 0], (None, None))
        self.assertEqual(rankfacts.directions(d, r), ["−", "−", "−"])

    def test_the_summary_counts_the_prefectures_that_went_up_and_names_the_ones_that_went_up_three_times(self):
        d, a = self.make([1, 10, 20, 40, 0], (5, 9))
        _, b = self.make([1, 10, 20, 5, 0], (9, 5))
        a["name"], b["name"] = "甲県", "乙県"
        html = rankfacts.sightings_after(d, [a, b])
        self.assertIn("令和6年度は、前年度(同じ期間)より増えたのが2道府県、減ったのが0道府県でした", html)
        self.assertIn("令和7年度は、前年度(同じ期間)より増えたのが1道府県、減ったのが1道府県でした", html)
        self.assertIn("3つとも増えたのは、甲県です", html)
        self.assertNotIn("3つとも減ったのは", html)

    def test_deaths_trend_is_the_five_last_full_years_oldest_first(self):
        years = [f"H{i}" for i in range(20, 31)] + ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]
        inj = {y: (0, 0, 0) for y in years}
        inj.update({"R03": (1, 1, 1), "R05": (1, 2, 2), "R07": (1, 1, 1), "R08": (5, 5, 5)})
        r = {"name": "テスト県", "inj": inj}
        d = {"inj": {"years": years}, "cur": "R08"}
        self.assertEqual(rankfacts.deaths_trend(d, r), "1 / 0 / 2 / 0 / 1")
        self.assertIn("令和3年度から令和7年度", rankfacts.deaths_head(d))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class RankingPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, CFG, cls.out, release=True)
        cls.d = build.prepare(cls.raw)
        cls.pop = population.load()["population"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    @staticmethod
    def rows(html):
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        return [re.findall(r"<td>(.*?)</td>", tr, re.S) for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S)]

    def test_injuries_per_million_in_every_row_is_the_tables_number_over_the_population(self):
        rows = self.rows(self.read("ranking/injuries/index.html"))
        self.assertGreaterEqual(len(rows), 35)
        by_name = {r["name"]: r for r in self.d["rows"]}
        for cells in rows:
            name = re.sub(r"<[^>]+>", "", cells[1])
            r = by_name[name]
            self.assertEqual(cells[6], f"{r['inj'][self.d['done']][1] / self.pop[name] * 1000:.1f}", name)
            self.assertEqual(cells[7], f"{r['injured7'] / self.pop[name] * 1000:.1f}", name)

    def test_the_injury_page_names_the_population_source_and_the_year(self):
        html = self.read("ranking/injuries/index.html")
        self.assertIn("総務省統計局「人口推計」(2024年10月1日現在", html)
        self.assertIn("出没件数は都道府県ごとに数え方が違うため、人口では割りません", html)

    def test_no_sighting_figure_is_divided_by_a_population(self):
        for rel in ("ranking/sightings/index.html", "ranking/change/index.html"):
            html = self.read(rel)
            text = re.sub(r"<[^>]+>", "", html.split("<main", 1)[1].split("</main>", 1)[0])
            for bad in ("人口", "あたり"):
                self.assertNotIn(bad, text, rel)

    def test_the_sightings_table_has_the_direction_column_and_it_matches_the_numbers(self):
        rows = self.rows(self.read("ranking/sightings/index.html"))
        by_name = {r["name"]: r for r in self.d["rows"]}
        for cells in rows:
            r = by_name[re.sub(r"<[^>]+>", "", cells[1])]
            self.assertEqual(cells[6].split(" / "), rankfacts.directions(self.d, r))
        d = self.d
        r = by_name[re.sub(r"<[^>]+>", "", rows[0][1])]
        ys = d["years"]
        expect = "増" if r["total"][ys[-2]] > r["total"][ys[-3]] else ("減" if r["total"][ys[-2]] < r["total"][ys[-3]] else "同")
        self.assertEqual(rows[0][6].split(" / ")[1], expect)

    def test_the_deaths_table_shows_the_five_years_one_by_one(self):
        rows = self.rows(self.read("ranking/deaths/index.html"))
        by_name = {r["name"]: r for r in self.d["rows"]}
        ys = [y for y in self.d["inj"]["years"] if y != self.d["cur"]][-5:]
        for cells in rows:
            r = by_name[re.sub(r"<[^>]+>", "", cells[1])]
            self.assertEqual(cells[4], " / ".join(str(r["inj"][y][2]) for y in ys))
            self.assertEqual(int(cells[3]), sum(r["inj"][y][2] for y in ys))                 # the column before it is the sum of those five

    def test_a_negative_case_a_wrong_population_would_change_the_numbers_the_test_reads(self):
        with mock.patch.object(rankfacts, "_POP", {"population": {n: 1 for n in population.NAMES}, "as_of": "2024-10-01", "source": "x"}):
            self.assertNotEqual(f"{rankfacts.per_million(3, '秋田県'):.1f}", f"{3 / self.pop['秋田県'] * 1000:.1f}")


if __name__ == "__main__":
    unittest.main()
