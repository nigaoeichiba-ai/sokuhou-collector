"""みんなのイラスト: the data computed from the pictures, the hubs' summaries, the about page's editorial section, and no AdSense tag on pages of links and forms.

Why (2026-10-19): another site of ours was refused by AdSense as "low value content"; 3,154 of this site's pages are a picture and a short text.
The numbers on a picture page come from the file; the tests make sure they are measured (not stock text) and that no two pictures read the same.
"""
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from sites.minna import build, facts, tips
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
        for h2 in ("編集方針", "誤りを見つけたら", "更新の履歴", "免責事項"):
            self.assertIn(f"<h2>{h2}</h2>", about)
        self.assertLess(about.index("<h2>編集方針</h2>"), about.index("<h2>免責事項</h2>"))
        # the owner does not want the site to say that its text, pages or pictures were made with AI or automatically (2026-10-19, 2026-10-20)
        for word in ("Claude", "Anthropic", "自動", "プログラムで", "AI(", "支援を受け"):
            self.assertNotIn(word, about, word)
        self.assertIn("キャラクターは当サイトのオリジナルです。", about)
        self.assertRegex(about, r"<li>20\d\d-\d\d-\d\d: ")
        for rel in ("privacy/index.html", "contact/index.html"):
            self.assertNotIn("<h2>編集方針</h2>", self.read(rel))                 # only the about page is extended
        self.assertEqual(about.count(SHARED_CFG["operator_name"]), 1)             # the company name stays on this page only, once


def f(colors, fill=60, bg_low=None):
    return {"w": 400, "h": 300, "fill": fill, "colors": colors, "bg_low": bg_low or {"白": 0, "黄": 0, "桃": 0, "空": 0, "黒": 0}, "dark": 0}


def item(i, series, w=400, h=300):
    return {"id": i, "series": series, "w": w, "h": h}


class Tips(unittest.TestCase):
    def test_the_background_sentence_follows_the_measured_share(self):
        none = tips.tip_lines(item("a", "s"), f([["赤", 100]]))[0]
        black = tips.tip_lines(item("a", "s"), f([["赤", 100]], bg_low={"白": 0, "黄": 0, "桃": 0, "空": 0, "黒": 80}))[0]
        light = tips.tip_lines(item("a", "s"), f([["白", 100]], bg_low={"白": 90, "黄": 40, "桃": 5, "空": 5, "黒": 0}))[0]
        every = tips.tip_lines(item("a", "s"), f([["灰色", 100]], bg_low={"白": 50, "黄": 50, "桃": 50, "空": 50, "黒": 50}))[0]
        self.assertIn("どの背景でも見分けられる", none)
        self.assertIn("黒の背景に置くと輪郭が沈みます", black)
        self.assertIn("輪郭が白・黄の背景に近い色で、沈みます", light)
        self.assertIn("桃・空・黒の上に置く", light)                           # the backgrounds measured as safe are the ones it recommends
        self.assertIn("輪郭が背景に近い色になりやすい", every)
        self.assertEqual(len({none, black, light, every}), 4)

    def test_print_size_numbers_and_the_postcard_clause_match_the_pixels(self):
        small = tips.tip_lines(item("a", "s", w=400, h=480), f([["赤", 100]]))[1]          # 400 px = 68 mm at 150 dpi: less than a postcard width
        big = tips.tip_lines(item("a", "s", w=640, h=442), f([["赤", 100]]))[1]            # 640 px = 108 mm at 150 dpi
        self.assertIn("300dpiで約34×41mm、150dpiで約68×81mm", small)
        self.assertIn("の拡大になり", small)
        self.assertIn("300dpiで約54×37mm、150dpiで約108×75mm", big)
        self.assertIn("はがきの幅(100mm)を超える", big)
        self.assertNotIn("の拡大になり", big)

    def test_margin_and_shape_sentences(self):
        wide = tips.tip_lines(item("a", "s", w=400, h=300), f([["赤", 100]], fill=30))
        tall = tips.tip_lines(item("a", "s", w=300, h=400), f([["赤", 100]], fill=90))
        square = tips.tip_lines(item("a", "s", w=400, h=400), f([["赤", 100]], fill=60))
        self.assertTrue(any("余白が広め" in x and "30%" in x for x in wide))
        self.assertTrue(any("余白がほとんどありません" in x and "90%" in x for x in tall))
        self.assertFalse(any("余白" in x for x in square))                          # a middling margin says nothing
        self.assertIn("横長なので", wide[-1])
        self.assertIn("縦長なので", tall[-1])
        self.assertIn("ほぼ正方形なので", square[-1])

    def test_no_sentence_says_how_the_picture_was_made(self):
        text = "".join(tips.tip_lines(item("a", "s"), f([["赤", 100]])))
        self.assertFalse(NoOriginClaims.CLAIM.search(text))


class Similar(unittest.TestCase):
    def test_nearest_first_one_per_other_set_never_itself_or_its_own_set(self):
        items = [item("me", "A"), item("a2", "A"), item("b1", "B"), item("b2", "B"), item("c1", "C"), item("d1", "D"), item("e1", "E"), item("g1", "G"), item("h1", "H"), item("far", "F")]
        facts_by = {"me": f([["赤", 70], ["白", 30]]), "a2": f([["赤", 70], ["白", 30]]), "b1": f([["赤", 60], ["白", 40]]), "b2": f([["赤", 70], ["白", 30]]),
                    "c1": f([["赤", 50], ["白", 50]]), "d1": f([["赤", 100]]), "e1": f([["赤", 30], ["青", 70]]), "g1": f([["赤", 90]]), "h1": f([["白", 90]]),
                    "far": f([["青", 100]])}
        got = tips.similar_map(items, lambda i: facts_by[i["id"]])["me"]
        ids = [c for c, _d in got]
        self.assertNotIn("me", ids)
        self.assertNotIn("a2", ids)                                                  # the same set
        self.assertEqual(len({i["series"] for i in items if i["id"] in ids}), len(ids))        # one picture per set
        self.assertNotIn("b1", ids)                                                  # b2 has exactly my colours and is nearer: one picture per set
        self.assertEqual(ids[0], "b2")
        dist = [d for _c, d in got]
        self.assertEqual(dist, sorted(dist))
        self.assertNotIn("far", ids)                                                 # no colour in common: not near

    def test_a_different_shape_is_farther(self):
        a = f([["赤", 100]])
        self.assertLess(tips.distance(a, a, "横長", "横長"), tips.distance(a, a, "横長", "縦長"))


class InThePicturePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.files = shared_site()
        cls.pages = [f for f in cls.files if re.fullmatch(r"illust/[^/]+/index\.html", f)]

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_every_picture_page_has_tips_and_most_have_similar_pictures_of_other_sets(self):
        with_similar = 0
        for rel in self.pages[::7]:
            h = self.read(rel)
            self.assertIn("使うときのコツ", h, rel)
            m = re.search(r'色と形が近いイラスト</span></h2>(.*?)</section>', h, re.S)
            if m:
                with_similar += 1
                own = rel.split("/")[1]
                links = re.findall(r'href="/illust/([^/"]+)/"', m.group(1))
                self.assertGreaterEqual(len(links), 3, rel)
                self.assertNotIn(own, links, rel)                                    # never itself
        self.assertGreater(with_similar / len(self.pages[::7]), 0.9)

    def test_the_tips_and_the_similar_lists_differ_from_picture_to_picture(self):
        tip_texts, sims = [], []
        for rel in self.pages[::5]:
            h = self.read(rel)
            tip_texts.append(re.search(r'使うときのコツ</span></h2>(.*?)</ul>', h, re.S).group(1))
            m = re.search(r'色と形が近いイラスト</span></h2>(.*?)</section>', h, re.S)
            sims.append(tuple(re.findall(r'href="/illust/([^/"]+)/"', m.group(1))) if m else ())
        self.assertGreaterEqual(len(set(tip_texts)) / len(tip_texts), 0.9)
        self.assertGreaterEqual(len(set(sims)) / len(sims), 0.9)

    def test_the_similar_pictures_are_shown_nearest_first(self):
        by = {i["id"]: i for i in build.load_data()[0]}
        rel = next(p for p in self.pages if "eto-sheep-kawaii-bow" in p)
        m = re.search(r'色と形が近いイラスト</span></h2>(.*?)</section>', self.read(rel), re.S)
        shown = re.findall(r'href="/illust/([^/"]+)/"', m.group(1))
        expect = [c for c, _d in build.SITE["similar"]["eto-sheep-kawaii-bow"]]
        self.assertEqual(shown, expect)
        dist = [d for _c, d in build.SITE["similar"]["eto-sheep-kawaii-bow"]]
        self.assertEqual(dist, sorted(dist))
        self.assertTrue(all(by[c]["series"] != by["eto-sheep-kawaii-bow"]["series"] for c in shown))


class PictureDescriptions(unittest.TestCase):
    def test_no_two_picture_pages_share_a_meta_description(self):
        """seo-sweep 2026-10-20: two pictures of one set with the same title (a wave in two outfits) shared a description; the place in the set now tells them apart."""
        out, files = shared_site()
        seen: dict[str, str] = {}
        dup = []
        for rel in files:
            if not re.fullmatch(r"illust/[^/]+/index\.html", rel):
                continue
            m = re.search(r'<meta name="description" content="([^"]*)"', (out / rel).read_text(encoding="utf-8"))
            self.assertTrue(m, rel)
            self.assertLessEqual(len(m.group(1)), 160, rel)
            if m.group(1) in seen:
                dup.append((seen[m.group(1)], rel))
            seen[m.group(1)] = rel
        self.assertEqual(dup, [])
        self.assertGreater(len(seen), 2000)

    def test_the_description_names_the_place_in_the_set(self):
        items, series = build.load_data()
        s = next(x for x in series if not x["legacy"] and build.series_use(x) and len(x["items"]) >= 3)
        a, b = s["items"][0], s["items"][2]
        da = build.illust_description(a, s, "かわいい", 0)
        db = build.illust_description(b, s, "かわいい", 2)
        self.assertIn(f"{len(s['items'])}点のうち1点目です", da)
        self.assertIn(f"{len(s['items'])}点のうち3点目です", db)
        self.assertNotEqual(da, db)
        legacy = next(x for x in series if x["legacy"])
        self.assertIn("点のうち2点目です", build.illust_description(legacy["items"][1], legacy, "かわいい", 1))


class NoOriginClaims(unittest.TestCase):
    """オーナー決定 2026-10-20: the site does not say how the pictures are made (nor that its text or pages were made by a program or an AI).
    The card maker's own words about the AI built into Chrome describe a feature, and a set about people who use AI at work is a subject; neither is a claim about the site."""
    CLAIM = re.compile(r"生成AI|AI生成|AIが制作|AIで制作|AI制作|AIで生成|AIで作成|AIによる(?:生成|制作)|AIの支援|AIを使って(?:作|制作)|人工知能|機械が作|自動で作|自動的に作|Claude|Anthropic|ChatGPT")

    def test_no_page_file_feed_or_data_says_how_the_pictures_are_made(self):
        out, files = shared_site()
        bad = []
        for rel in files:
            if not rel.endswith((".html", ".xml", ".json", ".txt", ".webmanifest", ".php")):
                continue
            text = (out / rel).read_text(encoding="utf-8", errors="ignore")
            m = self.CLAIM.search(text)
            if m:
                bad.append((rel, text[max(0, m.start() - 20):m.end() + 20]))
        self.assertEqual(bad, [])

    def test_the_check_finds_the_old_wording(self):
        for old in ("イラストは生成AIが制作しています。", "素材は透明PNGで、AI生成後に選定・整備した", "AIの支援を受けて作成", "AI(Anthropic の Claude)"):
            self.assertTrue(self.CLAIM.search(old), old)
        for fine in ("Chromeに内蔵のAIで、この端末の中で作ります(無料)。", "AI・DXを使う仕事の人物素材", "AIに質問する(AI・DXを使う仕事の人)"):
            self.assertFalse(self.CLAIM.search(fine), fine)

    def test_the_licence_page_keeps_the_conditions_and_states_no_owner_of_the_rights(self):
        out, _files = shared_site()
        html = (out / "license/index.html").read_text(encoding="utf-8")
        self.assertIn("<h2><span class=\"scribble\">権利について</span></h2>", html)
        self.assertIn("イラストの権利が誰に帰属するかについては、断定しません", html)


class NoAdsOnLinkPages(unittest.TestCase):
    TAG = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1" crossorigin="anonymous"></script>\n'

    def test_hubs_forms_and_the_404_lose_the_tag_and_pages_with_content_keep_it(self):
        html = f"<head>\n{self.TAG}</head><body>x</body>"
        gone = ["index.html", "illust/index.html", "illust/page/2/index.html", "genre/food/index.html", "genre/food/pixel/index.html", "touch/kawaii/index.html",
                "tag/abc/index.html", "search/index.html", "request/index.html", "special/index.html", "guide/index.html", "tool/index.html", "use/index.html",
                "contact/index.html", "contact/thanks.html", "404.html", "month/index.html", "pose/index.html"]
        kept = ["illust/some-picture/index.html", "series/dog-pose/index.html", "guide/nurie-insatsu/index.html", "special/nenga-2027/index.html", "about/index.html",
                "privacy/index.html", "tool/nenga/index.html", "use/flyer/index.html"]
        full = f"<head>\n{self.TAG}</head><body><main><p>{'あ' * build.ADS_MIN_PROSE}</p></main></body>"
        pages = {rel: html for rel in gone}
        pages.update({rel: full for rel in kept})
        pages["files/x.png"] = b"\x89PNG"
        build.drop_ads(pages)
        for rel in gone:
            self.assertNotIn("adsbygoogle", pages[rel], rel)
        for rel in kept:
            self.assertIn("adsbygoogle", pages[rel], rel)
        self.assertEqual(pages["files/x.png"], b"\x89PNG")

    def test_a_page_with_few_sentences_loses_the_tag_and_data_boxes_do_not_count_as_sentences(self):
        def page(inner: str) -> str:
            return f"<head>\n{self.TAG}</head><body><main>{inner}</main></body>"
        short = page(f"<p>{'あ' * (build.ADS_MIN_PROSE - 1)}</p>")
        data = page(f"<p>あ</p><table><tr><td><p>{'い' * 5000}</p></td></tr></table><dl><dt>x</dt><dd><p>{'う' * 5000}</p></dd></dl><pre><p>{'え' * 5000}</p></pre>")
        enough = page(f"<p>{'あ' * 300}</p><p>{'い' * 300}</p>")
        pages = {"illust/a/index.html": short, "series/b/index.html": data, "guide/c/index.html": enough}
        build.drop_ads(pages)
        self.assertNotIn("adsbygoogle", pages["illust/a/index.html"])
        self.assertNotIn("adsbygoogle", pages["series/b/index.html"])
        self.assertIn("adsbygoogle", pages["guide/c/index.html"])

    def test_the_page_path_of_a_file_name(self):
        self.assertEqual(build.page_path("index.html"), "/")
        self.assertEqual(build.page_path("genre/food/index.html"), "/genre/food/")
        self.assertEqual(build.page_path("contact/thanks.html"), "/contact/thanks.html")
        self.assertEqual(build.page_path("404.html"), "/404.html")


if __name__ == "__main__":
    unittest.main()
