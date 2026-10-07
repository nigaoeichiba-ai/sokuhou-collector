import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou import run
from sokuhou.sources import sorachi_kuma as kuma

PAGE = Path(__file__).parent / "fixtures" / "sorachi_kuma.html"


def _page() -> bytes:
    return PAGE.read_bytes()


class SorachiKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = kuma.parse_page(_page())

    def test_every_table_row_becomes_one_record(self):
        html = _page().decode("utf-8")
        tables = len(re.findall(r"<table", html))
        rows = len(re.findall(r"<tr", html)) - tables  # one header row per table (counted without using the parser)
        self.assertEqual(rows, 145)
        self.assertEqual(self.d["sightings_in_window"], 145)
        self.assertEqual(self.d["unparsed"], 0)

    def test_as_of_year_and_monthly_counts(self):
        self.assertEqual(self.d["as_of"], "2026-10-06")  # "令和8年10月6日 15時30分時点" on the page
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertEqual(self.d["monthly"]["R08"], {"4": 8, "5": 23, "6": 25, "7": 26, "8": 36, "9": 22, "10": 3})
        self.assertEqual(self.d["monthly"]["R07"], {"3": 2})  # January-March belong to the previous fiscal year
        self.assertEqual(sum(self.d["monthly"]["R08"].values()) + 2, 145)

    def test_rows_carry_the_municipality_of_their_table(self):
        s = self.d["sightings"]
        self.assertEqual(s[0], {"observed_at": "2026-10-04", "city": "赤平市", "place": "字赤平", "count": None, "kind": "痕跡", "species": "ヒグマ"})
        yubari = [x for x in s if x["city"] == "夕張市"]
        self.assertEqual(len(yubari), 13)
        self.assertIn({"observed_at": "2026-07-28", "city": "夕張市", "place": "富野", "count": 2, "kind": "目撃", "species": "ヒグマ"}, yubari)  # 親子グマ２頭
        self.assertIn({"observed_at": "2026-07-18", "city": "夕張市", "place": "南清水沢", "count": None, "kind": "痕跡", "species": "ヒグマ"}, yubari)  # 足跡
        self.assertEqual({x["city"] for x in s} - {"夕張市", "岩見沢市", "美唄市", "芦別市", "赤平市", "三笠市", "滝川市", "砂川市", "歌志内市", "深川市", "南幌町", "奈井江町",
                                                 "上砂川町", "由仁町", "長沼町", "栗山町", "月形町", "浦臼町", "新十津川町", "妹背牛町", "秩父別町", "雨竜町", "北竜町", "沼田町"}, set())

    def test_kinds(self):
        self.assertEqual(kuma._kind("ヒグマ１頭", ""), "目撃")
        self.assertEqual(kuma._kind("", "足跡"), "痕跡")
        self.assertEqual(kuma._kind("", "糞"), "痕跡")
        self.assertEqual(kuma._kind("クマ様", ""), "目撃(クマらしき)")
        self.assertEqual(kuma._kind("ヒグマ", ""), "目撃")  # no number is not a trace
        self.assertEqual(kuma._kind("ヒグマ２頭", "足跡も確認"), "目撃")  # a counted bear is a sighting

    def test_credit_and_note_say_what_the_data_is_and_is_not(self):
        self.assertIn("CC-BY", self.d["credit"])
        self.assertIn("加工して作成", self.d["credit"])
        self.assertIn("座標は公表されていません", self.d["update_note"])
        self.assertFalse(any("lat" in x for x in self.d["sightings"]))

    def test_a_page_without_its_time_stamp_or_with_few_rows_is_refused(self):
        with self.assertRaises(kuma.SorachiKumaError):
            kuma.parse_page(_page().replace("時点".encode(), "".encode()))
        with self.assertRaises(kuma.SorachiKumaError):
            kuma.parse_page(b"<html><body>" + "令和８年10月６日15時30分時点".encode() + b"</body></html>")

    def test_a_date_after_the_page_time_or_an_impossible_date_is_counted_as_unparsed_and_too_many_refuse(self):
        html = _page().decode("utf-8")
        one = html.replace(">10/4<", ">2/31<", 1).encode()
        self.assertEqual(kuma.parse_page(one)["unparsed"], 1)
        wrecked = re.sub(r">(\d{1,2})/(\d{1,2})<", ">13/40<", html).encode()
        with self.assertRaises(kuma.SorachiKumaError):
            kuma.parse_page(wrecked)

    def test_collect_without_network_and_registration(self):
        with mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=_page())):
            out = kuma.collect()
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertIn("sorachi_kuma", {s.name for s in run.GROUPS["kuma"]})


if __name__ == "__main__":
    unittest.main()
