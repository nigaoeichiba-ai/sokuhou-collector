"""The sentences of each prefecture page that are written only when they are true of that prefecture, and how alike the pages still are."""
import os
import re
import unittest
from itertools import combinations
from pathlib import Path

from datetime import date

from sites.saichin import adjacency, articles, build, history_old
from tests import saichin_overlap as ov
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401
from tests.test_saichin_trend import all_series, label, money

YEARS_ = list(range(1977, 2027))


class AdjacencyTest(unittest.TestCase):
    def test_the_table_is_symmetric_and_has_every_prefecture(self):
        n = adjacency.NEIGHBOURS
        self.assertEqual(sorted(n), sorted(build.SLUGS))
        for a, ns in n.items():
            for b in ns:
                self.assertIn(a, n[b], (a, b))
            self.assertEqual(len(ns), len(set(ns)), a)
            self.assertNotIn(a, ns)

    def test_known_numbers_of_neighbours(self):
        n = {a: len(v) for a, v in adjacency.NEIGHBOURS.items()}
        for name, count in (("長野", 8), ("埼玉", 7), ("岐阜", 7), ("福島", 6), ("三重", 6), ("京都", 6), ("北海道", 0), ("沖縄", 0), ("長崎", 1), ("千葉", 3), ("山口", 2)):
            self.assertEqual(n[name], count, name)


class StoryTest(SiteFixture):
    def prose(self, slug):
        return ov.prose(self.read(f"{slug}/index.html"))

    def test_the_neighbour_sentence_follows_the_amounts(self):
        raw = _raw()
        am = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        names = {r["short"]: r["name"] for r in self.d["rows"]}
        for r in self.d["rows"]:
            text = self.prose(r["slug"])
            near = adjacency.NEIGHBOURS[r["short"]]
            if not near:
                self.assertIn("陸続きで接する都道府県がありません", text, r["name"])
                continue
            higher = [n for n in near if am[n] > am[r["short"]]]
            lower = [n for n in near if am[n] < am[r["short"]]]
            same = [n for n in near if am[n] == am[r["short"]]]
            if not higher and not same:
                self.assertIn(f"接する{len(near)}都道府県は、どこも{r['name']}より低い額です", text, r["name"])
            elif not lower and not same:
                self.assertIn(f"接する{len(near)}都道府県は、どこも{r['name']}より高い額です", text, r["name"])
            else:
                self.assertIn(f"接する{len(near)}都道府県のうち、", text, r["name"])
                if higher:
                    self.assertRegex(text, rf"高いのは[^、]*{names[max(higher, key=lambda n: (am[n], n))]}", r["name"])
                if lower:
                    self.assertIn("低いのは", text, r["name"])
                self.assertEqual("高いのは" in text.split("接する", 1)[1].split("です。", 1)[0], bool(higher), r["name"])



    def test_the_island_prefectures_say_so_and_the_others_do_not(self):
        for slug in ("hokkaido", "okinawa"):
            self.assertIn("陸続きで接する都道府県がありません", self.prose(slug))
        self.assertNotIn("陸続きで接する", self.prose("saga"))

    def test_the_sentence_about_equal_amounts_appears_only_where_there_were_equal_years(self):
        raw, old = _raw(), history_old.load()
        series, _ = all_series(raw, old)
        for r in self.d["rows"]:
            s_ = series[r["short"]]
            zero = [fy for fy in range(1978, 2027) if s_[fy] is not None and s_[fy - 1] is not None and s_[fy] == s_[fy - 1]]
            self.assertEqual("前の年度と同じ額だったのは" in self.prose(r["slug"]), bool(zero), r["name"])




def fact_rows(page, after):
    """{row label: cell} of the two-column tables with <th scope="row"> rows that follow the heading `after`."""
    section = page.split(after, 1)[1]
    table = re.search(r"<table>.*?</table>", section, re.S).group(0)
    return {re.sub(r"<[^>]+>", "", a): re.sub(r"<[^>]+>", "", b) for a, b in re.findall(r'<th scope="row">(.*?)</th><td>(.*?)</td>', table, re.S)}


class FactsTest(SiteFixture):
    """Every sentence and table row of the prefecture pages that depends on a computed fact, recomputed here from the workbook fixture and the old document."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raw = _raw()
        cls.old = history_old.load()
        cls.series, _ = all_series(cls.raw, cls.old)
        cls.avg = {int(y): v for y, v in cls.raw["national_weighted_average"].items()}
        cls.full = {r["short"]: r["name"] for r in cls.d["rows"]}
        cls.slug = {r["short"]: r["slug"] for r in cls.d["rows"]}

    def prose(self, short):
        return ov.prose(self.read(f"{self.slug[short]}/index.html"))

    def rank_in(self, fy, short):
        s = self.series
        mine = s[short][fy]
        return None if mine is None else 1 + sum(1 for o in s.values() if o[fy] is not None and o[fy] > mine)

    # ---- tables
    def test_the_main_figures_table(self):
        for short, s in self.series.items():
            rows = fact_rows(self.read(f"{self.slug[short]}/index.html"), "の最低賃金の主な数字</h2>")
            first, last = s[1977], s[2026]
            self.assertEqual(rows["昭和52年度の額"], money(first), short)
            self.assertEqual(rows["令和8年度の額(決まった額)"], money(last), short)
            self.assertEqual(rows["49年間で上がった額"], f"+{money(last - first)}(約{last / first:.1f}倍、1年あたり約{(last - first) / 49:.0f}円)", short)
            rises = {fy: round(s[fy] - s[fy - 1], 2) for fy in YEARS_[1:] if s[fy] is not None and s[fy - 1] is not None}
            top = max((fy for fy in rises if rises[fy] > 0), key=lambda fy: (rises[fy], fy))
            self.assertEqual(rows["1年の引上げ額が最も大きかった年度"], f"{label(top)}の+{money(rises[top])}", short)
            pct = {fy: rises[fy] / s[fy - 1] * 100 for fy in rises}
            best = max(pct, key=lambda fy: (pct[fy], fy))
            self.assertEqual(rows["引上げ率が最も大きかった年度"], f"{label(best)}の{pct[best]:.1f}%", short)
            self.assertEqual(rows["直近10年間の上がり額(平成28年度から令和8年度まで)"], f"+{money(last - s[2016])}", short)
            self.assertEqual(rows["その前の10年間の上がり額(平成18年度から平成28年度まで)"], f"+{money(s[2016] - s[2006])}", short)
            if s[1989] is not None:
                self.assertEqual(rows["平成(元〜30年度)の上がり額"], f"+{money(s[2018] - s[1989])}", short)
                self.assertEqual(rows["令和(元〜8年度)の上がり額"], f"+{money(last - s[2018])}", short)
            else:
                self.assertNotIn("平成(元〜30年度)の上がり額", rows, short)                  # Kyoto: two rates in Heisei 1
            for t in (1000, 1100, 1200):
                fy = next((y for y in YEARS_ if s[y] is not None and s[y] >= t), None)
                self.assertEqual(rows[f"{t:,}円以上になった年度"], label(fy) if fy else "まだ届いていません", (short, t))
            nxt = (last // 100 + 1) * 100
            if last % 100:
                self.assertEqual(rows[f"次の節目の{nxt:,}円まで"], f"あと{nxt - last:g}円", short)
            else:
                self.assertNotIn("次の節目の", "".join(rows))

    def test_the_comparison_table(self):
        nat = lambda fy: round(self.avg[fy]) - round(self.avg[fy - 1])  # noqa: E731
        dates = {r["short"]: r["effective_date"] for r in self.d["rows"]}
        for short, s in self.series.items():
            rows = fact_rows(self.read(f"{self.slug[short]}/index.html"), "の引上げ額と発効日を、全国と比べる</h2>")
            rise = s[2026] - s[2025]
            raises = {o: self.series[o][2026] - self.series[o][2025] for o in self.series}
            rank = 1 + sum(1 for v in raises.values() if v > rise)
            self.assertEqual(rows["令和8年度の引上げ額"], f"+{rise}円(全国加重平均 +{nat(2026)}円、47都道府県中{rank}位)", short)
            sum3 = sum(s[fy] - s[fy - 1] for fy in (2024, 2025, 2026))
            self.assertEqual(rows["直近3年度の引上げ額の合計"], f"+{sum3}円(全国加重平均 +{sum(nat(fy) for fy in (2024, 2025, 2026))}円)", short)
            up = sum(1 for fy in (2024, 2025, 2026) if s[fy] - s[fy - 1] > nat(fy))
            dn = sum(1 for fy in (2024, 2025, 2026) if s[fy] - s[fy - 1] < nat(fy))
            self.assertEqual(rows["直近3回で、引上げ額が全国加重平均を上回った回数"], f"{up}回(下回った回数 {dn}回)", short)
            ten = range(2017, 2027)
            self.assertEqual(rows["直近10回で、引上げ額が全国加重平均以上だった回数"], f"{sum(1 for fy in ten if s[fy] - s[fy - 1] >= nat(fy))}回", short)
            self.assertEqual(rows["直近10回で、+50円以上の引上げだった回数"], f"{sum(1 for fy in ten if s[fy] - s[fy - 1] >= 50)}回", short)
            guide = articles.GUIDELINE[articles.RANK_OF[short]]
            mates = [o for o in self.series if articles.RANK_OF[o] == articles.RANK_OF[short]]
            pos = 1 + sum(1 for o in mates if raises[o] > rise)
            self.assertEqual(rows[f"令和8年度の目安({articles.RANK_OF[short]}ランク)"],
                             f"+{guide}円(決まった引上げ額は、目安との差 {rise - guide:+d}円。同じ{articles.RANK_OF[short]}ランクの{len(mates)}都道府県中、引上げ額は大きい方から{pos}番目)", short)
            d0 = date.fromisoformat(dates[short])
            earlier = sum(1 for v in dates.values() if v < dates[short])
            later = sum(1 for v in dates.values() if v > dates[short])
            self.assertEqual(rows["発効日"], f"{d0.year}年{d0.month}月{d0.day}日({'月火水木金土日'[d0.weekday()]}曜日)。早い方から{earlier + 1}番目で、これより遅い都道府県は{later}つ", short)
            hi = max(self.series[o][2026] for o in self.series)
            self.assertEqual(rows["最も高い額に対する割合"], f"{s[2026] / hi * 100:.1f}%(差 {hi - s[2026]}円)", short)

    def test_the_monthly_and_130_rows(self):
        for short, s in self.series.items():
            page = self.read(f"{self.slug[short]}/index.html")
            now = s[2026]
            low = -(-(now * 2000) // 1200) * 100              # monthly pay (8 hours x 250 days / 12 months) at the minimum wage, rounded up to 100 yen
            self.assertIn(f'<th scope="row">月給の下限(1日8時間・年250日。手当を除く)</th><td>{low:,}円</td>', page, short)
            a20 = now * 20 * 52
            cell = (f"週20時間でも年収が130万円を超えます({a20 / 10000:.1f}万円)" if a20 > 1_300_000
                    else f"週{1_300_000 / (52 * now):.1f}時間(週20時間では{a20 / 10000:.1f}万円)")
            self.assertIn(f'<th scope="row">最低賃金で働いて、年収が130万円になる週の労働時間</th><td>{cell}</td>', page, short)

    # ---- sentences
    def test_the_lead_says_how_far_from_the_national_average(self):
        for short, s in self.series.items():
            page = self.read(f"{self.slug[short]}/index.html")
            diff = s[2026] - round(self.avg[2026])
            tail = f"(全国加重平均 {round(self.avg[2026]):,}円)。"
            name = self.full[short]
            if diff == 0:
                want = f"{name}の額は、全国加重平均と同じ額です{tail}"
            else:
                w, n = ("高い" if diff > 0 else "低い"), abs(diff)
                want = (f"{name}の額は、全国加重平均とほぼ同じ水準で、{n}円{w}額です{tail}" if n <= 5 else
                        f"{name}の額は、全国加重平均より{n}円も{w}額です{tail}" if n >= 100 else
                        f"{name}の額は、全国加重平均より{n}円{w}、差の大きい水準です{tail}" if n >= 40 else
                        f"{name}の額は、全国加重平均より{n}円{w}額です{tail}")
            self.assertIn(want, page, short)

    def test_the_band_sentence(self):
        for short in self.series:
            rank = self.rank_in(2026, short)
            text = self.prose(short)
            want = (f"{rank}位は、47都道府県の先頭です。" if rank == 1 else f"{rank}位は、全国の上位5都道府県に入る高さです。" if rank <= 5 else
                    f"{rank}位は、上から10番目までに入ります。" if rank <= 10 else f"{rank}位は、全国の上位3分の1にあたります。" if rank <= 15 else
                    f"{rank}位は、真ん中より少し上です。" if rank <= 23 else f"{rank}位は、47都道府県のちょうど真ん中です。" if rank == 24 else
                    f"{rank}位は、真ん中より少し下です。" if rank <= 31 else f"{rank}位は、全国の下位3分の1にあたります。" if rank <= 37 else
                    f"{rank}位は、下から10番目までに入ります。" if rank <= 42 else f"{rank}位は、全国の下位5都道府県に入る低さです。" if rank <= 46 else
                    f"{rank}位は、47都道府県の最後です。")
            self.assertIn(want, text, short)

    def test_the_highest_and_the_lowest_get_their_own_sentences(self):
        self.assertIn("全国で最も高い額で、2番目の額との差は1円です。", self.prose("東京"))
        self.assertIn("全国で最も低い額で、2番目に低い額との差は1円です。", self.prose("宮崎"))
        for short in ("東京", "宮崎"):
            self.assertEqual(self.prose(short).count("全国で最も高い額で") + self.prose(short).count("全国で最も低い額で"), 1, short)
        self.assertNotIn("全国で最も高い額で", self.prose("大阪"))

    def test_the_date_sentence_only_for_the_earliest_and_the_latest(self):
        dates = {r["short"]: r["effective_date"] for r in self.d["rows"]}
        first, last = min(dates.values()), max(dates.values())
        for short, iso in dates.items():
            text = self.prose(short)
            if iso == first:
                self.assertIn("全国で最も早い日", text, short)
                self.assertIn(f"{list(dates.values()).count(first)}都道府県が同じ日です", text, short)
            elif iso == last:
                self.assertIn("全国で最も遅い日です", text, short)
            else:
                self.assertNotIn("の発効日の", text, short)

    def test_the_neighbour_order_sentences(self):
        for short, s in self.series.items():
            text = self.prose(short)
            flips = []
            for n in adjacency.NEIGHBOURS[short]:
                years = [fy for fy in YEARS_ if s[fy] is not None and self.series[n][fy] is not None]
                sign = lambda fy: (s[fy] > self.series[n][fy]) - (s[fy] < self.series[n][fy])  # noqa: E731
                cur = sign(years[-1])
                if cur == 0:
                    continue
                opposite = [fy for fy in years if sign(fy) == -cur]
                if opposite:
                    flips.append((max(opposite), n, cur))
            names = "|".join(self.full.values())
            m = re.search(rf"({names})より(低|高)かった最後の年度は([^で]+)で、その後は同額か、", text)
            if not flips:
                self.assertIsNone(m, short)
                continue
            fy, _, _ = max(flips)
            self.assertIsNotNone(m, short)
            self.assertEqual(m.group(3), label(fy), short)
            who = [n for f, n, c in flips if f == fy and self.full[n] == m.group(1)]
            self.assertTrue(who, (short, m.group(1)))
            self.assertEqual(m.group(2), "低" if [c for f, n, c in flips if n == who[0]][0] > 0 else "高", short)

    def test_the_gap_to_the_nearest_neighbour(self):
        for short, s in self.series.items():
            text = self.prose(short)
            near = adjacency.NEIGHBOURS[short]
            higher = [n for n in near if self.series[n][2026] > s[2026]]
            lower = [n for n in near if self.series[n][2026] < s[2026]]
            cand = ([min(higher, key=lambda n: self.series[n][2026])] if higher else [max(lower, key=lambda n: self.series[n][2026])] if lower else [])
            m = re.search(r"最も近い(上|下)の(\S+?)との差は、(\S+?)の([^。]+)。", text)
            ok = False
            if cand:
                x = cand[0]
                g0, g1 = abs(self.series[x][2016] - s[2016]), abs(self.series[x][2026] - s[2026])
                same_side = (self.series[x][2016] > s[2016]) == (self.series[x][2026] > s[2026])
                ok = same_side and g0 != 0 and g1 != 0
                if ok:
                    self.assertIsNotNone(m, short)
                    self.assertEqual(m.group(1), "上" if higher else "下", short)
                    self.assertEqual(m.group(3), "平成28年度", short)
                    want = (f"{g0:g}円から{g1:g}円に縮まりました" if g1 < g0 else f"{g0:g}円から{g1:g}円に広がりました" if g1 > g0 else f"{g0:g}円のまま変わっていません")
                    self.assertEqual(m.group(4), want, short)
                    tied = [self.full[n] for n in (higher or lower) if self.series[n][2026] == self.series[x][2026]]
                    self.assertIn(m.group(2), tied, short)
            if not ok:
                self.assertIsNone(m, short)

    def test_overtaking_in_ten_years(self):
        for short, s in self.series.items():
            up = sum(1 for o, so in self.series.items() if o != short and s[2016] < so[2016] and s[2026] > so[2026])
            down = sum(1 for o, so in self.series.items() if o != short and s[2016] > so[2016] and s[2026] < so[2026])
            text = self.prose(short)
            if up == 0 and down == 0:
                self.assertNotIn("追い越", text, short)
            elif down == 0:
                self.assertIn(f"この10年で、{up}都道府県を追い越しました。追い越された都道府県はありません。", text, short)
            elif up == 0:
                self.assertIn(f"この10年で、{down}都道府県に追い越されました。追い越した都道府県はありません。", text, short)
            else:
                self.assertIn(f"この10年で、{up}都道府県を追い越し、{down}都道府県に追い越されました。", text, short)

    def test_the_place_in_the_region_now_and_ten_years_ago(self):
        import sites.saichin.build as b
        for slug, rname, shorts in b.REGIONS:
            for short in shorts:
                s = self.series[short]
                p1 = 1 + sum(1 for o in shorts if self.series[o][2026] > s[2026])
                p0 = 1 + sum(1 for o in shorts if self.series[o][2016] > s[2016])
                want = (f"{rname}の{len(shorts)}都道府県の中での順位は、平成28年度の{p0}番目から{p1}番目に{'上がりました' if p1 < p0 else '下がりました'}。" if p1 != p0
                        else f"{rname}の{len(shorts)}都道府県の中での順位は、平成28年度と同じ{p1}番目です。")
                self.assertIn(want, self.prose(short), short)

    def test_the_year_of_reaching_1000_yen(self):
        first = {}
        for short, s in self.series.items():
            first[short] = next(fy for fy in YEARS_ if s[fy] is not None and s[fy] >= 1000)
        latest = max(first.values())
        for short, fy in first.items():
            earlier = sum(1 for v in first.values() if v < fy)
            same = sum(1 for v in first.values() if v == fy) - 1
            text = self.prose(short)
            tail = f"(同じ年度に届いたのは、ほかに{same}都道府県)。" if same else "(同じ年度に届いたのは、この都道府県だけ)。"
            if fy == latest and earlier:
                self.assertNotIn("1,000円以上になったのは", text, short)
            elif earlier == 0:
                self.assertIn(f"1,000円以上になったのは{label(fy)}で、全国で最も早い年度です{tail}", text, short)
            else:
                self.assertIn(f"1,000円以上になったのは{label(fy)}で、{earlier}都道府県が先に届いています{tail}", text, short)

    def test_the_guideline_sentence(self):
        for short, s in self.series.items():
            rank = articles.RANK_OF[short]
            guide = articles.GUIDELINE[rank]
            rise = s[2026] - s[2025]
            mates = [o for o in self.series if articles.RANK_OF[o] == rank]
            top = rise > guide and all(self.series[o][2026] - self.series[o][2025] <= rise for o in mates)
            text = self.prose(short)
            if rise == guide:
                self.assertIn(f"令和8年度の目安は{rank}ランクの+{guide}円で、決まった引上げ額は目安と同じです。", text, short)
            elif top:
                pos = 1
                self.assertIn(f"令和8年度の目安は{rank}ランクの+{guide}円で、決まった額は目安より{rise - guide}円多い+{rise}円です。同じ{rank}ランクの{len(mates)}都道府県の中で、上乗せが最も大きい県です。", text, short)
            else:
                self.assertNotIn("令和8年度の目安は", text, short)

    def test_the_rank_sentences(self):
        for short, s in self.series.items():
            text = self.prose(short)
            ranks = {fy: self.rank_in(fy, short) for fy in YEARS_ if s[fy] is not None}
            if len(set(ranks.values())) == 1:
                self.assertIn(f"全国順位は、昭和52年度から令和8年度まで、ずっと{ranks[2026]}位です。", text, short)
                continue
            diff = ranks[2016] - ranks[2026]
            was = f"10年前の平成28年度は{ranks[2016]}位でした。"
            want = (f"{was}この10年で、{diff}位も上がっています。" if diff >= 8 else f"{was}{diff}位上がっています。" if diff >= 3 else f"{was}{diff}位だけ上がりました。" if diff >= 1 else
                    f"10年前の平成28年度も{ranks[2016]}位で、順位は同じです。" if diff == 0 else f"{was}{-diff}位だけ下がりました。" if diff > -3 else
                    f"{was}{-diff}位下がっています。" if diff > -8 else f"{was}この10年で、{-diff}位も下がっています。")
            self.assertIn(want, text, short)

            def move(a, b):
                dd = ranks[a] - ranks[b]
                return "ほぼ横ばい" if abs(dd) <= 2 else f"{abs(dd)}位の{'上昇' if dd > 0 else '下落'}"
            if 1989 in ranks:
                self.assertIn(f"順位の動きを時代で分けると、昭和は{move(1977, 1989)}、平成は{move(1989, 2018)}、令和は{move(2018, 2026)}です。", text, short)
            else:
                self.assertNotIn("順位の動きを時代で分けると", text, short)                  # Kyoto: two rates in Heisei 1
            steps = [(ranks[a] - ranks[a + 1], a + 1) for a in YEARS_[:-1] if a in ranks and a + 1 in ranks]
            big = max(steps, key=lambda t: (abs(t[0]), 0)) if steps else None
            m = re.search(r"1年で順位が最も大きく動いたのは(\S+?)で、(\d+)位から(\d+)位に(上がりました|下がりました)。", text)
            if big and abs(big[0]) >= 4:
                self.assertIsNotNone(m, short)
                self.assertEqual(abs(int(m.group(2)) - int(m.group(3))), abs(big[0]), short)
                self.assertEqual(m.group(4), "上がりました" if int(m.group(3)) < int(m.group(2)) else "下がりました", short)
            else:
                self.assertIsNone(m, short)

    def test_the_counts_over_the_last_ten_revisions(self):
        nat = lambda fy: round(self.avg[fy]) - round(self.avg[fy - 1])  # noqa: E731
        ten = range(2017, 2027)
        for short, s in self.series.items():
            text = self.prose(short)
            reach = sum(1 for fy in ten if s[fy] - s[fy - 1] >= nat(fy))
            want = ("直近10回の改定で、引上げ額が全国加重平均の引上げ額に届いた年度は、一度もありません。" if reach == 0 else
                    f"直近10回の改定のうち、引上げ額が全国加重平均の引上げ額以上だったのは{reach}回だけです。" if reach <= 2 else
                    "直近10回の改定は、すべて全国加重平均の引上げ額以上でした。" if reach == 10 else
                    f"直近10回の改定のうち{reach}回は、引上げ額が全国加重平均の引上げ額以上でした。" if reach >= 8 else None)
            if want:
                self.assertIn(want, text, short)
            else:
                self.assertNotIn("全国加重平均の引上げ額以上", text, short)
            big = sum(1 for fy in ten if s[fy] - s[fy - 1] >= 50)
            if big == 0:
                self.assertIn("+50円以上の引上げは、直近10回の改定では一度もありません。", text, short)
            elif big == 1:
                first = next(fy for fy in ten if s[fy] - s[fy - 1] >= 50)
                self.assertIn(f"+50円以上の引上げは、直近10回では{label(first)}の1回だけです。", text, short)
            elif big >= 4:
                first = next(fy for fy in ten if s[fy] - s[fy - 1] >= 50)
                self.assertIn(f"+50円以上の引上げは、直近10回のうち{big}回あり、最初は{label(first)}です。", text, short)
            else:
                self.assertNotIn("+50円以上の引上げは", text, short)
            top = sum(1 for fy in ten if 1 + sum(1 for o in self.series.values() if o[fy] - o[fy - 1] > s[fy] - s[fy - 1]) <= 10)
            if top == 0:
                self.assertIn("直近10回の改定で、引上げ額が47都道府県の上位10位以内に入った年度は、一度もありません。", text, short)
            elif top >= 5:
                self.assertIn(f"直近10回の改定のうち{top}回は、引上げ額が47都道府県の上位10位以内でした。", text, short)
            else:
                self.assertNotIn("上位10位以内", text, short)

    def test_the_year_of_the_biggest_rise_is_mentioned_only_when_it_differs_from_the_nations(self):
        nat_up = {fy: round(self.avg[fy]) - round(self.avg[fy - 1]) for fy in range(2003, 2027)}
        nat_year = max(nat_up, key=lambda fy: (nat_up[fy], fy))
        for short, s in self.series.items():
            rises = {fy: round(s[fy] - s[fy - 1], 2) for fy in YEARS_[1:] if s[fy] is not None and s[fy - 1] is not None}
            mine = max(rises, key=lambda fy: (rises[fy], fy))
            text = self.prose(short)
            if mine == nat_year:
                self.assertNotIn("引上げ額が最も大きかった", text, short)
            else:
                self.assertIn(f"引上げ額が最も大きかった{label(mine)}は、全国加重平均の引上げ額が最も大きい{label(nat_year)}とは別の年度です。", text, short)

    def test_places(self):
        from sites.saichin.places import PLACES
        self.assertEqual(sorted(PLACES), sorted(build.SLUGS))
        for short, names in PLACES.items():
            self.assertEqual(len(set(names)), 3, short)
            self.assertTrue(all(n.endswith(("市", "区")) for n in names), short)
            a, b, c = names
            self.assertIn(f"{a}、{b}、{c}など、{self.full[short]}の中ならどこで働いても、適用される最低賃金は同じ{self.series[short][2026]:,}円です。", self.prose(short), short)


class SimilarityTest(SiteFixture):
    def test_the_measure_sees_a_page_that_only_swaps_names_and_numbers(self):
        page = self.read("hyogo/index.html")
        swapped = page.replace("兵庫県", "秋田県").replace("1,172", "1,090").replace("1172", "1090")
        a = ov.shingles(ov.normalise(ov.prose(page)))
        b = ov.shingles(ov.normalise(ov.prose(swapped)))
        self.assertEqual(ov.overlap(a, b), 1.0)

    def test_prefecture_pages_are_no_longer_the_same_text_with_other_numbers(self):
        slugs = list(build.SLUGS.values())
        sh = {s: ov.page_shingles(self.out / s / "index.html") for s in slugs}
        pairs = [ov.overlap(sh[a], sh[b]) for a, b in combinations(slugs, 2)]
        mean = sum(pairs) / len(pairs)
        self.assertLess(mean, 0.70, mean)                  # it was 0.96 when every page used one sentence frame, 0.82 with one frame per fact
        self.assertLess(max(pairs), 0.95)

    def test_every_page_has_prose_of_its_own_beyond_the_frame(self):
        for s in build.SLUGS.values():
            text = ov.prose(self.read(f"{s}/index.html"))
            self.assertGreater(len(text), 600, s)


class AreaStoryTest(SiteFixture):
    def prose(self, slug):
        return ov.prose(self.read(f"area/{slug}/index.html"))

    def facts(self):
        raw = _raw()
        am = {p["name"]: p["history"]["2026"]["amount"] for p in raw["prefectures"]}
        up = {p["name"]: p["history"]["2026"]["amount"] - p["history"]["2025"]["amount"] for p in raw["prefectures"]}
        eff = {p["name"]: p["history"]["2026"]["effective_date"] for p in raw["prefectures"]}
        full = {r["short"]: r["name"] for r in self.d["rows"]}
        return am, up, eff, full

    def test_the_rank_of_the_region_among_the_seven_is_by_simple_mean(self):
        am, up, eff, full = self.facts()
        means = {slug: sum(am[s] for s in shorts) / len(shorts) for slug, _, shorts in build.REGIONS}
        for slug, rname, shorts in build.REGIONS:
            text = self.prose(slug)
            rank = 1 + sum(1 for m in means.values() if m > means[slug])
            if rank == 1:
                self.assertIn("単純平均が最も高い地方です", text, slug)
            elif rank == 7:
                self.assertIn("単純平均が最も低い地方です", text, slug)
            else:
                self.assertIn(f"単純平均の高い順に並べると、{rank}番目です", text, slug)
            self.assertIn(f"単純平均{round(means[slug]):,}円", text, slug)

    def test_the_biggest_step_between_neighbours_is_recomputed_from_the_adjacency_table(self):
        am, up, eff, full = self.facts()
        for slug, rname, shorts in build.REGIONS:
            edges = [abs(am[a] - am[b]) for a in shorts for b in adjacency.NEIGHBOURS[a] if b in shorts and a < b]
            text = self.prose(slug)
            if not edges:
                continue
            self.assertIn(f"{max(edges)}円です。", text.split("県境をはさんで最も差が大きいのは、", 1)[1][:60], slug)
            if min(edges) != max(edges):
                tail = text.split("最も小さいのは、", 1)[1][:40]
                self.assertIn("同額" if min(edges) == 0 else f"{min(edges)}円の差", tail, slug)

    def test_raise_and_date_sentences(self):
        am, up, eff, full = self.facts()
        for slug, rname, shorts in build.REGIONS:
            text = self.prose(slug)
            hi, lo = max(up[s] for s in shorts), min(up[s] for s in shorts)
            self.assertIn(f"の+{hi}円、最も小さいのは", text, slug)
            self.assertIn(f"の+{lo}円で、{hi - lo}円の開きがあります", text, slug)
            d1, d2 = min(eff[s] for s in shorts), max(eff[s] for s in shorts)
            from datetime import date
            days = (date.fromisoformat(d2) - date.fromisoformat(d1)).days
            self.assertIn(f"{days}日の幅があります", text, slug)

    def test_the_table_of_the_seven_regions_is_on_every_region_page_with_the_current_one_marked(self):
        am, up, eff, full = self.facts()
        for slug, rname, shorts in build.REGIONS:
            page = self.read(f"area/{slug}/index.html")
            self.assertEqual(page.count("<tr class='on'>"), 1, slug)
            self.assertIn(f"<tr class='on'><td>{rname}</td><td>{round(sum(am[s] for s in shorts) / len(shorts)):,}円</td>", page, slug)
