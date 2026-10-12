"""The ledger and the analysis of what visitors sent through the 贈り物コンシェルジュ (sites/yorokobu/voice.py)."""
import json
import tempfile
import unittest
from pathlib import Path

from sites.yorokobu import voice


def rec(i, kind, text, site="yorokobu"):
    return {"id": f"{i:02d}abcdef0123", "at": "2026-10-12T10:00:00+09:00", "site": site, "kind": kind, "message": text, "email": "", "page": ""}


class LedgerTest(unittest.TestCase):
    def test_only_the_concierge_lines_become_rows_and_each_line_once(self):
        ledger = []
        added = voice.add_new([rec(1, "miss", "金継ぎの器を探しています"), rec(2, "contact", "お問い合わせ"), rec(3, "why", "もっと小さな花", site="minna"), rec(4, "why", "  もっと  小さな花 ")], ledger)
        self.assertEqual([r["kind"] for r in added], ["miss", "why"])
        self.assertEqual(ledger[1]["text"], "もっと 小さな花")
        self.assertEqual(voice.add_new([rec(1, "miss", "金継ぎの器を探しています")], ledger), [])              # the same line again: nothing

    def test_the_ledger_roundtrips_and_a_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "x" / "ledger.jsonl"
            self.assertEqual(voice.read_ledger(p), [])
            rows = voice.add_new([rec(1, "miss", "金継ぎの器")], [])
            voice.write_ledger(rows, p)
            self.assertEqual(voice.read_ledger(p), rows)


class AnalysisTest(unittest.TestCase):
    KNOWN = {"母の日", "母", "誕生日", "コーヒー", "セール"}

    def rows(self):
        texts = ["金継ぎの器を贈りたい", "金継ぎ 器 母の日", "盆栽のプレゼント", "盆栽がほしい 母", "コーヒー好きに", "盆栽 盆栽 盆栽"]
        return [voice.to_row(rec(i, "miss", t)) for i, t in enumerate(texts, 1)]

    def test_words_the_site_does_not_know_are_counted_once_per_sentence(self):
        got = dict(voice.gaps(self.rows(), self.KNOWN))
        self.assertEqual(got["盆栽"], 3)                         # three sentences (the thrice-written one counts once)
        self.assertEqual(got["金継"], 2)
        self.assertNotIn("母の日", got)
        self.assertNotIn("コーヒー", got)
        self.assertNotIn("プレゼント", got)

    def test_the_report_has_counts_and_candidates_and_not_one_sentence(self):
        cq = {"need": {"who": 5, "sale": 2}, "res": {"hit": 7, "miss": 3}, "fb": {"yes": 4, "no": 2}, "rec": {"mother": 6}}
        text = voice.analyze(self.rows(), cq, self.KNOWN)
        self.assertIn("盆栽: 3 ← 候補", text)
        self.assertIn("見つかった」4 / 「見つからない」2", text)
        self.assertIn("who: 5", text)
        for sentence in ("金継ぎの器を贈りたい", "盆栽がほしい 母"):
            self.assertNotIn(sentence, text)

    def test_the_counters_are_read_by_kind(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "s.json"
            p.write_text(json.dumps({"total": {"cq.need.who": 3, "cq.res.hit": 2, "dock.occ.birthday": 9, "cq.bad": 1}}), encoding="utf-8")
            self.assertEqual(voice.counters(p), {"need": {"who": 3}, "res": {"hit": 2}})
            self.assertEqual(voice.counters(Path(t) / "none.json"), {})

    def test_the_words_the_site_knows_come_from_its_own_content(self):
        known = voice.known_words()
        for w in ("母の日", "お母さん", "彼女", "セール"):
            self.assertIn(w, known)


class WorkflowTest(unittest.TestCase):
    def test_the_workflow_encrypts_before_it_commits_and_never_stores_clear_text(self):
        wf = (Path(voice.__file__).resolve().parents[2] / ".github" / "workflows" / "yorokobu-voice.yml").read_text(encoding="utf-8")
        self.assertIn("openssl smime -encrypt", wf)
        self.assertIn("sokuhou/inbox_cert.pem", wf)
        self.assertIn("git add data/inbox", wf)
        self.assertNotIn("git add .", wf)
        self.assertIn("rm -f raw_voice.txt new_voice.jsonl", wf)


if __name__ == "__main__":
    unittest.main()
