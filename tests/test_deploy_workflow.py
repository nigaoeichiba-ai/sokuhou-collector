"""The shape of .github/workflows/deploy.yml after the redesign of 2026-10-18 (docs DEPLOY_REDESIGN_100SITES.md).

The workflow is plain text here (PyYAML is not a dependency of the CI).  What is checked is what would hurt every site if it were lost: the plan job and the matrix it feeds,
the gates (the unit tests are read before the server is touched, the live check rolls back), the compatibility of the manual run (`deploy`, `only`: kuma-live.yml and the
watchdog start it), the commit id the live site publishes (the plan compares with it), and the restart on another runner when the server does not answer.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")


def steps():
    """[(name, block)] of the deploy job's steps, in order."""
    deploy = TEXT[TEXT.index("\n  deploy:"):]
    parts = re.split(r"\n      - (?=name: |uses: )", deploy)[1:]
    out = []
    for p in parts:
        m = re.match(r"name: (.*)", p)
        out.append((m.group(1) if m else p.split("\n")[0], p))
    return out


def index_of(prefix):
    hits = [i for i, (n, _) in enumerate(steps()) if n.startswith(prefix)]
    assert len(hits) == 1, (prefix, hits)
    return hits[0]


def block(prefix):
    return steps()[index_of(prefix)][1]


class PlanAndMatrix(unittest.TestCase):
    def test_the_plan_job_feeds_the_matrix_and_an_empty_plan_starts_nothing(self):
        self.assertIn("\n  plan:", TEXT)
        self.assertIn("python3 -m sokuhou.deployplan plan", TEXT)
        self.assertIn("needs: plan", TEXT)
        self.assertIn("if: needs.plan.outputs.count != '0'", TEXT)
        self.assertIn("matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}", TEXT)
        self.assertNotIn("include:\n          - site: saichin", TEXT)   # the sites are in data/sites.json, not here

    def test_a_wave_is_limited_and_a_site_never_waits_for_another_sites_job(self):
        m = re.search(r"max-parallel: (\d+)", TEXT)
        self.assertTrue(m and 4 <= int(m.group(1)) <= 12, "a wave takes at most 12 of the 20 runners and opens at most 12 SSH connections")
        self.assertIn("group: ${{ matrix.group }}", TEXT)
        self.assertIn("cancel-in-progress: false", TEXT)
        self.assertNotIn("cancel-in-progress: true", TEXT)
        self.assertIn("timeout-minutes: ${{ matrix.timeout }}", TEXT)

    def test_the_manual_run_keeps_its_inputs(self):
        for name in ("deploy:", "only:", "live_only:", "attempt:"):
            self.assertIn("      " + name, TEXT)
        kuma_live = (ROOT / ".github" / "workflows" / "kuma-live.yml").read_text(encoding="utf-8")
        self.assertIn("gh workflow run deploy.yml --ref main -f deploy=true -f only=kuma", kuma_live)

    def test_the_plan_gets_the_atomou_switches_and_the_workflow_token_is_read_only_except_for_the_restart(self):
        plan = TEXT[TEXT.index("\n  plan:"):TEXT.index("\n  deploy:")]
        self.assertIn("ATOMOU_BUILD_FLAG:", plan)
        self.assertIn("ATOMOU_PROBE:", plan)
        top = TEXT[:TEXT.index("\njobs:")]
        self.assertIn("permissions:\n  contents: read", top)
        self.assertNotIn("actions: write", top)
        job = TEXT[TEXT.index("\n  deploy:"):TEXT.index("    steps:", TEXT.index("\n  deploy:"))]
        self.assertIn("actions: write", job)


class TheGatesStay(unittest.TestCase):
    def test_the_build_writes_the_commit_it_was_built_from_and_the_plan_reads_it(self):
        self.assertIn('echo "$GITHUB_SHA" > release/deployed-sha.txt', TEXT)
        self.assertIn("/deployed-sha.txt", (ROOT / "sokuhou" / "deployplan.py").read_text(encoding="utf-8"))

    def test_the_fast_lane_skips_exactly_the_unit_tests_and_shrinks_the_live_check(self):
        self.assertIn("--sample 150 --prev prev_sitemap.xml", TEXT)
        self.assertEqual(TEXT.count("steps.gate.outputs.fast != 'true'"), 2)   # start of the tests, and their result
        self.assertIn("steps.gate.outputs.fast != 'true'", block("Unit tests, started now"))
        self.assertIn("steps.gate.outputs.fast != 'true'", block("Unit tests result"))

    def test_the_unit_tests_are_read_before_anything_on_the_server_changes(self):
        result = index_of("Unit tests result")
        self.assertLess(index_of("Unit tests, started now"), index_of("Build (release)"))
        self.assertGreater(result, index_of("Site check"))
        self.assertGreater(result, index_of("Phone-width layout check"))
        for later in ("Demo password file for atomou", "Upload and switch", "Verify the live site"):
            self.assertLess(result, index_of(later), later)
        # the only things before it that touch the server are reads (and yorokobu's private data, read)
        self.assertIn("[ \"$(cat \"$RUNNER_TEMP/tests.rc\")\" = 0 ]", block("Unit tests result"))

    def test_the_tests_run_in_a_second_work_tree_so_that_they_cannot_meet_what_the_build_writes(self):
        b = block("Unit tests, started now")
        self.assertIn("git worktree add --detach", b)
        self.assertIn("python tests/run_tests.py --strict --site", b)
        for ignored in ("^out/", "^release/"):
            self.assertIn(ignored, b)
        self.assertLess(index_of("Private mall data"), index_of("Unit tests, started now"))   # yorokobu's data is pulled first and copied along

    def test_the_site_check_the_layout_check_and_the_live_check_with_rollback_are_all_still_there(self):
        self.assertIn("python -m sokuhou.sitecheck release --base ${{ matrix.url }}", TEXT)
        self.assertIn("python -m sokuhou.layoutcheck release", TEXT)
        v = block("Verify the live site")
        self.assertIn("python -m sokuhou.sitecheck --live --base", v)
        self.assertIn("rolling back", v)
        self.assertIn("mv .deploy_prev public_html", v)
        self.assertLess(index_of("Site check"), index_of("Upload and switch"))
        self.assertLess(index_of("Upload and switch"), index_of("Verify the live site"))

    def test_the_live_only_run_reads_the_real_pages_and_changes_nothing(self):
        b = block("Live check only")
        self.assertIn("steps.gate.outputs.live == 'true'", b)
        self.assertIn("matrix.site != 'atomou'", b)   # behind a password
        self.assertIn("python -m sokuhou.sitecheck --live", b)
        gate = block("Gate")
        self.assertIn("go=false", gate[gate.index('LIVE_ONLY" = "true"'):])


class NoMallDataInTheGitHubCache(unittest.TestCase):
    """Owner rule 2026-10-17: what the Rakuten / Yahoo! / Amazon APIs give is never kept where the public can reach it - not in git, not in a log, not in the Actions cache
    or an artifact of this public repository.  Until 2026-10-18 the deploy kept out/yorokobu_items.json in actions/cache."""

    def test_no_workflow_caches_or_uploads_mall_data(self):
        for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = f.read_text(encoding="utf-8")
            for step in re.split(chr(10) + "      - ", text):
                if "actions/cache" in step or "upload-artifact" in step:
                    low = step.lower()
                    for word in ("yorokobu", "rakuten", "yahoo", "items.json", "ranking", "compare", "candidates"):
                        self.assertNotIn(word, low, f"{f.name}: a cache or artifact step mentions {word!r}: {step[:120]!r}")

    def test_the_deploy_takes_the_products_from_the_private_folder_and_fetches_only_when_they_are_missing(self):
        self.assertNotIn("actions/cache", TEXT)
        self.assertNotIn("Restore today's products", TEXT)
        fetch = block("Fetch products")
        self.assertIn("matrix.site == 'yorokobu'", fetch)
        self.assertIn("python -m sites.yorokobu.items_fresh || python -m sites.yorokobu.refresh --out out/yorokobu_items.json", fetch)
        self.assertGreater(index_of("Fetch products"), index_of("Private mall data"))   # the private pull (which brings yorokobu_items.json) comes first
        self.assertLess(index_of("Fetch products"), index_of("Build (release)"))
        self.assertNotIn("Keep the fetched products", TEXT)    # the daily yorokobu-items workflow is the only writer of the file


class NeverStuck(unittest.TestCase):
    """Owner, 2026-10-18: a change must not stay off the live site for hours because a run was cancelled, replaced or lost.  The reasons it cannot (and the tests that hold them):
    every site has a group of its own and no job is cancelled while it runs; a waiting job replaced by a newer one loses nothing, because the plan compares with the commit the
    live site was built from (tests/test_deploy_plan.py: the lost update of 2026-10-16); and the watchdog starts a stale site again by itself (tests/test_office_watch.py)."""

    def test_no_running_deploy_is_ever_cancelled(self):
        self.assertNotIn("cancel-in-progress: true", TEXT)
        self.assertIn("cancel-in-progress: false", TEXT)

    def test_the_watchdog_runs_twice_an_hour_and_after_every_deploy_and_starts_only_the_stale_site(self):
        wd = (ROOT / ".github" / "workflows" / "office-watch.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "17,47 * * * *"', wd)
        self.assertIn('workflows: ["deploy-sites"]', wd)
        self.assertIn('gh workflow run deploy.yml -f only="$site" -f deploy=true', wd)

    def test_the_wait_of_every_published_change_is_written_to_the_run_summary(self):
        b = block("How long the change waited")
        self.assertIn("GITHUB_STEP_SUMMARY", b)
        self.assertIn("steps.gate.outputs.really == 'true'", b)
        self.assertGreater(index_of("How long the change waited"), index_of("Verify the live site"))
        self.assertIn("since", (ROOT / "sokuhou" / "deployplan.py").read_text(encoding="utf-8"))

    def test_when_the_server_is_cut_off_the_ports_that_could_still_be_a_way_in_are_recorded(self):
        b = block("SSH setup")
        for port in ('"$SSH_PORT" 443 21 990',):
            self.assertIn(port, b)
        self.assertIn("REACH", b)


class OtherSessionsSteps(unittest.TestCase):
    def test_the_yorokobu_private_product_data_step_is_still_there_after_the_tests_and_before_the_upload(self):
        # lost once on 2026-10-18 when a copy of this file was put back over a newer one: a step another session adds must survive a rewrite of the workflow
        i = index_of("Private product data for api/items.php")
        self.assertGreater(i, index_of("Unit tests result"))
        self.assertLess(i, index_of("Upload and switch"))
        self.assertIn("matrix.site == 'yorokobu'", block("Private product data for api/items.php"))
        self.assertIn("steps.gate.outputs.really == 'true'", block("Private product data for api/items.php"))


class RealRunOrCheck(unittest.TestCase):
    def test_one_flag_decides_whether_the_server_is_changed_and_every_changing_step_reads_it(self):
        gate = block("Gate")
        self.assertIn("really=true", gate)
        self.assertIn('"$CHECK_ONLY" != "true"', gate)      # the pause switch: the repository variable DEPLOY_CHECK_ONLY
        self.assertIn('[ "$DEPLOY_INPUT" = "true" ] && really=true', gate)   # a manual run changes the server only when "Really deploy" is ticked
        for prefix in ("Demo password file for atomou", "IndexNow previous sitemap", "Upload and switch", "Verify the live site", "IndexNow submit"):
            self.assertIn("steps.gate.outputs.really == 'true'", block(prefix), prefix)
        self.assertNotIn("inputs.deploy ||", TEXT)

    def test_the_check_only_pause_still_builds_tests_and_proves_the_login(self):
        for prefix in ("Build (release)", "Site check", "Phone-width layout check", "Unit tests result", "Check the server"):
            self.assertNotIn("really", block(prefix).split("run:")[0], prefix)


class SshAndRestart(unittest.TestCase):
    def test_ssh_is_set_up_first_one_connection_and_a_short_wait(self):
        ssh = index_of("SSH setup")
        self.assertLess(ssh, index_of("Private mall data"))
        self.assertLess(ssh, index_of("Unit tests, started now"))
        b = block("SSH setup")
        self.assertIn("ControlMaster auto", b)
        self.assertIn("ServerAliveInterval", b)
        self.assertIn("for try in 1 2 3;", b)
        self.assertIn('echo "unreachable=true" >> "$GITHUB_OUTPUT"', b)
        self.assertNotIn("sleep \"$off\"", b)
        self.assertIn("sleep $((SLOT * 12 + RANDOM % 5))", b)      # the jobs of one run connect one after the other
        self.assertIn("SLOT: ${{ matrix.slot }}", b)
        self.assertNotIn("off=$((RANDOM % 160))", b)

    def test_a_lost_connection_in_the_later_steps_is_told_apart_from_a_real_failure(self):
        for prefix in ("Check the server", "Upload and switch"):
            b = block(prefix)
            self.assertIn('"$rc" = 255', b, prefix)    # 255 is ssh's own exit code: the connection, not the command
            self.assertIn('echo "unreachable=true" >> "$GITHUB_OUTPUT"', b, prefix)

    def test_a_site_whose_server_did_not_answer_is_started_again_up_to_three_times_and_only_that_site(self):
        b = block("Start this site again")
        self.assertIn("if: failure() &&", b)
        for step in ("steps.ssh.outputs.unreachable", "steps.servercheck.outputs.unreachable", "steps.upload.outputs.unreachable"):
            self.assertIn(step, b)
        self.assertIn('[ "$ATTEMPT" -ge 3 ]', b)
        self.assertIn('-f only="$SITE"', b)
        self.assertIn('-f deploy="$REALLY"', b)
        self.assertIn('-f attempt="$((ATTEMPT + 1))"', b)
        self.assertIs(steps()[-1][0].startswith("Start this site again"), True)


class IndexNowAndPassword(unittest.TestCase):
    def test_the_atomou_password_file_comes_after_the_tests(self):
        self.assertGreater(index_of("Demo password file for atomou"), index_of("Unit tests result"))


if __name__ == "__main__":
    unittest.main()
