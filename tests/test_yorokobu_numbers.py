import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, numberlists
from sokuhou import rakuten, sitecheck
from tests.test_yorokobu_fetch import raw_item

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
FILTERS = {"min_price": 500, "ng_words": ["訳あり", "中古"]}
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


def prod(code, reviews, rating, price=3000, name=None):
    return rakuten.normalize(raw_item(code, price, reviews=reviews, rating=rating, name=name or f"ギフト用 焼き菓子 {code} 詰め合わせ"))


def pairs_of(*items):
    return {"birthday-boyfriend": {"ideas": [{"label": "x", "type": "実用品", "query": "q", "why": "w", "items": list(items)}], "tiers": {}}}


class RulesTest(unittest.TestCase):
    def lists(self, items):
        v = numberlists.view(pairs_of(*items), FILTERS)
        return {L["slug"]: [i["code"] for i in L["items"]] for L in (v["lists"] if v else [])}

    def test_each_list_is_exactly_its_rule_and_the_ranges_do_not_overlap(self):
        items = ([prod(f"big{i}", 10000 + i, 4.5) for i in range(6)] + [prod(f"mid{i}", 3000 + i, 4.4) for i in range(6)] +
                 [prod(f"low{i}", 1000 + i, 4.3) for i in range(6)] + [prod(f"gem{i}", 100 + i, 4.8) for i in range(6)] +
                 [prod(f"cheap{i}", 400 + i, 4.7, price=1500) for i in range(6)])
        got = self.lists(items)
        self.assertEqual(sorted(got["reviews-10000"]), sorted(f"big{i}" for i in range(6)))
        self.assertEqual(sorted(got["reviews-3000"]), sorted(f"mid{i}" for i in range(6)))
        self.assertEqual(sorted(got["reviews-1000"]), sorted(f"low{i}" for i in range(6)))
        self.assertEqual(sorted(got["hidden-gems"]), sorted(f"gem{i}" for i in range(6)))
        self.assertEqual(sorted(got["cheap-and-loved"]), sorted(f"cheap{i}" for i in range(6)))

    def test_boundaries_ratings_and_the_sort_order(self):
        items = [prod("a", 10000, 4.3), prod("b", 9999, 4.3), prod("c", 10000, 4.29), prod("d", 12000, 4.9)] + [prod(f"z{i}", 20000 + i, 4.5) for i in range(4)]
        got = self.lists(items)["reviews-10000"]
        self.assertIn("a", got)                      # 10,000 reviews and 4.3 are inside
        self.assertNotIn("b", got)                   # 9,999 reviews is not
        self.assertNotIn("c", got)                   # 4.29 is below 4.3
        self.assertEqual(got[0], "z3")               # most reviews first
        self.assertEqual(got[-1], "a")

    def test_a_list_with_fewer_than_six_products_has_no_page(self):
        self.assertEqual(self.lists([prod(f"big{i}", 10000 + i, 4.5) for i in range(5)]), {})

    def test_products_the_site_would_not_show_are_left_out_and_a_product_counts_once(self):
        items = [prod(f"big{i}", 10000 + i, 4.5) for i in range(6)]
        bad = [prod("ng", 20000, 4.9, name="訳あり ギフト 詰め合わせ"), prod("cheap", 30000, 4.9, price=300)]
        pairs = pairs_of(*items, *bad)
        pairs["other"] = {"ideas": [], "tiers": {"t": [items[0], items[0]]}}             # the same product on another page
        v = numberlists.view(pairs, FILTERS)
        codes = [i["code"] for i in v["lists"][0]["items"]]
        self.assertEqual(sorted(codes), sorted(i["code"] for i in items))
        self.assertEqual(v["pool"], 6)

    def test_no_products_no_lists(self):
        self.assertIsNone(numberlists.view({}, FILTERS))


class BuildTest(unittest.TestCase):
    def build(self, extra):
        c = content.load(FIX)
        items = copy.deepcopy(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        items["pairs"]["birthday-boyfriend"]["ideas"][0]["items"] += extra
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "site"
        build.render_site(c, items, CFG, out, release=True, today=date(2026, 10, 7))
        return out

    def test_the_hub_and_list_pages_are_built_linked_and_labelled(self):
        out = self.build([prod(f"big{i}", 10000 + i, 4.6) for i in range(7)])
        self.assertTrue((out / "numbers/index.html").exists())
        self.assertTrue((out / "numbers/reviews-10000/index.html").exists())
        self.assertFalse((out / "numbers/hidden-gems/index.html").exists())
        home = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/numbers/"', home)
        page = (out / "numbers/reviews-10000/index.html").read_text(encoding="utf-8")
        self.assertIn("レビュー件数が10,000件以上で、レビュー平均が4.3以上", page)
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=", page)
        self.assertIn('aria-label="広告を含みます">PR</span>', page)
        self.assertIn("保証するものではありません", page)
        self.assertIn("/numbers/reviews-10000/", (out / "sitemap.xml").read_text(encoding="utf-8"))
        problems = [p for p in sitecheck.check_dir(out, CFG["site_url"]) if "numbers" in p]
        self.assertEqual(problems, [])

    def test_without_enough_products_there_is_no_numbers_section_at_all(self):
        out = self.build([])
        self.assertFalse((out / "numbers").exists())
        self.assertNotIn("/numbers/", (out / "index.html").read_text(encoding="utf-8"))
        build.RANKING_ON = False


if __name__ == "__main__":
    unittest.main()
