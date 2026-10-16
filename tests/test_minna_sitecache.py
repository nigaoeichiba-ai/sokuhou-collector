"""One build of みんなのイラスト for the page tests, the print tests and the browser tests.

Each of them used to call render_site (12,000 files, about a minute) into its own folder and delete it afterwards (10 to 16 seconds), and the calendar test
built the same site a fourth time.  The three read the output and never write into it, so one build in one folder serves them all; the folder is removed
when the test run ends.  A test that needs something the build does not contain adds it elsewhere (the browser test serves its own page by a route).
(2026-10-16, the audit of the test times: docs/office/audit_test_durations_2026-10-16.md)
"""
from __future__ import annotations

import atexit
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.minna import build

SHARED_CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト運営", "contact_form_url": "https://example.com/form",
              "adsense_pub_id": None, "indexnow_key": "0123456789abcdef0123456789abcdef"}
SHARED_DAY = date(2026, 10, 7)

_built: dict = {}


def shared_site() -> tuple[Path, list[str]]:
    """(the folder of the one release build, the list of its files); read only."""
    if "out" not in _built:
        tmp = tempfile.TemporaryDirectory()
        atexit.register(tmp.cleanup)
        out = Path(tmp.name) / "site"
        _built["files"] = build.render_site(SHARED_CFG, out, release=True, today=SHARED_DAY)
        _built["out"] = out
    return _built["out"], list(_built["files"])


class SharedSiteTest(unittest.TestCase):
    def test_the_build_is_made_once_and_every_listed_file_is_there(self):
        out, files = shared_site()
        out2, files2 = shared_site()
        self.assertEqual(out, out2)                                   # the same folder, not a second build
        self.assertEqual(files, files2)
        self.assertGreater(len(files), 1000)
        self.assertTrue((out / "index.html").exists())
        self.assertTrue(all((out / f).exists() for f in files[:200]))

    def test_the_list_is_a_copy(self):
        _out, files = shared_site()
        files.append("not-a-file")
        self.assertNotIn("not-a-file", shared_site()[1])
