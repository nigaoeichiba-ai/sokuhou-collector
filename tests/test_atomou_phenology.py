"""atomou 案3 「桜と紅葉の、例年の日」: the long series of the Japan Meteorological Agency (data/atomou/jma/, read 2026-10-11 with the owner's permission) is parsed and checked against a second place of
the Agency's (its page of the cherry blossoms, read the same day: the normal day and the 2025 day of five stations), against the Agency's own earliest / latest columns, and against what winter-flowering
cherries of the south and autumn leaves entered in January look like; the page is opened in a real Chrome; nothing is a forecast."""
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

from sites.atomou import build, phenology as ph  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 11)

# the Agency's page sakura_kaika.html (read 2026-10-11): station -> (the normal day 平年日, the day of 2025)
OFFICIAL = {"東京": (324, 324), "大阪": (327, 327), "札幌": (501, 423), "福岡": (322, 325), "那覇": (116, 105)}
# the Agency's earliest / latest use the regular tree only and so differ for these (all in Hokkaido / Muroran): checked by name, not hidden
KNOWN_OTHER = {("sakura-open", "岩見沢"), ("sakura-full", "岩見沢"), ("maple", "室蘭")}


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series = {key: ph.parse(ph.RAW / f"ruinenchi_{sid}.csv") for sid, key, _ in ph.SERIES}

    def test_the_four_files_are_whole(self):
        for key, s in self.series.items():
            self.assertEqual(len(s["stations"]), 102, key)
            for st in s["stations"]:
                for y, v in st["years"].items():
                    self.assertTrue(1953 <= y <= 2032 and 1 <= v // 100 <= 12 and 1 <= v % 100 <= 31, (key, st["name"], y, v))
                    date(2001, v // 100, v % 100)       # a real day of a year
        self.assertEqual([s["name"] for s in self.series.values()], ["さくらの開花", "さくらの満開", "いちょうの黄葉", "かえでの紅葉"])

    def test_the_numbers_agree_with_the_agencys_page_for_five_stations(self):
        by = {st["name"]: st for st in self.series["sakura-open"]["stations"]}
        for name, (normal, y2025) in OFFICIAL.items():
            self.assertEqual(by[name]["jma"]["normal"], normal, name)
            self.assertEqual(by[name]["years"][2025], y2025, name)

    def test_the_earliest_and_latest_agree_with_the_agencys_own_columns(self):
        n = bad = 0
        for key, s in self.series.items():
            for st in s["stations"]:
                j = st["jma"]
                regular = {y: v for y, v in st["years"].items() if st["rm"][y] in (8, 9)}
                if not regular or not j["earliest"] or 2026 in (j["earliest_year"], j["latest_year"]):      # the Agency's columns already hold 2026, the year columns do not
                    continue
                n += 1
                x = ph.stats(key, regular, 2025)
                if (x["early"][0], x["late"][0]) != (j["earliest"], j["latest"]):
                    bad += 1
                    self.assertIn((key, st["name"]), KNOWN_OTHER)
        self.assertGreater(n, 300)
        self.assertLessEqual(bad, len(KNOWN_OTHER))

    def test_the_committed_data_is_what_the_files_give(self):
        self.assertEqual(ph.load(), ph.build())


class Counting(unittest.TestCase):
    def test_a_winter_cherry_of_the_south_has_a_december_day_that_is_the_earliest(self):
        s = ph.stats("sakura-open", {1974: 1221, 1976: 105, 1977: 120}, 2025)
        self.assertEqual((s["early"], s["late"]), ([1221, 1974], [120, 1977]))
        # counted as plain days of the year the December day would be the latest: the check finds that
        self.assertEqual(max(ph.doy(v) for v in (1221, 105, 120)), ph.doy(1221))
        self.assertLess(ph.ordinal("sakura-open", 1221), ph.ordinal("sakura-open", 105))

    def test_an_autumn_leaf_entered_in_january_is_the_latest(self):
        s = ph.stats("ginkgo", {2000: 107, 2001: 1227, 1990: 1110}, 2025)
        self.assertEqual((s["early"], s["late"]), ([1110, 1990], [107, 2000]))
        self.assertGreater(ph.ordinal("ginkgo", 107), ph.ordinal("ginkgo", 1227))

    def test_the_usual_day_is_the_mean_of_the_last_ten_years_and_needs_five_of_them(self):
        years = {y: 321 for y in range(2016, 2026)}
        self.assertEqual(ph.stats("sakura-open", years, 2025)["usual"], 321)
        years[2016], years[2017] = 331, 311          # 10 days either side: the mean stays
        self.assertEqual(ph.stats("sakura-open", years, 2025)["usual"], 321)
        few = {y: 321 for y in range(2021, 2025)}
        self.assertEqual(ph.stats("sakura-open", few, 2025)["usual"], 0)          # four values: no usual day
        old = {y: 321 for y in range(1990, 2000)}
        self.assertEqual(ph.stats("sakura-open", old, 2025)["usual"], 0)          # none in the last ten years
        self.assertEqual(ph.stats("sakura-open", {}, 2025), None)

    def test_the_real_stations(self):
        d = ph.load()
        row = {it["id"]: {s["n"]: s for s in it["stations"]} for it in d["items"]}
        self.assertEqual(row["sakura-open"]["東京"]["early"], [314, 2023])
        self.assertEqual(row["sakura-open"]["東京"]["late"], [411, 1984])
        self.assertEqual(row["sakura-open"]["東京"]["normal"], 324)
        self.assertEqual(row["sakura-open"]["石垣島"]["early"], [1219, 1969])      # a December day of the year before: the earliest
        self.assertNotEqual(row["sakura-open"]["石垣島"]["late"][0], 1219)
        self.assertNotIn("西表島", row["sakura-open"])          # no usual day (it stopped observing): not listed
        self.assertEqual(d["last"], 2025)

    def test_every_prefecture_has_a_station_that_exists(self):
        self.assertEqual(list(ph.PREF_STATION), build.PREFECTURES)
        names = set(ph.stations_with(ph.load()))
        self.assertEqual({n for n in ph.PREF_STATION.values()} - names, set())


HARNESS = """<!doctype html><meta charset="utf-8"><title>pheno</title><body><pre id="out">{}</pre><div id="host"></div><script>
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
async function open() {
  var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:1400px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (res) { f.onload = res; f.src = '/kyou/sakura/?today=2026-10-11'; });
  await wait(900); return f;
}
(async function () {
  var out = {};
  localStorage.removeItem('atomou.v1');
  var f = await open(), d = f.contentDocument;
  out.first = d.getElementById('ph-st').value; out.firstText = d.getElementById('ph-out').innerText; out.n = d.getElementById('ph-st').options.length;
  var sel = d.getElementById('ph-st'); sel.value = '那覇'; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait(200);
  out.naha = d.getElementById('ph-out').innerText; out.dots = d.querySelectorAll('.ph-dots').length; out.dotLabel = (d.querySelector('.ph-dots') || { getAttribute: function () { return ''; } }).getAttribute('aria-label');
  sel.value = '%(partial)s'; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait(200);
  out.partial = d.getElementById('ph-out').innerText;
  out.wide = d.documentElement.scrollWidth > 376;
  f.remove();
  localStorage.setItem('atomou.v1', JSON.stringify({ v: 1, updated: '2026-10-11T00:00:00.000Z', entries: [], deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', setup: true, intro: true, region: '北海道' } }));
  f = await open(); d = f.contentDocument;
  out.region = d.getElementById('ph-st').value;
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


def days_to(mmdd, today=TODAY):
    t = date(today.year, mmdd // 100, mmdd % 100)
    if t < today:
        t = date(today.year + 1, mmdd // 100, mmdd % 100)
    return (t - today).days, t.year != today.year


class OnThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        cls.data = ph.load()
        # a station that has some of the four series and not all
        cls.partial = next(n for n in ph.stations_with(cls.data) if sum(1 for it in cls.data["items"] if any(s["n"] == n for s in it["stations"])) in (1, 2, 3))
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=TODAY), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__pheno.html").write_text(HARNESS % {"partial": cls.partial}, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=60000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__pheno.html"], capture_output=True, timeout=240)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.ui = json.loads(html.unescape(m.group(1)))
        cls.pages = build.build_pages(CFG, release=True, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_tokyo_by_default_with_the_days_to_the_usual_day(self):
        u = self.ui
        self.assertEqual(u["first"], "東京")
        self.assertEqual(u["n"], len(ph.stations_with(self.data)))
        t = u["firstText"].replace("\n", " ")
        self.assertIn("平年(気象庁、1991〜2020年): 3月24日ごろ", t)
        self.assertIn("直近10年の平均: 3月19日ごろ", t)
        n, nxt = days_to(324)
        self.assertTrue(nxt)
        self.assertIn(f"平年の日(3月24日)まで、来年の同じ日まで、あと{n}日です。", t)
        self.assertIn("いちばん早い日: 3月14日(2023年) / いちばん遅い日: 4月11日(1984年)", t)
        self.assertIn("これは過去の記録です。今年の時期の予想ではありません。", t)

    def test_another_station_the_dots_and_a_station_without_every_series(self):
        u = self.ui
        n, _ = days_to(116)
        self.assertIn("平年(気象庁、1991〜2020年): 1月16日ごろ", u["naha"].replace("\n", " "))
        self.assertIn(f"あと{n}日です。", u["naha"].replace("\n", " "))
        self.assertEqual(u["dots"], 2)          # Naha has the two cherry series only
        self.assertIn("直近10年:", u["dotLabel"])
        self.assertIn("この地点では、いま観測していません。", u["partial"])
        self.assertFalse(u["wide"])

    def test_the_station_of_the_chosen_prefecture_comes_first(self):
        self.assertEqual(self.ui["region"], "札幌")

    def test_the_page_names_its_source_says_it_changed_it_and_forecasts_nothing(self):
        p = self.pages["kyou/sakura/index.html"]
        flat = re.sub(r"<[^>]+>", "", p)
        for must in ("気象庁ホームページ", "加工して作成", "今年の開花の予想ではありません", "予想するものではありません"):
            self.assertIn(must, flat)
        self.assertIn("https://www.data.jma.go.jp/sakura/data/index.html", p)
        for bad in ("開花予想日", "見込み", "お花見の予定日", "咲くでしょう"):
            self.assertNotIn(bad, flat)
        self.assertIn('href="/kyou/sakura/"', self.pages["kyou/index.html"])
        self.assertIn("/kyou/sakura/", self.pages["sitemap.xml"])
        self.assertNotIn("/kyou/sakura/", self.pages["index.html"])        # under /kyou/ only (owner, 2026-10-11)
        for st in ("札幌", "東京", "那覇"):
            self.assertIn(f'<th scope="row">{st}</th>', p)


if __name__ == "__main__":
    unittest.main()
