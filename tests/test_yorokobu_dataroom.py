"""The data room: charts of the site's own products and of public statistics; every sentence with a number is made from the data of that build."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, dataroom, ranking
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


def inflated(copies: int = 14) -> dict:
    """The fixture products, each copied with other prices (so that there are enough products for a chart)."""
    items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
    prices = [1500, 2800, 3500, 4200, 5200, 6100, 7500, 9800, 12000, 16000, 24000]
    n = 0
    for v in items["pairs"].values():
        for idea in v.get("ideas", []):
            extra = []
            for it in idea["items"]:
                for k in range(copies):
                    c = copy.deepcopy(it)
                    n += 1
                    c.update(code=f'{it["code"]}-x{n}', price=prices[n % len(prices)], name=f'{it["name"]} {n}', free_shipping=(n % 3 != 0), gift=(n % 2 == 0))
                    extra.append(c)
            idea["items"].extend(extra)
    return items


def render(tmp: Path, items: dict | None, c: dict | None = None) -> Path:
    out = tmp / "site"
    build.render_site(c or content.load(FIX), items, CFG, out, release=items is not None, today=date(2026, 10, 7))
    return out


class DataRoomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rows = (dataroom.MIN_ROWS, dataroom.MIN_PER_ROW)
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = 2, 8                       # the fixture has two events and two people
        cls.items = inflated()
        cls.out = render(Path(cls.tmp.name), cls.items)
        cls.c = content.load(FIX)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = cls.rows
        build.RANKING_ON = False
        build.DATA_ON = False

    def read(self, rel: str) -> str:
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_hub_and_the_chart_pages_exist_and_are_linked_from_the_nav_and_the_home_page(self):
        for rel in ("data/index.html", "data/price-bands/index.html", "data/occasion-prices/index.html", "data/mothers-day-budget/index.html", "data/births-marriages/index.html"):
            self.assertTrue((self.out / rel).exists(), rel)
        for rel in ("index.html", "tool/index.html", "data/price-bands/index.html"):
            self.assertIn('<a href="/data/"', self.read(rel), rel)               # the same nav on every page, also on the pages another module draws
        self.assertIn('class="findings"', self.read("index.html"))
        self.assertIn("/data/price-bands/", self.read("sitemap.xml"))

    def test_the_price_band_numbers_are_the_real_ones(self):
        d = build.prepare(self.c, self.items, CFG)
        items = dataroom.all_products(d)
        html = self.read("data/price-bands/index.html")
        self.assertIn(f"{len(items):,}点", html)
        for s in dataroom.band_stats(items):
            self.assertIn(f'{s["n"]:,}点({s["share"]:.0f}%)', html, s["label"])
        self.assertEqual(sum(s["n"] for s in dataroom.band_stats(items)), len(items))      # every product is in exactly one band
        best = max((s for s in dataroom.band_stats(items) if s["n"] >= 3), key=lambda s: s["rating"])
        self.assertIn(f"{best['label']}で{best['rating']:.2f}です", html)

    def test_every_chart_has_its_source_and_its_numbers_as_a_table(self):
        for rel in ("data/price-bands/index.html", "data/occasion-prices/index.html", "data/mothers-day-budget/index.html", "data/births-marriages/index.html"):
            html = self.read(rel)
            figures = re.findall(r"<figure class=\"chart\">(.*?)</figure>", html, re.S)
            self.assertGreaterEqual(len(figures), 1, rel)
            for f in figures:
                self.assertIn("出典:", f.split("<figcaption>")[1], rel)
                self.assertIn("<table", f, rel)
        self.assertIn("日比谷花壇", self.read("data/mothers-day-budget/index.html"))
        self.assertIn("総務省統計局", self.read("data/births-marriages/index.html"))

    def test_the_mothers_day_page_puts_the_survey_next_to_the_products_and_says_what_differs(self):
        html = self.read("data/mothers-day-budget/index.html")
        self.assertIn("37.0%", html)                                                  # the survey figure of 2025
        self.assertIn("母の日の商品の価格(", html)                                   # the second chart (the site's own products)
        self.assertRegex(html, r"10,000円以上の割合は、2023年の7\.6%から、2025年の9\.0%へと増えています")

    def test_the_price_ranges_are_ordered_and_use_quartiles(self):
        self.assertEqual(dataroom.quartiles([1, 2, 3, 4, 5]), (2.0, 3.0, 4.0))
        a, m, b = dataroom.quartiles([1000, 2000, 3000, 4000])
        self.assertLess(a, m)
        self.assertLess(m, b)
        html = self.read("data/occasion-prices/index.html")
        meds = [int(x.replace(",", "")) for x in re.findall(r'<span class="hb-v">([\d,]+)円\(', html)]
        self.assertGreater(len(meds), 3)
        o = html.split("贈る相手ごとの")[0]                                           # the occasions chart: sorted by median, lowest first
        first = [int(x.replace(",", "")) for x in re.findall(r'<span class="hb-v">([\d,]+)円\(', o)]
        self.assertEqual(first, sorted(first))

    def test_the_pages_pass_the_site_check_and_carry_no_script(self):
        problems = [p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "/data/" in p or "data/" in p]
        self.assertEqual(problems, [])
        self.assertNotIn("<script", self.read("data/price-bands/index.html").split("<main")[1].split("</main>")[0])

    def test_with_too_few_products_there_is_no_price_chart_and_without_statistics_no_room_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = render(Path(tmp), json.loads((FIX / "items.json").read_text(encoding="utf-8")))
            self.assertFalse((out / "data/price-bands").exists())                    # 12 products are not a chart
            self.assertTrue((out / "data/births-marriages").exists())                # the public statistics need no products
        with tempfile.TemporaryDirectory() as tmp:
            c = content.load(FIX)
            c["stats"] = {}
            out = render(Path(tmp), json.loads((FIX / "items.json").read_text(encoding="utf-8")), c)
            self.assertFalse((out / "data").exists())
            self.assertNotIn('href="/data/"', (out / "index.html").read_text(encoding="utf-8"))
        build.DATA_ON = False

    def test_the_ranking_price_page_needs_four_segments_with_numbers(self):
        from tests.test_yorokobu_ranking import codes, day
        for n, expect in ((3, False), (4, True)):
            segs = {k: day(codes(16, k)) for k in ("f20", "m20", "f30", "m30")[:n]}
            store = ranking.update(ranking.update(None, segs, date(2026, 10, 6)), segs, date(2026, 10, 7))
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "s"
                build.render_site(content.load(FIX), self.items, CFG, out, release=True, today=date(2026, 10, 7), ranking=store)
                self.assertEqual((out / "data/ranking-prices/index.html").exists(), expect, n)
                if expect:
                    html = (out / "data/ranking-prices/index.html").read_text(encoding="utf-8")
                    self.assertIn("3,000円", html)
                    self.assertEqual(len(re.findall(r"<figure class=\"chart\">", html)), 2)
        build.RANKING_ON = False

    def test_a_statistics_table_that_does_not_add_up_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for f in FIX.iterdir():
                (Path(tmp) / f.name).write_bytes(f.read_bytes())
            s = json.loads((Path(tmp) / "stats.json").read_text(encoding="utf-8"))
            s["survey_budget"]["mothers-day"]["years"]["2025"][0] = 35.0              # 100% + 14.9
            (Path(tmp) / "stats.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(Path(tmp))
            s["survey_budget"]["mothers-day"]["years"]["2025"][0] = 20.1
            s["vital"]["births"]["series"]["2024"] = "686173"                           # a number that is a string
            (Path(tmp) / "stats.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(Path(tmp))


if __name__ == "__main__":
    unittest.main()
