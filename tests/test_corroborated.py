"""Sightings two publications agree on: the parsers of the municipalities' pages, the match with the prefecture's list, and what the page shows.

The pages below are small copies of the real structure (rows are real facts of 2026-10: a date, a place name).
"""
import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build
from sites.kuma import live as live_mod
from sokuhou import run, sitecheck
from sokuhou.sources import corroborated as co
from sokuhou.sources import kumalib
from tests.test_kuma_build import CFG, COUNTS_META, HAVE_PYPDF, _yamaguchi
from tests.test_kuma_cite import make_raw

TODAY = date(2026, 10, 12)

SAKATA = """<html><head><title>令和8年度クマ目撃情報</title></head><body><h1>令和8年度クマ目撃情報</h1>
<table><caption>管内クマ目撃情報一覧（10月）</caption>
<tr><th>&nbsp;</th><th>出没日</th><th>出没時間</th><th>地域</th><th>出没場所</th><th>目撃等情報</th></tr>
<tr><td class="center">133</td><td>10月5日</td><td>22：45頃</td><td>酒田</td><td>大多新田</td><td class="left">字村添地内の民家付近から北進するクマ（1頭・体長1.0ｍ程度）を目撃</td></tr>
</table>
<table><caption>管内クマ目撃情報一覧（9月）</caption>
<tr><th>&nbsp;</th><th>出没日</th><th>出没時間</th><th>地域</th><th>出没場所</th><th>目撃等情報</th></tr>
<tr><td>132</td><td>9月29日</td><td>16：30頃</td><td>酒田</td><td>坂野辺新田</td><td>字西狢山地内の工場付近から東進するクマ（1頭・体長1.0ｍ程度）を目撃</td></tr>
<tr><td>131</td><td>9月25日</td><td>10：20頃</td><td>酒田</td><td>坂野辺新田</td><td>字地続山地内のブドウハウスにおいてクマによるのものと思われる破損を確認</td></tr>
</table>
<table><caption>管内クマ目撃情報一覧（4月）</caption>
<tr><th>&nbsp;</th><th>出没日</th><th>出没時間</th><th>地域</th><th>出没場所</th><th>目撃等情報</th></tr>
<tr><td>1</td><td>4月1日</td><td>5：00頃</td><td>酒田</td><td>臼ケ沢</td><td>字池田通地内でクマ（1頭）を目撃</td></tr>
</table></body></html>"""

YAMAGATA_CITY = """<html><body><h1>クマに関する情報</h1><p>過去の記録は令和7年度のページへ。</p>
<p>【令和8年度クマ出没状況】<br>
No.108　10月3日（土曜）　午前11時00分頃　大字柏倉地内の山林にてクマ1頭を目撃<br>
No.107　10月2日（金曜）　午後5時45分頃　大字下宝沢地内の農地にてクマ1頭を目撃<br>
No.106　9月30日（水曜）　午前11時30分頃　大字上桜田地内(悠創の丘)にてクマのような動物2頭を目撃<br>
No.102　9月23日（水曜）午後0時30分頃　花楯二丁目地内の路上にてクマのような動物1頭を目撃<br>
No.92　8月2日（日曜）　午後1時00分頃　大字神尾地内の山林にてクマの疑いのある唸り声を聞いたとの通報<br>
</p><p>【令和7年度クマ出没状況】<br>
No.30　10月3日（金曜）　午前6時00分頃　大字黒沢地内の山林にてクマ1頭を目撃<br></p></body></html>"""

CHICHIBU = """<html><body><h2>令和8年度目撃等情報</h2>
<p>　5．令和8年9月18日　荒川日野地内（寺沢公衆トイレより北に約50m付近）</p>
<p>　2．令和8年6月13日　荒川贄川地内（荒川西小学校より南西に約200m付近）※　出没痕跡</p>
<p>&nbsp; &nbsp;9．令和8年10月9日　荒川上田野地内（諸上橋付近）</p>
<p>&nbsp;10．令和8年10月9日　荒川上田野地内（荒川総合運動公園付近）</p>
<p>　クマを目撃した場合は、秩父市役所生活衛生課まで連絡をお願いします。</p></body></html>"""

OGANO = """<html><body><main><h1>クマ等の出没情報について</h1>
<p><span>令和８年１０月６日　河原沢　大諸バス停北西１５０ｍ付近</span></p><p><a href="x.pdf">出没地点【PDF】</a></p>
<p><span>令和８年７月１５・１６日　小鹿野町両神薄　出原　出原バス停北東１００ｍ付近</span></p>
<p><span>令和７年１２月２３日　小鹿野町両神小森　両神ヘリポート北300ｍ付近</span></p></main></body></html>"""


def d(s):
    return date.fromisoformat(s)


class ParsersTest(unittest.TestCase):
    def test_sakata_reads_every_table_row_with_its_place_kind_and_count_and_the_year_of_the_fiscal_year(self):
        got = [(r["observed_at"], r["city"], r["place"], r["kind"], r["count"]) for r in co.parse_sakata(SAKATA)]
        self.assertEqual(got, [("2026-10-05", "酒田市", "大多新田字村添地内", "目撃", 1), ("2026-09-29", "酒田市", "坂野辺新田字西狢山地内", "目撃", 1),
                               ("2026-09-25", "酒田市", "坂野辺新田字地続山地内", "痕跡", None), ("2026-04-01", "酒田市", "臼ケ沢字池田通地内", "目撃", 1)])

    def test_a_row_in_january_to_march_belongs_to_the_next_calendar_year(self):
        html = SAKATA.replace("4月1日", "2月1日").replace("（4月）", "（2月）")
        self.assertIn("2027-02-01", [r["observed_at"] for r in co.parse_sakata(html)])

    def test_yamagata_city_reads_the_lines_of_each_year_section_and_counts_animals(self):
        got = {(r["observed_at"], r["place"], r["kind"], r["count"]) for r in co.parse_yamagata_city(YAMAGATA_CITY)}
        self.assertIn(("2026-10-03", "大字柏倉地内の山林", "目撃", 1), got)
        self.assertIn(("2026-09-30", "大字上桜田地内(悠創の丘)", "目撃", 2), got)
        self.assertIn(("2026-09-23", "花楯二丁目地内の路上", "目撃", 1), got)
        self.assertIn(("2026-08-02", "大字神尾地内の山林", "痕跡", None), got)         # a growl heard, not a sighting
        self.assertIn(("2025-10-03", "大字黒沢地内の山林", "目撃", 1), got)           # last year's section keeps last year's date
        self.assertEqual(len(got), 6)

    def test_chichibu_marks_a_trace_and_keeps_the_place_text(self):
        got = {(r["observed_at"], r["place"], r["kind"]) for r in co.parse_chichibu(CHICHIBU)}
        self.assertEqual(got, {("2026-09-18", "荒川日野地内(寺沢公衆トイレより北に約50m付近)", "目撃"), ("2026-06-13", "荒川贄川地内(荒川西小学校より南西に約200m付近)", "痕跡"),
                               ("2026-10-09", "荒川上田野地内(諸上橋付近)", "目撃"), ("2026-10-09", "荒川上田野地内(荒川総合運動公園付近)", "目撃")})

    def test_ogano_reads_full_width_digits_and_a_two_day_line_counts_for_its_first_day(self):
        got = [(r["observed_at"], r["place"]) for r in co.parse_ogano(OGANO)]
        self.assertEqual(got, [("2026-10-06", "河原沢 大諸バス停北西150m付近"), ("2026-07-15", "小鹿野町両神薄 出原 出原バス停北東100m付近"),
                               ("2025-12-23", "小鹿野町両神小森 両神ヘリポート北300m付近")])

    def test_a_page_that_changed_its_shape_is_refused_not_guessed(self):
        for parser, page in ((co.parse_sakata, "<html><h1>令和8年度</h1><table><tr><td>x</td></tr></table></html>"), (co.parse_yamagata_city, "<p>【令和8年度クマ出没状況】</p>"),
                             (co.parse_chichibu, "<p>お知らせ</p>"), (co.parse_ogano, "<p>お知らせ</p>")):
            with self.assertRaises(co.CorroboratedError, msg=parser.__name__):
                parser(page)
        with self.assertRaises(co.CorroboratedError):
            co.parse_sakata(SAKATA.replace("令和8年度", "").replace("令和8年度", ""))        # no fiscal year on the page: the dates cannot be placed
        with self.assertRaises(co.CorroboratedError):
            co.parse_chichibu("<p>1．令和8年2月31日　荒川</p>")

    def test_decode_follows_the_pages_own_charset(self):
        page = '<meta charset="Shift_JIS">令和8年度クマ'.encode("cp932")
        self.assertIn("令和8年度クマ", co.decode(page))


JOETSU_PAGE_HTML = """<html><body><h1>クマ目撃情報</h1>
<a href="/uploaded/attachment/290470.pdf">令和8年度：90件 [PDFファイル／186KB]</a>
<a href="/uploaded/attachment/284333.pdf">令和7年度：101件 [PDFファイル／205KB]</a>
<a href="/uploaded/attachment/268866.pdf">令和7年(1月から3月まで)：6件 [PDFファイル／72KB]</a></body></html>"""

JOETSU_TEXT = """№ 目撃月日 目撃時刻 目撃地域自治区 目撃場所 目撃時の状況
90 10月7日(水) 午前6時6分頃 清里区 寺脇地内 清里区寺脇地内の小竹橋付近で、体長約100センチメートルのクマ1頭を目撃したとの通報
が、清里区総合事務所にありました。
89 10月5日(月) 午前5時50分頃 三和区 北代地内 三和区北代地内の市道北代山高津線上で、体長100センチメートルほどのクマ1頭を目撃し
たとの通報が、三和区総合事務所にありました。
78 7月22日(水) 午前8時15分頃 三和区 錦地内
三和区錦地内、三和スポーツセンターから南に200ｍ付近の市道井ノ口錦線上で、体長100
センチメートルほどのクマらしき動物1頭を目撃したとの通報が、午前8時30分頃、三和区総
合事務所にありました。
クマの目撃情報（令和8年度）
2 4月12日(日) 午前10時頃 柿崎区 旭平地内
柿崎区旭平地内の吟田川付近で、体長約120センチメートルのクマ1頭を目撃したとの通報
が、柿崎区総合事務所にありました。"""


class JoetsuTest(unittest.TestCase):
    def test_the_pdf_of_the_newest_fiscal_year_is_found_on_the_page(self):
        self.assertEqual(co.joetsu_pdf_url(JOETSU_PAGE_HTML), "https://www.city.joetsu.niigata.jp/uploaded/attachment/290470.pdf")

    def test_a_pdf_on_another_host_or_a_page_without_one_is_refused(self):
        with self.assertRaises(co.CorroboratedError):
            co.joetsu_pdf_url(JOETSU_PAGE_HTML.replace('href="/uploaded/attachment/290470.pdf"', 'href="https://evil.example/290470.pdf"'))
        with self.assertRaises(co.CorroboratedError):
            co.joetsu_pdf_url("<html>お知らせ</html>")

    def test_the_text_is_read_row_by_row_even_when_the_status_runs_over_lines(self):
        got = [(r["observed_at"], r["place"], r["kind"], r["count"]) for r in co.parse_joetsu_text(JOETSU_TEXT)]
        self.assertEqual(got, [("2026-10-07", "清里区寺脇地内", "目撃", 1), ("2026-10-05", "三和区北代地内", "目撃", 1),
                               ("2026-07-22", "三和区錦地内", "目撃", 1), ("2026-04-12", "柿崎区旭平地内", "目撃", 1)])

    def test_text_without_rows_or_without_a_fiscal_year_is_refused(self):
        with self.assertRaises(co.CorroboratedError):
            co.parse_joetsu_text("令和8年度 お知らせ")
        with self.assertRaises(co.CorroboratedError):
            co.parse_joetsu_text(JOETSU_TEXT.replace("令和8年度", ""))

    def test_the_reader_goes_from_the_page_to_the_pdf_and_waits_between_the_two(self):
        asked, naps = [], []
        def fetch(url):
            asked.append(url)
            return JOETSU_PAGE_HTML.encode("utf-8")
        with mock.patch.object(co, "pdf_text", return_value=JOETSU_TEXT):
            got = co.joetsu_reader()(fetch, lambda: naps.append(1))
        self.assertEqual(len(got), 4)
        self.assertEqual(asked, [co.JOETSU_PAGE, "https://www.city.joetsu.niigata.jp/uploaded/attachment/290470.pdf"])
        self.assertEqual(naps, [1])


class NiigataHookTest(unittest.TestCase):
    def test_the_prefecture_rows_reach_the_match_with_the_same_reading_as_the_counts(self):
        from sokuhou.sources import arcgis_counts
        ms = lambda day: int(__import__("datetime").datetime(*day, 12, tzinfo=kumalib.JST).timestamp() * 1000)     # noqa: E731
        raw = [(ms((2026, 10, 7)), "7"), (None, "7"), (ms((2026, 10, 5)), "9"), (ms((2026, 10, 5)), "99")]
        got = arcgis_counts.matching_rows(raw, prefecture="新潟県", names={"7": "上越市", "9": "新潟県長岡市"})
        self.assertEqual(got, [(d("2026-10-07"), "上越市"), (d("2026-10-05"), "長岡市")])         # no date / an unknown code: left out

    def test_niigata_reads_joetsu_citys_list_through_the_hook(self):
        from sokuhou.sources import arcgis_counts, niigata_kuma
        seen = {}
        def fake(**kw):
            seen.update(kw)
            return kw["corroborate"]({"mode": "counts"}, [(d("2026-10-07"), "上越市")], TODAY, lambda url: b"")
        with mock.patch.object(arcgis_counts, "collect_counts", fake),                 mock.patch.object(co, "joetsu_reader", lambda: (lambda fetch, pause: co.parse_joetsu_text(JOETSU_TEXT))):
            out = niigata_kuma.collect(sleep=lambda s: None)
        self.assertEqual([r["place"] for r in out["corroborated"]], ["清里区寺脇地内"])


class ConfirmTest(unittest.TestCase):
    REC = [{"observed_at": "2026-10-05", "city": "酒田市", "place": "a", "kind": "目撃", "count": 1},
           {"observed_at": "2026-10-05", "city": "酒田市", "place": "b", "kind": "目撃", "count": 1},
           {"observed_at": "2026-10-03", "city": "山形市", "place": "c", "kind": "目撃", "count": 1}]

    def test_only_a_record_with_the_same_city_and_day_in_the_other_list_is_kept(self):
        got = co.confirm([(d("2026-10-05"), "酒田市"), (d("2026-10-02"), "山形市")], self.REC)
        self.assertEqual([r["place"] for r in got], ["b"])           # one prefecture row confirms one municipal record; the Oct-3 sighting is not in the prefecture's list

    def test_each_row_of_the_other_list_confirms_one_record_at_most(self):
        both = co.confirm([(d("2026-10-05"), "酒田市")] * 2, self.REC)
        self.assertEqual(sorted(r["place"] for r in both), ["a", "b"])
        self.assertEqual(len(co.confirm([(d("2026-10-05"), "酒田市")], self.REC)), 1)

    def test_a_day_off_by_one_or_another_city_confirms_nothing(self):
        self.assertEqual(co.confirm([(d("2026-10-04"), "酒田市"), (d("2026-10-05"), "鶴岡市"), (None, "山形市")], self.REC), [])

    def test_current_year_drops_other_years_and_the_future(self):
        rows = [{"observed_at": x, "city": "c", "place": "p", "kind": "目撃", "count": None} for x in ("2026-03-31", "2026-04-01", "2026-10-12", "2026-10-13")]
        self.assertEqual([r["observed_at"] for r in co.current_year(rows, TODAY)], ["2026-04-01", "2026-10-12"])


class AttachTest(unittest.TestCase):
    PAGES = [co.html_reader("https://sakata.example/", co.parse_sakata), co.html_reader("https://yamagata-city.example/", co.parse_yamagata_city)]
    PREF = [(d("2026-10-05"), "酒田市"), (d("2026-10-02"), "山形市"), (d("2026-09-29"), "酒田市")]

    def fetch(self, url):
        return {"https://sakata.example/": SAKATA, "https://yamagata-city.example/": YAMAGATA_CITY}[url].encode("utf-8")

    def test_the_confirmed_records_are_added_newest_first_and_nothing_else_changes(self):
        base = {"mode": "counts", "total_fy": 3}
        out = co.attach(dict(base), self.PREF, self.PAGES, self.fetch, TODAY)
        self.assertEqual([(r["observed_at"], r["place"]) for r in out["corroborated"]],
                         [("2026-10-05", "大多新田字村添地内"), ("2026-10-02", "大字下宝沢地内の農地"), ("2026-09-29", "坂野辺新田字西狢山地内")])
        self.assertEqual({k: v for k, v in out.items() if k not in ("corroborated", "corroborated_on")}, base)
        self.assertEqual(out["corroborated_on"], {"山形市": "2026-10-12", "酒田市": "2026-10-12"})
        for r in out["corroborated"]:
            self.assertEqual(set(r), co.STORED_FIELDS)

    def test_a_page_that_fails_is_skipped_and_reported_the_others_still_count(self):
        def fetch(url):
            if "sakata" in url:
                raise OSError("down")
            return self.fetch(url)
        err = io.StringIO()
        with redirect_stderr(err):
            out = co.attach({}, self.PREF, self.PAGES, fetch, TODAY)
        self.assertEqual([r["city"] for r in out["corroborated"]], ["山形市"])
        self.assertIn("sakata.example", err.getvalue())

    def test_when_nothing_can_be_confirmed_there_is_no_key_at_all(self):
        with redirect_stderr(io.StringIO()):
            self.assertNotIn("corroborated", co.attach({}, [], self.PAGES, self.fetch, TODAY))
            self.assertNotIn("corroborated", co.attach({}, self.PREF, self.PAGES, lambda url: b"<html>maintenance</html>", TODAY))


class CarryOverTest(unittest.TestCase):
    def rec(self, day, city, place="p"):
        return {"observed_at": day, "city": city, "place": place, "kind": "目撃", "count": None}

    def pack(self, fetched, records=None, on=None):
        out = {"fetched_at": fetched + "T06:30:00+09:00"}
        if records:
            out["corroborated"] = records
            out["corroborated_on"] = on
        return out

    def test_a_city_whose_page_failed_today_keeps_its_recent_records_and_the_others_are_fresh(self):
        old = self.pack("2026-10-12", [self.rec("2026-10-09", "酒田市"), self.rec("2026-10-02", "山形市")], {"酒田市": "2026-10-12", "山形市": "2026-10-12"})
        new = self.pack("2026-10-13", [self.rec("2026-10-02", "山形市"), self.rec("2026-10-12", "山形市", "q")], {"山形市": "2026-10-13"})
        got = co.carry_over(old, new)
        self.assertEqual([(r["city"], r["observed_at"]) for r in got["corroborated"]], [("山形市", "2026-10-12"), ("酒田市", "2026-10-09"), ("山形市", "2026-10-02")])
        self.assertEqual(got["corroborated_on"], {"酒田市": "2026-10-12", "山形市": "2026-10-13"})

    def test_every_page_failed_keeps_yesterdays_records(self):
        old = self.pack("2026-10-12", [self.rec("2026-10-09", "上越市")], {"上越市": "2026-10-12"})
        got = co.carry_over(old, self.pack("2026-10-13"))
        self.assertEqual([r["city"] for r in got["corroborated"]], ["上越市"])

    def test_a_page_that_stays_unreadable_stops_being_shown_after_three_days(self):
        old = self.pack("2026-10-09", [self.rec("2026-10-08", "上越市")], {"上越市": "2026-10-09"})
        self.assertIn("corroborated", co.carry_over(old, self.pack("2026-10-12")))              # 3 days: still kept
        self.assertNotIn("corroborated", co.carry_over(old, self.pack("2026-10-13")))           # 4 days: gone

    def test_nothing_to_carry_when_there_was_nothing_before(self):
        new = self.pack("2026-10-13")
        self.assertEqual(co.carry_over(None, new), new)
        self.assertEqual(co.carry_over({"fetched_at": "x"}, new), new)

    def test_the_kuma_sources_use_it_and_the_daily_job_installs_pypdf(self):
        by_name = {s.name: s for s in run.GROUPS["kuma"]}
        for name in ("niigata_kuma", "yamagata_kuma", "saitama_kuma"):
            self.assertIs(by_name[name].merge, co.carry_over, name)
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "kuma-live.yml").read_text(encoding="utf-8")
        self.assertIn("pip install --quiet -r requirements.txt", workflow)
        self.assertIn("pypdf", (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8"))


class StoreCheckTest(unittest.TestCase):
    def package(self, **extra):
        rows = [{"observed_at": "2026-10-05", "city": "酒田市"}, {"observed_at": "2026-10-04", "city": "山形市"}]
        out = kumalib.package_counts(source="yamagata", credit="c", update_note="n", as_of=d("2026-10-05"), rows=rows, page="p", files=["f"])
        out.update(extra)
        return out

    def test_a_counts_source_may_carry_confirmed_records_in_the_stored_shape_only(self):
        good = {"observed_at": "2026-10-05", "city": "酒田市", "place": "大多新田", "kind": "目撃", "count": 1}
        run.check_counts_bear(None, self.package(corroborated=[good]))
        for bad in ({**good, "lat": 38.9}, {**good, "city": "どこかの市"}, {k: v for k, v in good.items() if k != "kind"}):
            with self.assertRaises(run.SanityError):
                run.check_counts_bear(None, self.package(corroborated=[bad]))

    def test_rows_still_cannot_be_stored_under_the_old_keys(self):
        with self.assertRaises(run.SanityError):
            run.check_counts_bear(None, self.package(sightings=[{}]))


def counts_with_records():
    rows = [{"observed_at": "2026-10-03", "city": "福島市"}, {"observed_at": "2026-09-20", "city": "福島市"}, {"observed_at": "2026-09-02", "city": "会津若松市"}]
    out = kumalib.package_counts(source="fukushima", credit="出典:福島県の公開ページ", update_note="県が更新します", as_of=d("2026-10-05"), rows=rows,
                                 page="https://www.pref.fukushima.lg.jp/x.html", files=["https://www.pref.fukushima.lg.jp/x.html"])
    out["corroborated"] = [{"observed_at": "2026-10-03", "city": "福島市", "place": "荒井字ひみつ地内", "kind": "目撃", "count": 1},
                           {"observed_at": "2026-09-20", "city": "福島市", "place": "飯坂町ふしぎ付近", "kind": "痕跡", "count": None}]
    return out


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.raw = make_raw()
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs={"fukushima": counts_with_records(), "yamaguchi": _yamaguchi()}, today=TODAY)
            cls.plain = Path(cls.tmp.name) / "plain"
            plain = counts_with_records()
            del plain["corroborated"]
            build.render_site(cls.raw, CFG, cls.plain, release=True, prefs={"fukushima": plain, "yamaguchi": _yamaguchi()}, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel, root=None):
        return ((root or self.out) / rel).read_text(encoding="utf-8")

    def section(self):
        html = self.read("live/fukushima/index.html")
        return html.split("場所まで確認できた最新の目撃", 1)[1].split("<h2>", 1)[0]

    def test_the_confirmed_sightings_are_listed_with_their_place_and_kind(self):
        s = re.sub(r"<[^>]+>", " ", self.section())
        for want in ("福島市荒井字ひみつ地内", "福島市飯坂町ふしぎ付近", "目撃", "痕跡", "2件"):
            self.assertIn(want, s)

    def test_the_confirmed_section_names_no_source_and_carries_no_link(self):
        sec = self.section()
        self.assertNotIn("<a ", sec)
        self.assertNotIn("http", sec)
        self.assertNotIn("出典", sec)
        self.assertIn("複数の公開情報で一致を確認できた", sec)

    def test_without_confirmed_records_the_page_says_counts_only_and_has_no_such_section(self):
        plain = self.read("live/fukushima/index.html", self.plain)
        self.assertNotIn("場所まで確認できた", plain)
        self.assertIn("件数と最新の日付だけを載せています", plain)
        self.assertNotIn("荒井字ひみつ地内", plain)

    def test_the_other_pages_say_the_same_thing_as_the_prefecture_page(self):
        hub = self.read("live/index.html")
        self.assertIn("場所を確認できた目撃", hub)
        self.assertIn("複数の公開情報で一致を確認できた目撃は、場所も載せています", hub)
        cite = self.read("cite/index.html")
        self.assertIn("場所も載せています", cite)
        self.assertIn("件数(場所は、確認できた目撃だけ)", cite)
        self.assertIn("複数の公開情報で一致を確認できた目撃は、場所も載せています", self.read("about/index.html"))

    def test_confirmed_sightings_do_not_leak_into_the_list_the_map_the_feed_or_the_csv(self):
        for rel in ("live/feed.xml", "map/points.json", "live/index.html", "search/index.html"):
            self.assertNotIn("荒井字ひみつ地内", self.read(rel), rel)
        self.assertNotIn("荒井字ひみつ地内", self.read("data/kuma-sightings.csv"))
        self.assertNotIn("福島", self.read("data/kuma-sightings.csv"))

    def test_the_site_passes_the_site_checker(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])


if __name__ == "__main__":
    unittest.main()
