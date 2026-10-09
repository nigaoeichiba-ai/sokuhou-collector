"""Hand-picked Amazon products: text and a tagged link on the occasion and pair pages and on /amazon/; never a price, never a picture."""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content, quality
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError

HERE = Path(__file__).parent
SITE = Path(__file__).resolve().parents[1] / "sites" / "yorokobu"
FIX = HERE / "fixtures" / "yorokobu"
CFG = {**json.loads((SITE / "config.json").read_text(encoding="utf-8")), "amazon_tracking_id": "amazonmacs-22"}


def fixture_with(picks):
    tmp = tempfile.mkdtemp()
    dst = Path(tmp) / "c"
    shutil.copytree(FIX, dst)
    (dst / "amazon_picks.json").write_text(json.dumps({"checked": "2026-10-09", "picks": picks}, ensure_ascii=False), encoding="utf-8")
    return dst


GOOD = {"asin": "B00C6VIA6C", "name": "テスト菓子", "maker": "テスト社", "kind": "食べもの・飲みもの", "occasions": ["birthday"],
        "why": "個包装なので、家族で分けられます。", "source": "テスト"}


class AmazonPicksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load()
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=date(2026, 10, 9))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_real_picks_are_valid_written_calmly_and_have_no_price(self):
        picks = self.c["amazon"]
        self.assertGreaterEqual(len(picks), 15)
        for p in picks:
            self.assertEqual(quality.language_problems(p["why"] + p["name"], p["asin"]), [], p["asin"])
            self.assertNotRegex(p["why"], r"[0-9,]+円|[¥￥]")
            self.assertTrue(p["source"].endswith("(2026-10-09)"), p["asin"])

    def test_the_hub_lists_every_pick_with_a_tagged_sponsored_link_and_the_notice(self):
        html = self.read("amazon/index.html")
        for p in self.c["amazon"]:
            self.assertIn(f"https://www.amazon.co.jp/dp/{p['asin']}?tag=amazonmacs-22", html, p["asin"])
        self.assertEqual(html.count('rel="sponsored nofollow noopener"'), len(self.c["amazon"]))
        self.assertIn("Amazonのアソシエイトとして", html)
        self.assertIn('class="pr-quiet"', html)
        self.assertNotIn("<img", html.split("<main")[1].split("</main>")[0].replace('<img class="ic', ""))     # no product picture

    def test_an_occasion_page_shows_only_the_picks_for_it_and_links_to_the_hub(self):
        for rel, occ in (("occasion/birthday/index.html", "birthday"), ("occasion/mothers-day/index.html", "mothers-day")):
            if not (self.out / rel).exists():
                continue
            html = self.read(rel)
            want = [p for p in self.c["amazon"] if occ in p["occasions"]][:4]
            self.assertIn("Amazonで見つけた贈り物", html)
            for p in want:
                self.assertIn(p["asin"], html, rel)
            others = [p for p in self.c["amazon"] if occ not in p["occasions"]]
            for p in others:
                self.assertNotIn(p["asin"], html, rel)
            self.assertIn('href="/amazon/"', html)

    def test_a_pick_for_certain_recipients_is_not_shown_to_other_recipients(self):
        c = content.load()
        glen = next(p for p in c["amazon"] if p["asin"] == "B001TP4S62")
        self.assertIn(glen, build.amazon_picks_for(c, "fathers-day", "father"))
        self.assertNotIn(glen, build.amazon_picks_for(c, "fathers-day", "baby"))
        self.assertNotIn(glen, build.amazon_picks_for(c, "mothers-day", "father"))

    def test_without_an_associates_id_nothing_is_shown_and_there_is_no_hub(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(self.c, self.items, {**CFG, "amazon_tracking_id": None}, out, release=True, today=date(2026, 10, 9))
            self.assertFalse((out / "amazon").exists())
            self.assertNotIn("amazon.co.jp", (out / "occasion/birthday/index.html").read_text(encoding="utf-8"))

    def test_the_built_site_passes_the_checker(self):
        self.assertEqual([p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "amazon" in p], [])

    def test_bad_picks_stop_the_build(self):
        cases = {
            "bad asin": {**GOOD, "asin": "short"},
            "unknown occasion": {**GOOD, "occasions": ["no-such-day"]},
            "unknown recipient": {**GOOD, "recipients": ["nobody"]},
            "a price in the text": {**GOOD, "why": "3,000円で買えます。"},
            "missing field": {k: v for k, v in GOOD.items() if k != "why"},
        }
        for label, pick in cases.items():
            with self.subTest(label), self.assertRaises(BuildError):
                content.load(fixture_with([pick]))
        with self.assertRaises(BuildError):
            content.load(fixture_with([GOOD, GOOD]))                    # the same ASIN twice


if __name__ == "__main__":
    unittest.main()
