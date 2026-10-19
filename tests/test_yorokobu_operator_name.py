"""2026-10-19, owner: do not show the company name where it is not needed; only where the law needs it (the operator information page).  It stood in the structured data
(JSON-LD author / publisher) of the articles, picks and the New Year feature, and in the editorial policy.  The site's own name goes there."""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from tests.yorokobu_data import rich_boyfriend

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "yorokobu"
OP = "社名テスト商会"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": OP, "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None, "adsense_pub_id": None}
TEXT = (".html", ".xml", ".json", ".txt", ".php", ".js", ".webmanifest")


def pages_with(root: Path, word: str) -> set[str]:
    return {f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file() and f.suffix in TEXT and word in f.read_text(encoding="utf-8", errors="ignore")}


class OperatorNameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_company_name_is_on_the_operator_page_and_nowhere_else_of_the_build(self):
        self.assertEqual(pages_with(self.root, OP), {"about/index.html"})

    def test_the_operator_page_still_names_the_operator(self):
        t = (self.root / "about" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f"<dt>運営者</dt><dd>{OP}</dd>", t)

    def test_the_code_of_the_site_does_not_read_the_operator_name_for_anything_it_shows(self):
        # the operator page, privacy and contact are made by sokuhou/sitekit.py (the law's minimum); the pages of this site never take the name
        for f in (ROOT / "sites" / "yorokobu").glob("*.py"):
            self.assertNotRegex(f.read_text(encoding="utf-8"), r"""\boperator_name\b""", f.name)

    def test_the_structured_data_of_a_page_names_the_site_not_the_company(self):
        # the shapes the articles, picks and the New Year feature print: author / publisher "Organization"
        for f in ("features.py", "picksite.py", "shogatsu.py", "build.py"):
            t = (ROOT / "sites" / "yorokobu" / f).read_text(encoding="utf-8")
            for m in re.finditer(r'"(?:author|publisher)": \{"@type": "Organization", "name": ([^}]*)\}', t):
                self.assertIn('cfg["site_name"]', m.group(1), f)

    def test_the_check_would_catch_a_page_that_prints_the_name(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pick").mkdir()
            (Path(td) / "pick" / "x.html").write_text(f'<script type="application/ld+json">{{"author":{{"name":"{OP}"}}}}</script>', encoding="utf-8")
            self.assertEqual(pages_with(Path(td), OP), {"pick/x.html"})


if __name__ == "__main__":
    unittest.main()
