"""Run the unit tests of one site (plus everything shared), so that a broken project cannot block another project's deploy or the daily data run.

    python tests/run_tests.py                 # everything (local default)
    python tests/run_tests.py --site saichin  # the shared tests and saichin's own; the other projects' own tests are left out
    python tests/run_tests.py --site core     # the shared tests only (the daily data collection uses this)

A project owns its tests by name: tests/test_<project>*.py and tests/fixtures/<project>/.  Everything else is shared and runs for every site.
New project: add its entry to data/sites.json (the register); OWNED is derived from it.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:   # `python tests/run_tests.py` puts tests/ first on the path, not the repository root: "from tests import ..." needs the root (CI failed on this, 2026-10-17)
    sys.path.insert(0, str(ROOT))


def owned_patterns() -> tuple[dict[str, list[str]], set[str]]:
    """{site: [test module patterns]} from the register's `own` patterns for tests/ (tests/test_kuma* -> test_kuma*, tests/test_otsu_bear.py -> test_otsu_bear),
    and the sites whose tests also run in the `core` run (saichin: the daily data run has always run them)."""
    from sokuhou import deployplan
    out, core = {}, set()
    for name, site in deployplan.load_registry(env={}).get("sites", {}).items():
        if site.get("core_tests"):
            core.add(name)
        pats = []
        for p in site["own"]:
            if p.startswith("tests/test_"):
                m = p[len("tests/"):]
                pats.append(m[:-3] if m.endswith(".py") else m)
        out[name] = pats
    return out, core


OWNED, IN_CORE = owned_patterns()
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
    skip = [p for name, pats in OWNED.items() if site is not None and name != site and not (site == "core" and name in IN_CORE) for p in pats]
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
    if a.site in (None, "atomou"):   # atomou's tests build the same 7,800-page site again and again: one build per distinct arguments (it was 45 to 80 minutes in CI)
        from tests import test_atomou_buildcache
        test_atomou_buildcache.install()
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
