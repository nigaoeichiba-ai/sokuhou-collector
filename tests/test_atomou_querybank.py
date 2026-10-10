"""atomou: the query bank (data/atomou/query_bank.json) names real genres, fills in every recipe, and never uses a search that was shown to bring only portals."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402

DATA = json.loads((ROOT / "data" / "atomou" / "query_bank.json").read_text(encoding="utf-8"))


class QueryBank(unittest.TestCase):
    def test_every_recipe_has_a_known_genre_a_year_and_domains(self):
        self.assertGreaterEqual(len(DATA["recipes"]), 20)
        for r in DATA["recipes"]:
            self.assertIn(r["genre"], build.SLUGS, r["topic"])
            self.assertTrue("{Y" in r["q"] or "令和" in r["q"] or "{作品名}" in r["q"] or "クリスマスケーキ" in r["q"] or "提供終了" in r["q"] or "{試験名}" in r["q"] or "{施設名}" in r["q"] or "就航" in r["q"] or "{祭り名}" in r["q"] or "{フェス名}" in r["q"], r["topic"])
            self.assertTrue(r["domains"] and r["yield"], r["topic"])
            self.assertFalse(any("yahoo" in d.lower() for d in r["domains"]), r["topic"])
            self.assertNotIn("まとめ", r["q"], r["topic"])

    def test_no_recipe_or_theme_goes_after_a_forbidden_topic(self):
        banned = ("競馬", "競輪", "ボートレース", "パチンコ", "カジノ", "宝くじ", "toto", "jra.go.jp", "keirin.jp", "boatrace.jp")
        self.assertIn("ギャンブル", " ".join(DATA["forbidden"]["topics"]))
        blob = json.dumps(DATA["recipes"], ensure_ascii=False)
        themes = (ROOT / "data" / "atomou" / "research_themes.json").read_text(encoding="utf-8")
        for w in banned:
            self.assertNotIn(w, blob.replace("競馬・競輪・ボートレースは、禁止ワード(ギャンブル系)のため扱わない", ""), w)
            self.assertNotIn(w, themes, w)

    def test_the_domains_the_search_tool_refuses_are_not_used_in_a_recipe(self):
        bad = set(DATA["unusable_domains"]["domains"])
        for r in DATA["recipes"]:
            self.assertFalse(bad & set(r["domains"]), r["topic"])

    def test_the_rules_say_to_open_the_page_and_to_give_one_domain_at_a_time(self):
        text = " ".join(DATA["rules"])
        self.assertIn("公式ページを開いて", text)
        self.assertIn("1 つだけ", text)

    def test_monthly_patterns_are_https_and_aggregators_are_not_visited(self):
        for p in DATA["monthly_url_patterns"]["confirmed"] + DATA["monthly_url_patterns"]["pattern_only"]:
            self.assertTrue(p["url"].startswith("https://"), p["site"])
        self.assertTrue(DATA["monthly_url_patterns"]["aggregators_not_visited"])


if __name__ == "__main__":
    unittest.main()
