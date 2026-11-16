"""trend: トップの「今日やること」を、記事の `todo`(期限つき)から毎回選ぶ仕組み(sites/trend/homepage.py の pick_todo)。
期限切れの枠が出ると落ちる(負例)・期限の近い順・足りなければ期限のない予備で埋める・壊れた `todo` はビルドを止める。"""
from __future__ import annotations

import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "sites" / "trend"
sys.path.insert(0, str(SITE_DIR))
import homepage as hp  # noqa: E402

FB = [("予備1", "/fb1/", "予備の見出し1", "予備の説明1"), ("予備2", "/fb2/", "予備の見出し2", "予備の説明2"), ("予備3", "/fb3/", "予備の見出し3", "予備の説明3")]


def page(path, deadline, badge="バッジ"):
    return {"path": path, "todo": {"deadline": deadline, "badge": badge + path, "title": "見出し" + path, "text": "説明" + path}}


class TestPickTodo(unittest.TestCase):
    def test_earliest_deadline_first_and_only_three(self):
        content = [page("/d/", "2026-11-30"), page("/a/", "2026-11-16"), page("/c/", "2026-11-25"), page("/b/", "2026-11-20"), {"path": "/x/"}]
        got = hp.pick_todo(content, FB, today=datetime.date(2026, 11, 16))
        self.assertEqual([g[1] for g in got], ["/a/", "/b/", "/c/"])

    def test_the_deadline_day_itself_is_still_open_and_the_next_day_is_not(self):
        content = [page("/a/", "2026-11-16")]
        self.assertEqual(hp.pick_todo(content, FB, today=datetime.date(2026, 11, 16))[0][1], "/a/")
        nxt = hp.pick_todo(content, FB, today=datetime.date(2026, 11, 17))
        self.assertNotIn("/a/", [g[1] for g in nxt])

    def test_negative_an_expired_item_never_appears_and_the_fallback_fills_up(self):
        """期限切れの枠が出ると落ちる検査: 全部が期限切れなら、予備の3つだけ。"""
        content = [page("/a/", "2026-11-10"), page("/b/", "2026-11-12"), page("/c/", "2026-11-14")]
        got = hp.pick_todo(content, FB, today=datetime.date(2026, 11, 16))
        self.assertEqual([g[1] for g in got], ["/fb1/", "/fb2/", "/fb3/"])
        self.assertEqual(len(got), 3)

    def test_mixed_open_items_then_fallback(self):
        content = [page("/a/", "2026-11-16"), page("/old/", "2026-11-01")]
        got = hp.pick_todo(content, FB, today=datetime.date(2026, 11, 16))
        self.assertEqual([g[1] for g in got], ["/a/", "/fb1/", "/fb2/"])

    def test_a_broken_todo_stops_the_build(self):
        with self.assertRaises(SystemExit):
            hp.pick_todo([{"path": "/z/", "todo": {"deadline": "2026-13-45", "badge": "b", "title": "t", "text": "x"}}], FB, today=datetime.date(2026, 11, 16))
        with self.assertRaises(SystemExit):
            hp.pick_todo([{"path": "/z/", "todo": {"deadline": "2026-11-20", "badge": "b", "title": "t"}}], FB, today=datetime.date(2026, 11, 16))

    def test_the_real_articles_todo_data_is_valid_and_has_enough_open_items_today(self):
        """実際の記事の `todo` が、全部、日付として読め、キーがそろっていること(壊れたデータの検出)。"""
        items = []
        for f in (SITE_DIR / "content").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("todo"):
                for k in hp.TODO_KEYS:
                    self.assertTrue(d["todo"].get(k), (f.name, k))
                datetime.date.fromisoformat(d["todo"]["deadline"])
                items.append(d["todo"]["deadline"])
        self.assertGreaterEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
