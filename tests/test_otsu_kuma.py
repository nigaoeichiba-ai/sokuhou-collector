"""大津市のクマの目撃情報(件数だけを保存する)アダプタのテスト。ネットワークなし。

期待値は、固定ファイル(tests/fixtures/otsu_kuma_page.html: 市の「目撃情報一覧」の日付の見出し32件。場所と説明は、置き換えてある)から、
アダプタとは別の方法(正規表現ではなく、素朴な文字列の分割)で数えたものと、数えて書き写した値。
"""
import json
import unittest
from datetime import datetime
from pathlib import Path

from sokuhou import run
from sokuhou.sources import kumalib
from sokuhou.sources import otsu_kuma as kuma

HTML = (Path(__file__).parent / "fixtures" / "otsu_kuma_page.html").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST)


def naive_dates(html):
    """Another way: split at the heading, then read each <h3> by hand (full-width numbers are not used on this page)."""
    out = []
    for part in html.split("目撃情報一覧", 1)[1].split("<h3>")[1:]:
        title = part.split("</h3>")[0]
        if not title.startswith("令和"):
            continue
        y = int(title.split("令和")[1].split("年")[0])
        mo = int(title.split("年")[1].split("月")[0])
        d = int(title.split("月")[1].split("日")[0])
        out.append((2018 + y, mo, d))
    return out


class OtsuKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = kuma.parse(HTML, NOW)

    def test_the_fixture_has_32_dated_entries(self):
        self.assertEqual(len(naive_dates(HTML)), 32)

    def test_counts_equal_an_independent_count(self):
        mon = {}
        for y, m, d in naive_dates(HTML):
            mon[m] = mon.get(m, 0) + 1
        got = {int(m): n for m, n in self.out["monthly"]["R08"].items()}
        self.assertEqual(got, mon)
        self.assertEqual(self.out["total_fy"], 32)

    def test_the_numbers_copied_from_a_hand_count(self):
        out = self.out
        self.assertEqual(out["mode"], "counts")
        self.assertEqual(out["source"], "otsu")
        self.assertEqual(out["fy_current"], "R08")
        self.assertEqual(out["as_of"], "2026-10-03")
        self.assertEqual(out["monthly"]["R08"], {"4": 3, "5": 13, "6": 6, "7": 3, "8": 3, "9": 2, "10": 2})
        self.assertEqual(list(out["municipalities"]), ["大津市"])
        self.assertEqual(out["municipalities"]["大津市"]["latest"], "2026-10-03")
        self.assertEqual(out["unparsed"], 0)
        self.assertEqual(out["source_page"], kuma.PAGE)
        self.assertIn("大津市が作成したものではありません", out["credit"])

    def test_nothing_but_the_municipality_month_count_and_latest_date_is_stored(self):
        keys = set()

        def walk(x):
            if isinstance(x, dict):
                keys.update(x)
                for v in x.values():
                    walk(v)
        walk(self.out)
        self.assertEqual({k.lower() for k in keys} & {"lat", "lon", "latitude", "longitude", "place", "places", "sightings", "address", "content", "text"}, set())
        self.assertNotIn("北比良", json.dumps(self.out, ensure_ascii=False))
        for m in self.out["municipalities"].values():
            self.assertEqual(set(m), {"monthly", "latest"})
        run.check_counts_bear(None, self.out)
        with self.assertRaises(run.SanityError):
            run.check_counts_bear(self.out, {**self.out, "total_fy": 10})

    def test_a_page_whose_heading_is_gone_or_with_too_few_entries_is_refused(self):
        with self.assertRaises(kuma.OtsuKumaSourceError):
            kuma.parse(HTML.replace("目撃情報一覧", "一覧"), NOW)
        with self.assertRaises(kuma.OtsuKumaSourceError):
            kuma.parse(HTML.split("<h3>令和8年8月24日")[0] + "</div></article></body></html>", NOW)      # only the 5 newest... then 4 < MIN_ROWS
        self.assertTrue(issubclass(kuma.OtsuKumaSourceError, ValueError))

    def test_an_impossible_date_or_one_after_today_is_counted_and_too_many_refuse_the_page(self):
        bad_day = HTML.replace("令和8年10月3日（土曜）8時30分頃", "令和8年2月31日（土曜）8時30分頃", 1)
        out = kuma.parse(bad_day, NOW)
        self.assertEqual(out["unparsed"], 1)
        self.assertEqual(out["total_fy"], 31)
        future = HTML.replace("令和8年10月3日（土曜）8時30分頃", "令和8年12月3日（土曜）8時30分頃", 1)
        self.assertEqual(kuma.parse(future, NOW)["unparsed"], 1)
        many = HTML
        for d in ("10月3日（土曜）8時30分", "10月3日（土曜）6時00分", "9月11日（金曜）7時30分"):
            many = many.replace("令和8年" + d, "令和8年2月31日（土曜）0時00分", 1)
        with self.assertRaises(kuma.OtsuKumaSourceError):
            kuma.parse(many, NOW)

    def test_entries_above_the_heading_are_not_read(self):
        extra = HTML.replace("<h2><span class=\"bg\">", "<h3>令和8年1月1日（木曜）0時00分頃</h3><h2><span class=\"bg\">", 1)
        self.assertEqual(kuma.parse(extra, NOW)["total_fy"], 32)

    def test_the_default_fetch_is_the_polite_one(self):
        seen = []

        def fake(url, *a, **k):
            seen.append(url)
            return HTML.encode()
        from unittest import mock
        with mock.patch.object(kumalib, "polite_fetch", fake):
            out = kuma.collect(now=NOW)
        self.assertEqual(seen, [kuma.PAGE])
        self.assertEqual(out["total_fy"], 32)

    def test_otsu_is_collected_as_a_counts_source_with_the_counts_check(self):
        src = next(s for s in run.GROUPS["kuma"] if s.name == "otsu_kuma")
        self.assertIs(src.check, run.check_counts_bear)
        self.assertNotIn("otsu_bear", [s.name for s in run.GROUPS["kuma"]])


if __name__ == "__main__":
    unittest.main()
