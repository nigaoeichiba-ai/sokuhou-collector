"""The 贈り物コンシェルジュ (sites/yorokobu/concierge.py, assets/concierge.js, content/concierge.json) and the voice/counter operations of api/ask.php it uses."""
import functools
import html as html_lib
import http.server
import json
import re
import shutil
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, concierge, content
from sokuhou.sitekit import BuildError
from tests import ask_mock
from tests.test_yorokobu_e2e import CHROME, run_chrome

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト", "contact_form_url": "https://example.com/f",
       "rakuten_affiliate_id": "AFF.ID", "rakuten_tracking_id": "trk", "amazon_tracking_id": "test-22", "adsense_pub_id": None}


def real_data() -> dict:
    c = content.load()
    d = build.prepare(c, None, CFG)
    d["cfg"] = CFG
    return json.loads(concierge.data(d, CFG, build.finder_map(d)))


class DataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = real_data()

    def test_every_event_and_person_of_the_site_is_in_the_data_with_its_own_name_and_the_extra_words(self):
        occ = {o["s"]: o for o in self.data["occ"]}
        self.assertEqual(len(occ), 24)
        self.assertIn("母の日", occ["mothers-day"]["w"])
        self.assertIn("就職", occ["new-job"]["w"])                       # '就職・入社祝い' also answers to its first half
        self.assertIn("還暦", occ["longevity"]["w"])
        rec = {r["s"]: r for r in self.data["rec"]}
        self.assertEqual(len(rec), 18)
        self.assertEqual(rec["toddler"]["n"], "幼児")                      # the bracket of '幼児(1〜5歳)' is not part of the name
        self.assertIn("お母さん", rec["mother"]["w"])
        self.assertEqual(rec["mother"]["w"][0], "お母さん")                # the longest first
        self.assertEqual(self.data["tiers"][0]["s"], "under3000")
        self.assertEqual(sorted(t["id"] for t in self.data["topics"]), sorted(concierge.TOPICS))

    def test_the_word_lists_name_only_things_that_exist(self):
        raw = json.loads(concierge.FILE.read_text(encoding="utf-8"))
        concierge.check(raw)
        bad = {**raw, "occasion_words": {**raw["occasion_words"], "no-such-day": ["x"]}}
        with self.assertRaises(BuildError):
            concierge.check(bad)
        bad = {**raw, "ambiguous_recipients": {"友達": ["friend-female", "stranger"]}}
        with self.assertRaises(BuildError):
            concierge.check(bad)

    def test_a_topic_the_script_has_no_branch_for_stops_the_build(self):
        raw = json.loads(concierge.FILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "c.json"
            p.write_text(json.dumps({**raw, "topics": raw["topics"][:-1]}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(BuildError):
                concierge.load(p)


READ = r"""
const out = {};
(async () => {
  try {
    const C = window.YorokobuConcierge; C.setData(DATA);
    out.rows = SENTENCES.map(s => { const r = C.read(s); return [s, r.occ, r.rec, r.tier, r.amb ? r.amb.slugs.join('+') : '', r.intent, r.theme]; });
    out.yen = YENS.map(s => [s, C.yenOf(s.normalize('NFKC'))]);
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""

SENTENCES = [
    "母の日に、母へ 5000円くらい",
    "彼女の誕生日 1万円",
    "祖父母に敬老の日",
    "丈夫な傘を贈りたい",
    "夫の誕生日に",
    "夫婦で使えるもの",
    "友達の結婚祝い 3千円",
    "上司への退職祝い のしはどうする",
    "セールで安く買いたい",
    "70代の母に クリスマス",
    "予算は5000円〜8000円で、父の日",
    "カレーが好きな人に",
    "お母さんに",
    "明日までに届く誕生日プレゼント",
    "引っ越し祝い 2万5千円",
]
EXPECT = {
    "母の日に、母へ 5000円くらい": ["mothers-day", "mother", "3000-5000", "", "", ""],
    "彼女の誕生日 1万円": ["birthday", "girlfriend", "5000-10000", "", "", ""],
    "祖父母に敬老の日": ["respect-for-aged-day", "", "", "grandfather+grandmother", "", ""],
    "丈夫な傘を贈りたい": ["", "", "", "", "", ""],
    "夫の誕生日に": ["birthday", "husband", "", "", "", ""],
    "夫婦で使えるもの": ["", "", "", "", "", ""],
    "友達の結婚祝い 3千円": ["wedding-gift", "", "under3000", "friend-female+friend-male", "", ""],
    "上司への退職祝い のしはどうする": ["retirement", "boss", "", "", "manners", ""],
    "セールで安く買いたい": ["", "", "", "", "sale", ""],
    "70代の母に クリスマス": ["christmas", "mother", "", "", "", ""],
    "予算は5000円〜8000円で、父の日": ["fathers-day", "", "5000-10000", "", "", ""],
    "お母さんに": ["", "mother", "", "", "", ""],
    "明日までに届く誕生日プレゼント": ["birthday", "", "", "", "urgent", ""],
    "引っ越し祝い 2万5千円": ["housewarming", "", "over20000", "", "", ""],
}
YENS = [("5000円", 5000), ("5千円", 5000), ("1万円", 10000), ("1.5万円", 15000), ("2万5千円", 25000), ("3,000円〜5,000円", 5000), ("70代", 0), ("3人で", 0), ("100円", 0), ("1000万円", 0)]


@unittest.skipUnless(CHROME, "Chrome is not installed")
class ReadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = real_data()
        data["themes"] = [{"s": "coffee-lover", "n": "コーヒー好き", "w": ["コーヒー", "ドリップ"]}] + data["themes"]
        js = (Path(build.__file__).parent / "assets" / "concierge.js").read_text(encoding="utf-8")
        page = (f"<!doctype html><meta charset='utf-8'><pre id='out'></pre><script>var DATA = {json.dumps(data, ensure_ascii=False)}; var SENTENCES = {json.dumps(SENTENCES, ensure_ascii=False)}; "
                f"var YENS = {json.dumps([y[0] for y in YENS], ensure_ascii=False)};</script><script>{js}</script><script>document.addEventListener('DOMContentLoaded', function () {{ {READ} }});</script>")
        tmp = Path(tempfile.mkdtemp(prefix="cc_read_"))
        try:
            (tmp / "p.html").write_text(page, encoding="utf-8")
            dom = run_chrome((tmp / "p.html").as_uri())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("no result: " + dom[:300])
        cls.out = json.loads(html_lib.unescape(m.group(1)))

    def test_no_script_error(self):
        self.assertNotIn("error", self.out)

    def test_sentences_are_read_into_event_person_budget_and_intent(self):
        for s, occ, rec, tier, amb, intent, theme in self.out["rows"]:
            if s in EXPECT:
                self.assertEqual([occ, rec, tier, amb, intent], EXPECT[s][:5], s)

    def test_a_sentence_with_only_an_interest_leads_to_a_theme(self):
        row = next(r for r in self.out["rows"] if r[0] == "カレーが好きな人に")
        self.assertEqual(row[1:3], ["", ""])                              # カレー is not 彼 / カレ
        row = next(r for r in self.out["rows"] if r[0] == "丈夫な傘を贈りたい")
        self.assertEqual(row[2], "")                                       # 丈夫 is not 夫

    def test_money_is_read_from_a_sentence_and_numbers_that_are_not_money_are_not(self):
        got = {s: v for s, v in self.out["yen"]}
        for s, want in YENS:
            self.assertEqual(got[s], want, s)


class ServerTwinTest(unittest.TestCase):
    def test_counter_keys_of_the_concierge_pass_and_a_free_text_key_does_not(self):
        for good in ("cq.need.who", "cq.occ.mothers-day", "cq.bud.3000-5000", "cq.res.miss", "cq.fb.no", "cq.why.w3"):
            self.assertTrue(ask_mock.STAT.match(good), good)
        for bad in ("cq.need.", "cq.TOOLONGKIND.x", "cq.text.母の日", "cq.a.b c", "cq.a." + "x" * 40):
            self.assertFalse(ask_mock.STAT.match(bad), bad)

    def test_a_voice_line_is_kept_and_the_unsafe_ones_are_refused(self):
        s = ask_mock.Store()
        ok = s.handle({"v": 1, "op": "voice", "k": "miss", "t": "  もっと小さな花を贈りたい  "})
        self.assertEqual(ok[0], 204)
        self.assertEqual(s.voices, [{"kind": "miss", "message": "もっと小さな花を贈りたい"}])
        self.assertEqual(s.stats.get("cq.voice.miss"), 1)
        for text in ("電話は09012345678です", "a@example.com まで", "https://example.com を見て", "〒520-0031 大津市", "x", "あ" * 81, "050-1234 のこと",
                     "０９０ー１２３４ー５６７８", "090 1234 5678", "090・1234・5678", "東京都渋谷区神南1-2-3", "大阪市北区梅田３丁目１番１号", "example.com/foo", "taro at example dot com",
                     "taro＠example.com", "０９０‐１２３４‐５６７８", "(090) 1234-5678"):
            code = s.handle({"v": 1, "op": "voice", "k": "miss", "t": text})[0]
            self.assertIn(code, (400, 422), text)
        for fine in ("母の日に、5000円くらいの花", "3000〜5000円で探しています", "1番人気のものがいい", "10000円以内で", "京都のお菓子がいい", "70代の父に", "第3位まで知りたい"):
            self.assertEqual(s.handle({"v": 1, "op": "voice", "k": "miss", "t": fine})[0], 204, fine)
        self.assertEqual(s.handle({"v": 1, "op": "voice", "k": "free", "t": "こんにちは"})[0], 400)       # a kind the page does not use
        self.assertEqual(len(s.voices), 1 + 7)                      # the sentences that were fine are kept too

    def test_the_php_receiver_has_the_same_voice_checks(self):
        php = (Path(build.__file__).parent / "ask_receiver.php.tpl").read_text(encoding="utf-8")
        for needle in ("$op === 'voice'", "limit($dir, 'voice', 12)", "array('miss', 'why', 'need', 'other')", "$n < 2 || $n > 80",
                       "filesize($f) > 1048576", "cq\\.[a-z]{1,6}\\.[a-z0-9_-]{1,32}", "0600", "function looks_personal", "mb_convert_kana", "if (looks_personal($t))"):
            self.assertIn(needle, php)
        self.assertNotIn("REMOTE_ADDR'] ?? '') . '|' . $t", php)           # the address is never written next to the text
        self.assertNotIn("'ip'", php)
        self.assertIn(r'$line . "\n", FILE_APPEND', php)                      # a real escape, not a line break inside the string


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        cls.files = build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_page_loads_the_script_and_the_data_file_is_built(self):
        self.assertIn('src="/assets/concierge.js"', (self.root / "index.html").read_text(encoding="utf-8"))
        data = json.loads((self.root / "concierge-data.json").read_text(encoding="utf-8"))
        self.assertIn("pairs", data)
        self.assertIn("birthday-mother", data["pairs"])

    def test_the_privacy_page_says_what_the_concierge_does_with_what_is_typed(self):
        html = (self.root / "privacy" / "index.html").read_text(encoding="utf-8")
        self.assertIn("贈り物コンシェルジュ", html)
        self.assertIn("送る", html)


FLOW = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '420px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(400); return f;
}
(async () => {
  try {
    let f = await load('/'); let d = f.contentDocument, w = f.contentWindow;
    const calls = []; const real = w.fetch.bind(w);
    w.fetch = (u, o) => { if (String(u).indexOf('/api/ask.php') >= 0) { calls.push(JSON.parse(o.body)); return Promise.resolve({ ok: true }); } return real(u, o); };
    const chip = (label) => [...d.querySelectorAll('.cc-chip:not(:disabled)')].find(b => b.textContent.indexOf(label) >= 0);
    d.querySelector('.cc-open').click(); await wait(500);
    out.topics = [...d.querySelectorAll('.cc-chip')].map(b => b.textContent);
    out.panel_open = !d.querySelector('.cc-panel').hidden;
    chip('贈る相手が').click(); await wait(100);
    out.rec_chips = [...d.querySelectorAll('.cc-chip:not(:disabled)')].map(b => b.textContent);
    chip('母').click(); await wait(100);
    out.occ_chips = [...d.querySelectorAll('.cc-chip:not(:disabled)')].map(b => b.textContent);
    chip('誕生日').click(); await wait(100);
    out.tier_chips = [...d.querySelectorAll('.cc-chip:not(:disabled)')].map(b => b.textContent);
    chip('3,000円以内').click(); await wait(150);
    out.link_hrefs = [...d.querySelectorAll('.cc-link')].map(a => a.getAttribute('href'));
    chip('見つからない').click(); await wait(100);
    out.why_chips = [...d.querySelectorAll('.cc-chip:not(:disabled)')].length;
    chip('予算に合わなかった').click(); await wait(100);
    const vi = d.querySelector('.cc-voice input'); vi.value = '3000円より安いものが見たい';
    d.querySelector('.cc-voice').dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(200);
    out.voice_calls = calls.filter(c => c.op === 'voice');
    out.stat_keys = calls.filter(c => c.op === 'stat').map(c => c.k[0]);
    out.thanks = (d.querySelector('.cc-voice') || {}).innerText;
    // a typed sentence that the site cannot read: the word is offered to Rakuten (a PR link) and may be sent, but not with a phone number
    d.querySelector('.cc-close').click();
    d.querySelector('.cc-open').click(); await wait(200);
    const before = calls.length;
    d.querySelector('.cc-form input').value = '金継ぎの器'; d.querySelector('.cc-form').dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(200);
    const aff = d.querySelector('.cc-link[rel~="sponsored"]');
    out.miss_aff = aff ? aff.getAttribute('href').indexOf('hb.afl.rakuten.co.jp/hgc/AFF.ID/trk?pc=') > 0 : false;
    out.miss_pr = aff ? aff.innerText.indexOf('広告(PR)') >= 0 : false;
    const vs = d.querySelectorAll('.cc-voice input'); const lastVoice = vs[vs.length - 1];
    out.preset = lastVoice.value;
    out.after_miss_calls = calls.slice(before).map(c => c.op + ':' + (c.k || ''));
    lastVoice.value = '連絡は 09012345678 へ';
    lastVoice.closest('form').dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(100);
    out.unsafe_error = [...d.querySelectorAll('.cc-err')].map(e => e.textContent).join('');
    out.voice_calls_after_unsafe = calls.filter(c => c.op === 'voice').length;
    // a typed sentence that names the page
    d.querySelector('.cc-form input').value = '母の日に、母へ 3000円くらい'; d.querySelector('.cc-form').dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(200);
    out.typed_links = [...d.querySelectorAll('.cc-link')].map(a => a.getAttribute('href'));
    // do not track: nothing is counted
    f = await load('/'); d = f.contentDocument; w = f.contentWindow;
    Object.defineProperty(w.navigator, 'doNotTrack', { value: '1', configurable: true });
    const calls2 = []; const real2 = w.fetch.bind(w); w.fetch = (u, o) => { if (String(u).indexOf('/api/ask.php') >= 0) { calls2.push(o.body); return Promise.resolve({ ok: true }); } return real2(u, o); };
    d.querySelector('.cc-open').click(); await wait(500);
    [...d.querySelectorAll('.cc-chip')].find(b => b.textContent.indexOf('セール') >= 0).click(); await wait(150);
    out.dnt_calls = calls2.length;
    out.sale_link = [...d.querySelectorAll('.cc-link')].map(a => a.getAttribute('href'));
  } catch (e) { out.error = String(e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        build.render_site(content.load(FIX), items, CFG, cls.root, release=True, today=date(2026, 5, 3))
        (cls.root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{FLOW}</script>', encoding="utf-8")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cls.root))
        handler.log_message = lambda *a, **k: None
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        cls.out = json.loads(html_lib.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_no_script_error(self):
        self.assertNotIn("error", self.out)

    def test_the_first_question_offers_seven_ways_to_say_what_is_the_trouble(self):
        o = self.out
        self.assertTrue(o["panel_open"])
        self.assertEqual(len(o["topics"]), 7)
        self.assertIn("そのほか(書いて伝える)", o["topics"])

    def test_the_questions_lead_to_the_page_with_the_budget_and_offer_only_what_exists(self):
        o = self.out
        self.assertIn("母", o["rec_chips"])
        self.assertIn("決まっていない", o["rec_chips"])
        self.assertEqual(sorted(x for x in o["occ_chips"] if x != "決まっていない"), sorted(["誕生日", "母の日"]))      # the events the mother has a page for (in the fixture)
        self.assertEqual(o["link_hrefs"][0], "/gift/birthday-mother/?b=under3000#browse")
        self.assertIn("/memo/?o=birthday&r=mother", o["link_hrefs"])

    def test_what_was_asked_is_counted_as_kinds_and_the_text_is_sent_only_by_the_send_button(self):
        o = self.out
        for key in ("cq.need.who", "cq.rec.mother", "cq.occ.birthday", "cq.bud.under3000", "cq.res.hit", "cq.fb.no", "cq.why.w1"):
            self.assertIn(key, o["stat_keys"])
        self.assertEqual(o["voice_calls"], [{"v": 1, "op": "voice", "k": "why", "t": "3000円より安いものが見たい"}])
        self.assertIn("送りました", o["thanks"])

    def test_a_sentence_the_site_cannot_read_is_offered_as_a_pr_search_and_a_phone_number_is_not_sent(self):
        o = self.out
        self.assertTrue(o["miss_aff"])
        self.assertTrue(o["miss_pr"])
        self.assertEqual(o["preset"], "金継ぎの器")
        self.assertEqual(o["after_miss_calls"], ["stat:cq.res.miss"])           # counted as a kind; the words are not sent until the visitor presses 送る
        self.assertIn("個人の情報", o["unsafe_error"])
        self.assertEqual(len(o["voice_calls"]), 1)
        self.assertEqual(o["voice_calls_after_unsafe"], 1)

    def test_a_typed_sentence_names_the_page_and_do_not_track_counts_nothing(self):
        self.assertTrue(any(h.startswith("/gift/mothers-day-mother/") for h in self.out["typed_links"]), self.out["typed_links"])
        self.assertEqual(self.out["dnt_calls"], 0)
        self.assertEqual(self.out["sale_link"], ["/sale/"])


if __name__ == "__main__":
    unittest.main()
