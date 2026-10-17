"""sokuhou.lexicon and its use in styleloop / naturaljp (the shared dictionary of wording that is really in use).

The dictionary files come from the style-corpus research (data/style/lexicon/); these tests read them, so they are skipped where the folder is absent (the code itself fails open).
"""
import unittest

from sokuhou import lexicon as lx
from sokuhou import naturaljp as nj
from sokuhou import styleloop as sl

HAVE = (lx.DIR / "gift_ja.json").exists() and (lx.DIR / "general_ja.json").exists() and (lx.DIR / "sources.json").exists()


@unittest.skipUnless(HAVE, "the lexicon folder is not in this checkout")
class Lexicon(unittest.TestCase):
    def test_the_reference_for_the_judge_carries_the_owner_corrections_and_marks_weak_terms(self):
        r = lx.reference("yorokobu")
        self.assertIn("「集まりを開いた人」→ 幹事 / 主催者", r)
        self.assertIn("[owner]", r)
        self.assertIn("弱=決め手にしない", r)
        self.assertIn("AIの文に見える型", r)
        self.assertLessEqual(len(r), 7000)
        for site in ("kuma", "saichin", "minna", "atomou"):
            self.assertIn("AIの文に見える型", lx.reference(site))                  # the general patterns go to every site
        self.assertEqual(lx.reference("nosuchsite").count("【避ける言い方"), 0)

    def test_the_prompts_of_the_judge_carry_it(self):
        p = sl.judge_prompt("yorokobu", [sl.Unit("heading", "集まりを開いた人へ")])
        self.assertIn("実際によく使われる言い方", p)
        self.assertIn("幹事", p)
        self.assertIn("決め手にしない", p)
        self.assertIn("辞書にある言い方", p)

    def test_support_scores_the_owners_wording_above_the_avoided_one_and_weak_terms_count_for_nothing(self):
        self.assertGreater(lx.support("yorokobu", "幹事や主催者へ、後日贈るお礼の品"), 0)
        self.assertLess(lx.support("yorokobu", "集まりを開いた人へ、後日贈るお礼"), 0)
        self.assertLess(lx.support("yorokobu", "祖父母や年長の家族へ"), 0)
        weak = next(t for p in lx.data("yorokobu")["people"] for t in p["prefer"] if t.get("strength") == "weak")
        term = lx.split_terms(weak["term"])[0]
        self.assertEqual(lx.support("yorokobu", f"{term}へ"), 0)                      # a weak term decides nothing
        self.assertEqual(lx.support("minna", "幹事へ"), 0)                              # another site: another dictionary

    def test_a_term_is_confirmed_only_when_a_source_was_really_read(self):
        self.assertTrue(lx.confirmed({"strength": "owner"}))
        self.assertFalse(lx.confirmed({"strength": "weak", "evidence": ["E1"]}))
        src = lx.sources()
        unread = next(k for k, v in src.items() if v.get("status") in ("unreadable", "search-summary-only"))
        read = next(k for k, v in src.items() if v.get("status") == "read")
        self.assertFalse(lx.confirmed({"strength": "medium", "evidence": [unread]}))
        self.assertTrue(lx.confirmed({"strength": "medium", "evidence": [unread, read]}))

    def test_a_rewording_may_not_bring_back_wording_the_owner_asked_us_to_avoid(self):
        self.assertIn("年長の家族", lx.owner_avoided("yorokobu"))
        bad = sl.check_rewrite("敬老の日の贈り物", "年長の家族への贈り物", "yorokobu", "heading")
        self.assertTrue(any("owner asked us to avoid" in b for b in bad), bad)
        self.assertEqual(sl.check_rewrite("年長の家族に贈る品", "年長の家族に贈る品を選ぶ", "yorokobu", "heading"), [])    # already there: not brought back by this change

    def test_the_candidate_the_real_texts_use_wins_whatever_the_judge_preferred(self):
        u = sl.Unit("heading", "集まりを開いた人へ後日そっと労う贈り方")
        item = {"candidates": [{"text": "世話をした人へ後日贈るお礼の品", "key": "a"}, {"text": "幹事へ後日贈るお礼の品", "key": "b"}, {"text": "後日贈る感謝の気持ち", "key": "c"}], "choice": 1}
        text, order, _ = sl.choose("yorokobu", u, item)
        self.assertEqual(text, "幹事へ後日贈るお礼の品")
        self.assertIn("辞書+", sl.evidence(order))

    def test_the_researchs_twenty_examples_are_models_of_the_judge(self):
        befores = {e["before"] for e in sl.examples()}
        self.assertIn("夜型の人へ朝を押しつけない贈り方", befores)
        self.assertGreaterEqual(len(sl.examples()), 30)


class HeadingRules(unittest.TestCase):
    def heads(self, texts, site="yorokobu"):
        blocks = [nj.Block("heading", t, i + 1, "txt") for i, t in enumerate(texts)]
        return {h.rule for h in nj.check_blocks(blocks, "x.html", site)}

    def test_the_headline_shapes_the_research_counted(self):
        self.assertIn("heading_negation_frame", self.heads(["夜型の人へ朝を押しつけない贈り方"]))
        self.assertIn("heading_negation_frame", self.heads(["退職する人へ重くならない選び方"]))
        self.assertNotIn("heading_negation_frame", self.heads(["使う場所を限定しない"]))                  # a plain piece of advice in a negation is not the shape
        self.assertIn("heading_mood_subtitle", self.heads(["お歳暮の贈り物 一年の感謝を静かに届ける"]))
        self.assertIn("heading_mood_subtitle", self.heads(["卒業祝いの基本作法"]))
        self.assertNotIn("heading_mood_subtitle", self.heads(["お歳暮の贈り方 時期・相場・のし"]))
        self.assertIn("compound_theme_coinage", self.heads(["帰省軽やか"]))
        self.assertNotIn("compound_theme_coinage", self.heads(["帰省の手土産"]))

    def test_an_action_verb_heading_counts_only_three_to_a_page(self):
        self.assertNotIn("heading_action_verb", self.heads(["包みを整える", "渡す役を決める"]))
        self.assertIn("heading_action_verb", self.heads(["包みを整える", "渡す役を決める", "金額を決める", "形を整える"]))

    def test_the_heading_rules_do_not_touch_body_sentences(self):
        body = [nj.Block("para", "夜型の人へ朝を押しつけない贈り方を考えます。", 1, "txt")]
        self.assertNotIn("heading_negation_frame", {h.rule for h in nj.check_blocks(body, "x.html", "yorokobu")})

    def test_a_site_with_many_negation_headings_is_reported_once(self):
        heads = [f"見出しの例{i}は朝を押しつけない" for i in range(3)] + [f"見出しの例{i}の選び方と相場" for i in range(20)]
        hits = nj.site_hits(heads, "yorokobu")
        self.assertEqual([h.rule for h in hits], ["heading_negation_density"])
        self.assertIn("3本", hits[0].sentence)
        self.assertEqual(nj.site_hits([f"見出しの例{i}の選び方と相場" for i in range(30)] + ["見出しの例は朝を押しつけない"], "yorokobu"), [])      # 1 of 31: under 10%
        self.assertEqual(nj.site_hits(heads[:10], "yorokobu"), [])                                      # too few headings to count

    def test_a_list_whose_items_all_end_alike_is_reported(self):
        items = [nj.Block("item", f"柔らかい線画の{i}番目のタッチ。", i + 1, "txt") for i in range(6)]
        self.assertIn("list_same_tail", {h.rule for h in nj.check_blocks(items, "x.html", "minna")})
        varied = [nj.Block("item", t, i + 1, "txt") for i, t in enumerate(["線画のタッチ。", "水彩の淡い色合い。", "ベタ塗りのフラットな絵。", "鉛筆で描いたような質感。", "ドットで描いた絵。", "切り絵風の素材。"])]
        self.assertNotIn("list_same_tail", {h.rule for h in nj.check_blocks(varied, "x.html", "minna")})
        short = items[:4]
        self.assertNotIn("list_same_tail", {h.rule for h in nj.check_blocks(short, "x.html", "minna")})


if __name__ == "__main__":
    unittest.main()
