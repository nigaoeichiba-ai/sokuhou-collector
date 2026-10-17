"""楽天・Yahoo!のAPIの取得データは、公開リポジトリに置かず、サーバーの非公開の場所に置く (sites/yorokobu/privatedata.py)。"""
import io
import os
import re
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sites.yorokobu import privatedata

ROOT = Path(__file__).resolve().parents[1]
ENV = {"XSERVER_SSH_KEY": "KEYDATA", "XSERVER_HOST": "h.example", "XSERVER_USER": "u1"}


class FakeRun:
    """The server as one ssh answer: a pull gets a tar of the requested files the server has; a push is a tar on stdin that is unpacked into a dict."""

    def __init__(self, server=None, fail_first=0):
        self.calls = []
        self.server = dict(server or {})
        self.fail_first = fail_first

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.fail_first:
            self.fail_first -= 1
            return subprocess.CompletedProcess(cmd, 255, stdout=b"", stderr=b"")
        remote = cmd[-1]
        if kw.get("input") is not None:                                         # a push
            with tarfile.open(fileobj=io.BytesIO(kw["input"]), mode="r:") as tf:
                for m in tf:
                    self.server[m.name] = tf.extractfile(m).read()
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        names = re.search(r"for n in ([^;]+);", remote).group(1).split()          # a pull: the files named and present
        have = [n for n in names if n in self.server]
        buf = io.BytesIO()
        if have:
            with tarfile.open(fileobj=buf, mode="w:") as tf:
                for n in have:
                    info = tarfile.TarInfo(n)
                    info.size = len(self.server[n])
                    tf.addfile(info, io.BytesIO(self.server[n]))
        return subprocess.CompletedProcess(cmd, 0, stdout=buf.getvalue(), stderr=b"")


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

    def test_a_push_is_one_connection_into_a_folder_beside_public_html_mode_700_with_files_600(self):
        fake = FakeRun()
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", fake), mock.patch.object(privatedata, "DATA", Path(td)),                 mock.patch.object(privatedata, "WAIT", (0, 0, 0)):
            (Path(td) / "yorokobu_compare.json").write_text("{}", encoding="utf-8")
            (Path(td) / "yorokobu_yahoo.json").write_text('{"y": 1}', encoding="utf-8")
            self.assertEqual(privatedata.run("push", ["yorokobu_compare.json", "yorokobu_yahoo.json", "yorokobu_ranking.json"]), 0)
        self.assertEqual(len(fake.calls), 1)                                                        # all the files travel in one connection
        self.assertEqual(fake.server, {"yorokobu_compare.json": b"{}", "yorokobu_yahoo.json": b'{"y": 1}'})      # (a file that is not here is skipped)
        remote = fake.calls[0][0][-1]
        self.assertIn("mkdir -p ~/yorokobu-private", remote)
        self.assertIn("chmod 700", remote)
        self.assertIn("chmod 600", remote)
        self.assertIn("mv -f", remote)                                                              # unpacked aside, then moved into place
        self.assertNotIn("public_html", remote)                                                     # never a folder the web server serves

    def test_a_pull_is_one_connection_writes_the_files_and_skips_the_ones_the_server_does_not_have_yet(self):
        fake = FakeRun(server={"yorokobu_ranking.json": b'{"a": 1}'})
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", fake), mock.patch.object(privatedata, "DATA", Path(td)),                 mock.patch.object(privatedata, "WAIT", (0, 0, 0)):
            self.assertEqual(privatedata.run("pull", ["yorokobu_ranking.json", "yorokobu_yahoo.json"]), 0)
            self.assertEqual((Path(td) / "yorokobu_ranking.json").read_bytes(), b'{"a": 1}')
            self.assertFalse((Path(td) / "yorokobu_yahoo.json").exists())
            self.assertEqual(len(fake.calls), 1)
            fake2 = FakeRun()
            with mock.patch("subprocess.run", fake2):
                self.assertEqual(privatedata.run("pull", []), 0)                                    # nothing on the server yet: fine, and still one connection
            self.assertEqual(len(fake2.calls), 1)

    def test_a_pull_takes_only_the_files_it_asked_for_from_the_tar(self):
        fake = FakeRun(server={"yorokobu_ranking.json": b"{}", "evil.sh": b"x"})
        real = fake.__call__

        def sneaky(cmd, **kw):                                                                     # a server that sends more than was asked for
            out = real(cmd, **kw)
            buf = io.BytesIO(out.stdout)
            extra = io.BytesIO()
            with tarfile.open(fileobj=extra, mode="w:") as tf:
                for n, data in (("yorokobu_ranking.json", b"{}"), ("evil.sh", b"x"), ("../up.json", b"x")):
                    info = tarfile.TarInfo(n)
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
            return subprocess.CompletedProcess(cmd, 0, stdout=extra.getvalue(), stderr=b"")
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", sneaky), mock.patch.object(privatedata, "DATA", Path(td)),                 mock.patch.object(privatedata, "WAIT", (0, 0, 0)):
            privatedata.run("pull", ["yorokobu_ranking.json"])
            self.assertEqual(sorted(p.name for p in Path(td).iterdir()), ["yorokobu_ranking.json"])

    def test_a_failed_connection_is_tried_again_after_a_pause_and_gives_up_after_three(self):
        fake = FakeRun(server={"yorokobu_ranking.json": b"{}"}, fail_first=2)
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", fake), mock.patch.object(privatedata, "DATA", Path(td)),                 mock.patch.object(privatedata, "WAIT", (0, 0, 0)):
            self.assertEqual(privatedata.run("pull", ["yorokobu_ranking.json"]), 0)
            self.assertEqual(len(fake.calls), 3)
        dead = FakeRun(fail_first=9)
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, ENV), mock.patch("subprocess.run", dead), mock.patch.object(privatedata, "DATA", Path(td)),                 mock.patch.object(privatedata, "WAIT", (0, 0, 0)):
            self.assertEqual(privatedata.run("pull", ["yorokobu_ranking.json"]), 1)
            self.assertEqual(len(dead.calls), 3)

    def test_the_four_files_are_ignored_by_git_and_not_tracked(self):
        ignore = (ROOT / "data" / ".gitignore").read_text(encoding="utf-8")         # (data/ is on the auto-push's list of folders; the top .gitignore is not)
        for n in privatedata.FILES:
            self.assertIn(n, ignore.split())
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
