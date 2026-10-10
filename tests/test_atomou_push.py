"""atomou: push notifications — the encryption and VAPID (played against the browser's side), the day planner, the sender, the receiver's
template, the service worker, and the on-device planner in a real headless Chrome."""
import html
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest

import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

from sites.atomou import build, push_send, webpush  # noqa: E402
from tests.test_atomou_core_js import ASSETS, find_chrome  # noqa: E402

TODAY = date(2026, 10, 8)
CFG = {k: v for k, v in json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8")).items()}


def browser_subscription():
    """What a browser would hand over: its own P-256 key pair and a 16-byte auth secret."""
    k = ec.generate_private_key(webpush.CURVE)
    auth = webpush.b64u(bytes(range(16)))
    sub = {"endpoint": "https://push.example.net/send/abc123", "keys": {"p256dh": webpush.b64u(webpush.public_bytes(k.public_key())), "auth": auth}}
    return k, sub


class Crypto(unittest.TestCase):
    def test_message_round_trip_like_the_browser(self):
        k, sub = browser_subscription()
        body = webpush.encrypt("今日の予定があります。".encode("utf-8"), sub["keys"]["p256dh"], sub["keys"]["auth"])
        self.assertEqual(body[16:20], b"\x00\x00\x10\x00")   # rs 4096
        self.assertEqual(body[20], 65)                        # an uncompressed P-256 point follows
        self.assertEqual(webpush.decrypt(body, k, sub["keys"]["auth"]), "今日の予定があります。".encode("utf-8"))

    def test_rfc8291_example_vector(self):
        # RFC 8291 appendix A: the fixed keys and salt must produce exactly the ciphertext in the RFC
        ua_priv = webpush.b64u_decode("q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94")
        auth = "BTBZMqHH6r4Tts7J_aSIgg"
        salt = webpush.b64u_decode("DGv6ra1nlYgDCS1FRnbzlw")
        as_priv = webpush.b64u_decode("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw")
        ua_key = ec.derive_private_key(int.from_bytes(ua_priv, "big"), webpush.CURVE)
        as_key = ec.derive_private_key(int.from_bytes(as_priv, "big"), webpush.CURVE)
        body = webpush.encrypt(b"When I grow up, I want to be a watermelon", webpush.b64u(webpush.public_bytes(ua_key.public_key())), auth, salt=salt, server_key=as_key)
        expect = webpush.b64u_decode("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")
        self.assertEqual(body, expect)

    def test_vapid_token_verifies_with_the_public_key_and_names_the_push_service(self):
        priv, pub = webpush.generate_vapid()
        key = webpush.load_private_key(priv)
        token = webpush.vapid_token(key, "https://push.example.net", "https://atomou.com", now=1_700_000_000)
        claims = webpush.vapid_verify(token, webpush.public_key_from_bytes(webpush.b64u_decode(pub)))
        self.assertEqual(claims, {"aud": "https://push.example.net", "exp": 1_700_000_000 + 12 * 3600, "sub": "https://atomou.com"})
        self.assertEqual(webpush.audience_of("https://fcm.googleapis.com/fcm/send/xyz"), "https://fcm.googleapis.com")
        with self.assertRaises(ValueError):
            webpush.audience_of("http://plain.example/x")

    def test_pem_private_key_is_accepted_too(self):
        from cryptography.hazmat.primitives import serialization
        k = ec.generate_private_key(webpush.CURVE)
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        self.assertEqual(webpush.public_bytes(webpush.load_private_key(pem).public_key()), webpush.public_bytes(k.public_key()))

    def test_bad_subscription_keys_are_refused(self):
        with self.assertRaises(ValueError):
            webpush.encrypt(b"x", webpush.b64u(b"\x04" + b"\x00" * 10), webpush.b64u(b"\x00" * 16))
        with self.assertRaises(ValueError):
            webpush.encrypt(b"x" * 5000, *browser_subscription()[1]["keys"].values())


class Sender(unittest.TestCase):
    def folder(self, subs):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        for name, data in subs.items():
            (Path(td.name) / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return Path(td.name)

    def test_only_due_subscriptions_are_sent_and_dead_ones_are_listed(self):
        _, s1 = browser_subscription()
        _, s2 = browser_subscription()
        _, s3 = browser_subscription()
        s2["endpoint"] = "https://push.example.net/send/dead"
        s3["endpoint"] = "https://push.example.net/send/busy"
        f = self.folder({
            "a" * 64 + ".json": {**s1, "dates": [{"d": "2026-10-20", "s": "m"}, {"d": "2026-10-21", "s": "e"}]},
            "b" * 64 + ".json": {**s2, "dates": [{"d": "2026-10-20", "s": "m"}]},
            "c" * 64 + ".json": {**s3, "dates": [{"d": "2026-10-20", "s": "m"}]},
            "d" * 64 + ".json": {**s1, "dates": [{"d": "2026-10-20", "s": "e"}]},     # the evening slot: not now
            "e" * 64 + ".json": "{broken",
            "rate-20261020-abc": "3",
        })
        seen = []

        class Resp:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=0):
            seen.append(req)
            if req.full_url.endswith("/dead"):
                raise urllib.error.HTTPError(req.full_url, 410, "Gone", {}, io.BytesIO(b""))
            if req.full_url.endswith("/busy"):
                raise urllib.error.HTTPError(req.full_url, 503, "Busy", {}, io.BytesIO(b""))
            return Resp()

        priv, pub = webpush.generate_vapid()
        counts = push_send.run(f, "2026-10-20", "m", priv, opener=opener, public=pub)
        self.assertEqual(counts, {"subscriptions": 4, "due": 3, "sent": 1, "gone": 1, "retry": 1, "failed": 0, "key_matches_config": True})
        self.assertEqual((f / "gone.txt").read_text(), "b" * 64 + ".json\n")
        self.assertEqual(len(seen), 3)
        h = seen[0].headers
        self.assertEqual((h["Content-encoding"], h["Ttl"], h["Urgency"]), ("aes128gcm", "43200", "normal"))
        self.assertTrue(h["Authorization"].startswith("vapid t="))
        self.assertNotIn("endpoint", json.dumps(counts))

    def test_a_key_that_does_not_match_the_public_key_is_refused(self):
        _, s1 = browser_subscription()
        f = self.folder({"a" * 64 + ".json": {**s1, "dates": [{"d": "2026-10-20", "s": "m"}]}})
        other, _ = webpush.generate_vapid()
        with self.assertRaises(SystemExit):
            push_send.run(f, "2026-10-20", "m", other, opener=lambda *a, **k: None)
        self.assertFalse(push_send.run(f, "2026-10-20", "m", other, dry_run=True)["key_matches_config"])

    def test_payload_carries_only_the_day_and_slot(self):
        self.assertEqual(push_send.payload("2026-10-20", "e"), {"v": 1, "d": "2026-10-20", "s": "e"})

    def test_dry_run_sends_nothing_and_needs_no_key(self):
        _, s1 = browser_subscription()
        f = self.folder({"a" * 64 + ".json": {**s1, "dates": [{"d": "2026-10-20", "s": "m"}]}})
        counts = push_send.run(f, "2026-10-20", "m", None, dry_run=True)
        self.assertEqual((counts["due"], counts["sent"]), (1, 0))


class Receiver(unittest.TestCase):
    def test_template_stores_outside_the_web_root_and_only_known_fields(self):
        php = build.push_php()
        self.assertIn("dirname(__DIR__, 2)", php)                      # <site folder>, not public_html
        self.assertIn("'/push'", php)
        self.assertIn("hash('sha256', $endpoint)", php)                # file name = hash of the endpoint
        self.assertIn("preg_match('/^\\d{4}-\\d{2}-\\d{2}$/'", php)   # a date is a date
        self.assertIn("'endpoint' => $endpoint, 'keys' =>", php)
        for forbidden in ("title", "memo", "name", "REMOTE_ADDR' ] )"):
            self.assertNotIn("'" + forbidden + "'", php.replace("'endpoint'", ""))
        self.assertIn("if (!empty($d['off']))", php)                   # switching off deletes at once
        self.assertIn("http_response_code(429)", php)                  # a daily limit per sender
        self.assertRegex(php, r"preg_match\('#\^https://")            # only https endpoints

    def test_key_survives_a_careless_paste_and_a_bad_one_is_explained(self):
        priv, pub = webpush.generate_vapid()
        for wrapped in (priv, priv + "\r\n", "﻿" + priv, '"' + priv + '"', "​" + priv + " ", "  " + priv + "\n\n"):
            self.assertEqual(webpush.b64u(webpush.public_bytes(webpush.load_private_key(wrapped).public_key())), pub)
        with self.assertRaises(ValueError) as cm:
            webpush.load_private_key(priv + "　あ")
        msg = str(cm.exception)
        self.assertIn("U+3000", msg)
        self.assertIn("U+3042", msg)
        self.assertNotIn(priv, msg)                                 # the key itself is never printed

    def test_only_this_site_and_the_browsers_push_services_are_accepted(self):
        import re
        php = build.push_php({"site_url": "https://atomou.com/"})
        self.assertIn("$origin !== 'https://atomou.com'", php)         # the pages of this site only (as api/m.php)
        self.assertNotIn("__SITE_URL__", php)
        pat = re.search(r"preg_match\('#(\^https://\(\[A-Za-z0-9-\]\+\\.\)\*.*?)#', \$endpoint\)", php).group(1)
        for ok in ("https://fcm.googleapis.com/fcm/send/abc", "https://updates.push.services.mozilla.com/wpush/v2/abc",
                   "https://web.push.apple.com/QAbc", "https://wns2-par02p.notify.windows.com/?token=x", "https://updates-autopush.stage.mozaws.net/wpush/v2/a"):
            self.assertTrue(re.search(pat, ok), ok)
        for bad in ("https://evil.example.com/x", "https://fcm.googleapis.com.evil.example/x", "https://evilgoogleapis.com/x", "http://fcm.googleapis.com/x",
                    "https://169.254.169.254/latest/meta-data/", "https://push.apple.com@evil.example/x"):
            self.assertFalse(re.search(pat, bad), bad)

    def test_build_emits_the_receiver_and_the_service_worker_handlers(self):
        pages = build.build_pages({**CFG, "vapid_public": "BPublicKeyForTests_" + "x" * 60}, release=True, today=TODAY)
        self.assertIn("api/push.php", pages)
        sw = pages["sw.js"]
        self.assertIn("addEventListener('push'", sw)
        self.assertIn("addEventListener('notificationclick'", sw)
        self.assertIn("caches.open('atomou-notice')", sw)
        self.assertIn("showNotification(TITLE", sw)
        self.assertIn('id="push-box"', pages["my/index.html"])
        self.assertIn('id="push"', pages["privacy/index.html"])
        self.assertIn('"vapid":"BPublicKeyForTests_', pages["index.html"])

    def test_without_a_public_key_the_feature_is_absent(self):
        pages = build.build_pages({**CFG, "vapid_public": None}, release=True, today=TODAY)
        self.assertNotIn('id="push-box"', pages["my/index.html"])
        self.assertNotIn('"vapid"', pages["index.html"])
        self.assertNotIn('id="push"', pages["privacy/index.html"])


PLAN_PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['手続き・お金'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, vapid: 'BPublicKeyForTests' };
localStorage.setItem('atomou.v1', %(stored)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(plan)s"></script><script src="%(push)s"></script>
<script>var p = window.AtomouPush.plan([], [2026, 10, 8]); document.getElementById('out').textContent = JSON.stringify({ dates: p.dates, mirror: p.mirror, hash: p.hash, state: window.Atomou.state().prefs });</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class PlannerInChrome(unittest.TestCase):
    def run_page(self, stored: dict) -> dict:
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PLAN_PAGE % {"stored": json.dumps(json.dumps(stored, ensure_ascii=False)), **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "plan", "push")}}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-08"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_days_and_texts_follow_the_alarm_setting_and_the_tasks(self):
        stored = {"v": 1, "entries": [
            {"id": "a1", "title": "歯医者", "date": "2026-10-20", "precision": "day", "kind": "event", "time": "15:00", "alarm": "morning"},
            {"id": "a2", "title": "結婚記念日", "date": "2015-10-25", "precision": "day", "kind": "anniversary", "yearly": True, "alarm": "eve"},
            {"id": "a3", "title": "父の命日", "date": "2020-11-01", "precision": "day", "kind": "memorial", "yearly": True, "alarm": "none"},
            {"id": "a4", "title": "昔の日", "date": "2020-01-01", "precision": "day", "kind": "since", "alarm": "morning"},            # in the past: no knock
            {"id": "a5", "title": "遠い日", "date": "2030-01-01", "precision": "day", "kind": "until", "alarm": "week"},              # beyond the window
        ], "notes": {"m:a1": {"memo": "x", "tasks": [{"id": "t1", "before": 3, "text": "保険証を用意", "done": False}, {"id": "t2", "before": 1, "text": "済んだこと", "done": True}]}},
            "prefs": {"alarm": "morning", "push": True, "pushHash": "2026-10-01m"}}
        r = self.run_page(stored)
        # the yearly anniversary comes round twice within the 400 days of the window (2026-10-25 and 2027-10-25)
        self.assertEqual(r["dates"], [{"d": "2026-10-17", "s": "m"}, {"d": "2026-10-20", "s": "m"}, {"d": "2026-10-24", "s": "e"}, {"d": "2027-10-24", "s": "e"}])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-20|m"]], ["歯医者 15:00"])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-17|m"]], ["やること: 保険証を用意(歯医者)"])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-24|e"]], ["明日 結婚記念日"])
        self.assertEqual(r["mirror"]["2026-10-20|m"][0]["u"], "/plan/?key=m%3Aa1")
        self.assertNotIn("父の命日", json.dumps(r["mirror"], ensure_ascii=False))     # alarm "none"
        self.assertEqual(r["hash"], "2026-10-17m,2026-10-20m,2026-10-24e,2027-10-24e")
        self.assertEqual((r["state"]["push"], r["state"]["pushHash"]), (True, "2026-10-01m"))   # the two preferences survive the sanitiser

    def test_the_days_before_notices_are_planned_for_each_chosen_count_and_hostile_values_are_dropped(self):
        stored = {"v": 1, "entries": [
            {"id": "d1", "title": "旅行", "date": "2026-11-20", "precision": "day", "kind": "until", "alarm": "none"},
            {"id": "d2", "title": "静かな日", "date": "2026-11-20", "precision": "day", "kind": "memorial", "quiet": True, "alarm": "none"},
            {"id": "d3", "title": "夜に知らせる日", "date": "2026-11-25", "precision": "day", "kind": "until", "alarm": "none"},
            {"id": "d4", "title": "止めた日", "date": "2026-11-26", "precision": "day", "kind": "until", "alarm": "morning"},
            {"id": "d5", "title": "何も選ばない静かな日", "date": "2026-11-27", "precision": "day", "kind": "memorial", "quiet": True, "alarm": "none"}],
            "notes": {"m:d1": {"memo": "", "tasks": [], "remind": [30, 7, 1, 999, "x", 7, 45]},
                      "m:d2": {"memo": "", "tasks": [], "remind": [7]},
                      "m:d3": {"memo": "", "tasks": [], "remind": [3], "remindSlot": "e"},
                      "m:d4": {"memo": "", "tasks": [], "remind": [3], "mute": True}},
            "prefs": {"alarm": "morning", "push": True}}
        r = self.run_page(stored)
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-21|m"]], ["あと30日: 旅行"])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-11-19|m"]], ["明日 旅行"])
        days = {x["d"] + x["s"] for x in r["dates"]}
        self.assertNotIn("2026-10-06m", days)                                  # the custom 45 days before the 20th is already past: dropped
        self.assertEqual([l["t"] for l in r["mirror"]["2026-11-13|m"]], ["あと7日: 旅行", "あと7日: 静かな日"])   # a quiet day that asked for a notice gets it
        self.assertEqual([l["t"] for l in r["mirror"]["2026-11-22|e"]], ["あと3日: 夜に知らせる日"])             # the evening slot the visitor chose
        self.assertNotIn("止めた日", json.dumps(r["mirror"], ensure_ascii=False))                                # one switch turns every notice of the day off
        self.assertNotIn("何も選ばない静かな日", json.dumps(r["mirror"], ensure_ascii=False))                     # a quiet day that asked for nothing gets nothing

    def test_a_day_without_its_own_setting_follows_the_setting_on_the_my_page(self):
        # 2026-10-09 core check: changing "お知らせの時間" used to leave one's own days on the time they were created with
        stored = {"v": 1, "entries": [
            {"id": "b1", "title": "継ぐ日", "date": "2026-10-20", "precision": "day", "kind": "event", "alarm": ""},
            {"id": "b2", "title": "決めた日", "date": "2026-10-21", "precision": "day", "kind": "event", "alarm": "morning"},
            {"id": "b3", "title": "しない日", "date": "2026-10-22", "precision": "day", "kind": "event", "alarm": "none"}],
            "prefs": {"alarm": "eve", "push": True}}
        r = self.run_page(stored)
        self.assertEqual(r["dates"], [{"d": "2026-10-19", "s": "e"}, {"d": "2026-10-21", "s": "m"}])   # b1 the evening before (the setting), b2 its own, b3 none

    def test_the_hundred_day_marks_are_notified_and_a_yearly_day_in_every_turn(self):
        # 2026-10-09 Codex review: only ICS knew the 100-day marks, and a yearly day was planned for its next turn only
        stored = {"v": 1, "entries": [
            {"id": "c1", "title": "付き合った日", "date": "2026-07-01", "precision": "day", "kind": "anniversary", "every100": True, "alarm": "morning"},
            {"id": "c2", "title": "静かな日", "date": "2026-07-01", "precision": "day", "kind": "memorial", "quiet": True, "every100": True, "alarm": "morning"}],
            "prefs": {"alarm": "morning", "push": True}}
        r = self.run_page(stored)
        days = [x["d"] for x in r["dates"]]
        self.assertIn("2026-10-09", days)                    # the 100th day (2026-07-01 + 100)
        self.assertIn("2027-01-17", days)                    # the 200th
        self.assertIn("2027-08-05", days)                    # the 400th
        self.assertNotIn("2027-11-13", days)                 # the 500th is beyond the 400-day window (ends 2027-11-12)
        self.assertEqual([t["t"] for t in r["mirror"]["2026-10-09|m"]], ["付き合った日 から100日"])
        self.assertNotIn("静かな日 から100日", json.dumps(r["mirror"], ensure_ascii=False))     # a quiet day has no 100-day marks

    def test_hostile_preferences_are_reduced(self):
        r = self.run_page({"v": 1, "entries": [], "prefs": {"push": "yes", "pushHash": "<script>"}})
        self.assertEqual((r["state"]["push"], r["state"]["pushHash"]), (True, ""))


if __name__ == "__main__":
    unittest.main()


AFTER_SAVE_PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['手続き・お金'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, vapid: 'BPublicKeyForTests' };
localStorage.setItem('atomou.v1', %(stored)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><div id="plan"></div><script src="%(app)s"></script><script src="%(plan)s"></script><script src="%(push)s"></script>
<script>window.AtomouPush.afterSave(document.getElementById('plan'), %(quiet)s); %(extra)s var el = document.getElementById('after-save');
document.getElementById('out').textContent = JSON.stringify({ shown: !!el, text: el ? el.textContent : '', button: !!(el && el.querySelector('button')) });</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class AfterSaveInChrome(unittest.TestCase):
    IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"

    def run_page(self, ua: str, quiet: bool, extra: str = "") -> dict:
        stored = {"v": 1, "entries": [], "prefs": {}}
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(AFTER_SAVE_PAGE % {"stored": json.dumps(json.dumps(stored)), "quiet": "true" if quiet else "false", "extra": extra,
                                               **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "plan", "push")}}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                f"--user-agent={ua}", "--dump-dom", page.as_uri() + "?today=2026-10-08"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_iphone_safari_is_told_why_and_how_to_keep_the_day(self):
        # 2026-10-09 review: Safari removes script-written storage after about a week without a visit; the home-screen icon is exempt
        for quiet in (False, True):    # the same advice for a quiet (memorial) day: it is about not losing it
            r = self.run_page(self.IPHONE, quiet)
            self.assertTrue(r["shown"])
            self.assertIn("ホーム画面に追加", r["text"])
            self.assertIn("消えることがあります", r["text"])
            self.assertFalse(r["button"])                     # nothing to press: the steps are the share button's

    def test_a_browser_that_offers_to_install_gets_the_button(self):
        ev = "window.dispatchEvent(Object.assign(new Event('beforeinstallprompt', { cancelable: true }), { prompt: function () {}, userChoice: Promise.resolve({ outcome: 'dismissed' }) }));"
        desktop = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        r = self.run_page(desktop, False, ev)       # the event may come after the page was drawn
        self.assertTrue(r["shown"])
        self.assertIn("ホーム画面に追加", r["text"])
        self.assertTrue(r["button"])

    def test_a_browser_that_cannot_push_and_is_not_an_iphone_gets_no_card(self):
        # a file: page is not a secure context for the page's purposes (supported() is false), so nothing is offered and nothing breaks
        r = self.run_page("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36", False)
        self.assertFalse(r["shown"])


NIGHT_PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['手続き・お金'], slugs: ['deadline'], skins: { basic: { card: 'plain' }, dark: { card: 'plain', dark: true, attrs: {} }, sakura: { card: 'plain', attrs: {} } } };
var DARK = %(dark)s; window.matchMedia = function (q) { return { matches: DARK && /prefers-color-scheme:\s*dark/.test(q), addEventListener: function () {} }; };   // headless Chrome has no setting for the device's colour scheme
%(stored)s
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script>
<script>document.getElementById('out').textContent = JSON.stringify({ skin: document.documentElement.getAttribute('data-skin'), prefs: window.Atomou.state().prefs });</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class NightSkinInChrome(unittest.TestCase):
    def run_page(self, prefs: dict, dark_device: bool) -> dict:
        stored = {"v": 1, "entries": [], "prefs": prefs}
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            setter = "" if prefs is None else "localStorage.setItem('atomou.v1', " + json.dumps(json.dumps(stored)) + ");"   # None: a visitor who has stored nothing yet
            page.write_text(NIGHT_PAGE % {"stored": setter, "dark": "true" if dark_device else "false", **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app")}}, encoding="utf-8")
            args = [find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000"]
            r = subprocess.run(args + ["--dump-dom", page.as_uri() + "?today=2026-10-08"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_following_the_device_uses_the_night_skin_only_on_a_dark_device(self):
        # 2026-10-09: the owner asked for dark mode through the skins, not a new mechanism
        on = {"skin": "basic", "skinAuto": True, "skinNight": "dark"}
        self.assertEqual(self.run_page(on, True)["skin"], "dark")
        self.assertIsNone(self.run_page(on, False)["skin"])                      # a light device keeps the day skin
        self.assertIsNone(self.run_page({"skin": "basic"}, True)["skin"])        # not asked for: the page is never switched by itself
        r = self.run_page({"skin": "sakura", "skinAuto": True, "skinNight": "sakura"}, True)   # a night skin must be a dark one
        self.assertEqual(r["prefs"]["skinNight"], "dark")
        self.assertEqual(r["skin"], "dark")

    def test_a_fresh_visitor_has_the_night_preferences_too(self):
        for prefs in (None, {}):          # nothing stored yet (the blank state) and stored without them (the normaliser)
            r = self.run_page(prefs, False)
            self.assertEqual((r["prefs"]["skinAuto"], r["prefs"]["skinNight"], r["prefs"]["nightAsked"]), (False, "dark", False))
        r = self.run_page({}, False)
        self.assertEqual((r["prefs"]["skinAuto"], r["prefs"]["skinNight"], r["prefs"]["nightAsked"]), (False, "dark", False))
