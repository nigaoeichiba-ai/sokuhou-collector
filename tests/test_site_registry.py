"""data/sites.json, the site register, must stay a safe single source: the deploy plan, the test selection and the watchdog all read it, and a new site is one more
entry there (docs DEPLOY_REDESIGN_100SITES.md).  A typo here must fail a test, not publish the wrong site or skip one."""
import json
import subprocess
import unittest
from pathlib import Path

from sokuhou import deployplan

ROOT = Path(__file__).resolve().parents[1]
ENTRY_KEYS = {"name", "domain", "marker", "min_pages", "min_cards", "probe", "needs_var", "live_sha", "watch", "group", "timeout_minutes", "build", "own", "owns",
              "fast_lane", "dir", "url", "core_tests"}
SECRETISH = ("password", "secret", "token", "api_key", "apikey", "private key")


def tracked():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p]


class RegisterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
        cls.reg = deployplan.load_registry(env={"ATOMOU_BUILD_FLAG": "--release", "ATOMOU_PROBE": "/assets/catalog.json"})

    def test_every_entry_uses_known_keys_only(self):
        for e in self.raw["sites"]:
            self.assertEqual(set(e) - ENTRY_KEYS, set(), e["name"])

    def test_the_register_holds_no_secret_and_no_product_data(self):
        text = json.dumps(self.raw, ensure_ascii=False).lower()
        for word in SECRETISH + ("item.rakuten", "amazon.co.jp/dp", "shopping.yahoo"):
            self.assertNotIn(word, text)

    def test_every_site_folder_with_a_build_is_in_the_register_and_the_other_way_round(self):
        folders = {p.parent.name for p in (ROOT / "sites").glob("*/build.py")}
        self.assertEqual(folders, set(self.reg["sites"]))

    def test_names_are_not_prefixes_of_each_other(self):
        # the default patterns are prefixes (tests/test_<name>*, data/<name>*): 'mi' would claim minna's files
        names = list(self.reg["sites"])
        for a in names:
            for b in names:
                if a != b:
                    self.assertFalse(b.startswith(a), f"{a} is a prefix of {b}")

    def test_no_tracked_file_belongs_to_two_sites(self):
        for path in tracked():
            owners = [n for n, s in self.reg["sites"].items() if any(deployplan.fnmatch.fnmatchcase(path, p) for p in s["own"])]
            self.assertLessEqual(len(owners), 1, f"{path}: {owners}")

    def test_the_ignore_list_does_not_hide_a_site_file(self):
        for path in tracked():
            if deployplan.owner_of(path, self.reg) != "none":
                continue
            self.assertFalse(any(deployplan.fnmatch.fnmatchcase(path, p) for s in self.reg["sites"].values() for p in s["own"]), path)

    def test_a_site_needs_the_fields_the_job_uses(self):
        for n, s in self.reg["sites"].items():
            self.assertTrue(s["build"].startswith("python "), n)
            self.assertTrue(s["probe"].startswith("/") or "{env:" in s["probe"], n)
            self.assertGreaterEqual(s["min_pages"], 1, n)
            self.assertRegex(s["url"], r"^https://[a-z0-9.-]+$", n)

    def test_the_test_selection_is_derived_from_the_register(self):
        from tests import run_tests
        self.assertEqual(set(run_tests.OWNED), set(self.reg["sites"]))
        self.assertIn("test_kuma*", run_tests.OWNED["kuma"])
        self.assertIn("test_otsu_bear", run_tests.OWNED["kuma"])
        self.assertEqual(run_tests.IN_CORE, {"saichin"})

    def test_an_unset_placeholder_stops_the_plan_instead_of_publishing_with_an_empty_probe(self):
        reg = deployplan.load_registry(env={})
        with self.assertRaises(deployplan.RegistryError):
            deployplan.plan(reg, event="schedule", only="", before="", after="HEAD")

    def test_a_bad_entry_is_refused(self):
        import tempfile
        for bad in ({"name": "Bad Name", "domain": "x.example", "marker": "m"}, {"name": "ok", "marker": "m"}, {"name": "ok", "domain": "x.example"}):
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / "sites.json"
                p.write_text(json.dumps({"sites": [bad]}), encoding="utf-8")
                with self.assertRaises(deployplan.RegistryError):
                    deployplan.load_registry(p)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sites.json"
            e = {"name": "a", "domain": "a.example", "marker": "m"}
            p.write_text(json.dumps({"sites": [e, dict(e, name="b")]}), encoding="utf-8")   # the same domain twice
            with self.assertRaises(deployplan.RegistryError):
                deployplan.load_registry(p)
            p.write_text(json.dumps({"sites": [e, dict(e)]}), encoding="utf-8")   # the same name twice
            with self.assertRaises(deployplan.RegistryError):
                deployplan.load_registry(p)

    def test_a_new_site_is_one_entry(self):
        import tempfile
        raw = json.loads(json.dumps(self.raw))
        raw["sites"].append({"name": "newsite", "domain": "newsite.example", "marker": "表示名"})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sites.json"
            p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            site = deployplan.load_registry(p)["sites"]["newsite"]
        self.assertEqual(site["build"], "python sites/newsite/build.py --release --out release")
        self.assertEqual((site["dir"], site["url"], site["group"], site["probe"]), ("newsite.example", "https://newsite.example", "deploy-newsite", "/sitemap.xml"))
        self.assertIn("tests/test_newsite*", site["own"])


if __name__ == "__main__":
    unittest.main()
