"""trend: 提携の条件で、広告を置くページの title と meta(description)に広告主の名前を入れてはいけない案件がある。
挨拶状ドットコム(A8 s00000007052003、2026-11-28 提携)。記事を直すときに名前が戻ると落ちる。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1] / "sites" / "trend" / "content"
# (link id on the page, words that must not be in title / description)
RULES = [("4BGVY7+9LBL1M", ("挨拶状", "aisatsu"))]


def hits(page: dict) -> list[str]:
    body = json.dumps(page.get("sections", []), ensure_ascii=False)
    head = (page.get("title", "") + " " + page.get("description", "")).lower()
    return [w for mat, words in RULES if mat in body for w in words if w in head]


class TestAdHeadTerms(unittest.TestCase):
    def test_no_page_with_the_ad_names_the_advertiser_in_its_head(self):
        for f in CONTENT.glob("*.json"):
            self.assertEqual(hits(json.loads(f.read_text(encoding="utf-8"))), [], f.name)

    def test_the_check_notices_the_name(self):
        page = {"title": "年賀状の早割", "description": "挨拶状ドットコムの割引", "sections": [{"html": "a8mat=4BGVY7+9LBL1M+1IEW"}]}
        self.assertEqual(hits(page), ["挨拶状"])
        self.assertEqual(hits({**page, "sections": []}), [])


if __name__ == "__main__":
    unittest.main()
