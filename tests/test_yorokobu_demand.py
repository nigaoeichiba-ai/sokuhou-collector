"""The demand queue (sites/yorokobu/demand.py): what people search for, read with the site's own word lists."""
import json
import tempfile
import unittest
from pathlib import Path

from sites.yorokobu import demand


class DemandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = demand.Lexicon()

    def test_a_query_is_read_into_event_and_person_and_sorted_by_whether_the_page_exists(self):
        kind, r = self.lex.classify("母の日 プレゼント 母")
        self.assertEqual((kind, r["occ"], r["rec"]), ("answered", "mothers-day", "mother"))
        kind, r = self.lex.classify("母の日 プレゼント 祖父")
        self.assertEqual((r["occ"], r["rec"]), ("mothers-day", "grandfather"))
        self.assertIn(kind, ("pair", "answered"))
        self.assertEqual(self.lex.classify("母の日 プレゼント 祖父")[0], "answered" if "mothers-day-grandfather" in self.lex.pairs else "pair")

    def test_words_the_site_does_not_know_are_the_unknown_ones_and_filler_is_not(self):
        kind, r = self.lex.classify("ハリネズミ プレゼント おすすめ")
        self.assertEqual(kind, "unknown")
        self.assertEqual(r["unknown"], ["ハリネズミ"])
        self.assertEqual(self.lex.classify("プレゼント おすすめ 人気")[0], "other")
        self.assertEqual(self.lex.read("丈夫な傘")["rec"], "")                 # 丈夫 is not 夫

    def test_the_queue_counts_missing_pairs_and_unknown_words_with_an_example_and_reads_search_console(self):
        sug = {"母の日 プレゼント 祖父 70代": 3, "ハリネズミ プレゼント": 2, "ハリネズミ 誕生日": 1, "誕生日 プレゼント 彼女": 5, "金継ぎ 器": 1}
        gsc = [{"query": "誕生日 プレゼント 彼女", "impressions": 40, "clicks": 1, "position": 14.2}, {"query": "ハリネズミ プレゼント", "impressions": 9, "clicks": 0, "position": 30}]
        q = demand.build(sug, gsc, self.lex)
        words = {w["word"]: w for w in q["words"]}
        self.assertEqual(words["ハリネズミ"]["n"], 3)
        self.assertEqual(words["ハリネズミ"]["example"], "ハリネズミ プレゼント")
        self.assertEqual(q["gsc"][0]["query"], "誕生日 プレゼント 彼女")           # most shown first
        self.assertEqual(q["gsc"][0]["kind"], "answered")
        self.assertEqual(q["gsc"][1]["kind"], "unknown")
        md = demand.queue_md(q, [("金継", 2)])
        self.assertIn("ハリネズミ: 3回", md)
        self.assertIn("金継: 2", md)
        self.assertIn("| 誕生日 プレゼント 彼女 | 40 | 1 | 14.2 |", md)

    def test_suggestions_come_from_the_autocomplete_and_a_broken_answer_is_empty(self):
        fetch = lambda url: json.dumps(["q", ["母の日 プレゼント 花", "母の日 プレゼント 実用的"]]).encode()
        self.assertEqual(demand.suggest("母の日", fetch), ["母の日 プレゼント 花", "母の日 プレゼント 実用的"])
        self.assertEqual(demand.suggest("x", lambda u: b"not json"), [])
        def boom(url):
            raise OSError("offline")
        self.assertEqual(demand.suggest("x", boom), [])
        got = demand.collect(["a", "b"], fetch)
        self.assertEqual(got["母の日 プレゼント 花"], 2)                          # both seeds produced it

    def test_the_seeds_cover_every_event_and_person(self):
        s = demand.seeds()
        self.assertTrue(any(x.startswith("母の日 プレゼント") for x in s))
        self.assertTrue(any(x.startswith("彼女 プレゼント") for x in s))
        self.assertGreater(len(s), 100)

    def test_search_console_rows_are_read_from_either_shape_of_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "q.json"
            p.write_text(json.dumps({"queries": [{"query": "a", "impressions": 1}, {"nope": 1}]}), encoding="utf-8")
            self.assertEqual(len(demand.load_queries(p)), 1)
            p.write_text(json.dumps([{"query": "b"}]), encoding="utf-8")
            self.assertEqual(len(demand.load_queries(p)), 1)
            self.assertEqual(demand.load_queries(Path(t) / "none.json"), [])

    def test_the_factory_brief_carries_the_most_wanted_words_only_when_given_a_queue(self):
        from sites.yorokobu import factory
        with tempfile.TemporaryDirectory() as t:
            q = Path(t) / "QUEUE.md"
            q.write_text("# x\n\n## 2. words\n- ハリネズミ: 3回(例: ハリネズミ プレゼント)\n- 施設: 2回(例: 敬老の日 プレゼント 施設)\nprose line\n", encoding="utf-8")
            factory.brief("themes", 2, Path(t) / "with.md", Path(t) / "a.json", demand=q)
            factory.brief("themes", 2, Path(t) / "without.md", Path(t) / "a.json")
            with_ = (Path(t) / "with.md").read_text(encoding="utf-8")
            self.assertIn("REAL SEARCH DEMAND", with_)
            self.assertIn("- ハリネズミ: 3回", with_)
            self.assertNotIn("prose line", with_)
            self.assertNotIn("REAL SEARCH DEMAND", (Path(t) / "without.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
