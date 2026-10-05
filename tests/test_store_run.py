import json
import tempfile
import unittest
from pathlib import Path

from sokuhou import run, store


def _inc(started, place="大津市瀬田一丁目付近", kind="建物火災", **extra):
    return {"started_at": started, "place": place, "kind": kind, "status": "reported", **extra}


class StoreTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_write_if_changed_ignores_fetched_at_only_changes(self):
        p = self.dir / "a.json"
        self.assertTrue(store.write_if_changed(p, {"x": 1, "fetched_at": "2026-10-05T00:00:00+09:00"}))
        before = p.read_text(encoding="utf-8")
        self.assertFalse(store.write_if_changed(p, {"x": 1, "fetched_at": "2026-10-06T00:00:00+09:00"}))
        self.assertEqual(p.read_text(encoding="utf-8"), before)
        self.assertTrue(store.write_if_changed(p, {"x": 2, "fetched_at": "2026-10-06T00:00:00+09:00"}))
        self.assertEqual(store.read(p)["x"], 2)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_output_is_utf8_with_lf_and_stable_key_order(self):
        p = self.dir / "b.json"
        store.write_if_changed(p, {"b": "日本語", "a": 1})
        raw = p.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertIn("日本語".encode("utf-8"), raw)
        self.assertLess(raw.index(b'"a"'), raw.index(b'"b"'))

    def test_merge_keeps_history_and_updates_status(self):
        old = {"incidents": [_inc("2026-10-04T10:00:00+09:00"), _inc("2026-10-01T09:00:00+09:00", place="大津市堅田")]}
        new = {"source": "s", "incidents": [
            _inc("2026-10-04T10:00:00+09:00", status="resolved", resolved_at="2026-10-04T10:30:00+09:00", result="非火災と判明"),
            _inc("2026-10-05T08:00:00+09:00", place="大津市石山"),
        ]}
        out = store.merge_incidents(old, new)
        self.assertEqual(len(out["incidents"]), 3)  # the October 1 incident is no longer on the page but is kept
        self.assertEqual([i["started_at"][:10] for i in out["incidents"]], ["2026-10-05", "2026-10-04", "2026-10-01"])
        updated = next(i for i in out["incidents"] if i["started_at"].startswith("2026-10-04"))
        self.assertEqual(updated["status"], "resolved")
        self.assertEqual(updated["result"], "非火災と判明")

    def test_merge_without_previous_data(self):
        out = store.merge_incidents(None, {"incidents": [_inc("2026-10-05T08:00:00+09:00")]})
        self.assertEqual(len(out["incidents"]), 1)


class SanityChecksTest(unittest.TestCase):
    def test_jgrants(self):
        with self.assertRaises(run.SanityError):
            run.check_jgrants(None, {"total": 0})
        with self.assertRaises(run.SanityError):
            run.check_jgrants({"total": 167}, {"total": 10})
        run.check_jgrants({"total": 167}, {"total": 150})
        run.check_jgrants({"total": 5}, {"total": 1})  # tiny baselines may fluctuate

    def test_bear(self):
        ok = {"unparsed": [], "sightings": [1] * 139}
        run.check_bear({"sightings": [1] * 139}, ok)
        with self.assertRaises(run.SanityError):
            run.check_bear(None, {"unparsed": [{"name": "?"}], "sightings": [1] * 139})
        with self.assertRaises(run.SanityError):
            run.check_bear({"sightings": [1] * 139}, {"unparsed": [], "sightings": [1] * 10})

    def test_fire_and_minwage(self):
        with self.assertRaises(run.SanityError):
            run.check_fire(None, {"unparsed": ["x"]})
        run.check_fire(None, {"unparsed": []})
        with self.assertRaises(run.SanityError):
            run.check_minwage({"latest_fiscal_year": 2026}, {"latest_fiscal_year": 2025})
        with self.assertRaises(run.SanityError):
            run.check_estat_wage({"year_label": "令和7年"}, {"year_label": "令和6年"})


class RunGroupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_one_failing_source_does_not_block_the_others(self):
        def boom():
            raise RuntimeError("site down")
        good = run.Source("good", lambda: {"v": 1})
        bad = run.Source("bad", boom)
        changed, errors = run.run_group([bad, good], self.dir)
        self.assertEqual(changed, ["good"])
        self.assertEqual(list(errors), ["bad"])
        self.assertIn("RuntimeError: site down", errors["bad"])
        self.assertTrue((self.dir / "good.json").exists())
        self.assertFalse((self.dir / "bad.json").exists())

    def test_a_result_failing_its_sanity_check_keeps_the_previous_file(self):
        (self.dir / "jgrants.json").write_text(json.dumps({"total": 167, "subsidies": []}), encoding="utf-8")
        src = run.Source("jgrants", lambda: {"total": 0, "subsidies": []}, run.check_jgrants)
        changed, errors = run.run_group([src], self.dir)
        self.assertEqual(changed, [])
        self.assertIn("jgrants", errors)
        self.assertEqual(store_total(self.dir / "jgrants.json"), 167)

    def test_fire_history_survives_the_page_forgetting_old_incidents(self):
        first = {"unparsed": [], "incidents": [_inc("2026-10-01T09:00:00+09:00"), _inc("2026-10-02T09:00:00+09:00")]}
        second = {"unparsed": [], "incidents": [_inc("2026-10-05T09:00:00+09:00")]}
        for page in (first, second):
            src = run.Source("otsu_fire", lambda p=page: p, run.check_fire, store.merge_incidents)
            _, errors = run.run_group([src], self.dir)
            self.assertEqual(errors, {})
        saved = store.read(self.dir / "otsu_fire.json")
        self.assertEqual(len(saved["incidents"]), 3)

    def test_unchanged_data_reports_no_change(self):
        src = run.Source("x", lambda: {"v": 1, "fetched_at": "t"})
        self.assertEqual(run.run_group([src], self.dir)[0], ["x"])
        self.assertEqual(run.run_group([src], self.dir)[0], [])


class CliTest(unittest.TestCase):
    def test_unknown_group_is_a_usage_error(self):
        self.assertEqual(run.main(["run", "nope"]), 2)
        self.assertEqual(run.main(["run"]), 2)

    def test_groups_cover_every_collector(self):
        names = {s.name for group in run.GROUPS.values() for s in group}
        self.assertEqual(names, {"minwage", "estat_wage", "env_kuma", "jgrants", "otsu_bear", "otsu_fire"})


def store_total(path):
    return json.loads(path.read_text(encoding="utf-8"))["total"]


if __name__ == "__main__":
    unittest.main()
