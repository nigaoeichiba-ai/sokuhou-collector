"""商品比較の「ひとこと」と内訳バー、Amazonだけのページ(/compare/amazon/)、ギフトモールのリンク。"""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import amazonrank, build, commas, compare, compare_fetch, content, quality
from tests.test_yorokobu_compare import CFG, FIX, item
from tests.yorokobu_data import with_musts

A8 = "4BEGD8+UYL0A+4DMG+5YJRM"


def row(**kw):
    base = {"effective": 2000, "reviews": 120, "rating": 4.6, "free_shipping": True, "gift": True, "parts": (30, 30, 10, 10)}
    base.update(kw)
    return base


class SayTest(unittest.TestCase):
    def test_it_names_the_place_of_the_price_the_reviews_and_what_is_missing(self):
        s = compare.say(row(), 1, 20, 2500)
        self.assertIn("いちばん安い水準", s)
        self.assertIn("★4.60で120件と多く", s)
        self.assertIn("送料無料でギフト対応の表示もあります", s)
        s = compare.say(row(effective=4000, reviews=0, rating=0, free_shipping=False, gift=False), 19, 20, 2500)
        for needle in ("高い方", "中央値より1,500円高く", "レビューはまだありません", "送料は別にかかります", "ギフト対応の表示はありません"):
            self.assertIn(needle, s, needle)
        self.assertIn("参考程度", compare.say(row(reviews=4, rating=5.0), 7, 20, 2000))
        self.assertIn("低め", compare.say(row(reviews=400, rating=3.7), 7, 20, 2000))

    def test_it_never_gives_a_verdict_on_the_product_and_passes_the_language_gate(self):
        for rank in (1, 2, 3, 4, 10, 18, 20):
            for rv, rt in ((0, 0.0), (3, 5.0), (50, 4.6), (50, 4.2), (400, 4.7), (400, 3.6)):
                for ship in (True, False):
                    for gift in (True, False):
                        s = compare.say(row(effective=1000 + rank * 90, reviews=rv, rating=rt, free_shipping=ship, gift=gift), rank, 20, 1900)
                        self.assertEqual(quality.language_problems(s, "say"), [], s)
                        for sentence in re.split(r"(?<=。)", s):
                            self.assertEqual(commas.lighten(sentence), sentence, sentence)
                        self.assertNotRegex(s, "おすすめ|最安|買い|間違い|失敗しない")


class TiesTest(unittest.TestCase):
    def test_products_with_the_same_price_get_the_same_place(self):
        g = {"rows": [row(code=f"c{i}", effective=p) for i, p in enumerate((1000, 2000, 2000, 2000, 3000))]}
        places = compare.places(g["rows"])
        self.assertEqual([places[f"c{i}"] for i in range(5)], [1, 2, 2, 2, 5])


class StatTest(unittest.TestCase):
    def test_four_bars_each_a_share_of_its_own_maximum_with_the_points_written_out(self):
        html = compare.stat_html(row(parts=(20, 30, 10, 0)))
        self.assertEqual(html.count("<li>"), 4)
        for needle in ("width:50%", "width:75%", "width:100%", "width:0%", ">20<small>/40</small>", ">30<small>/40</small>", ">10<small>/10</small>", ">0<small>/10</small>"):
            self.assertIn(needle, html, needle)


class AmazonRankTest(unittest.TestCase):
    AXES = [{"key": k, "label": k, "note": k} for k in "abcd"]

    def days(self):
        def e(asin, date_):
            return {"asin": asin, "name": asin, "kind": "k", "headline": "h", "good": "g", "care": "c", "mood": "relax-1"}
        return [{"date": "2026-10-13", "amazon": [e("A1", 1), e("A2", 1), e("A3", 1)]}, {"date": "2026-10-14", "amazon": [e("A3", 1), e("A4", 1), e("A5", 1)]}]

    def test_the_total_is_the_sum_of_the_marks_scaled_to_a_hundred_and_ties_go_to_the_fewer_cautions(self):
        data = {"axes": self.AXES, "scores": {"A1": [5, 5, 5, 5], "A2": [3, 3, 3, 3], "A3": [4, 4, 4, 4], "A4": [5, 3, 5, 3], "A5": [5, 3, 3, 5]}}
        out = amazonrank.ranked(self.days(), data)
        self.assertEqual([e["asin"] for e in out], ["A1", "A5", "A3", "A4", "A2"])      # three products at 80: the one with the fewest cautions (care 5, 4, 3) first
        self.assertEqual([e["total"] for e in out], [100, 80, 80, 80, 60])
        self.assertEqual({e["asin"]: e["date"] for e in out}["A3"], "2026-10-14")       # an ASIN picked on two days counts once, with the newest entry

    def test_a_product_without_marks_or_with_the_wrong_number_of_marks_is_not_listed(self):
        data = {"axes": self.AXES, "scores": {"A1": [5, 5, 5, 5], "A2": [5, 5, 5]}}
        self.assertEqual([e["asin"] for e in amazonrank.ranked(self.days(), data)], ["A1"])

    def test_the_marks_file_covers_only_real_products_with_marks_from_one_to_five(self):
        data = amazonrank.load()
        asins = {a["asin"] for d in content.load()["daily"] for a in d["amazon"]}
        self.assertTrue(set(data["scores"]) <= asins, "marks for a product that is in no daily list")
        for asin, marks in data["scores"].items():
            self.assertEqual(len(marks), len(data["axes"]), asin)
            self.assertTrue(all(isinstance(m, int) and 1 <= m <= amazonrank.MAXMARK for m in marks), asin)
        self.assertGreaterEqual(len(amazonrank.ranked(content.load()["daily"], data)), 30)


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        gs = {g["slug"]: g for g in compare_fetch.groups()}
        cls.cat = gs["catalog-gift"]
        raw = {"version": 1, "fetched_at": "2026-10-14T05:40:00+09:00",
               "groups": {slug: [item(i, price=1000 + 150 * i, reviews=20 + 7 * i, ship=i % 3 != 0, gift=i % 2 == 0, name=f"{gs[slug]['words'][0]} ギフト {i}") for i in range(1, 16)] for slug in ("catalog-gift", "tumbler")}}
        cls.cfg = {**CFG, "shaddy_a8mat": A8}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, cls.cfg, cls.root, release=True, today=date(2026, 10, 14), compare_data=raw)
        cls.bare = tempfile.TemporaryDirectory()
        build.render_site(cls.c, items, CFG, Path(cls.bare.name), release=True, today=date(2026, 10, 14), compare_data=raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.bare.cleanup()

    def read(self, rel, root=None):
        return (Path(root or self.root.as_posix()) / rel).read_text(encoding="utf-8")

    def test_every_row_has_its_reading_and_four_bars_and_the_formula_says_where_they_come_from(self):
        html = self.read("compare/tumbler/index.html")
        rows = html.count('<li class="cmp-row"')
        self.assertEqual(rows, 15)
        self.assertEqual(html.count('class="cmp-why"'), rows)
        self.assertEqual(html.count('class="cmp-say"'), rows)
        self.assertEqual(html.count('<ul class="cmp-stat"'), rows)
        self.assertEqual(html.count('<span class="cmp-sl">'), rows * 4)
        self.assertIn("商品を使った感想ではありません", html)

    def test_the_amazon_page_ranks_scored_products_with_no_price_picture_or_review_of_amazon(self):
        html = self.read("compare/amazon/index.html")
        n = html.count('<li class="cmp-row az-row"')
        self.assertGreaterEqual(n, 30)
        self.assertEqual(html.count('<ul class="cmp-stat"'), n)
        totals = [int(x) for x in re.findall(r'<div class="cmp-score" title="編集点 (\d+)点">', html)]
        self.assertEqual(totals, sorted(totals, reverse=True))
        for needle in ("編集点のつけ方", "購入者のレビューも入っていません", "価格・在庫・購入者の評価は、Amazonのページでご確認ください", "Amazonのアソシエイトとして"):
            self.assertIn(needle, html, needle)
        self.assertEqual(len(re.findall(r'href="https://www\.amazon\.co\.jp/dp/[A-Z0-9]{10}\?tag=test-22"', html)), n * 3)       # image, title and button: the same link
        text = re.sub(r"<[^>]+>", " ", html)
        self.assertNotIn("★", text)
        self.assertNotRegex(text, r"[0-9,]{3,}円")
        self.assertNotIn("m.media-amazon.com", html)                                    # no Amazon picture
        self.assertIn("/compare/amazon/", self.read("sitemap.xml"))
        self.assertIn('href="/compare/amazon/"', self.read("compare/index.html"))
        self.assertIn('href="/compare/amazon/"', self.read("compare/tumbler/index.html"))

    def test_no_amazon_page_without_the_associates_id(self):
        cfg = {**CFG, "amazon_tracking_id": None}
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), self.c)
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(self.c, items, cfg, Path(tmp), release=True, today=date(2026, 10, 14))
            self.assertFalse((Path(tmp) / "compare" / "amazon").exists())

    def test_the_gift_mall_link_is_an_a8_affiliate_link_on_the_hub_and_on_gift_kinds_only(self):
        link = (f'<a href="https://px.a8.net/svt/ejp?a8mat={A8}" rel="nofollow">【シャディ公式】内祝や、お返しも！ギフト専門店【シャディギフトモール】</a>'      # A8's own code: its words, href and rel only
                f'<img border="0" width="1" height="1" src="https://www11.a8.net/0.gif?a8mat={A8}" alt="">')
        self.assertIn(link, self.read("compare/index.html"))
        self.assertIn(link, self.read("compare/catalog-gift/index.html"))
        self.assertNotIn("px.a8.net", self.read("compare/tumbler/index.html"))          # a tumbler is not what the gift mall is for
        self.assertIn("この表に入っていません", self.read("compare/catalog-gift/index.html"))
        self.assertNotIn("px.a8.net", self.read("compare/index.html", self.bare.name))   # no id in the config, no link

    def test_the_real_config_has_the_gift_mall_id_in_the_a8_form(self):
        cfg = json.loads((Path(build.__file__).parent / "config.json").read_text(encoding="utf-8"))
        self.assertRegex(cfg["shaddy_a8mat"], r"^[0-9A-Z]{6}\+[0-9A-Z]{5}\+[0-9A-Z]{4}\+[0-9A-Z]{5}$")


if __name__ == "__main__":
    unittest.main()
