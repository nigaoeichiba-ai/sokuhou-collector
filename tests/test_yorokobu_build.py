import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from sokuhou.sitekit import BuildError

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}
TODAY = date(2026, 5, 3)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.files = build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_page_set(self):
        for rel in ("index.html", "occasion/index.html", "for/index.html", "occasion/birthday/index.html", "for/mother/index.html",
                    "gift/birthday-boyfriend/index.html", "gift/birthday-mother/index.html", "gift/mothers-day-mother/index.html",
                    "about/index.html", "privacy/index.html", "contact/index.html", "404.html", "sitemap.xml", "robots.txt", ".htaccess"):
            self.assertIn(rel, self.files)

    def test_products_link_through_the_affiliate_id_and_are_marked(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=", html)
        self.assertIn('rel="sponsored nofollow noopener"', html)
        self.assertIn('<span class="pr-note">PR</span>楽天市場で見る', html)
        self.assertIn("このページには、広告", html)
        self.assertIn("amazon.co.jp/s?k=", html)
        self.assertIn("Amazonのアソシエイトとして", html)
        self.assertIn("3,000円以内のおすすめ", html)
        self.assertIn("2026年10月7日に取得した情報", html)

    def test_products_keep_the_order_chosen_by_the_fetch(self):
        html = self.read("gift/birthday-boyfriend/index.html")
        self.assertLess(html.index("テスト商品a1"), html.index("テスト商品a2"))  # the fetch ranks; the build does not reorder

    def test_own_shop_items_link_directly_with_a_disclosure_and_only_where_noted(self):
        mother = self.read("gift/birthday-mother/index.html")
        self.assertIn("https://item.rakuten.co.jp/2gaoe/p1/", mother)
        self.assertNotIn("hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=https%3A%2F%2Fitem.rakuten.co.jp%2F2gaoe", mother)
        self.assertIn("当サイト運営者のショップの商品です", mother)
        self.assertNotIn("当サイト運営者のショップの商品です", self.read("gift/birthday-boyfriend/index.html"))
        self.assertIn("思い出を形に残す", self.read("occasion/birthday/index.html"))
        self.assertNotIn("思い出を形に残す", self.read("occasion/mothers-day/index.html"))

    def test_empty_tiers_are_skipped(self):
        html = self.read("gift/birthday-mother/index.html")
        self.assertIn('id="t-under3000"', html)
        self.assertNotIn('id="t-3000-5000"', html)

    def test_season_block_follows_the_build_date(self):
        self.assertIn("母の日", self.read("index.html").split('class="tiles wide">')[1].split("</ul>")[0])
        out = Path(self.tmp.name) / "winter"
        build.render_site(self.c, self.items, CFG, out, release=True, today=date(2026, 8, 1))
        block = (out / "index.html").read_text(encoding="utf-8").split('class="tiles wide">')[1].split("</ul>")[0]
        self.assertNotIn("母の日", block)  # fixtures have no occasion in season in August: falls back to the evergreen ones
        self.assertIn("誕生日", block)

    def test_every_internal_link_and_asset_resolves(self):
        bad = []
        for rel in self.files:
            if not rel.endswith(".html"):
                continue
            html = self.read(rel)
            for href in re.findall(r'(?:href|src)="(/[^"#?]*)', html):
                target = href.lstrip("/")
                if href.endswith("/"):
                    target += "index.html"
                if target and target not in self.files and not (self.out / target).exists():
                    bad.append((rel, href))
        self.assertEqual(bad, [])

    def test_names_are_shortened_and_escaped(self):
        self.assertEqual(build.short("x" * 100, 10), "x" * 9 + "…")
        self.assertEqual(build.short("  a   b  "), "a b")

    def test_site_files(self):
        self.assertIn("Sitemap: https://yorokobu-present.com/sitemap.xml", self.read("robots.txt"))
        self.assertIn("楽天ウェブサービス", self.read("about/index.html"))
        self.assertIn("Supported by Rakuten Developers", self.read("index.html"))
        self.assertIn("運営者は、楽天市場で、似顔絵のショップも運営", self.read("about/index.html"))


class ReleaseGateTest(unittest.TestCase):
    def test_release_needs_fetched_products_and_operator_info(self):
        c = content.load(FIX)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BuildError):
                build.render_site(c, None, CFG, Path(tmp) / "a", release=True, today=TODAY)
            with self.assertRaises(BuildError):
                build.render_site(c, {"pairs": {"x": {}}}, {**CFG, "operator_name": ""}, Path(tmp) / "b", release=True, today=TODAY)
            files = build.render_site(c, None, CFG, Path(tmp) / "c", release=False, today=TODAY)  # a preview build works without products
            self.assertIn("index.html", files)


class ContentValidationTest(unittest.TestCase):
    def test_unknown_slug_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for f in FIX.glob("*.json"):
                (tmp / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            pairs = json.loads((tmp / "pairs.json").read_text(encoding="utf-8"))
            pairs["pairs"][0]["recipient"] = "nobody"
            (tmp / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(tmp)


if __name__ == "__main__":
    unittest.main()
