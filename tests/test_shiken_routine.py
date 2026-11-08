"""shiken-nittei.com の定期更新ルーティン: 朝チェックの公式ページの一覧が、サイトのデータから機械的に作られること。"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "sites" / "shiken" / "tools" / "morning_list.py"


class MorningListTest(unittest.TestCase):
    def test_every_source_of_every_event_has_an_official_page(self):
        from sites.shiken.gen import model
        from sites.shiken.gen.sources import OFFICIAL_PAGES
        used = {e["source"] for e in model.EVENT_LIST}
        for sid in used:
            self.assertIn(sid, OFFICIAL_PAGES, sid)
            self.assertTrue(OFFICIAL_PAGES[sid]["url"].startswith("https://"), sid)

    def test_the_list_follows_the_data_and_the_window(self):
        sys.path.insert(0, str(ROOT))
        spec_tool = __import__("importlib.util").util.spec_from_file_location("morning_list", TOOL)
        mod = __import__("importlib.util").util.module_from_spec(spec_tool)
        spec_tool.loader.exec_module(mod)
        from sites.shiken.gen import common, model
        before = common.TODAY
        try:
            data = mod.build(30, "2026-11-08", 7)
            ids = [e for g in data["sources"] for e in g["events"]]
            self.assertTrue(ids)
            self.assertTrue(all(-7 <= e["left"] <= 30 for e in ids))
            # every event of the data inside the window is in the list: nobody keeps a list by hand
            want = [e for e in model.EVENT_LIST if -7 <= common.left(e["iso"]) <= 30]
            self.assertEqual(len(ids), len(want))
            self.assertTrue(all(g["url"] and g["org"] for g in data["sources"]))
            # a day with other events gives another list
            other = mod.build(30, "2027-01-05", 7)
            self.assertNotEqual({g["source"] for g in data["sources"]}, {g["source"] for g in other["sources"]})
        finally:
            common.set_today(before.isoformat())

    def test_the_command_prints_the_markdown_list(self):
        import os
        r = subprocess.run([sys.executable, str(TOOL), "--today", "2026-11-08"], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("公式URL: https://", r.stdout)

    def test_the_routine_doc_is_in_the_repository_and_claude_md_points_to_it(self):
        doc = (ROOT / "sites" / "shiken" / "docs" / "daily-routine.md").read_text(encoding="utf-8")
        for needle in ("06:30", "07:00", "morning_list.py", "日次報告_YYYY-MM-DD.md", "確定稿なし", "公開を止めて"):
            self.assertIn(needle, doc, needle)
        self.assertIn("docs/daily-routine.md", (ROOT / "sites" / "shiken" / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
