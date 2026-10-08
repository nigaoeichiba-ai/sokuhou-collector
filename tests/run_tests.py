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
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED = {"atomou": ["test_atomou*"], "yorokobu": ["test_yorokobu*"], "minna": ["test_minna*"], "kuma": ["test_kuma*", "test_*_kuma", "test_otsu_bear*"]}
# the only skips CI accepts: the browser tests that are run on the owner's PC (CI measures the real build with sokuhou.layoutcheck instead)
ALLOWED_SKIPS = ("browser checks run locally",)


def flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from flatten(t)
        else:
            yield t


def module_of(test_id: str) -> str:
    """'tests.test_minna_build.MinnaBuildTest.test_x' -> 'test_minna_build'.  A module that fails to import (a missing library in another project's
    tests) is reported as 'tests.test_minna_factory'; it must still be recognised as that project's, or it would break every other project's run."""
    return next((p for p in test_id.split(".") if p.startswith("test_")), test_id)


def build(site: str | None) -> unittest.TestSuite:
    sys.path.insert(0, str(ROOT))
    found = unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    skip = [p for name, pats in OWNED.items() if site is not None and name != site for p in pats]
    out = unittest.TestSuite()
    for t in flatten(found):
        module = module_of(t.id())
        if any(fnmatch.fnmatch(module, p) for p in skip):
            continue
        out.addTest(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="a project name from OWNED, another site (shared tests + this one's), or 'core'")
    ap.add_argument("--strict", action="store_true", help="CI: a test may be skipped only for a reason listed in ALLOWED_SKIPS; any other skip (a missing library, font or tool) fails the run")
    a = ap.parse_args()
    suite = build(a.site)
    print(f"running {suite.countTestCases()} tests" + (f" for {a.site}" if a.site else ""))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    reasons = Counter(reason for _, reason in result.skipped)
    for reason, n in reasons.most_common():
        print(f"skipped {n}: {reason}")
    if not result.wasSuccessful():
        return 1
    if a.strict:
        unexpected = {r: n for r, n in reasons.items() if not any(k in r for k in ALLOWED_SKIPS)}
        if unexpected:
            print("STRICT: tests were skipped for a reason that hides a missing dependency (a skipped test checks nothing):")
            for r, n in unexpected.items():
                print(f"  {n} x {r}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
