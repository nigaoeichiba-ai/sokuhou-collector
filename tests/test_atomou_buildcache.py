"""One build per distinct (config, release, day) for the whole atomou test run.

About 45 test classes and tests each called sites.atomou.build.build_pages (7,800 pages, 1 to 3 minutes each on a CI runner), mostly with the same
arguments; deploy-sites spent 45 to 80 minutes in "Unit tests" because of it (2026-10-16).  tests/run_tests.py installs this before the run.
The pages are bytes and str, so a copy of the dict is enough for a test that adds or removes a page.  Nothing else is shared: a test that changes
something the build reads (a mock of the catalog, say) must pass its own config or call the uncached function (build_pages.__wrapped__).
"""
from __future__ import annotations

import functools
import json
from datetime import date

_cache: dict[str, dict] = {}


def install() -> None:
    from sites.atomou import build
    if getattr(build.build_pages, "__wrapped__", None) is not None:
        return
    real = build.build_pages

    @functools.wraps(real)
    def cached(cfg, release=False, today=None):
        key = json.dumps([cfg, bool(release), (today or date.today()).isoformat()], sort_keys=True, default=str)
        if key not in _cache:
            _cache[key] = real(cfg, release=release, today=today)
        return dict(_cache[key])

    cached.__wrapped__ = real
    build.build_pages = cached


import unittest  # noqa: E402


class BuildCacheTest(unittest.TestCase):
    def test_the_same_arguments_build_once_and_a_copy_is_returned(self):
        calls = []

        def fake(cfg, release=False, today=None):
            calls.append((release, today))
            return {"a": "x"}

        from sites.atomou import build
        real, before = build.build_pages, set(_cache)
        try:
            build.build_pages = fake
            install()
            first = build.build_pages({"k": 1}, release=True, today=date(2026, 10, 1))
            first["added"] = "y"                                                  # a test that changes its copy must not change the next test's
            second = build.build_pages({"k": 1}, release=True, today=date(2026, 10, 1))
            other = build.build_pages({"k": 2}, release=True, today=date(2026, 10, 1))
            self.assertEqual(second, {"a": "x"})
            self.assertEqual(len(calls), 2)                                       # (k=1) once, (k=2) once
            self.assertEqual(other, {"a": "x"})
        finally:
            build.build_pages = real
            for k in set(_cache) - before:                                         # only this test's own entries: the real builds stay cached for the others
                del _cache[k]


if __name__ == "__main__":
    unittest.main()
