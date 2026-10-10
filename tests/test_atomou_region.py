"""The prefecture a visitor lives in (kept on the device): the days of that place are found by the place or the region of each day."""
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
PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['お金・税金・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, regions: ['東京都', '大阪府', '北海道'] };
localStorage.setItem('atomou.v1', %(stored)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script>
<script>var cat = [
 {id: 'a', title: 'A', date: '2026-11-01', place: '東京都(東京ビッグサイト)', region: '東京都'},
 {id: 'b', title: 'B', date: '2026-10-20', place: '大阪府', region: '大阪府'},
 {id: 'c', title: 'C', date: '2026-10-12', place: '全国', region: '全国'},
 {id: 'd', title: 'D', date: '2026-10-01', place: '東京都', region: '東京都'},
 {id: 'e', title: 'E', date: '2026-10-15', place: '', region: '東京都'},
 {id: 'f', title: 'F', date: '2026-10-30', place: '東京都(静かな日)', region: '東京都', quiet: true}];
document.getElementById('out').textContent = JSON.stringify({ tokyo: window.AtomouApp.regionHits(cat, '東京都').map(function (x) { return x.id; }), region: window.Atomou.state().prefs.region });</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class RegionInChrome(unittest.TestCase):
    def run_page(self, region: str) -> dict:
        stored = {"v": 1, "entries": [], "prefs": {"region": region}}
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PAGE % {"stored": json.dumps(json.dumps(stored, ensure_ascii=False)), **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app")}}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-10"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_days_in_the_prefecture_come_by_place_or_region_nearest_first_and_a_quiet_or_past_day_does_not(self):
        r = self.run_page("東京都")
        self.assertEqual(r["tokyo"], ["e", "a"])             # D is past, F is quiet, B is Osaka, C is nationwide
        self.assertEqual(r["region"], "東京都")

    def test_a_region_that_is_not_a_prefecture_is_dropped(self):
        self.assertEqual(self.run_page("どこかの国")["region"], "")


if __name__ == "__main__":
    unittest.main()
