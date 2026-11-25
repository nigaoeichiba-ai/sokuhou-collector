"""This year's order on the sightings ranking, and the death list set beside the injury statistics (competitor review 2026-11-25).
The numbers are recounted here from the ministry fixtures, not taken from the builder."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, rankfacts
from tests.test_kuma_build import CFG, HAVE_PYPDF, LINKS, raw_data


def text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class RankingNowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, CFG, cls.out, release=True, links=LINKS)
        cls.d = build.prepare(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_this_years_table_is_the_ten_largest_of_the_published_months(self):
        s = self.raw["sightings"]
        cur, li = self.d["cur"], self.d["li"]
        want = sorted(((sum(v or 0 for v in p["monthly"][cur][: li + 1]), p["name"]) for p in s["prefectures"]
                       if any(v is not None for v in p["monthly"][cur][: li + 1])), key=lambda t: (-t[0], t[1]))[:10]
        html = self.read("ranking/sightings/index.html")
        part = html.split("で多い県</h2>")[1].split("</table>")[0]
        got = [(int(c[2].rstrip("件").replace(",", "")), c[1]) for c in
               ([text(td).strip() for td in re.findall(r"<td>(.*?)</td>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", part)) if c]
        self.assertEqual([g[0] for g in got], [w[0] for w in want])
        self.assertTrue(got[0][1].startswith(want[0][1]))
        self.assertIn(f"最も多いのは{got[0][1]}({want[0][0]:,}件)", text(html))
        self.assertIn("この順位は生息数の順ではありません", html)

    def test_equal_numbers_are_called_equal_and_a_gap_is_counted_by_prefecture(self):
        cur = self.d["cur"]
        listed = {}
        for i in self.raw["fatal"][cur]["incidents"]:
            listed[i["prefecture"]] = listed.get(i["prefecture"], 0) + i["victims"]
        total = sum(listed.values())
        as_of = self.raw["fatal"][cur]["as_of"]
        d = {**self.d, "inj": {**self.d["inj"], "national": {**self.d["inj"]["national"], cur: [0, 0, total]}}}
        self.assertIn("一覧の人数と同じです", rankfacts.later_deaths(d, listed, as_of))
        rows = [dict(r) for r in self.d["rows"]]
        for r in rows:
            r["inj"] = {**r["inj"], cur: [0, 0, listed.get(r["name"], 0) + (2 if r["name"] == "長野県" else 0)]}
        d = {**d, "rows": rows, "inj": {**d["inj"], "national": {**d["inj"]["national"], cur: [0, 0, total + 2]}}}
        out = text(rankfacts.later_deaths(d, listed, as_of))
        self.assertIn("一覧より2人多い数です", out)
        self.assertIn("長野県(2人)", out)
        self.assertNotIn("同じです", out)
        d["inj"]["national"][cur] = [0, 0, total - 1]
        low = rankfacts.later_deaths(d, listed, as_of)
        self.assertIn("一覧の人数とは一致していません", low)
        self.assertNotIn("多いのは", low)

    def test_the_death_pages_carry_the_comparison_and_the_title_names_both_years(self):
        html = self.read("deaths/index.html")
        self.assertIn("死亡者数を人身被害の統計と比べる", html)
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        count = sum(len(self.raw["fatal"][y]["incidents"]) for y in (self.d["done"], self.d["cur"]))
        for word in ("死亡事故一覧", "2025", "2026", f"{count}件"):
            self.assertIn(word, title)

    def test_a_prefecture_left_out_of_the_death_ranking_but_hit_this_year_is_named(self):
        cur = self.d["cur"]
        done = [y for y in self.d["inj"]["years"] if y != cur]
        zero = [r["name"] for r in self.d["rows"] if sum(r["inj"][y][2] for y in done) == 0]
        hit = [r["name"] for r in self.d["rows"] if r["name"] in zero and r["inj"][cur][2] > 0]
        self.assertEqual(bool(hit), "(途中)に死亡者の記録があります" in self.read("ranking/deaths/index.html"))
        rows = [{"name": "A県", "inj": {cur: [1, 1, 1]}}, {"name": "B県", "inj": {cur: [0, 0, 0]}}]
        self.assertIn("このうちA県は", rankfacts.only_this_year({"cur": cur, "rows": rows}, ["A県", "B県"]))
        self.assertEqual(rankfacts.only_this_year({"cur": cur, "rows": rows}, ["B県"]), "")


if __name__ == "__main__":
    unittest.main()
