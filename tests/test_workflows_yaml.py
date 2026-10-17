"""Every workflow file must be valid YAML.  A ': ' inside an unquoted step name once made deploy.yml invalid, and GitHub then ran no deploy at all for an hour (2026-10-18):
the error shows only as a failed run with no jobs.  This test parses each file the way GitHub does and names the file and the line."""
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(yaml, "PyYAML is not installed")
class WorkflowYamlTest(unittest.TestCase):
    def test_every_workflow_parses_and_has_a_trigger_and_jobs(self):
        files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreater(len(files), 10)
        for f in files:
            try:
                d = yaml.safe_load(f.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                self.fail(f"{f.name}: {e}")
            self.assertIsInstance(d, dict, f.name)
            self.assertTrue(d.get("jobs"), f.name)
            self.assertTrue(d.get("on") or d.get(True), f.name)         # YAML reads the key `on` as True

    def test_the_check_detects_the_mistake_that_happened(self):
        bad = "jobs:\n  a:\n    steps:\n      - name: Private data (never public: stays on the server)\n        run: echo\n"
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(bad)


if __name__ == "__main__":
    unittest.main()
