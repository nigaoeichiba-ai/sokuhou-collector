"""みんなのイラスト: the guides that were general were given what only this site can say (2026-10-28): the card maker's real screen, its limits counted against the guide's own examples, the licence
by use, the poses that exist, the sizes of the christmas pictures, two finished examples, the dates of 2027.  The numbers are measured; a sentence that could not be checked is gone."""
import json
import re
import unittest
from pathlib import Path

from PIL import Image

from sites.minna import build
from tests.test_minna_sitecache import shared_site

NEW = {
    "nenga-tsukurikata": "「年賀状をつくる」の画面と設定",
    "nenga-bunrei": "「年賀状をつくる」のひとこと欄に入るか",
    "kantyu-mimai": "2027年の寒中見舞いの日付",
    "shoyo-license": "当サイトの利用条件を用途別に見る",
    "line-reply-illust": "当サイトの動物ポーズ集にあるポーズ",
    "christmas-card": "当サイトのクリスマス素材の大きさと、カードの大きさ",
    "nenmatsu-kyugyo-oshirase": "見本と、素材の大きさ",
    "shichigosan-guide": "2026年11月15日から逆算する",
}


class SpecificGuides(unittest.TestCase):
    def guide(self, slug: str) -> str:
        out, _ = shared_site()
        return (out / "guide" / slug / "index.html").read_text(encoding="utf-8")

    def test_every_one_of_the_eight_guides_has_its_new_section_once(self):
        for slug, h2 in NEW.items():
            self.assertEqual(self.guide(slug).count(f"<h2>{h2}</h2>"), 1, slug)

    def test_the_figures_are_in_the_build_at_the_size_the_page_says(self):
        out, _ = shared_site()
        for slug in ("christmas-card", "nenmatsu-kyugyo-oshirase"):
            html = self.guide(slug)
            m = re.search(r'<img src="(/assets/examples/[^"]+)" alt="[^"]+" width="(\d+)" height="(\d+)"', html)
            self.assertTrue(m, slug)
            self.assertEqual(Image.open(out / m.group(1).lstrip("/")).size, (int(m.group(2)), int(m.group(3))), slug)

    def test_the_linked_pages_exist(self):
        out, files = shared_site()
        have = set(files)
        for slug in NEW:
            for href in re.findall(r'<ul class="check"><li><a href="(/[^"]+)">', self.guide(slug)) + re.findall(r'<li><a href="(/(?:series|special|tool|pose|license)/[^"]*)">', self.guide(slug)):
                self.assertTrue(href.endswith("/"), href)
                self.assertIn(href.lstrip("/") + "index.html", have, f"{slug}: {href}")

    def test_the_character_counts_of_the_nenga_bunrei_table_are_the_real_lengths(self):
        g = next(x for x in json.loads((Path(build.__file__).parent / "content" / "guides.json").read_text(encoding="utf-8"))["guides"] if x["slug"] == "nenga-bunrei")
        examples = [x for s in g["sections"] if s["h2"] in ("友人と家族への文例", "職場や取引先への文例", "先生やお世話になった人へ") for x in s["list"]]
        sec = next(s for s in g["sections"] if s["h2"] == NEW["nenga-bunrei"])
        self.assertEqual([r[2] for r in sec["table"]["rows"]], [f"{len(x)}字" for x in examples])
        for r, x in zip(sec["table"]["rows"], examples):
            self.assertEqual(r[3], "入る" if len(x) <= 90 else f"{len(x) - 90}字超える")

    def test_the_sentence_that_could_not_be_checked_is_gone(self):
        self.assertNotIn("ネットショップの受付期間", self.guide("nenga-2027-schedule"))

    def test_the_dates_of_2027_have_the_right_weekdays(self):
        html = self.guide("kantyu-mimai")
        for day in ("1月5日(火)", "1月7日(木)", "1月8日(金)", "1月15日(金)", "2月3日(水)", "2月4日(木)"):
            self.assertIn(day, html)

    def test_the_modified_date_is_in_the_article_data(self):
        self.assertIn('"dateModified": "2026-10-28"', self.guide("kantyu-mimai"))

class HagakiGuide(unittest.TestCase):
    """/guide/hagaki-size-ichiran/ (2026-10-28): checked against Japan Post, linked from the pages that talk about the same card, no ad tag."""

    def read(self, rel: str) -> str:
        out, _ = shared_site()
        return (out / rel).read_text(encoding="utf-8")

    def test_the_guide_says_when_it_was_checked_and_does_not_call_the_return_postcard_exempt(self):
        html = self.read("guide/hagaki-size-ichiran/index.html")
        self.assertIn("2026年10月28日に、日本郵便", html)
        self.assertIn("往復はがきを除く", html)
        self.assertNotIn("大きさの条件は上記の対象外", html)
        self.assertIn("日本郵便の表で確認", html)

    def test_five_pages_link_to_it(self):
        for rel in ("guide/nenga-tsukurikata/index.html", "guide/nenga-2027-schedule/index.html", "tool/nenga/index.html", "special/nenga-2027/index.html", "printables/index.html"):
            self.assertIn('href="/guide/hagaki-size-ichiran/"', self.read(rel), rel)

    def test_it_is_not_on_the_ad_allow_list(self):
        self.assertNotIn("/guide/hagaki-size-ichiran/", build.ADS_ALLOW)


if __name__ == "__main__":
    unittest.main()
