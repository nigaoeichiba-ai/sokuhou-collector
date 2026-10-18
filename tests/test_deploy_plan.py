"""The deploy plan (sokuhou/deployplan.py, the 'plan' job of .github/workflows/deploy.yml) must not lose a site's change and must not start a site that has none.

These are the scenarios of the old shell Gate (tests/test_deploy_gate.py before 2026-10-18), run against the plan on a throw-away git repository, plus the cases
the register adds: a site that had no owner pattern, a site added to the register, files the push trigger does not watch.

2026-10-16: minna's +9 series was pushed while minna's previous job was still running; GitHub cancelled the waiting minna job when a newer push came, and the newer
run skipped minna because its own diff touched only other sites.  The plan compares with the commit the live site was built from (served as /deployed-sha.txt).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sokuhou import deployplan

ROOT = Path(__file__).resolve().parents[1]
SITES = ("saichin", "kuma", "yorokobu", "minna", "atomou")


class PlanBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.live = {}
        self.reg = deployplan.load_registry(env={"ATOMOU_BUILD_FLAG": "--release", "ATOMOU_PROBE": "/assets/catalog.json"})
        for n, site in self.reg["sites"].items():
            d = self.tmp / "live" / n
            d.mkdir(parents=True)
            self.live[n] = d
            site["url"] = d.as_uri()
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

    def head(self):
        return self.git("rev-parse", "HEAD")

    def serve(self, site, sha):
        f = self.live[site] / "deployed-sha.txt"
        if sha is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(sha + "\n", encoding="utf-8")

    def plan(self, before, after, served=None, event="push", only="", sites=SITES):
        for s in sites:
            self.serve(s, served)
        return deployplan.plan(self.reg, event=event, only=only, before=before, after=after, cwd=self.repo)

    def go(self, site, before, after, served=None, **kw):
        return self.plan(before, after, served, **kw)["decisions"][site]["go"]

    def fast(self, site, before, after, served):
        return self.plan(before, after, served)["decisions"][site]["fast"]


class GateScenarios(PlanBase):
    def test_push_of_another_sites_files_skips_this_site_when_the_live_site_is_current(self):
        minna = self.commit("sites/minna/series.json", "minna")
        yoro = self.commit("sites/yorokobu/x.py", "yorokobu")
        self.assertFalse(self.go("minna", minna, yoro, served=minna))

    def test_lost_update_is_deployed_even_when_the_last_push_touched_only_another_site(self):
        live_minna = self.commit("sites/minna/old.json", "live minna")
        self.commit("sites/minna/series.json", "minna +9 series (its run was cancelled)")
        before = self.head()
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertTrue(self.go("minna", before, after, served=live_minna))

    def test_the_old_behaviour_would_have_lost_it(self):
        self.commit("sites/minna/series.json", "minna")
        before = self.head()
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertFalse(self.go("minna", before, after, served=None))

    def test_unknown_served_commit_falls_back_to_the_push_diff(self):
        self.commit("sites/minna/series.json", "minna")
        before = self.head()
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertFalse(self.go("minna", before, after, served="0123456789abcdef0123456789abcdef01234567"))
        self.assertFalse(self.go("minna", before, after, served="not a sha"))

    def test_shared_files_still_redeploy_every_site(self):
        before = self.head()
        after = self.commit("sokuhou/sitekit.py", "shared")
        for site in SITES:
            self.assertTrue(self.go(site, before, after, served=before), site)

    def test_a_rewrite_dictionary_deploys_only_its_own_site_and_the_judges_notes_deploy_nothing(self):
        before = self.head()
        after = self.commit("data/style/rewrites/yorokobu.json", "dictionary")
        self.assertTrue(self.go("yorokobu", before, after, served=before))
        for site in ("minna", "kuma", "saichin", "atomou"):
            self.assertFalse(self.go(site, before, after, served=before), site)
        for path in ("data/style/judged/yorokobu.json", "data/style/examples.json", "data/style/learned_rules.json", "data/style/lexicon/gift_ja.json",
                     "data/style/lexicon/README.md", "data/style/suggest_cache.json", "data/style/edited/yorokobu.json", "data/style/editor_prompt_ja.md"):
            before = self.head()
            after = self.commit(path, path)
            for site in SITES:
                self.assertFalse(self.go(site, before, after, served=before), (path, site))
        before = self.head()
        after = self.commit("sokuhou/styleloop.py", "the tool itself is shared")
        for site in SITES:
            self.assertTrue(self.go(site, before, after, served=before), site)

    def test_own_files_deploy(self):
        before = self.head()
        after = self.commit("sites/minna/series.json", "minna")
        self.assertTrue(self.go("minna", before, after, served=before))

    def test_atomou_is_compared_with_its_live_commit_too_when_that_can_be_read(self):
        # while the demo is behind a password /deployed-sha.txt answers 401: then the push's own BEFORE is the base (an unreadable file only means the fallback)
        self.commit("sites/atomou/a.py", "atomou")
        before = self.head()
        after = self.commit("sites/yorokobu/x.py", "yorokobu only")
        self.assertFalse(self.go("atomou", before, after, served=before))
        self.serve("atomou", None)
        self.assertFalse(self.go("atomou", before, after, served=None))


class FastLane(PlanBase):
    def test_fast_lane_only_for_minna_content(self):
        before = self.head()
        series = self.commit("sites/minna/library/new-series/series.json", "series")
        self.assertTrue(self.fast("minna", before, series, before))
        spec = self.commit("sites/minna/specs/new-series.json", "spec")
        self.assertTrue(self.fast("minna", before, spec, before))     # the diff from the live commit covers both commits
        guide = self.commit("sites/minna/content/guide.md", "guide text")
        self.assertTrue(self.fast("minna", before, guide, before))

    def test_fast_lane_never_for_code_templates_tests_or_shared_files(self):
        for path in ("sites/minna/build.py", "sites/minna/assets/style.css", "tests/test_minna_x.py", "sokuhou/sitekit.py", "requirements.txt"):
            before = self.head()
            self.commit("sites/minna/library/s/series.json", "series")
            after = self.commit(path, path)
            self.assertFalse(self.fast("minna", before, after, before), path)

    def test_fast_lane_is_only_for_minna(self):
        before = self.head()
        after = self.commit("sites/yorokobu/content/x.md", "yorokobu content")
        for site in ("yorokobu", "kuma", "saichin"):
            self.assertFalse(self.fast(site, before, after, before), site)

    def test_a_push_of_other_sites_files_next_to_minna_content_is_still_fast(self):
        before = self.head()
        self.commit("sites/minna/library/s/series.json", "series")
        after = self.commit("sites/yorokobu/compare.py", "yorokobu code")
        self.assertTrue(self.fast("minna", before, after, before))

    def test_no_fast_lane_without_a_push(self):
        before = self.head()
        after = self.commit("sites/minna/library/s/series.json", "series")
        d = self.plan(before, after, event="schedule")["decisions"]
        self.assertTrue(d["minna"]["go"])
        self.assertFalse(d["minna"]["fast"])


class WhoseIsIt(PlanBase):
    def test_saichin_has_its_own_files_now(self):
        # until 2026-10-18 deploy.yml had no pattern for saichin: one saichin file published all five sites
        before = self.head()
        after = self.commit("sites/saichin/build.py", "saichin")
        d = self.plan(before, after, served=before)["decisions"]
        self.assertEqual([n for n in SITES if d[n]["go"]], ["saichin"])

    def test_the_wage_data_belongs_to_saichin(self):
        before = self.head()
        for path in ("data/minwage.json", "data/estat_wage.json", "tests/test_saichin_pages.py"):
            after = self.commit(path, path)
            d = self.plan(before, after, served=before)["decisions"]
            self.assertEqual([n for n in SITES if d[n]["go"]], ["saichin"], path)

    def test_files_the_push_trigger_does_not_watch_publish_nothing(self):
        # the live commit can be older than several pushes; a README or another workflow in between is not a reason to publish every site
        before = self.head()
        self.commit("README.md", "readme")
        after = self.commit(".github/workflows/accesslog.yml", "another workflow")
        for site in SITES:
            self.assertFalse(self.go(site, before, after, served=before), site)

    def test_the_deploy_workflow_itself_publishes_every_site(self):
        before = self.head()
        after = self.commit(".github/workflows/deploy.yml", "workflow")
        for site in SITES:
            self.assertTrue(self.go(site, before, after, served=before), site)

    def test_only_names_one_site_and_an_unknown_name_is_an_error(self):
        before = self.head()
        after = self.commit("sokuhou/sitekit.py", "shared")
        d = self.plan(before, after, served=before, only="kuma")["decisions"]
        self.assertEqual([n for n in SITES if d[n]["go"]], ["kuma"])
        with self.assertRaises(deployplan.RegistryError):
            self.plan(before, after, only="kumaa")

    def test_a_schedule_and_a_manual_run_publish_every_site(self):
        before = self.head()
        after = self.commit("sites/minna/a.json", "minna")
        for event in ("schedule", "workflow_dispatch"):
            self.assertEqual([i["site"] for i in self.plan(before, after, event=event)["include"]], list(SITES))

    def test_the_matrix_carries_what_the_jobs_used_to_have_in_the_matrix(self):
        before = self.head()
        after = self.commit("sites/yorokobu/a.py", "yorokobu")
        inc = self.plan(before, after, served=before)["include"]
        self.assertEqual([i["site"] for i in inc], ["yorokobu"])
        y = inc[0]
        self.assertEqual((y["dir"], y["url"].startswith("file:"), y["min_pages"], y["marker"], y["probe"], y["group"]),
                         ("yorokobu-present.com", True, 120, "よろこぶプレゼント", "/sitemap.xml", "deploy-yorokobu"))   # its own group: GitHub keeps one waiting job per group and cancels an older waiting one, so a shared rakuten-api group let other waiters cancel the yorokobu deploy again and again (2026-10-18)
        self.assertEqual(y["build"], "python sites/yorokobu/build.py --release --out release --items out/yorokobu_items.json")


class WaitMeasured(PlanBase):
    def test_the_matrix_carries_the_commit_time_of_the_oldest_waiting_change(self):
        live = self.commit("sites/minna/old.json", "live minna")
        first = self.commit("sites/minna/a.json", "first minna change")
        self.commit("sites/yorokobu/x.py", "another site in between")
        after = self.commit("sites/minna/b.json", "second minna change")
        first_time = int(self.git("show", "-s", "--format=%ct", first))
        res = self.plan(live, after, served=live)
        inc = {i["site"]: i for i in res["include"]}
        self.assertEqual(inc["minna"]["since"], first_time)     # the change that has waited longest, not the newest
        self.assertTrue(inc["yorokobu"]["since"] > 0)
        self.assertIn("oldest waiting change", res["decisions"]["minna"]["why"])

    def test_a_manual_run_has_no_waiting_change_to_measure(self):
        before = self.head()
        after = self.commit("sites/minna/a.json", "minna")
        self.assertEqual([i["since"] for i in self.plan(before, after, event="workflow_dispatch", only="minna")["include"]], [0])


class ConnectionSlots(PlanBase):
    def test_the_sites_of_one_run_get_different_slots_and_a_single_site_goes_at_once(self):
        before = self.head()
        after = self.commit("sokuhou/sitekit.py", "shared")
        slots = [i["slot"] for i in self.plan(before, after, served=before)["include"]]
        self.assertEqual(slots, list(range(len(SITES))))
        after2 = self.commit("sites/minna/a.json", "minna")
        self.assertEqual([i["slot"] for i in self.plan(after, after2, served=after)["include"]], [0])

    def test_slots_repeat_after_ten_so_that_a_wave_waits_at_most_two_minutes(self):
        self.assertEqual(deployplan.SLOTS, 10)

class RegisterChanges(PlanBase):
    def register(self, mutate):
        data = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
        mutate(data)
        p = self.repo / "data" / "sites.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        self.git("add", "data/sites.json")
        self.git("commit", "-q", "-m", "register")
        return self.head()

    def test_adding_a_site_to_the_register_publishes_only_the_new_site(self):
        before = self.register(lambda d: None)
        after = self.register(lambda d: d["sites"].append({"name": "newsite", "domain": "newsite.example", "marker": "x"}))
        self.reg["sites"]["newsite"] = deployplan.load_registry(self.repo / "data" / "sites.json")["sites"]["newsite"]
        self.reg["sites"]["newsite"]["url"] = self.live["saichin"].as_uri()
        res = self.plan(before, after, served=before, sites=SITES)
        self.assertEqual([i["site"] for i in res["include"]], ["newsite"])

    def test_changing_one_sites_entry_publishes_only_that_site(self):
        before = self.register(lambda d: None)
        after = self.register(lambda d: d["sites"][0].__setitem__("min_pages", 71))
        res = self.plan(before, after, served=before)
        self.assertEqual([i["site"] for i in res["include"]], ["saichin"])

    def test_changing_the_shared_part_of_the_register_publishes_every_site(self):
        before = self.register(lambda d: None)
        after = self.register(lambda d: d["defaults"].__setitem__("min_pages", 21))
        res = self.plan(before, after, served=before)
        self.assertEqual([i["site"] for i in res["include"]], list(SITES))

    def test_a_register_that_cannot_be_compared_publishes_every_site(self):
        before = self.head()      # the register is not in the base commit
        after = self.register(lambda d: None)
        res = self.plan(before, after, served=before)
        self.assertEqual([i["site"] for i in res["include"]], list(SITES))


class WatchdogAgrees(PlanBase):
    def test_the_watchdog_applies_the_same_ownership_rules_as_the_plan(self):
        from sokuhou import office_watch
        paths = ["sites/minna/a.json", "sites/yorokobu/b.py", "sites/kuma/c.py", "sites/saichin/d.py", "tests/test_kuma_x.py", "tests/test_foo_kuma.py",
                 "tests/test_otsu_bear.py", "data/yorokobu_x.json", "data/atomou/x.json", "data/other.json", "data/foo_kuma.json", "sokuhou/sources/a_kuma.py",
                 "sokuhou/sitekit.py", "tests/fixtures/kuma_x/a.txt", "tests/test_minna_a.py", "requirements.txt", "tests/test_misc.py", "README.md",
                 "data/style/judged/a.json", "data/minwage.json"]
        for path in paths:
            before = self.head()
            after = self.commit(path, path)
            for site in ("saichin", "kuma", "yorokobu", "minna"):
                self.assertEqual(self.go(site, before, after, served=before), office_watch.touches(site, [path]), f"{site} {path}")


if __name__ == "__main__":
    unittest.main()
