"""atomou: the catalogue builder rejects what must never reach a page, keeps ids stable and gates indexing."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog  # noqa: E402

TODAY = date(2026, 10, 8)


def item(**kw):
    base = {"title": "テストの試験 申込締切", "date": "2026-11-20", "precision": "day", "kind": "締切", "category": "資格", "region": "全国",
            "son_toku": True, "source_url": "https://example.go.jp/exam", "source_quote": "11月20日まで", "checked_on": "2026-10-08",
            "verified": True, "sensitivity": "none", "ad_ok": True}
    base.update(kw)
    return base


def build(items, block=None, name="seed_exams_2026-10-08.json"):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / name).write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return catalog.build_catalog(TODAY, p, block or {"keywords": ["ヒトラー"]})


class CatalogRules(unittest.TestCase):
    def test_good_item_is_accepted_with_public_fields(self):
        entries, rejects = build([item()])
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual((e["group"], e["weekday"], e["status"], e["ad_ok"], e["quiet"]), ("試験・資格", "金", "active", True, False))
        self.assertEqual(sum(rejects.values()), 0)
        self.assertNotIn("note", catalog.public_json(entries)[0])  # nothing internal leaks into assets/catalog.json

    def test_negative_cases_never_reach_a_page(self):
        bad = {
            "未確認": item(verified=False),
            "必須の項目なし": item(source_url=""),
            "出典が https でない": item(source_url="http://example.go.jp/x"),
            "日付が不正": item(date="2026-13-40"),
            "終了して30日超": item(date="2026-08-01"),
            "除外リスト": item(title="ヒトラーの記念日"),
        }
        for reason, it in bad.items():
            with self.subTest(reason=reason):
                entries, rejects = build([it])
                self.assertEqual(entries, [])
                self.assertEqual(rejects[reason], 1)
        # an unknown category in a file that has no default genre cannot be placed on any page
        entries, rejects = build([item(category="不明の種類")], name="seed_zzz_2026-10-08.json")
        self.assertEqual((entries, rejects["ジャンル不明"]), ([], 1))
        # ... while a known file gives its items the file's genre
        entries, _ = build([item(category="その他")])
        self.assertEqual(entries[0]["group"], "試験・資格")

    def test_check_date_in_the_future_is_rejected(self):
        entries, rejects = build([item(checked_on="2026-12-01")])
        self.assertEqual((entries, rejects["日付が不正"]), ([], 1))

    def test_duplicates_are_dropped(self):
        entries, rejects = build([item(), item(title="同じ出典・同じ日付")])
        self.assertEqual((len(entries), rejects["重複"]), (1, 1))

    def test_id_does_not_depend_on_the_title(self):
        a, _ = build([item()])
        b, _ = build([item(title="タイトルを直した")])
        self.assertEqual(a[0]["id"], b[0]["id"])
        c, _ = build([item(date="2026-11-21")])
        self.assertNotEqual(a[0]["id"], c[0]["id"])

    def test_sensitive_items_are_quiet_and_never_ad_ok(self):
        for sens in ("grief", "disaster", "medical", "legal"):
            e, _ = build([item(sensitivity=sens, ad_ok=True)])
            self.assertTrue(e[0]["quiet"], sens)
            self.assertFalse(e[0]["ad_ok"], sens)

    def test_money_items_are_not_quiet_but_follow_ad_ok(self):
        e, _ = build([item(sensitivity="money", ad_ok=False)])
        self.assertFalse(e[0]["quiet"])
        self.assertFalse(e[0]["ad_ok"])

    def test_old_check_and_ended_status(self):
        e, _ = build([item(checked_on="2026-06-01")])
        self.assertEqual(e[0]["status"], "old_checked")
        e, _ = build([item(date="2026-10-01")])
        self.assertEqual(e[0]["status"], "ended")  # finished a week ago: still shown as "もう○日", but not indexed
        e, _ = build([item(date="2026-10-01", date_end="2026-10-20")])
        self.assertEqual(e[0]["status"], "active")  # a period that has not finished

    def test_indexing_is_gated_by_lead_time_and_weekly_allowance(self):
        its = [item(date=f"2026-10-{10 + i:02d}", source_url=f"https://example.go.jp/{i}") for i in range(12)]
        entries, _ = build(its)
        launch = TODAY
        ids = catalog.indexable_ids(entries, TODAY, launch, per_week=5)
        self.assertEqual(len(ids), 5)  # week 1 allows only 5 although 12 are eligible
        soonest = {e["id"] for e in entries[:5]}
        self.assertEqual(ids, soonest)
        self.assertEqual(len(catalog.indexable_ids(entries, date(2026, 10, 15), launch, per_week=5)), 10)
        far = build([item(date="2027-04-01")])[0]  # lead time (45 days before a deadline) has not begun
        self.assertEqual(catalog.indexable_ids(far, TODAY, launch), set())

    def test_the_real_seed_files_load(self):
        entries, rejects = catalog.build_catalog(TODAY)
        self.assertGreater(len(entries), 200)
        self.assertTrue(all(e["source_url"].startswith("https://") for e in entries))
        self.assertTrue(all(e["status"] != "ended" or e["date"] >= "2026-09-08" for e in entries))
        self.assertEqual(len({e["id"] for e in entries}), len(entries))


if __name__ == "__main__":
    unittest.main()
