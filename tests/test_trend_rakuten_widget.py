"""trend: 楽天モーションウィジェットを、トップ・カテゴリ・記事の全ページに共通テンプレートで入れる(オーナー指示 2026-11-22)。
1ページ最大3つ・『PR』を真上に・法務ページには入れない・楽天の部品は単独のブロック(他モールのリンクを混ぜない)・商品情報を出力に保存しない。
検査の関数に、決まりを破った形を渡して「検出できること」(負例)も確かめる。"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sites" / "trend"))
import rakuten_widget as rw  # noqa: E402

BLOCK_RE = re.compile(r'<aside class="rk-ad".*?</aside>', re.S)


def widget_problems(rel: str, t: str) -> list[str]:
    out = []
    blocks = BLOCK_RE.findall(t)
    if len(blocks) > rw.MAX_PER_PAGE:
        out.append(f"{rel}: ウィジェットが{len(blocks)}個(最大{rw.MAX_PER_PAGE})")
    for b in blocks:
        if '<p class="rk-pr">PR</p>' not in b:
            out.append(f"{rel}: ウィジェットの真上に『PR』が無い")
        if re.search(r"amazon|yahoo|a8\.net|valuecommerce|accesstrade", re.sub(r"<script.*?</script>", "", b, flags=re.S), re.I):
            out.append(f"{rel}: 楽天の部品に他モールのリンクが混ざっている")
        if re.search(r"position:\s*(fixed|sticky)|popup|modal", b, re.I):
            out.append(f"{rel}: 固定・ポップアップの表示がある")
    return out


ARTICLE = ('<main class="wrap"><h1>題</h1><p class="answer">答え</p><h2>3行まとめ</h2><p>a</p>' + "".join(f"<h2>節{i}</h2><p>b</p>" for i in range(6)) + "<h2>関連するページ</h2><ul></ul>"
           '<p class="credit">出典</p></main><footer></footer>')


class WidgetTemplate(unittest.TestCase):
    def test_article_gets_three_in_order(self):
        t = rw.add("x/index.html", ARTICLE)
        self.assertEqual(t.count('class="rk-ad"'), 3)
        self.assertEqual(widget_problems("x", t), [])
        self.assertLess(t.index('class="rk-ad"'), t.index("<h2>3行まとめ</h2>"))                 # right after the lead
        self.assertLess(t.rindex('class="rk-ad"'), t.index("<h2>関連するページ</h2>"))           # the last one is before the related articles

    def test_short_article_has_no_middle_one(self):
        t = rw.add("x/index.html", '<main class="wrap"><h1>題</h1><h2>a</h2><p>x</p><h2>関連するページ</h2><ul></ul></main>')
        self.assertEqual(t.count('class="rk-ad"'), 2)

    def test_idempotent(self):
        once = rw.add("x/index.html", ARTICLE)
        self.assertEqual(rw.add("x/index.html", once), once)

    def test_negative_cases_are_detected(self):
        many = ARTICLE + rw.block(True) * 4
        self.assertTrue(widget_problems("x", many))
        no_pr = rw.add("x/index.html", ARTICLE).replace('<p class="rk-pr">PR</p>', "")
        self.assertTrue(widget_problems("x", no_pr))
        mixed = rw.add("x/index.html", ARTICLE).replace('<p class="rk-pr">', '<a href="https://www.amazon.co.jp/">a</a><p class="rk-pr">')
        self.assertTrue(widget_problems("x", mixed))
        fixed = rw.add("x/index.html", ARTICLE).replace('class="rk-ad"', 'class="rk-ad" style="position:fixed;bottom:0"')
        self.assertTrue(widget_problems("x", fixed))

    def test_no_product_data_in_the_snippet(self):
        self.assertNotIn("itemCode", rw.WIDGET_SCRIPT)
        self.assertIn("rakuten_size=\"300x250\"", rw.WIDGET_SCRIPT)


class RealBuild(unittest.TestCase):
    def test_pages(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(ROOT / "sites" / "trend" / "build.py"), "--release", "--out", d], check=True, capture_output=True, cwd=ROOT)
            out = Path(d)
            for rel in ("index.html", "cat/bousai/index.html", "bousai-light/index.html"):
                t = (out / rel).read_text(encoding="utf-8")
                self.assertGreaterEqual(t.count('class="rk-ad"'), 2, rel)
                self.assertEqual(widget_problems(rel, t), [], rel)
            for rel in ("about/index.html", "privacy/index.html", "contact/index.html", "404.html"):
                self.assertNotIn('class="rk-ad"', (out / rel).read_text(encoding="utf-8"), rel)
            for f in out.rglob("index.html"):
                self.assertEqual(widget_problems(str(f), f.read_text(encoding="utf-8")), [], str(f))


if __name__ == "__main__":
    unittest.main()
