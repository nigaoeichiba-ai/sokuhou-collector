"""Owner rule 2026-10-17: the repository is PUBLIC, so mall (Rakuten / Yahoo! / Amazon) product data and secrets must never be tracked here.
This test fails the build (and so the deploy) when a tracked data file holds mall product URLs or a tracked file holds a secret-like string.

KNOWN_PENDING lists the files that still hold mall data and are being moved to the server's private folder (the yorokobu session). The list may only shrink:
a file that is not on it must be clean, and a file on it that became clean must be taken off the list (so the list never hides new leaks)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# files that still hold Rakuten product URLs and are being moved out (2026-10-17). Remove each line when the file is clean.
KNOWN_PENDING = set()   # nothing is pending any more (2026-10-17: the daily picks and the features keep only the item code; the shop's data is read from the API at build time)

MIN_HITS = 1   # one mall product URL in a data file is already mall data
MALL = re.compile(
    r"item\.rakuten\.co\.jp/[A-Za-z0-9_.-]+/[A-Za-z0-9_.%-]+|thumbnail\.image\.rakuten\.co\.jp/@0_mall/|item-shopping\.c\.yimg\.jp/"
    r"|store\.shopping\.yahoo\.co\.jp/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+|amazon\.co\.jp/(?:dp|gp/product)/B0[A-Z0-9]{8}")
SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{30,}|\bAKIA[0-9A-Z]{16}\b"
    r"|(?i:application_?id|app_?id)[\"']?\s*[:=]\s*[\"']?\d{16,20}\b")
DATA_EXT = (".json", ".jsonl", ".csv", ".tsv", ".txt")


def tracked():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p]


def read(path):
    try:
        return (ROOT / path).read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def mall_hits(files):
    bad = {}
    for p in files:
        if p.startswith("tests/") or not p.endswith(DATA_EXT):
            continue
        n = len(MALL.findall(read(p)))
        if n >= MIN_HITS:
            bad[p] = n
    return bad


class NoMallDataInGit(unittest.TestCase):
    def test_no_new_mall_data_files(self):
        files = tracked()
        bad = mall_hits(files)
        new = {p: n for p, n in bad.items() if p not in KNOWN_PENDING}
        self.assertEqual(new, {}, "mall product data is tracked in the PUBLIC repository (owner rule, see 副業/CLAUDE.md): keep it in the server's private folder: " + str(new))

    def test_pending_list_only_shrinks(self):
        files = set(tracked())
        bad = mall_hits(files)
        stale = sorted(p for p in KNOWN_PENDING if p not in bad)
        self.assertEqual(stale, [], "these files are clean or gone now: remove them from KNOWN_PENDING in tests/test_no_mall_data_in_git.py: " + str(stale))

    def test_no_secrets_in_tracked_files(self):
        hits = []
        for p in tracked():
            if p.startswith("tests/") or p.endswith((".png", ".webp", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".woff2", ".p7m")):
                continue
            if SECRET.search(read(p)):
                hits.append(p)
        self.assertEqual(hits, [], "secret-like text is tracked in the PUBLIC repository: " + str(hits))

    def test_the_check_detects_a_leak(self):
        """negative test: the patterns must flag what they are meant to flag"""
        sample = '{"a":"https://item.rakuten.co.jp/shopx/item1/","b":"https://item.rakuten.co.jp/shopy/item2/","c":"https://thumbnail.image.rakuten.co.jp/@0_mall/s/a.jpg"}'
        self.assertGreaterEqual(len(MALL.findall(sample)), 3)
        self.assertTrue(SECRET.search("-----BEGIN OPENSSH PRIVATE KEY-----"))
        self.assertTrue(SECRET.search('applicationId = "1012345678901234567"'))
        self.assertFalse(SECRET.search("the password is changed"))


if __name__ == "__main__":
    unittest.main()
