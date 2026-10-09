"""The rewrite of existing wording: a new text replaces the old only when it keeps every number, stays about as long and passes the language gate."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sites.yorokobu import rewrite


class AcceptTest(unittest.TestCase):
    OLD = "選びやすいです。渡しやすいです。使いやすいです。持ち帰りやすいです。3つの品を、2週間前までに確認します。"

    def test_a_better_text_with_the_same_numbers_is_accepted(self):
        new = "手に取りやすい小ぶりな品です。薄型なので渡すときに場所を取りません。毎日使えて、持ち帰りも楽です。3つの品を、2週間前までに確認します。"
        self.assertEqual(rewrite.accept(self.OLD, new, "x"), [])

    def test_each_kind_of_bad_answer_is_refused(self):
        cases = {
            "numbers differ": "手に取りやすい小ぶりな品です。薄型なので渡すときに場所を取りません。毎日使えて持ち帰りも楽です。4つの品を、2週間前までに確認します。",
            "length": "小ぶりな品です。",
            "comma after every": "手に取って、渡して、選んで、使って、持ち帰って、確認します。3つの品を、2週間前に、確認します。を、に、で、が、も、へ。",
            "internal word": "ソムリエが選んだ薄型の品です。薄型なので渡すときに場所を取りません。毎日使えて持ち帰りも楽です。3つの品を、2週間前までに確認します。",
            "unchanged": self.OLD,
        }
        for label, new in cases.items():
            self.assertTrue(rewrite.accept(self.OLD, new, "x"), label)

    def test_a_new_forbidden_word_is_refused_but_one_the_old_text_had_is_not_the_new_texts_fault(self):
        new = "最高に使いやすい品です。薄型なので渡すときに場所を取りません。毎日使えて持ち帰りも楽です。3つの品を、2週間前までに確認します。"
        self.assertTrue(any("forbidden" in w for w in rewrite.accept(self.OLD, new, "x")))

    def test_a_rewrite_that_is_not_better_than_the_old_text_is_refused(self):
        old = "選びやすいです。渡しやすいです。使いやすいです。持ち帰りやすいです。3つの品を確認します。"
        same_problem = "選びやすいです。渡しやすいです。使いやすいです。持ち帰りやすいです。3つの品を見比べます。"
        self.assertTrue(any("not better" in w for w in rewrite.accept(old, same_problem, "x")))

    def test_issues_are_named_so_that_codex_can_act_on_them(self):
        self.assertTrue(rewrite.issues_of("選びやすい。渡しやすい。持ち帰りやすい。"))
        self.assertTrue(rewrite.issues_of("そっと寄り添う品です。"))
        self.assertTrue(rewrite.issues_of("誕生日や記念日を登録すると、3週間前に、カレンダーで、お知らせします。"))
        self.assertEqual(rewrite.issues_of("通勤バッグに入る薄型のポーチなら、職場で渡しても持ち帰れます。"), [])


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for kind in rewrite.KINDS:
            shutil.copy(rewrite.CONTENT / rewrite.KINDS[kind][0], self.dir / rewrite.KINDS[kind][0])
        self._old = rewrite.CONTENT
        rewrite.CONTENT = self.dir

    def tearDown(self):
        rewrite.CONTENT = self._old
        self.tmp.cleanup()

    def answer(self, edit):
        _, items = rewrite.load("pairs")
        k = rewrite.KINDS["pairs"][2](items[0])
        flds = rewrite.fields("pairs", items[0])
        edit(flds)
        p = self.dir / "answer.json"
        p.write_text(json.dumps({k: flds}, ensure_ascii=False), encoding="utf-8")
        return k, p

    def test_merging_the_unchanged_text_leaves_the_file_byte_for_byte_alone(self):
        before = hashlib.md5((self.dir / "pairs.json").read_bytes()).hexdigest()
        _, p = self.answer(lambda f: None)
        done, kept, _ = rewrite.merge("pairs", p)
        self.assertEqual(done, 0)
        self.assertEqual(hashlib.md5((self.dir / "pairs.json").read_bytes()).hexdigest(), before)

    def test_an_accepted_field_changes_only_that_text_and_a_refused_one_stays(self):
        raw_before = (self.dir / "pairs.json").read_bytes().decode("utf-8")
        _, items = rewrite.load("pairs")
        old_lead, old_r0 = items[0]["lead"], items[0]["reasons"][0]

        def edit(f):
            f["lead"] = old_lead.replace("、", "、", 1) + ""          # same text: unchanged
            f["reasons.0"] = "あ" * 5                                   # far too short: refused
            f["how_to_choose.0"] = rewrite.fields("pairs", items[0])["how_to_choose.0"].replace("確認", "見比べ", 1) if "確認" in items[0]["how_to_choose"][0] else f["how_to_choose.0"] + "。"
        k, p = self.answer(edit)
        done, kept, notes = rewrite.merge("pairs", p)
        _, after = rewrite.load("pairs")
        self.assertEqual(after[0]["reasons"][0], old_r0)               # refused
        self.assertEqual(after[0]["lead"], old_lead)
        raw_after = (self.dir / "pairs.json").read_bytes().decode("utf-8")
        self.assertEqual(raw_before.count("\r\n"), raw_after.count("\r\n"))   # the line endings are kept
        self.assertTrue(any("kept old" in n for n in notes))

    def test_an_unknown_page_or_field_is_reported_not_applied(self):
        p = self.dir / "answer.json"
        p.write_text(json.dumps({"no-such-page": {"lead": "x" * 40}}), encoding="utf-8")
        done, kept, notes = rewrite.merge("pairs", p)
        self.assertEqual(done, 0)
        self.assertTrue(any("unknown page" in n for n in notes))

    def test_the_brief_lists_the_worst_pages_first_and_never_the_titles(self):
        out, ans = self.dir / "b.md", self.dir / "a.json"
        rewrite.brief("pairs", 3, out, ans)
        text = out.read_text(encoding="utf-8")
        self.assertIn(ans.as_posix(), text)
        self.assertIn("never like a template", text)
        self.assertNotIn('"title"', text.split("TEXTS:")[1])
        worst = rewrite.ranked("pairs")[0][1]
        self.assertIn(worst, text)

    def test_every_kind_has_fields_and_a_score(self):
        for kind in rewrite.KINDS:
            _, items = rewrite.load(kind)
            self.assertTrue(items, kind)
            self.assertTrue(rewrite.fields(kind, items[0]), kind)
            self.assertGreaterEqual(len(rewrite.ranked(kind)), 1)


if __name__ == "__main__":
    unittest.main()
