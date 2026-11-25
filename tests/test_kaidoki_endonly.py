"""sale-calendar.com: a sale whose end day alone was read (Lenovo and others) showed 「開始まであとN日」 while it was running (2026-11-25)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")

from sites.kaidoki.redesign import render  # noqa: E402
from sites.kaidoki.redesign import schedule as S  # noqa: E402

JS = Path(__file__).resolve().parents[1] / "sites/kaidoki/redesign/static/scripts/calendar.js"


def _item(title: str, s: str, e: str) -> dict:
    return S.C("c-t", "lenovo", title, s, e, "11月26日(木)まで", "", checked="2026-11-25")


class _Ctx:
    at = datetime(2026, 11, 25, 12, 0, tzinfo=timezone(timedelta(hours=9)))


class EndOnlyTest(unittest.TestCase):
    def test_the_list_entry_is_marked_and_an_ordinary_one_is_not(self):
        self.assertIn(" data-endonly", S.item_li(_item("店 企画(終了日)", "2026-11-26", "2026-11-26")))
        self.assertNotIn("data-endonly", S.item_li(_item("店 企画", "2026-11-26", "2026-11-28")))

    def test_the_sale_block_of_a_genre_page_says_running(self):
        self.assertIn('data-status="開催中"', render.brand_block(_item("店 企画(終了日)", "2026-11-30", "2026-11-30"), _Ctx.at))
        self.assertIn('data-status="開催予定"', render.brand_block(_item("店 企画", "2026-11-30", "2026-12-02"), _Ctx.at))        # negative: a sale with a start still to come
        self.assertIn('data-status="終了"', render.brand_block(_item("店 企画(終了日)", "2026-11-20", "2026-11-20"), _Ctx.at))

    @unittest.skipUnless(shutil.which("node"), "node is needed to run the script's function")
    def test_the_words_of_the_script(self):
        src = JS.read_text(encoding="utf-8").replace("\r\n", "\n")
        parts = [re.search(r"^  function dayNo\(.*$", src, re.M).group(0), re.search(r"^  function saleText\(.*?^  }$", src, re.M | re.S).group(0)]
        cases = [("2026-11-26", "2026-11-26", True, "終了まであと1日"), ("2026-11-25", "2026-11-25", True, "本日が最終日"),
                 ("2026-11-27", "2026-11-29", False, "開始まであと2日"), ("2026-11-20", "2026-11-29", False, "開催中")]
        code = "\n".join(parts) + "\nprocess.stdout.write(JSON.stringify(" + json.dumps([c[:3] for c in cases]) + ".map(function (c) { return saleText(c[0], c[1], c[2], '2026-11-25'); })));"
        r = subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [c[3] for c in cases])
        self.assertIn("isOver(e, li.dataset.et) ? '終了' : saleText(s, e, li.hasAttribute('data-endonly'), today)", src)


if __name__ == "__main__":
    unittest.main()
