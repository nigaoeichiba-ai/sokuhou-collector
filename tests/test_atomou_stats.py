"""atomou: the summary of the daily count files."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import stats  # noqa: E402


class Summary(unittest.TestCase):
    def folder(self, files: dict) -> Path:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        for name, data in files.items():
            (Path(td.name) / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return Path(td.name)

    def test_sums_days_inside_the_window_and_ignores_other_files(self):
        f = self.folder({
            "2026-10-07.json": {"view:home": 10, "skin:basic": 8, "skin:pop": 2, "act:save": 3, "act:skin:pop": 1, "home_order:default": 1},
            "2026-10-08.json": {"view:home": 5, "view:my": 2, "skin:pop": 5, "act:save": 1, "act:add:memorial": 2, "home_hidden:cats": 2, "big:on": 1, "act:block_hide:cats": 2},
            "2026-01-01.json": {"view:home": 999},               # outside the 30 days
            "rate-20261008-abcdef": "5",                         # the sender counter is not a count file
            "2026-10-09.json": "{broken",                        # a damaged file is skipped
        })
        s = stats.summary(stats.load(f, 30, date(2026, 10, 9)))
        self.assertEqual(s["page_views"], 17)
        self.assertEqual(s["views_by_page"], {"home": 15, "my": 2})
        self.assertEqual(s["skin_share_of_views"]["pop"], round(7 / 15, 3))
        self.assertEqual(s["actions"], {"save": 4})
        self.assertEqual((s["skin_picked"], s["added_by_kind"], s["blocks_hidden_on_views"], s["big_text_views"]), ({"pop": 1}, {"memorial": 2}, {"cats": 2}, 1))
        self.assertEqual(s["block_hide_clicks"], {"cats": 2})

    def test_which_official_days_are_put_into_planners_is_counted_by_public_id(self):
        f = self.folder({"2026-10-08.json": {"act:pop:c5e0902857": 4, "act:pop:aaaaaaaaaa": 9, "act:save": 13}})
        s = stats.summary(stats.load(f, 30, date(2026, 10, 9)))
        self.assertEqual(list(s["popular_days"].items()), [("aaaaaaaaaa", 9), ("c5e0902857", 4)])   # the most first
        self.assertEqual(s["actions"], {"save": 13})                                              # the per-day counts are not mixed into the plain actions

    def test_empty_folder_is_fine(self):
        s = stats.summary(stats.load(self.folder({}), 30, date(2026, 10, 9)))
        self.assertEqual((s["page_views"], s["actions"]), (0, {}))


if __name__ == "__main__":
    unittest.main()
