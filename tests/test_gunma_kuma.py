"""群馬県: the municipality is read from the place text; rows are stored as counts and as place-level records."""
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sokuhou import run
from sokuhou.sources import gunma_kuma as kuma
from sokuhou.sources import kumacounts, kumalib

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)


def features():
    return json.loads((FIX / "gunma_kuma.json").read_text(encoding="utf-8"))["features"]


def server(feats, asked=None):
    def fake(url):
        if asked is not None:
            asked.append(url)
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert q["returnGeometry"] == "false" and q["f"] == "json", q
        assert q["outFields"] == "field_18,field_11,field_8,field10", q          # no coordinates, no free-text columns beyond the note
        off, n = int(q["resultOffset"]), int(q["resultRecordCount"])
        return json.dumps({"features": feats[off:off + n], **({"exceededTransferLimit": True} if off + n < len(feats) else {})}).encode()
    return fake


def collect(feats=None, **patch):
    with mock.patch.object(kuma, "fetch", server(feats if feats is not None else features(), patch.pop("asked", None))), \
            mock.patch.object(kuma, "MIN_ROWS", patch.pop("min_rows", 1)), mock.patch.object(kumacounts, "PAUSE", 0):
        return kuma.collect(NOW)


class CityTest(unittest.TestCase):
    def test_the_municipality_is_the_start_of_the_place_text(self):
        for place, want in (("藤岡市坂原北久地域", "藤岡市"), ("中之条町大字西中之条字柴本　仁八橋付近", "中之条町"), ("吾妻郡嬬恋村大笹", "嬬恋村"),
                            ("みなかみ町藤原", "みなかみ町"), ("松井田町八城字稲荷地内", "安中市"), ("利根町老神地内　老神湯之上集会所の北方150ｍ付近", "沼田市"),
                            ("前橋市富士見町赤城山３　トレッカーズカフェ付近", "前橋市"), ("東吾妻町大字原町", "東吾妻町")):
            self.assertEqual(kuma.city_of(place), want, place)

    def test_a_place_without_a_municipality_goes_to_the_unknown_group(self):
        for place in ("県道中之条湯河原線　湯坂付近", "大字川井地内（川井集会所付近）", "二ッ岳（雄岳）登山道", ""):
            self.assertEqual(kuma.city_of(place), kuma.UNKNOWN, place)

    def test_a_longer_name_wins_over_its_prefix(self):
        self.assertEqual(kuma.city_of("東吾妻町川戸"), "東吾妻町")          # not 吾妻... ; 高山村 / 高崎市 do not capture each other either
        self.assertEqual(kuma.city_of("高崎市倉渕町"), "高崎市")
        self.assertEqual(kuma.city_of("高山村中山"), "高山村")


class CollectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = collect()

    def test_the_counts_are_the_number_of_rows_in_the_window(self):
        feats = features()
        days = [kumacounts.jst_date(f["attributes"]["field_18"]) for f in feats]
        want = sum(1 for d in days if d and d.year == 2026)
        self.assertEqual(sum(sum(m["monthly"].get("R08", {}).values()) + sum(m["monthly"].get("R07", {}).values()) for m in self.out["municipalities"].values()), want)
        self.assertEqual(self.out["mode"], "counts")

    def test_the_records_carry_date_municipality_place_kind_and_count_and_nothing_else(self):
        recs = self.out["corroborated"]
        self.assertTrue(recs)
        self.assertEqual({k for r in recs for k in r}, {"observed_at", "city", "place", "kind", "count"})
        self.assertEqual([r["observed_at"] for r in recs], sorted((r["observed_at"] for r in recs), reverse=True))
        self.assertTrue(all(r["observed_at"] >= "2026-04-01" for r in recs))             # this fiscal year only
        self.assertTrue(all(r["city"] in self.out["municipalities"] for r in recs))
        run.check_counts_bear(None, self.out)

    def test_a_trace_and_a_capture_are_not_called_sightings(self):
        a = {"attributes": {"field_18": int(datetime(2026, 10, 1, 9, tzinfo=kumalib.JST).timestamp() * 1000), "field_11": "安中市松井田町", "field_8": 1,
                            "field10": "クマの痕跡情報(柿の木の枝が折られた)"}}
        b = {"attributes": {"field_18": int(datetime(2026, 10, 2, 9, tzinfo=kumalib.JST).timestamp() * 1000), "field_11": "藤岡市坂原", "field_8": 2,
                            "field10": "くくり罠にかかり捕獲された"}}
        c = {"attributes": {"field_18": int(datetime(2026, 10, 3, 9, tzinfo=kumalib.JST).timestamp() * 1000), "field_11": "沼田市利根町", "field_8": None, "field10": ""}}
        got = {r["city"]: (r["kind"], r["count"]) for r in collect([a, b, c])["corroborated"]}
        self.assertEqual(got, {"安中市": ("痕跡", 1), "藤岡市": ("捕獲", 2), "沼田市": ("目撃", None)})

    def test_rows_are_paged_and_a_lost_column_is_an_error(self):
        asked = []
        with mock.patch.object(kuma, "PAGE_SIZE", 20):
            out = collect(asked=asked)
        self.assertGreater(len(asked), 1)
        self.assertEqual(out["municipalities"], self.out["municipalities"])
        with self.assertRaises(kuma.GunmaKumaSourceError):
            collect([{"attributes": {"field_18": 1}}])

    def test_it_is_registered_with_the_carry_over(self):
        from sokuhou.sources import corroborated
        by_name = {s.name: s for s in run.GROUPS["kuma"]}
        self.assertIs(by_name["gunma_kuma"].merge, corroborated.carry_over)


if __name__ == "__main__":
    unittest.main()
