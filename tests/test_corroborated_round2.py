"""The parsers of the second round of municipalities (Tsuruoka, Nanyo, Shirataka; Sanjo; Minano, Hanno): small copies of the real page structure."""
import unittest
from datetime import date

from sokuhou.sources import corroborated as co

TSURUOKA = """<html><h1>令和8年度 鶴岡管内のクマ出没情報</h1>
<table><caption>鶴岡管内のクマ出没情報（9月）</caption>
<tr><th>No.</th><th>出没日</th><th>出没時間</th><th>出没場所</th><th>地域</th><th>目撃・痕跡情報</th></tr>
<tr><td>121</td><td>9月15日</td><td>7:28頃</td><td><img alt="x"><a href="a.pdf">下川字窪畑地内（PDF：308KB）</a></td><td>鶴岡</td><td>湯野浜駐在所付近の民家敷地内でクマ1頭（体長約1.5m）を目撃した。</td></tr>
<tr><td>119</td><td>9月11日</td><td>8:53頃</td><td>鼠ヶ関地内</td><td>温海</td><td>鼠ヶ関小学校付近でクマの足跡を確認した。</td></tr></table>
<table><caption>（2月）</caption>
<tr><th>No.</th><th>出没日</th></tr><tr><td>5</td><td>2月3日</td><td>6:00頃</td><td>大山地内</td><td>鶴岡</td><td>クマ1頭を目撃。</td></tr></table></html>"""

NANYO = """<html><h1>クマに関する情報等</h1><p>令和８年（令和８年１０月７日現在）のクマの目撃等の件数は４０件です。</p>
<table><tr><th>No.</th><th>出没(等)日</th><th>日時</th><th>場所</th><th>体長等</th><th>看板設置</th></tr>
<tr><td>４０</td><td>10月7日</td><td>午後4時30分頃</td><td>小岩沢地内</td><td>体長1.0ｍ程度</td><td>無</td></tr>
<tr><td>３９</td><td>9月30日</td><td>午後8時20分頃</td><td>金山地内</td><td>体長不明</td><td>無</td></tr></table></html>"""

SHIRATAKA = """<html><h1>令和8年度クマ出没情報一覧</h1>
<table><tr><th>No.</th><th>月日</th><th>目撃・痕跡 発見時刻</th><th>地区</th><th>内容</th><th>位置</th></tr>
<tr><td>１</td><td>4/22</td><td>22時30分</td><td>深山</td><td>道路を横断するクマを目撃</td><td>https://maps.example/1</td></tr>
<tr><td>２</td><td>4/25</td><td>8時00分</td><td>大瀬</td><td>クマの足跡を発見</td><td>https://maps.example/2</td></tr>
<tr><td>５８</td><td>10/5</td><td>6時00分</td><td>畔藤</td><td>クマを目撃</td><td>-</td></tr></table></html>"""

SANJO = """<html><table><tr><th>N o</th><th>年月日</th><th>場 所</th><th>時間</th><th>頭 数</th><th>人 身被 害</th><th>分 類</th><th>状 況</th></tr>
<tr><td>21</td><td>令和8年9月17日</td><td>下大浦</td><td>午前10時30分頃</td><td>1</td><td>無</td><td>痕跡</td><td>下大浦地内、民家近くでクマの痕跡（フン）が確認された。</td></tr>
<tr><td>20</td><td>令和8年9月15日</td><td>曲谷</td><td>午後1時30分頃</td><td>1</td><td>無</td><td>目撃</td><td>曲谷地内、トレイルカメラで、クマが1頭撮影された。</td></tr></table></html>"""

MINANO = """<html><h3>出没・目撃情報箇所一覧(令和８年度)</h3>
<h4>皆野地内</h4>
<p>令和８年６月１３日<br>
美の山山頂から親鼻駅方面へ15分ほど下った地点</p>
<h4>三沢地内</h4>
<p>令和8年7月11日<br>
林道雨乞曽根坂線入口付近<br>
<br>
令和8年7月8日<br>
林道大霧山線入口付近<br>
<br>
</p>
<p><span><strong>金沢地内</strong></span><br>
<br>
<span>令和８年７月８日</span><br>
<span>町営バス諏訪平バス停付近</span></p>
<h4>上日野沢地内</h4>
<p>令和８年７月１１日<br>
大平地内</p>
<h3>出没・目撃情報箇所一覧(令和７年度)</h3>
<h4>皆野地内</h4>
<p>令和８年１月９日<br>
蓑山神社付近</p></html>"""

HANNO = """<html><table><caption>令和8年度 クマの目撃情報一覧</caption>
<tr><th>番号</th><th>日付</th><th>場所</th><th>&nbsp;</th></tr>
<tr><th>10</th><td>令和8年9月26日午後8時00分頃</td><td>飯能市大字上名栗地内</td><td>太嘉橋付近</td></tr>
<tr><th><p>8</p></th><td><p>令和8年9月11日午後9時10分頃</p></td><td>飯能市大字上名栗地内</td><td>人見自治会館付近</td></tr>
<tr><th>7</th><td>令和8年7月24日朝方</td><td>入間市大字上谷ヶ貫地内</td><td>市境付近</td></tr></table></html>"""


def tuples(rows):
    return [(r["observed_at"], r["city"], r["place"], r["kind"], r["count"]) for r in rows]


class RoundTwoParsersTest(unittest.TestCase):
    def test_tsuruoka_drops_the_pdf_note_and_reads_traces_and_counts(self):
        self.assertEqual(tuples(co.parse_tsuruoka(TSURUOKA)), [
            ("2026-09-15", "鶴岡市", "下川字窪畑地内", "目撃", 1), ("2026-09-11", "鶴岡市", "鼠ヶ関地内", "痕跡", None), ("2027-02-03", "鶴岡市", "大山地内", "目撃", 1)])

    def test_nanyo_reads_full_width_numbers_and_takes_the_year_from_the_calendar_year_heading(self):
        self.assertEqual(tuples(co.parse_nanyo(NANYO)), [("2026-10-07", "南陽市", "小岩沢地内", "目撃", None), ("2026-09-30", "南陽市", "金山地内", "目撃", None)])

    def test_shirataka_reads_slash_dates_inside_the_fiscal_year(self):
        self.assertEqual(tuples(co.parse_shirataka(SHIRATAKA)), [("2026-04-22", "白鷹町", "深山", "目撃", None), ("2026-04-25", "白鷹町", "大瀬", "痕跡", None),
                                                                   ("2026-10-05", "白鷹町", "畔藤", "目撃", None)])

    def test_sanjo_reads_the_class_and_the_number_of_bears(self):
        self.assertEqual(tuples(co.parse_sanjo(SANJO)), [("2026-09-17", "三条市", "下大浦", "痕跡", 1), ("2026-09-15", "三条市", "曲谷", "目撃", 1)])

    def test_minano_keeps_the_area_heading_with_each_place_and_a_place_that_looks_like_an_area_stays_a_place(self):
        got = [(r["observed_at"], r["place"]) for r in co.parse_minano(MINANO)]
        self.assertEqual(got, [("2026-06-13", "皆野地内 美の山山頂から親鼻駅方面へ15分ほど下った地点"), ("2026-07-11", "三沢地内 林道雨乞曽根坂線入口付近"),
                               ("2026-07-08", "三沢地内 林道大霧山線入口付近"), ("2026-07-08", "金沢地内 町営バス諏訪平バス停付近"),
                               ("2026-07-11", "上日野沢地内 大平地内"), ("2026-01-09", "皆野地内 蓑山神社付近")])

    def test_hanno_keeps_only_its_own_rows_and_joins_the_landmark(self):
        self.assertEqual(tuples(co.parse_hanno(HANNO)), [("2026-09-26", "飯能市", "飯能市大字上名栗地内 太嘉橋付近", "目撃", None),
                                                          ("2026-09-11", "飯能市", "飯能市大字上名栗地内 人見自治会館付近", "目撃", None)])

    def test_every_parser_refuses_a_page_without_rows(self):
        for name, (_, parser) in co.PARSERS_ROUND2.items():
            with self.assertRaises(co.CorroboratedError, msg=name):
                parser("<html><h1>令和8年度 令和8年</h1><p>お知らせ</p></html>")

    def test_the_dates_a_page_gives_are_not_shifted_by_the_match(self):
        rows = co.parse_sanjo(SANJO)
        kept = co.confirm([(date(2026, 9, 17), "三条市")], rows)
        self.assertEqual([r["place"] for r in kept], ["下大浦"])


if __name__ == "__main__":
    unittest.main()
