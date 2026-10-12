"""What a page says against what it shows: ideas keep only products of their own kind (must-words), a person's 「喜ばれやすいもの」 lines lead to products of
that kind, the first products of a page are of different kinds, and the real content has the words for all of it."""
import copy
import json
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from sites.yorokobu import build, consistency, content, dataroom, fetch, picking, refresh, relevance
from sokuhou.sitekit import BuildError
from tests.test_yorokobu_dataroom import CFG, FIX, inflated
from tests.test_yorokobu_fetch import CONTENT, FakeTransport, client, raw_item
from tests.test_yorokobu_refresh import PICKS, item_for


def it(code, name, price=3000, shop="s", reviews=100, rating=4.5):
    return {"code": code, "name": name, "price": price, "shop_code": shop, "shop": shop, "reviews": reviews, "rating": rating, "available": True,
            "free_shipping": True, "gift": False, "appoint": False, "image": "https://t/x.jpg", "url": "https://item.rakuten.co.jp/s/x/"}


class MustTest(unittest.TestCase):
    def test_a_title_has_to_name_the_kind_and_spellings_are_compared_as_one(self):
        must = ["タンブラー", "ボトル", "水筒"]
        self.assertTrue(relevance.fits_idea("真空 断熱 ステンレス タンブラー 保温", must))
        self.assertTrue(relevance.fits_idea("ｻｰﾓ ボトル 500ml", must))               # half-width kana
        self.assertTrue(relevance.fits_idea("サーモス 水筒 直飲み", must))
        self.assertFalse(relevance.fits_idea("名刺入れ 名入れ 本革 メンズ", must))     # what the search returned for 保温タンブラー
        self.assertTrue(relevance.fits_idea("何でも", None))                            # an idea without words accepts everything
        self.assertTrue(relevance.fits_idea("何でも", []))

    def test_pick_keeps_only_products_of_the_kind(self):
        filters = {"min_review_count": 10, "min_review_average": 4.0, "ng_words": [], "max_per_list": 5, "tiers": []}
        items = [it("a", "名刺入れ メンズ"), it("b", "保温 タンブラー メンズ", shop="t"), it("c", "水筒 ステンレス", shop="u")]
        got = picking.pick(items, None, filters, must=["タンブラー", "水筒"])
        self.assertEqual({i["code"] for i in got}, {"b", "c"})
        self.assertEqual(len(picking.pick(items, None, filters)), 3)

    def test_the_content_loader_refuses_a_bad_must(self):
        for bad in ("タンブラー", [], [""], ["a" * 13], [1]):
            with self.assertRaises(BuildError):
                content.check_must({"must": bad}, "t")
        content.check_must({"must": ["タンブラー"]}, "t")
        content.check_must({}, "t")

    def test_the_real_content_has_the_words_for_every_idea_and_every_line_of_likes(self):
        c = content.load()
        n = 0
        for p in content.pages(c):
            for i, idea in enumerate(p["ideas"]):
                n += 1
                self.assertTrue(idea.get("must"), f"{content.pair_key(p)}#{i} {idea['label']} has no must")
                self.assertFalse(set(idea["must"]) & {"ギフト", "プレゼント", "セット", "日本製", "人気"}, f"{content.pair_key(p)}#{i}: a word every title has")
        self.assertGreater(n, 700)
        for r in c["recipients"]:
            self.assertEqual(len(r["like_rows"]), len(r["likes"]), r["slug"])
            for row in r["like_rows"]:
                self.assertEqual(len(row["queries"]), 3, r["slug"])
                self.assertGreaterEqual(len(row["must"]), 3, r["slug"])

    def test_the_words_pass_the_products_that_were_curated_for_the_idea(self):
        """The candidates the editors chose from (real titles of an earlier fetch): the curated picks are of their idea's kind, nearly always."""
        cand = json.loads((build.ROOT / "data" / "yorokobu_candidates.json").read_text(encoding="utf-8"))["pairs"]
        picks = json.loads((build.HERE / "content" / "picks.json").read_text(encoding="utf-8"))
        c = content.load()
        spec = {content.pair_key(p): p["ideas"] for p in content.pages(c)}
        total = bad = 0
        for key, sels in picks.items():
            names = {x["code"]: x["name"] for lst in cand.get(key, []) for x in lst}
            for i, sel in enumerate(sels):
                for pk in sel["picks"]:
                    if pk["code"] in names and i < len(spec.get(key, [])):
                        total += 1
                        bad += not relevance.fits_idea(names[pk["code"]], spec[key][i].get("must"))
        self.assertGreater(total, 1000)
        self.assertLess(bad / total, 0.02, f"{bad} of {total} curated picks are not of their idea's kind")


class SpreadTest(unittest.TestCase):
    def test_the_best_of_each_kind_comes_first_and_one_shop_is_not_everything(self):
        necklaces = [it(f"n{i}", f"ネックレス{i}", reviews=5000 - i, shop="a") for i in range(5)]
        bath = [it("b0", "バスソルト", reviews=300, shop="b"), it("b1", "入浴剤", reviews=200, shop="c")]
        tea = [it("t0", "日本茶", reviews=400, shop="d")]
        got = build.spread([necklaces, bath, tea], 4)
        self.assertEqual([i["code"] for i in got], ["n0", "t0", "b0", "n1"])               # one of each kind, then the next best (not four necklaces)
        self.assertLessEqual(sum(1 for i in build.spread([necklaces], 5) if i["shop_code"] == "a"), 2)
        self.assertEqual(build.spread([], 4), [])


class FetchTest(unittest.TestCase):
    def content_with_likes(self):
        c = copy.deepcopy(CONTENT)
        c["recipients"] = [{"slug": "boyfriend", "likes": ["財布", "名入れ"],
                            "like_rows": [{"title": "財布", "queries": ["メンズ 財布", "メンズ カードケース"], "must": ["財布", "カードケース"]},
                                          {"title": "ペン", "queries": ["名入れ ペン"], "must": ["ペン"]}]}]
        return c

    def test_each_line_of_likes_gets_products_of_its_kind_the_best_of_each_search_in_turn(self):
        def items_for(url):
            if "%E8%B2%A1%E5%B8%83" in url and "%E3%82%AB%E3%83%BC%E3%83%89" not in url:               # メンズ 財布
                return [raw_item("w1", 3000, "s1", name="メンズ 財布 本革"), raw_item("x1", 3000, "s2", name="ベルト メンズ")]
            if "%E3%82%AB%E3%83%BC%E3%83%89" in url:
                return [raw_item("c1", 2500, "s3", name="カードケース 薄型")]
            return [raw_item("p1", 2000, "s4", name="名入れ ボールペン"), raw_item("p2", 2000, "s5", name="名入れ タオル")]
        out = fetch.collect_likes(self.content_with_likes(), client(FakeTransport(items_for)), {"errors": 0})
        self.assertEqual([[i["code"] for i in line] for line in out["boyfriend"]], [["w1", "c1"], ["p1"]])      # the belt and the towel are not what the line is about

    def test_an_idea_that_comes_out_short_gets_other_searches_and_only_the_right_kind_stays(self):
        c = copy.deepcopy(CONTENT)
        for p in c["pairs"]:
            for idea in p["ideas"]:
                idea["must"] = ["財布"] if idea["label"] == "財布" else ["財布", "ペン"]
        urls = []

        def items_for(url):
            urls.append(url)
            return [raw_item("a1", 2000, "s1", name="メンズ 財布 a"), raw_item("a2", 2100, "s2", name="帽子 メンズ"), raw_item("a3", 2200, "s3", name="財布 b")]
        data = fetch.collect(c, client(FakeTransport(items_for)), now=datetime(2026, 10, 12, 7, 0))
        ideas = data["pairs"]["birthday-boyfriend"]["ideas"]
        self.assertEqual({i["code"] for i in ideas[0]["items"]}, {"a1", "a3"})                    # the hat is out
        self.assertEqual(ideas[0]["must"], ["財布"])
        self.assertGreater(len(urls), 4)                                                           # a short idea was searched again


class RefreshTest(unittest.TestCase):
    def test_a_curated_pick_that_is_not_of_the_kind_is_replaced_by_a_backup_that_is(self):
        c = copy.deepcopy(CONTENT)
        c["pairs"][0]["ideas"][0]["must"] = ["財布"]

        def transport(url):
            res = item_for(url)
            if "itemCode=p1" in url:
                res[0]["itemName"] = "名刺入れ 本革"                      # curated once, but a card case is not a wallet
            elif "itemCode=" in url:
                res[0]["itemName"] = "二つ折り 財布 本革"
            return res
        data = refresh.refresh(c, client(FakeTransport(transport)), copy.deepcopy(PICKS), now=datetime(2026, 10, 12, 7, 0))
        codes = [i["code"] for i in data["pairs"]["birthday-boyfriend"]["ideas"][0]["items"]]
        self.assertNotIn("p1", codes)
        self.assertEqual(codes, ["p2", "b1"])


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cdir = Path(cls.tmp.name) / "c"
        cdir.mkdir()
        for f in FIX.iterdir():
            (cdir / f.name).write_bytes(f.read_bytes())
        rec = json.loads((cdir / "recipients.json").read_text(encoding="utf-8"))
        cls.words = []
        for r in rec["recipients"]:
            r["like_rows"] = [{"title": f"種類{i}", "queries": [f"検索{i}a", f"検索{i}b", f"検索{i}c"], "must": [f"語{i}"]} for i in range(len(r["likes"]))]
        (cdir / "recipients.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        cls.c = content.load(cdir)
        items = inflated(copies=3)
        n = 0
        for v in items["pairs"].values():                                    # the first line's word is in some titles, the second line's in none
            for idea in v.get("ideas", []):
                for x in idea["items"]:
                    n += 1
                    if n % 3 == 0:
                        x["name"] += " 語0"
        cls.items = items
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, items, CFG, cls.out, release=True, today=date(2026, 10, 12))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = build.DATA_ON = False

    def read(self, rel: str) -> str:
        return (self.out / rel).read_text(encoding="utf-8")

    def test_every_line_of_likes_has_a_heading_and_a_way_to_search_and_only_products_of_its_kind(self):
        html = self.read("for/boyfriend/index.html")
        rows = re.findall(r'<li class="like-row" id="like-\d+">(.*?)</li></ol>|<li class="like-row" id="like-\d+">(.*?)(?=<li class="like-row"|</ol>)', html, re.S)
        self.assertEqual(html.count('class="like-row"'), 3)
        for n in (1, 2, 3):
            block = re.search(rf'id="like-{n}">(.*?)(?=<li class="like-row"|</ol>)', html, re.S).group(1)
            self.assertIn(f"種類{n - 1}", block)
            self.assertIn(f"検索{n - 1}a", block)                                              # the search of the line (one button each for Rakuten and Amazon would need an ID)
            self.assertIn("楽天市場で「", block)
            names = re.findall(r'<div class="item-body"><h3><a[^>]*>(.*?)</a>', block)
            if n == 1:
                self.assertTrue(names)
            if n == 2:
                self.assertEqual(names, [])                                                    # nothing of that kind: no unrelated products, the search stays
            for name in names:
                self.assertIn("語0", name)

    def test_the_first_products_of_a_page_are_of_different_kinds(self):
        d = build.prepare(self.c, self.items, CFG)
        for key in [k for k in d["pairs"] if not k.startswith("theme-")][:4]:
            ideas = build.pair_items(d, key)[0]
            have = [i for i in ideas if i["items"]]
            if len(have) < 2:
                continue
            html = self.read(f"gift/{key}/index.html")
            top = re.search(r'<section class="top-picks">(.*?)</section>', html, re.S).group(1)
            codes = re.findall(r'data-code="([^"]+)"', top)
            owners = {next(i["label"] for i in have if any(x["code"] == c for x in i["items"])) for c in codes}
            self.assertGreaterEqual(len(owners), 2, key)
            self.assertIn("種類の違う人気の", top)

    def test_an_idea_with_a_single_product_is_not_shown_as_a_proposal(self):
        items = copy.deepcopy(self.items)
        key = next(k for k in items["pairs"] if not k.startswith("theme-"))
        items["pairs"][key]["ideas"][0]["items"] = items["pairs"][key]["ideas"][0]["items"][:1]
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(self.c, items, CFG, Path(tmp) / "s", release=True, today=date(2026, 10, 12))
            html = (Path(tmp) / "s" / "gift" / key / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="idea-0"', html)
        self.assertIn('id="idea-1"', html)

    def test_the_consistency_report_counts_what_is_wrong_and_what_is_thin(self):
        d = build.prepare(self.c, self.items, CFG)
        a = consistency.audit(d)
        self.assertEqual(a["wrong"], [])
        self.assertGreater(a["ideas"], 0)
        self.assertEqual(a["like_lines"], 6)
        self.assertIn("products not of their idea", consistency.summary(a))

    def test_the_build_drops_a_stored_product_that_is_not_of_the_ideas_kind(self):
        c = copy.deepcopy(self.c)
        for p in content.pages(c):
            for idea in p["ideas"]:
                idea["must"] = ["ZZZ"]
        d = build.prepare(c, self.items, CFG)
        self.assertEqual([i for key in d["pairs"] for idea in build.pair_items(d, key)[0] for i in idea["items"]], [])
        self.assertEqual(len(consistency.audit(d)["thin"]), consistency.audit(d)["ideas"])


if __name__ == "__main__":
    unittest.main()
