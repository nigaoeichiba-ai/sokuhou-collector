import unittest

from sites.yorokobu import curate


def item(n: int, shop: str = "a", name: str = "ハンドタオル ギフト 今治") -> dict:
    return {"code": f"{shop}:{n}", "name": f"{name} {n}", "price": 1000 + n, "shop": shop, "shop_code": shop, "reviews": 100, "rating": 4.5}


PAIR = {"occasion": "birthday", "recipient": "mother", "title": "母への誕生日プレゼント",
        "ideas": [{"label": f"案{i}", "type": "t", "query": "q", "why": "w"} for i in range(2)]}
C = {"pairs": [PAIR], "occ": {"birthday": {"name": "誕生日"}}}


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


class RepairTest(unittest.TestCase):
    IDEA = {"label": "入浴剤", "query": "メンズ 入浴剤 ギフトセット"}

    def test_on_topic_ignores_generic_gift_words(self):
        self.assertTrue(curate.on_topic("バスソルト 入浴剤 ギフトセット", self.IDEA))
        self.assertFalse(curate.on_topic("本革 二つ折り財布 メンズ ギフト", self.IDEA))

    def test_a_bad_pick_is_replaced_by_the_next_good_backup_without_a_note(self):
        items = [item(i, shop=f"s{i}", name="入浴剤 ギフトセット") for i in range(6)]
        items[1]["name"] = "メンズ 財布"                          # off topic
        sel = {"picks": [{"i": 0, "note": "香りの違う入浴剤四種"}, {"i": 1, "note": "本革の二つ折り財布です"}, {"i": 2, "note": "炭酸入りの入浴剤"}], "backups": [3, 4, 5]}
        row, errs = curate._repaired(sel, items, PAIR, "誕生日", set(), "k", self.IDEA)
        self.assertEqual(errs, [])
        self.assertEqual([x["code"] for x in row["picks"]], ["s0:0", "s2:2", "s3:3"])
        self.assertEqual(row["picks"][2]["note"], "")
        self.assertEqual(row["backups"], ["s4:4", "s5:5"])

    def test_an_idea_with_nothing_on_topic_is_left_empty_for_the_search_fallback(self):
        items = [item(i, shop=f"s{i}", name="メンズ 財布") for i in range(4)]
        row, errs = curate._repaired({"picks": [{"i": 0, "note": "二つ折りの財布です"}], "backups": [1, 2]}, items, PAIR, "誕生日", set(), "k", self.IDEA)
        self.assertEqual((row["picks"], errs), ([], []))


if __name__ == "__main__":
    unittest.main()
