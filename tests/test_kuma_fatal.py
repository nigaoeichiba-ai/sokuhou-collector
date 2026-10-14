"""The dated answer to "did anyone die of bears in this prefecture?" (build.fatal_answer): only the ministry's lists, always with their dates."""
import re
import unittest

from sites.kuma import build

D = {
    "done": "R07", "cur": "R08", "inj_as_of": "R08年8月末",
    "fatal": {"R07": {"as_of": "2025-11-20", "incidents": [
        {"date": "2025-10-03", "found_date": False, "place": "栗原市", "prefecture": "宮城県", "victims": 1},
        {"date": "2025-11-03", "found_date": True, "place": "湯沢市", "prefecture": "秋田県", "victims": 1}]},
              "R08": {"as_of": "2026-07-10", "incidents": [
                  {"date": "2026-06-02", "found_date": False, "place": "秋田市", "prefecture": "秋田県", "victims": 1}]}},
    "inj": {"years": ["H20", "H21", "H22", "R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]},
}


def pref(name, deaths_by_year):
    return {"name": name, "inj": {y: [0, 0, deaths_by_year.get(y, 0)] for y in D["inj"]["years"]}}


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class FatalAnswerTest(unittest.TestCase):
    def test_a_prefecture_in_the_ministrys_list_gets_its_incidents_with_their_dates_and_the_two_list_dates(self):
        t = text(build.fatal_answer(D, pref("秋田県", {"H22": 1, "R07": 4, "R08": 1})))
        self.assertIn("令和7年度は2025年11月20日時点、令和8年度は2026年7月10日時点", t)
        self.assertIn("秋田県の死亡事故が2件(2人)載っています", t)
        self.assertIn("2026年6月2日 秋田市", t)
        self.assertIn("2025年11月3日(被害者発見日) 湯沢市", t)
        self.assertLess(t.index("2026年6月2日"), t.index("2025年11月3日"))              # newest first
        self.assertIn("死亡者が出た年度は、令和8年度(1人)、令和7年度(4人)、平成22年度(1人)です", t)

    def test_a_prefecture_not_in_the_list_is_told_it_is_not_listed_never_that_nothing_happened(self):
        html = build.fatal_answer(D, pref("鳥取県", {"H22": 1}))
        t = text(html)
        self.assertIn("鳥取県の死亡事故は載っていません", t)
        self.assertIn("2025年11月20日時点", t)
        self.assertIn("平成20年度以降に死亡者が出た年度は、平成22年度(1人)です", t)
        for claim in ("なかった", "ありません。直近", "安全", "起きていません"):
            self.assertNotIn(claim, t)
        self.assertIn("直近の事故は、鳥取県・警察・市町村の発表で確認してください", t)

    def test_a_prefecture_with_no_death_year_says_there_is_no_record_in_the_statistics_with_its_date(self):
        t = text(build.fatal_answer(D, pref("千葉県", {})))
        self.assertIn("千葉県の死亡事故は載っていません", t)
        self.assertIn("令和8年8月末まで)に、平成20年度以降の死亡者の記録はありません", t)

    def test_many_death_years_show_the_five_newest_and_count_the_rest(self):
        t = text(build.fatal_answer(D, pref("北海道", {y: 1 for y in D["inj"]["years"][:9]})))
        self.assertIn("ほか4年度", t)
        self.assertEqual(len(re.findall(r"\(1人\)", t.split("死亡者が出た年度は、")[1].split("です")[0])), 5)


if __name__ == "__main__":
    unittest.main()
