import csv
import io
import json
import unittest
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from sokuhou import run
from sokuhou.sources import kumacounts, kumalib
from sokuhou.sources import yamagata_kuma as kuma

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)
FORBIDDEN_KEYS = {"lat", "lon", "latitude", "longitude", "place", "places", "sightings", "address", "mail", "email", "remarks", "note"}


def _csv() -> bytes:
    return (FIX / "yamagata_kuma.csv").read_bytes()


def _naive_expected(data: bytes):
    """Counted another way: plain csv + string splitting, no regex and no date type."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))[1:]
    monthly, by_city, latest, total = Counter(), {}, {}, 0
    for city, day in rows:
        y, m, d = (int(p) for p in day.split("/"))
        if y < 2026:
            continue
        fy = "R%02d" % ((y if m >= 4 else y - 1) - 2018)
        monthly[(fy, str(m))] += 1
        by_city.setdefault(city, Counter())[(fy, str(m))] += 1
        iso = "%04d-%02d-%02d" % (y, m, d)
        latest[city] = max(latest.get(city, ""), iso)
        total += 1
    return monthly, by_city, latest, total


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    return found


def _parse(data=None, **patch):
    with mock.patch.object(kuma, "MIN_ROWS", patch.pop("min_rows", 1)):
        return kuma.parse(data if data is not None else _csv(), "https://example.invalid/20261004_kemonote-cleaned.csv", TODAY)


class YamagataKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _parse()

    def test_counts_equal_a_naive_recount_of_the_fixture(self):
        monthly, by_city, latest, total = _naive_expected(_csv())
        self.assertEqual(total, 200)
        got = {(fy, m): n for fy, ms in self.out["monthly"].items() for m, n in ms.items()}
        self.assertEqual(got, dict(monthly))
        self.assertEqual(self.out["total_fy"], sum(n for (fy, _), n in monthly.items() if fy == "R08"))
        self.assertEqual(set(self.out["municipalities"]), set(by_city))
        for city, m in self.out["municipalities"].items():
            self.assertEqual({(fy, mo): n for fy, ms in m["monthly"].items() for mo, n in ms.items()}, dict(by_city[city]), city)
            self.assertEqual(m["latest"], latest[city], city)
        self.assertEqual(self.out["as_of"], max(latest.values()))
        self.assertEqual(self.out["fy_current"], "R08")
        self.assertEqual(self.out["unparsed"], 0)

    def test_the_stored_data_has_no_place_position_or_free_text(self):
        extra = ("ユーザ名,緯度,経度,目撃した日付,地名等,備考\n"
                 "山形市,38.208996,140.310162,2026/9/1,SECRET_PLACE_山形市大字片谷地,SECRET_REMARK_090-0000-0000\n"
                 "鶴岡市,38.5,139.8,2026/9/2,SECRET_PLACE_2,a@example.com\n").encode("utf-8-sig")
        out = _parse(extra)
        self.assertEqual(out["total_fy"], 2)
        text = json.dumps(out, ensure_ascii=False)
        for secret in ("SECRET", "38.2089", "140.31", "example.com", "090-"):
            self.assertNotIn(secret, text)
        self.assertFalse(_keys(out) & FORBIDDEN_KEYS)
        self.assertEqual({k for m in out["municipalities"].values() for k in m}, {"monthly", "latest"})
        run.check_counts_bear(None, self.out)   # the same guard the collector applies before storing

    def test_the_county_prefix_and_spaces_are_normalised(self):
        text = _csv().decode("utf-8-sig").replace("\n大蔵村,", "\n最上郡大蔵村,").replace("\n鮭川村,", "\n鮭川村 ,")
        self.assertIn("最上郡大蔵村", text)
        out = _parse(text.encode("utf-8-sig"))
        self.assertEqual(out["municipalities"], self.out["municipalities"])

    def test_unreadable_and_future_dates_are_excluded_and_counted(self):
        text = _csv().decode("utf-8-sig") + "山形市,2026/2/31\n山形市,不明\n山形市,2026/10/20\n山形市,2026/10/9\n"
        out = _parse(text.encode("utf-8-sig"))
        self.assertEqual(out["unparsed"], 3)             # Feb 31, "不明", Oct 20 (after today + 2 days); Oct 9 is allowed
        self.assertEqual(out["total_fy"], self.out["total_fy"] + 1)
        self.assertEqual(out["as_of"], "2026-10-09")

    def test_too_many_bad_dates_or_blank_municipalities_refuse_the_file(self):
        base = _csv().decode("utf-8-sig")
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse((base + "山形市,不明\n" * 10).encode("utf-8-sig"))      # 10/210 > 2%
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse((base + ",2026/9/1\n" * 15).encode("utf-8-sig"))        # 15/215 > 3%
        _parse((base + "山形市,不明\n" * 3).encode("utf-8-sig"))           # 3/203 is tolerated

    def test_a_changed_format_or_too_few_rows_is_refused(self):
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse(_csv().replace("目撃した日付".encode(), "目撃日".encode()))
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse(b"")
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse(_csv(), min_rows=500)
        with self.assertRaises(kuma.YamagataKumaSourceError):
            _parse("﻿他の,列\n1,2\n".encode("utf-8"))
        with self.assertRaises(kuma.YamagataKumaSourceError):
            kuma.read_rows(b"\xff\xfe\x00bad")

    def test_the_newest_dated_link_of_the_page_is_used(self):
        html = (FIX / "yamagata_kuma_page.html").read_text(encoding="utf-8")
        self.assertEqual(kuma.csv_url_from_page(html), "https://www.pref.yamagata.jp/documents/2414/20261004_kemonote-cleaned.csv")
        with self.assertRaises(kuma.YamagataKumaSourceError):
            kuma.csv_url_from_page("<p>no link</p>")
        with self.assertRaises(kuma.YamagataKumaSourceError):
            kuma.csv_url_from_page('<a href="https://evil.example/20261004_kemonote-cleaned.csv">x</a>')

    def test_collect_reads_the_page_then_the_csv_without_network(self):
        asked = []

        def fake(url):
            asked.append(url)
            if url == kuma.PAGE:
                return (FIX / "yamagata_kuma_page.html").read_bytes()
            self.assertEqual(url, "https://www.pref.yamagata.jp/documents/2414/20261004_kemonote-cleaned.csv")
            return _csv()

        with mock.patch.object(kuma, "fetch", fake), mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kumacounts, "PAUSE", 0):
            out = kuma.collect(NOW)
        self.assertEqual(len(asked), 2)
        self.assertEqual(out["mode"], "counts")
        self.assertEqual(out["source"], "yamagata")
        self.assertEqual(out["source_file"], asked[1])
        self.assertEqual(out["municipalities"], self.out["municipalities"])
        self.assertTrue(out["fetched_at"])
        self.assertIn("山形県", out["credit"])

    def test_the_pause_between_the_two_requests_is_at_least_a_second(self):
        self.assertGreaterEqual(kumacounts.PAUSE, 1.0)


if __name__ == "__main__":
    unittest.main()
