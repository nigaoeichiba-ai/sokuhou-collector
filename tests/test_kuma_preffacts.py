"""kuma-sokuho.com prefecture pages (2026-11-09): sentences that are true of that prefecture only (sites/kuma/preffacts.py).

Each sentence is written only when it applies; nothing is divided by a population or an area; every number must match the ministry's table.
The negative cases make the check fail when a sentence is written for a prefecture it does not fit.
"""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, preffacts
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data

INJ_YEARS = [f"H{i}" for i in range(20, 31)] + ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]


def make(inj=None, total=None, monthly=None, ytd=None, emergency=None, fatal=None, captures=None, has=True):
    """A prefecture row and the shared data, the shapes the build gives (only what preffacts reads)."""
    inj = inj or {}
    i = {y: tuple(inj.get(y, (0, 0, 0))) for y in INJ_YEARS}
    ys = ["R04", "R05", "R06", "R07", "R08"]
    total = total or {"R04": 200, "R05": 300, "R06": 400, "R07": 900, "R08": 500}
    flat = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    monthly = monthly or {y: flat[:] for y in ys}
    r = {"name": "テスト県", "short": "テスト", "has": has, "inj": i, "rank": {"injured": 7}, "total": total, "monthly": monthly,
         "ytd": ytd or {"R04": 50, "R05": 80, "R06": 100, "R07": 200, "R08": 500}}
    d = {"inj": {"years": INJ_YEARS}, "cur": "R08", "done": "R07", "years": ys, "months": [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3], "latest_month": 8,
         "inj_as_of": "R08年9月末", "captures": captures,
         "emergency": {"R07": {"cases": emergency or []}, "R08": {"cases": []}},
         "fatal": {"R07": {"incidents": fatal or []}, "R08": {"incidents": []}}}
    return d, r


class LeadTest(unittest.TestCase):
    def test_injury_and_deaths_are_stated_with_the_ranking_and_the_total(self):
        d, r = make(inj={"R07": (3, 4, 1), "R03": (1, 2, 2)})
        a, b = preffacts.lead(d, r)
        self.assertIn("3件・4人(うち死亡1人)で、39道府県中7位", a)
        self.assertIn("平成20年度以降の死亡者は、合計3人です", b)
        self.assertIn("最も多かったのは令和3年度の2人", b)

    def test_a_prefecture_without_injury_in_the_last_year_says_so_and_names_the_last_one(self):
        d, r = make(inj={"R02": (2, 2, 0)})
        a, b = preffacts.lead(d, r)
        self.assertIn("令和7年度は、人身被害の記録がありません", a)
        self.assertIn("直近の人身被害は令和2年度(2人)", a)
        self.assertIn("死亡者の記録はありません", b)

    def test_a_prefecture_without_any_injury_does_not_name_a_last_year(self):
        d, r = make()
        a, _ = preffacts.lead(d, r)
        self.assertIn("平成20年度から令和7年度まで、人身被害の記録がありません", a)
        self.assertNotIn("直近", a)

    def test_the_deaths_of_the_current_partial_year_are_counted(self):
        d, r = make(inj={"R08": (1, 1, 1)})
        _, b = preffacts.lead(d, r)
        self.assertIn("合計1人", b)
        self.assertIn("最後は令和8年度", b)


class InjuryHistoryTest(unittest.TestCase):
    def test_five_year_comparison_uses_the_full_years_only(self):
        d, r = make(inj={"R07": (1, 2, 0), "R06": (1, 3, 0), "H29": (1, 1, 0), "R08": (9, 9, 9)})
        html = preffacts.injury_html(d, r)
        self.assertIn("合計3件・6人", html)                       # R08 is partial and is not in the total
        self.assertIn("直近5年度(令和3年度から令和7年度)の合計は5人", html)
        self.assertIn("その前の5年度(1人)", html)
        self.assertIn("9件・9人(うち死亡9人)", html)               # the partial year is stated on its own, with its date

    def test_no_recent_injury_is_said_as_such(self):
        d, r = make(inj={"H29": (1, 4, 0)})
        self.assertIn("直近5年度(令和3年度から令和7年度)は、人身被害がありません。その前の5年度は4人", preffacts.injury_html(d, r))

    def test_all_zero_says_there_is_no_record_and_nothing_else(self):
        d, r = make()
        html = preffacts.injury_html(d, r)
        self.assertIn("人身被害の記録はありません", html)
        self.assertNotIn("直近5年度", html)


class SightingsTest(unittest.TestCase):
    def test_the_last_full_year_is_the_peak(self):
        d, r = make()
        s = preffacts.items(d, r)[0]
        self.assertIn("令和7年度の900件は、令和4年度以降で最も多い件数です", s)
        self.assertIn("最も少なかった令和4年度(200件)の約4.5倍", s)

    def test_another_year_is_the_peak(self):
        d, r = make(total={"R04": 200, "R05": 300, "R06": 1000, "R07": 500, "R08": 100})
        s = preffacts.items(d, r)[0]
        self.assertIn("最も多かったのは令和6年度(1,000件)", s)
        self.assertIn("令和7年度は、その50%にあたる500件", s)

    def test_this_years_period_is_compared_only_when_the_base_is_big_enough_and_the_change_is_large(self):
        d, r = make(ytd={"R04": 1, "R05": 1, "R06": 1, "R07": 52, "R08": 127})
        self.assertTrue(any("前年度の同じ期間(52件)の約2.4倍" in x for x in preffacts.items(d, r)))
        d, r = make(ytd={"R04": 1, "R05": 1, "R06": 1, "R07": 20, "R08": 127})        # base under 30
        self.assertFalse(any("前年度の同じ期間" in x for x in preffacts.items(d, r)))
        d, r = make(ytd={"R04": 1, "R05": 1, "R06": 1, "R07": 100, "R08": 110})       # a small change
        self.assertFalse(any("前年度の同じ期間" in x for x in preffacts.items(d, r)))

    def test_a_prefecture_without_the_ministrys_table_gets_no_sighting_sentence(self):
        d, r = make(has=False, total={y: None for y in ("R04", "R05", "R06", "R07", "R08")})
        self.assertEqual(preffacts.items(d, r), [])

    def test_a_missing_year_makes_the_comparison_silent(self):
        d, r = make(total={"R04": None, "R05": 300, "R06": 400, "R07": 900, "R08": 500})
        self.assertEqual(preffacts._sightings(d, r), [])


class SeasonTest(unittest.TestCase):
    @staticmethod
    def monthly(summer, autumn):
        v = [0] * 12
        v[2:5] = [summer // 3] * 3
        v[5:8] = [autumn // 3] * 3
        v[0] = 30
        return v

    def test_always_autumn(self):
        ys = ["R04", "R05", "R06", "R07", "R08"]
        m = {y: self.monthly(60, 300) for y in ys}
        d, r = make(monthly=m, total={y: sum(m[y]) for y in ys})
        s = preffacts._season(d, r)[0]
        self.assertTrue(s.startswith("4年度のすべてで、9〜11月の件数が6〜8月を上回りました"))

    def test_always_summer(self):
        ys = ["R04", "R05", "R06", "R07", "R08"]
        m = {y: self.monthly(300, 60) for y in ys}
        d, r = make(monthly=m, total={y: sum(m[y]) for y in ys})
        self.assertTrue(preffacts._season(d, r)[0].startswith("4年度のすべてで、6〜8月の件数が9〜11月を上回りました"))

    def test_mixed_years_are_named(self):
        ys = ["R04", "R05", "R06", "R07", "R08"]
        m = {"R04": self.monthly(60, 300), "R05": self.monthly(300, 60), "R06": self.monthly(300, 60), "R07": self.monthly(60, 300), "R08": self.monthly(0, 0)}
        d, r = make(monthly=m, total={y: sum(m[y]) for y in ys})
        s = preffacts._season(d, r)[0]
        self.assertIn("4年度のうち2年度(令和4年度・令和7年度)", s)
        self.assertIn("入れ替わっています", s)

    def test_a_small_year_makes_it_silent(self):
        ys = ["R04", "R05", "R06", "R07", "R08"]
        m = {y: self.monthly(3, 6) for y in ys}
        d, r = make(monthly=m, total={y: sum(m[y]) for y in ys})
        self.assertEqual(preffacts._season(d, r), [])


class RateAndCaptureTest(unittest.TestCase):
    def test_injuries_per_1000_sightings_are_computed_from_the_table_and_limited_to_the_same_prefecture(self):
        d, r = make(inj={"R04": (1, 1, 0), "R07": (2, 9, 0)}, total={"R04": 200, "R05": 300, "R06": 400, "R07": 900, "R08": 500})
        s = preffacts._rate(d, r)[0]
        self.assertIn("令和4年度が5.0人", s)
        self.assertIn("令和7年度が10.0人", s)
        self.assertIn("最も高かったのは令和7年度", s)
        self.assertIn("同じ県の年度どうしにだけ使えます", s)

    def test_a_year_with_few_sightings_makes_it_silent(self):
        d, r = make(inj={"R04": (1, 1, 0)}, total={"R04": 100, "R05": 300, "R06": 400, "R07": 900, "R08": 500})
        self.assertEqual(preffacts._rate(d, r), [])

    def test_no_injury_at_all_makes_it_silent(self):
        d, r = make()
        self.assertEqual(preffacts._rate(d, r), [])

    def test_captures_against_sightings(self):
        c = {"by": {"テスト": {"R06": (80, 80, 0), "R07": (270, 270, 0)}}, "years": ["R04", "R05", "R06", "R07", "R08"], "done": "R07"}
        d, r = make(captures=c)
        s = preffacts._capture(d, r)[0]
        self.assertIn("令和7年度の許可捕獲は270頭で、出没件数(900件)の30%", s)
        self.assertIn("令和6年度は80頭で20%", s)

    def test_a_prefecture_missing_from_the_capture_table_is_silent(self):
        c = {"by": {}, "years": ["R04", "R05", "R06", "R07", "R08"], "done": "R07"}
        d, r = make(captures=c)
        self.assertEqual(preffacts._capture(d, r), [])


class EmergencyAndDeathMonthsTest(unittest.TestCase):
    def test_emergency_is_stated_only_when_there_is_a_case(self):
        d, r = make()
        self.assertEqual(preffacts._emergency(d, r), [])
        d, r = make(emergency=[{"prefecture": "テスト県"}, {"prefecture": "他県"}])
        self.assertEqual(preffacts._emergency(d, r), ["環境省が把握する緊急銃猟は、令和7年度が1件、令和8年度が0件です。"])

    def test_death_months_need_two_incidents(self):
        inc = [{"prefecture": "テスト県", "date": "2025-06-22"}, {"prefecture": "テスト県", "date": "2025-10-03"}, {"prefecture": "他県", "date": "2025-07-01"}]
        d, r = make(fatal=inc)
        self.assertEqual(preffacts._death_months(d, r), ["環境省の一覧にある死亡事故2件が起きた月は、6月・10月です。"])
        d, r = make(fatal=inc[:1])
        self.assertEqual(preffacts._death_months(d, r), [])


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class PrefecturePagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, CFG, cls.out, release=True)
        cls.d = build.prepare(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def pages(self):
        for r in self.d["rows"]:
            if build.has_no_bears(self.d, r):
                continue
            yield r, (self.out / r["slug"] / "index.html").read_text(encoding="utf-8")

    def test_every_prefecture_page_opens_with_its_injuries_and_deaths(self):
        n_pages = 0
        for r, html in self.pages():
            n_pages += 1
            lead = re.search(r'<p class="lead">(.*?)</p>', html, re.S).group(1)
            self.assertIn("人身被害", lead, r["name"])
            self.assertTrue(("死亡者は、合計" in lead) or ("死亡者の記録はありません" in lead), r["name"])
            p = r["inj"][self.d["done"]]
            if p[1]:
                self.assertIn(f"{p[0]:,}件・{p[1]:,}人(うち死亡{p[2]:,}人)で、39道府県中{r['rank']['injured']}位", lead, r["name"])
        self.assertGreaterEqual(n_pages, 30)

    def test_the_numbers_in_the_injury_history_are_the_tables_numbers(self):
        for r, html in self.pages():
            years = [y for y in self.d["inj"]["years"] if y != self.d["cur"]]
            people = sum(r["inj"][y][1] for y in years)
            cases = sum(r["inj"][y][0] for y in years)
            if people:
                self.assertIn(f"合計{cases:,}件・{people:,}人です", html, r["name"])
            else:
                self.assertIn("人身被害の記録はありません", html, r["name"])

    def test_the_sighting_sentences_follow_the_ministrys_table(self):
        for r, html in self.pages():
            if not r["has"]:
                continue
            full = [y for y in self.d["years"] if y != self.d["cur"]]
            if any(r["total"][y] is None for y in full):
                continue
            top = max(full, key=lambda y: (r["total"][y], y))
            low = min(full, key=lambda y: (r["total"][y], y))
            if r["total"][low] > 0 and r["total"][top] > r["total"][low]:
                self.assertIn(f"{r['total'][top]:,}件", html, r["name"])

    def test_pages_differ_in_which_sentences_they_carry(self):
        sets = []
        for r, html in self.pages():
            body = html.split("<main", 1)[1]
            sets.append(frozenset(re.findall(r"最も多い件数です|入れ替わっています|のすべてで、9〜11月|のすべてで、6〜8月|緊急銃猟は、令和|起きた月は|許可捕獲は\d|直近5年度[^。]*がありません", body)))
        self.assertGreaterEqual(len(set(sets)), 4)

    def test_nothing_is_divided_by_a_population_or_an_area(self):
        for r, html in self.pages():
            text = re.sub(r"<[^>]+>", "", html.split("<main", 1)[1].split("</main>", 1)[0])
            for bad in ("人口", "面積", "10万人あたり", "100万人あたり"):
                self.assertNotIn(bad, text, r["name"])

    def test_the_new_sentences_avoid_the_banned_words_of_the_text_gate(self):
        for r, html in self.pages():
            body = html.split("<main", 1)[1].split("</main>", 1)[0]
            new = re.search(r'<p class="lead">(.*?)</p>', body, re.S).group(1) + (body.split("から言えること</h2>", 1)[1].split("</ul>", 1)[0] if "から言えること</h2>" in body else "")
            for bad in ("いちばん", "数えています", "見てください", "並びます", "載せます", "入口"):
                self.assertNotIn(bad, new, r["name"])

    def test_a_negative_case_a_season_sentence_for_a_prefecture_with_small_years_would_be_caught(self):
        d, r = make(total={"R04": 20, "R05": 30, "R06": 40, "R07": 50, "R08": 10}, monthly={y: [1] * 12 for y in ("R04", "R05", "R06", "R07", "R08")})
        self.assertEqual(preffacts._season(d, r), [])


if __name__ == "__main__":
    unittest.main()
