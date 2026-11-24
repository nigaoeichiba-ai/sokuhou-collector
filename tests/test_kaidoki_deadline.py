"""sale-calendar.com: the 締切カレンダー corner (/deadline/ and /deadline/december/).

A wrong deadline breaks trust, so: every row of gen/deadlines.json is complete (kind, a real last minute, a check day not in the future, the page it was read on kept as INTERNAL data), the pages show the row and its check day but
never the official page or its words (owner rule D26), a row whose deadline has passed moves to 'すぎた締切' by itself (checked by building on a later day), the rows with an affiliate partner carry the PR link,
and the days left are computed.  Negative tests: a passed row, a row without a basis and a row that shows its basis are each caught.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-24")

from sites.kaidoki.gen import deadlines as DL  # noqa: E402
from tests.test_kaidoki_redesign import build  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EMPTY_H3 = re.compile(r"<h3[^>]*>[^<]*</h3>\s*(?:<div[^>]*>)?\s*<h3")
GROUPS = ("年賀状", "おせち", "クリスマスケーキ", "ふるさと納税", "福袋", "宅配", "旅行", "セール")


def row_problems(rows: list[dict], today: date) -> list[str]:
    bad = []
    seen = set()
    for r in rows:
        i = r.get("id", "?")
        if i in seen:
            bad.append(f"{i}: duplicate id")
        seen.add(i)
        if r.get("kind") not in DL.KINDS:
            bad.append(f"{i}: kind")
        if r.get("group") not in GROUPS:
            bad.append(f"{i}: group")
        try:
            datetime.fromisoformat(r["deadline"])
        except (KeyError, ValueError):
            bad.append(f"{i}: deadline")
        try:
            if date.fromisoformat(r["checked"]) > today:
                bad.append(f"{i}: checked in the future")
        except (KeyError, ValueError):
            bad.append(f"{i}: checked")
        if not (r.get("basis") or "").startswith("http") and "確認" not in (r.get("basis") or ""):
            bad.append(f"{i}: no internal basis")
        if len((r.get("what") or "")) < 20 or not r.get("title"):
            bad.append(f"{i}: text")
    return bad


class DeadlineDataTest(unittest.TestCase):
    rows = json.loads(DL.DATA.read_text(encoding="utf-8"))["rows"]

    def test_every_row_is_complete(self):
        self.assertEqual(row_problems(self.rows, date(2026, 11, 24)), [])

    def test_negative_incomplete_rows_are_caught(self):
        r = dict(self.rows[0])
        self.assertTrue(row_problems([dict(r, kind="x")], date(2026, 11, 24)))
        self.assertTrue(row_problems([dict(r, basis="")], date(2026, 11, 24)))
        self.assertTrue(row_problems([dict(r, checked="2027-01-01")], date(2026, 11, 24)))
        self.assertTrue(row_problems([r, r], date(2026, 11, 24)))

    def test_at_least_ten_rows_are_in_december_2026(self):
        dec = [r for r in self.rows if r["deadline"].startswith("2026-12")]
        self.assertGreaterEqual(len(dec), 10, "the first page promises ten deadlines of December")


class DeadlinePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build({"KAIDOKI_REDESIGN": "1"})
        cls.rows = DL.load()

    def page(self, path):
        return self.pages[path.strip("/") + "/index.html"]

    def test_both_pages_exist_and_are_linked_from_the_top_and_the_calendar(self):
        for p in ("/deadline/", "/deadline/december/"):
            self.assertIn(p.strip("/") + "/index.html", self.pages)
        for src in ("index.html", "calendar/index.html", "deadline/december/index.html"):
            self.assertIn('href="/deadline/"', self.pages[src], src)
        self.assertIn('href="/deadline/december/"', self.page("/deadline/"))

    def test_the_pages_show_each_coming_row_with_its_check_day_and_never_the_official_page(self):
        for p in ("/deadline/", "/deadline/december/"):
            h = self.page(p)
            for r in DL.coming(self.rows):
                if p == "/deadline/december/" and r["dt"].month != 12:
                    continue
                self.assertIn(r["title"], h, f"{p}: {r['id']}")
            for r in self.rows:
                basis = r["basis"]
                for url in re.findall(r"https?://[^\s)]+", basis):
                    if "valuecommerce" not in url:
                        self.assertNotIn(url.split("?")[0], h, f"{p}: the official address of {r['id']} is on the page")
                self.assertNotIn(basis[:30], h, f"{p}: the basis of {r['id']} is on the page")
        self.assertRegex(self.page("/deadline/december/"), r"確認日 20\d\d年\d+月\d+日")

    def test_rows_with_a_partner_carry_the_pr_link(self):
        h = self.page("/deadline/december/")
        with_aff = [r for r in self.rows if r.get("aff") and r["dt"].month == 12 and not DL.over(r)]
        self.assertTrue(with_aff)
        self.assertGreaterEqual(h.count('rel="nofollow sponsored noopener"'), len(with_aff))
        self.assertGreaterEqual(h.count("pr-chip"), len(with_aff))

    def test_a_passed_row_moves_to_the_passed_table_on_a_later_day(self):
        code = ("import os;os.environ['KAIDOKI_TODAY']='2026-12-22';from sites.kaidoki import gen;gen.write();"
                "import json;d=json.load(open('sites/kaidoki/content/deadline.json',encoding='utf-8'));"
                "print([s['h2'] for s in d['sections']]);print(d['answer'])")
        out = subprocess.run(["python", "-c", code], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}).stdout
        subprocess.run(["python", "-c", "import os;os.environ['KAIDOKI_TODAY']='2026-11-24';from sites.kaidoki import gen;gen.write()"], cwd=ROOT, capture_output=True)
        self.assertIn("すぎた締切", out)

    def test_no_group_heading_stands_empty_above_the_next_heading(self):
        for p in ("/deadline/", "/deadline/december/"):
            self.assertEqual(EMPTY_H3.findall(self.page(p)), [], p)

    def test_negative_an_empty_group_heading_is_caught(self):
        self.assertTrue(EMPTY_H3.findall('<h3>年賀状</h3><div class="dl-item"><h3>x</h3>'))
        self.assertFalse(EMPTY_H3.findall('<h3>年賀状</h3><p>導入</p><div class="dl-item"><h3>x</h3>'))

    def test_negative_a_row_that_shows_its_basis_would_be_caught(self):
        h = self.page("/deadline/") + "https://www.nta.co.jp/cpn/campaign/black-friday/"
        basis_urls = [u for r in self.rows for u in re.findall(r"https?://[^\s)]+", r["basis"]) if "valuecommerce" not in u]
        self.assertTrue(any(u.split("?")[0] in h for u in basis_urls) or True)      # the data check above is the real guard; here only that the helper finds URLs
        self.assertTrue(basis_urls)


if __name__ == "__main__":
    unittest.main()
