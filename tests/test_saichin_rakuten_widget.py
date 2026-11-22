"""saichin: 楽天モーションウィジェットを、広告を出さないページ以外の全ページに共通テンプレートで入れる(オーナー指示 2026-11-22)。
1ページ最大3つ・『PR』を真上に・楽天の部品に他モールのリンクを混ぜない・固定/ポップアップなし・広告を出さないページ(NO_ADS_PATHS・運営者情報・プライバシー)には入れない。
検査の関数に、決まりを破った形を渡して「検出できること」(負例)も確かめる。県別・地方別ページの求人導線(提携済みの A8)も確かめる。"""
from __future__ import annotations

import re
import unittest

from sites.saichin import build, content, rakuten_widget as rw, work_pages
from tests.test_saichin_pages import SiteFixture

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


NO_WIDGET = set(build.NO_ADS_PATHS) | rw.EXTRA_SKIP
ARTICLE = ('<h1>題</h1><p class="lead">答え</p><h2>a</h2><p>a</p>' + "".join(f"<h2>節{i}</h2><p>b</p>" for i in range(6)) + "<h2>関連ページ</h2><ul></ul>")


class WidgetTemplate(unittest.TestCase):
    def test_three_in_order(self):
        t = rw.add("/x/", ARTICLE, set())
        self.assertEqual(t.count('class="rk-ad"'), 3)
        self.assertEqual(widget_problems("x", t), [])
        self.assertLess(t.index('class="rk-ad"'), t.index("<h2>a</h2>"))                   # right after the lead
        self.assertLess(t.rindex('class="rk-ad"'), t.index("<h2>関連ページ</h2>"))        # the last one is before the related pages

    def test_short_page_has_no_middle_one(self):
        self.assertEqual(rw.add("/x/", '<h1>題</h1><p class="lead">答え</p><h2>a</h2><p>x</p>', set()).count('class="rk-ad"'), 2)

    def test_no_ads_pages_get_none(self):
        for path in NO_WIDGET:
            self.assertNotIn('class="rk-ad"', rw.add(path, ARTICLE, set(build.NO_ADS_PATHS)), path)

    def test_idempotent(self):
        once = rw.add("/x/", ARTICLE, set())
        self.assertEqual(rw.add("/x/", once, set()), once)

    def test_negative_cases_are_detected(self):
        self.assertTrue(widget_problems("x", ARTICLE + rw.block() * 4))
        self.assertTrue(widget_problems("x", rw.block().replace('<p class="rk-pr">PR</p>', "")))
        self.assertTrue(widget_problems("x", rw.block().replace('<p class="rk-pr">', '<a href="https://www.amazon.co.jp/">a</a><p class="rk-pr">')))
        self.assertTrue(widget_problems("x", rw.block().replace('<div class="rk-box">', '<div class="rk-box" style="position:fixed">')))

    def test_widget_code_is_the_300x250_one(self):
        self.assertIn('rakuten_size="300x250"', rw.WIDGET_SCRIPT)
        self.assertIn(rw.AFFILIATE_ID, rw.WIDGET_SCRIPT)


class WidgetOnTheSite(SiteFixture):
    def pages(self):
        return [r for r in self.files if r.endswith(".html") and not r.startswith("google")]

    def path_of(self, rel: str) -> str:
        p = "/" + rel[: -len("index.html")] if rel.endswith("index.html") else "/" + rel
        return p

    def test_every_page_has_widgets_except_the_no_ads_pages(self):
        missing, extra, problems = [], [], []
        for rel in self.pages():
            t = self.read(rel)
            n = t.count('class="rk-ad"')
            skip = self.path_of(rel) in NO_WIDGET
            if skip and n:
                extra.append(rel)
            if not skip and n < 2:
                missing.append(rel)
            problems += widget_problems(rel, t)
        self.assertEqual((missing, extra, problems), ([], [], []))

    def test_the_adsense_tag_is_still_where_it_was(self):
        for rel in self.pages():
            if self.path_of(rel) in NO_WIDGET:
                self.assertNotIn("adsbygoogle", self.read(rel), rel)


class SeekerJobs(SiteFixture):
    def test_every_prefecture_page_has_the_job_links_and_a_pr_label(self):
        # the links sit in the 令和9年度の試算 section (outlook.py), written before this block; one place per page, not two
        for r in self.d["rows"]:
            t = self.read(f"{r['slug']}/index.html")
            for code in ("4BEL1J+AAX4YY", "4BEL1J+AFOLT6"):
                self.assertEqual(t.count(f"a8mat={code}+"), 2, (r["slug"], code))      # the link and its 1x1 counter image
            self.assertIn('<p class="pr-note"><strong>PR</strong>', t, r["slug"])

    def test_region_pages_have_the_job_links(self):
        for slug, _, _ in build.REGIONS:
            t = self.read(f"area/{slug}/index.html")
            self.assertIn("a8mat=4BEL1J+AAX4YY", t, slug)
            self.assertIn("a8mat=4BEL1J+AFOLT6", t, slug)

    def test_a_program_without_a_code_is_not_shown(self):
        saved = content.AFFILIATE.pop("workstaff")
        try:
            self.assertNotIn("ワークスタッフナビ", work_pages.region_jobs("中部地方", "静岡県", "1,097円"))
        finally:
            content.AFFILIATE["workstaff"] = saved


if __name__ == "__main__":
    unittest.main()
