"""みんなのイラスト: the data computed from the pictures, the hubs' summaries, the about page's editorial section, and no AdSense tag on pages of links and forms.

Why (2026-10-19): another site of ours was refused by AdSense as "low value content"; 3,154 of this site's pages are a picture and a short text.
The numbers on a picture page come from the file; the tests make sure they are measured (not stock text) and that no two pictures read the same.
"""
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from sites.minna import build, facts
from tests.test_minna_sitecache import SHARED_CFG, shared_site


def make_png(draw_fn, size=(200, 160)) -> Path:
    d = tempfile.mkdtemp()
    p = Path(d) / "x.webp"
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im))
    im.save(p, format="WEBP", lossless=True)
    return p


class Measured(unittest.TestCase):
    def test_a_black_outline_vanishes_only_on_the_black_background(self):
        p = make_png(lambda d: (d.ellipse((30, 20, 170, 140), fill=(255, 201, 60, 255), outline=(10, 10, 10, 255), width=6)))
        f = facts.compute(p)
        self.assertGreaterEqual(f["bg_low"]["黒"], 80)                 # a black line on a near-black ground
        for name in ("白", "黄", "桃", "空"):
            self.assertLessEqual(f["bg_low"][name], 5, name)
        self.assertIn("黒の背景では、輪郭の", facts.bg_sentence(f["bg_low"]))
        self.assertIn("白・黄・桃・空の背景ならはっきり見えます", facts.bg_sentence(f["bg_low"]))
        self.assertEqual(facts.bg_sentence({"白": 40, "黄": 36, "桃": 38, "空": 41, "黒": 0}),
                         "黒の背景ならはっきり見えます。白・黄・桃・空の背景では、輪郭の36〜41%ほどが背景に近い色で、縁がぼやけます。")     # backgrounds of a similar share are said once

    def test_a_pale_outline_blurs_on_the_light_backgrounds_instead(self):
        p = make_png(lambda d: d.ellipse((30, 20, 170, 140), fill=(240, 240, 250, 255), outline=(250, 250, 250, 255), width=6))
        f = facts.compute(p)
        self.assertGreaterEqual(f["bg_low"]["白"], 80)
        self.assertLessEqual(f["bg_low"]["黒"], 5)

    def test_fill_and_colours_follow_the_picture(self):
        full = facts.compute(make_png(lambda d: d.rectangle((0, 0, 199, 159), fill=(220, 40, 40, 255))))
        small = facts.compute(make_png(lambda d: d.rectangle((80, 60, 119, 99), fill=(220, 40, 40, 255))))
        self.assertGreaterEqual(full["fill"], 95)
        self.assertLessEqual(small["fill"], 8)
        self.assertEqual(full["colors"][0][0], "赤")
        green = facts.compute(make_png(lambda d: d.rectangle((0, 0, 199, 159), fill=(40, 160, 70, 255))))
        self.assertEqual(green["colors"][0][0], "緑")

    def test_shape_and_print_size(self):
        self.assertEqual(facts.shape(400, 300), "横長")
        self.assertEqual(facts.shape(300, 400), "縦長")
        self.assertEqual(facts.shape(400, 400), "ほぼ正方形")
        self.assertAlmostEqual(facts.mm(300, 300), 25.4, places=1)


class InThePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def block(self, rel):
        m = re.search(r'<h2><span class="scribble">このイラストのデータ</span></h2>(<dl class="facts">.*?</dl>)', self.read(rel), re.S)
        self.assertTrue(m, rel)
        return m.group(1)

    def test_every_picture_page_has_its_own_data_block(self):
        pages = [f for f in self.files if re.fullmatch(r"illust/[^/]+/index\.html", f)]
        self.assertGreater(len(pages), 2000)
        sample = pages[::17]
        blocks = [self.block(p) for p in sample]
        for b in blocks:
            for label in ("大きさ", "印刷の目安", "ファイル", "主な色", "絵の大きさ", "背景との相性"):
                self.assertIn(f"<dt>{label}</dt>", b)
            self.assertNotIn("<dd></dd>", b)
        self.assertGreaterEqual(len(set(blocks)) / len(blocks), 0.97)       # measured from each file: almost no two pages read alike

    def test_set_and_hub_pages_are_summed_up_from_the_same_numbers(self):
        s = self.read("series/dog-pose/index.html")
        self.assertIn("このセットのデータ", s)
        for label in ("点数と形", "大きさ", "よく出る色", "まとめて保存", "タッチ", "追加した日"):
            self.assertIn(f"<dt>{label}</dt>", s)
        for rel in ("genre/animals/index.html", "touch/kawaii/index.html", "illust/index.html"):
            h = self.read(rel)
            self.assertIn("この一覧のデータ", h, rel)
            for label in ("点数", "内訳", "形", "よく出る色", "最新の追加"):
                self.assertIn(f"<dt>{label}</dt>", h, rel)
        tag_pages = [f for f in self.files if f.startswith("tag/") and f.endswith("index.html") and "/page/" not in f]
        self.assertTrue(tag_pages)
        self.assertIn("この一覧のデータ", self.read(tag_pages[0]))

    def test_the_about_page_says_how_the_site_is_edited_made_corrected_and_changed(self):
        about = self.read("about/index.html")
        for h2 in ("編集方針", "このサイトの作り方", "誤りを見つけたら", "更新の履歴", "免責事項"):
            self.assertIn(f"<h2>{h2}</h2>", about)
        self.assertLess(about.index("<h2>編集方針</h2>"), about.index("<h2>免責事項</h2>"))
        self.assertIn("AI(Anthropic の Claude)の支援", about)
        self.assertRegex(about, r"<li>20\d\d-\d\d-\d\d: ")
        for rel in ("privacy/index.html", "contact/index.html"):
            self.assertNotIn("<h2>編集方針</h2>", self.read(rel))                 # only the about page is extended
        self.assertEqual(about.count(SHARED_CFG["operator_name"]), 1)             # the company name stays on this page only, once


class NoAdsOnLinkPages(unittest.TestCase):
    TAG = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1" crossorigin="anonymous"></script>\n'

    def test_hubs_forms_and_the_404_lose_the_tag_and_pages_with_content_keep_it(self):
        html = f"<head>\n{self.TAG}</head><body>x</body>"
        gone = ["index.html", "illust/index.html", "illust/page/2/index.html", "genre/food/index.html", "genre/food/pixel/index.html", "touch/kawaii/index.html",
                "tag/abc/index.html", "search/index.html", "request/index.html", "special/index.html", "guide/index.html", "tool/index.html", "use/index.html",
                "contact/index.html", "contact/thanks.html", "404.html", "month/index.html", "pose/index.html"]
        kept = ["illust/some-picture/index.html", "series/dog-pose/index.html", "guide/nurie-insatsu/index.html", "special/nenga-2027/index.html", "about/index.html",
                "privacy/index.html", "tool/nenga/index.html", "use/flyer/index.html"]
        pages = {rel: html for rel in gone + kept}
        pages["files/x.png"] = b"\x89PNG"
        build.drop_ads(pages)
        for rel in gone:
            self.assertNotIn("adsbygoogle", pages[rel], rel)
        for rel in kept:
            self.assertIn("adsbygoogle", pages[rel], rel)
        self.assertEqual(pages["files/x.png"], b"\x89PNG")

    def test_the_page_path_of_a_file_name(self):
        self.assertEqual(build.page_path("index.html"), "/")
        self.assertEqual(build.page_path("genre/food/index.html"), "/genre/food/")
        self.assertEqual(build.page_path("contact/thanks.html"), "/contact/thanks.html")
        self.assertEqual(build.page_path("404.html"), "/404.html")


if __name__ == "__main__":
    unittest.main()
