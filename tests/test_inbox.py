import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sokuhou import inbox

ROOT = Path(__file__).resolve().parents[1]


def line(i, msg="こんにちは、確認のための文章です。", **over):
    return json.dumps({"id": f"a{i}", "at": "2026-10-07T08:00:00+09:00", "site": "yorokobu-present.com", "kind": "その他", "message": msg,
                       "email": "", "page": "", "who": "secret-hash", "ua": "x", **over}, ensure_ascii=False)


class TakeNewTest(unittest.TestCase):
    def test_only_lines_beyond_the_state_are_taken_and_the_state_advances(self):
        raw = "== 2026-10.jsonl\n" + line(1) + "\n" + line(2) + "\n"
        new, state = inbox.take_new(raw, {})
        self.assertEqual([r["id"] for r in new], ["a1", "a2"])
        self.assertEqual(state, {"2026-10.jsonl": 2})
        raw2 = raw + line(3) + "\n== 2026-11.jsonl\n" + line(4) + "\n"
        new, state = inbox.take_new(raw2, state)
        self.assertEqual([r["id"] for r in new], ["a3", "a4"])
        self.assertEqual(state, {"2026-10.jsonl": 3, "2026-11.jsonl": 1})
        self.assertEqual(inbox.take_new(raw2, state)[0], [])

    def test_private_fields_are_dropped_and_garbage_is_skipped(self):
        new, _ = inbox.take_new("== f.jsonl\nnot json\n" + line(1) + "\n" + json.dumps({"id": "z"}) + "\n", {})
        self.assertEqual(len(new), 1)
        self.assertNotIn("who", new[0])
        self.assertNotIn("ua", new[0])
        self.assertEqual(set(new[0]), set(inbox.FIELDS))

    def test_empty_dump_changes_nothing(self):
        self.assertEqual(inbox.take_new("", {"a": 3}), ([], {"a": 3}))


@unittest.skipUnless(shutil.which("openssl"), "openssl is not installed")
class EncryptionTest(unittest.TestCase):
    def test_a_message_encrypted_with_the_public_certificate_is_not_readable_without_the_key_and_round_trips_with_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            key, cert = tmp / "k.pem", tmp / "c.pem"
            r = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "2", "-subj", "//CN=t"],
                               capture_output=True, env={**__import__("os").environ, "MSYS_NO_PATHCONV": "1"})
            if r.returncode != 0:
                self.skipTest("openssl req failed here: " + r.stderr.decode()[:100])
            src, enc = tmp / "m.jsonl", tmp / "m.p7m"
            src.write_text(line(1, "秘密のメッセージ") + "\n", encoding="utf-8")
            subprocess.run(["openssl", "smime", "-encrypt", "-aes256", "-binary", "-in", str(src), "-out", str(enc), "-outform", "DER", str(cert)], check=True)
            self.assertNotIn("秘密".encode(), enc.read_bytes())
            self.assertEqual(inbox.decrypt(enc, key)[0]["message"], "秘密のメッセージ")

    def test_the_repository_certificate_exists_and_the_workflow_encrypts_with_it(self):
        self.assertTrue((ROOT / "sokuhou" / "inbox_cert.pem").read_text().startswith("-----BEGIN CERTIFICATE-----"))
        wf = (ROOT / ".github" / "workflows" / "inbox.yml").read_text(encoding="utf-8")
        self.assertIn("openssl smime -encrypt", wf)
        self.assertIn("sokuhou/inbox_cert.pem", wf)
        self.assertNotIn("PRIVATE KEY", wf)


class OwnerNoticeTest(unittest.TestCase):
    """The owner is told by a GitHub issue (e-mailed by GitHub) that something came; the issue lives in a PUBLIC repository, so it carries no message text."""

    def test_the_summary_has_site_count_and_kinds_only(self):
        recs = [json.loads(line(1, msg="ひみつの本文", email="a@example.com", page="/x/", kind="データの誤りのご指摘")),
                json.loads(line(2, msg="もうひとつの本文", kind="掲載内容に関するご連絡(掲載の中止のご依頼など)")),
                json.loads(line(3, msg="三つ目", kind="データの誤りのご指摘"))]
        out = inbox.summarize("kuma", recs)
        self.assertEqual(out, "kuma: 3件(データの誤りのご指摘 2件、掲載内容に関するご連絡(掲載の中止のご依頼など) 1件)")
        for secret in ("ひみつ", "本文", "a@example.com", "/x/", "secret-hash"):
            self.assertNotIn(secret, out)

    def test_the_command_prints_nothing_when_there_is_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "new.jsonl"
            f.write_text("", encoding="utf-8")
            r = subprocess.run(["python", "-m", "sokuhou.inbox", "summary", "--site", "kuma", "--file", str(f)], capture_output=True, cwd=ROOT)
            self.assertEqual((r.returncode, r.stdout), (0, b""))
            f.write_text(line(1) + chr(10), encoding="utf-8")
            r = subprocess.run(["python", "-m", "sokuhou.inbox", "summary", "--site", "kuma", "--file", str(f)], capture_output=True, cwd=ROOT)
            self.assertIn("kuma: 1件(その他 1件)", r.stdout.decode("utf-8"))

    def test_the_workflow_runs_hourly_opens_an_issue_from_the_summary_and_never_puts_message_text_in_it(self):
        wf = (ROOT / ".github" / "workflows" / "inbox.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "50 * * * *"', wf)
        self.assertIn("issues: write", wf)
        self.assertIn("gh issue create", wf)
        self.assertIn("sokuhou.inbox summary", wf)
        step = wf.split("gh issue create")[0].split("run: |")[-1]   # the shell of the notice step only (not its name)
        for forbidden in ("new_$site.jsonl", "raw_", "message", "email", ".p7m"):
            self.assertNotIn(forbidden, step)   # the issue body is built from notice.txt only
        self.assertIn("notice.txt", step)


if __name__ == "__main__":
    unittest.main()
