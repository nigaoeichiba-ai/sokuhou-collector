"""Days found in a pasted text (a search result, an AI's answer, a flyer): read on the device with plain rules, no network, no guessing beyond the words."""
import html
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_atomou_core_js import find_chrome  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "sites/atomou/assets"

CASES = [
    "〇〇バンド ワンマンライブ 2026年12月1日(火) 開場18:00 開演19:00 会場: 渋谷",
    "次の試験は令和8年11月8日(日)です。申込は10月30日までに。",
    "12/24(木) クリスマスイブのディナー予約 19時30分",
    "来年の3月3日にひな祭りがあります",
    "日付のない文章です。",
    "2026/12/25 発売 / 2027.1.5 締切",
    "年末の12月31日と、昨日の10月9日",
]

PAGE = """<!doctype html><meta charset="utf-8"><script src="%(core)s"></script><pre id="out">pending</pre>
<script>var cases = %(cases)s, today = [2026, 10, 10];
document.getElementById('out').textContent = JSON.stringify(cases.map(function (t) { return AtomouCore.extractDays(t, today).map(function (x) { return { iso: x.iso, time: x.time, title: x.title }; }); }));</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class ExtractInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PAGE % {"core": (ASSETS / "core.js").as_uri(), "cases": json.dumps(CASES, ensure_ascii=False)}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=3000",
                                "--dump-dom", page.as_uri()], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_a_live_flyer_gives_the_day_the_start_time_and_the_title(self):
        r = self.res[0]
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["iso"], r[0]["time"]), ("2026-12-01", "19:00"))      # the opening (開場 18:00) is not the start (開演 19:00)
        self.assertTrue(r[0]["title"].startswith("〇〇バンド ワンマンライブ"))

    def test_an_era_year_and_a_day_without_a_year(self):
        self.assertEqual([x["iso"] for x in self.res[1]], ["2026-10-30", "2026-11-08"])   # 令和8年 = 2026; "10月30日" is the next 10/30 from today
        self.assertEqual([x["iso"] for x in self.res[3]], ["2027-03-03"])                 # 3/3 has passed this year: next year's

    def test_a_slash_date_with_a_weekday_and_a_time_in_hours(self):
        r = self.res[2]
        self.assertEqual((r[0]["iso"], r[0]["time"]), ("2026-12-24", "19:30"))

    def test_nothing_is_made_up_from_a_text_without_a_day(self):
        self.assertEqual(self.res[4], [])

    def test_several_notations_in_one_text(self):
        self.assertEqual([x["iso"] for x in self.res[5]], ["2026-12-25", "2027-01-05"])

    def test_a_day_just_past_is_kept_only_when_nothing_is_ahead(self):
        self.assertEqual([x["iso"] for x in self.res[6]], ["2026-10-09", "2026-12-31"])


if __name__ == "__main__":
    unittest.main()
