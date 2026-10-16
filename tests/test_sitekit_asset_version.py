"""sitekit.asset_version keeps its hash while the assets are untouched (every page asks for it: reading all the files for each of 4,800 pages took two minutes of
atomou's build, 2026-10-16) and must still notice an edited, a added and a removed file."""
import os
import tempfile
import unittest
from pathlib import Path

from sokuhou import sitekit


def bump(p: Path, seconds: int = 5) -> None:
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))   # a coarse file system clock must not hide the edit


class AssetVersionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "a.css").write_text("body{color:red}", encoding="utf-8")
        (self.dir / "img").mkdir()
        (self.dir / "img" / "b.svg").write_text("<svg/>", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_same_files_give_the_same_version_and_it_matches_a_fresh_hash(self):
        v = sitekit.asset_version(self.dir)
        self.assertEqual(sitekit.asset_version(self.dir), v)
        sitekit._VERSIONS.clear()
        self.assertEqual(sitekit.asset_version(self.dir), v)          # the kept value is what a full read gives

    def test_an_edit_of_the_same_size_changes_the_version(self):
        v = sitekit.asset_version(self.dir)
        f = self.dir / "a.css"
        f.write_text("body{color:bue}", encoding="utf-8")             # the same number of bytes
        bump(f)
        self.assertNotEqual(sitekit.asset_version(self.dir), v)

    def test_a_new_file_and_a_removed_file_change_the_version(self):
        v = sitekit.asset_version(self.dir)
        (self.dir / "img" / "c.svg").write_text("<svg/>", encoding="utf-8")
        bump(self.dir / "img")
        v2 = sitekit.asset_version(self.dir)
        self.assertNotEqual(v2, v)
        (self.dir / "img" / "c.svg").unlink()
        bump(self.dir / "img", 10)
        self.assertEqual(sitekit.asset_version(self.dir), v)          # back to the first set of files, back to the first version


if __name__ == "__main__":
    unittest.main()
