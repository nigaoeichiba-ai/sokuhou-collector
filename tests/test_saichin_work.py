"""The two guides for hourly workers (/guide/wall/, /guide/raise/): every number recomputed from the workbook fixture; the rules they state are the cited pages'."""
import re

from sites.saichin import build, content
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401


def cells(page, heading_regex):
    section = re.split(heading_regex, page, maxsplit=1)[1]
    table = re.search(r"<table>.*?</table>", section, re.S).group(0)
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[dh]>(.*?)</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S)]


class WallGuideTest(SiteFixture):
    def amounts(self):
        raw = _raw()
        return {p["name"] + build.SUFFIX.get(p["name"], "県"): p["history"]["2026"]["amount"] for p in raw["prefectures"]}

    def test_every_prefecture_row_is_recomputed(self):
        page = self.read("guide/wall/index.html")
        rows = cells(page, r"<h2>最低賃金で週20時間働いたときの年収と、130万円に届く時間</h2>")[1:]
        am = self.amounts()
        self.assertEqual(len(rows), 47)
        self.assertEqual([r[0] for r in rows], [n for n, _ in sorted(am.items(), key=lambda t: (-t[1], t[0]))])        # highest minimum wage first
        for name, w, monthly, annual, hours, over in rows:
            a = am[name]
            self.assertEqual(w, f"{a:,}円", name)
            self.assertEqual(annual, f"{a * 20 * 52 / 10000:.1f}万円", name)
            self.assertEqual(monthly, f"{round(a * 20 * 52 / 12 / 100) * 100:,}円", name)
            self.assertEqual(hours, f"{1_300_000 / (52 * a):.1f}時間", name)
            self.assertEqual(over, "超える" if a * 20 * 52 > 1_300_000 else "超えない", name)

    def test_the_lead_names_the_lowest_and_highest_year_income_and_who_passes_130(self):
        page = self.read("guide/wall/index.html")
        am = self.amounts()
        lo, hi = min(am, key=lambda n: (am[n], n)), max(am, key=lambda n: (am[n], n))
        self.assertIn(f"年収は{lo}の{am[lo] * 1040 / 10000:.1f}万円から{hi}の{am[hi] * 1040 / 10000:.1f}万円までです", page)
        over = [n for n in sorted(am, key=lambda n: (-am[n], n)) if am[n] * 1040 > 1_300_000]
        self.assertEqual(over, ["東京都", "神奈川県"])
        self.assertIn("週20時間で130万円を超えるのは、東京都と神奈川県です。", page)
        self.assertGreaterEqual(min(am.values()), 1016)
        self.assertIn("全47都道府県が1,016円以上です", page)

    def test_the_rules_it_states_are_those_of_the_cited_pages(self):
        page = self.read("guide/wall/index.html")
        for needle in ("2026年10月1日に、社会保険の「月額8.8万円以上」という賃金の要件がなくなりました", "週の所定労働時間が20時間以上であること",
                       "従業員数51人以上の企業", "10年かけて段階的に縮小・撤廃", "2か月を超えて続くとき",
                       "年収が130万円以上になると", "第3号被保険者", "最低賃金1,016円以上の地域で週20時間以上働くと、年額換算で約106万円です"):
            self.assertIn(needle, page)
        g = content.GUIDE_BY_SLUG["wall"]
        self.assertEqual(g["verified"], "2026-10-20")
        for _, url in g["sources"]:
            self.assertIn(url, page)
        self.assertEqual(g["sources"][0][1], "https://www.nenkin.go.jp/oshirase/taisetu/jigyosho/2026/202610/100104.html")

    def test_the_arithmetic_of_the_ministrys_1016_yen(self):
        self.assertEqual(-(-88_000 * 12 // (20 * 52)), 1016)           # 8.8万円 x 12 months / (20 hours x 52 weeks), rounded up: the Ministry's 1,016 yen
        self.assertAlmostEqual(1016 * 20 * 52 / 10000, 105.66, places=2)   # about 1.06 million yen a year


class RaiseGuideTest(SiteFixture):
    def test_the_five_year_table_is_recomputed_from_the_national_average(self):
        raw = _raw()
        avg = raw["national_weighted_average"]
        rows = cells(self.read("guide/raise/index.html"), r"<h2>2\. 最低賃金が上がった年に、何が変わるか</h2>")[1:]
        self.assertEqual(len(rows), 5)
        for row, fy in zip(rows, range(2022, 2027)):
            up = round(avg[str(fy)]) - round(avg[str(fy - 1)])
            self.assertEqual(row[0], raw["fiscal_year_labels"][str(fy)])
            self.assertEqual(row[1], f"+{up}円")
            self.assertEqual(row[2], f"{up / round(avg[str(fy - 1)]) * 100:.1f}%")
            self.assertEqual(row[3], f"+{round(up * 20 * 52 / 12):,}円")

    def test_the_region_table_is_recomputed(self):
        raw = _raw()
        am = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        rows = cells(self.read("guide/raise/index.html"), r"<h2>4\. 通勤できる範囲で、地方内の違いを知る</h2>")[1:]
        self.assertEqual(len(rows), 7)
        diffs = []
        for rname, hi_cell, lo_cell, diff in rows:
            slug, _, shorts = next(x for x in build.REGIONS if x[1] == rname)
            vals = {s: am[s] for s in shorts}
            hi, lo = max(vals.values()), min(vals.values())
            self.assertIn(f"{hi:,}円", hi_cell)
            self.assertIn(f"{lo:,}円", lo_cell)
            self.assertEqual(diff, f"{hi - lo}円")
            diffs.append(hi - lo)
        self.assertEqual(diffs, sorted(diffs, reverse=True))
        self.assertEqual(max(diffs), 160)                                # Kanto: Tokyo 1,280 and Gunma 1,120
        page = self.read("guide/raise/index.html")
        self.assertIn(f"全国では最高と最低で{max(am.values()) - min(am.values())}円、地方の中で最も差が大きいのは関東の160円です", page)

    def test_the_example_of_a_wage_30_yen_above_the_minimum(self):
        page = self.read("guide/raise/index.html")
        self.assertIn("+56円上がると、時給は新しい最低賃金を下回ります。勤め先は時給を引き上げなければなりません", page)

    def test_the_rules_it_states_are_those_of_the_cited_pages(self):
        page = self.read("guide/raise/index.html")
        for needle in ("発効日以降は、賃金の計算期間の途中でも、改定後の額以上を払う必要があります", "派遣先の事業場がある都道府県の額",
                       "試用期間中でも、最低賃金は適用されます", "都道府県労働局長の許可を受けた場合に限られます", "若者雇用促進法にもとづく指針",
                       "一定時間分の時間外・休日・深夜の割増賃金を、定額で払うもの"):
            self.assertIn(needle, page)
        g = content.GUIDE_BY_SLUG["raise"]
        for _, url in g["sources"]:
            self.assertIn(url, page)


class BothGuidesTest(SiteFixture):
    def test_no_affiliate_or_shop_link_and_no_ai_wording_until_a_program_is_approved(self):
        for slug in ("wall", "raise"):
            page = self.read(f"guide/{slug}/index.html")
            for word in ("a8.net", "rakuten", "amazon", "valuecommerce", "rel=\"sponsored\"", "Claude", "AIの支援", "自動作成"):
                self.assertNotIn(word, page, (slug, word))
            hosts = set(re.findall(r'href="https?://([^/"]+)', page))
            self.assertLessEqual(hosts, {"saichin-sokuho.com", "www.nenkin.go.jp", "www.mhlw.go.jp", "saiteichingin.mhlw.go.jp", "jsite.mhlw.go.jp", "laws.e-gov.go.jp", "www.digital.go.jp"}, slug)

    def test_the_guides_are_linked_from_the_hub_the_home_page_and_the_prefecture_pages(self):
        for slug in ("wall", "raise"):
            self.assertIn(f'href="/guide/{slug}/"', self.read("guide/index.html"))
            self.assertIn(f'href="/guide/{slug}/"', self.read("index.html"))
            self.assertIn(f'href="/guide/{slug}/"', self.read("tokyo/index.html"))
            self.assertIn(f"https://saichin-sokuho.com/guide/{slug}/", self.read("sitemap.xml"))

    def test_the_guides_keep_the_ad_tag_rule(self):
        for slug in ("wall", "raise"):
            self.assertNotIn("guide/" + slug + "/", build.NO_ADS_PATHS)
        self.assertIn("/guide/", build.NO_ADS_PATHS)
