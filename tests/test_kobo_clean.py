"""Natural sentences must never be marked by the dictionary or the sentence-level rules.  When a new dictionary entry (or rule) marks one of them, this fails:
fix the entry's exclusion (unless), or remove the example only if the owner says the sentence is not natural.  Run before every kobo publish (tools/kobo_publish.ps1)."""
import json
import unittest
from pathlib import Path

from sokuhou.kobo import doc, lexicon, style_rules

SENTENCE_LEVEL = {"S56", "S77", "S79", "S81", "S82", "S85", "S08", "S09", "S14", "S54"}
F = Path(__file__).parent.parent / "sokuhou" / "kobo" / "data" / "clean_sentences.json"


class CleanSentences(unittest.TestCase):
    def test_the_dictionary_does_not_mark_natural_sentences(self):
        self.assertEqual(lexicon.clean_conflicts(), [])

    def test_the_sentence_rules_do_not_mark_natural_sentences(self):
        for s in json.loads(F.read_text(encoding="utf-8"))["sentences"]:
            d = doc.parse("# 題\n\n冒頭です。二文目です。\n\n## 見出し\n" + s + "\n")
            codes = {x["code"] for x in style_rules.check(d) if x["code"] in SENTENCE_LEVEL}
            self.assertFalse(codes, f"{s} -> {codes}")


    def test_a_too_wide_entry_is_caught(self):
        """The accident of 2026-11-05: a new entry (決める) marked an old example sentence.  The check must see it."""
        import tempfile
        d = json.loads(lexicon.PATH.read_text(encoding="utf-8"))
        d["entries"].append({"id": "wX", "code": "S99", "label": "x", "pattern": "決め", "msg": "x", "replace": [], "auto": []})
        old = lexicon.PATH
        with tempfile.TemporaryDirectory() as td:
            lexicon.PATH = Path(td) / "w.json"
            lexicon.PATH.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            try:
                self.assertTrue([c for c in lexicon.clean_conflicts() if c[1] == "wX"])
            finally:
                lexicon.PATH = old


if __name__ == "__main__":
    unittest.main()
