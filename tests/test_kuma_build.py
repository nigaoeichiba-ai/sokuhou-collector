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
        self.assertEqual(len(entries), 3)
        self.assertEqual(len({e.findtext(f"{ns}id") for e in entries}), 3)
        days = [e.findtext(f"{ns}updated")[:10] for e in entries]
        self.assertEqual(days, ["2026-10-02", "2026-10-01", "2026-09-09"])  # the ministry's dates, not the build date
        links = [e.find(f"{ns}link").get("href") for e in entries]
        self.assertEqual(len(set(links)), 3)  # the Bluesky poster tells entries apart by link
        self.assertTrue(all(link.startswith("https://kuma-sokuho.com/") and "#u-" in link for link in links))

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
