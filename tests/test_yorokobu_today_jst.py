"""The yorokobu build's "today" is the Japanese date (the Actions runner's clock is UTC, which showed
"あと◯日" one day too many between 00:00 and 09:00 JST, found in the weekly review of 2026-10-12)."""
import re
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "sites" / "yorokobu" / "build.py").read_text(encoding="utf-8")


class TodayIsJst(unittest.TestCase):
    def test_build_uses_jst_not_the_runner_clock(self):
        line = next(l for l in SRC.splitlines() if re.match(r"\s+today = today or ", l))
        self.assertIn("timedelta(hours=9)", line)
        self.assertNotIn("date.today()", line)


class BulkDrinksAreNotListed(unittest.TestCase):
    """Cases of 500ml x24 tea and paper-pack juice showed on /numbers/ and /budget/ (weekly review 2026-10-12)."""

    def test_filters_drop_bulk_drinks_and_frozen_food(self):
        import json
        ng = json.loads((Path(__file__).resolve().parent.parent / "sites" / "yorokobu" / "content" / "filters.json").read_text(encoding="utf-8"))["ng_words"]
        for name in ("緑茶 彩茶 あやちゃ 500ml×24本 お茶", "お茶 緑茶 500ml ペットボトル", "野菜ジュース 195ml 紙パック 選べる 72本", "11種22食 冷凍食品 冷凍惣菜"):
            self.assertTrue(any(w in name for w in ng), name)
        self.assertFalse(any(w in "今治タオル フェイスタオル 4枚セット ギフト" for w in ng))


if __name__ == "__main__":
    unittest.main()
