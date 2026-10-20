"""The sentences of each prefecture page that are written only when they are true of that prefecture, and how alike the pages still are."""
import os
import re
import unittest
from itertools import combinations
from pathlib import Path

from sites.saichin import adjacency, build, history_old
from tests import saichin_overlap as ov
from tests.test_saichin_pages import CFG, SiteFixture, _raw  # noqa: F401
from tests.test_saichin_trend import all_series


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

    def test_the_highest_and_the_lowest_get_their_own_sentences(self):
        self.assertIn("全国で最も高い額で、2番目の額との差は1円です。", self.prose("tokyo"))
        self.assertIn("全国で最も低い額で、2番目に低い額との差は1円です。", self.prose("miyazaki"))
        for slug in ("tokyo", "miyazaki"):
            self.assertEqual(self.prose(slug).count("全国で最も高い額で") + self.prose(slug).count("全国で最も低い額で"), 1, slug)
        self.assertNotIn("全国で最も高い額で", self.prose("osaka"))

    def test_the_date_sentence_follows_the_dates(self):
        dates = sorted(r["effective_date"] for r in self.d["rows"])
        first, last = dates[0], dates[-1]
        for r in self.d["rows"]:
            text = self.prose(r["slug"])
            if r["effective_date"] == first:
                self.assertIn("全国で最も早い日", text, r["name"])
                self.assertIn(f"{dates.count(first)}都道府県が同じ日です", text, r["name"])
            elif r["effective_date"] == last:
                self.assertIn("全国で最も遅い日です", text, r["name"])
            else:
                earlier = sum(1 for x in dates if x < r["effective_date"])
                self.assertIn(f"早い方から数えて{earlier + 1}番目の日です", text, r["name"])

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

    def test_the_milestone_sentence_matches_the_workbook(self):
        raw = _raw()
        for r in self.d["rows"]:
            amts = next(p for p in raw["prefectures"] if p["name"] == r["short"])["history"]
            now = amts["2026"]["amount"]
            text = self.prose(r["slug"])
            if now % 100:
                nxt = (now // 100 + 1) * 100
                self.assertIn(f"次の節目の{nxt:,}円まで、あと{nxt - now}円です", text, r["name"])
            top = max((t for t in (1000, 1100, 1200) if now >= t), default=None)
            if top:
                self.assertIn(f"{top:,}円以上になったのは", text, r["name"])
            else:
                self.assertIn("1,000円には、まだ届いていません", text, r["name"])

    def test_the_monthly_line_and_the_130_line(self):
        raw = _raw()
        for r in self.d["rows"]:
            now = next(p for p in raw["prefectures"] if p["name"] == r["short"])["history"]["2026"]["amount"]
            text = self.prose(r["slug"])
            low = -(-(now * 2000) // 1200) * 100              # the monthly pay (8 hours x 250 days / 12 months) at the minimum wage, rounded up to 100 yen
            self.assertIn(f"手当を除いた月給が{low:,}円を下回ると、最低賃金を下回ります", text, r["name"])
            a20 = now * 20 * 52
            if a20 > 1_300_000:
                self.assertIn(f"週20時間でも年収が130万円を超えます({a20 / 10000:.1f}万円)", text, r["name"])
            else:
                self.assertIn(f"年収が130万円になるのは週{1_300_000 / (52 * now):.1f}時間です", text, r["name"])


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
        self.assertLess(mean, 0.88, mean)                  # it was 0.96 when every page used one sentence frame
        self.assertLess(sum(1 for p in pairs if p > 0.95) / len(pairs), 0.10)

    def test_every_page_has_prose_of_its_own_beyond_the_frame(self):
        for s in build.SLUGS.values():
            text = ov.prose(self.read(f"{s}/index.html"))
            self.assertGreater(len(text), 900, s)


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
