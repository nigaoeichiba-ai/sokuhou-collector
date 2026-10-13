"""Shizuoka, Kanagawa and Ishikawa publish their bear lists as PDFs behind a page: finding the PDF, reading its rows, and the three adapters."""
import unittest
from datetime import datetime
from unittest import mock

from sokuhou import run
from sokuhou.sources import corroborated, kumacounts, kumalib, prefpdfs
from sokuhou.sources import ishikawa_kuma, kanagawa_kuma, shizuoka_kuma

NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)

SHIZUOKA = """№ 目撃日 時間 市町 地名等 備考
1 4月2日 6:30 富士宮市 猪之頭
3 4月6日 18:00 静岡市葵区 梅ヶ島
6 4月13日 6:55 浜松市浜名区 引佐町的場
10 5月12日 11:30 裾野市 須山　 十里木越前岳登山道
28 5月23日 17:45 浜松市浜名区 引佐町狩宿 5/23捕獲
110 10月2日 21:25 富士宮市 内房
110件R8目撃件数
3/3 ページ"""

KANAGAWA = """月日 時間 頭数 状況 場所等 区分
目撃・
痕跡
その他
1 4月4日 5時30分頃 1 目撃 松田町寄 人里 ○
4 5月13日 7時頃 1 痕跡 山北町玄倉 山中 ○
13 6月9日 13時頃 2 目撃 相模原市緑区牧野 人里 ○
21 7月11日 日中 1 目撃 伊勢原市日向 山中 ○
34 9月15日 17時20分頃 1 捕殺
厚木市中荻野
調査目的の生体捕獲用のはこわなに錯誤捕獲。
47 10月10日 11時ごろ 1 目撃 相模原市緑区鳥屋 山中 ○
計 45 2"""

ISHIKAWA = """令和８年のクマ出没記録（目撃情報）
番号 場所 備考
1 R8.2.23 9時25分 能美市和光台4丁目地内
能美市和光台４丁目にて、東の山へ向かう子グマ１頭を
目撃
2 R8.4.6 5時45分 小松市那谷町地内
揚水機場付近の県道を横断するクマ２頭を目撃
3 R8.4.6 16時50分頃 宝達志水町小川地内
米出インター口付近にて、クマ１頭を目撃
206 R8.10.1 6時50分 小松市中海町地内 東部地区グラウンドへ坂を上がっていくクマ1頭を目撃
令和８年のクマ出没記録（目撃情報）
番号 場所 備考出没日時
208 R8.10.3 5時27分頃 七尾市鵜浦町地内 鵜浦町地内の市道でクマらしき動物1頭を目撃
210 R8.10.5 20時10分 野々市市三日市町地内 国道付近にて、クマの幼獣1頭を目撃
211 R8.10.6 20時10分 どこかの村内 国道付近にて、クマ1頭を目撃"""

PAGE_HTML = """<html><a href="/a/261005kuma.pdf">【NEW】令和8年度クマ出没情報(10月5日時点) (PDF 54.9KB)</a>
<a href="/a/r7kumamap.pdf">令和7年度クマ出没情報 (PDF 72.0KB)</a><a href="https://other.example/x.pdf">令和8年度クマ出没情報 (PDF)</a></html>"""


def tup(rows):
    return [(r["observed_at"], r["city"], r["place"], r["kind"], r["count"]) for r in rows]


class FindTest(unittest.TestCase):
    def test_the_pdf_of_this_fiscal_year_is_found_by_its_label_or_address(self):
        base = "https://www.pref.example.jp/x/1.html"
        self.assertEqual(prefpdfs.pdf_link(PAGE_HTML, base, label="令和8年度クマ出没情報"), "https://www.pref.example.jp/a/261005kuma.pdf")
        self.assertEqual(prefpdfs.pdf_link(PAGE_HTML, base, href="r7kumamap"), "https://www.pref.example.jp/a/r7kumamap.pdf")

    def test_a_pdf_on_another_host_or_no_pdf_at_all_is_refused(self):
        base = "https://www.pref.example.jp/x/1.html"
        with self.assertRaises(prefpdfs.PdfListError):
            prefpdfs.pdf_link(PAGE_HTML, base, href="x.pdf")
        with self.assertRaises(prefpdfs.PdfListError):
            prefpdfs.pdf_link(PAGE_HTML, base, label="令和9年度")


class ParseTest(unittest.TestCase):
    def test_shizuoka_keeps_wards_and_marks_a_capture(self):
        got = tup(prefpdfs.parse_shizuoka(SHIZUOKA, 2026))
        self.assertEqual(got[0], ("2026-04-02", "富士宮市", "猪之頭", "目撃", None))
        self.assertIn(("2026-04-06", "静岡市葵区", "梅ヶ島", "目撃", None), got)
        self.assertIn(("2026-05-23", "浜松市浜名区", "引佐町狩宿 5/23捕獲", "捕獲", None), got)
        self.assertEqual(len(got), 6)                                     # the footer lines are not rows

    def test_kanagawa_reads_the_status_the_number_and_a_place_on_the_next_line(self):
        got = tup(prefpdfs.parse_kanagawa(KANAGAWA, 2026))
        self.assertEqual(got[0], ("2026-04-04", "松田町", "松田町寄", "目撃", 1))
        self.assertIn(("2026-05-13", "山北町", "山北町玄倉", "痕跡", 1), got)
        self.assertIn(("2026-06-09", "相模原市", "相模原市緑区牧野", "目撃", 2), got)
        self.assertIn(("2026-09-15", "厚木市", "厚木市中荻野", "捕獲", 1), got)
        self.assertIn(("2026-10-10", "相模原市", "相模原市緑区鳥屋", "目撃", 1), got)
        self.assertEqual(len(got), 6)

    def test_ishikawa_reads_a_status_over_several_lines_and_full_width_digits(self):
        got = tup(prefpdfs.parse_ishikawa(ISHIKAWA))
        self.assertEqual(got[0], ("2026-02-23", "能美市", "能美市和光台4丁目地内", "目撃", 1))
        self.assertIn(("2026-04-06", "小松市", "小松市那谷町地内", "目撃", 2), got)
        self.assertIn(("2026-10-05", "野々市市", "野々市市三日市町地内", "目撃", 1), got)           # 野々市市 is not read as 野々市 + 市
        self.assertIn(("2026-10-01", "小松市", "小松市中海町地内", "目撃", 1), got)
        self.assertEqual(len(got), 6)                                    # 'どこかの村内' is not a municipality of the prefecture: left out

    def test_text_without_rows_is_refused(self):
        for fn in (lambda: prefpdfs.parse_shizuoka("お知らせ", 2026), lambda: prefpdfs.parse_kanagawa("お知らせ", 2026), lambda: prefpdfs.parse_ishikawa("お知らせ")):
            with self.assertRaises(prefpdfs.PdfListError):
                fn()


def fake_fetch(page_html):
    def fetch(url):
        return page_html.encode("utf-8") if url.endswith((".html", "/")) else b"%PDF"
    return fetch


class AdapterTest(unittest.TestCase):
    def run_adapter(self, mod, html, text, rows_min=1):
        with mock.patch.object(mod, "fetch", fake_fetch(html)), mock.patch.object(corroborated, "pdf_text", return_value=text), \
                mock.patch.object(mod, "MIN_ROWS", rows_min), mock.patch.object(kumacounts, "PAUSE", 0):
            return mod.collect(NOW)

    def test_shizuoka_counts_by_month_and_stores_the_places_of_this_fiscal_year(self):
        out = self.run_adapter(shizuoka_kuma, PAGE_HTML.replace('href="https://other.example/x.pdf"', 'href="/skip.txt"'), SHIZUOKA)
        self.assertEqual(out["total_fy"], 6)
        self.assertEqual(out["municipalities"]["富士宮市"]["latest"], "2026-10-02")
        self.assertEqual(len(out["corroborated"]), 6)
        self.assertEqual({k for r in out["corroborated"] for k in r}, corroborated.STORED_FIELDS)
        run.check_counts_bear(None, out)

    def test_kanagawa_and_ishikawa_are_found_by_their_own_link(self):
        kn = '<a href="/documents/15077/kuma_r8_1013.pdf">ツキノワグマの目撃等情報を更新しました(令和8年10月13日)(PDF:395KB)</a><a href="/documents/15077/kuma_r5_4.pdf">令和4年度</a>'
        out = self.run_adapter(kanagawa_kuma, f"<html>{kn}</html>", KANAGAWA)
        self.assertEqual((out["total_fy"], out["source"]), (6, "kanagawa"))
        self.assertTrue(out["source_file"].endswith("kuma_r8_1013.pdf"))
        out = self.run_adapter(ishikawa_kuma, '<html><a href="documents/261007mokugeki.pdf">詳細な出没情報(PDF:273KB)</a></html>', ISHIKAWA)
        self.assertEqual(out["source"], "ishikawa")
        self.assertEqual(out["municipalities"]["能美市"]["monthly"], {"R07": {"2": 1}})              # February belongs to the previous fiscal year
        self.assertEqual(out["total_fy"], 5)
        self.assertEqual(len(out["corroborated"]), 5)                                                  # the February row is not in this fiscal year's table

    def test_too_few_rows_stores_nothing(self):
        with self.assertRaises(prefpdfs.PdfListError):
            self.run_adapter(kanagawa_kuma, PAGE_HTML.replace("261005kuma", "kuma_r8_1013"), KANAGAWA, rows_min=50)

    def test_the_three_are_registered_with_the_carry_over(self):
        by_name = {s.name: s for s in run.GROUPS["kuma"]}
        for n in ("shizuoka_kuma", "kanagawa_kuma", "ishikawa_kuma"):
            self.assertIs(by_name[n].merge, corroborated.carry_over, n)


if __name__ == "__main__":
    unittest.main()
