"""The survey boards of the data room, the charts as pictures to keep or send, the share row and the icons."""
import copy
import io
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, dataroom, ogimage
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError
from tests.test_yorokobu_dataroom import CFG, FIX, inflated

REAL = Path(build.HERE) / "content" / "surveys.json"


def board_content(tmp: Path) -> dict:
    """The fixture content plus a surveys.json made of two real boards (one moved to an occasion the fixture has) and the Mother's Day extra."""
    for f in FIX.iterdir():
        (tmp / f.name).write_bytes(f.read_bytes())
    real = json.loads(REAL.read_text(encoding="utf-8"))
    xmas = copy.deepcopy(next(b for b in real["boards"] if b["slug"] == "christmas"))
    xmas.update(slug="birthday-survey", occasion="birthday")
    feel = next(b for b in real["boards"] if b["slug"] == "gift-feelings")
    (tmp / "surveys.json").write_text(json.dumps({"boards": [xmas, feel], "mothers_day_extra": real["mothers_day_extra"]}, ensure_ascii=False), encoding="utf-8")
    return content.load(tmp)


class BoardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rows = (dataroom.MIN_ROWS, dataroom.MIN_PER_ROW)
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = 2, 8
        cdir = Path(cls.tmp.name) / "c"
        cdir.mkdir()
        cls.c = board_content(cdir)
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, inflated(), CFG, cls.out, release=True, today=date(2026, 10, 7))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = cls.rows
        build.RANKING_ON = False
        build.DATA_ON = False

    def read(self, rel: str) -> str:
        return (self.out / rel).read_text(encoding="utf-8")

    # ------------------------------------------------------------ the content file
    def test_the_real_surveys_file_loads_and_every_board_names_its_sources(self):
        c = content.load()
        boards = c["surveys"]["boards"]
        self.assertGreaterEqual(len(boards), 5)
        for b in boards:
            self.assertTrue(b["studies"] and b["cautions"] and b["takeaways"], b["slug"])
            for s in b["studies"]:
                self.assertTrue(s["url"].startswith("https://") and s["n"] > 0 and s["period"], s["id"])

    def test_a_sentence_with_a_number_that_is_not_in_the_data_is_refused(self):
        b = copy.deepcopy(json.loads(REAL.read_text(encoding="utf-8"))["boards"][0])
        content.check_board(b)                                                     # as written: fine
        bad = copy.deepcopy(b)
        bad["takeaways"][0] = bad["takeaways"][0].replace("17,643円", "18,643円")
        with self.assertRaises(BuildError):
            content.check_board(bad)
        bad = copy.deepcopy(b)
        bad["charts"][0]["finding"] = "子どもへ贈った人は、52%です。"
        with self.assertRaises(BuildError):
            content.check_board(bad)

    def test_a_chart_row_that_does_not_fit_its_unit_or_a_source_that_does_not_exist_is_refused(self):
        b = json.loads(REAL.read_text(encoding="utf-8"))["boards"][0]
        for edit in (lambda x: x["charts"][0]["rows"].__setitem__(0, ["子ども", 125]),
                     lambda x: x["charts"][0].__setitem__("study", "nobody"),
                     lambda x: x["studies"][0].__setitem__("url", "http://example.com/"),
                     lambda x: x["studies"][0].__setitem__("n", 0),
                     lambda x: x.__setitem__("cautions", [])):
            bad = copy.deepcopy(b)
            edit(bad)
            with self.assertRaises(BuildError):
                content.check_board(bad)

    # ------------------------------------------------------------ the pages
    def test_a_board_shows_the_numbers_the_sentences_the_sources_and_the_way_to_the_products(self):
        html = self.read("data/birthday-survey/index.html")
        for text in ("3秒でわかる", "17,643円", "恋人への平均予算", "わかったこと", "調べた調査", "株式会社アイディエーション", "見かたの注意", "この予算で、探す"):
            self.assertIn(text, html, text)
        self.assertIn("https://prtimes.jp/main/html/rd/p/000000031.000030222.html", html)           # the source link
        self.assertIn("880人", html)
        self.assertEqual(len(re.findall(r'<figure class="chart" id="birthday-survey--', html)), 3)  # three charts, each with its own anchor
        self.assertGreaterEqual(html.count('<li class="item"'), 2)                                  # products of the price range
        self.assertIn("楽天市場で探す", html)
        self.assertIn('class="pr-quiet"', html)                                                     # a page with affiliate links says so
        hub = self.read("data/index.html")
        self.assertIn("/data/birthday-survey/", hub)
        self.assertIn("/data/gift-feelings/", hub)
        self.assertIn("/data/birthday-survey/", self.read("sitemap.xml"))

    def test_a_board_for_no_occasion_has_no_shop_section(self):
        html = self.read("data/gift-feelings/index.html")
        self.assertNotIn("この予算で、探す", html)
        self.assertNotIn('<li class="item"', html)
        self.assertIn("35.4%", html)

    def test_a_board_of_an_occasion_the_site_does_not_have_is_left_out(self):
        self.assertFalse((self.out / "data/christmas").exists())                                    # (the fixture has no Christmas)

    def test_the_mothers_day_page_gets_the_other_surveys(self):
        html = self.read("data/mothers-day-budget/index.html")
        self.assertIn("ほかの調査では", html)
        self.assertIn("花キューピット", html)
        self.assertIn("エン・ジャパン", html)
        self.assertIn("71%", html)

    def test_the_board_pages_pass_the_site_check(self):
        problems = [p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "data/" in p]
        self.assertEqual(problems, [])

    # ------------------------------------------------------------ the charts as pictures
    @unittest.skipUnless(ogimage.available(), "no Pillow or no Japanese font")
    def test_every_chart_with_a_card_has_a_preview_image_and_a_tall_one_to_keep(self):
        from PIL import Image
        ids = re.findall(r'<figure class="chart" id="([^"]+)"', self.read("data/birthday-survey/index.html") + self.read("data/price-bands/index.html"))
        self.assertGreaterEqual(len(ids), 4)
        for cid in ids:
            with Image.open(self.out / "og" / "data" / f"{cid}.png") as wide, Image.open(self.out / "data" / "img" / f"{cid}.png") as tall:
                self.assertEqual(wide.size, (1200, 630), cid)
                self.assertEqual(tall.size, (1080, 1350), cid)
        html = self.read("data/birthday-survey/index.html")
        first = re.search(r'<figure class="chart" id="([^"]+)"', html).group(1)
        self.assertIn(f"/og/data/{first}.png", html)                                                # the page's share preview is its first chart
        self.assertIn(f'href="/data/img/{first}.png" download=', html)                              # keep it
        self.assertIn("画像を送る", html)                                                           # (shown by the script where the phone can share a file)
        self.assertIn(f"https://yorokobu-present.com/data/birthday-survey/#{first}", html)         # sent with the link to the very chart

    @unittest.skipUnless(ogimage.available(), "no Pillow or no Japanese font")
    def test_the_chart_card_draws_bars_and_ranges_and_is_deterministic(self):
        from PIL import Image
        rows = (("A", 10, "10点"), ("B", 40, "40点"))
        a = ogimage.chart_card(title="テスト", finding="いちばん多いのはBです。", rows=rows, source="出典: テスト", site="example.com")
        b = ogimage.chart_card(title="テスト", finding="いちばん多いのはBです。", rows=rows, source="出典: テスト", site="example.com")
        self.assertEqual(a, b)
        im = Image.open(io.BytesIO(a)).convert("RGB")
        self.assertIn(ogimage.BAR["s1"], {im.getpixel((x, y)) for x in range(300, 900, 7) for y in range(200, 560, 5)})   # a bar is drawn
        r = ogimage.chart_card(title="価格", finding="x", rows=(("母の日", 1000, 2500, 5000, "2,500円"),), source="s", site="e.com", ranges=True, tall=True)
        self.assertEqual(Image.open(io.BytesIO(r)).size, (1080, 1350))

    # ------------------------------------------------------------ sending a page
    def test_the_share_row_has_line_mail_x_and_copy_and_the_mail_carries_the_page_address(self):
        row = build.share_bar(CFG, "/gift/x/", "テストの候補です。", hint=True)
        for text in ("LINEで送る", "メールで送る", "Xで共有", "共有する", "リンクをコピー", "自分のトーク"):
            self.assertIn(text, row)
        self.assertIn("mailto:?subject=", row)
        self.assertIn("https%3A%2F%2Fyorokobu-present.com%2Fgift%2Fx%2F", row)                       # the page, never an affiliate link
        self.assertNotIn("自分のトーク", build.share_bar(CFG, "/gift/x/", "t"))                      # the hint only where asked

    def test_the_script_can_draw_the_candidate_list_as_a_picture_and_mail_it(self):
        js = (build.HERE / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("fav-img", js)
        self.assertIn("canvas", js)
        self.assertIn("mailto:?subject=", js)
        self.assertIn("canShare", js)                                                               # the phone's share sheet takes the file; otherwise it is downloaded


class IconsTest(unittest.TestCase):
    def test_the_icons_are_the_header_logo_in_the_site_colour(self):
        from PIL import Image
        assets = build.HERE / "assets"
        with Image.open(assets / "favicon.ico") as ico:
            self.assertEqual(ico.info["sizes"], {(16, 16), (32, 32), (48, 48)})
        for name, size in (("favicon-32.png", 32), ("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
            with Image.open(assets / name) as raw:
                im = raw.convert("RGBA")
            self.assertEqual(im.size, (size, size), name)
            px = {im.getpixel((x, y))[:3] for x in range(0, size, max(1, size // 24)) for y in range(0, size, max(1, size // 24)) if im.getpixel((x, y))[3] == 255}
            self.assertIn((232, 80, 63), px, name)                                                  # the coral tile
            self.assertIn((255, 255, 255), px, name)                                                # the white box
        with Image.open(assets / "icon-512.png") as a, Image.open(assets / "apple-touch-icon.png") as b:
            self.assertEqual(a.convert("RGBA").getpixel((0, 0))[3], 0)                              # rounded corners
            self.assertEqual(b.convert("RGBA").getpixel((0, 0))[3], 255)                            # iOS rounds the touch icon itself
        self.assertIn('fill="#e8503f"', build.LOGO_MARK)                                            # the logo and the icons use the same colour


if __name__ == "__main__":
    unittest.main()
