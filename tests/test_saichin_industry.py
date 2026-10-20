"""The industry-specific minimum wages: the parser of the Ministry's table (against a saved copy of the page) and the section of each prefecture page.

The expected rows are read from the saved page by a second, separate reading (cell by cell), not by the parser under test."""
import copy
import re
import tempfile
import unittest
from pathlib import Path

from sites.saichin import build, industry_view
from sokuhou.sources import mhlw_industry
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401

FIXTURE = Path(__file__).parent / "fixtures" / "mhlw_industry_nationallist.html"
ERA = {"昭和": 1925, "平成": 1988, "令和": 2018}
PREF_CELL = re.compile(r"北海道|.{2,3}[都府県]")
DATE_CELL = re.compile(r"(昭和|平成|令和)(\d+|元)\.(\d+)\.(\d+)")


def read_rows(text):
    """[(prefecture as written, industry, hourly text, daily text, date text)] by walking the page's table cells."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>.*?</td>", text, re.S)]
    pref, rows, i = None, [], 0
    while i < len(cells):
        if PREF_CELL.fullmatch(cells[i]):
            pref = cells[i]
            i += 1
        elif i + 3 < len(cells) and DATE_CELL.fullmatch(cells[i + 3]):
            rows.append((pref, cells[i], cells[i + 1], cells[i + 2], cells[i + 3]))
            i += 4
        else:
            i += 1
    return rows


def short(p):
    return p if p == "北海道" else p[:-1]


def iso(text):
    m = DATE_CELL.fullmatch(text)
    return f"{ERA[m.group(1)] + (1 if m.group(2) == '元' else int(m.group(2))):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"


def yen(text):
    return int(re.search(r"([\d,]+)円", text).group(1).replace(",", ""))


class ParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")
        cls.data = mhlw_industry.parse(cls.html)

    def test_every_row_of_the_page_is_parsed_with_its_values(self):
        want = read_rows(self.html)
        got = self.data["rows"]
        self.assertEqual(len(got), len(want))
        self.assertEqual(len(got), 223)
        for g, (p, ind, hourly, daily, eff) in zip(got, want):
            self.assertEqual(g["pref"], short(p))
            self.assertEqual(g["industry"], ind)
            self.assertEqual(g["hourly"], yen(hourly))
            self.assertEqual(g["regional_applies"], "※" in hourly)
            self.assertEqual(g["daily"], yen(daily) if "円" in daily else None)
            self.assertEqual(g["effective_date"], iso(eff))

    def test_known_rows(self):
        rows = [r for r in self.data["rows"] if r["pref"] == "千葉"]
        steel = next(r for r in rows if r["industry"] == "鉄鋼業")
        self.assertEqual((steel["hourly"], steel["effective_date"], steel["regional_applies"]), (1210, "2025-12-25", False))
        self.assertEqual(len([r for r in self.data["rows"] if r["pref"] == "岐阜"]), 3)   # Gifu's rows follow rows that hold only the prefecture's name or nothing
        self.assertEqual({r["pref"] for r in self.data["rows"]}, set(mhlw_industry.PREFECTURES))
        self.assertEqual(self.data["table_label"], "令和7年度")
        self.assertEqual(sum(1 for r in self.data["rows"] if r["daily"] is not None), 3)

    def test_it_refuses_partial_data(self):
        with self.assertRaises(mhlw_industry.IndustryParseError):
            mhlw_industry.parse(self.html.replace("沖縄県</a>", "沖縄x</a>"))
        with self.assertRaises(mhlw_industry.IndustryParseError):
            mhlw_industry.parse(re.sub(r"この表は.*?現在のものです。", "", self.html))
        with self.assertRaises(mhlw_industry.IndustryParseError):
            mhlw_industry.parse(self.html[: len(self.html) // 2])


class SectionTest(SiteFixture):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.data = mhlw_industry.parse(FIXTURE.read_text(encoding="utf-8"))
        cls.data["fetched_at"] = "2026-10-20T19:15:47+09:00"
        cls.files = build.render_site(_raw(), CFG, cls.out, release=True, industry=cls.data)
        cls.d = build.prepare(_raw())
        cls.want = {}
        for p, ind, hourly, daily, eff in read_rows(FIXTURE.read_text(encoding="utf-8")):
            cls.want.setdefault(short(p), []).append((ind, "※" in hourly, yen(hourly), daily, iso(eff)))

    def table(self, slug):
        page = self.read(f"{slug}/index.html")
        section = page.split("の特定(産業別)最低賃金</h2>", 1)[1]
        table = re.search(r"<table>.*?</table>", section, re.S).group(0)
        body = re.search(r"<tbody>(.*?)</tbody>", table, re.S).group(1)
        return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td>(.*?)</td>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S)]

    def test_each_prefecture_page_lists_exactly_its_industries(self):
        for r in self.d["rows"]:
            rows = self.table(r["slug"])
            want = self.want[r["short"]]
            self.assertEqual(len(rows), len(want), r["name"])
            self.assertEqual(sorted(x[0] for x in rows), sorted(w[0] for w in want), r["name"])
            for ind, star, amount, daily, eff in want:
                row = next(x for x in rows if x[0] == ind)
                y, m, d_ = eff.split("-")
                self.assertEqual(row[1], f"{amount:,}円", (r["name"], ind))
                self.assertEqual(row[3], f"{int(y)}年{int(m)}月{int(d_)}日", (r["name"], ind))
                self.assertEqual(row[4], "地域別(※)" if star else "特定の額", (r["name"], ind))
                self.assertEqual(row[2], f"{yen(daily):,}円" if "円" in daily else "-", (r["name"], ind))
            applying = [x for x in rows if x[4] == "特定の額"]
            amounts = [int(x[1][:-1].replace(",", "")) for x in applying]
            self.assertEqual(amounts, sorted(amounts, reverse=True), r["name"])
            self.assertEqual(rows[: len(applying)], applying, r["name"])           # the amounts that apply come first

    def test_the_sentences_count_and_name_the_industries(self):
        for r in self.d["rows"]:
            text = re.sub(r"<[^>]+>", "", self.read(f"{r['slug']}/index.html"))
            rows = self.want[r["short"]]
            apply_ = [x for x in rows if not x[1]]
            self.assertIn(f"{r['name']}には、特定(産業別)最低賃金が{len(rows)}産業分あります。", text, r["name"])
            if apply_:
                self.assertIn(f"このうち{len(apply_)}産業は、特定の額が適用されます。", text, r["name"])
                top = max(apply_, key=lambda x: x[2])
                self.assertIn(f"最も高いのは、{top[0]}の{top[2]:,}円で、", text, r["name"])
                if len(rows) > len(apply_):
                    self.assertIn(f"残りの{len(rows) - len(apply_)}産業は、「※」が付いていて、地域別最低賃金が適用されます。", text, r["name"])
            else:
                self.assertIn("いずれも、厚生労働省の表で「※」が付いていて、地域別最低賃金が適用される額です。", text, r["name"])

    def test_each_region_page_counts_the_industries_that_apply_in_its_prefectures(self):
        for slug, rname, shorts in build.REGIONS:
            page = self.read(f"area/{slug}/index.html")
            section = page.split(f"<h2>{rname}の特定(産業別)最低賃金</h2>", 1)[1]
            body = re.search(r"<tbody>(.*?)</tbody>", section, re.S).group(1)
            rows = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td>(.*?)</td>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S)]
            self.assertEqual(len(rows), len(shorts), slug)
            counted = {}
            for name, n_all, n_apply, top in rows:
                short_ = next(s for s in shorts if name.startswith(s))
                want = self.want[short_]
                applying = [w for w in want if not w[1]]
                self.assertEqual((int(n_all), int(n_apply)), (len(want), len(applying)), name)
                if applying:
                    best = max(applying, key=lambda w: w[2])
                    self.assertEqual(top, f"{best[0]}({best[2]:,}円)", name)
                else:
                    self.assertEqual(top, "-", name)
                for w in applying:
                    counted.setdefault(w[0], []).append(name)
            text = re.sub(r"<[^>]+>", "", section.split("<table>", 1)[0])
            n_with = sum(1 for r in rows if int(r[2]) > 0)
            if n_with == 0:
                self.assertIn(f"{rname}の{len(shorts)}都道府県には、特定(産業別)最低賃金の額が適用される産業が、ありません。", text, slug)
                continue
            self.assertIn(f"{rname}の{len(shorts)}都道府県のうち、特定(産業別)最低賃金の額が適用される産業が1つ以上あるのは{n_with}都道府県です。", text, slug)
            multi = sorted(((n, v) for n, v in counted.items() if len(v) > 1), key=lambda t: (-len(t[1]), t[0]))
            if multi:
                self.assertIn("、".join(f"{n}({len(v)}都道府県)" for n, v in multi[:4]), text, slug)
            else:
                self.assertIn("同じ産業が2つ以上の都道府県で適用されることは、ありません。", text, slug)

    def test_the_source_the_date_and_the_rule_are_stated(self):
        page = self.read("chiba/index.html")
        self.assertIn("厚生労働省「特定(産業別)最低賃金全国一覧」(令和7年度)。データの取得日: 2026年10月20日。", page)
        self.assertIn("高い方が適用されます(最低賃金法第6条第1項)", page)

    def test_without_the_data_the_section_is_not_written(self):
        out = Path(self.tmp.name) / "plain"
        build.render_site(_raw(), CFG, out, release=True)
        self.assertNotIn("特定(産業別)最低賃金</h2>", (out / "chiba" / "index.html").read_text(encoding="utf-8"))

    def test_the_view_refuses_a_prefecture_without_rows(self):
        bad = copy.deepcopy(self.data)
        bad["rows"] = [r for r in bad["rows"] if r["pref"] != "沖縄"]
        with self.assertRaises(industry_view.IndustryError):
            industry_view.view(bad, self.d)


class CollectorRegistrationTest(unittest.TestCase):
    def test_the_source_is_in_the_daily_group_and_its_check_refuses_a_collapse(self):
        from sokuhou import run
        self.assertIn("minwage_industry", [s.name for s in run.GROUPS["daily"]])
        old = {"rows": [{}] * 200}
        run.check_minwage_industry(old, {"rows": [{}] * 150})
        run.check_minwage_industry(None, {"rows": [{}] * 10})
        with self.assertRaises(run.SanityError):
            run.check_minwage_industry(old, {"rows": [{}] * 100})


if __name__ == "__main__":
    unittest.main()
