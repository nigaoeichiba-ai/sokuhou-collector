"""trend: 出典は記事の最下部の「出典:」にまとめる(オーナー決定 2026-11-14)。
本文に「（出典：…）」の注記、「出典」の節、表の「出典」の列、出典のリンク一覧を置かない。最下部の出典の行(credit)に、社内の言い方(「窓口が…確認」)や URL を入れない。
検査の関数に、直前の形(出典の注記を置いた記事)を渡して「検出できること」(負例)も確かめる。"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sites" / "trend" / "content"
AFFILIATE = ("rakuten", "amazon", "valuecommerce", "a8.net", "shopping.yahoo")
# 読者が自分で開く、サービスの公式ステータスページへの案内(出典ではなく、使い方の案内)。ここに無いものは、本文に置かない
ALLOWED_PLAIN_LINKS = {"/trend-outlook-outage/": ("status.cloud.microsoft", "x.com/MSFT365Status")}


def problems(page: dict) -> list[str]:
    out = []
    path = page.get("path", "")
    text = json.dumps(page.get("sections", []), ensure_ascii=False).replace('\\"', '"')   # the quotes of the html come out escaped
    if re.search(r"（出典：|\(出典:", text):
        out.append(f"{path}: 本文に「（出典：…）」の注記がある")
    for s in page.get("sections", []):
        if isinstance(s, dict) and re.match(r"^出典", s.get("h2", "")):
            out.append(f"{path}: 「{s['h2']}」の節が本文にある")
        t = isinstance(s, dict) and s.get("table")
        if t and any(re.search(r"出典", c) for c in t.get("cols", [])):
            out.append(f"{path}: 表に「出典」の列がある")
    for m in re.finditer(r'<a [^>]*href="(https?://[^"]+)"', text):
        u = m.group(1)
        if not any(a in u for a in AFFILIATE) and not any(a in u for a in ALLOWED_PLAIN_LINKS.get(path, ())):
            out.append(f"{path}: 出典らしい外部リンクが本文にある: {u[:60]}")
    credit = page.get("credit") or ""
    if "窓口" in credit:
        out.append(f"{path}: 出典の行に社内の言い方(窓口)がある")
    if re.search(r"https?://", credit):
        out.append(f"{path}: 出典の行に URL がある")
    return out


class SourceFooterTest(unittest.TestCase):
    def test_published_articles(self):
        bad = []
        for f in sorted(CONTENT.glob("*.json")):
            bad += problems(json.loads(f.read_text(encoding="utf-8")))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_detects_the_old_forms(self):
        base = {"path": "/x/", "credit": "厚生労働省「発生状況」(2026年11月13日公表)をもとに作成", "sections": []}
        self.assertEqual(problems(base), [])
        self.assertTrue(problems({**base, "sections": [{"paras": ["（出典：厚生労働省より。2026年11月13日確認）"]}]}))
        self.assertTrue(problems({**base, "sections": [{"h2": "出典・確認日", "paras": ["a"]}]}))
        self.assertTrue(problems({**base, "sections": [{"table": {"cols": ["項目", "出典"], "rows": [["a", "b"]]}}]}))
        self.assertTrue(problems({**base, "sections": [{"html": '<ul><li><a href="https://www.mhlw.go.jp/" rel="noopener">厚生労働省</a></li></ul>'}]}))
        self.assertTrue(problems({**base, "credit": "各社の公式発表(窓口が2026年11月12日に確認)をもとに作成"}))
        self.assertTrue(problems({**base, "credit": "厚生労働省 https://www.mhlw.go.jp/"}))
        # 提携リンク(PR)は出典ではない
        self.assertEqual(problems({**base, "sections": [{"html": '<p><a href="https://hb.afl.rakuten.co.jp/x" rel="nofollow sponsored noopener">楽天で探す</a></p>'}]}), [])


if __name__ == "__main__":
    unittest.main()
