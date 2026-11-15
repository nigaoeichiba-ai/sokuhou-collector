"""gen.write() rewrites the tracked content/*.json and site.json for today's date; a test or a local build puts them back when the process ends (2026-11-15: a full test run left 15+ tracked
files changed in the working folder and stopped publish.ps1).  Pinned here on a temporary copy: the write changes the files, restore() brings them back byte for byte."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sites.kaidoki import gen


class GenRestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "content").mkdir()
        (self.root / "content" / "old.json").write_text('{"old": 1}\n', encoding="utf-8")
        (self.root / "content" / "home.json").write_text('{"path": "/", "updated": "2026-11-03"}\n', encoding="utf-8")
        (self.root / "site.json").write_text(json.dumps({"updated": "2026-11-03", "name": "x"}) + "\n", encoding="utf-8")
        self.before = {f.name: f.read_bytes() for f in [*(self.root / "content").glob("*.json"), self.root / "site.json"]}
        self.patches = [mock.patch.object(gen, "SITE", self.root), mock.patch.object(gen, "_ORIGINAL", {}), mock.patch.object(gen, "all_pages", return_value=[{"path": "/", "updated": "2026-11-15"}]),
                        mock.patch.object(gen.atexit, "register")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _now(self):
        return {f.name: f.read_bytes() for f in [*(self.root / "content").glob("*.json"), self.root / "site.json"]}

    def test_write_changes_the_files_and_restore_puts_them_back(self):
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "", "KAIDOKI_KEEP_GEN": ""}):
            gen.write()
        self.assertNotEqual(self._now(), self.before)                  # the write did change them (a test run would have left this behind)
        self.assertGreater(gen.restore(), 0)
        self.assertEqual(self._now(), self.before)                     # back, byte for byte: the file removed by the write (old.json) too

    def test_negative_without_restore_the_change_stays(self):
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "", "KAIDOKI_KEEP_GEN": ""}):
            gen.write()
        self.assertNotIn("old.json", self._now())                      # this is the state restore() has to undo: it is detected by comparing with the first copy

    def test_in_ci_or_with_the_keep_switch_nothing_is_remembered(self):
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}):
            gen.write()
        self.assertEqual(gen._ORIGINAL, {})
        self.assertEqual(gen.restore(), 0)


if __name__ == "__main__":
    unittest.main()
