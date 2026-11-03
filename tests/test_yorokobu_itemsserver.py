"""api/items.php (sites/yorokobu/itemsserver.py + items_receiver.php.tpl): the shops' data is not a public file; the pages ask for a few products at a time (2026-10-18, owner order; Rakuten Web Service
terms, Article 10 (1) (9)).  There is no PHP on the test machine: the Python twin `answer` is tested here and the PHP template is checked for the same rules in its text."""
import random
import re
import unittest
from pathlib import Path

from sites.yorokobu import itemsserver as S

ROOT = Path(__file__).resolve().parents[1]
DB = {
    "items": {f"s:{i}": {"n": f"品{i}", "p": 1000 + i, "i": f"https://thumbnail.image.rakuten.co.jp/{i}.jpg", "u": f"https://hb.afl.rakuten.co.jp/hgc/ID/?pc=p{i}"} for i in range(40)},
    "gacha": {"rec": {"mother": {"name": "母", "tiers": {"3000": [["a", 2000, "i", "u1", 1, 40], ["b", 2500, "i", "u2", 1, 40]], "5000": [["c", 4000, "i", "u3", 1, 40]]}}}},
    "rec": {"coffee": [{"n": "x", "p": 1000, "i": "i", "u": "u", "g": "f"}, {"n": "y", "p": 2000, "i": "i", "u": "u2", "g": "m"}, {"n": "z", "p": 3000, "i": "i", "u": "u3"}, {"n": "w", "p": 9000, "i": "i", "u": "u4"}]},
}


class AnswerTest(unittest.TestCase):
    def test_products_by_code_only_the_ones_asked_and_found_at_most_24_and_bad_codes_dropped(self):
        code, out = S.answer({"c": "s:1,s:2,nope,s:3"}, DB)
        self.assertEqual((code, sorted(out)), (200, ["s:1", "s:2", "s:3"]))
        many = ",".join(f"s:{i}" for i in range(40))
        self.assertEqual(len(S.answer({"c": many}, DB)[1]), 24)
        self.assertEqual(S.answer({"c": "<img src=x>,../../etc/passwd,a b"}, DB), (200, {}))
        self.assertEqual(S.answer({}, DB)[0], 400)                         # no list of everything exists

    def test_the_gacha_gives_one_row_and_not_the_last_one_unless_it_is_the_only_one(self):
        rnd = random.Random(1)
        seen = {S.answer({"r": "mother", "t": "3000", "x": "u1"}, DB, rnd)[1]["row"][3] for _ in range(20)}
        self.assertEqual(seen, {"u2"})
        self.assertEqual(S.answer({"r": "mother", "t": "5000", "x": "u3"}, DB, rnd)[1]["row"][3], "u3")
        self.assertEqual(S.answer({"r": "mother", "t": "9999"}, DB, rnd), (200, {"row": None}))
        self.assertEqual(S.answer({"r": "Mother!", "t": "3000"}, DB)[0], 400)

    def test_a_group_gives_a_few_products_that_fit_the_price_and_the_person(self):
        got = lambda **q: [it["n"] for it in S.answer({"g": "coffee", **q}, DB)[1]["items"]]
        self.assertEqual(got(), ["x", "y", "z", "w"])
        self.assertEqual(got(max="2500"), ["x", "y"])
        self.assertEqual(got(min="2500"), ["z", "w"])
        self.assertEqual(got(gender="f"), ["x", "z", "w"])                 # a title made for the other sex is left out
        self.assertEqual(got(n="2"), ["x", "y"])
        self.assertEqual(S.answer({"g": "../x"}, DB)[0], 400)


class TemplateTest(unittest.TestCase):
    PHP = (ROOT / "sites" / "yorokobu" / "items_receiver.php.tpl").read_text(encoding="utf-8")

    def test_the_php_has_the_rules_the_python_twin_has(self):
        for needle in ("yorokobu-private", "HTTP_SEC_FETCH_SITE", "HTTP_REFERER", "array_slice(", ", 0, 24)", "random_int", "REQUEST_METHOD", "'GET'",
                       "yorokobu_items_db.json", "yorokobu_gacha_db.json", "yorokobu_rec_db.json", "__LIMIT__", "__SITE_URL__", "429"):
            self.assertIn(needle, self.PHP, needle)
        self.assertNotIn("DOCUMENT_ROOT", self.PHP)                          # the data is outside the web root: never looked for inside it
        self.assertIsNone(re.search(r"json_encode\(\$db\)", self.PHP))      # nothing hands out a whole file

    def test_the_generated_script_has_the_site_and_the_limit_filled_in(self):
        php = S.items_php({"site_url": "https://example.test/"})
        self.assertIn("'https://example.test/'", php)
        self.assertNotIn("__SITE_URL__", php)
        self.assertNotIn("__LIMIT__", php)
        self.assertIn(f">= {S.DAILY_LIMIT}", php)

    def test_the_deploy_pushes_the_three_private_files_and_git_ignores_them(self):
        deploy = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn("privatedata push " + " ".join(S.PRIVATE_FILES.values()), deploy)
        ignore = (ROOT / "data" / ".gitignore").read_text(encoding="utf-8")
        for name in S.PRIVATE_FILES.values():
            self.assertIn(name, ignore.split())


PAIR_DB = {**DB, "gacha": {**DB["gacha"], "pair": {"birthday-mother": {"tiers": {"3000": [
    [0, 0, "財布1", 2000, "i0", "L0a", 10, 45], [0, 0, "財布2", 2100, "i0b", "L0b", 10, 44],
    [1, 1, "菓子", 2500, "i1", "L1", 20, 46], [2, 2, "ハンカチ", 1800, "i2", "L2", 5, 43], [3, 4, "名入れ", 2900, "i3", "L3", 7, 42]]}}}}}


class PairAnswerTest(unittest.TestCase):
    """?pk=<pair key>&t=<tier>: up to three rows of DIFFERENT ideas for an occasion x recipient pair (the three-product gacha, 2026-11-03)."""

    def ask(self, rnd=None, **q):
        return S.answer({"pk": "birthday-mother", "t": "3000", **q}, PAIR_DB, rnd or random.Random(3))

    def test_three_rows_of_three_different_ideas(self):
        for seed in range(20):
            code, out = self.ask(random.Random(seed))
            self.assertEqual(code, 200)
            rows = out["rows"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({r[0] for r in rows}), 3)

    def test_the_kind_to_take_and_the_kinds_to_leave_out(self):
        self.assertEqual({r[1] for r in self.ask(k="1")[1]["rows"]}, {1})
        rows = self.ask(exc="0,4")[1]["rows"]
        self.assertTrue(rows and all(r[1] not in (0, 4) for r in rows))
        self.assertEqual(self.ask(k="7")[1], {"rows": []})                       # no such kind in this pair: nothing, not an error

    def test_the_links_shown_last_are_left_out_while_another_is_left(self):
        for seed in range(20):
            rows = self.ask(random.Random(seed), x="L0a,L1")[1]["rows"]
            by = {r[0]: r[5] for r in rows}
            if 0 in by:
                self.assertEqual(by[0], "L0b")                                   # idea 0 has another product: that one
            if 1 in by:
                self.assertEqual(by[1], "L1")                                    # idea 1 has no other: the same is better than none

    def test_n_is_capped_at_three_and_bad_input_is_refused_or_ignored(self):
        self.assertEqual(len(self.ask(n="1")[1]["rows"]), 1)
        self.assertEqual(len(self.ask(n="99")[1]["rows"]), 3)
        self.assertEqual(S.answer({"pk": "../x", "t": "3000"}, PAIR_DB)[0], 400)
        self.assertEqual(S.answer({"pk": "birthday-mother", "t": "<b>"}, PAIR_DB)[0], 400)
        self.assertEqual(len(self.ask(exc="a,99999,,1")[1]["rows"]), len(self.ask(exc="1")[1]["rows"]))          # junk in exc is ignored, the real kind still counts

    def test_an_unknown_pair_or_budget_gives_no_rows(self):
        self.assertEqual(S.answer({"pk": "nope", "t": "3000"}, PAIR_DB), (200, {"rows": []}))
        self.assertEqual(self.ask(t="9999")[1], {"rows": []})

    def test_the_old_one_row_gacha_still_answers(self):
        self.assertEqual(S.answer({"r": "mother", "t": "3000"}, PAIR_DB, random.Random(1))[0], 200)

    def test_the_php_has_the_same_branch(self):
        php = (ROOT / "sites" / "yorokobu" / "items_receiver.php.tpl").read_text(encoding="utf-8")
        for needle in ("isset($_GET['pk'], $_GET['t'])", "['pair'][$pk]['tiers'][$t]", "exc", "shuffle($ideas)", "random_int", "min(3,"):
            self.assertIn(needle, php, needle)


if __name__ == "__main__":
    unittest.main()
