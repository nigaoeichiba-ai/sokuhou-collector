"""atomou: the member records' seal (PHP's format) and the e-mail notice sender (played against a fake SMTP)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import mail_send, members  # noqa: E402

KEY = bytes(range(32))
CFG = {"member_mail_from": "noreply@atomou.com", "site_url": "https://atomou.com", "operator_name": "株式会社MACS"}


class Seal(unittest.TestCase):
    def test_round_trip_and_layout(self):
        d = {"email": "a@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "m", "t": "歯医者 15:00"}]}}
        b64 = members.seal(d, KEY, iv=b"\x01" * 12)
        self.assertEqual(members.unseal(b64, KEY), d)
        import base64
        raw = base64.b64decode(b64)
        self.assertEqual(raw[:12], b"\x01" * 12)          # iv | tag | ciphertext, as api/m.php writes it
        self.assertIsNone(members.unseal(b64, bytes(32)))  # the wrong key gives nothing, not an exception
        self.assertIsNone(members.unseal("not base64!", KEY))
        self.assertIsNone(members.unseal(b64[:-4] + "AAAA", KEY))


class Sender(unittest.TestCase):
    def folder(self, recs):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        f = Path(td.name)
        (f / "m").mkdir()
        (f / "key").write_bytes(KEY)
        for name, d in recs.items():
            (f / "m" / f"{name}.json").write_text(members.seal(d, KEY) if isinstance(d, dict) else d, encoding="utf-8")
        return f

    def test_only_members_with_the_switch_on_and_a_line_today_get_one_mail(self):
        f = self.folder({
            "a" * 64: {"email": "a@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "m", "t": "歯医者 15:00"}, {"d": "2026-10-20", "s": "m", "t": "やること: 保険証(歯医者)"}]}},
            "b" * 64: {"email": "b@example.com", "notices": {"on": False, "dates": [{"d": "2026-10-20", "s": "m", "t": "x"}]}},   # switched off
            "c" * 64: {"email": "c@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "e", "t": "x"}]}},    # the evening slot
            "d" * 64: {"email": "d@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-21", "s": "m", "t": "x"}]}},    # tomorrow
            "e" * 64: "damaged",
        })
        sent = []

        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def send(self, msg):
                if msg["To"] == "fail@example.com":
                    raise RuntimeError("550")
                sent.append(msg)

        counts = mail_send.run(f, "2026-10-20", "m", CFG, smtp=Fake())
        self.assertEqual(counts, {"members": 4, "due": 1, "sent": 1, "failed": 0})
        msg = sent[0]
        self.assertEqual(msg["To"], "a@example.com")
        self.assertEqual(msg["From"], "あと何日、もう何日 <noreply@atomou.com>")
        self.assertEqual(msg["Subject"], "【あと何日、もう何日】10月20日の予定(2件)")
        body = msg.get_content()
        self.assertIn("・歯医者 15:00\n・やること: 保険証(歯医者)\n", body)
        self.assertIn("https://atomou.com/my/", body)
        self.assertIn("マイページでオフにしてください", body)
        self.assertIn("株式会社MACS", body)
        self.assertEqual(msg["Auto-Submitted"], "auto-generated")
        self.assertNotIn("http", body.replace("https://atomou.com", ""))   # no other links: not an advertisement

    def test_evening_subject_says_tomorrow_and_a_failure_does_not_stop_the_rest(self):
        f = self.folder({
            "a" * 64: {"email": "fail@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "e", "t": "x"}]}},
            "b" * 64: {"email": "b@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "e", "t": "明日 結婚記念日"}]}},
        })
        sent = []

        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def send(self, msg):
                if msg["To"] == "fail@example.com":
                    raise RuntimeError("550")
                sent.append(msg)

        counts = mail_send.run(f, "2026-10-20", "e", CFG, smtp=Fake())
        self.assertEqual((counts["due"], counts["sent"], counts["failed"]), (2, 1, 1))
        self.assertEqual(sent[0]["Subject"], "【あと何日、もう何日】明日の予定: 明日 結婚記念日")

    def test_dry_run_counts_only(self):
        f = self.folder({"a" * 64: {"email": "a@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "m", "t": "x"}]}}})
        self.assertEqual(mail_send.run(f, "2026-10-20", "m", CFG, dry_run=True)["sent"], 0)


class Weekly(Sender):
    def test_the_monday_digest_goes_only_to_members_who_switched_it_on(self):
        f = self.folder({
            "a" * 64: {"email": "a@example.com", "notices": {"on": True, "weekly": True, "dates": [{"d": "2026-10-19", "s": "m", "t": "会議"}, {"d": "2026-10-23", "s": "m", "t": "歯医者"}, {"d": "2026-10-30", "s": "m", "t": "先の予定"}]}},
            "b" * 64: {"email": "b@example.com", "notices": {"on": True, "dates": [{"d": "2026-10-20", "s": "m", "t": "x"}]}},                       # no weekly switch
            "c" * 64: {"email": "c@example.com", "notices": {"on": False, "weekly": True, "dates": [{"d": "2026-10-20", "s": "m", "t": "x"}]}},       # notices off
        })
        sent = []

        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def send(self, msg):
                sent.append(msg)

        counts = mail_send.run(f, "2026-10-19", "w", CFG, smtp=Fake())
        self.assertEqual((counts["due"], counts["sent"]), (1, 1))
        msg = sent[0]
        self.assertEqual(msg["To"], "a@example.com")
        self.assertIn("今週の予定(10月19日から)", msg["Subject"])
        body = msg.get_content()
        self.assertIn("・10月19日 会議\n・10月23日 歯医者\n", body)
        self.assertNotIn("先の予定", body)                      # beyond the 7 days
        self.assertIn("https://atomou.com/my/", body)
        self.assertIn("止めるときは、マイページでオフにしてください", body)
        self.assertNotIn("amazon", body.lower())
        self.assertNotIn("rakuten", body.lower())

    def test_lines_and_official_days(self):
        m = {"notices": {"on": True, "weekly": True, "dates": [{"d": "2026-10-19", "s": "m", "t": "A"}, {"d": "2026-10-19", "s": "e", "t": "A"}, {"d": "2026-10-26", "s": "m", "t": "B"}]}}
        self.assertEqual(mail_send.weekly_lines(m, "2026-10-19"), ["10月19日 A"])           # a line once, and 7 days only (the 26th is the next Monday)
        self.assertEqual(mail_send.weekly_lines({"notices": {"on": True, "dates": m["notices"]["dates"]}}, "2026-10-19"), [])
        entries = [{"id": "x1", "title": "近い日", "date": "2026-10-20", "precision": "day", "quiet": False, "status": "active"},
                   {"id": "x2", "title": "静かな日", "date": "2026-10-20", "precision": "day", "quiet": True, "status": "active"},
                   {"id": "x3", "title": "予想", "date": "2026-10-21", "precision": "day", "quiet": False, "status": "active", "estimated": True},
                   {"id": "x4", "title": "遠い日", "date": "2026-12-01", "precision": "day", "quiet": False, "status": "active"},
                   {"id": "x5", "title": "月だけ", "date": "2026-10-22", "precision": "month", "quiet": False, "status": "active"}]
        self.assertEqual([e["id"] for e in mail_send.official_days(entries, "2026-10-19")], ["x1"])


if __name__ == "__main__":
    unittest.main()
