"""IndexNow for every site (sokuhou/indexnow.py): keys, the key file, what is sent, and the order of the steps in the deploy workflow.

No network: the fetch and the POST go through a fake opener.
"""
import io
import json
import re
import tempfile
import unittest
import urllib.error
from pathlib import Path

from sokuhou import indexnow as ix

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://saichin-sokuho.com"
KEY = "0123456789abcdef0123456789abcdef"


def sitemap(*pairs):
    body = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>" for u, m in pairs)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


class FakeResponse:
    def __init__(self, status=200, body=b""):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeNet:
    """Answers GETs from a dict {url: bytes} and records every POST."""
    def __init__(self, pages=None, post_status=200):
        self.pages, self.posts, self.post_status = pages or {}, [], post_status

    def __call__(self, req, timeout=0):
        if req.get_method() == "POST":
            self.posts.append(json.loads(req.data.decode("utf-8")))
            if self.post_status >= 400:
                raise urllib.error.HTTPError(req.full_url, self.post_status, "x", {}, io.BytesIO())
            return FakeResponse(self.post_status)
        if req.full_url not in self.pages:
            raise urllib.error.URLError("not found")
        return FakeResponse(200, self.pages[req.full_url])


class KeysTest(unittest.TestCase):
    def test_every_public_site_has_a_valid_unique_key(self):
        keys = ix.load_keys()
        self.assertEqual(set(keys), {"saichin-sokuho.com", "kuma-sokuho.com", "yorokobu-present.com", "minna-no-illust.com"})
        self.assertEqual(len(set(keys.values())), 4)
        for key in keys.values():
            self.assertRegex(key, r"^[0-9a-f]{16,128}$")

    def test_minna_keeps_the_key_its_own_build_already_publishes(self):
        cfg = json.loads((ROOT / "sites" / "minna" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(ix.load_keys()["minna-no-illust.com"], cfg["indexnow_key"])

    def test_a_bad_key_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.json"
            for bad in ("XYZ", "abc", "g" * 32, "A" * 32, "a" * 200):
                p.write_text(json.dumps({"hosts": {"x.com": bad}}), encoding="utf-8")
                with self.assertRaises(ix.IndexNowError, msg=bad):
                    ix.load_keys(p)

    def test_an_unknown_host_or_a_malformed_base_is_refused(self):
        with self.assertRaises(ix.IndexNowError):
            ix.key_for("https://unknown.example", {"saichin-sokuho.com": KEY})
        for base in ("http://saichin-sokuho.com", "saichin-sokuho.com", "https://saichin-sokuho.com/path", ""):
            with self.assertRaises(ix.IndexNowError, msg=base):
                ix.host_of(base)


class KeyFileTest(unittest.TestCase):
    def test_the_key_file_holds_the_key_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as d:
            path = ix.prepare(Path(d), BASE, {"saichin-sokuho.com": KEY})
            self.assertEqual(path.name, f"{KEY}.txt")
            self.assertEqual(path.read_bytes(), KEY.encode())
            ix.prepare(Path(d), BASE, {"saichin-sokuho.com": KEY})                  # again: same result
            self.assertEqual(list(Path(d).iterdir()), [path])


class SitemapAndChangeTest(unittest.TestCase):
    def test_parse_reads_urls_and_lastmod_in_order(self):
        got = ix.parse_sitemap(sitemap((BASE + "/", "2026-10-12"), (BASE + "/a/", "")))
        self.assertEqual(list(got.items()), [(BASE + "/", "2026-10-12"), (BASE + "/a/", "")])

    def test_a_sitemap_index_and_broken_xml_are_refused_with_a_message(self):
        idx = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://x.com/s.xml</loc></sitemap></sitemapindex>'
        with self.assertRaises(ix.IndexNowError):
            ix.parse_sitemap(idx)
        with self.assertRaises(ix.IndexNowError):
            ix.parse_sitemap("<urlset><url>")
        with self.assertRaises(ix.IndexNowError):
            ix.parse_sitemap("")

    def test_new_urls_come_first_then_changed_newest_first_and_unchanged_never(self):
        prev = ix.parse_sitemap(sitemap((BASE + "/old/", "2026-10-01"), (BASE + "/same/", "2026-10-01"), (BASE + "/chg1/", "2026-10-01"), (BASE + "/chg2/", "2026-10-01")))
        new = ix.parse_sitemap(sitemap((BASE + "/old/", "2026-10-01"), (BASE + "/same/", "2026-10-01"), (BASE + "/chg1/", "2026-10-05"),
                                       (BASE + "/chg2/", "2026-10-09"), (BASE + "/n1/", "2026-10-12"), (BASE + "/n2/", "")))
        self.assertEqual(ix.changed(prev, new), [BASE + "/n1/", BASE + "/n2/", BASE + "/chg2/", BASE + "/chg1/"])

    def test_a_url_without_lastmod_is_never_reported_as_changed(self):
        prev = {BASE + "/a/": ""}
        self.assertEqual(ix.changed(prev, {BASE + "/a/": ""}), [])
        self.assertEqual(ix.changed({BASE + "/a/": "2026-10-01"}, {BASE + "/a/": ""}), [])

    def test_the_cap_keeps_the_newest_and_the_new(self):
        prev = {f"{BASE}/p{i}/": "2026-10-01" for i in range(50)}
        new = {f"{BASE}/p{i}/": f"2026-10-{(i % 28) + 1:02d}" for i in range(50)}
        new[BASE + "/brand-new/"] = "2026-10-12"
        got = ix.changed(prev, new, cap=5)
        self.assertEqual(len(got), 5)
        self.assertEqual(got[0], BASE + "/brand-new/")

    def test_a_site_that_claims_everything_changed_is_capped_not_flooded(self):
        prev = {f"{BASE}/p{i}/": "2026-10-11" for i in range(3000)}
        new = {f"{BASE}/p{i}/": "2026-10-12" for i in range(3000)}
        self.assertEqual(len(ix.changed(prev, new)), ix.DEFAULT_CAP)


class PayloadTest(unittest.TestCase):
    def test_a_good_payload(self):
        body = ix.payload(BASE, KEY, [BASE + "/", BASE + "/a/", BASE + "/"])
        self.assertEqual(body, {"host": "saichin-sokuho.com", "key": KEY, "keyLocation": f"{BASE}/{KEY}.txt", "urlList": [BASE + "/", BASE + "/a/"]})

    def test_urls_of_another_host_or_scheme_are_refused(self):
        for bad in ("https://kuma-sokuho.com/a/", "http://saichin-sokuho.com/a/", "https://saichin-sokuho.com.evil.example/a/", "//saichin-sokuho.com/a/"):
            with self.assertRaises(ix.IndexNowError, msg=bad):
                ix.payload(BASE, KEY, [BASE + "/", bad])

    def test_an_empty_list_and_a_bad_key_are_refused_and_the_list_is_capped_at_the_protocol_limit(self):
        with self.assertRaises(ix.IndexNowError):
            ix.payload(BASE, KEY, [])
        with self.assertRaises(ix.IndexNowError):
            ix.payload(BASE, "not-hex", [BASE + "/"])
        many = [f"{BASE}/p{i}/" for i in range(ix.MAX_URLS + 50)]
        self.assertEqual(len(ix.payload(BASE, KEY, many)["urlList"]), ix.MAX_URLS)


class PostTest(unittest.TestCase):
    def test_200_and_202_are_success_and_errors_raise(self):
        body = ix.payload(BASE, KEY, [BASE + "/"])
        self.assertEqual(ix.post(body, FakeNet(post_status=200)), 200)
        self.assertEqual(ix.post(body, FakeNet(post_status=202)), 202)
        for status in (400, 403, 422, 429):
            with self.assertRaises(ix.IndexNowError, msg=status):
                ix.post(body, FakeNet(post_status=status))


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.keys = {"saichin-sokuho.com": KEY}
        self._orig = ix.load_keys
        ix.load_keys = lambda path=ix.KEYS_FILE: self.keys

    def tearDown(self):
        ix.load_keys = self._orig
        self.tmp.cleanup()

    def release(self, *pairs):
        (self.root / "sitemap.xml").write_text(sitemap(*pairs), encoding="utf-8")

    def prev(self, *pairs):
        p = self.root / "prev.xml"
        p.write_text(sitemap(*pairs), encoding="utf-8")
        return str(p)

    def run_submit(self, net, *extra, prev=None):
        args = ["submit", "--root", str(self.root), "--base", BASE] + (["--prev", prev] if prev else []) + list(extra)
        return ix.main(args, net)

    def test_sends_only_what_changed_after_checking_that_the_key_file_is_live(self):
        self.release((BASE + "/", "2026-10-12"), (BASE + "/new/", "2026-10-12"), (BASE + "/same/", "2026-10-01"))
        net = FakeNet({f"{BASE}/{KEY}.txt": KEY.encode()})
        code = self.run_submit(net, prev=self.prev((BASE + "/", "2026-10-11"), (BASE + "/same/", "2026-10-01")))
        self.assertEqual(code, 0)
        self.assertEqual(len(net.posts), 1)
        self.assertEqual(net.posts[0]["urlList"], [BASE + "/new/", BASE + "/"])
        self.assertEqual(net.posts[0]["keyLocation"], f"{BASE}/{KEY}.txt")

    def test_nothing_is_sent_when_the_key_file_is_not_live_or_holds_another_key(self):
        self.release((BASE + "/", "2026-10-12"))
        prev = self.prev((BASE + "/", "2026-10-11"))
        for pages in ({}, {f"{BASE}/{KEY}.txt": b"someone-else"}):
            net = FakeNet(pages)
            self.assertEqual(self.run_submit(net, prev=prev), 1)
            self.assertEqual(net.posts, [])

    def test_without_a_previous_sitemap_nothing_is_sent(self):
        self.release((BASE + "/", "2026-10-12"))
        net = FakeNet({f"{BASE}/{KEY}.txt": KEY.encode()})
        self.assertEqual(self.run_submit(net), 0)
        self.assertEqual(self.run_submit(net, prev=str(self.root / "missing.xml")), 0)
        self.assertEqual(net.posts, [])

    def test_nothing_changed_means_nothing_sent(self):
        self.release((BASE + "/", "2026-10-11"))
        net = FakeNet({f"{BASE}/{KEY}.txt": KEY.encode()})
        self.assertEqual(self.run_submit(net, prev=self.prev((BASE + "/", "2026-10-11"))), 0)
        self.assertEqual(net.posts, [])

    def test_all_sends_every_url_once(self):
        self.release((BASE + "/", "2026-10-12"), (BASE + "/a/", ""))
        net = FakeNet({f"{BASE}/{KEY}.txt": KEY.encode()})
        self.assertEqual(self.run_submit(net, "--all"), 0)
        self.assertEqual(net.posts[0]["urlList"], [BASE + "/", BASE + "/a/"])

    def test_dry_run_sends_nothing_and_does_not_even_need_the_key_file(self):
        self.release((BASE + "/", "2026-10-12"))
        net = FakeNet()
        self.assertEqual(self.run_submit(net, "--dry-run", prev=self.prev((BASE + "/", "2026-10-11"))), 0)
        self.assertEqual(net.posts, [])

    def test_a_rejected_post_is_a_failure_exit_code_not_a_crash(self):
        self.release((BASE + "/", "2026-10-12"))
        net = FakeNet({f"{BASE}/{KEY}.txt": KEY.encode()}, post_status=403)
        self.assertEqual(self.run_submit(net, prev=self.prev((BASE + "/", "2026-10-11"))), 1)

    def test_a_site_without_a_key_fails_cleanly(self):
        self.release((BASE + "/", "2026-10-12"))
        self.keys = {}
        self.assertEqual(self.run_submit(FakeNet(), "--all"), 1)

    def test_snapshot_saves_a_real_sitemap_and_ignores_everything_else(self):
        out = self.root / "snap.xml"
        good = sitemap((BASE + "/", "2026-10-11"))
        self.assertEqual(ix.main(["snapshot", "--base", BASE, "--out", str(out)], FakeNet({BASE + "/sitemap.xml": good.encode()})), 0)
        self.assertEqual(len(ix.parse_sitemap(out.read_bytes())), 1)
        out.unlink()
        for pages in ({}, {BASE + "/sitemap.xml": b"<html>an error page</html>"}):
            self.assertEqual(ix.main(["snapshot", "--base", BASE, "--out", str(out)], FakeNet(pages)), 0)       # never fails the deploy
            self.assertFalse(out.exists())


class WorkflowTest(unittest.TestCase):
    """The deploy workflow must run the three IndexNow steps in the right places, and a failure of IndexNow must never fail a deploy."""
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        cls.names = re.findall(r"^      - name: (.+)$", cls.text, re.M)

    def index_of(self, needle):
        hits = [i for i, n in enumerate(self.names) if needle in n]
        self.assertEqual(len(hits), 1, f"{needle!r}: {hits}")
        return hits[0]

    def test_the_key_file_is_added_before_the_upload_and_the_old_sitemap_is_kept_before_the_upload(self):
        up = self.index_of("Upload and switch")
        self.assertLess(self.index_of("IndexNow key file"), up)
        self.assertLess(self.index_of("IndexNow previous sitemap"), up)

    def test_the_submission_comes_after_the_live_check(self):
        self.assertGreater(self.index_of("IndexNow submit"), self.index_of("Verify the live site"))

    def test_the_submission_cannot_fail_the_deploy_and_skips_atomou(self):
        block = self.text.split("- name: IndexNow submit", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("continue-on-error: true", block)
        self.assertIn("matrix.site != 'atomou'", block)
        self.assertIn("python -m sokuhou.indexnow submit", block)

    def test_the_key_file_and_the_snapshot_steps_also_skip_atomou_and_never_fail(self):
        for name in ("IndexNow key file", "IndexNow previous sitemap"):
            block = self.text.split(f"- name: {name}", 1)[1].split("\n      - name:", 1)[0]
            self.assertIn("matrix.site != 'atomou'", block, name)
        snap = self.text.split("- name: IndexNow previous sitemap", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("continue-on-error: true", snap)


if __name__ == "__main__":
    unittest.main()
