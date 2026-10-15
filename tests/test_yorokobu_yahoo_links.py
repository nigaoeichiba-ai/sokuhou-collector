"""Yahoo!ショッピングへのバリューコマースのリンク: 作り方、使う場所、広告の表示。"""
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from sites.yorokobu import build, compare_fetch, content
from tests.test_yorokobu_compare import CFG, FIX, item
from tests.yorokobu_data import with_musts

VC = {"sid": "3784606", "pid": "892726918"}
CFG_Y = {**CFG, "yahoo_vc": VC}


class UrlTest(unittest.TestCase):
    def test_the_link_goes_through_valuecommerce_with_the_site_and_ad_ids_and_carries_the_yahoo_search_page_encoded(self):
        u = build.yahoo_url(CFG_Y, "お歳暮 ギフト")
        p = urlparse(u)
        self.assertEqual((p.scheme, p.netloc, p.path), ("https", "ck.jp.ap.valuecommerce.com", "/servlet/referral"))
        q = parse_qs(p.query)
        self.assertEqual((q["sid"], q["pid"]), (["3784606"], ["892726918"]))
        target = q["vc_url"][0]
        self.assertTrue(target.startswith("https://shopping.yahoo.co.jp/search?p="))        # a page the programme allows as a link target
        self.assertEqual(unquote(urlparse(target).query), "p=お歳暮 ギフト")
        self.assertNotIn(" ", u)

    def test_without_the_ids_there_is_no_link_and_no_button(self):
        self.assertEqual(build.yahoo_url(CFG, "お歳暮"), "")
        self.assertEqual(build.yahoo_btn(CFG, "お歳暮", "x"), "")

    def test_the_button_is_marked_as_an_advertisement_link(self):
        b = build.yahoo_btn(CFG_Y, "お歳暮", "Yahoo!ショッピングで探す")
        self.assertIn('rel="sponsored nofollow noopener"', b)
        self.assertIn('target="_blank"', b)
        self.assertIn("&amp;vc_url=", b)

    def test_each_link_carries_the_programmes_impression_counter(self):
        b = build.yahoo_btn(CFG_Y, "お歳暮", "x")
        self.assertIn('<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3784606&amp;pid=892726918" width="1" height="1" alt=', b)
        self.assertEqual(b.count("<a "), 1)

    def test_the_real_config_has_the_ids(self):
        cfg = json.loads((Path(build.__file__).parent / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["yahoo_vc"], VC)


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        gs = {g["slug"]: g for g in compare_fetch.groups()}
        raw = {"version": 1, "fetched_at": "2026-10-14T05:40:00+09:00",
               "groups": {slug: [item(i, price=1000 + 150 * i, reviews=20 + 7 * i, name=f"{gs[slug]['words'][0]} ギフト {i}") for i in range(1, 16)] for slug in ("catalog-gift", "tumbler")}}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, {**CFG_Y, "shaddy_a8mat": "4BEGD8+UYL0A+4DMG+5YJRM"}, cls.root, release=True, today=date(2026, 10, 15), compare_data=raw)
        cls.bare = tempfile.TemporaryDirectory()
        build.render_site(cls.c, items, CFG, Path(cls.bare.name), release=True, today=date(2026, 10, 15), compare_data=raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.bare.cleanup()

    def read(self, rel, root=None):
        return (Path(root or self.root.as_posix()) / rel).read_text(encoding="utf-8")

    def test_the_sheets_and_the_comparison_pages_offer_yahoo_and_say_that_no_yahoo_price_is_in_the_table(self):
        for rel in ("oseibo/index.html", "nenga/index.html", "oiwai/seijin/index.html", "oiwai/kekkon/index.html"):
            self.assertRegex(self.read(rel), r'href="https://ck\.jp\.ap\.valuecommerce\.com/servlet/referral\?sid=3784606&amp;pid=892726918&amp;vc_url=[^"]+" rel="sponsored nofollow noopener"', rel)
        t = self.read("compare/tumbler/index.html")
        self.assertIn("この表にYahoo!ショッピングの価格は入っていません", t)
        self.assertIn("valuecommerce.com", t)
        self.assertIn("valuecommerce.com", self.read("compare/index.html"))

    def test_the_notice_at_the_foot_names_each_programme_the_page_really_links_to(self):
        foot = re.search(r'<aside class="pr-foot">.*?</aside>', self.read("compare/catalog-gift/index.html"), re.S).group(0)
        self.assertIn("バリューコマース(Yahoo!ショッピング)", foot)
        self.assertIn("A8.net", foot)
        self.assertIn("楽天アフィリエイト", foot)
        plain = re.search(r'<aside class="pr-foot">.*?</aside>', self.read("compare/tumbler/index.html"), re.S).group(0)
        self.assertNotIn("A8.net", plain)                                              # the tumbler page has no gift-mall link
        self.assertIn("バリューコマース(Yahoo!ショッピング)", plain)

    def test_a_page_without_a_yahoo_link_does_not_name_the_programme(self):
        for rel in ("oseibo/index.html", "compare/tumbler/index.html"):
            html = self.read(rel, self.bare.name)
            self.assertNotIn("valuecommerce", html, rel)
            self.assertNotIn("バリューコマース", html, rel)

    def test_no_yahoo_image_logo_or_price_is_shown(self):
        for rel in ("oseibo/index.html", "compare/tumbler/index.html"):
            html = self.read(rel)
            self.assertNotIn("s.yimg.jp", html, rel)
            self.assertNotIn("shopping.c.yimg.jp", html, rel)
            self.assertNotRegex(re.sub(r"<[^>]+>", " ", html), r"Yahoo![^。]{0,20}[0-9,]{3,}円")


if __name__ == "__main__":
    unittest.main()
