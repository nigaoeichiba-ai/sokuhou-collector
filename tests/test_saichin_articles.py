"""The three articles (/guide/r8/, /guide/monthly/, /guide/city/): numbers recomputed from the workbook fixture, and the official figures they quote checked against it."""
import re

from sites.saichin import articles, build, content
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401


def cells(page, after):
    section = page.split(after, 1)[1]
    table = re.search(r"<table>.*?</table>", section, re.S).group(0)
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[dh]>(.*?)</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S)]


class R8ArticleTest(SiteFixture):
    def raw_raises(self):
        return {p["name"]: p["history"]["2026"]["amount"] - p["history"]["2025"]["amount"] for p in _raw()["prefectures"]}

    def test_the_ministrys_count_of_decided_raises_matches_the_workbook(self):
        """The press release of 2026-09-03 counts the 47 raises (54 to 65 yen); the workbook must give the same distribution."""
        dist = {}
        for v in self.raw_raises().values():
            dist[v] = dist.get(v, 0) + 1
        self.assertEqual(dist, articles.DECIDED_DISTRIBUTION)
        self.assertEqual(sum(articles.DECIDED_DISTRIBUTION.values()), 47)

    def test_the_ranks_cover_every_prefecture_once_with_the_counts_of_the_press_release(self):
        names = [s for shorts, _ in articles.RANKS.values() for s in shorts]
        self.assertEqual(sorted(names), sorted(build.SLUGS))
        self.assertEqual({rk: len(shorts) for rk, (shorts, _) in articles.RANKS.items()}, {"A": 6, "B": 28, "C": 13})
        self.assertEqual({rk: amount for rk, (_, amount) in articles.RANKS.items()}, {"A": 54, "B": 56, "C": 56})

    def test_every_row_is_the_raise_minus_the_guideline_of_its_rank(self):
        page = self.read("guide/r8/index.html")
        rows = cells(page, "<h2>目安より何円上がったか(47都道府県)</h2>")[1:]
        self.assertEqual(len(rows), 47)
        raises = self.raw_raises()
        diffs = []
        for name, rank, guide, got, diff, amount, date in rows:
            short = next(s for s in raises if name.startswith(s))
            guideline = articles.GUIDELINE[articles.RANK_OF[short]]
            self.assertEqual(rank, articles.RANK_OF[short], name)
            self.assertEqual(guide, f"+{guideline}円", name)
            self.assertEqual(got, f"+{raises[short]}円", name)
            d = raises[short] - guideline
            self.assertEqual(diff, f"+{d}円" if d > 0 else ("同じ" if d == 0 else f"{d}円"), name)
            diffs.append(d)
        self.assertEqual(diffs, sorted(diffs, reverse=True))

    def test_the_lead_counts_above_equal_and_below_and_names_the_biggest(self):
        raises = self.raw_raises()
        gl = {s: articles.GUIDELINE[articles.RANK_OF[s]] for s in raises}
        above = sum(1 for s in raises if raises[s] > gl[s])
        same = sum(1 for s in raises if raises[s] == gl[s])
        below = sum(1 for s in raises if raises[s] < gl[s])
        page = self.read("guide/r8/index.html")
        self.assertIn(f"国の目安を上回った都道府県は{above}、同じは{same}、下回ったのは{below}です", page)
        self.assertEqual((above, same, below), (33, 14, 0))
        self.assertIn("最も上乗せが大きかったのは佐賀県で、目安より9円多い+65円です", page)
        self.assertIn("引上げ額は+54円から+65円で", page)

    def test_the_process_and_the_official_figures_are_those_of_the_two_press_releases(self):
        page = self.read("guide/r8/index.html")
        for needle in ("第74回中央最低賃金審議会", "第75回中央最低賃金審議会", "Aランクが54円、Bランクが56円、Cランクが56円", "1,176円(+55円、4.9%)",
                       "全国加重平均は1,177円(+56円)で、目安制度が始まった昭和53年度以降で2番目の大きさです",
                       "7月28日", "9月3日", "10月1日〜12月2日"):
            self.assertIn(needle, page, needle)
        g = content.GUIDE_BY_SLUG["r8"]
        for _, url in g["sources"]:
            self.assertIn(url, page)
        self.assertIn("https://www.mhlw.go.jp/stf/newpage_74920.html", [u for _, u in g["sources"]])
        self.assertIn("https://www.mhlw.go.jp/stf/newpage_75950.html", [u for _, u in g["sources"]])

    def test_the_distribution_table_has_the_twelve_amounts(self):
        rows = cells(self.read("guide/r8/index.html"), "<h2>引上げ額の分布</h2>")[1:]
        self.assertEqual({int(a[1:-1]): int(n) for a, n in rows}, articles.DECIDED_DISTRIBUTION)


class MonthlyArticleTest(SiteFixture):
    def test_every_row_is_recomputed(self):
        raw = _raw()
        am = {p["name"] + build.SUFFIX.get(p["name"], "県"): p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        rows = cells(self.read("guide/monthly/index.html"), "<h2>47都道府県の月給換算の早見表</h2>")[1:]
        self.assertEqual(len(rows), 47)
        self.assertEqual([r[0] for r in rows], [n for n, _ in sorted(am.items(), key=lambda t: (-t[1], t[0]))])
        for name, w, day, m40, m30, m20, low in rows:
            a = am[name]
            self.assertEqual(w, f"{a:,}円", name)
            self.assertEqual(day, f"{a * 8:,}円", name)
            self.assertEqual(m40, f"{round(a * 40 * 52 / 12 / 100) * 100:,}円", name)
            self.assertEqual(m30, f"{round(a * 30 * 52 / 12 / 100) * 100:,}円", name)
            self.assertEqual(m20, f"{round(a * 20 * 52 / 12 / 100) * 100:,}円", name)
            self.assertEqual(low, f"{-(-(a * 2000) // 1200) * 100:,}円", name)         # monthly pay for 2000 hours a year, rounded up to 100 yen
            self.assertGreaterEqual(int(low.replace(",", "").replace("円", "")) / (2000 / 12), a, name)    # never below the minimum wage

    def test_the_worked_examples(self):
        page = self.read("guide/monthly/index.html")
        self.assertIn("200,000 ÷ 166.7 ≒ 1,200円で、最低賃金を下回ります", page)           # Tokyo 1,280
        self.assertIn("200,000 ÷ 140 ≒ 1,429円", page)
        self.assertAlmostEqual(200000 / 140, 1428.57, places=1)
        self.assertLess(200000 / (2000 / 12), 1280)
        self.assertIn("東京都(最低賃金1,280円)", page)

    def test_the_two_ends_in_the_lead(self):
        raw = _raw()
        am = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        lo, hi = min(am.values()), max(am.values())
        page = self.read("guide/monthly/index.html")
        self.assertIn(f"宮崎県で{-(-(lo * 2000) // 1200) * 100:,}円、東京都で{-(-(hi * 2000) // 1200) * 100:,}円を下回ると", page)


class CityArticleTest(SiteFixture):
    def test_each_city_shows_the_amount_of_its_prefecture(self):
        raw = _raw()
        am = {p["name"]: (p["history"]["2026"]["amount"], p["history"]["2026"]["effective_date"]) for p in raw["prefectures"]}
        rows = cells(self.read("guide/city/index.html"), "<h2>主な市と、適用される最低賃金</h2>")[1:]
        self.assertEqual(len(rows), len(articles.CITIES))
        self.assertEqual(len({r[0] for r in rows}), len(rows))
        for city, pref, amount, _date in rows:
            short = next(s for s in am if pref.startswith(s))
            self.assertEqual(amount, f"{am[short][0]:,}円", city)
        want = {"大阪市": "大阪府", "札幌市": "北海道", "福岡市": "福岡県", "宇治市": "京都府", "尼崎市": "兵庫県", "横浜市": "神奈川県", "那覇市": "沖縄県"}
        got = {r[0]: r[1] for r in rows}
        for city, pref in want.items():
            self.assertEqual(got[city], pref, city)

    def test_the_rules_it_states_are_the_cited_pages(self):
        page = self.read("guide/city/index.html")
        for needle in ("都道府県ごとに1つずつ定められていて", "派遣先の事業場がある都道府県です", "最も高い額が適用されます(最低賃金法第6条第1項)"):
            self.assertIn(needle, page)


class ThreeArticlesTest(SiteFixture):
    def test_linked_from_the_hub_the_home_page_and_the_sitemap_without_ads_rules_broken(self):
        for slug in ("r8", "monthly", "city"):
            self.assertIn(f'href="/guide/{slug}/"', self.read("guide/index.html"))
            self.assertIn(f'href="/guide/{slug}/"', self.read("index.html"))
            self.assertIn(f"https://saichin-sokuho.com/guide/{slug}/", self.read("sitemap.xml"))
            page = self.read(f"guide/{slug}/index.html")
            self.assertNotIn("a8.net", page)
            self.assertNotIn("pr-note", page)                                  # no advertisement on these pages
            self.assertEqual(content.GUIDE_BY_SLUG[slug]["verified"], "2026-10-20")
            self.assertGreater(len(re.sub(r"<[^>]+>", "", page)), 1800, slug)


class ExpandedGuidesTest(SiteFixture):
    """The five basic guides: at least 1,800 characters of prose each, and the worked examples recomputed (the numbers are those of the Ministry's pages)."""

    SLUGS = ("what-is", "how-decided", "excluded", "calculate", "below")

    def text(self, slug):
        return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", self.read(f"guide/{slug}/index.html")))

    def test_each_page_has_enough_text(self):
        for slug in self.SLUGS:
            body = re.sub(r"<[^>]+>", "", content.GUIDE_BY_SLUG[slug]["body"])
            self.assertGreaterEqual(len(body), 1800, slug)

    def test_the_payslip_example_adds_up(self):
        page = self.text("excluded")
        self.assertEqual(160000 + 20000, 180000)
        self.assertEqual(160000 + 20000 + 5000 + 8000 + 30000, 223000)
        self.assertIn("支給総額223,000円", page.replace("<td>", ""))
        self.assertEqual(round(180000 / (2000 / 12)), 1080)
        self.assertEqual(round(223000 / (2000 / 12)), 1338)
        for needle in ("180,000÷166.7≒1,080円", "約1,338円"):
            self.assertIn(needle, page)

    def test_the_taxi_example_is_the_ministrys(self):
        page = self.text("excluded")
        self.assertEqual(168000 + 6300 + 3150, 177450)
        self.assertEqual(round(177450 / 170), 1044)
        self.assertEqual(168000 / 200, 840)
        for needle in ("総支給額は177,450円", "約1,044円", "168,000÷200=840円"):
            self.assertIn(needle, page)

    def test_the_calculation_examples(self):
        page = self.text("calculate")
        self.assertAlmostEqual(7600 / 8, 950)
        self.assertEqual(round(7600 / 7), 1086)
        self.assertEqual(30000 / 40, 750)
        self.assertEqual(round(200000 / (8 * 250 / 12)), 1200)
        self.assertEqual(round(200000 / (7 * 240 / 12)), 1429)
        self.assertEqual(6000 / 8 + 25000 * 12 / (250 * 8), 900)
        self.assertEqual(136000 / 170 + 50000 / 200, 1050)
        for needle in ("7,600÷8=950円", "7,600÷7≒1,086円", "30,000÷40=750円", "200,000÷166.7≒1,200円", "200,000÷140≒1,429円", "合計は1,050円"):
            self.assertIn(needle, page)
        hours = {(8, 260): 173.3, (8, 250): 166.7, (7.5, 245): 153.1, (7, 240): 140.0, (6, 200): 100.0}
        rows = cells(self.read("guide/calculate/index.html"), "<h2>1か月の平均の所定労働時間</h2>")[1:]
        self.assertEqual(len(rows), len(hours))
        for h, d, m in rows:
            self.assertEqual(float(m[:-2]), round(float(h[:-2]) * float(d[:-1]) / 12, 1), (h, d))

    def test_the_shortfall_examples(self):
        page = self.text("below")
        self.assertEqual(50 * 120, 6000)
        self.assertEqual(50 * 120 * 6, 36000)
        self.assertEqual(round(160000 / (2000 / 12)), 960)
        self.assertEqual(round(2000 / 12 * 40, -2), 6700)
        for needle in ("50円×120時間=6,000円", "36,000円", "160,000÷166.7≒960円", "≒6,700円"):
            self.assertIn(needle, page)

    def test_the_statute_references_are_those_of_the_act(self):
        """Article numbers read on e-Gov on 2026-10-20: 4 (effect, items not counted), 6 (highest applies), 7 (reduction), 9-11 (decision, objection in 15 days), 13 (dispatch), 14 (30 days), 15-16 (specific), 22 (equal members), 40 (fine)."""
        how = self.text("how-decided")
        for needle in ("第10条", "第11条第2項", "公示の日から15日以内", "第14条第2項", "30日を過ぎた日", "第15条第1項", "第16条", "第22条"):
            self.assertIn(needle, how)
        what = self.text("what-is")
        for needle in ("第3条", "第6条第1項", "第7条", "第9条第1項", "第13条", "50万円以下の罰金"):
            self.assertIn(needle, what)
        self.assertIn("第40条", self.text("below"))
        self.assertIn("第4条第3項", self.text("excluded"))

    def test_the_r8_counts_on_the_decision_page_are_those_of_the_workbook(self):
        raises = {p["name"]: p["history"]["2026"]["amount"] - p["history"]["2025"]["amount"] for p in _raw()["prefectures"]}
        gl = {s: articles.GUIDELINE[articles.RANK_OF[s]] for s in raises}
        above = sum(1 for s in raises if raises[s] > gl[s])
        same = sum(1 for s in raises if raises[s] == gl[s])
        self.assertIn(f"{above}の都道府県が目安を上回り、{same}の都道府県が同じで、下回ったところはありません", self.text("how-decided"))

    def test_the_pages_keep_their_urls_and_sources(self):
        for slug in self.SLUGS:
            page = self.read(f"guide/{slug}/index.html")
            for _, url in content.GUIDE_BY_SLUG[slug]["sources"]:
                self.assertIn(url, page)
        self.assertIn("https://www.check-roudou.mhlw.go.jp/qa/roudousya/chingin/q9.html", self.read("guide/below/index.html"))


class TermsCityRankingTest(SiteFixture):
    """/guide/terms/ (the words of the news, with Reiwa 8 figures), the all-prefecture table of /guide/city/, and the reading notes under the rankings."""

    def text(self, path):
        return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", self.read(path)))

    def test_terms_page(self):
        page = self.read("guide/terms/index.html")
        text = self.text("guide/terms/index.html")
        self.assertGreater(len(text), 2000)
        raw = _raw()
        avg = {int(y): v for y, v in raw["national_weighted_average"].items()}
        up = round(avg[2026]) - round(avg[2025])
        now = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        self.assertIn(f"全国加重平均は{round(avg[2026]):,}円(+{up}円)になりました", text)
        self.assertIn(f"ニュースの「+{up}円」は、全国加重平均の上がり幅です", text)
        self.assertIn(f"{max(now.values()) - min(now.values())}円の幅があります", text)
        self.assertIn("東京都の1,280円", text)
        rises = {p["name"]: p["history"]["2026"]["amount"] - p["history"]["2025"]["amount"] for p in raw["prefectures"]}
        self.assertIn(f"+{min(rises.values())}円から+{max(rises.values())}円まで、県によって違います", text)
        for slug in ("how-decided", "excluded", "calculate", "monthly", "what-is"):
            self.assertIn(f'href="/guide/{slug}/"', page)
        for _, url in content.GUIDE_BY_SLUG["terms"]["sources"]:
            self.assertIn(url, page)
        self.assertIn("/guide/terms/", self.read("sitemap.xml"))

    def test_city_page_lists_three_cities_of_every_prefecture_with_its_amount(self):
        from sites.saichin.places import PLACES
        raw = _raw()
        am = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        rows = cells(self.read("guide/city/index.html"), "<h2>47都道府県の主な市</h2>")[1:]
        self.assertEqual(len(rows), 47)
        for pref, cities, amount in rows:
            short = next(s for s in am if pref.startswith(s))
            self.assertEqual(cities, "、".join(PLACES[short]), pref)
            self.assertEqual(amount, f"{am[short]:,}円", pref)
        self.assertGreater(len(self.text("guide/city/index.html")), 2000)

    def test_ranking_notes_name_the_two_ends_and_the_gap(self):
        raw = _raw()
        now = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        full = {r["short"]: r["name"] for r in self.d["rows"]}
        text = self.text("ranking/high/index.html")
        by_name = {full[s]: now[s] for s in now}
        listed = re.search(r"最も高い5都道府県は、(.*?)です", text).group(1)
        pairs = re.findall(r"([^、()]+?)\(([\d,]+)円\)", listed)
        self.assertEqual(len(pairs), 5)
        for name, a in pairs:
            self.assertEqual(by_name[name], int(a.replace(",", "")), name)
        self.assertEqual([int(a.replace(",", "")) for _, a in pairs], sorted(now.values(), reverse=True)[:5])
        gap = max(now.values()) - min(now.values())
        self.assertIn(f"最高額と最低額の差は{gap}円で、1日8時間・年250日働くと、この時給の差は年に{gap * 2000:,}円になります", text)
        self.assertEqual(len(set(now.values())), int(re.search(r"同じ額の都道府県があるのは、(\d+)通りの額", text).group(1)))
        rises = {s: p for s, p in ((p["name"], p["history"]["2026"]["amount"] - p["history"]["2025"]["amount"]) for p in raw["prefectures"])}
        rt = self.text("ranking/raise/index.html")
        self.assertIn(f"引上げ額は+{min(rises.values())}円から+{max(rises.values())}円まで{len(set(rises.values()))}通りあり", rt)
        self.assertIn(f"最大と最小の差は{max(rises.values()) - min(rises.values())}円です", rt)
