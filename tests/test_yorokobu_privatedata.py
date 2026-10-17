"""楽天・Yahoo!のAPIの取得データは、公開リポジトリに置かず、サーバーの非公開の場所に置く (sites/yorokobu/privatedata.py)。"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sites.yorokobu import privatedata

ROOT = Path(__file__).resolve().parents[1]
ENV = {"XSERVER_SSH_KEY": "KEYDATA", "XSERVER_HOST": "h.example", "XSERVER_USER": "u1"}


class FakeRun:
    def __init__(self, pull=None):
        self.calls = []
        self.pull = pull or {}

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        last = cmd[-1]
        m = re.search(r"cat ~/yorokobu-private/(\S+)$", last)
        if m and last.startswith("test -f"):
            data = self.pull.get(m.group(1))
            return subprocess.CompletedProcess(cmd, 0 if data is not None else 1, stdout=data or b"", stderr=b"")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")


class StoreTest(unittest.TestCase):
    def test_without_the_server_secrets_nothing_happens(self):
        with mock.patch.dict(os.environ, {k: "" for k in ENV}):
            with mock.patch("subprocess.run") as r:
                self.assertEqual(privatedata.run("pull", []), 0)
                self.assertEqual(privatedata.run("push", []), 0)
                r.assert_not_called()

    def test_an_unknown_file_is_refused(self):
        with mock.patch.dict(os.environ, ENV):
            self.assertEqual(privatedata.run("push", ["../../etc/passwd"]), 2)

    def test_a_push_writes_to_a_folder_beside_public_html_and_is_not_readable_by_others(self):
        fake = FakeRun()
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", fake), mock.patch.object(privatedata, "DATA", Path(td)):
            (Path(td) / "yorokobu_compare.json").write_text("{}", encoding="utf-8")
            self.assertEqual(privatedata.run("push", ["yorokobu_compare.json"]), 0)
        cmds = [c[-1] for c, _ in fake.calls]
        self.assertTrue(any("mkdir -p ~/yorokobu-private" in c and "chmod 700" in c for c in cmds), cmds)
        up = [c for c in cmds if ".part" in c][0]
        self.assertIn("~/yorokobu-private/yorokobu_compare.json", up)
        self.assertIn("chmod 600", up)
        self.assertTrue(all("public_html" not in c for c in cmds), cmds)                          # never a folder the web server serves

    def test_a_pull_writes_the_file_and_skips_one_the_server_does_not_have_yet(self):
        fake = FakeRun(pull={"yorokobu_ranking.json": b'{"a": 1}'})
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", fake), mock.patch.object(privatedata, "DATA", Path(td)):
            self.assertEqual(privatedata.run("pull", ["yorokobu_ranking.json", "yorokobu_yahoo.json"]), 0)
            self.assertEqual((Path(td) / "yorokobu_ranking.json").read_bytes(), b'{"a": 1}')
            self.assertFalse((Path(td) / "yorokobu_yahoo.json").exists())

    def test_the_four_files_are_ignored_by_git_and_not_tracked(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for n in privatedata.FILES:
            self.assertIn(f"data/{n}", ignore)
        out = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, text=True).stdout
        for n in privatedata.FILES:
            self.assertNotIn(f"data/{n}", out, "the API data is in the public repository")


class WorkflowTest(unittest.TestCase):
    def read(self, name):
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_the_four_data_workflows_do_not_commit_and_store_privately(self):
        for name, f in (("yorokobu-compare.yml", "yorokobu_compare.json"), ("yorokobu-yahoo.yml", "yorokobu_yahoo.json"), ("yorokobu-ranking.yml", "yorokobu_ranking.json"),
                        ("yorokobu-candidates.yml", "yorokobu_candidates.json")):
            t = self.read(name)
            self.assertNotIn("git push", t, name)
            self.assertNotIn("git add data/", t, name)
            self.assertIn("contents: read", t, name)
            self.assertIn(f"privatedata push {f}", t, name)

    def test_the_deploy_takes_the_data_from_the_private_folder_before_the_unit_tests_and_the_build(self):
        t = self.read("deploy.yml")
        i = t.index("python -m sites.yorokobu.privatedata pull")
        self.assertLess(i, t.index("python tests/run_tests.py"))
        self.assertLess(i, t.index("      - name: Build (release)"))
        self.assertIn("matrix.site == 'yorokobu'", t[t.rindex("- name: Private mall data", 0, i):i])


if __name__ == "__main__":
    unittest.main()
