"""atomou 案4 「今日の1問」: the question of each date (assets/quiz.js) is made from the date alone and its right answer is checked here by an independent count in Python for 300 dates
(holiday rules, solar terms, weekdays, day of the year, the weeks of a year); the same date always gives the same question; a quiet day, an estimate, a month-only day and a far day are never
asked about; the page shows the reason with the answer, keeps the result on the device only, and never carries an ad."""
import calendar
import functools
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, calendar_data as cal, datecore  # noqa: E402
from sokuhou import layoutcheck  # noqa: E402
from tests.test_atomou_controls import _Quiet, _Server  # noqa: E402

ASSETS = ROOT / "sites" / "atomou" / "assets"
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
WD = "月火水木金土日"
START = date(2026, 10, 11)
DAYS = 300

HOL = sorted([n, d.isoformat()] for y in (2026, 2027, 2028) for d, n in cal.holidays(y).items())      # in the order of the NAMES on purpose: the script must not depend on the order (deploy-time bug: the page once listed them so)
TERMS = [[t["name"], t["date"].isoformat()] for y in (2026, 2027) for t in cal.terms_of(y)]
CARDS = [
    {"id": "aaaaaaaaaa", "title": "テスト試験", "date": "2026-11-03", "precision": "day"},
    {"id": "bbbbbbbbbb", "title": "静かな日", "date": "2026-11-04", "precision": "day", "quiet": True},
    {"id": "cccccccccc", "title": "推定の日", "date": "2026-11-05", "precision": "day", "estimated": True},
    {"id": "dddddddddd", "title": "月だけの日", "date": "2026-11-06", "precision": "month"},
    {"id": "eeeeeeeeee", "title": "遠い日", "date": "2027-06-06", "precision": "day"},
]

PAGE = """<!doctype html><meta charset="utf-8"><script src="@@core@@"></script><script src="@@quiz@@"></script><pre id="out">pending</pre>
<script>
(function () {
  var C = AtomouCore, Q = AtomouQuiz, hol = %(hol)s, terms = %(terms)s, cards = %(cards)s, out = { days: [], again: true, nodata: [], onlyQuiet: [] };
  var t = C.parse('%(start)s');
  for (var i = 0; i < %(days)d; i++) {
    var d = C.addDays(t, i), q = Q.make(d, { hol: hol, terms: terms, cards: cards });
    out.days.push([C.iso(d), q]);
    if (JSON.stringify(q) !== JSON.stringify(Q.make(d, { hol: hol, terms: terms, cards: cards }))) out.again = false;
  }
  for (var j = 0; j < 8; j++) { var q2 = Q.make(C.addDays(t, j), {}); out.nodata.push(q2 && q2.type); }
  for (var k = 0; k < 8; k++) { var q3 = Q.make(C.addDays(t, k), { cards: [cards[1], cards[2], cards[3], cards[4]] }); out.onlyQuiet.push(q3 && [q3.type, q3.q]); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


def expected(iso, qtype):
    """The right answer text of a question, counted without the script's helpers."""
    t = date.fromisoformat(iso)
    if qtype == "holiday":
        nxt = min(d for d in (date.fromisoformat(x[1]) for x in HOL) if d > t)
        return f"{(nxt - t).days}日"
    if qtype == "sat":
        n = sum(1 for k in range(1, 400) if (t + timedelta(days=k)).year == t.year and (t + timedelta(days=k)).weekday() == 5)
        return f"{n}回"
    if qtype == "doy":
        return f"{(t - date(t.year, 1, 1)).days + 1}日目"
    if qtype == "xmas":
        y = t.year + 1 if (t.month == 12 and t.day > 25) else t.year
        return WD[date(y, 12, 25).weekday()] + "曜日"
    if qtype == "plus100":
        d = t + timedelta(days=100)
        return f"{d.month}月{d.day}日"
    if qtype == "nextmonth":
        y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
        return f"{calendar.monthrange(y, m)[1]}日"
    if qtype == "term":
        nxt = min(d for d in (date.fromisoformat(x[1]) for x in TERMS) if d > t)
        return f"{(nxt - t).days}日"
    raise AssertionError(qtype)


class Questions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        src = PAGE % {"hol": json.dumps(HOL, ensure_ascii=False), "terms": json.dumps(TERMS, ensure_ascii=False), "cards": json.dumps(CARDS, ensure_ascii=False), "start": START.isoformat(), "days": DAYS}
        src = src.replace("@@core@@", (ASSETS / "core.js").as_uri()).replace("@@quiz@@", (ASSETS / "quiz.js").as_uri())     # after the formatting: the paths hold % signs
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "q.html"
            p.write_text(src, encoding="utf-8")
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=8000", "--dump-dom", p.as_uri()],
                               capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_the_right_answer_is_right_for_every_date(self):
        seen = {}
        for iso, q in self.res["days"]:
            self.assertIsNotNone(q, iso)
            if q["type"] != "card":
                self.assertEqual(q["choices"][q["ans"]], expected(iso, q["type"]), (iso, q["type"], q["q"]))
            seen[q["type"]] = seen.get(q["type"], 0) + 1
        self.assertEqual(sorted(seen), sorted(["holiday", "sat", "doy", "xmas", "plus100", "nextmonth", "term", "card"]))     # every kind of question comes round

    def test_four_different_choices_and_the_place_of_the_answer_moves(self):
        places = set()
        for iso, q in self.res["days"]:
            self.assertEqual(len(q["choices"]), 4, (iso, q["type"]))
            self.assertEqual(len(set(q["choices"])), 4, (iso, q["choices"]))
            self.assertTrue(0 <= q["ans"] < 4)
            self.assertTrue(q["why"] and q["q"])
            places.add(q["ans"])
        self.assertEqual(places, {0, 1, 2, 3})

    def test_the_same_date_gives_the_same_question(self):
        self.assertTrue(self.res["again"])

    def test_a_question_about_an_official_day_is_about_a_plain_one_with_a_link_to_its_page(self):
        cards = [(iso, q) for iso, q in self.res["days"] if q["type"] == "card"]
        self.assertTrue(cards)
        plain = {"aaaaaaaaaa": date(2026, 11, 3), "eeeeeeeeee": date(2027, 6, 6)}      # the quiet one, the estimate and the month-only one are never asked about; the far one only within 120 days
        asked = set()
        for iso, q in cards:
            cid = q["link"].split("/")[2]
            self.assertIn(cid, plain, (iso, q["link"]))
            d = plain[cid]
            asked.add(cid)
            self.assertEqual(q["choices"][q["ans"]], WD[d.weekday()] + "曜日", iso)
            self.assertTrue(0 < (d - date.fromisoformat(iso)).days <= 120, (iso, cid))
        self.assertEqual(asked, set(plain))

    def test_without_data_the_questions_that_need_none_are_asked_and_a_quiet_day_is_never(self):
        self.assertTrue(all(t in ("sat", "doy", "xmas", "plus100", "nextmonth") for t in self.res["nodata"]), self.res["nodata"])
        for t, q in self.res["onlyQuiet"]:
            self.assertNotEqual(t, "card", q)
            for bad in ("静かな日", "推定の日", "月だけの日", "遠い日"):
                self.assertNotIn(bad, q)

    def test_a_wrong_count_would_be_caught(self):
        # the check is no mirror of the script: a holiday counted one day short is not the right answer
        iso, q = next((i, x) for i, x in self.res["days"] if x["type"] == "holiday")
        wrong = f"{int(expected(iso, 'holiday')[:-1]) - 1}日"
        self.assertNotEqual(q["choices"][q["ans"]], wrong)


class OnThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=True, today=START)

    def test_the_page_has_no_ads_is_not_listed_and_is_linked_from_the_home_chips(self):
        q = self.pages["quiz/index.html"]
        self.assertIn('id="quiz"', q)
        self.assertIn("noindex", q)
        self.assertNotIn("pagead2.googlesyndication", q)
        self.assertNotIn("/quiz/", self.pages["sitemap.xml"])
        self.assertIn('href="/quiz/"', self.pages["index.html"])
        self.assertIn("quiz", build.BUNDLE)
        self.assertLess(build.BUNDLE.index("plan"), build.BUNDLE.index("quiz"))

    def test_the_page_carries_only_what_the_questions_need(self):
        q = self.pages["quiz/index.html"]
        m = re.search(r'data-hol="([^"]*)"', q)
        hol = json.loads(html.unescape(m.group(1)))
        self.assertIn(["元日", "2027-01-01"], hol)
        self.assertEqual([x[1] for x in hol], sorted(x[1] for x in hol))      # in the order of the dates
        self.assertTrue(all(len(x) == 2 for x in hol))
        t = json.loads(html.unescape(re.search(r'data-terms="([^"]*)"', q).group(1)))
        self.assertIn(["霜降", "2026-10-23"], t)

    def test_nothing_is_sent_and_nothing_of_a_life_or_a_game_is_kept(self):
        js = (ASSETS / "quiz.js").read_text(encoding="utf-8")
        self.assertNotIn("fetch(", js)
        self.assertNotIn("XMLHttpRequest", js)
        self.assertNotIn("sendBeacon", js)
        for bad in ("ランキング", "連続", "ポイント", "ストリーク"):
            self.assertNotIn(bad, js, bad)


HARNESS = """<!doctype html><meta charset="utf-8"><title>quiz</title><body><pre id="out">{}</pre><div id="host"></div><script>
function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
async function open(w) {
  var f = document.createElement('iframe'); f.style.cssText = 'width:375px;height:900px;border:0'; document.getElementById('host').appendChild(f);
  await new Promise(function (res) { f.onload = res; f.src = '/quiz/?today=2026-10-11'; });
  await wait(900); return f;
}
(async function () {
  var out = {};
  localStorage.removeItem('atomou.q.v1');
  var f = await open(), d = f.contentDocument, A = f.contentWindow.AtomouApp, Q = f.contentWindow.AtomouQuiz;
  var box = d.getElementById('quiz'), cat = await A.loadCatalog();
  var made = Q.make(A.TODAY, { hol: JSON.parse(box.getAttribute('data-hol')), terms: JSON.parse(box.getAttribute('data-terms')), cards: cat });
  out.q = made.q; out.type = made.type; out.n = d.querySelectorAll('.quiz-choices button').length; out.noResultYet = !d.querySelector('.quiz-result');
  var wrongIdx = made.ans === 0 ? 1 : 0;
  d.querySelectorAll('.quiz-choices button')[wrongIdx].click(); await wait(300);
  out.afterWrong = d.querySelector('.quiz-result') ? d.querySelector('.quiz-result').textContent : '';
  out.disabled = [].every.call(d.querySelectorAll('.quiz-choices button'), function (b) { return b.disabled; });
  out.stored = localStorage.getItem('atomou.q.v1');
  f.remove();
  f = await open(); d = f.contentDocument;      // opened again the same day: the answer is still there and cannot be changed
  out.again = d.querySelector('.quiz-result') ? d.querySelector('.quiz-result').textContent : '';
  out.againDisabled = [].every.call(d.querySelectorAll('.quiz-choices button'), function (b) { return b.disabled; });
  out.wide = d.documentElement.scrollWidth > 376;
  f.remove();
  localStorage.setItem('atomou.q.v1', JSON.stringify({ d: { '2026-10-11': 'x', 'bad': 1, '2026-10-10': 1 } }));   // junk in the storage is dropped
  f = await open(); d = f.contentDocument;
  out.junk = d.querySelector('.quiz-result') ? 'answered' : 'fresh';
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""


class InTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chrome = layoutcheck.find_chrome()
        if not chrome:
            raise unittest.SkipTest("Chrome is needed")
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(build.build_pages(CFG, release=True, today=START), Path(cls.tmp.name))
        (Path(cls.tmp.name) / "__quiz.html").write_text(HARNESS, encoding="utf-8")
        cls.srv = _Server(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=60000",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--dump-dom", f"http://127.0.0.1:{cls.srv.server_address[1]}/__quiz.html"], capture_output=True, timeout=240)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
        assert m and m.group(1).strip() != "{}", "the harness did not finish"
        cls.res = json.loads(html.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def test_answering_shows_the_reason_keeps_the_result_on_the_device_and_cannot_be_changed(self):
        r = self.res
        self.assertEqual(r["n"], 4)
        self.assertTrue(r["noResultYet"])
        self.assertIn("ざんねん。答えは「", r["afterWrong"])
        self.assertIn("今週は 1回 答えました。お休みしても、何も失いません。", r["afterWrong"])
        self.assertTrue(r["disabled"])
        self.assertEqual(json.loads(r["stored"]), {"d": {"2026-10-11": 0}})
        self.assertIn("ざんねん。答えは「", r["again"])
        self.assertTrue(r["againDisabled"])
        self.assertFalse(r["wide"])

    def test_junk_in_the_storage_is_dropped_not_trusted(self):
        self.assertEqual(self.res["junk"], "fresh")


if __name__ == "__main__":
    unittest.main()
