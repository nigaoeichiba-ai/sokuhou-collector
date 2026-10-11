"""atomou: a change of a shared card is announced to the devices that asked (push slot s): who is due, nothing repeated, nothing but "updated" in the message,
the server's helper scripts (Python 3.6), the receiver template, the service worker, the opt-in on the my page and the workflow."""
import ast
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, push_send, webpush  # noqa: E402
from tests.test_atomou_push import browser_subscription  # noqa: E402

A, B, C = "A" * 22, "B" * 22, "C" * 22


def sub_file(extra):
    _, s = browser_subscription()
    return {**s, "dates": [], **extra}


class SharedDue(unittest.TestCase):
    def test_who_is_due(self):
        v = {A: 3, B: 1, C: 9}
        self.assertEqual(push_send.shared_due(sub_file({"watch": [{"id": A, "ver": 1, "sent": 0}]}), v), {A: 3})
        self.assertEqual(push_send.shared_due(sub_file({"watch": [{"id": A, "ver": 3, "sent": 0}]}), v), {})            # the device has seen it
        self.assertEqual(push_send.shared_due(sub_file({"watch": [{"id": A, "ver": 1, "sent": 3}]}), v), {})            # already announced
        self.assertEqual(push_send.shared_due(sub_file({"watch": [{"id": A, "ver": 1, "sent": 2}]}), v), {A: 3})        # a newer change than the announced one
        self.assertEqual(push_send.shared_due(sub_file({"watch": [{"id": "gone", "ver": 0}]}), v), {})                   # a card the server no longer has
        self.assertEqual(push_send.shared_due(sub_file({}), v), {})
        self.assertEqual(push_send.shared_due(sub_file({"watch": ["x", {"id": 5}, {"id": A, "ver": "bad"}]}), v), {})

    def test_the_message_says_only_that_something_changed(self):
        self.assertEqual(push_send.payload("2026-10-20", "s"), {"v": 1, "s": "u"})
        self.assertIn("s", push_send.SLOTS)


class Sending(unittest.TestCase):
    def folder(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, d in files.items():
            (Path(tmp.name) / name).write_text(json.dumps(d), encoding="utf-8")
        return Path(tmp.name)

    def test_only_the_due_get_a_message_and_it_is_written_down(self):
        sent = []

        class Resp:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=0):
            sent.append(req.full_url)
            return Resp()

        _, s1 = browser_subscription()
        _, s2 = browser_subscription()
        s1["endpoint"] = "https://push.example.net/send/one"
        s2["endpoint"] = "https://push.example.net/send/two"
        f = self.folder({"a" * 64 + ".json": {**s1, "dates": [], "watch": [{"id": A, "ver": 1, "sent": 0}]},
                         "b" * 64 + ".json": {**s2, "dates": [], "watch": [{"id": A, "ver": 4, "sent": 0}]}})
        priv, pub = webpush.generate_vapid()
        counts = push_send.run(f, "2026-10-20", "s", priv, opener=opener, public=pub, versions={A: 4})
        self.assertEqual((counts["due"], counts["sent"]), (1, 1))
        self.assertEqual(sent, ["https://push.example.net/send/one"])
        self.assertEqual(json.loads((f / "notified.json").read_text(encoding="utf-8")), {"a" * 64 + ".json": {A: 4}})
        self.assertNotIn("endpoint", json.dumps(counts))

    def test_nothing_due_writes_an_empty_note(self):
        f = self.folder({"a" * 64 + ".json": sub_file({"watch": [{"id": A, "ver": 4, "sent": 0}]})})
        counts = push_send.run(f, "2026-10-20", "s", None, dry_run=True, versions={A: 4})
        self.assertEqual(counts["due"], 0)
        self.assertEqual((f / "notified.json").read_text(encoding="utf-8"), "{}")


class ServerHelpers(unittest.TestCase):
    def test_python_3_6_syntax(self):
        for n in ("server_versions.py", "server_mark_sent.py"):
            ast.parse((ROOT / "sites/atomou" / n).read_text(encoding="utf-8"), feature_version=(3, 6))

    def run_script(self, name, home):
        env = {"HOME": str(home), "USERPROFILE": str(home), "PATH": __import__("os").environ.get("PATH", ""), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
        return subprocess.run([sys.executable, "-I", str(ROOT / "sites/atomou" / name)], capture_output=True, env=env, timeout=60, text=True, encoding="utf-8")

    def test_versions_lists_ids_and_numbers_only(self):
        with tempfile.TemporaryDirectory() as home:
            d = Path(home) / "atomou.com" / "shared"
            d.mkdir(parents=True)
            (d / f"c-{A}.json").write_text(json.dumps({"ver": 3, "ct": "secret-locked-text", "eh": "x"}), encoding="utf-8")
            (d / f"c-{B}.json").write_text(json.dumps({"ver": 2, "blocked": True}), encoding="utf-8")
            (d / "c-short.json").write_text("{}", encoding="utf-8")
            r = self.run_script("server_versions.py", home)
        self.assertEqual(json.loads(r.stdout), {A: 3})
        self.assertNotIn("secret", r.stdout)

    def test_mark_sent_sets_sent_and_removes_the_note(self):
        with tempfile.TemporaryDirectory() as home:
            d = Path(home) / "atomou.com" / "push"
            d.mkdir(parents=True)
            name = "a" * 64 + ".json"
            (d / name).write_text(json.dumps({"watch": [{"id": A, "ver": 1, "sent": 0}, {"id": B, "ver": 1, "sent": 0}]}), encoding="utf-8")
            (d / ".notified.json").write_text(json.dumps({name: {A: 4}, "../evil.json": {A: 1}}), encoding="utf-8")
            r = self.run_script("server_mark_sent.py", home)
            rec = json.loads((d / name).read_text(encoding="utf-8"))
            self.assertFalse((d / ".notified.json").exists())
        self.assertIn("marked 1", r.stdout)
        self.assertEqual([w["sent"] for w in rec["watch"]], [4, 0])


class Wiring(unittest.TestCase):
    def test_receiver_template_keeps_watch_and_sent(self):
        t = (ROOT / "sites/atomou/push_receiver.php.tpl").read_text(encoding="utf-8")
        self.assertIn("'watch' => array_values($watch)", t)
        self.assertIn("preg_match('/^[A-Za-z0-9_-]{22}$/'", t)
        self.assertIn("$watch[$o['id']]['sent'] = max(", t)
        self.assertIn("++$nw > 30", t)

    def test_service_worker_and_my_page_and_privacy(self):
        cfg = json.loads((ROOT / "sites/atomou/config.json").read_text(encoding="utf-8"))
        pages = build.build_pages(cfg, release=True)
        self.assertIn("d.s === 'u'", pages["sw.js"])
        self.assertIn('id="push-shared"', pages["my/index.html"])
        js = (ROOT / "sites/atomou/assets/push.js").read_text(encoding="utf-8")
        self.assertIn("prefs.pushShared", js)
        self.assertIn("watch: p.watch", js)
        self.assertIn("pushShared", (ROOT / "sites/atomou/assets/app.js").read_text(encoding="utf-8"))
        if cfg.get("vapid_public"):
            self.assertIn("共有カードが更新されたときも、通知する", pages["privacy/index.html"])

    def test_workflow_runs_slot_s_hourly_and_writes_back(self):
        wf = (ROOT / ".github/workflows/atomou-push.yml").read_text(encoding="utf-8")
        for needle in ('cron: "37 * * * *"', "server_versions.py", "server_mark_sent.py", "--versions versions.json", "notified.json"):
            self.assertIn(needle, wf)


if __name__ == "__main__":
    unittest.main()
