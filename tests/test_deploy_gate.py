"""The deploy gate (the 'Gate' step of .github/workflows/deploy.yml) must not lose a site's change.

2026-10-16: minna's +9 series was pushed while minna's previous job was still running; GitHub cancelled the waiting minna job when a newer push came, and the newer
run skipped minna because its own diff touched only other sites.  The change stayed unpublished until the next full run.  The gate now compares with the commit the
live site was built from (served as /deployed-sha.txt).  These tests run the real script from the workflow file in a throw-away git repository.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


def gate_script() -> str:
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8"))
    for job in wf["jobs"].values():
        for step in job["steps"]:
            if step.get("id") == "gate":
                return step["run"]
    raise AssertionError("no Gate step")


@unittest.skipUnless(BASH and shutil.which("git") and shutil.which("curl"), "bash, git and curl are needed")
class DeployGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.live = self.tmp / "live"
        self.live.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.base = self.commit("sites/saichin/a.txt", "base")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + str(len(list(self.repo.rglob("*")))), encoding="utf-8")
        self.git("add", path)
        self.git("commit", "-q", "-m", text)
        return self.git("rev-parse", "HEAD")

    def run_gate(self, site, before, after, served=None):
        if served is None:
            (self.live / "deployed-sha.txt").unlink(missing_ok=True)
        else:
            (self.live / "deployed-sha.txt").write_text(served + "\n", encoding="utf-8")
        out = self.tmp / "out.txt"
        out.write_text("", encoding="utf-8")
        env = {**os.environ, "KEY": "k", "HOST": "h", "USER_ID": "u", "KUMA": "true", "YOROKOBU": "true", "MINNA": "true", "ATOMOU": "true",
               "RK_APP": "a", "RK_KEY": "b", "SITE": site, "EVENT": "push", "ONLY": "", "BEFORE": before, "AFTER": after,
               "URL": self.live.as_uri(), "GITHUB_OUTPUT": str(out), "ATOMOU_PUBLIC": "true", "DEMO_USER": "d", "DEMO_PASS": "p"}
        r = subprocess.run([BASH, "-c", gate_script()], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return "go=true" in out.read_text(encoding="utf-8")

    def test_push_of_another_sites_files_skips_this_site_when_the_live_site_is_current(self):
        minna = self.commit("sites/minna/series.json", "minna")
        yoro = self.commit("sites/yorokobu/x.py", "yorokobu")
        self.assertFalse(self.run_gate("minna", minna, yoro, served=minna))

    def test_lost_update_is_deployed_even_when_the_last_push_touched_only_another_site(self):
        # the live minna is older than minna's own commit; the newest push (the one that replaced the cancelled job) touched only yorokobu
        live_minna = self.commit("sites/minna/old.json", "live minna")
        self.commit("sites/minna/series.json", "minna +9 series (its run was cancelled)")
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertTrue(self.run_gate("minna", before, after, served=live_minna))

    def test_the_old_behaviour_would_have_lost_it(self):
        # no deployed-sha.txt on the live site (the first run after this change): the push's own diff is used, as before
        self.commit("sites/minna/series.json", "minna")
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertFalse(self.run_gate("minna", before, after, served=None))

    def test_unknown_served_commit_falls_back_to_the_push_diff(self):
        self.commit("sites/minna/series.json", "minna")
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertFalse(self.run_gate("minna", before, after, served="0123456789abcdef0123456789abcdef01234567"))
        self.assertFalse(self.run_gate("minna", before, after, served="not a sha"))

    def test_shared_files_still_redeploy_every_site(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sokuhou/sitekit.py", "shared")
        for site in ("saichin", "kuma", "yorokobu", "minna"):
            self.assertTrue(self.run_gate(site, before, after, served=before), site)

    def test_own_files_deploy(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/minna/series.json", "minna")
        self.assertTrue(self.run_gate("minna", before, after, served=before))


class DeployWorkflowWritesTheShaTest(unittest.TestCase):
    def test_the_build_publishes_the_commit_it_was_built_from(self):
        text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn('echo "$GITHUB_SHA" > release/deployed-sha.txt', text)
        self.assertIn('"$URL/deployed-sha.txt"', text)


if __name__ == "__main__":
    unittest.main()
