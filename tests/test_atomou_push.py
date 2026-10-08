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
window.ATOMOU = { v: 'x', groups: ['締切・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, vapid: 'BPublicKeyForTests' };
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
        self.assertEqual(r["dates"], [{"d": "2026-10-17", "s": "m"}, {"d": "2026-10-20", "s": "m"}, {"d": "2026-10-24", "s": "e"}])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-20|m"]], ["歯医者 15:00"])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-17|m"]], ["やること: 保険証を用意(歯医者)"])
        self.assertEqual([l["t"] for l in r["mirror"]["2026-10-24|e"]], ["明日 結婚記念日"])
        self.assertEqual(r["mirror"]["2026-10-20|m"][0]["u"], "/plan/?key=m%3Aa1")
        self.assertNotIn("父の命日", json.dumps(r["mirror"], ensure_ascii=False))     # alarm "none"
        self.assertEqual(r["hash"], "2026-10-17m,2026-10-20m,2026-10-24e")
        self.assertEqual((r["state"]["push"], r["state"]["pushHash"]), (True, "2026-10-01m"))   # the two preferences survive the sanitiser

    def test_hostile_preferences_are_reduced(self):
        r = self.run_page({"v": 1, "entries": [], "prefs": {"push": "yes", "pushHash": "<script>"}})
        self.assertEqual((r["state"]["push"], r["state"]["pushHash"]), (True, ""))


if __name__ == "__main__":
    unittest.main()
