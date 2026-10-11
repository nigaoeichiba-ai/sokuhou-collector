"""atomou 案5 「週で見る」: the weeks of a day on its plan page (words and one cell for each week; none for a quiet day or today; words only past 26 years behind / 2 years ahead) and the
rest of the year in weeks on /kyou/.  A real Chrome opens the built pages (today = 2026-10-11) with days of the visitor's own put in its storage first; the numbers are counted by hand
below (tests/fixtures/atomou/date_vectors.json holds the day-count cases both languages share)."""
import functools
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = "2026-10-11"

# id, date, kind  ->  (what the page says, the cells in the grid)   [counted from 2026-10-11 by hand: see the comments]
OWN = [
    ("pa", "2020-04-01", "anniversary"),   # 2,384 days behind = 340 weeks 4 days: 341 cells, the last one partial
    ("pb", "2026-12-25", "event"),         # 75 days ahead = 10 weeks 5 days: 11 cells
    ("pc", "1990-01-01", "anniversary"),   # 13,432 days = 1,918 weeks: more than 26 years: words only
    ("pd", "2030-06-01", "event"),         # 1,329 days = 189 weeks: more than 2 years ahead: words only
    ("pe", "2020-01-01", "memorial"),      # a quiet day: no section
    ("pf", "2026-10-18", "event"),         # exactly 7 days ahead: 1 week, 1 cell, none partial
    ("pg", "2026-10-14", "event"),         # 3 days ahead: "3日", 1 partial cell
    ("ph", TODAY, "event"),                # today: no section
    ("pi", "2026-10-04", "anniversary"),   # exactly 7 days behind
]
WANT = {
    "pa": ("もう340週4日(2,384日)です。", 341, 1), "pb": ("あと10週5日(75日)です。", 11, 1), "pc": ("もう1918週6日(13,432日)です。", 0, 0), "pd": ("あと189週6日(1,329日)です。", 0, 0),
    "pe": None, "pf": ("あと1週(7日)です。", 1, 0), "pg": ("あと3日です。", 1, 1), "ph": None, "pi": ("もう1週(7日)です。", 1, 0),
}

HARNESS = """<!doctype html><meta charset="utf-8"><title>weeks</title><body><pre id="out">[]</pre><div id="host"></div><script>
var OWN = %(own)s, TODAY = %(today)s, results = {};
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
(async function () {
  var st = { v: 1, updated: '2026-10-11T00:00:00.000Z', entries: OWN.map(function (o) { return { id: o[0], title: 'テスト' + o[0], date: o[1], precision: 'day', kind: o[2], quiet: o[2] === 'memorial', created: '2026-10-01' }; }),
    deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', setup: true, intro: true } };
  localStorage.setItem('atomou.v1', JSON.stringify(st));
  for (var i = 0; i < OWN.length; i++) {
    var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:900px;border:0'; document.getElementById('host').appendChild(f);
    await new Promise(function (res) { f.onload = res; f.src = '/plan/?key=m:' + OWN[i][0] + '&today=' + TODAY; });
    await wait(700);
    var d = f.contentDocument, sec = d.getElementById('weeks'), g = d.querySelector('#weeks .wgrid');
    results[OWN[i][0]] = sec ? { line: (sec.querySelector('.weeks-line') || {}).textContent || '', cells: g ? g.children.length : 0, part: g ? g.querySelectorAll('i.part').length : 0, label: g ? g.getAttribute('aria-label') : '',
      hasSec: true, over: d.documentElement.scrollWidth > 376 } : { hasSec: false, over: d.documentElement.scrollWidth > 376 };
    f.remove();
  }
  var k = document.createElement('iframe'); k.style.cssText = 'width:375px;height:900px;border:0'; document.getElementById('host').appendChild(k);
  await new Promise(function (res) { k.onload = res; k.src = '/kyou/?today=' + TODAY; });
  await wait(900);
  var kd = k.contentDocument, yl = kd.getElementById('year-left');
  results.kyou = { hidden: yl ? yl.hidden : null, items: yl ? [].map.call(yl.querySelectorAll('li'), function (l) { return l.textContent; }) : [] };
  document.getElementById('out').textContent = JSON.stringify(results);
})();
</script>"""


class Weeks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=__import__("datetime").date(2026, 10, 11)), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__weeks.html").write_text(HARNESS % {"own": json.dumps([list(o) for o in OWN]), "today": json.dumps(TODAY)}, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=60000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__weeks.html"], capture_output=True, timeout=240)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "[]", "the harness did not finish"
        cls.res = json.loads(html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_the_words_and_the_cells_of_each_day(self):
        for k, want in WANT.items():
            r = self.res[k]
            if want is None:
                self.assertFalse(r["hasSec"], k)
                continue
            self.assertTrue(r["hasSec"], k)
            self.assertEqual((r["line"], r["cells"], r["part"]), want, k)

    def test_the_grid_is_described_for_a_screen_reader_and_never_makes_the_page_wider(self):
        self.assertIn("1マスが1週です。この日から340週4日分", self.res["pa"]["label"])
        self.assertIn("この日まで10週5日分", self.res["pb"]["label"])
        for k in WANT:
            self.assertFalse(self.res[k]["over"], k)

    def test_the_rest_of_the_year_on_kyou(self):
        k = self.res["kyou"]
        self.assertFalse(k["hidden"])
        # 2026-10-11: 81 days are left in the year = 11 weeks 4 days; 11 Saturdays and 11 Sundays come after today; the next term is Sōkō on 2026-10-23, 12 days = 1 week 5 days
        self.assertEqual(k["items"], ["2026年が終わるまで、あと11週4日(81日)です。", "今日より後の土曜日は、年内にあと11回、日曜日は11回です。", "次の節気「霜降」まで、あと1週5日です。"])


class Wording(unittest.TestCase):
    def test_the_block_is_in_the_kyou_page_and_not_in_the_menu(self):
        pages = build.build_pages(CFG, release=True, today=__import__("datetime").date(2026, 10, 11))
        k = pages["kyou/index.html"]
        self.assertIn('id="year-left"', k)
        self.assertIn("霜降", k)
        self.assertNotIn("year-left", pages["index.html"])

    def test_no_weeks_of_a_life_are_counted(self):
        # the owner's rule: nothing that counts the weeks of a person's life (an average life span) is ever made
        js = (ROOT / "sites" / "atomou" / "assets" / "plan.js").read_text(encoding="utf-8") + (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        for bad in ("寿命", "残りの人生", "人生の残り", "lifeExpect"):
            self.assertNotIn(bad, js, bad)


if __name__ == "__main__":
    unittest.main()
