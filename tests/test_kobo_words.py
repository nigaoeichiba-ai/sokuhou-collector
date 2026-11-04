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
        def fake(model, prompt, system=None):                 # the options are shuffled: choose the one with 不足 by its number
            n = next(int(line.split(".")[0]) for line in prompt.splitlines() if "不足" in line and line[:1].isdigit())
            return json.dumps({"best": n, "why": "x"})
        runner.set_backend(fake)
        opts = ["防災グッズ、全部そろってますか", "防災グッズ、不足はありませんか", "防災グッズを数えてみよう", "防災グッズ:人数分を確認", "防災グッズ、必要なもの教えます"]
        t, info = engine.pick_title(GOOD, opts)
        self.assertEqual(t, "防災グッズ、不足はありませんか")
        self.assertEqual(len(info["options"]), 3)                  # the 数えてみよう and the subtitle are out before the vote
        self.assertEqual(engine.set_title("# 古い題\n\n本文\n", "新しい題"), "# 新しい題\n\n本文\n")

    def test_standard_flow_has_three_haiku_readers_and_one_codex_proofreader(self):
        from tests.test_kobo import MAT
        seen = []

        def fake(model, prompt, system=None):
            seen.append(model)
            return json.dumps({"gist": "x", "points": []})
        runner.set_backend(fake)
        pp = engine.persona_points(GOOD, MAT)
        self.assertEqual(sorted(seen), ["codex", "haiku", "haiku", "haiku", "haiku", "sonnet"])      # no sonnet / haiku proofreaders unless the article is named
        self.assertEqual(len(pp["readers"]), 6)
        seen.clear()
        engine.persona_points(GOOD, dict(MAT, deep_readers=True))
        self.assertEqual(seen.count("sonnet"), 2)                                  # the named article gets all three proofreaders

    def test_the_owners_nine_points_on_the_bousai_parent(self):
        from sokuhou.kobo import lexicon
        cases = [("家の人数の行を見ると、目安が分かります。", "いっしょに暮らす人数の行を見ると"),
                 ("□のつかなかったものが、足りないものです。", None),
                 ("うちには、8つの種類のうち、いくつそろっていましたか？", "8項目のうち、そろっているのはいくつですか"),
                 ("いちばん足りないと思うのは、どれですか？", "いちばん足りない防災グッズはどれですか"),
                 ("足りない防災グッズは、下の一覧からそのページを読めます。", None),
                 ("置き場所が狭い家の、備えの分け方", "収納が少ない家の備え方"),
                 ("ふだんの買い物で備えをそろえる", "いつもの買い物で防災グッズを買い足す"),
                 ("一定量を持つ方法", "いつも一定量ストックしておく方法"),
                 ("足りないものから読むと、分かりやすいです。", "足りない防災グッズのページから読むと")]
        for text, expect in cases:
            self.assertTrue(lexicon.scan([text]), text)                         # every one is marked
            if expect:
                self.assertIn(expect, lexicon.autofix(text)[0], text)           # and the mechanical ones are replaced
        # "もの" is replaced only in the 備え context; a contract page is left alone
        self.assertIn("足りない防災グッズ", lexicon.autofix("家の備えで足りないものを確認します。")[0])
        self.assertEqual(lexicon.autofix("契約で足りないものを書きます。")[0], "契約で足りないものを書きます。")

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
