"""The table cap of newsite.check_spec: 3 per page by default, a site may raise it in site.json (trend: 7, 2026-11-15). Negative cases: the default still stops a 4th table,
the raised cap still stops one more than it allows."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sokuhou import newsite

SITE = Path(__file__).resolve().parents[1] / "sites" / "trend"


def page(n):
    return {"_file": "x.json", "path": "/x/", "kind": "article", "parent": "/", "sources": [], "title": "t", "h1": "h", "description": "d", "sections": [{"table": {"cols": ["a"], "rows": [["1"]]}}] * n}


def tables_errors(spec, n):
    try:
        newsite.check_spec(spec, [page(n), {"_file": "h.json", "path": "/", "kind": "hub", "sources": [], "title": "t", "h1": "h", "description": "d", "sections": []}])
    except Exception as e:   # the check raises with all the errors in the message
        return str(e)
    return ""


class MaxTables(unittest.TestCase):
    def test_default_cap_is_three(self):
        self.assertIn("tables (at most 3", tables_errors({}, 4))
        self.assertNotIn("tables (at most", tables_errors({}, 3))

    def test_a_site_can_raise_it_and_the_raised_cap_still_stops(self):
        self.assertNotIn("tables (at most", tables_errors({"max_tables": 7}, 7))
        self.assertIn("tables (at most 7", tables_errors({"max_tables": 7}, 8))

    def test_trend_has_its_cap_and_a_reason(self):
        spec = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["max_tables"], 7)
        self.assertTrue(spec["max_tables_why"])


if __name__ == "__main__":
    unittest.main()
