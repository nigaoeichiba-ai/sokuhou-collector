"""atomou: the daily research list (data/atomou/research_themes.json) names real genres, covers every genre and every day, and keeps the sources the owner ruled out out of it."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402

DATA = json.loads((ROOT / "data" / "atomou" / "research_themes.json").read_text(encoding="utf-8"))


class ResearchThemes(unittest.TestCase):
    def test_every_theme_has_a_known_genre_and_a_day(self):
        ids = set()
        for t in DATA["themes"]:
            self.assertIn(t["genre"], build.SLUGS, t["id"])
            self.assertIn(t["day"], range(DATA["days"]), t["id"])
            self.assertTrue(t["name"] and t["primary"], t["id"])
            self.assertNotIn(t["id"], ids)
            ids.add(t["id"])

    def test_every_genre_and_every_day_has_a_theme(self):
        self.assertEqual({t["genre"] for t in DATA["themes"]}, set(build.SLUGS))
        self.assertEqual({t["day"] for t in DATA["themes"]}, set(range(DATA["days"])))

    def test_no_theme_takes_its_facts_from_a_news_site(self):
        for t in DATA["themes"]:
            self.assertNotIn("Yahoo", t["name"] + t["primary"])
        self.assertTrue(any("Yahoo" in x for x in DATA["trending"]["not_used"]))
        self.assertFalse(any("yahoo" in s["url"].lower() for s in DATA["trending"]["sources"]))

    def test_every_theme_has_a_search_with_a_year_and_no_news_portal(self):
        for t in DATA["themes"]:
            self.assertIn("{Y}", t["q"], t["id"])                                 # a year is always in the words (without it old articles come first)
            self.assertNotIn("まとめ", t["q"], t["id"])                            # "まとめ" brings the affiliate blogs
            self.assertIsInstance(t["tested"], bool)
            self.assertFalse(any("yahoo" in x.lower() for x in t["domains"]), t["id"])
        self.assertGreaterEqual(sum(1 for t in DATA["themes"] if t["tested"]), 8)

    def test_the_search_advice_names_what_works_and_what_to_avoid(self):
        s = DATA["search"]
        self.assertTrue(s["works"] and s["avoid"] and len(s["event_words"]) >= 20)
        self.assertTrue(any("まとめ" in x for x in s["avoid"]))

    def test_the_regional_rotation_covers_the_whole_country_in_a_week(self):
        self.assertEqual(len(DATA["regional"]["rotation"]), DATA["days"])
        self.assertTrue(all("{県}" in x for x in DATA["regional"]["themes"]))


if __name__ == "__main__":
    unittest.main()
