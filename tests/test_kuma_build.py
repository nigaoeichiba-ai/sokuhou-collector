"""The bear site: built from the ministry's PDFs (the test fixtures), checked against numbers from outside the code."""
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import pypdf  # noqa: F401
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False

from sites.kuma import build, charts, content
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
    """Otsu City's own sighting list, shown newest first, with the city's page and map credited."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, otsu=OTSU)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_newest_first_and_the_latest_is_on_the_home_page(self):
        html = self.read("live/index.html")
        self.assertLess(html.index("北比良"), html.index("伊香立下龍華町"))
        self.assertLess(html.index("伊香立下龍華町"), html.index("南小松"))
        self.assertIn("最新の目撃: 10月3日(2日前) 北比良", html)  # fetched 2026-10-05, seen 2026-10-03
        self.assertIn("最新の目撃(滋賀県大津市・市の公式): 10月3日 北比良", self.read("index.html"))

    def test_the_city_page_and_map_are_linked_and_credited(self):
        html = self.read("live/index.html")
        self.assertIn("https://www.city.otsu.lg.jp/soshiki/025/1605/g/t/74581.html", html)
        self.assertIn("https://www.google.com/maps/d/viewer?mid=1rE5HcSdJnm2gX3iT1FMt0aCVuQ9ArDs", html)
        self.assertIn("大津市が作成したものではありません", html)

    def test_counts_are_the_citys_and_ours_and_older_years_are_not_mixed_in(self):
        html = self.read("live/index.html")
        self.assertIn("大津市は、令和8年度の目撃情報を3件と公表しています", html)
        self.assertIn("読み取った令和8年度の件数は、3件です", html)
        self.assertIn("<td>2025年10月20日</td><td>仰木町</td>", html)  # last year's sighting carries its year in the list
        self.assertIn("<tr><td>2026年10月3日 8時30分ごろ</td>", html)
        month_table = html.split("令和8年度の月別</h2>")[1].split("</table>")[0]
        self.assertEqual(re.findall(r"<td>(\d+)月</td><td>(\d+)</td>", month_table), [("9", "1"), ("10", "2")])  # this year only

    def test_shiga_page_carries_the_live_block_and_other_prefectures_do_not(self):
        self.assertIn("大津市の最新の目撃情報(市の公式)", self.read("shiga/index.html"))
        self.assertNotIn("大津市の最新の目撃情報", self.read("akita/index.html"))

    def test_nav_has_the_live_link_only_when_there_is_data(self):
        self.assertIn('href="/live/"', self.read("index.html"))
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "n", release=True, otsu=None)
            self.assertNotIn("live/index.html", files)
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


if __name__ == "__main__":
    unittest.main()


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
    """Miyagi's and Akita's own published lists on the live page: credited, dated, and nothing after the prefecture's as-of date."""

    @classmethod
    def setUpClass(cls):
        cls.raw = raw_data()
        cls.raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.raw, CFG, cls.out, release=True, otsu=None, prefs={"miyagi": MIYAGI, "akita": AKITA})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_live_page_exists_without_otsu_and_lists_both_prefectures(self):
        html = self.read("live/index.html")
        self.assertIn("いまは、宮城県・秋田県です", html)
        self.assertIn('href="/live/"', self.read("index.html"))

    def test_a_row_dated_after_the_as_of_date_is_not_listed_but_the_monthly_total_keeps_the_prefectures_figure(self):
        html = self.read("live/index.html")
        self.assertNotIn("駒場字上五仏", html)
        self.assertIn("日付が公表時点より後になっている記録が1件あります", html)
        self.assertIn("宮城県が公表している令和8年度の記録は、4件です", html)  # 2 + 2 from the monthly table, as published
        self.assertLess(html.index("松坂字銅山"), html.index("石積字森"))

    def test_credits_as_of_and_links(self):
        html = self.read("live/index.html")
        self.assertIn("出典:宮城県「令和8年度クマ目撃等情報」を加工して作成。宮城県が作成したものではありません", html)
        self.assertIn("CC BY 4.0", html)
        self.assertIn("データは2026年10月5日時点です", html)
        self.assertIn("最新の記録は2026年8月31日の分までです", html)
        self.assertIn("https://www.pref.miyagi.jp/x.html", html)

    def test_akita_counts_are_sightings_only_and_the_address_is_not_doubled(self):
        html = self.read("live/index.html")
        self.assertIn("秋田県が公表している令和8年度の記録は、1,117件です(目撃のみ", html)  # 882 + 235
        self.assertNotIn("秋田市秋田県秋田市", html)
        self.assertNotIn("lat", html.split("秋田県</h2>")[1].lower().split("</table>")[0])  # no coordinates

    def test_home_alert_uses_the_latest_sighting_not_a_trace(self):
        home = self.read("index.html")
        self.assertIn("最新の目撃(宮城県・県の公式): 10月5日 大和町松坂字銅山", home)
        self.assertIn("最新の目撃(秋田県・県の公式。更新は月1回ほど): 8月31日 秋田県鹿角市十和田大湯下川原", home)  # the 14:53 row is a trace

    def test_prefecture_pages_carry_their_block(self):
        self.assertIn("宮城県が公表している最新の目撃情報", self.read("miyagi/index.html"))
        self.assertIn("秋田県が公表している最新の目撃情報", self.read("akita/index.html"))
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
            build.render_site(raw, CFG, Path(tmp) / "s", release=True, otsu=None, prefs={"okayama": okayama})
            html = (Path(tmp) / "s" / "live" / "index.html").read_text(encoding="utf-8")
            self.assertIn("<td>2026年9月6日</td><td>新見市哲西町大野部</td><td>目撃</td>", html)
            self.assertIn("岡山県が公表している令和8年度の記録は、3件です", html)
            home = (Path(tmp) / "s" / "index.html").read_text(encoding="utf-8")
            self.assertIn("最新の目撃(岡山県・県の公式。更新は不定期): 9月6日 新見市哲西町大野部", home)


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
        self.assertIn("Amazonのアソシエイトとして、テスト運営は適格販売により収入を得ています。", self.read("goods/index.html"))
        self.assertIn("Amazonのアソシエイトとして、テスト運営は適格販売により収入を得ています。", self.read("privacy/index.html"))
        self.assertIn("効果も保証しません", self.read("goods/index.html"))

    def test_nav_has_the_goods_link_and_a_site_without_ids_has_no_goods_page(self):
        self.assertIn('href="/goods/"', self.read("index.html"))
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(self.raw, CFG, Path(tmp) / "n", release=True)
            self.assertNotIn("goods/index.html", files)
            self.assertNotIn("Amazonのアソシエイト", (Path(tmp) / "n" / "privacy" / "index.html").read_text(encoding="utf-8"))
