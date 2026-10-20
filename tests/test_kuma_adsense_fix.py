"""kuma-sokuho.com, AdSense review fixes (2026-10-20): /about/, pages kept out of the index, the prefecture without bears, the municipality pages' own content.

Each rule has a negative case: the check must fail when the thing it guards is broken (a thin page indexed, an automation word, a zero table).
"""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import about, build, indexing
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data

TODAY = date(2026, 10, 7)


def _rows(city, n_rows, kind="目撃"):
    return [{"observed_at": f"2026-09-{1 + i % 28:02d}T09:00:00+09:00", "city": city, "place": f"場所{i}", "count": 1, "kind": kind if i % 4 else "痕跡",
             "species": "クマ", "lat": 34.2, "lon": 131.6} for i in range(n_rows)]


def _yamaguchi(city_rows: dict):
    rows = [r for city, k in city_rows.items() for r in _rows(city, k)]
    return {"source": "yamaguchi", "source_page": "https://yamaguchi-opendata.jp/x", "as_of": "2026-10-06", "fy_current": "R08",
            "credit": "出典:山口県警察のオープンデータ(CC BY)を加工して作成", "update_note": "県警が更新します",
            "fetched_at": "2026-10-07T06:20:00+09:00", "sightings": rows, "monthly": {"R08": {"9": len(rows)}}}


class IndexingRulesTest(unittest.TestCase):
    def test_a_municipality_page_is_thin_below_the_index_floor_and_below_the_no_demand_floor_unless_google_showed_it(self):
        few, some, many = [0] * 4, [0] * 8, [0] * indexing.NO_DEMAND_CITY_ROWS
        shown = {"live_cities": [indexing.city_hash("akita", "鹿角市")], "digest_weeks": []}
        with mock.patch.object(indexing, "_DEMAND", {"live_cities": [], "digest_weeks": []}):
            self.assertTrue(indexing.city_is_thin("akita", "鹿角市", few))
            self.assertTrue(indexing.city_is_thin("akita", "鹿角市", some))
            self.assertFalse(indexing.city_is_thin("akita", "鹿角市", many))
        with mock.patch.object(indexing, "_DEMAND", shown):
            self.assertFalse(indexing.city_is_thin("akita", "鹿角市", some))           # shown in a search: stays indexed
            self.assertTrue(indexing.city_is_thin("akita", "鹿角市", few))             # still too thin even if shown (the older rule)
            self.assertTrue(indexing.city_is_thin("akita", "大館市", some))            # another municipality: not shown

    def test_old_week_pages_are_noindex_except_the_newest_and_those_google_showed(self):
        weeks = [f"2026-W{w:02d}" for w in range(41, 13, -1)]                        # 28 weeks, newest first
        with mock.patch.object(indexing, "_DEMAND", {"live_cities": [], "digest_weeks": ["2026-W20", "2026-W34"]}):
            thin = indexing.thin_weeks(weeks)
        keep = [k for k in weeks if k not in thin]
        self.assertEqual(set(keep), {"2026-W41", "2026-W40", "2026-W20", "2026-W34"})
        self.assertEqual(len(thin), 24)

    def test_the_demand_file_has_the_keys_the_build_reads(self):
        self.assertTrue(indexing._DEMAND["live_cities"])
        for h in indexing._DEMAND["live_cities"]:
            self.assertRegex(h, r"^[0-9a-f]{6}$")
        for k in indexing._DEMAND["digest_weeks"]:
            self.assertRegex(k, r"^\d{4}-W\d{2}$")


class CityPageHelpersTest(unittest.TestCase):
    def test_short_place_drops_the_prefecture_county_and_municipality_in_front(self):
        self.assertEqual(live_mod.short_place("五城目町", "秋田県南秋田郡五城目町七倉"), "七倉")
        self.assertEqual(live_mod.short_place("岩国市", "岩国市錦町広瀬"), "錦町広瀬")
        self.assertEqual(live_mod.short_place("富谷市", "富谷市一ノ関臑合山　地内"), "一ノ関臑合山")
        self.assertEqual(live_mod.short_place("三種町", "秋田県三種町"), "")                # the municipality alone says nothing about where

    def test_places_html_lists_only_places_that_repeat_and_the_newest(self):
        rows = [{"place": p} for p in ("岩国市A", "岩国市B", "岩国市A", "岩国市C", "岩国市A", "岩国市B", "岩国市D")]
        html = live_mod.places_html("岩国市", rows)
        self.assertIn("<li>A: 3件</li><li>B: 2件</li>", html)
        self.assertNotIn("C: ", html)
        self.assertIn("<li>A</li><li>B</li><li>C</li><li>D</li></ul>", html)             # the newest (up to five) distinct places, newest first
        self.assertEqual(live_mod.places_html("岩国市", [{"place": "岩国市A"}, {"place": "岩国市B"}]).count("同じ場所"), 0)

    def test_peak_week_is_reported_only_when_it_is_the_single_busiest_week_with_three_or_more(self):
        day = lambda d: {"at": f"2026-09-{d:02d}T09:00:00+09:00"}      # noqa: E731
        got = live_mod.peak_week([day(d) for d in (1, 2, 3, 20)])
        self.assertEqual((got[0], got[1], got[2]), (date(2026, 9, 1), date(2026, 9, 7), 3))
        self.assertIsNone(live_mod.peak_week([day(d) for d in (1, 2, 20, 21)]))          # fewer than 3
        self.assertIsNone(live_mod.peak_week([day(d) for d in (1, 2, 3, 20, 21, 22)]))    # two weeks tie: no sentence rather than a guess


class CityFactsTest(unittest.TestCase):
    """The municipality pages carry only the sentences that are true of that municipality, so two pages differ in structure and in the names they mention."""
    TODAY = date(2026, 10, 20)

    @staticmethod
    def rows(days, kind="目撃"):
        return [{"at": f"{d}T09:00:00+09:00", "kind": kind, "place": f"{d}の場所", "city": "X"} for d in sorted(days, reverse=True)]

    def lv(self, **cities):
        return {"by_pref": {"akita": {c: r for c, r in cities.items()}}, "today": self.TODAY}

    def facts(self, city, **cities):
        return live_mod.city_facts("akita", city, cities[city], self.lv(**cities), self.TODAY)

    def test_the_biggest_municipality_names_the_second_and_a_small_one_names_the_first(self):
        big = self.rows([f"2026-09-{d:02d}" for d in range(1, 21)])
        mid = self.rows([f"2026-08-{d:02d}" for d in range(1, 11)])
        small = self.rows(["2026-07-01", "2026-07-02", "2026-07-03"])
        tiny = self.rows(["2026-06-01", "2026-06-02"])
        cities = {"大館市": big, "能代市": mid, "男鹿市": small, "三種町": tiny}
        first = "".join(self.facts("大館市", **cities)["lead"])
        self.assertIn("いちばん記録の多い市町村です(2位は能代市の10件)", first)
        last = "".join(self.facts("三種町", **cities)["lead"])
        self.assertIn("記録の数は4位と、少ない側です。1位の大館市は20件です", last)
        self.assertNotIn("いちばん記録の多い", last)

    def test_a_municipality_without_recent_records_says_so_instead_of_comparing_two_zeros(self):
        rows = self.rows(["2026-05-01", "2026-05-02", "2026-05-03"])
        lead = "".join(self.facts("大館市", **{"大館市": rows})["lead"])
        self.assertIn("直近60日(その前の30日を含む)には、記録がありません", lead)
        self.assertNotIn("より増えています", lead)

    def test_the_busiest_week_is_in_the_lead_only_when_it_holds_a_large_share(self):
        spread = self.rows([f"2026-0{m}-0{d}" for m in (5, 6, 7, 8) for d in (1, 2, 3)])
        lead = "".join(self.facts("大館市", **{"大館市": spread})["lead"])
        self.assertNotIn("に集まっています", lead)                                   # 3 of 12 in the best week: a quarter, not a concentration
        packed = self.rows(["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-09-01", "2026-09-20"])
        lead = "".join(self.facts("大館市", **{"大館市": packed})["lead"])
        self.assertIn("記録の67%(4件)は、7月1日から7月7日の7日間に集まっています", lead)

    def test_kinds_a_late_first_record_and_a_long_gap_are_stated_only_when_they_apply(self):
        rows = self.rows(["2026-05-10", "2026-06-01", "2026-08-30"])
        items = "".join(self.facts("大館市", **{"大館市": rows})["items"])
        self.assertIn("記録は、すべて「目撃」です", items)
        self.assertIn("年度の最初の記録は5月10日で、4月ではありません", items)
        self.assertIn("記録のない日が最も長く続いたのは、6月2日から8月29日の89日間です", items)
        early = self.rows(["2026-04-02", "2026-04-05", "2026-04-09"], kind="痕跡")
        items = "".join(self.facts("大館市", **{"大館市": early})["items"])
        self.assertNotIn("4月ではありません", items)
        self.assertNotIn("最も長く続いた", items)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class AdsenseFixSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.no_demand = mock.patch.object(indexing, "_DEMAND", {"live_cities": [], "digest_weeks": []})     # the real list names these real municipalities: start from none shown
        cls.no_demand.start()
        cls.cities = {"岩国市": 30, "周南市": 9, "萩市": 6, "下松市": 4}               # indexed by rows / thin and not shown / thin and not shown / below the old floor
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs={"yamaguchi": _yamaguchi(cls.cities)}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.no_demand.stop()
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def city_rel(self, city):
        return f"live/yamaguchi/{live_mod.city_slug('yamaguchi', city)}/index.html"

    @staticmethod
    def main_text(html):
        body = html.split("<main", 1)[1].split("</main>", 1)[0]
        return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", body))

    # ---- /about/
    def test_about_has_the_editorial_sections_and_enough_text(self):
        html = self.read("about/index.html")
        for h in ("編集方針", "数字が載るまでの方法", "この数字で言えないこと", "誤りを見つけたら", "更新の履歴"):
            self.assertIn(f"<h2>{h}</h2>", html)
        self.assertGreaterEqual(len(self.main_text(html)), 1200)
        for step in ("出典", "取得", "計算", "検査", "公開"):
            self.assertIn(f"<strong>{step}</strong>", html)
        self.assertIn("クマが多いかどうかを表しません", html)

    def test_no_page_says_it_was_made_by_ai_or_automatically(self):
        for rel in self.files:
            if rel.endswith(".html"):
                text = self.read(rel)
                for word in ("AI支援", "自動作成", "自動で作成", "自動で作っ", "自動で作り", "自動生成"):
                    self.assertNotIn(word, text, f"{rel}: {word}")
                self.assertNotRegex(re.sub(r"クマAIカメラ", "", text).replace("adsbygoogle", ""), r"(?<![A-Za-z])AI(?![A-Za-z])", rel)   # "クマAIカメラ" is Toyama's own label for a kind of record

    def test_the_company_name_is_not_in_the_editorial_text(self):
        self.assertNotIn("株式会社", about.editorial_html())
        self.assertNotIn("MACS", about.editorial_html())

    def test_the_update_history_is_newest_first_and_dated(self):
        days = [d for d, _ in about.UPDATES]
        self.assertEqual(days, sorted(days, reverse=True))
        self.assertRegex(self.read("about/index.html"), r"2026年10月20日: 運営者情報に")

    # ---- the sentence that said the page only lines up the municipality's records
    def test_no_page_says_the_records_are_lined_up_as_published(self):
        for rel in self.files:
            if rel.endswith(".html"):
                self.assertNotIn("そのまま並べています", self.read(rel), rel)

    # ---- municipality pages
    def test_a_municipality_page_leads_with_what_it_counts_and_computes_more_than_the_list(self):
        rel = self.city_rel("岩国市")
        html = self.read(rel)
        lead = re.search(r'<p class="lead">(.*?)</p>', html).group(1)
        for part in ("令和8年度の記録は30件です", "直近30日は", "その前の30日(", "いちばん記録の多い市町村です(2位は周南市の9件)"):
            self.assertIn(part, lead)
        text = re.sub(r"<[^>]+>", " ", html)
        for part in ("記録のあった日は", "数え方と、読むときの注意", "件数の数え方は、「"):
            self.assertIn(part, text)
        records = html.split("新しい順の記録(直近20件)</h2>", 1)[1].split("</table>", 1)[0]
        self.assertEqual(records.count("<tr>") - 1, live_mod.CITY_ROWS)               # the record table stops at CITY_ROWS rows (30 records here)

    def test_a_municipality_page_has_at_least_400_characters_of_text_outside_tables_and_headings(self):
        for city in ("岩国市", "周南市", "萩市"):
            html = self.read(self.city_rel(city)).split("<main", 1)[1].split("</main>", 1)[0]
            html = re.sub(r"<(table|nav|h1|h2|h3|svg)\b.*?</\1>", "", html, flags=re.S)
            self.assertGreaterEqual(len(re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html))), 400, city)

    def test_thin_municipality_pages_are_noindex_and_out_of_the_sitemap_and_the_others_are_in_it(self):
        sitemap = self.read("sitemap.xml")
        for city, thin in (("岩国市", False), ("周南市", True), ("萩市", True), ("下松市", True)):
            html = self.read(self.city_rel(city))
            url = live_mod.city_url("yamaguchi", city)
            noindex = '<meta name="robots" content="noindex,follow">' in html
            self.assertEqual(noindex, thin, city)
            self.assertEqual(url in sitemap, not thin, city)

    def test_a_municipality_page_that_google_showed_stays_indexed_while_thin(self):
        shown = {"live_cities": [indexing.city_hash("yamaguchi", "周南市")], "digest_weeks": []}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(indexing, "_DEMAND", shown):
            build.render_site(self.raw, CFG, Path(tmp) / "s", release=True, prefs={"yamaguchi": _yamaguchi(self.cities)}, today=TODAY)
            self.assertNotIn("noindex", (Path(tmp) / "s" / self.city_rel("周南市")).read_text(encoding="utf-8"))
            self.assertIn(live_mod.city_url("yamaguchi", "周南市"), (Path(tmp) / "s" / "sitemap.xml").read_text(encoding="utf-8"))

    # ---- the prefecture without bears
    def test_chiba_is_a_short_noindex_page_without_a_table_of_zeros(self):
        html = self.read("chiba/index.html")
        self.assertIn('<meta name="robots" content="noindex,follow">', html)
        self.assertNotIn("/chiba/", self.read("sitemap.xml"))
        self.assertNotIn("<table", html)
        self.assertIn("千葉県にクマはいる?", html)
        self.assertIn("生息していないとされています", html)
        for name in ("茨城県", "埼玉県", "東京都"):
            self.assertIn(name, html)
        self.assertIn('href="/ibaraki/"', html)

    def test_chiba_gets_the_full_page_again_if_the_ministry_ever_lists_an_injury_there(self):
        raw = raw_data()
        raw["notices"] = []
        raw["injuries"]["prefectures"] = [dict(p, by_year={**p["by_year"], raw["injuries"]["years"][-1]: [1, 1, 0]}) if p["name"] == "千葉" else p
                                          for p in raw["injuries"]["prefectures"]]
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(raw, CFG, Path(tmp) / "s", release=True)
            html = (Path(tmp) / "s" / "chiba" / "index.html").read_text(encoding="utf-8")
            self.assertIn("<table", html)
            self.assertNotIn("noindex", html)

    def test_other_prefectures_are_unaffected(self):
        self.assertNotIn("noindex", self.read("akita/index.html"))
        self.assertIn("/akita/", self.read("sitemap.xml"))
        self.assertIn("<table", self.read("hokkaido/index.html"))                      # no ministry row either, but it has data: not the short page

    def test_the_site_check_passes_with_the_noindex_pages_in_place(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])


if __name__ == "__main__":
    unittest.main()
