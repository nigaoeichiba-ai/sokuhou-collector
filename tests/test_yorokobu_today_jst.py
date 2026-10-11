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


if __name__ == "__main__":
    unittest.main()
