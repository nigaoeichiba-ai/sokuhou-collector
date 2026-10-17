"""お正月の特集: 内容の関門(数字は出典つき・試したと書かない・画像がそろう)、曜日の計算、できあがりのページ。"""
import copy
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, shogatsu
from tests.test_yorokobu_compare import CFG, FIX
from tests.yorokobu_data import with_musts

DATA = shogatsu.load()


def mutated(fn):
    d = copy.deepcopy(DATA)
    fn(d)
    return shogatsu.problems(d)


class GateTest(unittest.TestCase):
    def test_the_real_content_passes_its_own_gate(self):
        self.assertEqual(shogatsu.problems(DATA), [])

    def test_a_number_or_date_in_a_section_without_a_source_is_found(self):
        def f(d):
            d["articles"][0]["sections"][2]["src"] = []                      # take the sources of a section away and put a figure into it
            d["articles"][0]["sections"][2]["list"].append("金額は3,000円ほどです")
        self.assertTrue(any("a number or date without a source" in p for p in mutated(f)))

    def test_a_number_in_an_answer_without_a_source_is_found(self):
        def f(d):
            d["articles"][1]["faq"][2]["a"] = "目安は1月7日です。"
        self.assertTrue(any("faq3" in p and "without a source" in p for p in mutated(f)))

    def test_the_year_of_the_page_may_stand_in_a_heading_and_a_lead(self):
        def f(d):
            d["articles"][1]["lead"] = "2027年の暦に当てはめます。"
        self.assertEqual(mutated(f), [])

    def test_a_source_that_is_not_known_or_not_a_page_that_was_read_is_found(self):
        def unknown(d):
            d["articles"][0]["sections"][0]["src"] = ["nope"]
        self.assertTrue(any("unknown source nope" in p for p in mutated(unknown)))

        def foreign(d):
            d["sources"]["dm"]["url"] = "https://example.com/x"
        self.assertTrue(any("is not a page that was read" in p for p in mutated(foreign)))

    def test_saying_the_site_tried_it_or_promising_or_claiming_the_cheapest_is_found(self):
        for text, mark in (("実際に使ってみて", "tried it itself"), ("必ず喜ばれます", "必ず"), ("最安です", "最安"), ("筆者は", "tried it itself")):
            def f(d, text=text):
                d["articles"][0]["sections"][2]["list"].append(text)
            self.assertTrue(any(mark in p for p in mutated(f)), text)

    def test_a_missing_picture_or_alt_text_is_found(self):
        def gone(d):
            d["articles"][0]["image"]["file"] = "no-such-picture"
        self.assertEqual(sum("no-such-picture" in p for p in mutated(gone)), 3)         # the page, the 480-px copy, the share card

        def noalt(d):
            d["hub"]["image"]["alt"] = ""
        self.assertTrue(any("image needs" in p for p in mutated(noalt)))

    def test_an_article_resting_on_one_source_is_found(self):
        def f(d):
            a = d["articles"][5]
            for s in a["sections"]:
                s["src"] = [k for k in s.get("src", [])][:1] and ["tk"]
            for q in a["faq"]:
                q["src"] = ["tk"] if q.get("src") else []
        self.assertTrue(any("fewer than two sources" in p for p in mutated(f)))

    def test_a_ragged_or_empty_table_cell_and_a_calendar_without_sources_are_found(self):
        def ragged(d):
            d["hub"]["sections"][0]["table"]["rows"][0] = ["1月1日"]
        self.assertTrue(any("wrong number of cells" in p for p in mutated(ragged)))

        def nosrc(d):
            d["hub"]["sections"][0]["src"] = []
        self.assertTrue(any("a calendar names its sources" in p or "without a source" in p for p in mutated(nosrc)))


class CalendarTest(unittest.TestCase):
    def test_the_weekday_of_each_plain_date_is_worked_out_from_the_year(self):
        t = {"head": ["a", "b"], "rows": [["1月1日", "x"], ["1月2日", "x"], ["1月3日", "x"], ["1月9日", "x"], ["1月11日", "x"], ["2月4日ごろ", "x"]]}
        rows = shogatsu._weekdays(t, 2027)["rows"]
        self.assertEqual([r[0] for r in rows], ["1月1日(金)", "1月2日(土)", "1月3日(日)", "1月9日(土)", "1月11日(月)", "2月4日ごろ"])

    def test_what_the_text_says_about_the_days_of_2027_is_true(self):
        wd = lambda m, d: "月火水木金土日"[date(2027, m, d).weekday()]
        self.assertEqual([wd(1, 1), wd(1, 2), wd(1, 3)], ["金", "土", "日"])                 # 「三が日は金・土・日」「元日が金曜日」
        self.assertEqual((wd(1, 9), wd(1, 10), wd(1, 11)), ("土", "日", "月"))               # 「1月9日は土曜日」「成人の日(1月11日)は月曜日で三連休」
        self.assertEqual(DATA["year"], 2027)
        hub = " ".join(s.get("p", [""])[0] for s in DATA["hub"]["sections"])
        self.assertIn("元日が金曜日", hub)
        self.assertIn("1月11日の月曜日", hub)

    def test_the_second_monday_of_january_2027_is_the_11th_as_the_cabinet_office_lists_it(self):
        mondays = [d for d in range(1, 32) if date(2027, 1, d).weekday() == 0]
        self.assertEqual(mondays[1], 11)
        self.assertIn("www8.cao.go.jp", DATA["sources"]["cao"]["url"])


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        items = with_musts(json.loads((FIX / "items.json").read_text(encoding="utf-8")), cls.c)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.render_site(cls.c, items, {**CFG, "yahoo_vc": {"sid": "1", "pid": "2"}}, cls.root, release=True, today=date(2026, 10, 17))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def paths(self):
        return ["shogatsu/index.html"] + [f"shogatsu/{a['slug']}/index.html" for a in DATA["articles"]]

    def test_the_landing_page_and_the_ten_articles_are_built(self):
        self.assertEqual(len(DATA["articles"]), 10)
        for p in self.paths():
            html = self.read(p)
            self.assertEqual(html.count("<h1"), 1, p)
            self.assertRegex(html, r'<link rel="canonical" href="https://yorokobu-present\.com/shogatsu/[^"]*">', p)
            self.assertIn("| よろこぶプレゼント</title>", html, p)

    def test_each_page_names_its_sources_with_links_and_says_it_did_not_try_the_products(self):
        for p in self.paths():
            html = self.read(p)
            self.assertIn("出典(確認日 2026年10月17日)", html, p)
            self.assertEqual(html.count("この記事は、出典先を要約・比較し、当サイトの考え方を足したものです。しきたりには諸説があり、地域や家で違います。贈る相手の習慣が分かるときは、それに合わせてください。"), 1, p)   # the one notice
            self.assertNotIn("seas-from", html, p)
            self.assertNotIn("上のページを開いて読みました", html, p)
            self.assertRegex(html, r'<a href="https://www\.(mistore|takashimaya|daimaru-matsuzakaya)[^"]*" rel="noopener nofollow" target="_blank">', p)

    def test_the_pictures_exist_have_their_size_and_only_the_first_is_loaded_with_priority(self):
        for p in self.paths():
            html = self.read(p)
            imgs = re.findall(r'<img src="(/assets/shogatsu/[^"]+)"[^>]*>', html)
            self.assertTrue(imgs, p)
            for m in re.finditer(r'<img src="(/assets/shogatsu/[^"]+)"([^>]*)>', html):
                self.assertTrue((self.root / m.group(1).lstrip("/")).exists(), m.group(1))
            first = re.search(r'<figure class="shg-fig"><img [^>]*>', html).group(0)
            self.assertIn('width="1200" height="800"', first)
            self.assertIn('fetchpriority="high"', first)
            self.assertIn("srcset=", first)
            self.assertNotRegex(first, r'alt=""')

    def test_the_structured_data_is_valid_json_and_names_the_share_picture(self):
        for p in self.paths():
            blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.read(p), re.S)
            kinds = [json.loads(b).get("@type") for b in blocks]
            self.assertIn("Article", kinds, p)
            art = next(json.loads(b) for b in blocks if json.loads(b).get("@type") == "Article")
            self.assertRegex(art["image"], r"^https://yorokobu-present\.com/assets/shogatsu/shogatsu-[a-z-]+-og\.webp$")
            self.assertEqual(art["dateModified"], "2026-10-17")
            self.assertIn('property="og:image"', self.read(p))

    def test_the_calendar_shows_the_weekdays_the_program_worked_out(self):
        hub = self.read("shogatsu/index.html")
        for cell in ("1月1日(金)", "1月2日(土)", "1月3日(日)", "1月11日(月)", "2月4日ごろ"):
            self.assertIn(f"<th scope=\"row\">{cell}</th>", hub, cell)
        art = self.read("shogatsu/itsumade/index.html")
        self.assertIn("1月9日(土)", art)
        kan = self.read("shogatsu/kanchu-mimai/index.html")
        for cell in ("1月8日(金)", "1月16日(土)", "2月4日ごろ"):
            self.assertIn(f"<th scope=\"row\">{cell}</th>", kan, cell)

    def test_the_pages_are_listed_for_search_engines_and_the_feed_and_the_new_strip(self):
        sitemap = self.read("sitemap.xml")
        for p in ["/shogatsu/"] + [f"/shogatsu/{a['slug']}/" for a in DATA["articles"]]:
            self.assertIn(f"https://yorokobu-present.com{p}</loc>", sitemap, p)
        feed = self.read("feed.xml")
        self.assertEqual(sum(f"/shogatsu/" in e for e in feed.split("<entry>")), 11)
        home = self.read("index.html")
        self.assertIn('href="/shogatsu/"', home)
        self.assertIn("お正月の特集", home)

    def test_occasion_pages_for_the_new_year_lead_to_the_feature(self):
        for occ, article in (("year-end-gathering", "aite-betsu"), ("homecoming", "kisei-temiyage"), ("oseibo", "itsumade")):
            html = self.read(f"occasion/{occ}/index.html")
            self.assertIn(f'href="/shogatsu/{article}/"', html, occ)

    def test_the_home_block_is_shown_only_in_its_season(self):
        self.assertEqual(shogatsu.home_band(date(2026, 6, 1)), "")
        self.assertEqual(shogatsu.home_band(date(2027, 1, 16)), "")
        for d in (date(2026, 10, 1), date(2026, 12, 25), date(2027, 1, 15)):
            self.assertIn('href="/shogatsu/"', shogatsu.home_band(d))

    def test_no_page_says_cheapest_or_always_or_that_the_site_tried_the_thing(self):
        for p in self.paths():
            text = re.sub(r"<[^>]+>", " ", self.read(p))
            for w in ("最安", "必ず", "実際に使ってみ", "試してみ"):
                self.assertNotIn(w, text, (p, w))

    def test_the_buttons_are_search_links_with_the_affiliate_marks(self):
        for p in self.paths():
            html = self.read(p)
            self.assertRegex(html, r'class="btn" href="https://hb\.afl\.rakuten\.co\.jp/[^"]+" rel="sponsored nofollow noopener" target="_blank">楽天市場で', p)
            self.assertIn("ck.jp.ap.valuecommerce.com", html, p)


if __name__ == "__main__":
    unittest.main()
