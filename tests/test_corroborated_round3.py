"""Fukushima City, Hirakawa City and the Fukushima TV bear stories: small copies of the real page structure."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build
from sites.kuma import live as live_mod
from sokuhou.sources import corroborated as co
from sokuhou.sources import kumalib
from tests.test_corroborated import TODAY, counts_with_records
from tests.test_kuma_build import CFG, COUNTS_META, HAVE_PYPDF, _yamaguchi
from tests.test_kuma_cite import make_raw

FUKUSHIMA_CITY = """<html><table><tr><th>No</th><th>日時</th><th>場所 (獣マップへリンク)</th><th>備考</th></tr>
<tr><td>131</td><td>令和8年9月23日(水曜日) 12時30分</td><td>松川町字杉内地内 (獣マップへリンク)</td><td></td></tr>
<tr><td>129</td><td>令和8年9月17日(木曜日) 6時00分</td><td>平石字信夫隠地内 (獣マップへリンク)</td><td>クマの足跡</td></tr>
<tr><td>128</td><td>令和8年9月16日(水曜日) 16時35分</td><td>飯坂町中野字朴沢地内 (獣マップへリンク)</td><td>車と衝突事故によりクマは死亡</td></tr></table></html>"""

HIRAKAWA = """<html><h1>令和8年度クマ出没情報</h1><table><tr><th>種別</th><th>年月日</th><th>時間</th><th>場所</th><th>詳細</th></tr>
<tr><td>目撃</td><td>令和8年4月15日</td><td>8時20分頃</td><td>碇ヶ関古懸三ツ森</td><td>親子のクマ2頭目撃</td></tr>
<tr><td>農作物被害</td><td>令和8年9月30日</td><td>-</td><td>碇ヶ関樋ヶ沢</td><td>デントコーンの食害</td></tr></table></html>"""

FTV_ONE = """<html><body><h1>【熊出没】10月5日（月）福島県のクマ...</h1>
<div class="x">【熊出没】10月5日（月）福島県のクマ目撃情報 白河市の市道<br>2026年10月05日 12:16</div>
<p>＝＝＜中通り＞＝＝</p><p>【白河市】</p>
<p>・関辺油久保 午前7時50分ごろ 市道にいるクマ1頭（体長1ｍ）</p>
<p>＝＝＜浜通り＞＝＝</p><p>※情報が入り次第更新します</p></body></html>"""

FTV_TWO_DAYS = """<html><body><div>【熊出没】10月3日（土）・4日（日）福島県のクマ目撃情報 大玉村の道路や土手でクマ目撃</div>
<p>【大玉村】</p><p>・玉井袖窪 3日午前5時ごろ 道路上のクマ1頭（体長1m）を目撃</p>
<p>・玉井上額沢 4日午前4時ごろ 田んぼの土手でクマ1頭（体長1m）を目撃</p>
<p>【伊達市】</p><p>・梁川町舟生深沢 午後4時20分ごろ 県道で足跡を確認</p>
<p>・梁川町白根 5日午前1時ごろ クマ1頭</p></body></html>"""

DAY_LIST = """<html><a href="https://www.fukushima-tv.co.jp/localnews/2026/10/2026101000000003.html"><span>【熊出没】10月10日(土)福島県のクマ目撃情報 会津若松市</span></a>
<a href="https://www.fukushima-tv.co.jp/localnews/2026/10/2026101000000004.html"><span>天気予報</span></a>
<a href="https://www.fukushima-tv.co.jp/localnews/2026/10/2026101000000003.html"><span>【熊出没】10月10日(土)福島県のクマ目撃情報 会津若松市</span></a></html>"""


def tuples(rows):
    return [(r["observed_at"], r["city"], r["place"], r["kind"], r["count"]) for r in rows]


class CityParsersTest(unittest.TestCase):
    def test_fukushima_city_drops_the_map_link_and_reads_remarks(self):
        self.assertEqual(tuples(co.parse_fukushima_city(FUKUSHIMA_CITY)), [
            ("2026-09-23", "福島市", "松川町字杉内地内", "目撃", None), ("2026-09-17", "福島市", "平石字信夫隠地内", "痕跡", None),
            ("2026-09-16", "福島市", "飯坂町中野字朴沢地内", "その他", None)])         # a road accident is neither a sighting nor a trace

    def test_hirakawa_separates_sightings_from_crop_damage(self):
        self.assertEqual(tuples(co.parse_hirakawa(HIRAKAWA)), [("2026-04-15", "平川市", "碇ヶ関古懸三ツ森", "目撃", 2), ("2026-09-30", "平川市", "碇ヶ関樋ヶ沢", "被害", None)])

    def test_pages_without_rows_are_refused(self):
        for parser in (co.parse_fukushima_city, co.parse_hirakawa):
            with self.assertRaises(co.CorroboratedError):
                parser("<html><p>お知らせ</p></html>")


class FukushimaTvTest(unittest.TestCase):
    URL = "https://www.fukushima-tv.co.jp/localnews/2026/10/2026100500000006.html"

    def test_the_links_of_bear_stories_are_picked_from_a_day_list_once(self):
        self.assertEqual(co.ftv_article_links(DAY_LIST), ["https://www.fukushima-tv.co.jp/localnews/2026/10/2026101000000003.html"])

    def test_a_one_day_story_is_dated_by_its_title(self):
        self.assertEqual(tuples(co.parse_ftv_article(FTV_ONE, self.URL)), [("2026-10-05", "白河市", "関辺油久保", "目撃", 1)])

    def test_a_story_of_two_days_dates_each_line_by_its_day_prefix_and_leaves_out_an_undated_or_foreign_day(self):
        got = tuples(co.parse_ftv_article(FTV_TWO_DAYS, "https://www.fukushima-tv.co.jp/localnews/2026/10/2026100400000004.html"))
        self.assertEqual(got, [("2026-10-03", "大玉村", "玉井袖窪", "目撃", 1), ("2026-10-04", "大玉村", "玉井上額沢", "目撃", 1)])
        # '伊達市 ... 午後4時20分ごろ' has no day in a two-day story, and '5日' is not one of the story's days: neither is guessed

    def test_a_story_from_january_about_december_belongs_to_the_year_before(self):
        html = FTV_ONE.replace("10月5日", "12月31日")
        got = co.parse_ftv_article(html, "https://www.fukushima-tv.co.jp/localnews/2027/01/2027010100000001.html")
        self.assertEqual(got[0]["observed_at"], "2026-12-31")

    def test_a_story_without_a_title_is_refused(self):
        with self.assertRaises(co.CorroboratedError):
            co.parse_ftv_article("<html>お知らせ</html>", self.URL)

    def test_the_reader_reads_the_day_lists_then_each_story_once_and_a_missing_day_is_only_a_missing_day(self):
        asked = []

        def fetch(url):
            asked.append(url)
            if url.endswith("/2026/10/12/"):
                raise OSError("404")
            if url.endswith("/2026/10/05/"):
                return DAY_LIST.replace("2026101000000003", "2026100500000006").encode("utf-8")
            if url.endswith("2026100500000006.html"):
                return FTV_ONE.encode("utf-8")
            return b"<html></html>"
        naps = []
        got = co.ftv_reader(date(2026, 10, 12), days=9)(fetch, lambda: naps.append(1))
        self.assertEqual(tuples(got), [("2026-10-05", "白河市", "関辺油久保", "目撃", 1)])
        self.assertEqual(sum(1 for u in asked if u.endswith("/")), 9)                       # 9 days of lists
        self.assertEqual(sum(1 for u in asked if u.endswith("2026100500000006.html")), 1)    # the story once, though two lists link to it
        self.assertEqual(len(naps), len(asked))                                             # a pause before every request

    def test_a_page_that_suddenly_lists_dozens_of_stories_is_refused(self):
        many = "".join(f'<a href="https://www.fukushima-tv.co.jp/localnews/2026/10/20261005{i:08d}.html"><span>【熊出没】10月5日 福島県</span></a>' for i in range(60))
        with self.assertRaises(co.CorroboratedError):
            co.ftv_reader(date(2026, 10, 12), days=1)(lambda url: many.encode("utf-8"), lambda: None)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class HirakawaCreditTest(unittest.TestCase):
    def build(self, city):
        with tempfile.TemporaryDirectory() as tmp:
            raw = counts_with_records()
            raw["corroborated"] = [{**r, "city": city} for r in raw["corroborated"]]
            raw["municipalities"] = {**raw["municipalities"], city: raw["municipalities"]["福島市"]}
            with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
                build.render_site(make_raw(), CFG, Path(tmp) / "s", release=True, prefs={"fukushima": raw, "yamaguchi": _yamaguchi()}, today=TODAY)
            return (Path(tmp) / "s" / "live" / "fukushima" / "index.html").read_text(encoding="utf-8")

    def test_the_credit_the_licence_asks_for_is_printed_for_hirakawa_and_for_no_other_city(self):
        self.assertIn("平川市のデータ(公共データ利用規約・第1.0版)を、当サイトが加工して作成しました", self.build("平川市"))
        self.assertNotIn("公共データ利用規約", self.build("福島市"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class CoverageWordingTest(unittest.TestCase):
    def page(self, raw):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            build.render_site(make_raw(), CFG, Path(tmp) / "s", release=True, prefs={"fukushima": raw, "yamaguchi": _yamaguchi()}, today=TODAY)
            return (Path(tmp) / "s" / "live" / "fukushima" / "index.html").read_text(encoding="utf-8")

    def test_it_says_which_municipalities_have_places_unless_they_all_do(self):
        some = counts_with_records()
        self.assertIn("場所まで載せているのは、福島市の分だけで、ほかの市町村の目撃は、上の件数にだけ含まれます", self.page(some))
        every = counts_with_records()
        every["corroborated"] = every["corroborated"] + [{"observed_at": "2026-09-02", "city": "会津若松市", "place": "町北町", "kind": "目撃", "count": None}]
        html = self.page(every)
        self.assertIn("すべての市町村の分です", html)
        self.assertNotIn("ほかの市町村の目撃は、上の件数にだけ", html)


if __name__ == "__main__":
    unittest.main()
