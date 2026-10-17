"""atomou: the 特集 (a long page for a big event, made from numbers; our view marked as such): the form is checked, an unfinished one is not found by search engines, the cards link to it with one
line, and the first one (箱根駅伝2027) is well formed and its numbers are the checked ones."""
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, features  # noqa: E402
from tests.test_atomou_build import CFG  # noqa: E402

TODAY = date(2026, 10, 13)


def feat(**kw):
    f = {"slug": "test-race", "stage": "公開", "title": "テスト大会を数字から読む", "lead": "テスト大会まで、あと何日か。数字から読みます。", "method": "数字は公式の記録です。",
         "sections": [{"h": "結果", "table": {"head": ["順位", "名前"], "rows": [["1", "A"], ["2", "B"]]}, "paras": ["Aが優勝しました。"]},
                      {"h": "見方", "view": True, "paras": ["Aが強いと考えられます。"], "how": "平均を取りました。"},
                      {"h": "差", "chart": {"title": "差(秒)", "unit": "秒", "rows": [["A", 0], ["B", 12.5]]}}],
         "updates": [{"on": "2026-10-13", "text": "公開しました。"}], "cards": [{"title": "テスト大会", "date": "2026-11-01"}]}
    f.update(kw)
    return f


class Form(unittest.TestCase):
    def test_a_good_feature_is_valid_and_each_kind_of_damage_is_not(self):
        self.assertTrue(features.valid(feat()))
        bad = {
            "a slug with a capital": feat(slug="Test"),
            "no title": feat(title=""),
            "a stage that does not exist": feat(stage="下書き"),
            "no method": feat(method=""),
            "no sections": feat(sections=[]),
            "a section with nothing to show": feat(sections=[{"h": "空"}]),
            "a section without a heading": feat(sections=[{"h": "", "paras": ["x"]}]),
            "a table row of the wrong width": feat(sections=[{"h": "表", "table": {"head": ["a", "b"], "rows": [["1"]]}}]),
            "a chart value that is not a number": feat(sections=[{"h": "図", "chart": {"rows": [["A", "x"]]}}]),
        }
        for why, f in bad.items():
            self.assertFalse(features.valid(f), why)

    def test_the_bar_chart_is_plain_svg_with_the_figures_written(self):
        svg = features.bar_svg({"title": "差", "unit": "秒", "rows": [["A", 0], ["B", 12.5]]})
        self.assertTrue(svg.startswith("<svg") and svg.endswith("</svg>"))
        self.assertIn("12.5秒", svg)
        self.assertNotIn("<script", svg)


class InTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)

    def test_the_first_feature_has_its_pages_its_chip_and_its_link_on_the_cards(self):
        self.assertIn("tokushu/hakone-2027/index.html", self.pages)
        self.assertIn("tokushu/index.html", self.pages)
        page = self.pages["tokushu/hakone-2027/index.html"]
        self.assertIn("箱根駅伝2027(第103回)を数字から読む", page)
        self.assertIn("当サイトの見方", page)                       # our view is marked
        self.assertIn("この特集は、公式の記録など数字と事実をもとに当サイトが作った分析です", page)      # and the page says what it is
        self.assertIn('href="/tokushu/"', self.pages["index.html"])
        linked = [k for k, v in self.pages.items() if k.startswith("e/") and isinstance(v, str) and 'href="/tokushu/hakone-2027/"' in v]
        self.assertGreaterEqual(len(linked), 4)                     # the cards of the race and its steps (the race, its qualifier, and the two races before it)

    def test_the_numbers_of_the_first_feature_are_the_checked_ones(self):
        f = json.loads((ROOT / "data/atomou/features/hakone-2027.json").read_text(encoding="utf-8"))
        self.assertTrue(features.valid(f))
        text = json.dumps(f, ensure_ascii=False)
        for fact in ("10:37:34", "217.1km", "2:05:56", "2027年1月2日(土)往路", "山梨学院大学", "10月17日"):
            self.assertIn(fact, text)
        view = [s for s in f["sections"] if s.get("view")]
        self.assertTrue(view and all(s.get("how") for s in view))   # every view says how its figure was made
        for s in f["sections"]:
            for p in s.get("paras") or []:
                self.assertNotIn("必ず", p)                          # no promise about a race

    def test_an_unfinished_feature_is_held_back_from_search_engines_and_the_sitemap(self):
        c = build.Ctx(CFG, False, TODAY, [], build.skins.css())      # a build that is not a preview (a preview is noindex everywhere)
        html, idx = features.feature_page(c, feat(stage="準備中"), "名前")
        self.assertFalse(idx)
        self.assertIn("noindex", html)
        html2, idx2 = features.feature_page(c, feat(), "名前")
        self.assertTrue(idx2)
        self.assertNotIn("noindex", html2)
        self.assertIn("<dt>", features.card_link([feat()], "x", "y") + "<dt>")
        self.assertEqual(features.card_link([feat()], "別の大会", "2026-11-01"), "")
        self.assertIn('href="/tokushu/test-race/"', features.card_link([feat()], "テスト大会", "2026-11-01"))

    def test_the_sitemap_lists_the_published_feature(self):
        self.assertIn("/tokushu/hakone-2027/", self.pages["sitemap.xml"])


if __name__ == "__main__":
    unittest.main()
