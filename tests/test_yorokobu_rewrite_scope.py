"""data/style/rewrites/yorokobu.json replaces a text on EVERY page that has it.  A line whose original is a string of the page templates (features.py, build.py, ...)
therefore hits every page made from that template: on 2026-10-18 the heading 「渡す場面を思い浮かべる」 of the 8 detailed articles became 「在宅勤務の友人に贈る場面」
on all of them, because the line had been written for one article (a mug).  Such a line must say `"scope": "template"` (a person looked at it and the wording fits every page the
template makes); a rewording for one page belongs in data/style/edited/ (page-limited) or in the page's own content."""
import ast
import json
import unittest
from pathlib import Path

from sokuhou import styleloop as sl

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "yorokobu"


def template_strings(py_files, other_files) -> dict[str, list[str]]:
    """{file name: the text constants of its code (docstrings left out) or, for js/tpl files, the whole text}."""
    out: dict[str, list[str]] = {}
    for f in py_files:
        tree = ast.parse(Path(f).read_text(encoding="utf-8"))
        doc = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                    and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
                doc.add(id(n.body[0].value))
        out[Path(f).name] = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc]
    for f in other_files:
        out[Path(f).name] = [Path(f).read_text(encoding="utf-8")]
    return out


def unscoped_template_hits(entries: list[dict], strings: dict[str, list[str]]) -> list[tuple[str, str]]:
    """[(original, file)] of the lines without scope=template whose original is part of a template's text."""
    hits = []
    for e in entries:
        if e.get("scope") == "template":
            continue
        key = sl.norm(e["from"])
        for name, texts in strings.items():
            if any(key in t for t in texts):
                hits.append((e["from"], name))
                break
    return hits


def sources() -> dict[str, list[str]]:
    py = [p for p in SITE.glob("*.py")]
    other = [p for p in (SITE / "assets").glob("*.js")] + list(SITE.glob("*.tpl"))
    return template_strings(py, other)


class RewriteScopeTest(unittest.TestCase):
    def test_no_dictionary_line_rewrites_a_template_text_without_scope_template(self):
        entries = sl.load_rewrites("yorokobu")
        self.assertTrue(entries)
        bad = unscoped_template_hits(entries, sources())
        self.assertEqual(bad, [], "these lines replace text that the page templates print on every page; if the wording fits every such page add \"scope\": \"template\", "
                                  "otherwise move the rewording to data/style/edited/ (one page) or the page's content: " + str(bad))

    def test_the_scanner_finds_the_shared_headings(self):                                 # it must really see features.py, or the test above proves nothing
        s = sources()
        self.assertTrue(any("渡す場面を思い浮かべる" in t for t in s["features.py"]))
        self.assertTrue(any("数値の表を見る" in t for t in s["dataroom.py"]))

    def test_the_line_that_changed_all_8_articles_would_be_caught(self):                    # negative test: the 2026-10-17 line
        old = {"from": "渡す場面を思い浮かべる", "to": "在宅勤務の友人に贈る場面", "kind": "heading", "by": "editor"}
        self.assertEqual(unscoped_template_hits([old], sources()), [("渡す場面を思い浮かべる", "features.py")])
        self.assertEqual(unscoped_template_hits([dict(old, scope="template")], sources()), [])

    def test_a_rewording_of_a_text_that_is_not_in_a_template_is_not_flagged(self):
        e = {"from": "この文は、どのひな形にも載っていない", "to": "x", "kind": "note"}
        self.assertEqual(unscoped_template_hits([e], sources()), [])

    def test_docstrings_are_not_template_text(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.py"
            p.write_text('"""説明にだけ出す語句"""\n\ndef f():\n    """関数の説明の語句"""\n    return "<h2>見出しの語句</h2>"\n', encoding="utf-8")
            s = template_strings([p], [])
        es = [{"from": w, "to": "x"} for w in ("説明にだけ出す語句", "関数の説明の語句", "見出しの語句")]
        self.assertEqual([h[0] for h in unscoped_template_hits(es, s)], ["見出しの語句"])


if __name__ == "__main__":
    unittest.main()
