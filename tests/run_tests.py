"""Run the unit tests of one site (plus everything shared), so that a broken project cannot block another project's deploy or the daily data run.

    python tests/run_tests.py                 # everything (local default)
    python tests/run_tests.py --site saichin  # the shared tests and saichin's own; the other projects' own tests are left out
    python tests/run_tests.py --site core     # the shared tests only (the daily data collection uses this)

A project owns its tests by name: tests/test_<project>*.py and tests/fixtures/<project>/.  Everything else is shared and runs for every site.
New project: add its name and pattern to OWNED.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED = {"yorokobu": ["test_yorokobu*"], "minna": ["test_minna*"]}


def flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from flatten(t)
        else:
            yield t


def build(site: str | None) -> unittest.TestSuite:
    sys.path.insert(0, str(ROOT))
    found = unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    skip = [p for name, pats in OWNED.items() if site is not None and name != site for p in pats]
    out = unittest.TestSuite()
    for t in flatten(found):
        module = t.id().split(".")[-3] if t.id().count(".") >= 2 else t.id()
        if any(fnmatch.fnmatch(module, p) for p in skip):
            continue
        out.addTest(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="a project name from OWNED, another site (shared tests + this one's), or 'core'")
    a = ap.parse_args()
    suite = build(a.site)
    print(f"running {suite.countTestCases()} tests" + (f" for {a.site}" if a.site else ""))
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
