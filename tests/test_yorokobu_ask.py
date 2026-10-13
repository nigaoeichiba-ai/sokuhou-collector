"""The 「それとなく聞く」アンケート, the 診断ドック, the QR code and the diagnosis picture: the content file, the pages, the receiver's safeguards (PHP source), the push sender and the
scripts in a browser (against tests/ask_mock.py, the Python twin of the receiver)."""
import copy
import hashlib
import html as html_lib
import json
import os
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import askpages, askserver, askstats, ask_push, build, content, ogimage, relevance, webpush
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError
from tests import ask_mock
from tests.test_yorokobu_dataroom import CFG, inflated
from tests.test_yorokobu_e2e import CHROME, run_chrome
from tests.yorokobu_data import with_musts

CFG = {**CFG, "vapid_public": json.loads((build.HERE / "config.json").read_text(encoding="utf-8"))["vapid_public"]}

REAL_ASK = Path(build.HERE) / "content" / "ask.json"
FORBIDDEN = re.compile(r"プレゼント|ギフト|贈|誕生日|祝|サプライズ|present", re.I)


def ask_items(c: dict) -> dict:
    """Fixture products at many prices whose titles carry the words of the interest groups (so that every group has products), and of their ideas."""
    items = with_musts(inflated(copies=5), c)
    words = [spec["must"][0] for spec in c["ask"]["interests"].values()]
    n = 0
    for v in items["pairs"].values():
        for idea in v.get("ideas", []):
            for it in idea["items"]:
                n += 1
                it["name"] += " " + words[n % len(words)]
    return items


class AskContentTest(unittest.TestCase):
    def raw(self):
        return json.loads(REAL_ASK.read_text(encoding="utf-8"))

    def load_with(self, data: dict):
        with tempfile.TemporaryDirectory() as tmp:
            for f in (build.HERE / "content").iterdir():
                if f.is_file() and f.name != "ask.json":
                    (Path(tmp) / f.name).write_bytes(f.read_bytes())
            (Path(tmp) / "ask.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            (Path(tmp) / "daily").mkdir()
            return content._load_ask(Path(tmp))

    def test_the_real_file_is_sound_and_the_secret_mode_never_says_what_it_is_for(self):
        c = content.load()
        ask = c["ask"]
        self.assertEqual(len(ask["questions"]), 9)
        self.assertEqual(len(ask["interests"]), 18)
        for q in ask["questions"]:
            self.assertFalse(content.SECRET_FORBIDDEN.search(q["secret"]), q["id"])
            for o in q["options"]:
                self.assertFalse(content.SECRET_FORBIDDEN.search(o["label"]), o["id"])
        for k in ("title", "lead", "done"):
            self.assertFalse(content.SECRET_FORBIDDEN.search(ask["intro"]["secret"][k]), k)

    def test_a_secret_wording_that_gives_the_purpose_away_is_refused(self):
        for edit in (lambda d: d["questions"][0].__setitem__("secret", "プレゼントの参考に、休日の過ごし方を教えてください。"),
                     lambda d: d["intro"]["secret"].__setitem__("lead", "誕生日の準備のアンケートです。"),
                     lambda d: d["questions"][1]["options"][0].__setitem__("label", "贈り物にするコーヒー")):
            d = self.raw()
            edit(d)
            with self.assertRaises(BuildError):
                self.load_with(d)
        self.load_with(self.raw())                                                    # as written: fine

    def test_a_weight_for_an_unknown_group_or_on_the_avoid_or_budget_question_or_a_missing_option_is_refused(self):
        for edit in (lambda d: d["questions"][0]["options"][0].__setitem__("w", {"nonexistent": 2}),
                     lambda d: d["questions"][7]["options"][0].__setitem__("w", {"sweets": 1}),
                     lambda d: d["questions"][8]["options"].pop(),
                     lambda d: d["questions"][1]["options"][1].__setitem__("id", d["questions"][1]["options"][0]["id"]),
                     lambda d: d["questions"][0]["options"][0].__setitem__("w", {"sweets": 9}),
                     lambda d: d["interests"]["coffee_tea"].__setitem__("must", [])):
            d = self.raw()
            edit(d)
            with self.assertRaises(BuildError):
                self.load_with(d)


class AskServerTest(unittest.TestCase):
    ask = content.load()["ask"]
    php = askserver.ask_php({"site_url": "https://yorokobu-present.com/"}, ask)

    def test_the_receiver_has_its_safeguards(self):
        p = self.php
        self.assertTrue(p.startswith("<?php"))
        self.assertNotIn("__SITE_URL__", p)
        self.assertNotIn("__ASK__", p)
        self.assertIn('"q1":{"max":3,"o":["home","cafe"', p)                          # the questions and options of this site, and how many may be chosen at once
        self.assertIn('"q5":{"max":1,', p)                                            # a single choice takes one
        self.assertIn("$origin !== 'https://yorokobu-present.com'", p)                 # the pages of this site only
        self.assertIn("dirname(__DIR__, 2)", p)                                        # <site folder>, outside the web root
        for needle in ("hash_equals(", "hash('sha256', $key)", "idok(", "limit($dir, 'new', 20)", "limit($dir, 'ans', 60)", "limit($dir, 'read', 600)", "limit($dir, 'sub', 40)", "limit($dir, 'stat', 80)",
                       ">= 40) { $code = 429; }", "!isset($ASK[$q])", "in_array($x, $ASK[$q]['o'], true)", "count($c) > (int)$ASK[$q]['max']", "count($a) > 12", "strlen($raw) > 16384",
                       "$p['watch'] = $keep;", ">= 3000) { out(503); }", "if (!$watch) { @unlink($file); out(204); }", "$m['c'] < $cut", "array_slice($files, 0, 300)",
                       "'/^(dock\\.[a-z0-9]{1,8}\\.[a-z0-9_-]{1,32}|pop\\.[ra]\\.[A-Za-z0-9._:-]{3,64}|cq\\.[a-z]{1,6}\\.[a-z0-9_-]{1,32})$/'", "googleapis\\.com|push\\.services\\.mozilla\\.com", "if (!owns($meta, $x['key'] ?? ''))", "mt_rand(1, 40)", "120 * 86400", "if (flock($h, LOCK_EX)) {"):
            self.assertIn(needle, p, needle)
        self.assertEqual(p.count("REMOTE_ADDR"), 1)                                    # the address is only used for the daily hash of the limit
        self.assertNotIn("HTTP_USER_AGENT", p)
        self.assertNotIn("$_GET", p)
        self.assertNotIn("$_REQUEST", p)
        self.assertNotIn("mail(", p)                                                   # nobody's address is mailed from here
        self.assertIn("'kh' => hash('sha256', $key)", p)                               # only the hash of the key is stored
        self.assertNotIn("'key' => $key", p)

    def test_the_python_twin_enforces_the_same_rules(self):
        st = ask_mock.Store(askserver.allowlist(self.ask))
        i, k = "A" * 22, "B" * 22
        self.assertEqual(st.handle({"v": 1, "op": "new", "id": i, "key": k, "mode": "s"})[0], 204)
        self.assertEqual(st.handle({"v": 1, "op": "new", "id": i, "key": k})[0], 409)
        self.assertEqual(st.handle({"v": 1, "op": "new", "id": "short", "key": k})[0], 400)
        self.assertNotIn(k, json.dumps(st.surveys))                                    # the key itself is not kept
        self.assertEqual(st.handle({"v": 1, "op": "answer", "id": i, "a": {"q1": ["home", "cafe"]}})[0], 204)
        self.assertEqual(st.answers[i][0]["a"], {"q1": ["home", "cafe"]})
        for bad in ({"q99": ["home"]}, {"q1": ["fake"]}, {"q1": ["home", "BAD OPT"]}, {"q1": ["home", "cafe", "cook", "walk"]}, {"q5": ["useful", "design"]}, {"q1": []}, {}):
            self.assertEqual(st.handle({"v": 1, "op": "answer", "id": i, "a": bad})[0], 400, bad)   # an unknown question or option, too many, none: the whole answer is refused
        self.assertEqual(st.surveys[i]["n"], 1)                                          # and none of them was counted
        self.assertEqual(st.handle({"v": 1, "op": "answer", "id": "C" * 22, "a": {"q1": ["home"]}})[0], 404)
        self.assertEqual(st.handle({"v": 1, "op": "read", "id": i, "key": "C" * 22})[0], 403)    # a wrong key reads nothing
        code, out = st.handle({"v": 1, "op": "read", "id": i, "key": k})
        self.assertEqual((code, out["n"]), (200, 1))
        for _ in range(39):
            st.handle({"v": 1, "op": "answer", "id": i, "a": {"q1": ["home"]}})
        self.assertEqual(st.handle({"v": 1, "op": "answer", "id": i, "a": {"q1": ["home"]}})[0], 429)   # at most 40 answers
        self.assertEqual(st.handle({"v": 1, "op": "stat", "k": ["ask.q1.home"]})[0], 400)         # a client cannot count answers, only the dock
        self.assertEqual(st.handle({"v": 1, "op": "stat", "k": ["dock.occ.birthday", "x"]})[0], 204)
        self.assertEqual(st.handle({"v": 1, "op": "sub", "sub": {"endpoint": "https://evil.example/x", "keys": {}}})[0], 400)   # only the browsers' push services
        self.assertEqual(st.handle({"v": 1, "op": "del", "id": i, "key": "C" * 22})[0], 403)
        self.assertEqual(st.handle({"v": 1, "op": "del", "id": i, "key": k})[0], 204)

    def test_a_push_subscription_watches_only_the_surveys_its_owner_made_and_starts_from_the_answers_it_has(self):
        st = ask_mock.Store(askserver.allowlist(self.ask))
        i, k = "A" * 22, "B" * 22
        st.handle({"v": 1, "op": "new", "id": i, "key": k})
        for _ in range(3):
            st.handle({"v": 1, "op": "answer", "id": i, "a": {"q1": ["home"]}})
        ep = "https://fcm.googleapis.com/fcm/send/abc"
        sub = {"endpoint": ep, "keys": {"p256dh": "x" * 20, "auth": "y" * 20}}
        st.handle({"v": 1, "op": "sub", "sub": sub, "watch": [{"id": i, "key": k}, {"id": "D" * 22, "key": k}, {"id": i, "key": "C" * 22}]})
        self.assertEqual(st.subs[ep]["watch"], [{"id": i, "sent": 3}])                 # the unknown survey and the wrong key are not watched; no old answer is announced
        st.handle({"v": 1, "op": "sub", "sub": {**sub, "endpoint": "https://fcm.googleapis.com/fcm/send/empty"}, "watch": [{"id": "D" * 22, "key": k}]})
        self.assertNotIn("https://fcm.googleapis.com/fcm/send/empty", st.subs)         # nothing of the sender's to watch: nothing is kept
        st.handle({"v": 1, "op": "del", "id": i, "key": k})
        self.assertEqual(st.subs, {})                                                  # deleting the survey takes it out of the subscription, which then watches nothing and goes

    def test_the_sender_names_who_has_something_new_and_sends_nothing_without_the_matching_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ("a" * 64 + ".json")).write_text(json.dumps({"endpoint": "https://fcm.googleapis.com/x", "keys": {"p256dh": "k", "auth": "a"},
                                                                    "watch": [{"id": "A" * 22, "sent": 2}, {"id": "B" * 22, "sent": 5}]}), encoding="utf-8")
            (folder / ("b" * 64 + ".json")).write_text(json.dumps({"endpoint": "https://fcm.googleapis.com/y", "keys": {"p256dh": "k", "auth": "a"}, "watch": [{"id": "B" * 22, "sent": 5}]}), encoding="utf-8")
            (folder / "broken.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(len(ask_push.load(folder)), 2)
            subs = dict((p.name[0], s) for p, s in ask_push.load(folder))
            self.assertEqual(ask_push.due(subs["a"], {"A" * 22: 3, "B" * 22: 5}), {"A" * 22: 3})
            self.assertEqual(ask_push.due(subs["b"], {"A" * 22: 3, "B" * 22: 5}), {})
            counts = ask_push.run(folder, {"A" * 22: 3, "B" * 22: 5}, None, dry_run=True)
            self.assertEqual((counts["subscriptions"], counts["due"], counts["sent"]), (2, 1, 0))
            with self.assertRaises(SystemExit):
                ask_push.run(folder, {"A" * 22: 3}, None)                                  # something to send, but no key
            self.assertEqual(ask_push.payload(2), {"v": 1, "a": 1, "n": 2})              # the message carries no answer

    def test_the_counters_are_merged_by_month_and_only_valid_names_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "2026-09.json").write_text(json.dumps({"dock.occ.birthday": 3, "ask.q1.home": 2, "bad key": 9, "dock.n.all": 3}), encoding="utf-8")
            (Path(tmp) / "2026-10.json").write_text(json.dumps({"dock.occ.birthday": 4, "ask.n.all": 5, "ask.new.s": 1, "ask.q2.coffee": 4}), encoding="utf-8")
            (Path(tmp) / "x.json").write_text("{}", encoding="utf-8")
            m = askstats.merge(Path(tmp))
        self.assertEqual(sorted(m["months"]), ["2026-09", "2026-10"])
        self.assertEqual(m["total"]["dock.occ.birthday"], 7)
        self.assertNotIn("bad key", m["total"])
        text = askstats.report(m)
        self.assertIn("answers: 5", text)
        self.assertIn("q2: coffee 4", text)

    def test_the_web_push_encryption_is_the_one_the_atomou_site_tests(self):
        self.assertTrue(callable(webpush.send) and callable(webpush.load_private_key))
        self.assertEqual(webpush.b64u(b"\xfb\xff"), "-_8")


class AskPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.yorokobu import dataroom
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rows = (dataroom.MIN_ROWS, dataroom.MIN_PER_ROW)
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = 2, 8
        c = content.load()
        cls.items = ask_items(c)
        cls.root = Path(cls.tmp.name) / "site"
        build.render_site(c, cls.items, CFG, cls.root, release=True, today=date(2026, 10, 12))

    @classmethod
    def tearDownClass(cls):
        from sites.yorokobu import dataroom
        cls.tmp.cleanup()
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = cls.rows
        build.RANKING_ON = build.DATA_ON = False

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def test_the_pages_exist_the_private_ones_are_noindex_and_out_of_the_sitemap(self):
        for rel in ("ask/index.html", "ask/r/index.html", "ask/s/index.html", "ask/mine/index.html", "dock/index.html", "ask/rec.json", "dock/data.json", "api/ask.php", "sw.js"):
            self.assertTrue((self.root / rel).exists(), rel)
        sm = self.read("sitemap.xml")
        self.assertIn("/ask/</loc>", sm)
        self.assertIn("/dock/</loc>", sm)
        for p in ("/ask/r/", "/ask/s/", "/ask/mine/"):
            self.assertNotIn(p, sm)
            self.assertIn('content="noindex,nofollow"', self.read(p.strip("/") + "/index.html"), p)
        self.assertEqual([p for p in sitecheck.check_dir(self.root, CFG["site_url"], skip=("lists",)) if "ask" in p or "dock" in p], [])

    def test_the_secret_page_carries_no_word_of_what_it_is_for_and_no_site_name(self):
        s = self.read("ask/s/index.html")
        self.assertIsNone(FORBIDDEN.search(s), FORBIDDEN.search(s) and FORBIDDEN.search(s).group(0))
        self.assertNotIn("よろこぶ", s)
        self.assertNotIn("yorokobu", s)
        self.assertNotIn('rel="icon" href="/favicon', s)                                # the gift-box icon would tell
        self.assertNotIn("sale-bar", s)                                                  # the sale bar (an advertisement of the site's) never reaches the surprise page
        self.assertNotIn("セール", s)
        o = self.read("ask/r/index.html")
        self.assertIn("プレゼント", o)                                                  # the open mode says it
        self.assertNotIn("かんたんなアンケート</h1>\n<p class=\"ask-lead\" data-lead>プレゼント", o)

    def test_the_questions_and_options_are_the_ones_of_the_content_file(self):
        ask = content.load()["ask"]
        d = json.loads(html_lib.unescape(re.search(r'id="ask-respond"[^>]*data-json="([^"]*)"', self.read("ask/s/index.html")).group(1)))
        self.assertEqual([q["id"] for q in d["q"]], [q["id"] for q in ask["questions"]])
        self.assertEqual(d["q"][0]["text"], ask["questions"][0]["secret"])
        self.assertNotIn("w", d["q"][0]["options"][0])                                   # the weights stay on the results page

    def test_the_data_files_hold_only_products_of_their_group_and_numbers_of_this_build(self):
        rec = json.loads(self.read("ask/rec.json"))
        ask = content.load()["ask"]
        self.assertEqual(set(rec["groups"]), set(ask["interests"]))
        owners = {}
        for gid, g in rec["groups"].items():
            for it in g["items"]:
                self.assertTrue(it["u"].startswith("https://hb.afl.rakuten.co.jp/"), gid)
                owners.setdefault((it["n"], it["p"]), []).append(gid)
        self.assertTrue(all(len(v) == 1 for v in owners.values()), "a product is listed under one group only")
        self.assertGreaterEqual(sum(1 for g in rec["groups"].values() if g["items"]), 3)       # (the fixture has few shops, and a shop gives two products at most)
        dock = json.loads(self.read("dock/data.json"))
        self.assertEqual(len(dock["occasions"]), 24)
        self.assertEqual(len(dock["types"]), 8)
        self.assertEqual(set(dock["groups"]), set(askpages.RISK))
        self.assertTrue(all(0 < g["risk"] < 1 for g in dock["groups"].values()))
        mothers = next(o for o in dock["occasions"] if o["slug"] == "mothers-day")
        self.assertEqual(mothers["board"], "/data/mothers-day-budget/")
        self.assertEqual(mothers["dates"], ["2026-05-10", "2027-05-09"])

    def test_the_privacy_page_describes_what_the_survey_stores(self):
        p = self.read("privacy/index.html")
        for needle in ('id="ask"', "鍵を一方向に変換した値", "120日", "通知の宛先", "GitHub Actions", "回数をだれのものか分からない形で数えます"):
            self.assertIn(needle, p, needle)

    def test_the_tools_page_and_the_service_worker(self):
        t = self.read("tool/index.html")
        self.assertIn('href="/dock/"', t)
        self.assertIn('href="/ask/"', t)
        sw = self.read("sw.js")
        self.assertIn("addEventListener('push'", sw)
        self.assertNotIn("fetch", sw.replace("self.clients", ""))                        # no cache, no request handling: nothing to go stale

    def test_the_diagnosis_result_has_a_picture_to_keep(self):
        html = self.read("diagnosis/practical-steady/index.html")
        self.assertIn('href="/diagnosis/img/practical-steady.png" download=', html)
        self.assertIn("画像を送る", html)
        if ogimage.available():
            from PIL import Image
            with Image.open(self.root / "diagnosis" / "img" / "practical-steady.png") as im:
                self.assertEqual(im.size, (1080, 1350))

    def test_every_share_row_has_the_qr_button_which_a_script_shows_on_a_pc(self):
        html = self.read("data/christmas/index.html") if (self.root / "data/christmas/index.html").exists() else self.read("gift/christmas-girlfriend/index.html")
        self.assertIn('class="share-btn qr" hidden', html)
        self.assertTrue((self.root / "assets/qr.js").exists())


# ---------------------------------------------------------------------------------------------------- the scripts in a browser
SCENARIO = r"""
const out = {};
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const S = (u) => u.replace('https://yorokobu-present.com', location.origin);
async function load(url) {
  const f = document.createElement('iframe'); f.style.width = '800px'; f.style.height = '900px'; document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; }); await wait(500); return f;
}
async function sha(text) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join(''); }
(async () => {
  try {
    // ---- 1. make a survey (the secret mode)
    let f = await load('/ask/'), d = f.contentDocument, w = f.contentWindow; w.localStorage.clear();
    d.querySelector('input[name=mode][value=s]').checked = true;
    d.querySelector('[data-make]').click(); await wait(700);
    const link = d.querySelector('.ask-link').value;
    out.link = link; out.out_visible = !d.querySelector('.ask-out').hidden;
    out.line_ok = d.querySelector('[data-line]').href.startsWith('https://line.me/R/share?text='); out.mail_ok = d.querySelector('[data-mail]').href.startsWith('mailto:');
    out.say = d.querySelector('.ask-say').textContent;
    const mine = JSON.parse(w.localStorage.getItem('yorokobu.ask')); out.stored = [mine.length, mine[0].m, mine[0].key.length, mine[0].id.length];
    out.mine_href = d.querySelector('[data-mine]').getAttribute('href');
    // ---- 2. the other person answers
    f = await load(S(link)); d = f.contentDocument; w = f.contentWindow;
    out.respond = { title: d.title, h1: d.querySelector('.ask-h1').textContent, nq: d.querySelectorAll('.ask-q').length, gift: /プレゼント|ギフト|贈|祝|誕生日|サプライズ/.test(d.body.innerText) };
    out.submit_disabled_first = d.querySelector('.ask-form button').disabled;
    for (const v of ['home', 'cafe', 'cook', 'walk']) d.querySelector('[data-q=q1] input[value=' + v + ']').click();
    out.q1 = [d.querySelectorAll('[data-q=q1] input:checked').length, d.querySelectorAll('[data-q=q1] input:disabled').length];
    const r1 = d.querySelector('[data-q=q5] input[value=useful]'); r1.click(); const on1 = r1.checked; r1.click(); out.radio_toggle = [on1, r1.checked];
    d.querySelector('[data-q=q2] input[value=coffee]').click(); d.querySelector('[data-q=q8] input[value=scent]').click(); d.querySelector('[data-q=q9] input[value=b5000]').click();
    out.submit_enabled = !d.querySelector('.ask-form button').disabled;
    d.querySelector('.ask-form').dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(700);
    out.done = d.querySelector('[data-lead]').textContent; out.form_hidden = d.querySelector('.ask-form').hidden;
    f = await load(S(link)); out.reopen = f.contentDocument.querySelector('[data-lead]').textContent;
    f = await load('/ask/s/#nonsense'); out.bad_link = f.contentDocument.querySelector('[data-lead]').textContent;
    // ---- 3. two more answers, then the results
    for (const a of [{ q1: ['cafe', 'walk'], q2: ['coffee'], q4: ['beauty', 'kitchen'], q8: ['sweet'], q9: ['b2000'] }, { q1: ['home'], q2: ['alcohol'], q3: ['sweet'], q4: ['room'], q8: ['scent', 'allergy'], q9: ['b5000'] }])
      await fetch('/api/ask.php', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ v: 1, op: 'answer', id: mine[0].id, a }) });
    f = await load('/ask/mine/'); d = f.contentDocument; w = f.contentWindow;
    out.list_text = d.querySelector('.ask-list').textContent;
    f = await load('/ask/mine/#' + mine[0].id); d = f.contentDocument; w = f.contentWindow; await wait(1200);
    const det = d.querySelector('.ask-detail');
    out.detail = { n: (det.querySelector('.ask-sum b') || {}).textContent, bars: det.querySelectorAll('.ask-aq').length, lines: [...det.querySelectorAll('.ask-lines li')].map(l => l.textContent),
                   rec_groups: det.querySelectorAll('.ask-recgroup').length, cards: det.querySelectorAll('.ask-recgroup li.item').length, push_btn: !!det.querySelector('[data-push]'), notice: (det.querySelector('.notice') || {}).textContent || '' };
    out.rec_prices_under_budget = [...det.querySelectorAll('.ask-recgroup li.item .price')].map(p => Number(p.textContent.replace(/[^0-9]/g, ''))).every(p => p <= 5000);
    out.links_rel = [...det.querySelectorAll('.ask-recgroup a.btn')].every(a => /sponsored/.test(a.rel));
    // the analysis as a pure function
    const data = JSON.parse(d.querySelector('#ask-mine').getAttribute('data-json'));
    const A = w.YorokobuAsk.analyze(data.q, data.interests, [{ a: { q2: ['alcohol'], q8: ['scent'], q9: ['b20000'] } }, { a: { q2: ['alcohol'], q4: ['beauty'], q8: ['scent'], q9: ['b10000'] } }, { a: { q2: ['tea'], q8: ['none'], q9: ['bmore'] } }]);
    out.analysis = { n: A.n, top: A.ranked.slice(0, 3).map(r => r.id), zero: A.zero.sort(), budget: A.budget, has_beauty: A.ranked.some(r => r.id === 'beauty'), has_bath: A.ranked.some(r => r.id === 'bath_care') };
    const A0 = w.YorokobuAsk.analyze(data.q, data.interests, []); out.analysis_empty = [A0.n, A0.ranked.length, A0.budget];
    // the link to read the results on another device: it carries the key
    const key = mine[0].key; w.localStorage.clear();
    f = await load('/ask/mine/#' + mine[0].id + '.' + key); await wait(1200);
    out.imported = [JSON.parse(f.contentWindow.localStorage.getItem('yorokobu.ask')).length, f.contentWindow.location.hash === '#' + mine[0].id, (f.contentDocument.querySelector('.ask-sum b') || {}).textContent];
    // a wrong key reads nothing
    f.contentWindow.localStorage.setItem('yorokobu.ask', JSON.stringify([{ id: mine[0].id, key: 'Z'.repeat(22), m: 's', c: '2026-10-12' }]));
    f = await load('/ask/mine/#' + mine[0].id); await wait(900); out.wrong_key = f.contentDocument.querySelector('.ask-detail .notice') ? f.contentDocument.querySelector('.ask-detail .notice').textContent : '';
    // ---- 4. the dock
    const dock = await (await fetch('/dock/data.json')).json(), rec = await (await fetch('/ask/rec.json')).json();
    f = await load('/dock/'); w = f.contentWindow;
    const D = w.YorokobuDock, mothers = dock.occasions.find(o => o.slug === 'mothers-day');
    const rich = D.diagnose({ occ: 'mothers-day', date: '2026-11-12', gender: 'f', age: '60s', types: ['alone-time'], interests: ['coffee_tea', 'plants'], avoid: ['scent'], budget: String(mothers.range.med), memo: 'x' }, dock, rec, '2026-10-12');
    out.rich = { grade: rich.grade, total: rich.total, rows: rich.rows.map(r => [r.key, r.score, r.eval]), top: rich.top.map(t => t.id), days: rich.days, zero: rich.zero, target: rich.target };
    const empty = D.diagnose({ occ: '', date: '', gender: '', age: '', types: [], interests: [], avoid: [], budget: '', memo: '' }, dock, rec, '2026-10-12');
    out.empty = { grade: empty.grade, total: empty.total, rows: empty.rows.map(r => [r.key, r.score]), top: empty.top.length };
    const young = D.diagnose({ occ: 'birthday', date: '2026-10-13', age: 'u20', interests: ['alcohol', 'sweets'], avoid: ['sweet'], budget: '3000' }, dock, rec, '2026-10-12');
    out.young = { top: young.top.map(t => t.id), zero: young.zero.sort(), days: young.days, time: young.rows.find(r => r.key === 'time').score };
    const past = D.diagnose({ occ: 'christmas', date: '2026-10-01', interests: ['coffee_tea'], budget: '3000' }, dock, rec, '2026-10-12'); out.past = [past.days, past.rows.find(r => r.key === 'time').score];
    const val = D.diagnose({ occ: 'valentine', interests: [], budget: '2000' }, dock, rec, '2026-10-12'); out.valentine_top = val.top.map(t => t.id);
    out.counter_keys = D.counterKeys({ occ: 'mothers-day', age: '60s', gender: 'f', interests: ['coffee_tea'], types: ['alone-time'], avoid: ['scent'] }, rich).every(k => /^dock\.[a-z0-9]{1,8}\.[a-z0-9_-]{1,32}$/.test(k));
    out.counter_keys_sample = D.counterKeys({ occ: '', interests: [], types: [], avoid: [] }, empty);
    // the form, as a person uses it
    const form = f.contentDocument.querySelector('.dock-form'); form.elements.occ.value = 'christmas'; form.elements.budget.value = '5000';
    for (const v of ['coffee_tea', 'sweets', 'plants', 'alcohol', 'bath_care', 'beauty']) { const c = form.querySelector('input[name=int][value=' + v + ']'); c.click(); }
    out.int_limit = [form.querySelectorAll('input[name=int]:checked').length, form.querySelectorAll('input[name=int]:disabled').length];
    form.dispatchEvent(new w.Event('submit', { cancelable: true })); await wait(800);
    const sheet = f.contentDocument.querySelector('.dock-report');
    out.sheet = { shown: !sheet.hidden, rows: sheet.querySelectorAll('tbody tr').length, kinds: sheet.querySelectorAll('.sheet-kind').length, grade: (sheet.querySelector('.sheet-grade') || {}).textContent, tools: [...sheet.querySelectorAll('.sheet-tools button')].map(b => b.textContent), cards: sheet.querySelectorAll('li.item').length };
    // ---- 5. the QR code: the matrices of three addresses are the ones checked against a decoder
    await new Promise((ok, ng) => { const s = document.createElement('script'); s.src = '/assets/qr.js'; s.onload = ok; s.onerror = ng; document.head.appendChild(s); });
    out.qr = [];
    for (const t of ['https://yorokobu-present.com/ask/s/#DKaInIx8YITT5mvmYZI2IA', 'https://yorokobu-present.com/data/christmas/#christmas--budget', 'テスト', 'https://yorokobu-present.com/ask/mine/#DKaInIx8YITT5mvmYZI2IA.AbCdEfGhIjKlMnOpQrStUv']) {
      const q = window.YorokobuQR.build(t); out.qr.push([q.version, (await sha(q.modules.map(r => r.map(c => c ? '1' : '0').join('')).join(''))).slice(0, 16)]);
    }
    out.qr_svg = window.YorokobuQR.svg('https://yorokobu-present.com/').startsWith('<svg');
    out.qr_too_long = window.YorokobuQR.svg('x'.repeat(300));
  } catch (e) { out.error = String(e && e.stack || e); }
  document.getElementById('out').textContent = JSON.stringify(out);
})();
"""


@unittest.skipUnless(CHROME, "Chrome is not installed")
@unittest.skipIf(os.environ.get("CI") and not os.environ.get("RUN_E2E"), "browser checks run locally; CI must not be blocked by a browser quirk")
class AskBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.yorokobu import dataroom
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rows = (dataroom.MIN_ROWS, dataroom.MIN_PER_ROW)
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = 2, 8
        c = content.load()
        root = Path(cls.tmp.name) / "site"
        build.render_site(c, ask_items(c), CFG, root, release=True, today=date(2026, 10, 12))
        (root / "e2e.html").write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><script>{SCENARIO}</script>', encoding="utf-8")
        cls.server, cls.store = ask_mock.serve(root, 0, askserver.allowlist(c["ask"]))
        dom = run_chrome(f"http://127.0.0.1:{cls.server.server_address[1]}/e2e.html")
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if not m:
            raise AssertionError("the scenario produced no result: " + dom[:300])
        cls.out = json.loads(html_lib.unescape(m.group(1)))

    @classmethod
    def tearDownClass(cls):
        from sites.yorokobu import dataroom
        cls.server.shutdown()
        cls.tmp.cleanup()
        dataroom.MIN_ROWS, dataroom.MIN_PER_ROW = cls.rows
        build.RANKING_ON = build.DATA_ON = False

    def test_the_scenario_ran_to_the_end(self):
        self.assertNotIn("error", self.out, self.out.get("error"))
        self.assertIn("qr_too_long", self.out)

    def test_a_secret_survey_is_made_with_a_link_on_its_own_page_and_a_key_that_stays_on_the_device(self):
        o = self.out
        self.assertRegex(o["link"], r"^https://yorokobu-present\.com/ask/s/#[A-Za-z0-9_-]{22}$")
        self.assertTrue(o["out_visible"] and o["line_ok"] and o["mail_ok"])
        self.assertEqual(o["stored"], [1, "s", 22, 22])
        self.assertTrue(o["mine_href"].startswith("/ask/mine/#"))
        self.assertIsNone(FORBIDDEN.search(o["say"]), o["say"])                           # the text to send with it does not give the purpose away either
        calls = [c for c in self.store.calls if c[0] == "new"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["mode"], "s")

    def test_the_other_person_answers_by_choosing_only_and_cannot_send_it_twice_from_the_same_browser(self):
        o = self.out
        self.assertEqual(o["respond"]["h1"], "最近の好みについて")
        self.assertEqual(o["respond"]["nq"], 9)
        self.assertFalse(o["respond"]["gift"])
        self.assertTrue(o["submit_disabled_first"] and o["submit_enabled"])
        self.assertEqual(o["q1"], [3, 5])                                                  # three at most: the others are switched off
        self.assertEqual(o["radio_toggle"], [True, False])                                 # a single choice can be taken back
        self.assertIn("回答を受け取りました", o["done"])
        self.assertTrue(o["form_hidden"])
        self.assertIn("回答を受け取りました", o["reopen"])
        self.assertIn("正しくない", o["bad_link"])
        first = next(c for c in self.store.calls if c[0] == "answer")[1]["a"]
        self.assertEqual(first, {"q1": ["home", "cafe", "cook"], "q2": ["coffee"], "q8": ["scent"], "q9": ["b5000"]})

    def test_the_results_add_the_answers_up_and_read_them_without_inventing_numbers(self):
        o = self.out
        self.assertIn("回答 3件", o["list_text"])
        d = o["detail"]
        self.assertEqual(d["n"], "3")
        self.assertGreaterEqual(d["bars"], 6)
        text = " ".join(d["lines"])
        self.assertIn("香りが強いものは苦手と答えた人が2人", text)
        self.assertIn("食物アレルギーがあると答えた人が1人", text)
        self.assertIn("「5,000円まで」", text)
        self.assertGreaterEqual(d["rec_groups"], 2)
        self.assertGreater(d["cards"], 0)
        self.assertTrue(d["push_btn"])
        self.assertTrue(o["rec_prices_under_budget"])                                      # products are within the amount the people take easily
        self.assertTrue(o["links_rel"])
        a = o["analysis"]
        self.assertEqual(a["n"], 3)
        self.assertEqual(a["zero"], ["bath_care", "beauty"])                               # two of three avoid strong scents: baths and beauty are taken out
        self.assertFalse(a["has_beauty"] or a["has_bath"])
        self.assertEqual(a["top"][0], "alcohol")
        self.assertEqual(a["budget"], {"band": "b20000", "count": 3, "upper": 20000})        # the middle of 10,000 / 20,000 / more
        self.assertEqual(o["analysis_empty"], [0, 0, None])

    def test_a_link_to_the_results_carries_the_key_and_a_wrong_key_reads_nothing(self):
        o = self.out
        self.assertEqual(o["imported"], [1, True, "3"])
        self.assertIn("読めませんでした", o["wrong_key"])

    def test_the_dock_gives_a_report_whose_numbers_follow_from_the_input(self):
        o = self.out
        r = o["rich"]
        self.assertEqual(r["days"], 31)
        self.assertEqual(r["target"], "2026-11-12")                                        # the day typed, not the day before in a time zone east of Greenwich
        self.assertIn(r["grade"], ("A", "B"))
        rows = {k: s for k, s, _ in r["rows"]}
        self.assertEqual(rows["budget"], 100)                                              # a budget at the price median
        self.assertEqual(rows["time"], 100)                                                # 31 days to go
        self.assertEqual(r["zero"], ["bath_care", "beauty"])
        self.assertIn("plants", r["top"])
        e = o["empty"]
        self.assertIn(e["grade"], ("E", "—"))
        self.assertEqual([k for k, s in e["rows"] if s is None], ["budget", "time", "clarity", "risk"])    # what is not known is not scored
        self.assertEqual(e["top"], 0)
        y = o["young"]
        self.assertIn("alcohol", y["zero"])                                                # no alcohol for someone under twenty
        self.assertNotIn("alcohol", y["top"])
        self.assertEqual((y["days"], y["time"]), (1, 20))
        self.assertEqual(o["past"], [-11, 10])
        self.assertEqual(o["valentine_top"], ["sweets"])                                   # the survey says chocolate is what people want to give
        self.assertTrue(o["counter_keys"])
        self.assertEqual(o["counter_keys_sample"][:2], ["dock.n.all", "dock.occ.none"])
        s = o["sheet"]
        self.assertTrue(s["shown"])
        self.assertEqual(s["rows"], 5)
        self.assertEqual(o["int_limit"], [5, 13])                                          # five interests at most: the other thirteen are switched off
        self.assertGreaterEqual(s["kinds"], 1)
        self.assertEqual(s["tools"], ["印刷する", "画像で保存", "結果をコピー"])
        counted = [c for c in self.store.calls if c[0] == "stat"]
        self.assertEqual(len(counted), 1)                                                  # only the form's own submit counts (the pure calls above send nothing)
        self.assertFalse([k for k in counted[0][1]["k"] if re.search(r"\.[0-9]+$", k)])    # no typed value is sent: the amount only as a band (b5000)
        self.assertIn("dock.budget.b5000", counted[0][1]["k"])

    def test_the_qr_matrices_are_those_checked_against_a_decoder(self):
        self.assertEqual(self.out["qr"], [[4, "4a0aa1d2915366aa"], [4, "9346f2634c649809"], [1, "1ba6e451f4841d80"], [5, "193d4dd7009b9b01"]])
        self.assertTrue(self.out["qr_svg"])
        self.assertEqual(self.out["qr_too_long"], "")                                       # past what version 10 holds: nothing, not a wrong code


if __name__ == "__main__":
    unittest.main()
