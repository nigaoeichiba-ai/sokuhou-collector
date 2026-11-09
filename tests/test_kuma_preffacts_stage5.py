"""kuma-sokuho.com prefecture pages, stage 5 (2026-11-09): facts that differ by prefecture -- the ministry's nut-crop survey, the spread of records over municipalities,
the districts where records repeat.  Negative cases: a prefecture the ministry's table does not list gets no claim; a prefecture covered in part is not described."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, preffacts
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data
from tests.test_kuma_preffacts import make


class MastTest(unittest.TestCase):
    def test_the_data_file_has_the_24_prefectures_of_the_ministrys_table_and_the_9_alerts(self):
        m = preffacts._MAST
        self.assertEqual(len(m["prefectures"]), m["surveyed"])
        self.assertEqual(set(m["alert"]), {"北海道", "栃木県", "群馬県", "滋賀県", "京都府", "兵庫県", "奈良県", "鳥取県", "山口県"})
        self.assertTrue(set(m["alert"]) <= set(m["prefectures"]))
        self.assertEqual(m["as_of"], "2026-10-29")
        self.assertTrue(m["pdf"].startswith("https://www.env.go.jp/"))
        for name, row in m["prefectures"].items():
            for k in ("buna", "mizunara", "konara"):
                self.assertTrue(row[k], (name, k))
            self.assertTrue(any(row[k] != m["missing_marker"] for k in ("buna", "mizunara", "konara")), name)       # a row with no rating at all would say nothing
            self.assertTrue(row["link"] == "" or row["link"].startswith("https://"), name)

    def test_the_ratings_are_the_tables_words(self):
        m = preffacts._MAST["prefectures"]
        self.assertEqual((m["福島県"]["buna"], m["福島県"]["mizunara"], m["福島県"]["konara"]), ("大豊作", "豊作", "豊作"))
        self.assertEqual((m["兵庫県"]["mizunara"], m["兵庫県"]["konara"]), ("大凶作", "大凶作"))
        self.assertEqual(m["山口県"]["konara"], "凶作")

    def test_the_sentence_gives_the_ratings_the_alert_and_what_was_not_surveyed(self):
        d, r = make()
        r["name"] = "山口県"
        s = preffacts._mast(d, r)[0]
        self.assertIn("山口県はコナラが「凶作」でした", s)
        self.assertIn("ブナ・ミズナラは調査がありません", s)
        self.assertIn("西中国山地として島根県がまとめた調査です", s)
        self.assertIn("注意喚起を行っている道府県に挙げています", s)
        self.assertIn("島根県の結果", s)                                  # Yamaguchi's own page is the Shimane one

    def test_a_prefecture_not_in_the_table_gets_no_sentence_and_no_claim_about_a_survey(self):
        d, r = make()
        r["name"] = "岩手県"
        self.assertEqual(preffacts._mast(d, r), [])

    def test_the_alert_sentence_is_only_for_the_nine(self):
        d, r = make()
        r["name"] = "福島県"
        self.assertNotIn("注意喚起", preffacts._mast(d, r)[0])

    def test_a_negative_case_a_missing_rating_is_never_printed_as_a_rating(self):
        d, r = make()
        r["name"] = "愛知県"
        s = preffacts._mast(d, r)[0]
        self.assertNotIn("ブナが", s)
        self.assertIn("ブナは調査がありません", s)


class ConcentrationTest(unittest.TestCase):
    @staticmethod
    def lv(counts: dict, slug="miyagi"):
        recs = {c: [{"slug": slug, "city": c, "place": f"{c}字{i}"} for i in range(k)] for c, k in counts.items()}
        return {"by_pref": {slug: recs}, "counts": [], "records": [x for v in recs.values() for x in v]}

    def test_the_top_three_and_their_share(self):
        d, r = make()
        r["slug"] = "miyagi"
        d["lv"] = self.lv({"甲市": 30, "乙町": 20, "丙村": 15, "丁市": 10, "戊町": 8, "己村": 7, "庚市": 5, "辛区": 5})
        s = preffacts._concentration(d, r)[0]
        self.assertIn("記録がある8市町村のうち", s)
        self.assertIn("甲市(30件)、乙町(20件)、丙村(15件)で、この3つで", s)

    def test_a_city_with_a_large_share_is_named_as_such(self):
        d, r = make()
        r["slug"] = "miyagi"
        d["lv"] = self.lv({"甲市": 90, "乙町": 20, "丙村": 15, "丁市": 10, "戊町": 8, "己村": 7})
        s = preffacts._concentration(d, r)[0]
        self.assertIn("甲市が90件で全体の", s)
        self.assertIn("2位は乙町(20件)", s)

    def test_rows_that_are_not_municipalities_are_left_out(self):
        d, r = make()
        r["slug"] = "gunma"
        d["lv"] = self.lv({"市町村が分からないもの": 266, "甲町": 62, "乙市": 36, "丙市": 30, "丁村": 20, "戊町": 15, "己村": 10, "大台ヶ原": 40}, slug="gunma")
        s = preffacts._concentration(d, r)[0]
        self.assertNotIn("分から", s)
        self.assertNotIn("大台ヶ原", s)
        self.assertIn("記録がある6市町村", s)

    def test_a_small_total_or_few_municipalities_say_nothing(self):
        d, r = make()
        r["slug"] = "miyagi"
        d["lv"] = self.lv({"甲市": 30, "乙町": 20, "丙村": 15, "丁市": 10, "戊町": 8, "己村": 8})        # 91 records: below 100
        self.assertEqual(preffacts._concentration(d, r), [])
        d["lv"] = self.lv({"甲市": 60, "乙町": 40, "丙村": 15, "丁市": 10, "戊町": 8})                   # five municipalities
        self.assertEqual(preffacts._concentration(d, r), [])

    def test_a_prefecture_covered_in_part_is_not_described(self):
        d, r = make()
        r["slug"] = "hokkaido"
        d["lv"] = self.lv({f"{c}市": 30 for c in "甲乙丙丁戊己"}, slug="hokkaido")
        d["lv"]["records"] = [dict(x, src="sorachi") for x in d["lv"]["records"]]      # a source that covers only part of the prefecture
        self.assertEqual(preffacts._concentration(d, r), [])

    def test_the_district_drops_street_numbers_and_the_chome(self):
        self.assertEqual(preffacts.district("富谷市", "富谷市大清水一丁目 付近"), "大清水")
        self.assertEqual(preffacts.district("富谷市", "富谷市明石杉ノ入　地内"), "明石杉ノ入")
        self.assertEqual(preffacts.district("横手市", "秋田県横手市大字増田町増田字上町123"), "増田町増田字上町")
        self.assertEqual(preffacts.district("甲市", "甲市1-2-3"), "")

    def test_districts_name_only_places_with_five_records_or_more(self):
        d, r = make()
        r["slug"] = "miyagi"
        lv = self.lv({f"{c}市": 30 for c in "甲乙丙丁"})
        for i, x in enumerate(lv["records"]):
            x["place"] = "甲市A町" if i < 8 else f"{x['city']}B{i}町"                 # eight in one district, the rest all different
        d["lv"] = lv
        s = preffacts._districts(d, r)[0]
        self.assertIn("甲市A町(8件)", s)
        self.assertEqual(s.count("件)"), 1)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class Stage5PagesTest(unittest.TestCase):
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
            if not build.has_no_bears(self.d, r):
                yield r, (self.out / r["slug"] / "index.html").read_text(encoding="utf-8")

    def test_the_survey_sentence_is_on_the_prefectures_of_the_table_and_on_no_other_page(self):
        names = set(preffacts._MAST["prefectures"])
        got = set()
        for r, html in self.pages():
            if "堅果類の結実調査(速報)" in html:
                got.add(r["name"])
                row = preffacts._MAST["prefectures"][r["name"]]
                for k, sp in (("buna", "ブナ"), ("mizunara", "ミズナラ"), ("konara", "コナラ")):
                    if row[k] != "－":
                        self.assertIn(f"{sp}が「{row[k]}」", html, r["name"])
        shown = {r["name"] for r, _ in self.pages()}
        self.assertEqual(got, names & shown)
        self.assertGreaterEqual(len(got), 20)

    def test_no_page_says_that_something_is_unconfirmed(self):
        for r, html in self.pages():
            body = re.sub(r"<[^>]+>", "", html.split("<main", 1)[1].split("</main>", 1)[0])
            self.assertNotIn("未確認", body, r["name"])


if __name__ == "__main__":
    unittest.main()
