"""みんなのイラスト: the 301 redirects of URLs that are gone (sites/minna/redirects.py): every target is a page of the build, no source is (a redirect would hide a living page), and the rules are in .htaccess."""
import re
import unittest

from sites.minna import redirects
from tests.test_minna_sitecache import shared_site


class Redirects(unittest.TestCase):
    def pages(self) -> set[str]:
        out, files = shared_site()
        return {f[: -len("index.html")].rstrip("/") if f.endswith("index.html") else f for f in files if f.endswith(".html")}

    def test_every_target_is_a_page_of_the_build(self):
        have = self.pages()
        for old, new in redirects.REDIRECTS.items():
            self.assertTrue(new.startswith("/") and new.endswith("/"), new)
            self.assertIn(new.strip("/"), have, f"{old} -> {new}")

    def test_no_source_is_a_page_of_the_build_or_below_one(self):
        have = self.pages()
        for old in redirects.REDIRECTS:
            self.assertFalse(any(p == old or p.startswith(old + "/") for p in have), old)

    def test_no_target_is_itself_redirected_and_there_are_no_loops(self):
        for old, new in redirects.REDIRECTS.items():
            self.assertNotIn(new.strip("/"), redirects.REDIRECTS, new)
            self.assertNotEqual(old, new.strip("/"))

    def test_the_rules_are_in_htaccess_after_the_https_rule(self):
        out, _ = shared_site()
        ht = (out / ".htaccess").read_text(encoding="utf-8")
        self.assertIn("RewriteRule ^tag/7d1895fb2a(/.*)?$ /genre/work/ [R=301,L]", ht)
        self.assertLess(ht.index("https://%{HTTP_HOST}"), ht.index("^tag/7d1895fb2a"))
        for line in redirects.htaccess_lines().splitlines():
            self.assertRegex(line, r"^RewriteRule \^[a-z0-9/-]+\(/\.\*\)\?\$ /[a-z0-9/-]+/ \[R=301,L\]$")

    def test_a_rule_matches_the_old_url_with_and_without_a_page_number_and_not_a_longer_name(self):
        pat = re.compile(r"^tag/09e7384c81(/.*)?$")
        self.assertTrue(pat.match("tag/09e7384c81/"))
        self.assertTrue(pat.match("tag/09e7384c81/page/4/"))
        self.assertTrue(pat.match("tag/09e7384c81"))
        self.assertFalse(pat.match("tag/09e7384c81x/"))


if __name__ == "__main__":
    unittest.main()
