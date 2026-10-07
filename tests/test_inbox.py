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


if __name__ == "__main__":
    unittest.main()
