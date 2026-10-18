"""The incremental upload of a built site (sokuhou/deployupload.py).  The commands are not run: a fake `run` records them, so that the ORDER and the SAFETY of the steps are tested -
the live folder is changed only by the last command, and only after the server was found identical to the build."""
import os
import tempfile
import unittest
from unittest import mock

from sokuhou import deployupload as up


class Recorder:
    def __init__(self, rsync_ok=True, rsync_rc=0, dry_run_output="", remote_rc=0):
        self.calls = []
        self.rsync_ok, self.rsync_rc, self.dry_run_output, self.remote_rc = rsync_ok, rsync_rc, dry_run_output, remote_rc

    def run(self, cmd, stdin=None, capture=False):
        self.calls.append(("run", cmd))
        if cmd[0] == "rsync" and "-n" in cmd:
            return mock.Mock(returncode=0, stdout=self.dry_run_output, stderr="")
        if cmd[0] == "rsync":
            return mock.Mock(returncode=self.rsync_rc, stdout="", stderr="")
        script = cmd[-1] if cmd[0] == "ssh" else ""
        self.calls[-1] = ("ssh", script)
        return mock.Mock(returncode=self.remote_rc, stdout="", stderr="")


def kinds(rec):
    out = []
    for kind, c in rec.calls:
        if kind == "ssh":
            out.append("cp" if "cp -al" in c else "switch" if "mv .deploy_next public_html" in c else "ssh")
        elif "-n" in c:
            out.append("dry-run")
        else:
            out.append("rsync")
    return out


class IncrementalUploadTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"USER_ID": "u", "HOST": "h", "SSH_PORT": "10022"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def go(self, rec, **kw):
        with mock.patch.object(up, "run", rec.run):
            return up.upload_rsync("minna-no-illust.com", "release", **kw)

    def test_the_order_is_copy_with_hard_links_send_what_differs_check_by_content_then_switch(self):
        rec = Recorder()
        self.assertEqual(self.go(rec), 0)
        self.assertEqual(kinds(rec), ["cp", "rsync", "dry-run", "switch"])

    def test_the_new_folder_starts_as_a_hard_linked_copy_of_the_live_one(self):
        rec = Recorder()
        self.go(rec)
        first = rec.calls[0][1]
        self.assertIn("cp -al public_html .deploy_next", first)
        self.assertIn("rm -rf .deploy_next", first)

    def test_files_are_compared_by_content_deleted_files_go_and_atomous_live_folders_stay(self):
        rec = Recorder()
        self.go(rec)
        cmd = next(c for k, c in rec.calls if k == "run" and "--stats" in c)
        for flag in ("--checksum", "--delete"):
            self.assertIn(flag, cmd)
        for d in ("live", "demo/live", "demo.atomou.com/live"):
            self.assertIn(f"P /{d}/", cmd)                          # protected: not deleted by --delete
        self.assertNotIn("--inplace", cmd)                          # a replaced file is a new file: the rollback copy keeps its content
        self.assertTrue(cmd[-2].endswith("release/") and cmd[-1].endswith(":minna-no-illust.com/.deploy_next/"))

    def test_nothing_is_switched_when_the_server_does_not_hold_what_was_built(self):
        rec = Recorder(dry_run_output=">fc.t...... illust/a/index.html\n*deleting   old.html\nsent 10 bytes  received 5 bytes\n")
        self.assertEqual(self.go(rec), 1)
        self.assertNotIn("switch", kinds(rec))
        self.assertEqual(kinds(rec), ["cp", "rsync", "dry-run"])

    def test_the_summary_lines_of_rsync_are_not_differences(self):
        rec = Recorder(dry_run_output="sending incremental file list\n\nsent 1,234 bytes  received 12 bytes  2,492.00 bytes/sec\ntotal size is 747,000,000  speedup is 600,000.00 (DRY RUN)\n")
        self.assertEqual(self.go(rec), 0)
        self.assertIn("switch", kinds(rec))

    def test_a_failed_copy_stops_before_anything_is_sent(self):
        rec = Recorder(remote_rc=1)
        self.assertEqual(self.go(rec), 1)
        self.assertEqual(kinds(rec), ["cp"])

    def test_a_lost_connection_is_reported_as_unreachable_and_the_live_folder_is_untouched(self):
        rec = Recorder(rsync_rc=12)
        self.assertEqual(self.go(rec), 255)
        self.assertNotIn("switch", kinds(rec))

    def test_the_switch_keeps_the_rollback_folder_and_checks_the_new_one(self):
        rec = Recorder()
        self.go(rec)
        script = rec.calls[-1][1]
        for part in ("test -f .deploy_next/index.html", "test -f .deploy_next/.htaccess", "rm -rf .deploy_prev", "mv public_html .deploy_prev", "mv .deploy_next public_html"):
            self.assertIn(part, script)
        self.assertLess(script.index("mv public_html .deploy_prev"), script.index("mv .deploy_next public_html"))


class ModeTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"USER_ID": "u", "HOST": "h"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_auto_uses_rsync_when_both_ends_have_it_and_tar_otherwise(self):
        for available, expected in ((True, "rsync"), (False, "tar")):
            with mock.patch.object(up, "has_rsync", return_value=available), mock.patch.object(up, "upload_rsync", return_value=0) as r, mock.patch.object(up, "upload_tar", return_value=0) as t:
                self.assertEqual(up.main(["--dir", "x.example"]), 0)
                self.assertEqual((r.called, t.called), (expected == "rsync", expected == "tar"))

    def test_a_failure_gives_exit_1_and_a_lost_connection_is_written_for_the_workflow(self):
        with tempfile.NamedTemporaryFile("r+", delete=False) as out:
            path = out.name
        self.addCleanup(os.unlink, path)
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": path}), mock.patch.object(up, "has_rsync", return_value=True), mock.patch.object(up, "upload_rsync", return_value=255):
            self.assertEqual(up.main(["--dir", "x.example"]), 1)
        self.assertIn("unreachable=true", open(path, encoding="utf-8").read())

    def test_the_tar_way_still_carries_over_the_live_folders_of_atomou(self):
        captured = {}

        def fake_run(cmd, stdin=None, capture=False):
            captured["script"] = cmd[-1]
            return mock.Mock(returncode=0)

        class P:
            stdout = mock.Mock()
            returncode = 0

            def wait(self):
                return 0

        with mock.patch.object(up, "run", fake_run), mock.patch.object(up.subprocess, "Popen", return_value=P()):
            self.assertEqual(up.upload_tar("atomou.com", "release"), 0)
        s = captured["script"]
        self.assertIn("for d in live demo/live demo.atomou.com/live;", s)
        self.assertIn('cp -a "public_html/$d" ".deploy_next/$d"', s)
        self.assertLess(s.index("mv public_html .deploy_prev"), s.index("mv .deploy_next public_html"))


if __name__ == "__main__":
    unittest.main()
