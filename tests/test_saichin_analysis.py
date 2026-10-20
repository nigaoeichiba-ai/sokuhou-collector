"""The /analysis/ pages and the "numbers" blocks: every figure on them is recomputed here from the raw workbook, by a second, separate calculation."""
import re
from datetime import date

from sites.saichin import analysis, analysis_pages, build, history_old
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401

LABEL_OF = lambda raw, fy: raw["fiscal_year_labels"][str(fy)]  # noqa: E731
YEARS = list(range(2002, 2027))


def amount(raw, short, fy):
    return next(p for p in raw["prefectures"] if p["name"] == short)["history"][str(fy)]["amount"]


def amounts(raw, fy):
    return [p["history"][str(fy)]["amount"] for p in raw["prefectures"]]


def rows_of(page, after):
    """Cell texts of every row of the first table after the heading `after`."""
    section = page.split(after, 1)[1]
    table = re.search(r"<table>.*?</table>", section, re.S).group(0)
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        cells = re.findall(r"<t[dh]>(.*?)</t[dh]>", tr, re.S)
        rows.append([re.sub(r"<[^>]+>", "", c) for c in cells])
    return rows


def wrong_gap_rows(page, raw):
    """Years whose row of the gap table does not carry the gap and ratio computed from the workbook (empty = all right)."""
    rows = {r[0]: r for r in rows_of(page, "<h2>年度別の一覧</h2>")[1:]}
    bad = []
    for fy in YEARS:
        hi, lo = max(amounts(raw, fy)), min(amounts(raw, fy))
        row = rows[LABEL_OF(raw, fy)]
        if row[3] != f"{hi - lo}円" or row[4] != f"{lo / hi * 100:.1f}%" or not row[1].startswith(f"{hi:,}円") or not row[2].startswith(f"{lo:,}円"):
            bad.append(fy)
    return bad


def wrong_raise_rows(page, raw):
    rows = {r[0]: r for r in rows_of(page, "<h2>年度別の一覧</h2>")[1:]}
    avg = raw["national_weighted_average"]
    bad = []
    for fy in YEARS[1:]:
        up = round(avg[str(fy)]) - round(avg[str(fy - 1)])
        row = rows[LABEL_OF(raw, fy)]
        if row[1] != f"+{up}円" or row[2] != f"{up / round(avg[str(fy - 1)]) * 100:.1f}%":
            bad.append(fy)
        diffs = [a - b for a, b in zip(amounts(raw, fy), amounts(raw, fy - 1))]
        if not row[3].startswith(f"+{max(diffs)}円") or not row[4].startswith(f"+{min(diffs)}円"):
            bad.append(fy)
        if row[5] != str(sum(1 for x in diffs if x >= 30)) or row[6] != str(sum(1 for x in diffs if x >= 50)):
            bad.append(fy)
    return bad


class AnalysisPagesTest(SiteFixture):
    def test_the_hub_and_five_pages_exist_in_the_sitemap_and_the_nav(self):
        for rel in ("analysis/index.html", *(f"analysis/{s}/index.html" for s in analysis_pages.ORDER)):
            self.assertIn(rel, self.files)
        sitemap = self.read("sitemap.xml")
        for s in analysis_pages.ORDER:
            self.assertIn(f"https://saichin-sokuho.com/analysis/{s}/", sitemap)
        self.assertIn('<a href="/analysis/">分析</a>', self.read("index.html"))
        hub = self.read("analysis/index.html")
        for s in analysis_pages.ORDER:
            self.assertIn(f'href="/analysis/{s}/"', hub)
            self.assertIn(f'href="/analysis/{s}/"', self.read("index.html"))

    def test_the_gap_table_matches_the_workbook_for_every_year(self):
        self.assertEqual(wrong_gap_rows(self.read("analysis/gap/index.html"), _raw()), [])

    def test_a_wrong_gap_figure_is_detected(self):
        page = self.read("analysis/gap/index.html").replace("<td>195円</td>", "<td>196円</td>")
        self.assertEqual(wrong_gap_rows(page, _raw()), [2026])

    def test_the_lead_names_the_widest_gap_of_the_workbook(self):
        raw = _raw()
        gaps = {fy: max(amounts(raw, fy)) - min(amounts(raw, fy)) for fy in YEARS}
        widest = max(gaps, key=lambda fy: (gaps[fy], fy))
        lead = re.search(r'<p class="lead">(.*?)</p>', self.read("analysis/gap/index.html"), re.S).group(1)
        self.assertIn(f"{LABEL_OF(raw, 2002)}の{gaps[2002]}円から、{LABEL_OF(raw, 2026)}の{gaps[2026]}円", lead)
        self.assertIn(f"{LABEL_OF(raw, widest)}の{gaps[widest]}円", lead)

    def test_the_raise_table_matches_the_workbook_for_every_year(self):
        self.assertEqual(wrong_raise_rows(self.read("analysis/raises/index.html"), _raw()), [])

    def test_a_wrong_raise_figure_is_detected(self):
        raw = _raw()
        up = round(raw["national_weighted_average"]["2026"]) - round(raw["national_weighted_average"]["2025"])
        page = self.read("analysis/raises/index.html").replace(f"<td>+{up}円</td>", f"<td>+{up + 1}円</td>", 1)
        self.assertEqual(wrong_raise_rows(page, raw), [2026])

    def test_every_milestone_year_is_the_first_year_at_or_above_the_amount(self):
        raw = _raw()
        rows = {r[0]: r for r in rows_of(self.read("analysis/milestones/index.html"), "<h2>都道府県別の到達年度</h2>")[1:]}
        self.assertEqual(len(rows), 47)
        for p in raw["prefectures"]:
            name = p["name"] + build.SUFFIX.get(p["name"], "県")
            for col, t in enumerate(analysis.THRESHOLDS, start=1):
                first = next((fy for fy in YEARS if amount(raw, p["name"], fy) >= t), None)
                expected = analysis.short_label(LABEL_OF(raw, first)) if first else "-"
                self.assertEqual(rows[name][col], expected, (name, t))

    def test_the_milestone_lead_counts_match_the_workbook(self):
        raw = _raw()
        n1100 = sum(1 for a in amounts(raw, 2026) if a >= 1100)
        n1200 = sum(1 for a in amounts(raw, 2026) if a >= 1200)
        lead = re.search(r'<p class="lead">(.*?)</p>', self.read("analysis/milestones/index.html"), re.S).group(1)
        self.assertIn(f"1,100円以上が{n1100}都道府県、1,200円以上が{n1200}都道府県", lead)
        first_1000 = min(fy for fy in YEARS if max(amounts(raw, fy)) >= 1000)
        self.assertIn(f"初めて1,000円以上になったのは{LABEL_OF(raw, first_1000)}", lead)
        last_1000 = max(next(fy for fy in YEARS if amount(raw, p["name"], fy) >= 1000) for p in raw["prefectures"])
        self.assertIn(f"全47都道府県が1,000円以上になったのは{LABEL_OF(raw, last_1000)}で、最初の都道府県から{last_1000 - first_1000}年", lead)

    def test_the_rank_table_is_ranked_by_competition_ranking_from_the_workbook(self):
        raw = _raw()
        rows = {r[0]: r for r in rows_of(self.read("analysis/ranks/index.html"), "<h2>47都道府県の順位表</h2>")[1:]}
        self.assertEqual(len(rows), 47)

        def rank(short, fy):
            mine = amount(raw, short, fy)
            return 1 + sum(1 for a in amounts(raw, fy) if a > mine)
        for p in raw["prefectures"]:
            short = p["name"]
            name = short + build.SUFFIX.get(short, "県")
            ranks = [rank(short, fy) for fy in YEARS]
            self.assertEqual(rows[name][1:], [f"{ranks[0]}位", f"{rank(short, 2016)}位", f"{ranks[-1]}位", f"{min(ranks)}位", f"{max(ranks)}位"], name)

    def test_the_biggest_climber_and_faller_in_the_lead_are_the_workbook_extremes(self):
        raw = _raw()

        def rank(short, fy):
            mine = amount(raw, short, fy)
            return 1 + sum(1 for a in amounts(raw, fy) if a > mine)
        change = {p["name"]: rank(p["name"], 2002) - rank(p["name"], 2026) for p in raw["prefectures"]}
        up, down = max(change.values()), min(change.values())
        lead = re.search(r'<p class="lead">(.*?)</p>', self.read("analysis/ranks/index.html"), re.S).group(1)
        def phrase(value):
            return "、".join(short + build.SUFFIX.get(short, "県") for short, c in change.items() if c == value)
        short_up = next(short for short, c in change.items() if c == up)
        short_down = next(short for short, c in change.items() if c == down)
        self.assertIn(f"最も順位を上げたのは{phrase(up)}({rank(short_up, 2002)}位→{rank(short_up, 2026)}位)", lead)
        self.assertIn(f"最も下げたのは{phrase(down)}({rank(short_down, 2002)}位→{rank(short_down, 2026)}位)", lead)
        self.assertGreater(up, 0)
        self.assertLess(down, 0)

    def test_the_date_columns_never_overlap_and_add_up_to_the_prefectures_that_raised(self):
        raw = _raw()
        rows = {r[0]: r for r in rows_of(self.read("analysis/dates/index.html"), "<h2>年度別の一覧</h2>")[1:]}
        for fy in YEARS[1:]:
            dates = []
            for p in raw["prefectures"]:
                cur, before = p["history"][str(fy)], p["history"][str(fy - 1)]
                if cur["amount"] != before["amount"]:
                    dates.append(date.fromisoformat(build.plausible_effective(p["name"], fy, cur["effective_date"])[0]))
            if not dates:
                continue
            base = date(fy, 10, 1)
            by_oct1 = sum(1 for x in dates if x <= base)
            in_oct = sum(1 for x in dates if x.year == fy and x.month == 10 and x.day >= 2)
            nov_dec = sum(1 for x in dates if x.year == fy and x.month in (11, 12))
            later = sum(1 for x in dates if x.year > fy)
            self.assertEqual(by_oct1 + in_oct + nov_dec + later, len(dates), fy)
            row = rows[LABEL_OF(raw, fy)]
            self.assertEqual(row[1:2] + row[5:], [str(len(dates)), str(by_oct1), str(in_oct), str(nov_dec), str(later)], fy)
            self.assertEqual(row[4], f"{(max(dates) - min(dates)).days}日", fy)

    def test_no_page_states_a_cause(self):
        for s in analysis_pages.ORDER:
            text = re.sub(r"<[^>]+>", "", self.read(f"analysis/{s}/index.html"))
            for word in ("原因", "影響", "背景には", "ためです", "のため上が", "が理由"):
                self.assertNotIn(word, text, (s, word))
            self.assertIn("額が動いた理由は調べていません", text)

    def test_each_analysis_page_tells_where_the_numbers_come_from(self):
        for s in analysis_pages.ORDER:
            page = self.read(f"analysis/{s}/index.html")
            self.assertIn("厚生労働省「地域別最低賃金の全国一覧」", page)
            self.assertIn('href="/data/"', page)
            self.assertIn('href="/cite/"', page)


def money(v):
    """296円, 320.88円, 1,172円 (own formatting, independent of the site's)."""
    return f"{int(v):,}円" if v == int(v) else f"{v:,.2f}".rstrip("0").rstrip(".") + "円"


def series_1977(raw, old, short):
    """{fiscal year: amount} from Showa 52 on, from the saved old page and the workbook; Kyoto's split years are absent."""
    s = {int(y): v for y, v in old["prefectures"][short].items() if int(y) < 2002}
    s.update({int(y): v["amount"] for y, v in next(p for p in raw["prefectures"] if p["name"] == short)["history"].items()})
    return s


class NumbersBlockTest(SiteFixture):
    def test_each_prefecture_page_has_the_numbers_block_with_values_from_the_workbook_and_the_old_document(self):
        raw = _raw()
        old = history_old.load()
        every = {p["name"]: series_1977(raw, old, p["name"]) for p in raw["prefectures"]}
        hi0, lo0 = max(s[1977] for s in every.values()), min(s[1977] for s in every.values())
        hi1, lo1 = max(s[2026] for s in every.values()), min(s[2026] for s in every.values())
        for short, amts in every.items():
            r = next(x for x in self.d["rows"] if x["short"] == short)
            page = self.read(f"{r['slug']}/index.html")
            self.assertIn(f"{r['name']}の昭和52年度から令和8年度までを数字で見る</h2>", page, short)
            rows = {x[0]: x for x in rows_of(page, "を数字で見る</h2>")[1:]}
            self.assertEqual(rows["最低賃金"][1:], [money(amts[1977]), money(amts[2026])], short)
            self.assertEqual(rows["最高額の都道府県との差"][1:], ["最高額" if amts[1977] == hi0 else f"{money(hi0 - amts[1977])}低い",
                                                       "最高額" if amts[2026] == hi1 else f"{money(hi1 - amts[2026])}低い"], short)
            self.assertEqual(rows["最低額の都道府県との差"][1:], ["最低額" if amts[1977] == lo0 else f"{money(amts[1977] - lo0)}高い",
                                                       "最低額" if amts[2026] == lo1 else f"{money(amts[2026] - lo1)}高い"], short)
            if short == "京都":
                continue                                                    # Kyoto's two rates: checked in test_kyoto_has_two_rates_from_showa_54_to_heisei_1
            for t in analysis.PREF_THRESHOLDS:
                reached = [fy for fy in sorted(amts) if amts[fy] >= t]
                if reached:
                    self.assertRegex(page, rf"<tr><td>{t:,}円</td><td>{LABEL_OF_ANY(reached[0])}</td>", (short, t))
                else:
                    self.assertNotRegex(page, rf"<tr><td>{t:,}円</td><td>(昭和|平成|令和)", (short, t))

    def test_each_area_page_has_the_numbers_block(self):
        raw = _raw()
        old = history_old.load()
        for slug, rname, shorts in build.REGIONS:
            page = self.read(f"area/{slug}/index.html")
            self.assertIn(f"{rname}の昭和52年度から令和8年度までを数字で見る</h2>", page, slug)
            rows = {x[0]: x for x in rows_of(page, "を数字で見る</h2>")[1:]}
            first, last = [series_1977(raw, old, s)[1977] for s in shorts], [series_1977(raw, old, s)[2026] for s in shorts]
            self.assertEqual(rows["最も低い額"][1:], [money(min(first)), money(min(last))], slug)
            self.assertEqual(rows["最も高い額"][1:], [money(max(first)), money(max(last))], slug)
            self.assertEqual(rows["最高額と最低額の差"][1:], [money(max(first) - min(first)), money(max(last) - min(last))], slug)
            self.assertEqual(rows["単純平均"][1:], [money(round(sum(first) / len(first))), money(round(sum(last) / len(last)))], slug)


def LABEL_OF_ANY(fy):
    """The Japanese era label of a fiscal year, written out here (not taken from the site)."""
    if fy <= 1988:
        return f"昭和{fy - 1925}年度"
    if fy == 1989:
        return "平成元年度"
    if fy <= 2018:
        return f"平成{fy - 1988}年度"
    return "令和元年度" if fy == 2019 else f"令和{fy - 2018}年度"


class AboutPageTest(SiteFixture):
    def test_the_operator_page_has_the_policy_and_the_update_history(self):
        page = self.read("about/index.html")
        for heading in ("編集方針", "誤りを見つけたら", "更新の履歴"):
            self.assertIn(f"<h2>{heading}</h2>", page)
        from sites.saichin import content
        days = [d for d, _ in content.UPDATES]
        self.assertEqual(days, sorted(days, reverse=True))               # newest first
        self.assertEqual(len(set(days)), len(days))
        for day, text in content.UPDATES:
            self.assertIn(text, page)


class FaqGuideTest(SiteFixture):
    """The FAQ guide restates what the Ministry's pages say (read in a browser on 2026-10-19); the numbers in it are checked here."""
    def test_the_figures_of_the_faq_are_the_ministrys(self):
        from sites.saichin import content
        g = content.GUIDE_BY_SLUG["faq"]
        self.assertAlmostEqual(30000 / 40, 750.0)
        for needle in ("30,000 ÷ 40 = 750円", "全国で223件です(令和8年4月1日現在)", "50万円以下の罰金", "派遣先の事業場がある都道府県の最低賃金", "労働基準法第9条"):
            self.assertIn(needle, g["body"])
        self.assertEqual(g["body"].count("<li>") - g["body"].split("<h2>特定")[1].count("<li>"), 5)          # the five cases in which a lower amount can be permitted
        self.assertEqual(g["verified"], "2026-10-19")

    def test_the_page_shows_its_own_confirmation_date_and_every_source(self):
        from sites.saichin import content
        page = self.read("guide/faq/index.html")
        self.assertIn("内容の確認日: 2026年10月19日", page)
        for _, url in content.GUIDE_BY_SLUG["faq"]["sources"]:
            self.assertIn(url, page)
        self.assertIn('href="/guide/faq/"', self.read("guide/index.html"))
        self.assertIn('href="/guide/faq/"', self.read("tokyo/index.html"))

    def test_no_page_says_it_was_made_by_ai_or_automatically(self):
        """The owner's decision (2026-10-19): the site does not state how its text was produced."""
        for rel in self.files:
            if not rel.endswith((".html", ".xml", ".json", ".csv")):
                continue
            text = re.sub(r"<script[^>]*src=[^>]*></script>", "", self.read(rel))
            for word in ("Claude", "Anthropic", "AIの支援", "AI(", "人工知能", "自動で作", "自動作成", "自動生成", "機械が", "プログラムで計算"):
                self.assertNotIn(word, text, (rel, word))
