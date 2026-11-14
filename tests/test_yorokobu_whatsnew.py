"""The home page strip 「新しく追加したページ」 picks up new articles AND new themes (2026-11-15: a day that added 8 themes and 4 articles showed only themes)."""
import unittest

from sites.yorokobu import build


def _data(n_articles: int, n_themes: int, day: str = "2026-11-15") -> dict:
    return {
        "c": {"articles": [{"slug": f"art-{i}", "title": f"記事{i}", "date": day} for i in range(n_articles)]},
        "live_themes": [{"slug": f"th-{i}", "title": f"テーマ{i}", "added": day} for i in range(n_themes)],
    }


class WhatsNewTest(unittest.TestCase):
    def test_new_articles_reach_the_home_page_even_when_many_themes_were_added_the_same_day(self):
        html = build.whats_new(_data(4, 8))
        self.assertIn('href="/read/art-', html)
        self.assertIn('href="/theme/th-', html)

    def test_the_strip_keeps_its_size(self):
        html = build.whats_new(_data(4, 8))
        self.assertLessEqual(html.count("<li>"), 6)

    def test_negative_the_old_single_sorted_list_would_have_shown_no_article(self):
        d = _data(4, 8)
        old = sorted(
            [(a["date"], f'/read/{a["slug"]}/', a["title"], "読みもの") for a in d["c"]["articles"]]
            + [(t["added"], f'/theme/{t["slug"]}/', t["title"], "テーマ") for t in d["live_themes"]], reverse=True)[:6]
        self.assertFalse([r for r in old if r[3] == "読みもの"], "the old selection hid the articles; this test documents the failure the new one fixes")

    def test_the_newest_articles_come_first_within_their_kind(self):
        d = _data(0, 0)
        d["c"]["articles"] = [{"slug": "old", "title": "古い", "date": "2026-10-01"}, {"slug": "new", "title": "新しい", "date": "2026-11-15"},
                              {"slug": "mid", "title": "中", "date": "2026-11-01"}, {"slug": "mid2", "title": "中2", "date": "2026-11-02"}]
        html = build.whats_new(d)
        self.assertIn("/read/new/", html)
        self.assertNotIn("/read/old/", html)


if __name__ == "__main__":
    unittest.main()
