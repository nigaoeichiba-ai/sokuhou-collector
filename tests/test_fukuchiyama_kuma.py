"""福知山市: the list page links one page per month of the fiscal year; each month's table gives the day and the place."""
import unittest
from datetime import datetime
from unittest import mock

from sokuhou import run
from sokuhou.sources import corroborated as co
from sokuhou.sources import fukuchiyama_kuma as kuma
from sokuhou.sources import kumacounts, kumalib

NOW = datetime(2026, 10, 13, 6, 30, tzinfo=kumalib.JST)

TOP = """<html><a href="/soshiki/27/1.html">京都府クマ目撃情報</a>
<p>令和8年度目撃情報 <a href="/soshiki/27/84428.html">・4月目撃情報</a> <a href="/soshiki/27/89598.html">・10月目撃情報</a>
<a href="https://other.example/x.html">・9月目撃情報</a></p>
<p>令和7年度目撃情報 <a href="/soshiki/27/74358.html">・4月目撃情報</a> <a href="/soshiki/27/79489.html">・10月目撃情報</a></p></html>"""


def month(era, m, rows):
    body = "".join(f'<tr><th>{d}</th><th><a href="/x.pdf">{p} [PDFファイル／175KB]</a></th></tr>' for d, p in rows)
    return f"<html><h1>熊出没情報〔令和{era}年{m}月分〕</h1><table><thead><tr><th>目撃日</th><th>目撃場所</th></tr>{body}<tr><th>&nbsp;</th><th>&nbsp;</th></tr></thead></table></html>"


PAGES = {co.FUKUCHIYAMA_PAGE: TOP,
         "https://www.city.fukuchiyama.lg.jp/soshiki/27/84428.html": month(8, 4, [("20日（月曜日）", "福知山市大江町")]),
         "https://www.city.fukuchiyama.lg.jp/soshiki/27/89598.html": month(8, 10, [("5日（月曜日）", "福知山市大江町尾藤（尾藤口）"), ("<p>6<strong>日（火曜日）</strong></p>", "福知山市字大門"),
                                                                                      ("11日（日曜日）", "福知山市字夷")])}


class ParseTest(unittest.TestCase):
    def test_the_month_links_of_this_fiscal_year_only_and_only_on_the_citys_host(self):
        self.assertEqual(co.fukuchiyama_month_links(TOP, 8), ["https://www.city.fukuchiyama.lg.jp/soshiki/27/84428.html", "https://www.city.fukuchiyama.lg.jp/soshiki/27/89598.html"])
        self.assertEqual(len(co.fukuchiyama_month_links(TOP, 7)), 2)
        with self.assertRaises(co.CorroboratedError):
            co.fukuchiyama_month_links(TOP, 9)

    def test_a_month_page_gives_the_day_and_the_place_without_the_pdf_note(self):
        got = [(r["observed_at"], r["place"]) for r in co.parse_fukuchiyama_month(PAGES["https://www.city.fukuchiyama.lg.jp/soshiki/27/89598.html"])]
        self.assertEqual(got, [("2026-10-05", "福知山市大江町尾藤(尾藤口)"), ("2026-10-06", "福知山市字大門"), ("2026-10-11", "福知山市字夷")])

    def test_a_page_without_its_month_is_refused(self):
        with self.assertRaises(co.CorroboratedError):
            co.parse_fukuchiyama_month("<html><h1>お知らせ</h1></html>")


class CollectTest(unittest.TestCase):
    def fetch(self, url):
        return PAGES[url].encode("utf-8")

    def test_the_adapter_counts_by_month_and_stores_the_places(self):
        with mock.patch.object(kuma, "fetch", self.fetch), mock.patch.object(kuma, "MIN_ROWS", 1), mock.patch.object(kumacounts, "PAUSE", 0):
            out = kuma.collect(NOW)
        self.assertEqual(out["total_fy"], 4)
        self.assertEqual(out["municipalities"]["福知山市"]["monthly"]["R08"], {"4": 1, "10": 3})
        self.assertEqual([r["place"] for r in out["corroborated"]], ["福知山市字夷", "福知山市字大門", "福知山市大江町尾藤(尾藤口)", "福知山市大江町"])
        run.check_counts_bear(None, out)

    def test_a_month_that_cannot_be_read_does_not_hide_the_others(self):
        def fetch(url):
            if url.endswith("84428.html"):
                raise OSError("down")
            return self.fetch(url)
        got = co.fukuchiyama_reader(8)(fetch, lambda: None)
        self.assertEqual(len(got), 3)
        with self.assertRaises(co.CorroboratedError):
            co.fukuchiyama_reader(8)(lambda url: (_ for _ in ()).throw(OSError("down")) if url.endswith(".html") and "27/8" in url else TOP.encode(), lambda: None)

    def test_it_is_registered_with_the_carry_over(self):
        self.assertIs({s.name: s for s in run.GROUPS["kuma"]}["fukuchiyama_kuma"].merge, co.carry_over)


if __name__ == "__main__":
    unittest.main()
