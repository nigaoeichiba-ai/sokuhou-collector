import copy
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import factory, quality

FIX = Path(__file__).parent / "fixtures" / "yorokobu"


def good_theme(slug="rainy-day", **over):
    t = {"slug": slug, "group": "feeling", "name": "雨の日に", "title": "雨の日に届けたいプレゼント",
         "lead": "外に出るのがおっくうな雨の日は、家の中で気分が上がる小さな品が似合います。使い道が決まっていて、置き場所に困らない物を選ぶと、受け取る側も気楽です。窓の外の天気とは関係なく、気持ちよく過ごしてもらえる贈り方を探します。",
         "reasons": ["家で使える物は、天気に関係なく使い道がはっきりしています。", "香りや温かさのある物は、気分を切り替えるきっかけになります。", "小さめの品なら、重ねて贈っても場所を取りません。"],
         "how_to_choose": ["置く場所を想像して、大きさを決める。", "香りは弱めを選び、好みが分かれにくくする。", "届く日が雨でも使えるよう、防水の包装を確かめる。"],
         "avoid": ["濡れると傷む素材の物", "強い香りの物"], "recipient": None,
         "ideas": [{"label": "ルームシューズ", "type": "ファッション小物", "query": "ルームシューズ ギフト 洗える", "why": "家の中で足元から温めてくれて、雨の日の気分を上げてくれます。"},
                   {"label": "ハーブティー", "type": "食べもの・飲みもの", "query": "ハーブティー ティーバッグ 詰め合わせ", "why": "湯気と香りでほっとできて、雨音を聞きながら味わえます。"},
                   {"label": "ブランケット", "type": "癒し・リラックス", "query": "ブランケット ひざ掛け 洗える", "why": "ソファや椅子で羽織れて、湿った日の肌寒さをやわらげます。"},
                   {"label": "室内干しグッズ", "type": "実用品", "query": "室内干し ハンガー おしゃれ", "why": "洗濯物が乾きにくい日の手間を減らす、気の利いた実用品です。"}],
         "keywords": ["ルームシューズ", "ハーブティー", "ブランケット", "室内干し", "入浴剤", "アロマ", "傘", "レインブーツ"], "tiers": ["under3000", "3000-5000"]}
    t.update(over)
    return t


def good_article(slug="ask-without-asking", **over):
    a = {"slug": slug, "title": "さりげなく好みを聞き出す会話のコツ", "lead": "贈り物を選ぶ前に、相手の好みをそっと知っておけると、選ぶ時間が楽になります。会話の中で自然に聞き出す方法を、場面ごとに紹介します。聞きすぎて相手に気づかれないための、ちょっとした工夫もまとめました。",
         "sections": [{"h": f"場面その{i}の聞き方", "body": "最近買ったものや気に入っているものを話題にすると、相手は構えずに答えてくれます。" * 4 + f"{i}番目の場面では、聞き方を少し変えて、相手の返事を広げるように問いかけます。"} for i in range(4)],
         "checklist": ["聞きすぎない", "メモは後で取る"], "faq": [{"q": "聞いても失礼になりませんか", "a": "雑談の形で、相手の話を広げる聞き方なら失礼にはなりません。"}, {"q": "聞けないときはどうしますか", "a": "共通の知人や、相手の持ち物から好みを推し量る方法があります。"}],
         "themes": ["beauty", "thanks-daily"]}
    a.update(over)
    return a


class FactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for f in FIX.glob("*.json"):
            shutil.copy(f, self.dir / f.name)
        self._orig = factory.CONTENT
        factory.CONTENT = self.dir

    def tearDown(self):
        factory.CONTENT = self._orig
        self.tmp.cleanup()

    def test_a_good_theme_is_merged_with_its_date(self):
        n, probs = factory.merge_themes({"themes": [good_theme()]}, date(2026, 10, 8))
        self.assertEqual((n, probs), (1, []))
        data = json.loads((self.dir / "themes.json").read_text(encoding="utf-8"))
        self.assertEqual(data["themes"][-1]["added"], "2026-10-08")

    def test_bad_themes_are_refused_with_reasons(self):
        for bad, needle in ((good_theme(lead="短い"), "lead length"), (good_theme(slug="beauty"), "slug exists"),
                            (good_theme(title="人気の贈り物ランキングで選ぶプレゼント"), "forbidden"), (good_theme(group="nope"), "unknown group"),
                            (good_theme(slug="Rain Day"), "slug must be")):
            n, probs = factory.merge_themes({"themes": [bad]}, date(2026, 10, 8))
            self.assertEqual(n, 0)
            self.assertTrue(any(needle in p for p in probs), (needle, probs))

    def test_a_query_already_used_is_refused(self):
        t = good_theme()
        t["ideas"][0]["query"] = "焼き菓子 詰め合わせ 個包装"      # the fixture's thanks-daily uses it
        n, probs = factory.merge_themes({"themes": [t]}, date(2026, 10, 8))
        self.assertTrue(any("already used" in p for p in probs))

    def test_a_new_group_comes_along(self):
        n, probs = factory.merge_themes({"themes": [good_theme(group="situation")], "new_groups": [{"slug": "situation", "name": "場面から選ぶ", "blurb": "渡す場面から探します。"}]}, date(2026, 10, 8))
        self.assertEqual((n, probs), (1, []))
        self.assertTrue((self.dir / "theme_groups.json").exists())

    def test_articles_merge_and_refuse(self):
        n, probs = factory.merge_articles({"articles": [good_article()]}, date(2026, 10, 8))
        self.assertEqual((n, probs), (1, []))
        data = json.loads((self.dir / "articles.json").read_text(encoding="utf-8"))
        self.assertEqual(data["articles"][0]["date"], "2026-10-08")
        for bad, needle in ((good_article(slug="x", themes=["nope", "beauty"]), "related themes"), (good_article(slug="y", sections=[]), "missing sections"),
                            (good_article(slug="ask-without-asking"), "slug exists")):
            n, probs = factory.merge_articles({"articles": [copy.deepcopy(bad)]}, date(2026, 10, 9))
            self.assertEqual(n, 0)
            self.assertTrue(any(needle in p for p in probs), (needle, probs))

    def test_briefs_name_what_is_already_covered(self):
        out = self.dir / "b.md"
        factory.brief("themes", 4, out, Path("x/answer.json"))
        text = out.read_text(encoding="utf-8")
        self.assertIn("thanks-daily", text)
        self.assertIn("x/answer.json", text)
        factory.merge_articles({"articles": [good_article()]}, date(2026, 10, 8))
        factory.brief("articles", 3, out, Path("x/a2.json"))
        self.assertIn("ask-without-asking", out.read_text(encoding="utf-8"))

    def test_map_dots_of_a_new_theme_are_kept_and_bad_ones_ignored(self):
        t = good_theme(map=[[1, 0], [-2, -1], [1.5, 1], [0, 2]])
        n, probs = factory.merge_themes({"themes": [t]}, date(2026, 10, 8))
        self.assertEqual((n, probs), (1, []))
        tags = json.loads((self.dir / "map_tags.json").read_text(encoding="utf-8")) if (self.dir / "map_tags.json").exists() else {}
        self.assertEqual(tags["theme-rainy-day"][1], [-2, -1])
        t2 = good_theme(slug="rainy-day-two", map=[[9, 9]] * 4)
        t2["ideas"] = [{**i, "query": i["query"] + " 二"} for i in t2["ideas"]]
        n, probs = factory.merge_themes({"themes": [t2]}, date(2026, 10, 9))
        tags = json.loads((self.dir / "map_tags.json").read_text(encoding="utf-8"))
        self.assertNotIn("theme-rainy-day-two", tags)

    def test_retry_brief_carries_the_problems(self):
        ans = self.dir / "answer.json"
        ans.write_text(json.dumps({"themes": [good_theme(lead="短い")]}, ensure_ascii=False), encoding="utf-8")
        n, probs = factory.merge_themes(json.loads(ans.read_text(encoding="utf-8")), date(2026, 10, 8))
        ans.with_suffix(".problems.txt").write_text("\n".join(probs), encoding="utf-8")
        out = self.dir / "retry.md"
        factory.retry_brief("themes", ans, out)
        text = out.read_text(encoding="utf-8")
        self.assertIn("lead length", text)
        self.assertIn("answer_fixed.json", text)


class QualityTest(unittest.TestCase):
    def test_repeated_sentences(self):
        s = "これは二十五文字を超える、同じ文章が二回出てくるかどうかを調べるための長い文です。"
        self.assertEqual(quality.repeated_sentences([s, "別の文。" + s]), [s.rstrip("。")])


if __name__ == "__main__":
    unittest.main()
