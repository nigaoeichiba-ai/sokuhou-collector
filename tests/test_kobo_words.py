"""Tests of the named-word check, the title vote, the text statistics and the audit (kobo light mode). The models are faked."""
import json
import unittest

from sokuhou.kobo import doc, engine, runner, textstats
from tests.test_kobo import GOOD


class Words(unittest.TestCase):
    def tearDown(self):
        runner.set_backend(None)

    def test_named_check_asks_three_models_by_word_and_learns(self):
        asked = []

        def fake(model, prompt, system=None):
            if "各行は" in prompt:
                asked.append(model)
                return json.dumps({"items": [{"n": 1, "natural": model == "haiku", "reason": "場所ではない", "alternatives": ["a", "b", "c"]}]})
            return GOOD
        runner.set_backend(fake)
        text = "# 題\n\n冒頭の文です。2文目です。\n\n## 3行まとめ\n- 一\n- 二\n- 三\n\n## 見出し\n\n足りない所を確認します。\n"
        nc = engine.named_check(text)
        self.assertEqual(sorted(asked), ["codex", "haiku", "sonnet"])
        f = nc["flagged"][0]
        self.assertEqual(sorted(f["by"]), ["codex", "sonnet"])      # haiku said it was natural; one model saying no is enough
        self.assertEqual(f["id"], "w04")
        self.assertIn("言い換え案", engine.named_notes(nc))
        self.assertEqual(len(nc["learned"]), 2)

    def test_title_is_picked_by_votes_and_bad_titles_are_dropped(self):
        def fake(model, prompt, system=None):
            return json.dumps({"best": 2, "why": "x"})
        runner.set_backend(fake)
        opts = ["防災グッズ、全部そろってますか", "防災グッズ、不足はありませんか", "防災グッズを数えてみよう", "防災グッズ:人数分を確認", "防災グッズ、必要なもの教えます"]
        t, info = engine.pick_title(GOOD, opts)
        self.assertEqual(t, "防災グッズ、不足はありませんか")
        self.assertEqual(len(info["options"]), 3)                  # the 数えてみよう and the subtitle are out before the vote
        self.assertEqual(engine.set_title("# 古い題\n\n本文\n", "新しい題"), "# 新しい題\n\n本文\n")

    def test_stats_and_the_audit_of_what_the_rewrite_added(self):
        st = textstats.stats(doc.parse(GOOD))
        self.assertIn("len_cv", st)
        d = "# 題\n\n文です。\n"
        f = "# 題\n\n文です。市は9月に1200件と発表しました。いちばん多いのでそうなります。\n"
        msgs = " ".join(x["msg"] for x in textstats.audit(d, f, ""))
        self.assertIn("1200", msgs)
        self.assertIn("最上級", msgs)
        self.assertIn("理由", msgs)

    def test_learned_reasons_are_merged_once(self):
        import tempfile
        from pathlib import Path
        from sokuhou.kobo import lexicon
        with tempfile.TemporaryDirectory() as td:
            lexicon.LEARNED_PATH = Path(td) / "learned.json"
            try:
                item = {"id": "w04", "model": "sonnet", "reason": "場所ではない", "alternatives": ["足りないもの"]}
                self.assertEqual(lexicon.merge_learned([item, item]), 1)           # the same reason twice is one
                self.assertEqual(json.loads(lexicon.LEARNED_PATH.read_text(encoding="utf-8"))["w04"][0]["reason"], "場所ではない")
            finally:
                lexicon.LEARNED_PATH = None


if __name__ == "__main__":
    unittest.main()
