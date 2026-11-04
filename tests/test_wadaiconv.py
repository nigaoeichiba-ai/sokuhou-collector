"""Tests of wadaiconv: the workshop's markdown becomes a page with real parts, and its text is not touched."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from sokuhou import wadaiconv as cv

MD = """# 防災の数え方

台風が近づいています。家の備えを数えてみませんか。

## 3行まとめ
- 一つ目の要点
- 二つ目の要点
- 三つ目の要点

## 目次
- ■ 数え方
- 買い足し

## ■ 数え方

数え方は簡単です。人数と日数をかけます。

[表: 人数別の早見表]

表の数字を見てください。

[チェックリスト]

[アンケート]

## 買い足し

足りない分を足します。

[商品カード]

[子ページの案内]

> ライフハック: 少しずつ足す
> ふだんの買い物で少し多めに買います。

> 豆知識: 名前の話
> 台風の名前は順番に使います。
"""
MAT = {"parts": [{"mark": "[表: 人数別の早見表]", "what": "x", "content": "| 人数 | 水 3日分 | 食事 3日分 |\n|---|---|---|\n| 1人 | 9L | 9食 |\n| 2人 | 18L | 18食 |"},
                 {"mark": "[チェックリスト]", "what": "x", "content": "□ 水 □ 食料 □ ライト"}]}
CFG = {"pages": {"p1": {"series": "総点検", "polls": [{"id": "a", "question": "いくつ?", "options": ["0〜1", "2〜3"]}, {"id": "b", "question": "足りないのは?", "options": ["水", "食料", "特にない"]}],
                        "children": [{"title": "水の数え方", "href": "kobo_p2.html"}]}}}


def make(tmp: Path, md=MD, mat=MAT):
    d = tmp / "out" / "p1"
    d.mkdir(parents=True)
    (d / "article-opus.md").write_text(md, encoding="utf-8")
    (d / "article-opus.json").write_text(json.dumps({"updated": "2026-11-04"}), encoding="utf-8")
    (tmp / "materials").mkdir()
    (tmp / "materials" / "p1.json").write_text(json.dumps(mat, ensure_ascii=False), encoding="utf-8")
    return tmp


class TestConv(unittest.TestCase):
    def build(self, **kw):
        with tempfile.TemporaryDirectory() as t:
            make(Path(t), **kw)
            return cv.build_page("p1", Path(t), CFG, Path(t))

    def test_parse(self):
        m = cv.parse_md(MD)
        self.assertEqual(m["title"], "防災の数え方")
        self.assertTrue(m["lead"].startswith("台風が近づいています"))
        self.assertEqual(len(m["tldr"]), 3)
        self.assertEqual([s["heading"] for s in m["sections"]], ["数え方", "買い足し"])          # the leading ■ is dropped from the heading
        kinds = [b["t"] for s in m["sections"] for b in s["blocks"]]
        self.assertEqual(kinds.count("mark"), 5)
        self.assertEqual(kinds.count("box"), 2)

    def test_every_marker_becomes_a_part_and_the_text_is_untouched(self):
        page, info = self.build()
        self.assertEqual(info["unresolved"], [])
        self.assertNotIn("[表:", page)
        self.assertNotIn("[チェックリスト]", page)
        self.assertNotIn("[アンケート]", page)
        self.assertIn("<table", page)
        self.assertIn('class="calc"', page)                                      # people -> amounts
        self.assertEqual(page.count('class="poll"'), 2)                          # two polls
        self.assertEqual(page.count('type="checkbox"'), 3)
        self.assertIn('class="slot"', page)
        self.assertIn('href="kobo_p2.html"', page)
        for para in ("数え方は簡単です。人数と日数をかけます。", "表の数字を見てください。", "足りない分を足します。", "台風が近づいています。家の備えを数えてみませんか。"):
            self.assertIn(para, page)
        self.assertIn("ライフハック", page)
        self.assertIn("豆知識", page)

    def test_the_ad_note_is_not_shown_without_a_product(self):
        page, _ = self.build()
        self.assertNotIn("下の案内には広告が含まれます", page)

    def test_a_marker_with_no_data_is_reported_not_hidden(self):
        page, info = self.build(mat={"parts": []})
        self.assertIn("[表: 人数別の早見表]", info["unresolved"])
        self.assertIn("部品がまだありません", page)

    def test_the_poll_says_it_is_optional_and_asks_for_nothing_personal(self):
        page, _ = self.build()
        self.assertIn("答えは任意です", page)
        self.assertNotRegex(page, r"名前を入力|メールアドレス")

    def test_cost_table_has_inputs_and_computed_rows(self):
        md = "| 項目 | A店 | B店 |\n|---|---|---|\n| 1回の料金 × 回数 | | |\n| 入会金 | | |\n| 一緒に勧められた商品・サービス | | |\n| そのほか(通う交通費など) | | |\n| 総額 | | |\n| 総額 ÷ 回数(1回あたり) | | |\n| 途中でやめたときに請求される額 | | |"
        html = cv.table_part("総額の計算", md, "cost")
        self.assertEqual(html.count('data-k="price"'), 2)
        self.assertEqual(html.count('data-k="total"'), 2)
        self.assertEqual(html.count('data-k="per"'), 2)
        self.assertIn("costcalc", html)

    def test_html_in_the_text_is_escaped(self):
        page, _ = self.build(md=MD.replace("数え方は簡単です。", "数え方は<script>alert(1)</script>簡単です。"))
        self.assertNotIn("<script>alert(1)</script>", page)


if __name__ == "__main__":
    unittest.main()
