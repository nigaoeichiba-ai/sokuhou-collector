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


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


def gate_script() -> str:
    """The shell script of the Gate step, read from the workflow text (PyYAML is not a dependency of the CI)."""
    lines = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "id: gate":
            j = next(k for k in range(i, len(lines)) if lines[k].strip() == "run: |")
            indent = len(lines[j]) - len(lines[j].lstrip())
            body = []
            for l2 in lines[j + 1:]:
                if l2.strip() and len(l2) - len(l2.lstrip()) <= indent:
                    break
                body.append(l2[indent + 2:] if l2.strip() else "")
            return "\n".join(body)
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
        return "go=true" in self.gate_output(site, before, after, served)

    def gate_output(self, site, before, after, served=None):
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
        return out.read_text(encoding="utf-8")

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

    def test_a_rewrite_dictionary_deploys_only_its_own_site_and_the_judges_notes_deploy_nothing(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("data/style/rewrites/yorokobu.json", "dictionary")
        self.assertTrue(self.run_gate("yorokobu", before, after, served=before))
        for site in ("minna", "kuma", "saichin", "atomou"):
            self.assertFalse(self.run_gate(site, before, after, served=before), site)
        for path in ("data/style/judged/yorokobu.json", "data/style/examples.json", "data/style/learned_rules.json", "data/style/lexicon/gift_ja.json", "data/style/lexicon/README.md", "data/style/suggest_cache.json", "data/style/edited/yorokobu.json", "data/style/editor_prompt_ja.md"):
            before = self.git("rev-parse", "HEAD")
            after = self.commit(path, path)
            for site in ("saichin", "kuma", "yorokobu", "minna"):
                self.assertFalse(self.run_gate(site, before, after, served=before), (path, site))
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sokuhou/styleloop.py", "the tool itself is shared")
        for site in ("saichin", "kuma", "yorokobu", "minna"):
            self.assertTrue(self.run_gate(site, before, after, served=before), site)

    def test_own_files_deploy(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/minna/series.json", "minna")
        self.assertTrue(self.run_gate("minna", before, after, served=before))


    def fast(self, site, before, after, served):
        return "fast=true" in self.gate_output(site, before, after, served)

    def test_fast_lane_only_for_minna_content(self):
        before = self.git("rev-parse", "HEAD")
        series = self.commit("sites/minna/library/new-series/series.json", "series")
        self.assertTrue(self.fast("minna", before, series, before))
        spec = self.commit("sites/minna/specs/new-series.json", "spec")
        self.assertTrue(self.fast("minna", before, spec, before))     # the diff from the live commit covers both commits
        guide = self.commit("sites/minna/content/guide.md", "guide text")
        self.assertTrue(self.fast("minna", before, guide, before))

    def test_fast_lane_never_for_code_templates_tests_or_shared_files(self):
        for path in ("sites/minna/build.py", "sites/minna/assets/style.css", "tests/test_minna_x.py", "sokuhou/sitekit.py", "requirements.txt"):
            before = self.git("rev-parse", "HEAD")
            self.commit("sites/minna/library/s/series.json", "series")
            after = self.commit(path, path)
            self.assertFalse(self.fast("minna", before, after, before), path)

    def test_fast_lane_is_only_for_minna(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/yorokobu/content/x.md", "yorokobu content")
        for site in ("yorokobu", "kuma", "saichin"):
            self.assertFalse(self.fast(site, before, after, before), site)

    def test_a_push_of_other_sites_files_next_to_minna_content_is_still_fast(self):
        before = self.git("rev-parse", "HEAD")
        self.commit("sites/minna/library/s/series.json", "series")
        after = self.commit("sites/yorokobu/compare.py", "yorokobu code")
        self.assertTrue(self.fast("minna", before, after, before))

    def test_no_fast_lane_without_a_push(self):
        before = self.git("rev-parse", "HEAD")
        after = self.commit("sites/minna/library/s/series.json", "series")
        out = self.tmp / "o2.txt"
        out.write_text("", encoding="utf-8")
        env = {**os.environ, "KEY": "k", "HOST": "h", "USER_ID": "u", "MINNA": "true", "SITE": "minna", "EVENT": "schedule", "ONLY": "", "BEFORE": "", "AFTER": after,
               "URL": self.live.as_uri(), "GITHUB_OUTPUT": str(out)}
        subprocess.run([BASH, "-c", gate_script()], cwd=self.repo, env=env, capture_output=True, text=True, check=True)
        text = out.read_text(encoding="utf-8")
        self.assertIn("go=true", text)
        self.assertIn("fast=false", text)

    def test_the_watchdog_applies_the_same_ownership_rules_as_the_gate(self):
        from sokuhou import office_watch
        paths = ["sites/minna/a.json", "sites/yorokobu/b.py", "sites/kuma/c.py", "sites/saichin/d.py", "tests/test_kuma_x.py", "tests/test_foo_kuma.py",
                 "tests/test_otsu_bear.py", "data/yorokobu_x.json", "data/atomou/x.json", "data/other.json", "data/foo_kuma.json", "sokuhou/sources/a_kuma.py",
                 "sokuhou/sitekit.py", "tests/fixtures/kuma_x/a.txt", "tests/test_minna_a.py", "requirements.txt", "tests/test_misc.py"]
        for path in paths:
            before = self.git("rev-parse", "HEAD")
            after = self.commit(path, path)
            for site in ("saichin", "kuma", "yorokobu", "minna"):
                self.assertEqual(self.run_gate(site, before, after, served=before), office_watch.touches(site, [path]), f"{site} {path}")


class DeployWorkflowWritesTheShaTest(unittest.TestCase):
    def test_the_build_publishes_the_commit_it_was_built_from(self):
        text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn('echo "$GITHUB_SHA" > release/deployed-sha.txt', text)
        # the fast lane skips exactly the unit tests and shrinks the live check; nothing else
        self.assertIn("steps.gate.outputs.go == 'true' && steps.gate.outputs.fast != 'true'", text)
        self.assertIn("--sample 150 --prev prev_sitemap.xml", text)
        self.assertEqual(text.count("steps.gate.outputs.fast != 'true'"), 1)
        self.assertIn('"$URL/deployed-sha.txt"', text)


if __name__ == "__main__":
    unittest.main()
