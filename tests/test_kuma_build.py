"""The bear site: built from the ministry's PDFs (the test fixtures), checked against numbers from outside the code."""
import csv
import io
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import pypdf  # noqa: F401
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False

from sites.kuma import build, charts, content
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError
from sokuhou.sources import env_kuma

FIX = Path(__file__).parent / "fixtures"
CFG = {"site_url": "https://kuma-sokuho.com", "site_name": "クマ出没速報", "operator_name": "テスト運営",
       "contact_form_url": "https://forms.example.com/x", "contact_email": None, "adsense_pub_id": None,
       "bluesky_handle": "info-s.bsky.social", "x_handle": "infosokuho"}
LINKS = {"秋田": [{"label": "テスト", "url": "https://www.pref.akita.lg.jp/x", "source": "pref"}]}


def raw_data():
    page = ('<a href="r08jiko-gaiyo.pdf">a</a><a href="r08kinkyu-jishi.pdf">b</a>'
            '<a href="r07jiko-gaiyo.pdf">c</a><a href="r07kinkyu-jishi.pdf">d</a>').encode()
    files = {"syutubotu.pdf": "env_kuma_syutubotu.pdf", "injury-qe.pdf": "env_kuma_injury.pdf",
             "r08jiko-gaiyo.pdf": "env_kuma_r08_fatal.pdf", "r08kinkyu-jishi.pdf": "env_kuma_r08_emergency.pdf",
             "r07jiko-gaiyo.pdf": "env_kuma_r07_fatal.pdf", "r07kinkyu-jishi.pdf": "env_kuma_r07_emergency.pdf"}

    def fake(url):
        name = url.rsplit("/", 1)[1]
        return SimpleNamespace(body=page if name == "effort12.html" else (FIX / files[name]).read_bytes())
    with mock.patch.object(env_kuma, "fetch", fake):
        return env_kuma.collect()


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class KumaSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, links=LINKS)
        cls.d = build.prepare(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    # ---- the numbers
    def test_home_shows_the_national_figures(self):
        html = self.read("index.html")
        for text in ("50,801件", "20,513", "約2.5倍", "216件・238人(うち死亡13人)", "17,362件"):
            self.assertIn(text, html)

    def test_ranking_matches_the_press_top_five(self):
        html = self.read("ranking/sightings/index.html")
        rows = re.findall(r'<tr><td>(\d+)</td><td><a href="/([a-z]+)/">', html)
        self.assertEqual([slug for _, slug in rows[:5]], ["akita", "iwate", "miyagi", "niigata", "aomori"])
        self.assertEqual(rows[0][0], "1")
        self.assertEqual(len(rows), 37)  # 39 listed; Hokkaido and Chiba have "-" instead of figures

    def test_akita_page_matches_the_prefecture_own_figures(self):
        html = self.read("akita/index.html")
        self.assertIn("13,592件", html)
        self.assertIn("39道府県中1位", html)
        self.assertIn("59件・67人(うち死亡4人)", html)  # Akita Prefecture itself reports 59 cases, 67 people for FY R07
        self.assertIn("https://www.pref.akita.lg.jp/x", html)

    def test_months_not_yet_published_are_gaps_not_zeros(self):
        nat = self.d["national"]["monthly"]["R08"]
        self.assertEqual(nat[4:], [None] * 8)
        self.assertEqual(self.d["latest_month"], 7)
        self.assertEqual(self.d["nat_ytd"]["R08"], 17362)

    def test_year_on_year_ranking_excludes_small_bases(self):
        html = self.read("ranking/change/index.html")
        slugs = [x for x in re.findall(r'<a href="/([a-z]+)/">', html.split("<tbody>")[1]) if x in self.d["by_slug"]]
        self.assertTrue(slugs)
        for slug in slugs:
            self.assertGreaterEqual(self.d["by_slug"][slug]["ytd"]["R07"], 30)

    def test_prefectures_without_figures_are_named_where_the_text_says_so(self):
        nodata = [r["name"] for r in self.d["rows"] if not r["has"]]
        self.assertEqual(nodata, ["北海道", "千葉県"])
        self.assertIn("北海道と千葉県は、環境省の表に数値がありません", self.read("ranking/sightings/index.html"))
        self.assertIn("北海道と千葉県は、出没件数の欄が", self.read("guide/data/index.html"))
        self.assertIn("数値がありません(「-」)", self.read("chiba/index.html"))

    def test_text_comes_from_the_data(self):
        self.assertEqual(self.d["peak_month"], 10)
        self.assertIn("10月が最も多く(15,998件)", self.read("index.html"))

    # ---- cautions and honesty
    def test_every_comparison_page_carries_the_ministry_caution(self):
        for rel in ("ranking/sightings/index.html", "ranking/change/index.html", "ranking/injuries/index.html",
                    "trend/index.html", "akita/index.html"):
            html = self.read(rel)
            self.assertIn("速報値", html, rel)
            self.assertIn("都道府県ごとに異なる方法", html, rel)

    def test_freshness_statement_names_the_months_and_dates(self):
        html = self.read("index.html")
        self.assertIn("出没件数は7月分まで(2026年9月9日更新)", html)
        self.assertIn("令和8年8月末", html)
        self.assertIn("緊急銃猟は9月30日分まで(2026年10月1日更新)", html)

    def test_fatal_list_says_what_the_dates_mean(self):
        html = self.read("emergency/index.html")
        self.assertIn("被害者発見日", html)
        self.assertIn("2026年7月10日現在", html)
        self.assertIn("緊急銃猟(実施)", html)

    # ---- structure
    def test_pages(self):
        for rel in ("index.html", "trend/index.html", "emergency/index.html", "notify/index.html", "guide/index.html",
                    "about/index.html", "privacy/index.html", "contact/index.html", "404.html", "feed.xml", "sitemap.xml"):
            self.assertIn(rel, self.files)
        prefs = [f for f in self.files if re.fullmatch(r"[a-z]+/index\.html", f) and f.split("/")[0] in self.d["by_slug"]]
        self.assertEqual(len(prefs), 39)
        for g in content.GUIDES:
            self.assertIn(f"guide/{g['slug']}/index.html", self.files)

    def test_internal_links_resolve(self):
        known = set(self.files)
        for rel in self.files:
            if not rel.endswith("index.html"):
                continue
            for href in re.findall(r'href="(/[^"#?]*)', self.read(rel)):
                target = href.lstrip("/")
                ok = target == "" or target in known or (target.rstrip("/") + "/index.html") in known
                self.assertTrue(ok, f"{rel} links to {href}")

    def test_no_template_leftovers(self):
        for rel in self.files:
            if rel.endswith(".html"):
                html = self.read(rel)
                self.assertNotIn("{source}", html, rel)
                self.assertNotRegex(html, r"\{[a-z_]+\}", rel)
                self.assertNotIn("None", re.sub(r"<[^>]+>", " ", html), rel)

    def test_sitemap_matches_the_pages(self):
        locs = re.findall(r"<loc>([^<]+)</loc>", self.read("sitemap.xml"))
        self.assertEqual(len(locs), len([f for f in self.files if f.endswith("index.html")]))
        self.assertIn("https://kuma-sokuho.com/akita/", locs)

    def test_feed_is_valid_and_dated_by_the_ministry(self):
        root = ET.fromstring(self.read("feed.xml"))
        ns = "{http://www.w3.org/2005/Atom}"
        entries = root.findall(f"{ns}entry")
        self.assertEqual(len(entries), 6)  # three data updates and the three newest ministry notices
        self.assertEqual(len({e.findtext(f"{ns}id") for e in entries}), 6)
        days = [e.findtext(f"{ns}updated")[:10] for e in entries]
        self.assertEqual(days, ["2026-10-02", "2026-10-01", "2026-09-09", "2026-08-28", "2026-08-05", "2026-07-03"])  # the ministry's dates, not the build date
        links = [e.find(f"{ns}link").get("href") for e in entries]
        self.assertEqual(len(set(links)), 6)  # the Bluesky poster tells entries apart by link
        self.assertTrue(all(link.startswith("https://kuma-sokuho.com/") and link.count("#") == 1 for link in links))

    def test_news_page_lists_the_ministry_notices_with_their_links(self):
        html = self.read("news/index.html")
        self.assertIn("クマ被害対策等関係情報のお知らせ(令和8年8月28日追加)", html)
        self.assertIn("https://www.env.go.jp/nature/choju/effort/effort12/kuma-oshirase-r080828.pdf", html)
        self.assertEqual(html.count('rel="noopener" target="_blank">'), 12 + 2)  # twelve notices, the credit line and the footer credit
        self.assertIn("環境省の最近のお知らせ", self.read("index.html"))
        self.assertLess(html.index("2026年8月28日"), html.index("2026年7月3日"))  # newest first

    def test_release_is_indexable_and_preview_is_not(self):
        self.assertNotIn("noindex", self.read("index.html"))
        self.assertIn("Allow: /", self.read("robots.txt"))
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(self.raw, {**CFG, "operator_name": None}, Path(tmp) / "p")
            self.assertIn("noindex", (Path(tmp) / "p" / "index.html").read_text(encoding="utf-8"))
            self.assertIn("Disallow: /", (Path(tmp) / "p" / "robots.txt").read_text(encoding="utf-8"))

    def test_release_without_operator_info_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(BuildError):
            build.render_site(self.raw, {**CFG, "operator_name": None}, Path(tmp) / "x", release=True)

    def test_guides_have_sources_and_a_check_date(self):
        for g in content.GUIDES:
            self.assertTrue(g["sources"], g["slug"])
            self.assertTrue(all(u.startswith("https://") for _, u in g["sources"]))
        self.assertRegex(content.VERIFIED_AT, r"\d{4}-\d{2}-\d{2}")

    def test_guides_do_not_promise_effects(self):
        for g in content.GUIDES:
            self.assertNotRegex(g["body"], r"必ず(助か|守れ|撃退)|絶対に安全|100%")


OTSU = {
    "fetched_at": "2026-10-05T17:33:25+09:00",
    "official_counts": {"令和8年度": 3, "令和7年度": 45},
    "sightings": [
        {"fiscal_year": "令和8年度", "observed_at": "2026-09-11T07:30:00+09:00", "place": "南小松", "lat": 35.2, "lon": 135.9},
        {"fiscal_year": "令和8年度", "observed_at": "2026-10-03T08:30:00+09:00", "place": "北比良", "lat": 35.25, "lon": 135.93},
        {"fiscal_year": "令和8年度", "observed_at": "2026-10-03T06:00:00+09:00", "place": "伊香立下龍華町", "lat": 35.1, "lon": 135.8},
        {"fiscal_year": "令和7年度", "observed_at": "2025-10-20T00:00:00+09:00", "place": "仰木町", "lat": 35.1, "lon": 135.9},
    ],
}


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class LiveTest(unittest.TestCase):
    """Otsu City's own sighting list: newest first, with the city's page credited, on its own municipality page."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, otsu=OTSU, today=date(2026, 10, 5))
        cls.city = f"live/shiga/{live_mod.city_slug('shiga', '大津市')}/index.html"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_newest_first_and_the_latest_is_on_the_home_page(self):
        html = self.read("live/shiga/index.html")
        self.assertLess(html.index("北比良"), html.index("伊香立下龍華町"))
        self.assertLess(html.index("伊香立下龍華町"), html.index("南小松"))
        self.assertIn("最新の記録: 10月3日(2日前) 大津市北比良", self.read(self.city))  # fetched 2026-10-05, seen 2026-10-03
        self.assertIn("<li>10月3日 滋賀県大津市北比良<b>目撃</b></li>", self.read("index.html"))

    def test_the_city_page_is_linked_and_credited(self):
        html = self.read("live/shiga/index.html")
        self.assertIn("https://www.city.otsu.lg.jp/soshiki/025/1605/g/t/74581.html", html)
        self.assertIn("大津市が作成したものではありません", html)
        self.assertIn('href="/live/shiga/"', self.read("live/index.html"))

    def test_counts_are_ours_and_older_years_are_not_mixed_in(self):
        html = self.read(self.city)
        self.assertIn("令和8年度の記録は3件で、直近30日は3件", html)
        self.assertNotIn("仰木町", html)  # last fiscal year's sighting
        self.assertIn("<tr><td>2026年10月3日 8時30分ごろ</td>", html)
        month_table = html.split("大津市の月別の記録</h2>")[1].split("</table>")[0]
        self.assertEqual(re.findall(r"<td>(\d+)月</td><td>(\d+)</td>", month_table), [("9", "1"), ("10", "2")])

    def test_shiga_page_carries_the_live_block_and_other_prefectures_do_not(self):
        self.assertIn("大津市の最新の目撃情報(市の公式)", self.read("shiga/index.html"))
        self.assertIn('href="/live/shiga/"', self.read("shiga/index.html"))
        self.assertNotIn("大津市の最新の目撃情報", self.read("akita/index.html"))

    def test_nav_has_the_live_link_only_when_there_is_data(self):
        self.assertIn('href="/live/"', self.read("index.html"))
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "n", release=True, otsu=None)
            self.assertNotIn("live/index.html", files)
            self.assertNotIn("map/index.html", files)
            self.assertNotIn('href="/live/"', (Path(tmp) / "n" / "index.html").read_text(encoding="utf-8"))


class ChartTest(unittest.TestCase):
    def test_nice_max_and_gaps(self):
        self.assertEqual(charts.nice_max(216), 250)
        self.assertEqual(charts.nice_max(50801), 100000)
        svg = charts.lines([{"label": "a", "values": [1, None, 3], "cls": "c0"}], ["x", "y", "z"], title="t", desc="d")
        self.assertEqual(svg.count("<polyline"), 0)  # two isolated points: dots, no line
        self.assertEqual(svg.count("<circle"), 2)

    def test_axis_starts_at_zero_and_text_is_escaped(self):
        svg = charts.bars(["a<b"], [5], title="t&t", desc="d")
        self.assertIn("a&lt;b", svg)
        self.assertIn("t&amp;t", svg)
        self.assertIn(">0<", svg)


MIYAGI = {
    "source": "miyagi", "source_page": "https://www.pref.miyagi.jp/x.html", "as_of": "2026-10-05", "fy_current": "R08",
    "credit": "出典:宮城県「令和8年度クマ目撃等情報」を加工して作成", "update_note": "宮城県が更新します", "fetched_at": "2026-10-06T06:20:00+09:00",
    "dates_after_as_of": 1,
    "sightings": [
        {"observed_at": "2026-10-29T15:20:00+09:00", "city": "大衡村", "place": "駒場字上五仏", "count": 1, "kind": "目撃", "species": "クマ"},
        {"observed_at": "2026-10-05T07:40:00+09:00", "city": "大和町", "place": "松坂字銅山", "count": 1, "kind": "目撃", "species": "クマ"},
        {"observed_at": "2026-10-04T08:45:00+09:00", "city": "富谷市", "place": "石積字森", "count": 1, "kind": "痕跡", "species": "クマ"},
    ],
    "monthly": {"R08": {"9": 2, "10": 2}},
}
AKITA = {
    "source": "akita", "source_page": "https://ckan.pref.akita.lg.jp/dataset/x", "as_of": "2026-08-31", "fy_current": "R08",
    "credit": "出典:秋田県「クマダス」(秋田県オープンデータ、CC BY 4.0)を加工して作成", "update_note": "更新は月に1回ほどです",
    "fetched_at": "2026-10-06T06:20:00+09:00",
    "sightings": [
        {"observed_at": "2026-08-31T14:53:00+09:00", "city": "秋田市", "place": "秋田県秋田市寺内児桜２丁目１５", "count": 1, "kind": "痕跡(その他)", "species": "ツキノワグマ"},
        {"observed_at": "2026-08-31T13:30:00+09:00", "city": "鹿角市", "place": "秋田県鹿角市十和田大湯下川原", "count": 1, "kind": "目撃", "species": "ツキノワグマ"},
    ],
    "monthly": {"R08": {"7": 882, "8": 235}},
}


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class PrefLiveTest(unittest.TestCase):
    """Miyagi's and Akita's own published lists: credited, dated, and nothing after the prefecture's as-of date."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, CFG, cls.out, release=True, otsu=None, prefs={"miyagi": MIYAGI, "akita": AKITA}, today=date(2026, 10, 6))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_live_page_exists_without_otsu_and_lists_both_prefectures(self):
        html = self.read("live/index.html")
        self.assertIn("いまは、2か所(宮城県・秋田県)です", html)
        self.assertIn('href="/live/miyagi/"', html)
        self.assertIn('href="/live/akita/"', html)
        self.assertIn('href="/live/"', self.read("index.html"))

    def test_a_row_dated_after_the_as_of_date_is_not_listed_or_counted(self):
        for rel in ("live/index.html", "live/miyagi/index.html"):
            self.assertNotIn("駒場字上五仏", self.read(rel))
        html = self.read("live/miyagi/index.html")
        self.assertIn("日付が公表時点より後になっている記録が1件あります", html)
        self.assertIn("宮城県が公表している令和8年度の記録は、2件です", html)
        self.assertLess(html.index("松坂字銅山"), html.index("石積字森"))

    def test_credits_as_of_and_links(self):
        html = self.read("live/miyagi/index.html")
        self.assertIn("出典:宮城県「令和8年度クマ目撃等情報」を加工して作成。位置の座標は", html)
        self.assertIn("データは2026年10月5日時点です", html)
        self.assertIn("https://www.pref.miyagi.jp/x.html", html)
        akita = self.read("live/akita/index.html")
        self.assertIn("CC BY 4.0", akita)
        self.assertIn("最新の記録は2026年8月31日の分までです", akita)

    def test_akita_address_is_not_doubled_and_no_coordinates_are_printed(self):
        html = self.read("live/akita/index.html")
        self.assertIn("秋田県が公表している令和8年度の記録は、2件です", html)
        self.assertNotIn("秋田市秋田県秋田市", html)
        self.assertNotIn("lat", html.lower().split("<main")[1].split("</main>")[0])

    def test_home_alert_uses_the_latest_sighting_not_a_trace(self):
        home = self.read("index.html")
        self.assertIn("<li>10月5日 宮城県大和町松坂字銅山<b>目撃</b></li>", home)
        self.assertNotIn("石積字森", home)  # a trace is not a sighting
        self.assertNotIn("寺内児桜", home)  # Akita's newest row is a trace

    def test_prefecture_pages_carry_their_block(self):
        self.assertIn("宮城県が公表している最新の目撃情報", self.read("miyagi/index.html"))
        self.assertIn('href="/live/akita/"', self.read("akita/index.html"))
        self.assertNotIn("が公表している最新の目撃情報", self.read("iwate/index.html"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class DateOnlyTest(unittest.TestCase):
    """Okayama publishes dates without a time of day: the list must show the date alone."""

    def test_day_text_without_a_time(self):
        self.assertEqual(build.day_text("2026-09-06"), "9月6日")
        self.assertEqual(build.day_text("2026-09-06", year=True), "2026年9月6日")
        self.assertEqual(build.day_text("2026-09-06T07:05:00+09:00"), "9月6日 7時05分ごろ")

    def test_okayama_section_renders(self):
        okayama = {"source": "okayama", "source_page": "https://www.pref.okayama.jp/page/1006862.html", "as_of": "2026-09-06",
                   "fy_current": "R08", "credit": "出典:岡山県「岡山県ツキノワグマ出没情報」を加工して作成", "update_note": "岡山県が適宜更新します",
                   "fetched_at": "2026-10-06T06:20:00+09:00",
                   "sightings": [{"observed_at": "2026-09-06", "city": "新見市", "place": "哲西町大野部", "count": None, "kind": "目撃", "species": "ツキノワグマ"}],
                   "monthly": {"R08": {"9": 3}}}
        raw = raw_data()
        raw["notices"] = []
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(raw, CFG, Path(tmp) / "s", release=True, otsu=None, prefs={"okayama": okayama}, today=date(2026, 10, 6))
            html = (Path(tmp) / "s" / "live" / "okayama" / "index.html").read_text(encoding="utf-8")
            self.assertIn("<td>2026年9月6日</td><td>新見市哲西町大野部</td><td>目撃</td>", html)
            self.assertIn("岡山県が公表している令和8年度の記録は、1件です", html)
            home = (Path(tmp) / "s" / "index.html").read_text(encoding="utf-8")
            self.assertIn("<li>9月6日 岡山県新見市哲西町大野部<b>目撃</b></li>", home)


def _yamaguchi():
    """Rows with coordinates in three municipalities (a county prefix on one), one of them with fewer than MIN_CITY_ROWS rows."""
    def row(day, city, place, kind="目撃", lat=34.2, lon=131.6):
        return {"observed_at": day, "city": city, "place": place, "count": 1, "kind": kind, "species": "クマ", "lat": lat, "lon": lon}
    rows = [
        row("2026-10-06T09:30:00+09:00", "萩市", "大井 門前橋", lat=34.4, lon=131.4),
        row("2026-10-03T06:15:00+09:00", "岩国市", "美川町根笠", lat=34.2, lon=132.0),
        row("2026-09-30T09:07:00+09:00", "岩国市", "錦町広瀬", "痕跡", lat=34.3, lon=132.0),
        row("2026-09-20T17:40:00+09:00", "岩国市", "柱野", lat=34.1, lon=132.2),
        row("2026-09-15T18:00:00+09:00", "阿武郡阿武町", "大字奈古"),
        row("2026-06-01T08:00:00+09:00", "岩国市", "日付が古い(90日より前)"),
        row("2026-02-01T08:00:00+09:00", "岩国市", "前の年度の1月(別の年度)"),
    ]
    return {"source": "yamaguchi", "source_page": "https://yamaguchi-opendata.jp/x", "as_of": "2026-10-06", "fy_current": "R08",
            "credit": "出典:山口県警察のオープンデータ(CC BY)を加工して作成", "update_note": "県警が更新します",
            "fetched_at": "2026-10-07T06:20:00+09:00", "sightings": rows, "monthly": {"R08": {"6": 1, "9": 3, "10": 2}}}


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class LiveSectionTest(unittest.TestCase):
    """Prefecture and municipality pages, the feed and the map, built from one record list."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, otsu=None, prefs={"yamaguchi": _yamaguchi()}, today=date(2026, 10, 7))
        cls.iwakuni = f"live/yamaguchi/{live_mod.city_slug('yamaguchi', '岩国市')}/index.html"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_city_slug_is_stable_ascii_and_never_collides_within_a_prefecture(self):
        self.assertEqual(live_mod.city_slug("yamaguchi", "岩国市"), live_mod.city_slug("yamaguchi", "岩国市"))
        self.assertRegex(live_mod.city_slug("yamaguchi", "岩国市"), r"^m-[0-9a-f]{6}$")
        self.assertNotEqual(live_mod.city_slug("yamaguchi", "岩国市"), live_mod.city_slug("yamaguchi", "萩市"))
        self.assertNotEqual(live_mod.city_slug("yamaguchi", "岩国市"), live_mod.city_slug("okayama", "岩国市"))
        self.assertEqual(live_mod.city_slug("yamaguchi", "岩国市"), "m-" + __import__("hashlib").sha1("yamaguchi/岩国市".encode()).hexdigest()[:6])  # fixed: URLs must not change

    def test_only_cities_with_enough_rows_get_a_page_and_the_county_prefix_is_dropped(self):
        self.assertIn(self.iwakuni, self.files)
        self.assertNotIn(f"live/yamaguchi/{live_mod.city_slug('yamaguchi', '萩市')}/index.html", self.files)  # 1 row
        self.assertEqual(live_mod.norm_city("阿武郡阿武町"), "阿武町")
        pref = self.read("live/yamaguchi/index.html")
        self.assertIn("<td>阿武町</td>", pref)
        self.assertNotIn("阿武郡阿武町</td>", pref)
        self.assertNotIn(f'href="{live_mod.city_url("yamaguchi", "萩市")}"', pref)
        self.assertIn(f'href="{live_mod.city_url("yamaguchi", "岩国市")}"', pref)

    def test_city_page_counts_only_this_fiscal_year_and_lists_newest_first(self):
        html = self.read(self.iwakuni)
        self.assertIn("令和8年度の記録は4件で", html)  # the January row of the previous fiscal year is not counted
        self.assertNotIn("前の年度の1月", html)
        self.assertLess(html.index("美川町根笠"), html.index("錦町広瀬"))
        self.assertLess(html.index("錦町広瀬"), html.index("柱野"))
        self.assertIn("<h1>岩国市のクマの目撃情報(山口県・令和8年度)</h1>", html)
        self.assertIn("<title>岩国市のクマ出没・目撃情報(山口県・令和8年度・4件)</title>", html)

    def test_pages_state_what_the_numbers_are_not(self):
        html = self.read(self.iwakuni)
        self.assertIn("そのまま比べられません", html)
        self.assertIn("出典:山口県警察のオープンデータ(CC BY)を加工して作成", html)

    def test_feed_has_one_entry_per_row_newest_first_with_stable_ids(self):
        feed = ET.fromstring(self.read("live/feed.xml"))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = feed.findall("a:entry", ns)
        self.assertEqual(len(entries), 6)  # this fiscal year only
        self.assertIn("萩市大井 門前橋", entries[0].find("a:title", ns).text)
        ids = [e.find("a:id", ns).text for e in entries]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(feed.find("a:updated", ns).text, "2026-10-06T00:00:00+09:00")  # the newest record, so a rebuild does not re-announce

    def test_map_points_are_the_last_90_days_with_coordinates_and_prefectures_are_named(self):
        data = json.loads(self.read("map/points.json"))
        self.assertEqual(data["prefs"], {"yamaguchi": "山口県"})
        days = [p[2] for p in data["points"]]
        self.assertEqual(days, sorted(days, reverse=True))
        self.assertNotIn("2026-06-01", days)  # older than 90 days from the fetch date
        self.assertEqual(len(data["points"]), 5)
        lat, lon = data["points"][0][:2]
        self.assertEqual((lat, lon), (34.4, 131.4))
        self.assertIn("/assets/map.js", self.read("map/index.html"))

    def test_the_csv_holds_the_licensed_rows_with_their_terms_and_the_data_page_describes_it(self):
        raw = self.read("data/kuma-sightings.csv")
        self.assertTrue(raw.startswith(chr(0xFEFF) + "取得元,ライセンス・利用条件,都道府県,市町村,場所,日時,種別,頭数,緯度,経度"))
        rows = list(csv.reader(io.StringIO(raw.lstrip(chr(0xFEFF)))))
        self.assertEqual(len(rows), 1 + 6)  # the six rows of this fiscal year; the previous January is not in it
        self.assertEqual(rows[1][:7], ["山口県", "CC BY", "山口県", "萩市", "大井 門前橋", "2026-10-06T09:30:00+09:00", "目撃"])
        self.assertIn("阿武町", {r[3] for r in rows[1:]})  # the county prefix is dropped
        page = self.read("data/index.html")
        self.assertIn("6件", page)
        self.assertIn(">CSVをダウンロード(6件)<", page)
        self.assertIn('href="/data/kuma-sightings.csv"', page)

    def test_a_source_without_stated_terms_is_not_offered_for_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "o", release=True, otsu=OTSU, today=date(2026, 10, 5))
            self.assertNotIn("data/index.html", files)
            self.assertNotIn("data/kuma-sightings.csv", files)
        self.assertEqual(live_mod.LIVE_SOURCES["yamaguchi"]["license"], "CC BY")

    def test_the_built_site_passes_the_site_checker(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])


class LiveHelpersTest(unittest.TestCase):
    def test_fiscal_year_boundaries(self):
        self.assertEqual(live_mod.fy_of("2026-04-01"), "R08")
        self.assertEqual(live_mod.fy_of("2026-03-31T23:00:00+09:00"), "R07")
        self.assertEqual(live_mod.fy_of("2027-01-15"), "R08")

    def test_county_prefix_is_dropped_only_for_towns_and_villages(self):
        self.assertEqual(live_mod.norm_city("上北郡七戸町"), "七戸町")
        self.assertEqual(live_mod.norm_city("郡山市"), "郡山市")
        self.assertEqual(live_mod.norm_city("仙台市青葉区"), "仙台市青葉区")
        self.assertEqual(live_mod.norm_city("北秋田市"), "北秋田市")


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class GoodsTest(unittest.TestCase):
    """Affiliate goods page: PR-labelled, sponsored links, the disclosure sentences, absent without IDs."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = {**CFG, "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444", "rakuten_tracking_id": "kuma-top",
               "amazon_tracking_id": "amazonmacs-22"}
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, cfg, cls.out, release=True)
        cls.cfg = cfg

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_links_carry_the_ids_and_are_marked_sponsored(self):
        html = self.read("goods/index.html")
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/kuma-top?pc=", html)
        self.assertIn("https://www.amazon.co.jp/s?k=%E3%82%AF%E3%83%9E%E9%88%B4&amp;tag=amazonmacs-22", html)
        self.assertEqual(html.count('rel="sponsored nofollow noopener"'), 12)  # six goods x two shops
        self.assertEqual(html.count("楽天市場で探す"), 6)
        self.assertEqual(html.count("Amazonで探す"), 6)

    def test_disclosures(self):
        self.assertIn("Amazonのアソシエイトとして、クマ出没速報は適格販売により収入を得ています。", self.read("goods/index.html"))
        self.assertIn("Amazonのアソシエイトとして、クマ出没速報は適格販売により収入を得ています。", self.read("privacy/index.html"))
        self.assertIn("効果も保証しません", self.read("goods/index.html"))

    def test_nav_has_the_goods_link_and_a_site_without_ids_has_no_goods_page(self):
        self.assertIn('href="/goods/"', self.read("index.html"))
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "n", release=True)
            self.assertNotIn("goods/index.html", files)
            self.assertNotIn("Amazonのアソシエイト", (Path(tmp) / "n" / "privacy" / "index.html").read_text(encoding="utf-8"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class SourceKeyIsNotThePrefectureTest(unittest.TestCase):
    """A source named after its region (the Sorachi bureau) shows up under its prefecture (Hokkaido) everywhere."""

    @classmethod
    def setUpClass(cls):
        from sokuhou.sources import sorachi_kuma
        cls.tmp = tempfile.TemporaryDirectory()
        raw = raw_data()
        raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        sorachi = sorachi_kuma.parse_page((FIX / "sorachi_kuma.html").read_bytes())
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(raw, CFG, cls.out, release=True, prefs={"sorachi": sorachi}, today=date(2026, 10, 7))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_pages_are_under_the_prefecture_slug(self):
        self.assertIn("live/hokkaido/index.html", self.files)
        self.assertNotIn("live/sorachi/index.html", self.files)
        self.assertIn("live/hokkaido/feed.xml", self.files)

    def test_the_prefecture_page_of_the_ministry_links_to_it(self):
        html = self.read("hokkaido/index.html")
        self.assertIn('href="/live/hokkaido/"', html)
        self.assertIn("北海道空知総合振興局が公表している最新の目撃情報", html)

    def test_the_municipality_pages_exist_and_the_site_checker_passes(self):
        self.assertIn(f"live/hokkaido/{live_mod.city_slug('hokkaido', '砂川市')}/index.html", self.files)
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])
        self.assertIn("空知総合振興局", self.read("live/hokkaido/index.html"))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class CapturesPagesTest(unittest.TestCase):
    """The ministry's permitted-captures table: a ranking page, a block on each prefecture page, the feed, and nothing when there is no data."""

    @classmethod
    def setUpClass(cls):
        from sokuhou.sources import env_capture_kuma
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = raw_data()
        cls.raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.caps = env_capture_kuma.parse_captures((FIX / "env_kuma_capture.pdf").read_bytes())
        cls.caps["source_page"] = "https://www.env.go.jp/nature/choju/effort/effort12/effort12.html"
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, captures=cls.caps)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_ranking_page_numbers_and_year_names(self):
        html = self.read("ranking/captures/index.html")
        self.assertIn("令和7年度の全国のクマ類の許可捕獲数は14,741頭で、秋田県が2,691頭で最も多く", html)
        self.assertIn("<tr><td>平成20年度</td><td>1,492</td>", html)  # a Heisei year is not called Reiwa 20
        self.assertNotIn("令和20年度", html)
        self.assertIn("令和8年度(暫定)", html)
        self.assertIn("令和8年7月末まで", html)
        first = html.split("道府県別(令和7年度の多い順)")[1].split("</tr>")[1]
        self.assertIn("秋田県", first)

    def test_ties_share_a_rank(self):
        html = self.read("ranking/captures/index.html")
        self.assertEqual(html.count("<tr><td>28</td>"), 3)  # Nara, Okayama and Shiga all have 2

    def test_tab_and_home_link_exist_only_with_data(self):
        self.assertIn('href="/ranking/captures/"', self.read("ranking/sightings/index.html"))
        self.assertIn('href="/ranking/captures/"', self.read("index.html"))
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "n", release=True)
            self.assertNotIn("ranking/captures/index.html", files)
            self.assertNotIn("ranking/captures", (Path(tmp) / "n" / "ranking" / "sightings" / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn("許可捕獲数", (Path(tmp) / "n" / "akita" / "index.html").read_text(encoding="utf-8"))

    def test_prefecture_block_with_its_rank_and_an_unlisted_prefecture(self):
        akita = self.read("akita/index.html")
        self.assertIn("令和7年度の許可捕獲数は、2,691頭(捕殺2,691頭・非捕殺0頭)で、36道府県中1位でした", akita)
        self.assertIn("令和8年度は、令和8年7月末までで252頭です", akita)
        kochi = self.read("kochi/index.html")
        self.assertIn("環境省の許可捕獲数の表には、高知県は載っていません", kochi)
        self.assertIn("環境省の許可捕獲数の表には、愛媛県は載っていません", self.read("ehime/index.html"))

    def test_feed_announces_the_update_by_the_ministrys_date(self):
        feed = self.read("feed.xml")
        self.assertIn("クマの許可捕獲数を、令和8年7月末まで更新しました(環境省)", feed)
        self.assertIn("<updated>2026-09-09T00:00:00+09:00</updated>", feed)

    def test_the_site_checker_passes(self):
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])


if __name__ == "__main__":
    unittest.main()
