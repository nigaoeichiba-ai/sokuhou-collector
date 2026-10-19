"""Weekly review 2026-10-19 (AdSense answered "low-value content" for saichin; yorokobu has 569 pages, most of them lists of products): the editors' own words on the list pages,
analyses made from the site's own data in the data room, the operator page with how the site is made / corrections / history, and no AdSense tag on hubs, forms and the error page."""
import json
import re
import tempfile
import unittest
from unittest import mock
from datetime import date
from pathlib import Path

from sites.yorokobu import aboutextra, build, content, dataroom, numberlists, ownanalysis, ranking
from tests.yorokobu_data import rich_boyfriend

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
ROOT = Path(__file__).resolve().parents[1]
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "社名テスト商会", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": None, "adsense_pub_id": "pub-1234567890123456"}
TAG = "pagead2.googlesyndication.com"
MADE_BY = re.compile(r"生成AI|AI(?:の)?(?:支援|を使|で作|が作|による)|AI支援|人工知能|自動(?:で|的に)?(?:作成|生成|執筆)|機械(?:が|で|的に)(?:作|書|生成)")


class NotesTest(unittest.TestCase):
    notes = json.loads((ROOT / "sites" / "yorokobu" / "content" / "page_notes.json").read_text(encoding="utf-8"))

    def test_every_ranking_page_numbers_list_and_budget_band_has_a_note(self):
        self.assertEqual({s["slug"] for s in ranking.all_segments()} - set(self.notes["ranking"]), set())
        self.assertEqual({"cheap-and-loved", "hidden-gems", "reviews-1000", "reviews-3000", "reviews-10000"} - set(self.notes["numbers"]), set())
        self.assertEqual({"under3000", "3000-5000", "5000-10000", "10000-20000", "over20000"} - set(self.notes["budget"]), set())

    def test_a_note_has_three_parts_of_its_own_and_none_is_repeated_on_another_page(self):
        seen: dict[str, str] = {}
        for kind, d in self.notes.items():
            if kind.startswith("_"):
                continue
            for slug, n in d.items():
                self.assertEqual(set(n), {"why", "scene", "care"}, f"{kind}/{slug}")
                for part, text in n.items():
                    self.assertGreaterEqual(len(text), 10 if part == "scene" else 25, f"{kind}/{slug}/{part}")
                    self.assertNotIn(text, seen, f"{kind}/{slug}/{part} repeats {seen.get(text)}")
                    seen[text] = f"{kind}/{slug}/{part}"

    def test_a_note_carries_no_shop_text_or_company_name(self):
        text = json.dumps(self.notes, ensure_ascii=False)
        for bad in ("株式会社", "http", "円OFF", "送料無料"):
            self.assertNotIn(bad, text)

    def test_the_block_is_html_and_empty_for_an_unknown_page(self):
        html = build.note_block("ranking", "g-bag")
        self.assertIn('class="editor-note"', html)
        for label in ("見る価値", "渡す場面", "注意したい点"):
            self.assertIn(label, html)
        self.assertEqual(build.note_block("ranking", "no-such-page"), "")


class OperatorPageTest(unittest.TestCase):
    def test_the_history_is_valid_newest_first_and_names_the_corrections(self):
        es = aboutextra.entries()
        self.assertEqual(aboutextra.problems(es), [])
        self.assertTrue(any(e["kind"] == "訂正" for e in es))

    def test_the_check_would_catch_a_bad_history(self):
        bad = [{"date": "2026-10-01", "kind": "更新", "text": "a"}, {"date": "2026-10-02", "kind": "変更", "text": ""}, {"date": "xx", "kind": "更新", "text": "b"}]
        self.assertEqual(len(aboutextra.problems(bad)), 4)

    def test_only_the_operator_page_gets_the_block(self):
        self.assertEqual(aboutextra.inject("<h1>プライバシーポリシー</h1><h2>免責事項</h2>"), "<h1>プライバシーポリシー</h1><h2>免責事項</h2>")
        out = aboutextra.inject("<h1>運営者情報</h1><dl></dl><h2>免責事項</h2>x")
        self.assertLess(out.index("更新の履歴"), out.index("<h2>免責事項</h2>"))


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = rich_boyfriend(json.loads((FIX / "items.json").read_text(encoding="utf-8")))
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def test_the_operator_page_says_how_the_site_is_made_how_corrections_are_told_and_its_history(self):
        t = self.read("about/index.html")
        for word in ("編集方針と作り方", "訂正のお知らせ", 'id="history"', "更新の履歴", "2026年10月19日"):
            self.assertIn(word, t)
        self.assertEqual(t.count("社名テスト商会"), 1)                               # the company is named on its operator line only

    def test_the_policy_page_says_where_corrections_are_listed(self):
        self.assertIn('href="/about/#history"', self.read("policy/index.html"))

    def test_no_page_says_it_was_made_with_ai_or_by_machine(self):
        # owner, 2026-10-19: the site does not say "made with AI support", "made automatically" or "made by a machine" anywhere
        bad = [f.relative_to(self.root).as_posix() for f in self.root.rglob("*.html") if MADE_BY.search(f.read_text(encoding="utf-8"))]
        self.assertEqual(bad, [])

    def test_the_check_would_catch_such_a_sentence(self):
        for s in ("文章の下書きには生成AIを使っています。", "AIの支援を受けて作成しました", "自動で作成されたページ", "機械が作った文章", "AI支援"):
            self.assertTrue(MADE_BY.search(s), s)
        self.assertFalse(MADE_BY.search("回答は120日たつと自動で消えます。"))

    def test_hubs_forms_and_the_error_page_have_no_ad_tag_and_the_content_pages_keep_it(self):
        for rel in ("theme/index.html", "for/index.html", "occasion/index.html", "contact/index.html", "404.html"):
            if (self.root / rel).exists():
                self.assertNotIn(TAG, self.read(rel), rel)
        kept = [p for p in ("about/index.html", "privacy/index.html") if (self.root / p).exists()]
        self.assertTrue(kept)
        for rel in kept:
            self.assertIn(TAG, self.read(rel), rel)
        pages = list((self.root / "gift").glob("*/index.html")) + list((self.root / "theme").glob("*/index.html"))
        self.assertTrue(pages)
        self.assertTrue(all(TAG in p.read_text(encoding="utf-8") for p in pages))

    def test_the_stripper_would_catch_a_hub_that_kept_the_tag(self):
        tag = f'<script async src="https://{TAG}/pagead/js/adsbygoogle.js?client=ca-pub-1" crossorigin="anonymous"></script>\n'
        pages = {"theme/index.html": f"<head>{tag}</head>", "gift/x/index.html": f"<head>{tag}</head>", "404.html": f"<head>{tag}</head>"}
        self.assertEqual(build.strip_ads(pages), 2)
        self.assertNotIn(TAG, pages["theme/index.html"])
        self.assertNotIn(TAG, pages["404.html"])
        self.assertIn(TAG, pages["gift/x/index.html"])


def item(code, price):
    return {"code": code, "name": code, "price": price, "url": "u", "image": "i", "shop": "s", "shop_code": code, "reviews": 10, "rating": 4.5, "available": True,
            "free_shipping": True, "gift": False, "appoint": False}


class AnalysisTest(unittest.TestCase):
    def d_kinds(self, kinds=6, per=10):
        ideas = [{"label": f"k{k}", "type": f"種類{k}", "must": [], "items": [item(f"k{k}-{i}", 1000 * (k + 1) + i * 100) for i in range(per)]} for k in range(kinds)]
        return {"pairs": {"p": {"ideas": ideas, "tiers": {}}}, "fetched_label": "2026年10月19日 7:00", "site_name": "x"}

    def test_kind_prices_states_the_highest_and_lowest_kind_and_publishes_no_product(self):
        r = ownanalysis.kind_prices(self.d_kinds())
        path, h1, lead, body, crumb, finding = r
        self.assertEqual(path, "/data/kind-prices/")
        self.assertIn("種類5", finding)                                  # the dearest kind
        self.assertIn("どうやって数えたか", body)
        self.assertIn("見かたの注意", body)
        self.assertNotIn("k0-1", body)                                   # no product code or name

    def test_kind_prices_makes_nothing_from_too_little_data(self):
        self.assertIsNone(ownanalysis.kind_prices(self.d_kinds(kinds=3)))
        self.assertIsNone(ownanalysis.kind_prices(self.d_kinds(per=3)))

    def seg(self, slug, kind, n=12, new=2, stay=5, days=6):
        return {"slug": slug, "label": slug, "kind": kind, "date": "2026-10-19", "items": [item(f"{slug}{i}", 2000) for i in range(n)], "days": days,
                "n_entered": new, "n_stay": stay, "thin": False}

    def d_rank(self, days=6):
        segs = {f"f{i}": self.seg(f"f{i}", "people", new=i, days=days) for i in range(6)}
        segs.update({f"g-{i}": self.seg(f"g-{i}", "genre", stay=i, days=days) for i in range(6)})
        return {"ranking": {"date": "2026-10-19", "segments": segs, "order": list(segs), "risers": []}}

    def test_turnover_names_the_extremes_with_counts_only(self):
        path, h1, lead, body, crumb, finding = ownanalysis.ranking_turnover(self.d_rank())
        self.assertEqual(path, "/data/ranking-turnover/")
        self.assertIn("f5", finding)                                      # the list with the most new products
        self.assertIn("記録は6日分", body)
        self.assertNotIn("f50", body)                                      # no product code

    def test_turnover_needs_three_days_of_records(self):
        self.assertIsNone(ownanalysis.ranking_turnover(self.d_rank(days=2)))
        self.assertIsNone(ownanalysis.ranking_turnover({}))

    def test_both_analyses_are_registered_in_the_data_room_and_its_hub_says_how_numbers_are_made(self):
        self.assertIn(dataroom.ranking_turnover, dataroom.BUILDERS)
        self.assertIn(dataroom.kind_prices, dataroom.BUILDERS)
        d = {**self.d_kinds(), "c": {"surveys": {}, "pairs": [], "occasions": [], "recipients": []}, "site_url": CFG["site_url"]}
        with mock.patch.object(dataroom, "results", lambda d: [ownanalysis.kind_prices(d)]):
            pages = dataroom.build_pages(d, CFG, False)
        self.assertIn("data/kind-prices/index.html", pages)
        self.assertIn("このデータ室の数字について", pages["data/index.html"])


if __name__ == "__main__":
    unittest.main()
