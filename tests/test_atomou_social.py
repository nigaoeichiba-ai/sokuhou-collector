"""atomou daily posts: what is picked, how it reads, and that a quiet day or a secret never leaks."""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sites.atomou import catalog, social  # noqa: E402

BASE = "https://atomou.com"


class Posts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today = date(2026, 10, 12)       # a Monday
        cls.entries, _ = catalog.build_catalog(cls.today)

    def test_up_to_three_posts_with_facts_and_a_link_and_nothing_else(self):
        for k in range(0, 40):
            day = self.today + timedelta(days=k)
            posts = social.pick(self.entries, day, BASE)
            self.assertLessEqual(len(posts), 3)
            for p in posts:
                self.assertIn("https://atomou.com/", p["text"])
                self.assertLessEqual(len(p["text"]), 300, p["text"])
                for bad in ("おめでとう", "@", "#", "必ず", "絶対"):
                    self.assertNotIn(bad, p["text"])

    def test_a_quiet_day_is_never_posted(self):
        quiet = {e["title"] for e in self.entries if e["quiet"]}
        days = {e["id"] for e in social.public_days(self.entries, self.today)}
        self.assertFalse([e for e in self.entries if e["quiet"] and e["id"] in days])
        for k in range(0, 120):
            for p in social.pick(self.entries, self.today + timedelta(days=k), BASE):
                for t in quiet:
                    self.assertNotIn(t, p["text"])

    def test_monday_has_the_week_and_the_same_day_gives_the_same_posts(self):
        kinds = [p["kind"] for p in social.pick(self.entries, self.today, BASE)]
        self.assertIn("week", kinds)
        self.assertEqual(social.pick(self.entries, self.today, BASE), social.pick(self.entries, self.today, BASE))
        self.assertNotIn("week", [p["kind"] for p in social.pick(self.entries, self.today + timedelta(days=1), BASE)])

    def test_bluesky_link_ranges_are_byte_offsets_of_the_address(self):
        text = "日本語の本文。\nhttps://atomou.com/e/abc/"
        f = social.bluesky_facets(text)
        self.assertEqual(len(f), 1)
        raw = text.encode("utf-8")
        self.assertEqual(raw[f[0]["index"]["byteStart"]:f[0]["index"]["byteEnd"]].decode("utf-8"), "https://atomou.com/e/abc/")

    def test_nothing_is_sent_without_secrets(self):
        import io
        import os
        from contextlib import redirect_stdout
        for k in ("ATOMOU_BSKY_HANDLE", "ATOMOU_BSKY_APP_PASSWORD", "ATOMOU_MASTODON_BASE", "ATOMOU_MASTODON_TOKEN"):
            os.environ.pop(k, None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            social.main(["--today", "2026-10-12", "--out", os.devnull, "--post"])
        self.assertIn("no secrets, nothing sent", buf.getvalue())

    def test_the_workflow_only_reads_the_repository_and_sends_by_secrets(self):
        wf = (Path(__file__).resolve().parents[1] / ".github/workflows/atomou-social.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:", wf)
        self.assertIn("contents: read", wf)
        for bad in ("git push", "git commit", "contents: write"):
            self.assertNotIn(bad, wf)
        for k in ("ATOMOU_BSKY_HANDLE", "ATOMOU_BSKY_APP_PASSWORD", "ATOMOU_MASTODON_BASE", "ATOMOU_MASTODON_TOKEN"):
            self.assertIn("secrets." + k, wf)


if __name__ == "__main__":
    unittest.main()
