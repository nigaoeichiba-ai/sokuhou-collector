"""The natural-Japanese publish gate (sokuhou/stylegate.py): a ratchet over the real release after the dictionary.

An unnatural sentence stops the publish (ratchet mode), a warning that is in the baseline does not, a sentence the dictionary fixed does not, a high finding always does,
and in shadow mode nothing stops but the report is the same.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sokuhou import naturaljp as nj
from sokuhou import stylegate as sg

MID = "この記事がお役に立てれば幸いです。"            # closing_kouei (mid)
HIGH = "いかがでしたでしょうか。ぜひ参考にしてみてください。"  # closing_ikaga (high)
GOOD = "気になる品があれば、候補の一覧から価格を見比べてください。"
PLAIN = "ゴーヤの苗は、四月の終わりに植えるのが目安です。"


def page(*paras: str) -> str:
    return "<!doctype html><html lang=ja><head><title>t</title></head><body><main><h1>見出し</h1>" + "".join(f"<p>{p}</p>" for p in paras) + "</main></body></html>"


class Folder:
    def __init__(self, testcase, pages: dict[str, str]):
        self.tmp = tempfile.TemporaryDirectory()
        testcase.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, html in pages.items():
            (self.root / name).write_text(html, encoding="utf-8")


def baseline_of(site: str, root: Path) -> dict:
    hits, _ = sg.collect(root, site, dictionary=False)
    return {"version": 1, "sites": {site: sg.baseline_entry(hits, "2026-10-20")}}


class GateTest(unittest.TestCase):
    def test_the_fixture_sentences_are_what_they_say(self):
        self.assertEqual([(h.rule, h.level) for h in nj.check_text(MID, "kuma", min_level="low")], [("closing_kouei", "mid")])
        self.assertEqual([(h.rule, h.level) for h in nj.check_text(HIGH, "kuma", min_level="low") if h.rule == "closing_ikaga"], [("closing_ikaga", "high")])
        self.assertEqual(nj.check_text(GOOD, "kuma", min_level="low"), [])

    def test_a_new_unnatural_sentence_stops_the_publish(self):
        f = Folder(self, {"index.html": page(PLAIN), "a.html": page(PLAIN, MID)})
        base = {"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}               # a baseline from before this sentence
        code, text, v = sg.run_check(f.root, "kuma", "ratchet", baseline=base)
        self.assertEqual(code, 1)
        self.assertEqual([h.rule for h in v.new], ["closing_kouei"])
        for part in ("a.html", "closing_kouei", MID, "直し方"):                                    # the page, the sentence, the rule and how to fix
            self.assertIn(part, text)
        self.assertIn("styleloop add --site kuma", text)

    def test_a_warning_that_is_in_the_baseline_does_not_stop_it(self):
        f = Folder(self, {"index.html": page(PLAIN), "a.html": page(PLAIN, MID)})
        base = baseline_of("kuma", f.root)
        self.assertEqual(base["sites"]["kuma"]["counts"], {"high": 0, "mid": 1})
        code, text, v = sg.run_check(f.root, "kuma", "ratchet", baseline=base)
        self.assertEqual((code, v.old, v.new, v.high), (0, 1, [], []))
        self.assertIn("問題なし", text)

    def test_the_same_sentence_with_another_number_is_not_new(self):
        f = Folder(self, {"a.html": page("この記事が3件の目撃に役立てば幸いです。")})
        g = Folder(self, {"a.html": page("この記事が12件の目撃に役立てば幸いです。")})
        base = baseline_of("kuma", f.root)
        self.assertEqual(sg.run_check(g.root, "kuma", "ratchet", baseline=base)[0], 0)

    def test_a_sentence_the_dictionary_fixed_does_not_stop_it(self):
        f = Folder(self, {"a.html": page(PLAIN, MID)})
        base = {"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}
        self.assertEqual(sg.run_check(f.root, "kuma", "ratchet", baseline=base)[0], 1)
        # the deploy applies the dictionary to the folder first: the folder then holds the fixed sentence
        (f.root / "a.html").write_text(page(PLAIN, GOOD), encoding="utf-8")
        code, _, v = sg.run_check(f.root, "kuma", "ratchet", baseline=base)
        self.assertEqual((code, v.new), (0, []))

    def test_the_dictionary_is_read_in_memory_when_the_folder_was_not_through_it(self):
        f = Folder(self, {"a.html": page(PLAIN, MID)})
        base = {"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}
        with mock.patch.object(nj, "published_text", lambda raw, site: raw.replace(MID, GOOD)):
            self.assertEqual(sg.run_check(f.root, "kuma", "ratchet", dictionary=True, baseline=base)[0], 0)
            self.assertEqual(sg.run_check(f.root, "kuma", "ratchet", dictionary=False, baseline=base)[0], 1)    # the deploy's way: what is in the folder is what is published

    def test_a_high_finding_stops_it_even_when_the_baseline_has_it(self):
        f = Folder(self, {"a.html": page(PLAIN, HIGH)})
        base = baseline_of("kuma", f.root)
        self.assertEqual(base["sites"]["kuma"]["counts"]["high"], 1)
        code, text, v = sg.run_check(f.root, "kuma", "ratchet", baseline=base)
        self.assertEqual((code, [h.rule for h in v.high]), (1, ["closing_ikaga"]))
        self.assertIn("closing_ikaga", text)

    def test_shadow_reports_the_same_but_never_stops(self):
        f = Folder(self, {"a.html": page(PLAIN, MID, HIGH)})
        base = {"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}
        code, text, v = sg.run_check(f.root, "kuma", "shadow", baseline=base)
        self.assertEqual(code, 0)
        self.assertTrue(v.fails)
        self.assertIn("shadow", text)
        self.assertIn("would-fail=yes", sg.shadow_line(v))
        self.assertTrue(sg.annotate(v).startswith("::warning "))
        v.mode = "ratchet"
        self.assertTrue(sg.annotate(v).startswith("::error "))

    def test_off_does_not_read_anything(self):
        self.assertEqual(sg.run_check(Path("/nonexistent-folder"), "kuma", "off")[0], 0)

    def test_a_low_finding_is_only_counted(self):
        f = Folder(self, {"a.html": page("今日も、最新の情報です！ 参考になる、大切な、お知らせです！！")})
        base = {"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}
        code, _, v = sg.run_check(f.root, "kuma", "ratchet", baseline=base)
        self.assertEqual((code, v.new, v.high), (0, [], []))

    def test_without_a_baseline_the_gate_warns_and_does_not_stop(self):
        f = Folder(self, {"a.html": page(PLAIN, MID)})
        code, text, v = sg.run_check(f.root, "kuma", "ratchet", baseline={"version": 1, "sites": {}})
        self.assertEqual(code, 0)
        self.assertIn("基準値", text)

    def test_the_gate_never_stops_a_publish_because_of_its_own_error(self):
        f = Folder(self, {"a.html": page(PLAIN)})
        with mock.patch.object(sg, "collect", side_effect=RuntimeError("boom")):
            code, text, v = sg.run_check(f.root, "kuma", "ratchet", baseline={"version": 1, "sites": {}})
        self.assertEqual(code, 0)
        self.assertIn("crashed", text)
        self.assertEqual(sg.run_check(Path("/nonexistent-folder"), "kuma", "ratchet")[0], 0)

    def test_shrink_drops_only_what_is_fixed_and_never_adds(self):
        f = Folder(self, {"a.html": page(PLAIN, MID)})
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sg, "BASELINE", Path(d) / "baseline.json"):
            sg.save_baseline(baseline_of("kuma", f.root))
            (f.root / "a.html").write_text(page(PLAIN, HIGH), encoding="utf-8")                    # the mid one is fixed, a new (high) one appears
            self.assertEqual(sg.cmd_baseline("kuma", f.root, shrink=True), 0)
            entry = sg.load_baseline()["sites"]["kuma"]
            self.assertEqual(entry["keys"], {})
            self.assertEqual(entry["counts"], {"high": 0, "mid": 0})

    def test_the_baseline_holds_hashes_not_text(self):
        f = Folder(self, {"a.html": page(PLAIN, MID)})
        raw = json.dumps(baseline_of("kuma", f.root), ensure_ascii=False)
        self.assertNotIn("幸いです", raw)


class PrecheckCodeTest(unittest.TestCase):
    def test_a_failing_precheck_returns_the_code_publish_ps1_stops_on(self):
        f = Folder(self, {"index.html": page(PLAIN, MID)})
        with mock.patch.object(sg, "changed_files", return_value=["sites/kuma/x.json"]), mock.patch.object(nj, "built_dir", return_value=f.root),                 mock.patch.object(sg, "load_baseline", return_value={"version": 1, "sites": {"kuma": sg.baseline_entry([], "2026-10-20")}}),                 mock.patch.dict("os.environ", {"NATURALJP_GATE": "ratchet"}):
            self.assertEqual(sg.precheck("origin/main", ["kuma"]), 8)


class ModeTest(unittest.TestCase):
    def test_modes_come_from_the_register_and_the_environment(self):
        sites = {"defaults": {"naturaljp_gate": "shadow"}, "sites": [{"name": "kuma", "naturaljp_gate": "ratchet"}, {"name": "minna"}]}
        with mock.patch.dict("os.environ", {"NATURALJP_GATE": ""}):
            self.assertEqual(sg.mode_for("kuma", sites), "ratchet")
            self.assertEqual(sg.mode_for("minna", sites), "shadow")
            self.assertEqual(sg.mode_for("unknown", {}), "shadow")
        with mock.patch.dict("os.environ", {"NATURALJP_GATE": "off"}):
            self.assertEqual(sg.mode_for("kuma", sites), "off")
        with mock.patch.dict("os.environ", {"NATURALJP_GATE": "nonsense"}):
            self.assertEqual(sg.mode_for("kuma", sites), "ratchet")

    def test_the_real_register_has_a_valid_mode_for_every_site(self):
        with mock.patch.dict("os.environ", {"NATURALJP_GATE": ""}):
            for s in nj.SITES:
                self.assertIn(sg.mode_for(s), sg.MODES, s)

    def test_which_sites_the_commits_touch(self):
        with mock.patch.dict("os.environ", {"NATURALJP_GATE": ""}):
            self.assertEqual(sg.sites_touched(["sites/kuma/build.py"]), ["kuma"])
            self.assertEqual(sg.sites_touched(["data/style/rewrites/yorokobu.json"]), ["yorokobu"])
            self.assertEqual(sg.sites_touched(["tests/test_x.py"]), [])
            self.assertEqual(set(sg.sites_touched(["sokuhou/naturaljp.py"])), set(nj.SITES))


class WorkflowTest(unittest.TestCase):
    def test_the_gate_step_runs_after_the_dictionary_and_before_the_site_check(self):
        wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        a = wf.index("python -m sokuhou.styleloop apply release")
        b = wf.index("python -m sokuhou.stylegate check release --site")
        c = wf.index("python -m sokuhou.sitecheck release")
        self.assertTrue(a < b < c)
        self.assertIn("NATURALJP_GATE: ${{ vars.NATURALJP_GATE }}", wf)

    def test_the_baseline_changes_no_deploy_by_itself(self):
        reg = json.loads((Path(__file__).resolve().parents[1] / "data" / "sites.json").read_text(encoding="utf-8"))
        self.assertIn("data/style/baseline.json", reg["ignore"])


if __name__ == "__main__":
    unittest.main()
