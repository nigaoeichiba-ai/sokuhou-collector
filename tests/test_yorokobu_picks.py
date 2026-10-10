"""今日のおすすめギフト: the gate every day's file has to pass, and the pages built from it."""
import copy
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, dailypicks as dp
from sokuhou import rakuten, sitecheck
from sokuhou.sitekit import BuildError
from tests.test_yorokobu_fetch import raw_item

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
SITE = Path(__file__).resolve().parents[1] / "sites" / "yorokobu"
DAY_FILE = SITE / "content" / "daily" / "2026-10-11.json"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}


def day() -> dict:
    return json.loads(DAY_FILE.read_text(encoding="utf-8"))


def live_items(d: dict, sold_out: tuple[str, ...] = ()) -> dict:
    out = {}
    for i, e in enumerate(d["rakuten"]):
        shop, num = e["code"].split(":")
        it = rakuten.normalize(raw_item(num, 3000 + i * 500, shop=shop, reviews=100 + i, rating=4.5, name=f"{e['name']} 楽天の表記"))
        it["code"] = e["code"]
        it["available"] = e["code"] not in sold_out
        out[e["code"]] = it
    return out


def render(tmp: Path, days: list[dict], daily_items: dict | None, name: str = "site") -> Path:
    items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
    if daily_items is not None:
        items["daily"] = daily_items
    out = tmp / name
    build.render_site(content.load(content_dir_for(tmp, name, days)), items, CFG, out, release=True, today=date(2026, 10, 11))
    return out


def content_dir_for(tmp: Path, name: str, days: list[dict]) -> Path:
    c = tmp / f"content-{name}"
    shutil.copytree(FIX, c)
    (c / "daily").mkdir()
    for x in days:
        (c / "daily" / f"{x['date']}.json").write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
    return c


class GateTest(unittest.TestCase):
    def test_the_real_day_file_passes_the_gate(self):
        self.assertEqual(dp.problems(day()), [])

    def test_a_day_needs_ten_and_ten_products_and_three_highlights(self):
        d = day()
        d["rakuten"] = d["rakuten"][:9]
        self.assertTrue(any("9 Rakuten" in p for p in dp.problems(d)))
        d = day()
        d["highlights"][1]["ref"] = d["highlights"][0]["ref"]
        self.assertTrue(any("highlights" in p for p in dp.problems(d)))

    def test_absolute_claims_medical_words_and_hype_are_refused(self):
        for word in ("絶対に喜ばれます", "必ず届きます", "日本一の味", "疲れが改善します", "大人気の一品"):
            d = day()
            d["rakuten"][0]["summary"] = d["rakuten"][0]["summary"] + word
            self.assertTrue(any("banned word" in p for p in dp.problems(d)), word)

    def test_an_amazon_text_may_not_carry_a_price_a_rating_or_a_review_count(self):
        for text in ("価格は2,000円です", "評価は★4.5です", "1万件のレビューがあります", "¥1980"):
            d = day()
            d["amazon"][0]["good"] = d["amazon"][0]["good"] + text
            self.assertTrue(any("Amazon text may not carry" in p for p in dp.problems(d)), text)
        d = day()
        d["rakuten"][0]["good"] = d["rakuten"][0]["good"] + "この商品は3,000円ほどです。"   # a Rakuten price is Rakuten's own data, allowed in text
        self.assertFalse(any("Amazon text" in p for p in dp.problems(d)))

    def test_text_copied_from_the_shop_page_is_found(self):
        d = day()
        shop = "発送日時点で賞味期限まで残り21日以上の商品をお届けします。常温でそのまま保存できます。"
        d["rakuten"][0]["care"] = "発送日時点で賞味期限まで残り21日以上の商品をお届けします。改まった贈り物にするなら、紙袋を用意します。"
        self.assertTrue(any("shop's own text" in p for p in dp.problems(d, {"r1": shop})))
        self.assertFalse(any("shop's own text" in p for p in dp.problems(day(), {"r1": shop})))     # the day's own wording of the same fact is fine
        self.assertTrue(dp.copied("あいうえおかきくけこさしすせそ", "xあいうえおかきくけこさしすせそy", 14))
        self.assertFalse(dp.copied("あいうえおかきくけこ", "あいうえおかきくけ", 14))

    def test_two_entries_with_the_same_headline_or_opening_are_refused(self):
        d = day()
        d["rakuten"][1]["headline"] = d["rakuten"][0]["headline"]
        self.assertTrue(any("share a headline" in p for p in dp.problems(d)))
        d = day()
        d["amazon"][1]["summary"] = d["amazon"][0]["summary"][:10] + d["amazon"][1]["summary"][10:]
        self.assertTrue(any("begin the same way" in p for p in dp.problems(d)))

    def test_childish_tone_and_machine_phrasing_use_the_site_wide_style_gate(self):
        d = day()
        d["amazon"][2]["summary"] = d["amazon"][2]["summary"] + "ぜんぶそろっていて、わくわくします。"
        self.assertTrue(any("childish tone" in p for p in dp.problems(d)))

    def test_codes_asins_kinds_and_mood_images_are_checked(self):
        d = day()
        d["rakuten"][0]["code"] = "no code"
        d["amazon"][0]["asin"] = "123"
        d["amazon"][1]["mood"] = "nothing-9"
        d["amazon"][2]["kind"] = "おもちゃ"
        bad = " ".join(dp.problems(d))
        for part in ("Rakuten item code", "bad ASIN", "bad mood image", "unknown kind"):
            self.assertIn(part, bad)

    def test_every_mood_image_exists_for_every_kind(self):
        for key in dp.KIND_KEY.values():
            for v in range(1, dp.MOOD_VARIANTS + 1):
                self.assertTrue((SITE / "assets" / "mood" / f"{key}-{v}.webp").exists(), f"{key}-{v}")
        for e in day()["amazon"]:
            self.assertTrue((SITE / "assets" / "mood" / f"{e['mood']}.webp").exists(), e["mood"])

    def test_a_bad_file_stops_the_build_and_a_misdated_file_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = day()
            d["rakuten"][0]["summary"] = "短い"
            c = content_dir_for(Path(tmp), "bad", [d])
            with self.assertRaises(BuildError):
                content.load(c)
            (c / "daily" / "2026-10-11.json").write_text(json.dumps({**day(), "date": "2026-10-12"}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                content.load(c)


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.d = day()
        older = {**copy.deepcopy(cls.d), "date": "2026-10-10"}
        older["theme"] = "前の日のテーマを、別の言葉で言い表したもの"
        cls.out = render(t, [cls.d, older], live_items(cls.d))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = build.DATA_ON = build.PICKS_ON = False

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_pages_exist_are_in_the_sitemap_the_nav_the_home_page_and_the_feed(self):
        for rel in ("picks/index.html", "picks/2026-10-11/index.html", "picks/2026-10-10/index.html"):
            self.assertTrue((self.out / rel).exists(), rel)
        sm = self.read("sitemap.xml")
        self.assertIn("/picks/2026-10-11/", sm)
        for rel in ("index.html", "tool/index.html", "picks/index.html"):
            self.assertIn('<a href="/picks/"', self.read(rel), rel)
        home = self.read("index.html")
        self.assertIn('href="/picks/2026-10-11/"', home)
        self.assertIn("今日のおすすめ", home)
        self.assertIn("/picks/2026-10-11/", self.read("feed.xml"))

    def test_the_newest_day_says_today_and_the_older_one_its_date_with_links_between_them(self):
        new, old = self.read("picks/2026-10-11/index.html"), self.read("picks/2026-10-10/index.html")
        self.assertIn("<h1>今日のおすすめギフト20選 10月11日</h1>", new)
        self.assertIn("<h1>2026年10月10日のおすすめギフト20選</h1>", old)
        self.assertIn('href="/picks/2026-10-10/"', new)
        self.assertIn('href="/picks/2026-10-11/"', old)

    def test_twenty_cards_ten_from_each_shop_with_both_shops_buttons(self):
        html = self.read("picks/2026-10-11/index.html")
        self.assertEqual(len(re.findall(r'<article class="pick"', html)), 20)
        r_part = html.split('id="amazon"')[0].split('id="rakuten"')[1]
        a_part = html.split('id="amazon"')[1].split('id="policy"')[0]
        self.assertEqual(r_part.count('<article class="pick"'), 10)
        self.assertEqual(a_part.count('<article class="pick"'), 10)
        self.assertEqual(r_part.count(">楽天市場で見る<"), 10)
        self.assertEqual(r_part.count(">Amazonで探す<"), 10)                  # the same product, looked for on the other shop: a button of the same kind
        self.assertEqual(a_part.count(">Amazonで見る<"), 10)
        self.assertEqual(a_part.count(">楽天市場で探す<"), 10)
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=", r_part)
        self.assertIn("tag=amazonmacs-22", a_part)
        self.assertIn("https://www.amazon.co.jp/dp/B00UG9X98U?tag=amazonmacs-22", a_part)

    def test_rakuten_cards_show_the_price_from_the_lookup_amazon_cards_show_none_and_say_the_picture_is_an_image(self):
        html = self.read("picks/2026-10-11/index.html")
        r_part = html.split('id="amazon"')[0].split('id="rakuten"')[1]
        a_part = html.split('id="amazon"')[1].split('id="policy"')[0]
        self.assertIn("¥3,000", r_part)
        self.assertIn("時点の情報", r_part)
        self.assertNotIn("¥", a_part)
        self.assertNotIn("円", a_part)
        self.assertEqual(a_part.count("イメージ画像"), 10)
        self.assertIn("/assets/mood/food-1.webp", a_part)
        self.assertIn("商品写真ではなく、贈る場面を表したイメージ", a_part)
        self.assertIn("価格と商品の写真を載せていません", a_part)

    def test_the_page_says_how_the_text_was_made_and_does_not_claim_to_have_tried_the_products(self):
        html = self.read("picks/2026-10-11/index.html")
        self.assertIn("実際に使って試した感想ではありません", html)
        self.assertIn("そのまま載せていません", html)
        self.assertIn("Amazonのアソシエイトとして", html)                      # the Associates sentence is on a page with Amazon links
        self.assertIn('class="pr-chip"', html)

    def test_structured_data_lists_the_twenty_with_their_anchors(self):
        html = self.read("picks/2026-10-11/index.html")
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        item_list = next(x for x in ld if x["@type"] == "ItemList")
        self.assertEqual(item_list["numberOfItems"], 20)
        self.assertEqual(len(item_list["itemListElement"]), 20)
        self.assertTrue(item_list["itemListElement"][0]["url"].endswith("/picks/2026-10-11/#r1"))

    def test_the_site_check_passes_for_the_picks_pages(self):
        problems = [p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "picks" in p]
        self.assertEqual(problems, [])

    def test_a_product_that_rakuten_no_longer_lists_as_available_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = render(Path(tmp), [self.d], live_items(self.d, sold_out=("tsukada:10000019",)))
            html = (out / "picks/2026-10-11/index.html").read_text(encoding="utf-8")
            self.assertIn("楽天市場で選ぶ9点", html)
            self.assertNotIn("塚田商店", html)
            self.assertIn("今日のおすすめギフト19選", html)

    def test_without_a_lookup_the_card_keeps_the_saved_picture_and_shows_no_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = render(Path(tmp), [self.d], None)
            html = (out / "picks/2026-10-11/index.html").read_text(encoding="utf-8")
            r_part = html.split('id="amazon"')[0].split('id="rakuten"')[1]
            self.assertEqual(r_part.count('<article class="pick"'), 10)
            self.assertNotIn("¥", r_part)
            self.assertIn("価格・在庫は、販売ページでご確認ください。", r_part)
            self.assertIn(self.d["rakuten"][0]["img"], r_part)

    def test_without_an_associates_id_the_amazon_part_is_left_out_instead_of_breaking_the_build(self):
        global CFG
        saved = CFG
        CFG = {**CFG, "amazon_tracking_id": None}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = render(Path(tmp), [self.d], live_items(self.d))
                html = (out / "picks/2026-10-11/index.html").read_text(encoding="utf-8")
                self.assertEqual(html.count('<article class="pick"'), 10)
                self.assertNotIn("amazon.co.jp", html)
                self.assertNotIn('id="amazon"', html)
                self.assertNotIn("Amazonのアソシエイト", html)
                self.assertNotIn("#a3", html)                                       # a highlight that points at an Amazon product is dropped
        finally:
            CFG = saved

    def test_no_day_files_means_no_picks_pages_and_no_nav_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = render(Path(tmp), [], None)
            self.assertFalse((out / "picks").exists())
            self.assertNotIn('href="/picks/"', (out / "index.html").read_text(encoding="utf-8"))
        build.PICKS_ON = False


class RefreshTest(unittest.TestCase):
    def test_the_codes_of_the_newest_days_are_what_the_refresh_looks_up(self):
        d1, d2 = day(), {**day(), "date": "2026-10-10"}
        codes = dp.rakuten_codes([d1, d2], limit=1)
        self.assertEqual(len(codes), 10)
        self.assertEqual(len(dp.rakuten_codes([d1, d2], limit=2)), 20)


if __name__ == "__main__":
    unittest.main()
