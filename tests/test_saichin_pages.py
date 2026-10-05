"""Tests for the redesigned site: new page types, link integrity, guide sources and chart output."""
import re
import tempfile
import unittest
from pathlib import Path

from sites.saichin import build, charts, content
from sokuhou.sources import mhlw_minwage

FIXTURE = Path(__file__).parent / "fixtures" / "mhlw_minwage_history.xlsx"
CFG = {"site_url": "https://saichin-sokuho.com", "site_name": "最低賃金速報", "operator_name": "テスト運営",
       "contact_form_url": "https://forms.example.com/x", "contact_email": None, "adsense_pub_id": None}


def _raw():
    raw = mhlw_minwage.parse_xlsx(FIXTURE.read_bytes())
    raw.update({"source_page": mhlw_minwage.PAGE, "source_file": "x.xlsx", "fetched_at": "2026-10-05T17:00:00+09:00"})
    return raw


class SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(_raw(), CFG, cls.out, release=True)
        cls.d = build.prepare(_raw())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def amounts(self):
        return {r["short"]: r for r in self.d["rows"]}

    # ---- integrity
    def test_every_internal_link_resolves(self):
        broken = []
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            for href in re.findall(r'href="(/[^"#?]*)"', self.read(rel)):
                target = self.out / href.lstrip("/")
                if not (target.is_file() or (target / "index.html").is_file()):
                    broken.append((rel, href))
        self.assertEqual(broken, [])

    def test_every_page_has_exactly_one_h1_title_description_and_canonical(self):
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            text = self.read(rel)
            self.assertEqual(text.count("<h1"), 1, rel)
            self.assertRegex(text, r"<title>[^<]{6,}</title>", rel)
            if rel != "404.html":  # the 404 page is not indexed
                self.assertRegex(text, r'<meta name="description" content="[^"]{20,}"', rel)
                self.assertIn('<link rel="canonical"', text, rel)

    def test_assets_are_loaded_with_a_content_version(self):
        ver = build.asset_version()
        self.assertRegex(ver, r"^[0-9a-f]{8}$")
        for rel in ("index.html", "shiga/index.html", "guide/calculate/index.html"):
            text = self.read(rel)
            self.assertIn(f'/assets/style.css?v={ver}', text, rel)
            self.assertIn(f'/assets/app.js?v={ver}', text, rel)
        # legal pages load no script, but still version the stylesheet
        self.assertIn(f'/assets/style.css?v={ver}', self.read("about/index.html"))
        self.assertNotIn("app.js", self.read("about/index.html"))

    def test_titles_are_unique(self):
        titles = [re.search(r"<title>(.*?)</title>", self.read(r)).group(1) for r in self.files if r.endswith(".html")]
        self.assertEqual(len(titles), len(set(titles)))

    # ---- footer / nav (operator, privacy, contact are small and at the bottom)
    def test_legal_links_are_in_the_footer_only(self):
        text = self.read("index.html")
        header = re.search(r"<header.*?</header>", text, re.S).group(0)
        footer = re.search(r"<footer.*?</footer>", text, re.S).group(0)
        for href in ("/about/", "/privacy/", "/contact/"):
            self.assertNotIn(href, header)
            self.assertIn(href, footer)

    def test_current_section_is_marked_in_the_nav(self):
        self.assertRegex(self.read("area/kanto/index.html"), r'<a href="/area/" aria-current=\'page\'>地方別</a>')
        self.assertRegex(self.read("ranking/low/index.html"), r"aria-current='page'>ランキング</a>")
        index = self.read("index.html")
        self.assertEqual(index.count("aria-current"), 1)

    # ---- regions
    def test_regions_cover_every_prefecture_once(self):
        shorts = [p for _, _, ps in build.REGIONS for p in ps]
        self.assertEqual(sorted(shorts), sorted(mhlw_minwage.PREFECTURES))
        self.assertEqual(len(shorts), len(set(shorts)))

    def test_area_page_lists_its_members_and_the_right_extremes(self):
        text = self.read("area/kinki/index.html")
        members = [r for r in self.d["rows"] if r["region_slug"] == "kinki"]
        self.assertEqual(len(members), 7)
        for r in members:
            self.assertIn(f'href="/{r["slug"]}/"', text)
        top = max(members, key=lambda r: r["amount"])
        self.assertIn(f"最も高いのは{top['name']}", text)

    # ---- rankings
    def test_rankings_are_ordered_and_share_ranks_for_ties(self):
        high = self.read("ranking/high/index.html")
        low = self.read("ranking/low/index.html")
        raise_ = self.read("ranking/raise/index.html")
        first_name = lambda t: re.search(r'<td class="rk">\d+</td><td><a href="/[a-z]+/">([^<]+)</a>', t).group(1)  # noqa: E731
        self.assertEqual(first_name(high), "東京都")
        self.assertEqual(first_name(low), "宮崎県")
        biggest = max(self.d["rows"], key=lambda r: (r["raise"], -ord(r["name"][0])))
        self.assertEqual(first_name(raise_), sorted((r for r in self.d["rows"] if r["raise"] == biggest["raise"]), key=lambda r: r["name"])[0]["name"])
        ranks = [int(x) for x in re.findall(r'<td class="rk">(\d+)</td>', high)]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(len(ranks), 47)
        self.assertEqual(ranks.count(1), 1)

    def test_every_ranking_lists_all_47(self):
        for kind in build.RANKINGS:
            self.assertEqual(self.read(f"ranking/{kind}/index.html").count('<td class="rk">'), 47)

    # ---- calendar
    def test_calendar_has_every_prefecture_once_and_dates_in_order(self):
        text = self.read("calendar/index.html")
        days = re.findall(r'<section class="cal-day" data-date="(\d{4}-\d{2}-\d{2})"', text)
        self.assertEqual(days, sorted(days))
        self.assertEqual(len(days), len({r["effective_date"] for r in self.d["rows"]}))
        links = re.findall(r'<li><a href="/([a-z]+)/">', text)
        self.assertEqual(sorted(links), sorted(r["slug"] for r in self.d["rows"]))
        self.assertIn("10月1日(木)", text)  # 2026-10-01 is a Thursday

    # ---- history
    def test_history_page(self):
        text = self.read("history/index.html")
        self.assertEqual(len(re.findall(r"<tr><td>(?:平成|令和)", text)), 25)
        self.assertIn("平成14年度", text)
        self.assertIn("令和元年度", text)
        self.assertIn("1,177円", text)
        self.assertIn("<svg", text)
        self.assertIn("グラフの縦軸は0から始まっていません", text)

    # ---- guides
    def test_every_guide_has_sources_and_a_verification_date(self):
        for g in content.GUIDES:
            self.assertTrue(g["sources"], g["slug"])
            self.assertTrue(all(u.startswith("https://") for _, u in g["sources"]), g["slug"])
        self.assertRegex(content.VERIFIED_AT, r"^\d{4}-\d{2}-\d{2}$")

    def test_guide_pages_show_their_sources_and_date(self):
        for g in content.GUIDES:
            text = self.read(f"guide/{g['slug']}/index.html")
            for _, url in g["sources"]:
                self.assertIn(url, text, g["slug"])
            self.assertIn("内容の確認日", text)

    def test_guide_facts_match_the_verified_sources(self):
        body = " ".join(g["body"] for g in content.GUIDES)
        for needle in ("50万円以下の罰金", "30万円以下の罰金", "第4条", "30日", "精皆勤手当、通勤手当、家族手当",
                       "月給 ÷ 1か月平均所定労働時間", "賞与"):
            self.assertIn(needle, body)

    def test_the_calculator_exists_only_on_the_calculate_guide(self):
        for g in content.GUIDES:
            text = self.read(f"guide/{g['slug']}/index.html")
            self.assertEqual('id="calc"' in text, g["slug"] == "calculate", g["slug"])
        self.assertIn('id="data"', self.read("guide/calculate/index.html"))

    def test_the_worked_example_is_arithmetically_right(self):
        self.assertAlmostEqual(180000 / (2000 / 12), 1080.0)
        self.assertIn("1,080円", content.GUIDE_BY_SLUG["calculate"]["body"])

    # ---- prefecture pages
    def test_prefecture_page_has_chart_breadcrumb_and_region_mates(self):
        text = self.read("shiga/index.html")
        self.assertIn('<svg class="chart"', text)
        self.assertIn('href="/area/kinki/"', text)
        self.assertIn("同じ地方(近畿)の最低賃金", text)
        self.assertNotIn('href="/shiga/"', re.search(r"同じ地方.*?</ul>", text, re.S).group(0))  # not listed as its own neighbour

    def test_the_lead_sentence_is_timeless(self):
        text = self.read("shiga/index.html")
        self.assertIn("に改定され、発効日は2026年10月3日です", text)
        self.assertNotIn("改定されます", text)

    def test_hero_and_cards_on_the_front_page(self):
        text = self.read("index.html")
        self.assertIn('class="big"', text)
        self.assertEqual(text.count('class="pref-card"'), 47)
        self.assertEqual(text.count('<section class="region"'), 7)
        self.assertIn("全国加重平均", text)
        self.assertNotIn("発効済み</span>", text)  # state labels are filled by script, never baked in


class VerificationFileTest(unittest.TestCase):
    def _render(self, value):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "s"
        files = build.render_site(_raw(), {**CFG, "google_site_verification": value}, out, release=True)
        return out, files

    def test_verification_file_is_written_with_google_content(self):
        out, files = self._render("googleabcac004d8b7d556.html")
        self.assertIn("googleabcac004d8b7d556.html", files)
        self.assertEqual((out / "googleabcac004d8b7d556.html").read_text(encoding="utf-8"),
                         "google-site-verification: googleabcac004d8b7d556.html\n")

    def test_no_file_when_not_configured(self):
        _, files = self._render(None)
        self.assertFalse([f for f in files if f.startswith("google")])

    def test_a_malformed_name_is_refused(self):
        for bad in ("../evil.html", "google123.html", "googleabcac004d8b7d556.php"):
            with self.assertRaises(build.BuildError):
                self._render(bad)

    def test_the_verification_file_is_not_in_the_sitemap(self):
        out, _ = self._render("googleabcac004d8b7d556.html")
        self.assertNotIn("googleabcac", (out / "sitemap.xml").read_text(encoding="utf-8"))


class ChartTest(unittest.TestCase):
    def test_line_chart_is_accessible_and_scaled(self):
        svg = charts.line([("A", 100), ("B", 120), ("C", 150)], title="T<>", desc="D")
        self.assertIn('role="img"', svg)
        self.assertIn("<title", svg)
        self.assertIn("T&lt;&gt;", svg)  # escaped
        self.assertEqual(svg.count("<circle"), 3)
        ys = [float(v) for v in re.findall(r'<circle[^>]* cy="([\d.]+)"', svg)]
        self.assertGreater(ys[0], ys[1])
        self.assertGreater(ys[1], ys[2])  # larger values are drawn higher (smaller y)
        self.assertNotIn("nan", svg.lower())

    def test_flat_series_does_not_divide_by_zero(self):
        svg = charts.line([("A", 100), ("B", 100)], title="t", desc="d")
        self.assertNotIn("nan", svg.lower())
        self.assertNotIn("inf", svg.lower())

    def test_too_few_points_returns_nothing(self):
        self.assertEqual(charts.line([("A", 1)], title="t", desc="d"), "")


if __name__ == "__main__":
    unittest.main()
