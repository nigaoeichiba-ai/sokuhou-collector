"""atomou: the order of the official days on the search page (owner, 2026-10-12): the day that comes next, new ones, the ones most visitors put in (the order of live/pop.v1.json, ids only), the
fields chosen on the setup first, and the chosen prefecture first.  A real Chrome opens the built search page; the order is checked against the page's own catalogue by property, so the check does not copy the sort."""
import functools
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 12)

HARNESS = """<!doctype html><meta charset="utf-8"><title>sort</title><body><pre id="out">{}</pre><div id="host"></div><script>
window.onerror = function (m, s, l) { document.getElementById('out').textContent = JSON.stringify({ error: m + ' @' + l }); };
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function seed(sort, extra) {
  var st = { v: 1, updated: '2026-10-12T00:00:00.000Z', entries: [], deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', setup: true, intro: true, genres: ['趣味・ゲーム・アニメ'], region: '東京都', sort: { mine: '', pub: sort } } };
  if (extra) extra(st);
  localStorage.setItem('atomou.v1', JSON.stringify(st));
}
async function run(mode, extra) {
  seed(mode, extra);
  var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:812px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (res) { f.onload = res; f.src = '/search/?q=%E7%99%BA%E5%A3%B2&today=2026-10-12&limit=2000'; });
  await wait(1500);
  var d = f.contentDocument, A = f.contentWindow.AtomouApp, cat = await A.loadCatalog(), by = {};
  cat.forEach(function (c) { by[c.id] = c; });
  var pref = '東京都';
  var rows = [].map.call(d.querySelectorAll('#results .card'), function (card) {
    var c = by[card.getAttribute('data-key').slice(2)];
    return { id: c.id, date: c.date, added: c.added, title: c.title, picked: !!A.picked(c), here: String(c.place || '').indexOf(pref) >= 0 || c.region === pref };
  });
  var out = { value: d.getElementById('pub-sort').value, rows: rows, note: d.getElementById('pub-note').textContent, wide: d.documentElement.scrollWidth > 376 };
  f.remove(); return out;
}
(async function () {
  var res = {};
  res.soon = await run('soon');
  res.new = await run('new');
  res.pop = await run('pop');
  res.pick = await run('pick');
  res.area = await run('area');
  res.pickNone = await run('pick', function (st) { st.prefs.genres = []; });
  res.areaNone = await run('area', function (st) { st.prefs.region = ''; });
  // the choice made on the page is kept
  seed('soon');
  var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:812px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (r) { f.onload = r; f.src = '/search/?q=%E7%99%BA%E5%A3%B2&today=2026-10-12&limit=2000'; }); await wait(1200);
  var s = f.contentDocument.getElementById('pub-sort'); s.value = 'new'; s.dispatchEvent(new Event('change', { bubbles: true })); await wait(400);
  res.kept = JSON.parse(localStorage.getItem('atomou.v1')).prefs.sort;
  document.getElementById('out').textContent = JSON.stringify(res);
})();
</script>"""


class SortPublic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        entries, _ = catalog.build_catalog(TODAY)
        pool = sorted((e for e in entries if "発売" in e["title"] and e["status"] != "ended" and not e["quiet"]), key=lambda e: (e["date"], e["title"]))
        assert len(pool) >= 12, len(pool)
        cls.pop_ids = [pool[10]["id"], pool[0]["id"], pool[5]["id"]]       # the order of the file: the most put-in first (all of them are among the days the search finds, so the cap of 60 cuts nothing)
        cls.tmp = tempfile.TemporaryDirectory()
        site = Path(cls.tmp.name)
        build.write_pages(build.build_pages(CFG, release=True, today=TODAY), site)
        (site / "live").mkdir(exist_ok=True)
        (site / "live" / "pop.v1.json").write_text(json.dumps({"v": 1, "items": [{"id": i} for i in cls.pop_ids]}), encoding="utf-8")
        (site / "__sort.html").write_text(HARNESS, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=120000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__sort.html"], capture_output=True, timeout=400)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.res = json.loads(html.unescape(m.group(1)))
        assert "error" not in cls.res, cls.res["error"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def ids(self, k):
        return [r["id"] for r in self.res[k]["rows"]]

    def test_every_order_lists_the_same_days(self):
        base = sorted(self.ids("soon"))
        self.assertGreater(len(base), 60)      # the page lists 60 at most; the harness lifts the cap (limit=2000), so every order shows all the days the word 発売 finds
        for k in ("new", "pop", "pick", "area", "pickNone", "areaNone"):
            self.assertEqual(sorted(self.ids(k)), base, k)

    def test_soon_is_by_date(self):
        rows = self.res["soon"]["rows"]
        self.assertEqual([r["date"] for r in rows], sorted(r["date"] for r in rows))
        self.assertEqual(self.res["soon"]["value"], "soon")

    def test_new_is_the_newest_put_in_first_then_by_date(self):
        rows = self.res["new"]["rows"]
        for a, b in zip(rows, rows[1:]):
            self.assertGreaterEqual(a["added"], b["added"])
            if a["added"] == b["added"]:
                self.assertLessEqual(a["date"], b["date"])
        self.assertGreater(len({r["added"] for r in rows}), 1)      # the days were not all put in on one day: the order says something

    def test_pop_puts_the_most_put_in_first_in_the_order_of_the_file_then_the_rest_by_date(self):
        ids = self.ids("pop")
        self.assertEqual(ids[:3], self.pop_ids)
        rest = self.res["pop"]["rows"][3:]
        self.assertEqual([r["date"] for r in rest], sorted(r["date"] for r in rest))
        self.assertEqual(self.res["pop"]["note"], "")

    def test_pick_puts_the_chosen_fields_first_and_area_the_chosen_prefecture(self):
        for k, flag in (("pick", "picked"), ("area", "here")):
            rows = self.res[k]["rows"]
            flags = [r[flag] for r in rows]
            self.assertTrue(any(flags), k)
            self.assertTrue(not all(flags), k)
            self.assertEqual(flags, sorted(flags, reverse=True), k)      # all of the chosen kind, then the others
            for grp in (True, False):
                part = [r["date"] for r in rows if r[flag] is grp]
                self.assertEqual(part, sorted(part), (k, grp))

    def test_a_choice_with_nothing_to_lean_on_says_so_and_stays_by_date(self):
        self.assertEqual(self.ids("pickNone"), self.ids("soon"))
        self.assertIn("分野を選ぶと", self.res["pickNone"]["note"])
        self.assertEqual(self.ids("areaNone"), self.ids("soon"))
        self.assertIn("都道府県を選ぶと", self.res["areaNone"]["note"])

    def test_the_choice_is_kept_and_nothing_is_wide(self):
        self.assertEqual(self.res["kept"]["pub"], "new")
        for k in ("soon", "new", "pop", "pick", "area"):
            self.assertFalse(self.res[k]["wide"], k)


if __name__ == "__main__":
    unittest.main()
