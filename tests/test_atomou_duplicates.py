"""atomou: one event is one card.  The same event listed under two names on the same date (「日商簿記検定 第174回」と「日商簿記検定 第174回(統一試験)」、「東京マラソン2027」と「東京マラソン2027 開催」)
is taken out through data/atomou/merged.json; this test fails when a daily research run adds a new pair that the list does not cover, and says which two.
The check itself is tried on the pairs that were found on 2026-11-14 (a negative test: it must find them) and on look-alikes that are different events (it must not merge them)."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog  # noqa: E402


def card(title: str, d: str = "2026-11-15") -> dict:
    return {"title": title, "date": d, "id": title}


class DupKey(unittest.TestCase):
    def test_it_finds_the_pairs_of_2026_11_14(self):
        pairs = [
            ("日商簿記検定 第174回", "日商簿記検定 第174回(統一試験)"),
            ("東京マラソン2027", "東京マラソン2027 開催"),
            ("巨人 秋季キャンプ 2026", "巨人 秋季キャンプ2026 開始"),
            ("2027年用年賀はがきの発売", "2027年用年賀はがきの販売開始"),
            ("第105回全国高校サッカー選手権大会 開幕", "第105回全国高等学校サッカー選手権大会 開幕(予想)"),
            ("コミックマーケット109", "コミックマーケット109(3日間)"),
            ("公認会計士試験 令和9年 論文式試験", "公認会計士試験 論文式試験"),
            ("iPhone Duo", "iPhone Duo 販売開始"),
        ]
        for a, b in pairs:
            groups = catalog.duplicate_groups([card(a), card(b)])
            self.assertEqual(len(groups), 1, f"not found: {a} / {b}")

    def test_it_keeps_different_events_apart(self):
        different = [
            ("慶應義塾大学 商学部 一般選抜 合格発表", "慶應義塾大学 文学部 一般選抜 合格発表"),
            ("早稲田大学 先進理工学部 一般選抜 試験", "早稲田大学 創造理工学部 一般選抜 試験"),
            ("第35回きゅう師国家試験 合格発表", "第35回はり師国家試験 合格発表"),
            ("柏市 固定資産税・都市計画税 第4期分の納期限", "横浜市 固定資産税・都市計画税 第4期分の納期限"),
        ]
        for a, b in different:
            self.assertEqual(catalog.duplicate_groups([card(a), card(b)]), [], f"merged by mistake: {a} / {b}")

    def test_the_same_name_on_two_dates_is_two_cards(self):
        self.assertEqual(catalog.duplicate_groups([card("東京マラソン2027", "2027-03-07"), card("東京マラソン2027 開催", "2027-03-08")]), [])


class TheData(unittest.TestCase):
    def test_no_event_is_listed_twice(self):
        entries, _ = catalog.build_catalog(date.today())
        groups = catalog.duplicate_groups(entries)
        names = ["  / ".join(f"{e['title']} ({e['id']})" for e in g) + f"  [{g[0]['date']}]" for g in groups]
        self.assertEqual(groups, [], "the same event twice; add it to data/atomou/merged.json ({date, drop, keep}):\n" + "\n".join(names))

    def test_a_card_taken_out_has_a_redirect_to_the_one_that_stays(self):
        entries, _ = catalog.build_catalog(date.today())
        moved = catalog.merged_redirects(entries)
        ids = {e["id"] for e in entries}
        self.assertGreaterEqual(len(moved), 40)
        for a, b in moved.items():
            self.assertNotIn(a, ids, "the old card is still built")
            self.assertIn(b, ids, "the redirect leads nowhere")


if __name__ == "__main__":
    unittest.main()
