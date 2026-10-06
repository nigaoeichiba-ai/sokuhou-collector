import unittest

from sites.yorokobu import curate


def item(n: int, shop: str = "a", name: str = "ハンドタオル ギフト 今治") -> dict:
    return {"code": f"{shop}:{n}", "name": f"{name} {n}", "price": 1000 + n, "shop": shop, "shop_code": shop, "reviews": 100, "rating": 4.5}


PAIR = {"occasion": "birthday", "recipient": "mother", "title": "母への誕生日プレゼント",
        "ideas": [{"label": f"案{i}", "type": "t", "query": "q", "why": "w"} for i in range(2)]}
C = {"pairs": [PAIR]}


def cands(shops=("a", "b", "c", "d", "e", "f")):
    return {"birthday-mother": [[item(i, shops[i % len(shops)]) for i in range(8)], [item(10 + i, shops[i % len(shops)]) for i in range(8)]]}


def good_idea(first: int = 0):
    return {"picks": [{"i": first + k, "note": "今治産の綿を使ったハンドタオル2枚組"} for k in range(3)], "backups": [first + 3, first + 4]}


class CurateTest(unittest.TestCase):
    def test_valid_answer_becomes_codes(self):
        out, errors = curate.validate({"birthday-mother": [good_idea(), good_idea()]}, C, cands())
        self.assertEqual(errors, [])
        self.assertEqual(out["birthday-mother"][0]["picks"][0]["code"], "a:0")
        self.assertEqual(out["birthday-mother"][1]["backups"], ["d:13", "e:14"])

    def test_rules_are_enforced(self):
        a = good_idea()
        a["picks"][0]["note"] = "人気のハンドタオルです"
        self.assertTrue(any("note uses" in e for e in curate.validate({"birthday-mother": [a, good_idea()]}, C, cands())[1]))
        b = good_idea()
        b["picks"][1]["i"] = b["picks"][0]["i"]
        self.assertTrue(any("repeat" in e for e in curate.validate({"birthday-mother": [b, good_idea()]}, C, cands())[1]))
        self.assertTrue(any("ideas answered" in e for e in curate.validate({"birthday-mother": [good_idea()]}, C, cands())[1]))
        self.assertTrue(any("unknown page" in e for e in curate.validate({"nope": []}, C, cands())[1]))

    def test_one_shop_may_not_fill_the_row(self):
        errors = curate.validate({"birthday-mother": [good_idea(), good_idea()]}, C, cands(shops=("a",)))[1]
        self.assertTrue(any("one shop" in e for e in errors))

    def test_wrong_gender_is_refused(self):
        c = cands()
        c["birthday-mother"][0][1]["name"] = "メンズ 二つ折り財布"
        errors = curate.validate({"birthday-mother": [good_idea(), good_idea()]}, C, c)[1]
        self.assertTrue(any("does not fit" in e for e in errors))

    def test_same_product_twice_on_a_page_is_refused(self):
        c = cands()
        c["birthday-mother"][1][0] = dict(c["birthday-mother"][0][0])
        errors = curate.validate({"birthday-mother": [good_idea(), good_idea()]}, C, c)[1]
        self.assertTrue(any("already used" in e for e in errors))

    def test_titles_for_another_narrow_occasion_are_refused(self):
        from sites.yorokobu.relevance import fits_occasion
        self.assertFalse(fits_occasion("お歳暮 2026 スイーツ ギフト", "birthday"))
        self.assertFalse(fits_occasion("名入れ刺繍 ポーチ 母子手帳 ケース 出産祝い", "birthday"))
        self.assertTrue(fits_occasion("お歳暮 2026 スイーツ ギフト", "oseibo"))
        self.assertTrue(fits_occasion("名入れ ポーチ 誕生日 クリスマス ギフト", "birthday"))


if __name__ == "__main__":
    unittest.main()
