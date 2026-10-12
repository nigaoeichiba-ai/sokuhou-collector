"""atomou: nothing about where a date came from is shown on the cards (owner, 2026-10-12): no source table, no "出典", no check date; a link "公式ページ" only when the official page is known;
a day taken from two reports carries the badge "報道で確認"; every page says that a card's date may be wrong."""
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, review, skins  # noqa: E402
from tests.test_atomou_build import CFG, TODAY  # noqa: E402

DISC = "カードの日付は間違っていることがあります。"


def seed(title, **kw):
    it = {"title": title, "date": "2026-11-20", "kind": "発売", "category": "ゲーム・アニメ", "group": "趣味・ゲーム・アニメ", "subject": "テスト作品", "what": "新作の発売日", "place": "全国",
          "source_url": "https://news-a.example/x", "source_quote": "2026年11月20日発売", "checked_on": "2026-10-07", "verified": True, "precision": "day"}
    it.update(kw)
    return it


class Sources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "seed_t_2026-10-12.json").write_text(json.dumps([
                seed("報道だけの新作", basis="press", source_url2="https://news-b.example/x"), seed("報道と公式の新作", basis="press", source_url="https://news-a.example/y", source_url2="https://news-b.example/y", official_url="https://maker.example/news"),
                seed("公式の新作", basis="official", source_url="https://maker.example/z", source_quote="2026年11月20日発売")]), encoding="utf-8")
            (d / "blocklist.json").write_text('{"keywords": []}', encoding="utf-8")
            cls.entries, _ = catalog.build_catalog(TODAY, seed_dir=d)
        cls.ctx = build.Ctx(CFG, True, TODAY, cls.entries, skins.css())
        cls.by = {e["title"]: build.event_page(cls.ctx, e, True, cls.entries) for e in cls.entries}

    def test_the_catalogue_keeps_the_ground_of_a_day_but_never_publishes_the_source(self):
        by = {e["title"]: e for e in self.entries}
        self.assertEqual((by["報道だけの新作"]["basis"], by["公式の新作"]["basis"]), ("press", "official"))
        self.assertEqual(by["報道と公式の新作"]["official_url"], "https://maker.example/news")
        for e in catalog.public_json(self.entries):
            self.assertFalse({"source_url", "source_quote", "checked_on", "official_url", "basis"} & set(e))

    def test_a_day_page_shows_no_source_and_no_check_date(self):
        for title, page in self.by.items():
            for gone in ("出典", "確認日", "news-a.example", "掲載</dt>", "src-line"):
                self.assertNotIn(gone, page, f"{title}: {gone}")
        for k, v in self.pages.items():
            if k.startswith("e/") and isinstance(v, str):
                for gone in ("出典と確認日", "出典の文", "確認日</dt>", "出典: "):
                    self.assertNotIn(gone, v, k)

    def test_the_official_page_is_linked_only_when_it_is_known(self):
        self.assertNotIn("公式ページ</a>", self.by["報道だけの新作"])
        self.assertIn('href="https://maker.example/news"', self.by["報道と公式の新作"])
        self.assertIn('href="https://maker.example/z"', self.by["公式の新作"])
        self.assertIn("公式ページ</a>", self.by["公式の新作"])

    def test_the_badge_says_when_a_day_rests_on_reports(self):
        self.assertIn('vb-press" data-vbadge>報道で確認', self.by["報道だけの新作"])
        self.assertIn("公式の発表は、まだ確かめていません", self.by["報道だけの新作"])
        self.assertIn('vb-ok" data-vbadge>確認済', self.by["公式の新作"])

    def test_every_page_says_a_date_may_be_wrong(self):
        for k in ("index.html", "my/index.html", "add/index.html", "search/index.html"):
            self.assertIn(DISC, self.pages[k], k)
        for title, page in self.by.items():
            self.assertIn(DISC, page, title)

    def test_the_review_copy_follows_the_same_rule(self):
        pages = review.build_pages(CFG, TODAY)
        events = {k: v for k, v in pages.items() if k.startswith("e/") and isinstance(v, str)}
        self.assertTrue(events)
        for k, v in events.items():
            for gone in ("出典と確認日", "出典の文", "確認日</dt>", "出典: "):
                self.assertNotIn(gone, v, k)
            self.assertIn(DISC, v, k)
        for k in ("index.html", "about/index.html"):
            self.assertIn(DISC, pages[k], k)
            self.assertNotIn("出典と確認日を", pages[k], k)

    def test_no_screen_promises_a_source_and_a_check_date_any_more(self):
        pat = re.compile(r"出典と確認日|出典つき|出典の公式ページ")
        for k, v in self.pages.items():
            if isinstance(v, str) and (k.endswith(".html") or k.endswith(".js")):
                self.assertIsNone(pat.search(v), k)
        for js in (ROOT / "sites" / "atomou" / "assets").glob("*.js"):
            self.assertIsNone(pat.search(js.read_text(encoding="utf-8")), js.name)


if __name__ == "__main__":
    unittest.main()
