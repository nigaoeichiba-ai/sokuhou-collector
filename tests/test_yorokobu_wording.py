"""Wording: no 読点 in short phrases (owner, 2026-10-14: 「必要以上に読点を打たない」「短い文章に読点は一切不要」), full-width question marks, and the ♡ on every product picture."""
import json
import re
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from sites.yorokobu import build, commas, content
from tests.yorokobu_data import live_daily, with_musts

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}
TEXT_TAGS = {"h1", "h2", "h3", "summary", "button"}


class Headings(HTMLParser):
    """The text of every heading, summary and button of a page."""

    def __init__(self):
        super().__init__()
        self.stack, self.buf, self.out = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in TEXT_TAGS:
            self.stack.append(tag)
            self.buf = []

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if t:
                self.out.append(t)
            self.buf = []

    def handle_data(self, data):
        if self.stack:
            self.buf.append(data)


class LightWordingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        items["daily"] = live_daily(cls.c)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 13))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_heading_or_button_of_the_site_has_a_comma_a_short_phrase_does_not_need(self):
        bad = {}
        for p in self.root.rglob("*.html"):
            h = Headings()
            h.feed(p.read_text(encoding="utf-8"))
            for t in h.out:
                if "、" in t and commas.lighten_short(t) != t:
                    bad.setdefault(t, str(p.relative_to(self.root)))
        self.assertEqual(bad, {}, "short phrases with a needless 読点: " + "; ".join(f"{t} ({f})" for t, f in list(bad.items())[:12]))

    def test_the_headings_the_owner_named_read_without_commas(self):
        home = (self.root / "index.html").read_text(encoding="utf-8")
        for t in ("まず見たいおすすめページ", "新しく追加したページ", "数字で見る贈り物", "気持ち・興味から探す", "そろそろ準備したいイベント", "だれに贈りますか？", "迷ったときに"):
            self.assertIn(f"<h2>{t}</h2>", home, t)
        for old in ("迷ったときの道具", "迷ったときの、道具", "いま準備したいイベント", "だれに、贈りますか"):
            self.assertNotIn(old, home)

    def test_a_question_in_japanese_ends_with_a_full_width_question_mark(self):
        bad = []
        for p in self.root.rglob("*.html"):
            html = re.sub(r"<script.*?</script>|<style.*?</style>", "", p.read_text(encoding="utf-8"), flags=re.S)
            text = re.sub(r"<[^>]*>", " ", html)
            bad += [f"{p.relative_to(self.root)}: {m}" for m in re.findall(r"[ぁ-んァ-ヶ一-龥)）」]\?", text)[:1]]
        self.assertEqual(bad[:5], [])


class HeartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        items["daily"] = live_daily(cls.c)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, CFG, cls.root, release=True, today=date(2026, 10, 13))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_product_picture_of_the_daily_page_has_a_heart_on_it(self):
        day = sorted((self.root / "picks").glob("2026-*/index.html"))[-1].read_text(encoding="utf-8")
        cards = re.findall(r'<article class="pick".*?</article>', day, re.S)
        self.assertGreaterEqual(len(cards), 10)
        for c in cards:
            box = re.search(r'<div class="imgbox[^"]*">(.*?)</button></div>', c, re.S)
            self.assertTrue(box and 'class="fav"' in box.group(1), c[:120])               # the heart is inside the picture's own box
        self.assertTrue(any('data-code="a:' in c for c in cards), "an Amazon product is kept as a:<ASIN>")
        self.assertFalse(any('data-code="a:' in c and "data-price" in re.search(r'<button type="button" class="fav".*?</button>', c, re.S).group(0) for c in cards), "no price for an Amazon product")

    def test_the_feature_page_and_the_gift_cards_carry_the_heart_too(self):
        f = self.c["features"][0]
        page = (self.root / "pick" / f["slug"] / "index.html").read_text(encoding="utf-8")
        self.assertRegex(page, r'<div class="imgbox[^"]*"><div class="feat-photo.*?class="fav"')
        gift = (self.root / "gift" / "birthday-mother" / "index.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(gift.count('class="fav"'), 1)
        self.assertNotIn('class="fav"', (self.root / "about" / "index.html").read_text(encoding="utf-8"))


    def test_the_top_page_has_the_concierge_card_that_stays_hidden_without_the_script_and_the_script_opens_it(self):
        home = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertRegex(home, r'<section class="block cc-wrap" data-cc-box hidden>.*?<button type="button" class="btn big" data-cc-open hidden>相談してみる</button>')
        self.assertIn("贈り物のことでお困りではありませんか？", home)
        js = (Path(build.__file__).parent / "assets" / "concierge.js").read_text(encoding="utf-8")
        for needle in ("[data-cc-open]", "cc-nudge", "yorokobu.ccnudge"):
            self.assertIn(needle, js)
        css = (Path(build.__file__).parent / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.cc-open \{[^}]*background: var\(--accent\)")                   # the corner button is filled, not a white pill
        self.assertIn("prefers-reduced-motion", css)

    def test_the_corner_button_is_a_small_round_mark_on_a_phone_and_stays_large_and_labelled_on_a_pc(self):
        base = Path(build.__file__).parent / "assets"
        css = (base / "style.css").read_text(encoding="utf-8").replace("\r\n", "\n")
        js = (base / "concierge.js").read_text(encoding="utf-8")
        self.assertIn('<i class="cc-label">贈り物の相談</i>', js)                                 # the words stay in the page (screen readers); only drawn away on a phone
        phone = re.search(r"@media \(max-width: 640px\) \{\n  \.cc \{.*?\n\}\n", css, re.S)
        self.assertIsNotNone(phone)
        block = phone.group(0)
        self.assertRegex(block, r"\.cc-open \{[^}]*width: (3\d|4[0-4])px; height: (3\d|4[0-4])px")   # at most 44px, round
        self.assertRegex(block, r"\.cc-label \{[^}]*clip: rect")
        pc = re.search(r"^\.cc-open \{[^}]*\}", css, re.M).group(0)                              # outside the query: the big pill, unchanged
        self.assertIn("padding: .8em 1.5em .8em 1.1em", pc)
        self.assertNotIn("width: 38px", pc)

    def test_the_list_keeps_an_amazon_product_without_a_price_and_sends_only_the_rakuten_ones_as_a_link(self):
        js = (Path(build.__file__).parent / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('indexOf("a:") === 0', js)
        self.assertIn("/list/?c=", js)
        self.assertIn("filter(function (x) { return !amazon(x); })", js)
        mine = (Path(build.__file__).parent / "assets" / "mine.js").read_text(encoding="utf-8")
        self.assertIn("amazonCard", mine)


class ShortPhraseRuleTest(unittest.TestCase):
    def test_the_owners_examples(self):
        for before, after in (("だれに、贈りますか？", "だれに贈りますか？"), ("予算から、探す", "予算から探す"), ("いま、準備したいイベント", "いま準備したいイベント"),
                              ("まず見たい、おすすめページ", "まず見たいおすすめページ"), ("新しく追加した、ページ", "新しく追加したページ"), ("数字で見る、贈り物", "数字で見る贈り物"),
                              ("気持ち・興味から、探す", "気持ち・興味から探す"), ("迷ったときの、道具", "迷ったときの道具")):
            self.assertEqual(commas.lighten_short(before), after)

    def test_what_has_to_keep_its_comma(self):
        for keep in ("好きなもの、趣味、年齢", "朝は忙しく、夜は暇", "おいしい、安い", "サイズ: 30×30cm、重さ約60g", "決まっていなくても、いくらまでかけるかが決まっていれば", "汗を拭く場面で出番が多く、部活やジムにも使えます。"):
            self.assertEqual(commas.lighten_short(keep), keep)
        self.assertEqual(commas.lighten("花は来客を迎える飾りに、和菓子はお茶の時間に、ストールは初詣や買い物の外出に使えます。"), "花は来客を迎える飾りに、和菓子はお茶の時間に、ストールは初詣や買い物の外出に使えます。")


if __name__ == "__main__":
    unittest.main()
