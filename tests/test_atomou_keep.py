"""atomou: a day people look for long after it (a big event, a day in history) can be kept; a short notice is hidden 30 days after it; a year-only date makes a card of year precision."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog, seedcheck  # noqa: E402

TODAY = date(2026, 10, 10)


def item(title, day, **kw):
    it = {"title": title, "date": day, "date_end": None, "precision": "day", "kind": "開催", "group": "スポーツ", "category": "五輪", "subject": "オリンピック", "what": "大会の開幕日",
          "place": "全国", "region": "全国", "source_url": "https://official.example/x", "source_quote": "2024年7月26日", "checked_on": "2026-10-10", "sensitivity": "none", "ad_ok": True,
          "son_toku": False, "note": "", "verified": True}
    it.update(kw)
    return it


def build(items):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "seed_keep_2026-10-10.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return catalog.build_catalog(TODAY, Path(d))


class Keeping(unittest.TestCase):
    def test_an_old_day_is_hidden_unless_it_is_kept(self):
        entries, rejects = build([item("昔の短い知らせ", "2026-05-01"), item("パリ五輪の開会式", "2024-07-26", keep=True)])
        self.assertEqual([e["title"] for e in entries], ["パリ五輪の開会式"])
        self.assertEqual(rejects["終了して30日超"], 1)
        self.assertEqual((entries[0]["status"], entries[0]["keep"]), ("ended", True))

    def test_a_kept_past_day_is_still_indexable_and_public_and_a_short_one_is_not_kept(self):
        entries, _ = build([item("パリ五輪の開会式", "2024-07-26", keep=True), item("先月の知らせ", "2026-09-20")])
        ids = catalog.indexable_ids(entries, TODAY, date(2026, 10, 1), per_week=50)
        by = {e["title"]: e for e in entries}
        self.assertIn(by["パリ五輪の開会式"]["id"], ids)             # people search for it after it has passed
        self.assertNotIn(by["先月の知らせ"]["id"], ids)               # an ended short notice is not indexed
        self.assertTrue(all("keep" in p for p in catalog.public_json(entries)))

    def test_a_year_only_date_is_a_card_of_year_precision(self):
        entries, _ = build([item("ワールドカップ2030", "2030-01-01", precision="year", keep=True, source_quote="2030年")])
        self.assertEqual(entries[0]["precision"], "year")

    def test_the_checker_takes_a_kept_day_from_any_time_and_a_year_quote_with_the_year(self):
        c = {"title": "日本万国博覧会の開幕", "date": "1970-03-15", "kind": "開催", "group": "お金・税金・制度", "category": "万博", "subject": "大阪万博1970", "what": "万博の開幕日",
             "place": "大阪府", "source_url": "https://official.example/expo70", "source_quote": "1970年3月15日", "keep": True}
        pages = {"https://official.example/expo70": "日本万国博覧会は 1970年3月15日 に開幕しました"}
        ok, bad = seedcheck.check([c], TODAY, existing=set(), page_of=pages.get, render_of=lambda u: "")
        self.assertEqual((len(ok), bad), (1, []))
        ok, bad = seedcheck.check([{**c, "keep": False}], TODAY, existing=set(), page_of=pages.get, render_of=lambda u: "")
        self.assertEqual(bad[0][1], "date outside window")
        y = {**c, "title": "万博の年", "date": "2030-01-01", "precision": "year", "source_quote": "2030年に開催", "source_url": "https://official.example/y"}
        ok, bad = seedcheck.check([y], TODAY, existing=set(), page_of={"https://official.example/y": "次の大会は 2030年に開催されます"}.get, render_of=lambda u: "")
        self.assertEqual((len(ok), bad), (1, []))


if __name__ == "__main__":
    unittest.main()
