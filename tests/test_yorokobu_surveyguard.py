"""Owner 2026-11-17: no figure of another party's study on a page.  The guard finds the sentences the pages showed until 2026-11-27 (negative tests),
passes what may stay, and runs over every content file and script of the site."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sites.yorokobu import build, content, surveyguard
from sokuhou.sitekit import BuildError
from tests.test_yorokobu_dataroom import FIX

OLD = [
    "20〜50代の880人を対象とした調査をもとにクリスマスに贈る相手を図にしました。",
    "プレゼントをする予定がある人は40.3%で、2024年から減る傾向にあると、調査は伝えています。",
    "調査時期: 2025年3月28日、回答 903人。",
    "出産祝いの上位を、343〜468人へのアンケートをもとに紹介します。",
    "母の日に贈る予定の品では、カーネーションなどの花が44%で最多(エン・ジャパン 2025年、903人)",
    "お中元に贈った品で最多は、和菓子・洋菓子の44.1%(郵便局のネットショップ 2025年、408人)の調査です。",
    "昨年クリスマスプレゼントを贈った人は54%",
    "有効回答数は贈る人1,791人です。",
    "贈る人の予算(n=1,791)",
    "日比谷花壇の母の日アンケートによる数字です。",
    "検索の動きはGoogle トレンドを当サイトが調べました。",
]
MAY_STAY = [
    "ある調査では、母の日の予算は3,000〜4,999円を考える人が多い傾向です。",
    "当サイトの母の日の商品は3,000〜4,999円がいちばん多く44%です。",
    "素材は綿100%で、通常のフィルターより強度が約20〜30%高い紙です。",
    "日比谷花壇の花束です。",
    "var n = 0; for (n = 1; n < 10; n++) {}",
    "1つのアンケートに届くのは40人の回答までです。",
    "予算(25%)・時期(20%)・相手についての情報量(20%)の加重平均です。",
    "過去5年の合計では約4割が12月に集まります。",
    "出生数は、2000年の119万人から、2024年の69万人へ、42%減りました。",
]


class GuardTest(unittest.TestCase):
    def test_finds_the_sentences_the_pages_used_to_show(self):
        for s in OLD:
            self.assertTrue(surveyguard.problems(s), s)

    def test_passes_trends_own_numbers_and_product_facts(self):
        for s in MAY_STAY:
            self.assertEqual(surveyguard.problems(s), [], s)

    def test_records_are_not_pages(self):
        self.assertEqual(surveyguard.check_content({"studies": [{"org": "株式会社アイディエーション"}], "sources": {"a": "Google トレンド"}}), [])
        self.assertTrue(surveyguard.check_content({"lead": "株式会社アイディエーションによる数字です。"}))

    def test_every_content_file_of_the_site_passes(self):
        for f in sorted((Path(build.HERE) / "content").rglob("*.json")):
            if f.name == "stats.json":                      # public statistics and the record behind the Mother's Day trend: never printed as they are
                continue
            self.assertEqual(surveyguard.check_content(json.loads(f.read_text(encoding="utf-8"))), [], f.name)

    def test_the_scripts_and_the_texts_in_the_code_pass(self):
        for f in sorted((Path(build.HERE) / "assets").glob("*.js")):
            self.assertEqual(surveyguard.problems(f.read_text(encoding="utf-8")), [], f.name)
        for name in ("aboutextra.py", "askpages.py", "dataroom.py"):
            self.assertEqual(surveyguard.problems((Path(build.HERE) / name).read_text(encoding="utf-8")), [], name)

    def test_a_content_file_with_a_figure_of_a_study_cannot_be_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIX, Path(tmp), dirs_exist_ok=True)
            content.load(Path(tmp))                         # as it is: fine
            f = Path(tmp) / "guides.json"
            data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            self.assertIsNotNone(data)
            data["guides"][0]["intro_note"] = "ある調査では、贈った人は54%でした。"
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(Path(tmp))


if __name__ == "__main__":
    unittest.main()
