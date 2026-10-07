import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, factory, quality
from sokuhou import sitecheck

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


def line(tag: str) -> str:
    return f"{tag}、いつも気にかけてくれてありがとう。これからも、あなたらしく元気に過ごしてね。"


def good_set(to="母へ", style="丁寧", tag="a"):
    return {"to": to, "style": style, "lines": [line(f"{tag}1"), line(f"{tag}2"), line(f"{tag}3")]}


def good_entry(occasion="birthday", **over):
    m = {"occasion": occasion, "intro": "誕生日のメッセージは、長く書くより、その人らしさがひとつ入っているほうが心に残ります。相手との距離に合わせて言葉を選び、短くても気持ちがきちんと伝わる文を、そのまま使える形で集めました。",
         "sets": [good_set("母へ", "丁寧", "a"), good_set("友人へ", "やわらかい", "b"), good_set("職場の先輩へ", "丁寧", "c"),
                  good_set("恋人へ", "やわらかい", "d"), good_set("家族みんなへ", "ひとこと", "e")],
         "manners": ["年齢や見た目に触れる言葉は、相手によっては重く感じられるので避けます。", "長い文より、短くても具体的な思い出をひとつ添えるほうが伝わります。",
                     "忙しい相手には、返事を求める言い方をしないようにします。"],
         "closing": ["体に気をつけてね。", "また会える日を楽しみにしています。", "よい一年になりますように。"]}
    m.update(over)
    return m


class QualityTest(unittest.TestCase):
    OCC = {"birthday", "mothers-day"}

    def probs(self, m, known=None):
        return quality.message_problems(m, self.OCC, known)

    def test_a_good_entry_passes(self):
        self.assertEqual(self.probs(good_entry()), [])

    def test_each_rule_is_reported(self):
        cases = [
            (good_entry(occasion="nope"), "unknown occasion"),
            (good_entry(intro="短い"), "intro length"),
            (good_entry(sets=good_entry()["sets"][:3]), "sets 3"),
            (good_entry(manners=["短い"] * 3), "manners need"),
            (good_entry(closing=["短い"]), "closing needs"),
        ]
        for m, needle in cases:
            self.assertTrue(any(needle in p for p in self.probs(m)), (needle, self.probs(m)))
        bad = good_entry()
        bad["sets"][0]["style"] = "くだけた"
        self.assertTrue(any("style" in p for p in self.probs(bad)))
        bad = good_entry()
        bad["sets"][0]["lines"] = bad["sets"][0]["lines"][:2]
        self.assertTrue(any("has 2 lines" in p for p in self.probs(bad)))
        bad = good_entry()
        bad["sets"][0]["lines"][0] = "短すぎる。"
        self.assertTrue(any("message length" in p for p in self.probs(bad)))

    def test_duplicates_forbidden_words_and_emoji_are_reported(self):
        bad = good_entry()
        bad["sets"][1]["lines"][0] = bad["sets"][0]["lines"][0]
        self.assertTrue(any("twice" in p for p in self.probs(bad)))
        bad = good_entry()
        bad["sets"][0]["lines"][0] += "楽天で買ったよ。"
        self.assertTrue(any("forbidden 楽天" in p for p in self.probs(bad)))
        bad = good_entry()
        bad["sets"][0]["lines"][0] += "😀"
        self.assertTrue(any("emoji" in p for p in self.probs(bad)))

    def test_existing_occasion_is_refused(self):
        self.assertTrue(any("exist" in p for p in self.probs(good_entry(), {"birthday"})))

    def test_the_word_saikou_is_fine_in_a_message(self):
        m = good_entry()
        m["sets"][0]["lines"][0] = "お母さんは、私にとって最高の先生です。いつも本当にありがとう。これからも元気でいてね。"
        self.assertEqual(self.probs(m), [])


class FactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for f in FIX.glob("*.json"):
            shutil.copy(f, self.dir / f.name)
        self._orig = factory.CONTENT
        factory.CONTENT = self.dir

    def tearDown(self):
        factory.CONTENT = self._orig
        self.tmp.cleanup()

    def test_a_good_entry_is_merged_and_loads(self):
        n, probs = factory.merge_messages({"messages": [good_entry()]}, date(2026, 10, 8))
        self.assertEqual((n, probs), (1, []))
        c = content.load(self.dir)
        self.assertEqual(list(c["messages"]), ["birthday"])
        self.assertEqual(c["messages"]["birthday"]["added"], "2026-10-08")

    def test_a_bad_entry_changes_nothing_and_a_repeat_of_an_existing_message_is_refused(self):
        n, probs = factory.merge_messages({"messages": [good_entry(intro="短い")]}, date(2026, 10, 8))
        self.assertEqual(n, 0)
        self.assertFalse((self.dir / "messages.json").exists())
        factory.merge_messages({"messages": [good_entry("birthday")]}, date(2026, 10, 8))
        second = good_entry("mothers-day")                                         # same sentences as birthday's
        n, probs = factory.merge_messages({"messages": [second]}, date(2026, 10, 9))
        self.assertEqual(n, 0)
        self.assertTrue(any("repeats an existing" in p for p in probs), probs)

    def test_the_brief_asks_only_for_occasions_without_messages(self):
        factory.merge_messages({"messages": [good_entry("birthday")]}, date(2026, 10, 8))
        out = self.dir / "brief.md"
        factory.brief("messages", 5, out, self.dir / "answer.json")
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("- birthday |", text)
        self.assertIn("- mothers-day |", text)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name) / "content"
        d.mkdir()
        for f in FIX.glob("*.json"):
            shutil.copy(f, d / f.name)
        occ = [o["slug"] for o in json.loads((d / "occasions.json").read_text(encoding="utf-8"))["occasions"]]
        entries = []
        for i, slug in enumerate(occ[:2]):
            e = good_entry(slug)
            for s in e["sets"]:
                s["lines"] = [ln.replace("、いつも", f"、({i})いつも") for ln in s["lines"]]
            entries.append(e)
        (d / "messages.json").write_text(json.dumps({"messages": entries}, ensure_ascii=False), encoding="utf-8")
        cls.slugs = occ[:2]
        cls.c = content.load(d)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, items, CFG, cls.out, release=True, today=date(2026, 10, 7))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_hub_and_occasion_pages_exist_and_are_linked(self):
        self.assertTrue((self.out / "message/index.html").exists())
        for slug in self.slugs:
            self.assertTrue((self.out / f"message/{slug}/index.html").exists())
            self.assertIn(f'href="/message/{slug}/"', self.read(f"occasion/{slug}/index.html"))
        self.assertIn('href="/message/"', self.read("index.html"))
        self.assertIn("/message/" + self.slugs[0] + "/", self.read("sitemap.xml"))

    def test_the_page_has_copyable_messages_with_buttons_that_stay_hidden_without_script(self):
        html = self.read(f"message/{self.slugs[0]}/index.html")
        self.assertEqual(html.count('class="msg-text"'), 15 + 3)                  # 5 sets x 3 messages + 3 closing phrases
        self.assertEqual(html.count("data-copy hidden"), 15 + 3)
        self.assertIn("母へ", html)
        self.assertIn("言葉を選ぶときの、気をつけたいこと", html)
        self.assertNotIn("hb.afl.rakuten.co.jp", html)                            # a pure reading page: no affiliate link, so no PR notice either
        self.assertNotIn('class="pr-quiet"', html)
        self.assertIn("data-copy", (Path(build.HERE) / "assets" / "app.js").read_text(encoding="utf-8"))

    def test_the_built_pages_pass_the_site_checker(self):
        problems = [p for p in sitecheck.check_dir(self.out, CFG["site_url"]) if "message" in p]
        self.assertEqual(problems, [])

    def test_without_messages_there_are_no_pages_and_no_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            c = content.load(FIX)
            items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
            build.render_site(c, items, CFG, out, release=True, today=date(2026, 10, 7))
            self.assertFalse((out / "message").exists())
            self.assertNotIn("/message/", (out / "index.html").read_text(encoding="utf-8"))
        build.RANKING_ON = False


if __name__ == "__main__":
    unittest.main()
