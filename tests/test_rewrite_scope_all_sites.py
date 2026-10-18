"""The scope rule of test_yorokobu_rewrite_scope for the other sites: a dictionary line whose original is printed by a page template needs "scope": "template"
(2026-10-18 desk order, before edit/judge run on saichin, kuma, minna, atomou)."""
import unittest
from pathlib import Path

from sokuhou import styleloop as sl
from tests.test_yorokobu_rewrite_scope import template_strings, unscoped_template_hits

ROOT = Path(__file__).resolve().parents[1]


class AllSites(unittest.TestCase):
    def test_no_unscoped_template_line_in_any_dictionary(self):
        for site in ("saichin", "kuma", "minna", "atomou", "yorokobu"):
            d = ROOT / "sites" / site
            if not d.is_dir():
                continue
            py = [p for p in d.rglob("*.py")]
            other = list(d.rglob("*.js")) + list(d.rglob("*.tpl"))
            bad = unscoped_template_hits(sl.load_rewrites(site), template_strings(py, other))
            self.assertEqual(bad, [], f"{site}: add scope=template or move the line to data/style/edited/: {bad}")

    def test_an_unscoped_line_on_a_template_text_is_caught(self):
        d = ROOT / "sites" / "yorokobu"
        strings = template_strings(list(d.glob("*.py")), [])
        e = {"from": "渡す場面を思い浮かべる", "to": "x", "kind": "heading"}
        self.assertTrue(unscoped_template_hits([e], strings))


if __name__ == "__main__":
    unittest.main()
