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
        self.assertEqual((e["group"], e["weekday"], e["status"], e["ad_ok"], e["quiet"]), ("学校・資格", "金", "active", True, False))
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
        self.assertEqual(entries[0]["group"], "学校・資格")

    def test_check_date_in_the_future_is_rejected(self):
        entries, rejects = build([item(checked_on="2026-12-01")])
        self.assertEqual((entries, rejects["日付が不正"]), ([], 1))

    def test_duplicates_are_dropped(self):
        entries, rejects = build([item(), item(title="同じ出典・同じ日付")])
        self.assertEqual((len(entries), rejects["重複"]), (1, 1))

    def test_the_same_event_listed_in_two_seed_files_appears_once(self):
        # the marathons were in the regional and the sports file (2026-10-10); two pages with one text are two doorways to one event
        entries, rejects = catalog.build_catalog(date(2026, 10, 10))
        days = [(e["title"], e["date"]) for e in entries]
        self.assertEqual(len(days), len(set(days)))
        self.assertGreater(rejects["重複(同名同日)"], 0)

    def test_every_genre_has_events_and_every_event_has_a_known_genre(self):
        entries, _ = catalog.build_catalog(date(2026, 10, 10))
        used = {e["group"] for e in entries}
        self.assertEqual(used, set(catalog.GROUPS))
        self.assertEqual(len(catalog.GROUPS), 10)

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


BAD_SUBJECTS = ("その他", "地域", "全国")  # words that say nothing about what the topic is


def label_problems(rows) -> list[str]:
    """What a card must show so that anybody can tell what the day is: a subject (2-10 chars, never a vague word), what the day is (4-16 chars)
    and a place that is empty or short.  `rows` are catalogue entries or raw seed items."""
    out = []
    for r in rows:
        title, s, w, p = r.get("title", "?"), r.get("subject") or "", r.get("what") or "", r.get("place")
        if not 2 <= len(s) <= 10:
            out.append(f"{title}: subject の長さ {len(s)} ({s!r})")
        if any(b in s for b in BAD_SUBJECTS):
            out.append(f"{title}: subject が曖昧 ({s!r})")
        if not 4 <= len(w) <= 16:
            out.append(f"{title}: what の長さ {len(w)} ({w!r})")
        if p is None or len(p) > 30:
            out.append(f"{title}: place が長すぎる/無い ({p!r})")
    return out


class CardLabels(unittest.TestCase):
    def test_every_real_seed_item_says_what_it_is(self):
        raw = [it for _, it in catalog.load_seeds()]
        self.assertGreater(len(raw), 380)
        self.assertEqual(label_problems(raw), [])  # all of them, including items that are not published yet

    def test_every_published_entry_has_clear_labels(self):
        entries, _ = catalog.build_catalog(TODAY)
        self.assertEqual(label_problems(entries), [])
        self.assertEqual(label_problems(catalog.public_json(entries)), [])  # the browser gets the same three fields

    def test_the_check_catches_vague_or_bad_labels(self):
        bad = [item(title="曖昧1", subject="その他", what="試験の日", place="全国"), item(title="曖昧2", subject="おでかけ・地域", what="お祭りの日", place=""),
               item(title="曖昧3", subject="全国", what="試験の日", place=""), item(title="短い1", subject="資", what="試験の日", place=""),
               item(title="短い2", subject="資格", what="開催", place=""), item(title="長い1", subject="資格", what="試験の日", place="あ" * 31),
               item(title="長い2", subject="あ" * 11, what="試験の日", place=""), item(title="長い3", subject="資格", what="あ" * 17, place=""),
               item(title="空", subject="", what="", place="")]
        problems = label_problems(bad)
        for t in ("曖昧1", "曖昧2", "曖昧3", "短い1", "短い2", "長い1", "長い2", "長い3", "空"):
            with self.subTest(title=t):
                self.assertTrue(any(line.startswith(t + ":") for line in problems), problems)
        entries, _ = build([item(subject="その他", what="試験の日", place="全国")])  # and the same through the builder
        self.assertTrue(label_problems(entries))

    def test_labels_pass_through_to_entries_and_public_json(self):
        entries, _ = build([item(subject="簿記検定", what="申込の締切", place="京都府(京都商工会議所)", title_note="直す案")])
        e = entries[0]
        self.assertEqual((e["subject"], e["what"], e["place"]), ("簿記検定", "申込の締切", "京都府(京都商工会議所)"))
        pub = catalog.public_json(entries)[0]
        self.assertEqual((pub["subject"], pub["what"], pub["place"]), ("簿記検定", "申込の締切", "京都府(京都商工会議所)"))
        self.assertNotIn("title_note", pub)  # editorial notes never reach assets/catalog.json
        self.assertNotIn("title_note", e)

    def test_items_without_the_fields_fall_back_to_category_kind_region(self):
        e = build([item()])[0][0]
        self.assertEqual((e["subject"], e["what"], e["place"]), ("資格", "締切", "全国"))
        e = build([item(category="その他", region="地域")])[0][0]  # "その他" -> the group; "地域" says nothing -> empty
        self.assertEqual((e["subject"], e["place"]), ("学校・資格", ""))
        e = build([item(place="")])[0][0]  # an explicit empty place is kept (unknown), it does not fall back to the region
        self.assertEqual(e["place"], "")

    def test_subject_and_what_are_searchable_tags(self):
        e = build([item(title="第39期竜王戦七番勝負 第1局", subject="将棋", what="タイトル戦(竜王戦)第1局", category="その他")])[0][0]
        self.assertIn("将棋", e["tags"])  # the title never says 将棋
        self.assertIn("タイトル戦(竜王戦)第1局", e["tags"])
        raw = [it for _, it in catalog.load_seeds() if it.get("subject") == "将棋"]
        self.assertGreaterEqual(len(raw), 5)
        entries, _ = catalog.build_catalog(TODAY)
        shogi = [e for e in entries if e["subject"] == "将棋"]
        self.assertGreaterEqual(len(shogi), 5)
        self.assertTrue(all("将棋" in e["tags"] for e in shogi))
        self.assertTrue(any("将棋" not in e["title"] for e in shogi))  # found although the title does not say it


if __name__ == "__main__":
    unittest.main()
