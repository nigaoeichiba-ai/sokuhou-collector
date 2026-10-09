import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import demand


class TopicWords(unittest.TestCase):
    def test_filler_is_dropped(self):
        self.assertEqual(demand.topic_words("年賀状 ひつじ イラスト 無料 かわいい"), ["年賀状", "ひつじ"])

    def test_katakana_and_hiragana_are_one_word(self):
        self.assertEqual(demand.topic_words("ヒツジ イラスト"), ["ひつじ"])
        self.assertEqual(demand.norm("ヒツジ"), demand.norm("ひつじ"))

    def test_years_and_numbers_are_dropped(self):
        self.assertEqual(demand.topic_words("年賀状 2027 イラスト"), ["年賀状"])

    def test_only_filler_gives_nothing(self):
        self.assertEqual(demand.topic_words("イラスト 無料 フリー素材"), [])

    def test_glued_filler_is_stripped(self):
        self.assertEqual(demand.topic_words("ねこイラスト"), ["ねこ"])


class Coverage(unittest.TestCase):
    def test_all_words_must_match_one_illustration(self):
        items = [demand.norm("ひつじ 年賀状 手をふる"), demand.norm("ねこ ねる")]
        self.assertEqual(demand.covered(["ひつじ"], items), 1)
        self.assertEqual(demand.covered(["ひつじ", "年賀状"], items), 1)
        self.assertEqual(demand.covered(["ひつじ", "ねこ"], items), 0)   # a combination can be a gap although each word exists

    def test_real_library_knows_the_sheep(self):
        items, _ = demand.library_blobs()
        self.assertGreater(demand.covered(["ひつじ"], items), 12)


class Analyse(unittest.TestCase):
    def fake(self, engine, q):
        table = {
            "ひつじ イラスト": ["ひつじ イラスト かわいい", "ひつじ イラスト 無料"],
            "ほねほね イラスト": ["ほねほね イラスト 無料", "ほねほね イラスト 手書き"],
        }
        return table.get(q.strip().replace(" 無料", "").replace(" かわいい", "").replace(" 手書き", "").replace(" 白黒", "").replace(" 商用", ""), [])

    def test_gap_and_ok_are_told_apart(self):
        found, failed = demand.collect([("ひつじ イラスト", "always"), ("ほねほね イラスト", "always")], fetch=self.fake, engines=("google",), delay=0)
        self.assertEqual(failed, 0)
        items = [demand.norm("ひつじ " + str(i)) for i in range(20)]
        rows = {r["topic"]: r for r in demand.analyse(found, items, [])}
        self.assertEqual(rows["ひつじ"]["status"], "ok")
        self.assertEqual(rows["ほねほね"]["status"], "gap")

    def test_thin_is_below_the_limit(self):
        found = {"ねこ イラスト": {"seeds": {"s"}, "engines": {"google"}, "rank": 0, "groups": {"always"}}}
        rows = demand.analyse(found, [demand.norm("ねこ 1")] * 3, [])
        self.assertEqual(rows[0]["status"], "thin")

    def test_failed_requests_are_counted_not_hidden(self):
        _, failed = demand.collect([("a イラスト", "always")], fetch=lambda e, q: None, engines=("google",), delay=0)
        self.assertEqual(failed, len(demand.MODIFIERS))

    def test_run_writes_queue_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            rows = demand.run(Path(d), today=date(2026, 10, 10), months=1, engines=("google",), fetch=lambda e, q: ["ほねほね イラスト"] if q.startswith("ハロウィン") else [], delay=0)
            self.assertTrue(any(r["topic"] == "ほねほね" for r in rows))
            md = (Path(d) / "QUEUE.md").read_text(encoding="utf-8")
            self.assertIn("ほねほね", md)
            self.assertTrue(json.loads((Path(d) / "2026-10-10.json").read_text(encoding="utf-8"))["rows"])


class Variants(unittest.TestCase):
    def test_spelling_variants_are_one_word(self):
        self.assertEqual(demand.norm("果物"), demand.norm("フルーツ"))
        self.assertEqual(demand.norm("塗り絵"), demand.norm("ぬりえ"))

    def test_printable_topics_are_not_gaps(self):
        found = {"賞状 イラスト": {"seeds": {"s"}, "engines": {"google"}, "rank": 0, "groups": {"always"}},
                 "賞状 フレーム イラスト": {"seeds": {"s"}, "engines": {"google"}, "rank": 0, "groups": {"always"}}}
        rows = {r["key"]: r for r in demand.analyse(found, [], [])}
        self.assertEqual(rows[demand.norm("賞状")]["status"], "page")
        self.assertEqual(rows[demand.norm("賞状") + " " + demand.norm("フレーム")]["status"], "gap")   # the page answers "賞状", not "賞状 + frame illustrations"

    def test_reuse_judges_saved_suggestions_without_fetching(self):
        with tempfile.TemporaryDirectory() as d:
            demand.run(Path(d), today=date(2026, 10, 10), months=1, engines=("google",), fetch=lambda e, q: ["ほねほね イラスト"] if q.startswith("ハロウィン") else [], delay=0)

            def boom(engine, q):
                raise AssertionError("must not fetch")

            rows = demand.run(Path(d), today=date(2026, 10, 11), reuse=True, fetch=boom, delay=0)
            self.assertTrue(any(r["topic"] == "ほねほね" for r in rows))


class Seeds(unittest.TestCase):
    def test_season_looks_ahead_and_wraps_the_year(self):
        seeds = [s for s, g in demand.seeds_for(date(2026, 11, 20), 3) if g.startswith("season-")]
        self.assertIn("年賀状 イラスト", seeds)        # November
        self.assertIn("お正月 イラスト", seeds)        # December
        self.assertIn("成人式 イラスト", seeds)        # January (wrapped)

    def test_every_month_has_seasonal_seeds(self):
        self.assertEqual(sorted(demand.SEASON), list(range(1, 13)))


if __name__ == "__main__":
    unittest.main()
