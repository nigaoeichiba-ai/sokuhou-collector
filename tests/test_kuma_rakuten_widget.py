"""kuma: 楽天モーションウィジェットは、広告を出すページに共通部品で入れる。1ページ最大3つ・『PR』を真上に・人身被害が主題のページは本文の最後に1つだけ・
広告を出さないページ(連絡先など)とnoindexには入れない・楽天の部品は単独のブロック。「次の行動」の節には、理由の1文とPR・rel つきのリンクがあり、人身被害のページには置かない。
検査の関数に、決まりを破った形を渡して「検出できること」(負例)も確かめる。"""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build
from sites.kuma import rakuten_widget as rw
from tests.test_kuma_build import CFG, HAVE_PYPDF, LINKS, raw_data

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
    if blocks and rw.page_kind(t) == "harm":
        if len(blocks) != 1 or t.find('class="rk-ad"') < t.find("<h2"):
            out.append(f"{rel}: 人身被害のページで、最後の1つ以外にウィジェットがある")
    return out


def page(h1="題", extra="", h2s=("a", "b"), head=""):
    return (f"<html><head>{head}</head><body><main class=\"wrap\"><h1>{h1}</h1><p class=\"lead\">答え</p>{extra}"
            + "".join(f"<h2>{h}</h2><p>x</p>" for h in h2s) + "<h2>関連する研究ノート</h2><ul class=\"link-list\"></ul></main></body></html>")


class WidgetTemplate(unittest.TestCase):
    def test_normal_page_lead_middle_end(self):
        t = rw.add("x/index.html", page(h2s=[f"節{i}" for i in range(7)]))
        self.assertEqual(t.count('class="rk-ad"'), 3)
        self.assertEqual(widget_problems("x", t), [])
        self.assertLess(t.index('class="rk-ad"'), t.index("<h2>節0</h2>"))
        self.assertLess(t.rindex('class="rk-ad"'), t.index("<h2>関連する研究ノート</h2>"))

    def test_harm_page_only_one_at_the_end(self):
        t = rw.add("deaths/index.html", page(h1="熊による死亡事故の一覧", h2s=["一覧", "月別"]))
        self.assertEqual(t.count('class="rk-ad"'), 1)
        self.assertGreater(t.index('class="rk-ad"'), t.index("<h2>月別</h2>"))
        self.assertLess(t.index('class="rk-ad"'), t.index("<h2>関連する研究ノート</h2>"))

    def test_page_that_opens_with_deaths_has_nothing_before_the_middle(self):
        t = rw.add("aichi/index.html", page(h1="愛知県のクマ出没", h2s=["愛知県で、熊による死亡事故はあったか"] + [f"節{i}" for i in range(7)]))
        self.assertGreater(t.index('class="rk-ad"'), t.index("<h2>節2</h2>"))
        self.assertEqual(t.count('class="rk-ad"'), 2)

    def test_pages_without_ads_get_none(self):
        for rel in ("about/index.html", "privacy/index.html", "contact/index.html", "404.html", "search/index.html"):
            self.assertEqual(rw.add(rel, page()), page(), rel)
        noindex = page(head='<meta name="robots" content="noindex,follow">')
        self.assertEqual(rw.add("monthly/2026-04/index.html", noindex), noindex)

    def test_idempotent(self):
        once = rw.add("x/index.html", page())
        self.assertEqual(rw.add("x/index.html", once), once)

    def test_negative_cases_are_detected(self):
        ok = rw.add("x/index.html", page())
        self.assertTrue(widget_problems("x", ok + rw.block(True) * 4))
        self.assertTrue(widget_problems("x", ok.replace('<p class="rk-pr">PR</p>', "")))
        self.assertTrue(widget_problems("x", ok.replace('<p class="rk-pr">', '<a href="https://www.amazon.co.jp/">a</a><p class="rk-pr">')))
        self.assertTrue(widget_problems("x", ok.replace('class="rk-ad"', 'class="rk-ad" style="position:fixed;bottom:0"')))
        harm = rw.add("x/index.html", page(h1="死亡事故", h2s=["a"]))
        self.assertEqual(widget_problems("x", harm), [])
        self.assertTrue(widget_problems("x", harm.replace("<h2>a</h2>", rw.block(True) + "<h2>a</h2>")))   # a harm page with a widget before its body

    def test_no_product_data_in_the_snippet(self):
        self.assertNotIn("itemCode", rw.WIDGET_SCRIPT)
        self.assertIn('rakuten_size="300x250"', rw.WIDGET_SCRIPT)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class RealBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(raw_data(), {**CFG, "adsense_pub_id": "ca-pub-1234567890", "rakuten_affiliate_id": "aaa.bbb.ccc.ddd", "amazon_tracking_id": "amazonmacs-22"}, cls.out, release=True, links=LINKS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_pages(self):
        for rel in ("index.html", "ranking/sightings/index.html", "guide/prepare/index.html", "season/index.html"):
            t = self.read(rel)
            self.assertGreaterEqual(t.count('class="rk-ad"'), 1, rel)
            self.assertEqual(widget_problems(rel, t), [], rel)
        for rel in ("deaths/index.html", "ranking/deaths/index.html", "ranking/injuries/index.html", "trend/index.html"):
            self.assertEqual(self.read(rel).count('class="rk-ad"'), 1, rel)
        for rel in ("about/index.html", "privacy/index.html", "contact/index.html", "404.html"):
            self.assertNotIn('class="rk-ad"', self.read(rel), rel)

    def test_next_action_box(self):
        for rel in ("ranking/sightings/index.html", "season/index.html", "ranking/change/index.html"):
            t = self.read(rel)
            box = re.search(r'<aside class="pr-guide-box next-action">.*?</aside>', t, re.S).group(0)
            links = re.findall(r"<a href=\"([^\"]+)\"([^>]*)>", box)
            ext = [(h, a) for h, a in links if h.startswith("http")]
            self.assertGreaterEqual(len(ext), 4, rel)
            for h, a in ext:
                self.assertIn('rel="nofollow sponsored noopener"', a)
                self.assertIn('target="_blank"', a)
            self.assertIn("tag=amazonmacs-22", box)
            self.assertNotRegex(re.sub(r"<[^>]+>", "", box), r"https?://")        # no link text is a URL
        for rel in ("deaths/index.html", "ranking/deaths/index.html", "ranking/injuries/index.html", "trend/index.html", "emergency/index.html"):
            self.assertNotIn("next-action", self.read(rel), rel)
            self.assertNotIn("pr-guide-box", self.read(rel), rel)
