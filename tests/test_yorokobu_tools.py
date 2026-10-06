import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content as ct, tools

CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444", "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


class MapTest(unittest.TestCase):
    IDEAS = [{"label": a} for a in ("財布", "お茶", "ポーチ", "ストール")]

    def test_dots_are_drawn_and_link_to_the_ideas(self):
        svg = tools.gift_map("k", self.IDEAS, {"k": [[1, 0], [-2, -1], [1.5, 1], [0, 2]]})
        self.assertEqual(svg.count('class="gm-dot"'), 4)
        self.assertIn('href="#idea-2"', svg)
        self.assertIn("消えもの", svg)

    def test_identical_dots_are_nudged_apart(self):
        svg = tools.gift_map("k", self.IDEAS, {"k": [[1, 0], [1, 0], [1, 0], [1, 0]]})
        import re
        cx = re.findall(r'<circle cx="(\d+)" cy="(\d+)"', svg)
        self.assertEqual(len(set(cx)), 4)

    def test_without_tags_or_with_one_idea_there_is_no_map(self):
        self.assertEqual(tools.gift_map("k", self.IDEAS, {}), "")
        self.assertEqual(tools.gift_map("k", self.IDEAS, {"k": [[0, 0]] * 4}, shown={1}), "")
        self.assertEqual(tools.gift_map("k", self.IDEAS, {"k": [[0, 0]]}), "")


class SiteToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ct.load()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        build.render_site(cls.c, None, CFG, cls.out, release=False, today=date(2026, 10, 7))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_quiz_and_every_persona_page_exist(self):
        quiz = self.read("diagnosis/index.html")
        data = json.loads(__import__("html").unescape(quiz.split('data-json="')[1].split('"')[0]))
        self.assertEqual(len(data["questions"]), 6)
        for p in self.c["persona"]["personas"]:
            page = self.read(f"diagnosis/{p['slug']}/index.html")
            self.assertIn(p["name"], page)
            self.assertIn("LINEで送る", page)
            for s in p["themes"]:
                self.assertIn(f'href="/theme/{s}/"', page)

    def test_every_quiz_outcome_is_reachable(self):
        """Pick, for each persona, the option that favours it most in every question: it must win."""
        c = self.c["persona"]
        for p in c["personas"]:
            score = {x["slug"]: 0 for x in c["personas"]}
            for q in c["questions"]:
                best = max(q["options"], key=lambda o: o["w"].get(p["slug"], 0))
                for s, w in best["w"].items():
                    score[s] += w
            self.assertEqual(max(score, key=score.get), p["slug"], p["slug"])

    def test_checker_lists_every_entry_with_search_names(self):
        if not self.c["taboo"]:
            self.skipTest("no etiquette entries yet")
        page = self.read("tool/taboo/index.html")
        self.assertEqual(page.count('class="tb '), len(self.c["taboo"]))
        self.assertIn('data-names="', page)
        self.assertIn("name=\"q\"", page)

    def test_calculator_and_hub(self):
        self.assertIn('data-calc="return"', self.read("tool/calc/index.html"))
        hub = self.read("tool/index.html")
        for href in ("/diagnosis/", "/tool/calc/", "/memo/", "/calendar/") + (("/tool/taboo/",) if self.c["taboo"] else ()):
            self.assertIn(f'href="{href}"', hub)

    def test_theme_and_pair_pages_carry_the_gift_map_when_items_exist(self):
        # no products in this build: the proposals are empty, so no map either
        self.assertNotIn("gmap-svg", self.read("theme/beauty/index.html"))


class ArticleTest(unittest.TestCase):
    """Articles and extra theme groups, as the content factory adds them."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        fix = Path(__file__).parent / "fixtures" / "yorokobu"
        for f in fix.glob("*.json"):
            shutil.copy(f, root / f.name)
        (root / "articles.json").write_text(json.dumps({"articles": [{
            "slug": "casual-listening", "title": "さりげなく好みを聞く会話のコツ", "date": "2026-10-07",
            "lead": "贈り物の前に、相手の好みをさりげなく知っておくと、選ぶ時間が楽になります。会話の中で自然に聞き出す方法を紹介します。",
            "sections": [{"h": "最近の買い物から聞く", "body": "最近買ったものや気に入っているものを尋ねると、好みが自然に見えてきます。" * 3}],
            "checklist": ["聞きすぎない"], "faq": [{"q": "尋ねるのは失礼ですか", "a": "軽い雑談の形なら失礼にはなりません。"}], "themes": ["beauty", "thanks-daily"]}]}, ensure_ascii=False), encoding="utf-8")
        (root / "theme_groups.json").write_text(json.dumps({"groups": [{"slug": "situation", "name": "場面から選ぶ", "blurb": "手土産や持ち寄りなど、渡す場面から探します。"}]}, ensure_ascii=False), encoding="utf-8")
        data = json.loads((root / "themes.json").read_text(encoding="utf-8"))
        data["themes"][1]["group"] = "situation"
        data["themes"][1]["added"] = "2026-10-06"
        (root / "themes.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        cls.c = ct.load(root)
        cls.items = json.loads((fix / "items.json").read_text(encoding="utf-8"))
        cls.out = Path(cls.tmp.name) / "out"
        build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=date(2026, 10, 7))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_article_page_hub_feed_and_home_strip(self):
        page = self.read("read/casual-listening/index.html")
        self.assertIn("さりげなく好みを聞く会話のコツ", page)
        self.assertIn('"@type": "Article"', page)
        self.assertIn('href="/theme/beauty/"', page)
        self.assertIn("/read/casual-listening/", self.read("read/index.html"))
        self.assertIn("/read/casual-listening/", self.read("sitemap.xml"))
        feed = self.read("feed.xml")
        self.assertIn("<entry>", feed)
        self.assertIn("/read/casual-listening/", feed)
        home = self.read("index.html")
        self.assertIn("新しく追加した", home)
        self.assertIn("/read/casual-listening/", home)

    def test_a_group_added_by_the_factory_gets_its_tiles(self):
        hub = self.read("theme/index.html")
        self.assertIn("場面から選ぶ", hub)
        self.assertIn("/theme/beauty/", hub)

    def test_a_theme_with_too_few_products_is_not_published(self):
        items = json.loads(json.dumps(self.items))
        items["pairs"]["theme-beauty"] = {"ideas": [{**i, "items": []} for i in items["pairs"]["theme-beauty"]["ideas"]], "tiers": {}}
        out = Path(self.tmp.name) / "out2"
        build.render_site(self.c, items, CFG, out, release=True, today=date(2026, 10, 7))
        self.assertFalse((out / "theme" / "beauty" / "index.html").exists())
        self.assertNotIn("/theme/beauty/", (out / "theme" / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("/theme/beauty/", (out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((out / "theme" / "thanks-daily" / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
