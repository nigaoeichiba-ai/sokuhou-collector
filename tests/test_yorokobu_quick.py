"""The 贈る前の早見表: amounts, timing, noshi and cautions with their sources, on the occasion pages and as a note on the pair pages."""
import copy
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": "amazonmacs-22", "adsense_pub_id": None}
TODAY = date(2026, 5, 3)


def with_etiquette(edit):
    """Load the fixture content with etiquette.json edited by `edit(data)`."""
    tmp = tempfile.mkdtemp()
    dst = Path(tmp) / "c"
    shutil.copytree(FIX, dst)
    data = json.loads((FIX / "etiquette.json").read_text(encoding="utf-8"))
    edit(data)
    (dst / "etiquette.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return dst


class QuickSheetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_occasion_page_starts_with_the_sheet_and_names_its_sources(self):
        html = self.read("occasion/mothers-day/index.html")
        self.assertIn('id="quick"', html)
        self.assertIn("母の日の、贈る前の早見表", html)
        self.assertIn("3,000〜5,000円", html)
        self.assertIn("母の日/感謝", html)                                   # the noshi wording
        self.assertIn("5月の第2日曜日に届くよう", html)                        # the timing, in place of the generic one
        self.assertNotIn("贈る時期の目安", html)
        self.assertIn('href="https://example.com/c"', html)
        self.assertIn('rel="nofollow noopener"', html)
        self.assertIn("金額や習慣は目安です", html)
        self.assertLess(html.index('id="quick"'), html.index("選ぶポイント"))

    def test_an_occasion_with_no_fixed_amount_says_so_instead_of_inventing_one(self):
        html = self.read("occasion/birthday/index.html")
        self.assertIn("誕生日に決まった相場はありません", html)
        self.assertNotIn('class="quick-table"', html)
        self.assertIn("のしは、付けなくてもかまいません", html)

    def test_an_occasion_without_data_keeps_its_old_page(self):
        def only_mothers_day(d): d["occasions"] = d["occasions"][1:]
        c = content.load(with_etiquette(only_mothers_day))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(c, self.items, CFG, out, release=True, today=TODAY)
            html = (out / "occasion/birthday/index.html").read_text(encoding="utf-8")
            self.assertNotIn('id="quick"', html)
            self.assertIn("贈る時期の目安", html)
            self.assertNotIn('class="quick-pair"', (out / "gift/birthday-boyfriend/index.html").read_text(encoding="utf-8"))

    def test_a_pair_page_gets_the_amount_for_its_recipient_with_a_link_to_the_sheet(self):
        html = self.read("gift/mothers-day-mother/index.html")
        self.assertIn('class="quick-pair"', html)
        self.assertIn("3,000〜5,000円", html)
        self.assertIn('/occasion/mothers-day/#quick', html)
        self.assertNotIn('class="quick-pair"', self.read("gift/birthday-boyfriend/index.html"))      # no amount for that occasion: nothing is invented

    def test_the_built_pages_pass_the_site_checker(self):
        self.assertEqual([p for p in sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",)) if "occasion" in p or "gift" in p], [])

    def test_bad_data_stops_the_build(self):
        def one_source(d): d["occasions"][1]["sources"] = d["occasions"][1]["sources"][:1]
        def bad_range(d): d["occasions"][1]["budget"][0]["range"] = "3千円ほど"
        def low_with_amount(d): d["occasions"][1]["confidence"] = "low"
        def no_noshi_words(d): d["occasions"][1]["noshi"] = {"applicable": True}
        def unknown(d): d["occasions"][0]["slug"] = "no-such-day"
        def http_source(d): d["occasions"][1]["sources"][0]["url"] = "http://example.com/c"
        for edit in (one_source, bad_range, low_with_amount, no_noshi_words, unknown, http_source):
            with self.subTest(edit=edit.__name__):
                with self.assertRaises(BuildError):
                    content.load(with_etiquette(edit))

    def test_the_amount_for_a_recipient_is_found_by_the_relation_word(self):
        e = self.c["etiquette"]["mothers-day"]
        self.assertEqual(build.budget_for(e, "mother")["range"], "3,000〜5,000円")
        self.assertEqual(build.budget_for(e, "in-laws")["to"], "義父母")
        self.assertIsNone(build.budget_for(e, "colleague"))

    def test_the_real_etiquette_data_loads_is_written_calmly_and_every_amount_has_two_sources(self):
        from sites.yorokobu import quality
        real = content.load()["etiquette"]
        self.assertGreaterEqual(len(real), 4)
        for slug, e in real.items():
            texts = [e["timing"], e["noshi"].get("note", ""), *e["cautions"], e.get("return_gift") or "", e.get("budget_note") or "", *[r.get("note", "") for r in e.get("budget", [])]]
            self.assertEqual(quality.language_problems("".join(t if t.endswith("。") or not t else t for t in texts), slug), [], slug)
            self.assertGreaterEqual(len(e["sources"]), 2, slug)
            for r in e.get("budget", []):
                self.assertIn(e["confidence"], ("high", "medium"), slug)


if __name__ == "__main__":
    unittest.main()
