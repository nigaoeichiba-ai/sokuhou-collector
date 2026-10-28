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


class AutoTagRedirects(unittest.TestCase):
    """A keyword page that has existed and falls out of the 150 biggest keywords gets a 301 by itself (2026-10-29: 介護 and 介護士 had gone the day before)."""

    ITEMS = [{"series": "care", "genre": "life"}] * 5 + [{"series": "other", "genre": "life"}]

    def run_(self, published, built, tagged_items, manual=None):
        return redirects.auto_tag_redirects(published, built, lambda t: f"/tag/{t}/", lambda t: tagged_items.get(t, []),
                                            {"care": "/series/care/", "other": "/series/other/"}, {"life", "food"}, manual or {})

    def test_a_dropped_keyword_goes_to_the_set_that_holds_most_of_its_pictures(self):
        out = self.run_(["介護"], set(), {"介護": self.ITEMS})
        self.assertEqual(out, {"tag/介護": "/series/care/"})

    def test_a_keyword_spread_over_sets_goes_to_its_genre_and_one_without_pictures_to_the_list(self):
        spread = [{"series": f"s{i}", "genre": "food"} for i in range(6)]
        self.assertEqual(self.run_(["a"], set(), {"a": spread}), {"tag/a": "/genre/food/"})
        self.assertEqual(self.run_(["b"], set(), {}), {"tag/b": "/tag/"})

    def test_a_keyword_that_still_has_its_page_or_has_a_hand_written_redirect_gets_nothing(self):
        self.assertEqual(self.run_(["介護"], {"/tag/介護/"}, {"介護": self.ITEMS}), {})
        self.assertEqual(self.run_(["介護"], set(), {"介護": self.ITEMS}, manual={"tag/介護": "/x/"}), {})

    def test_the_two_keywords_that_went_missing_have_rules_in_the_build_and_every_rule_is_sound(self):
        out, files = shared_site()
        ht = (out / ".htaccess").read_text(encoding="utf-8")
        for h in ("54b977088b", "8e2d07faa2"):
            self.assertRegex(ht, rf"RewriteRule \^tag/{h}\(/\.\*\)\?\$ /[a-z0-9/-]+/ \[R=301,L\]")
        pages = {f[: -len("index.html")].rstrip("/") for f in files if f.endswith("index.html")}
        for old, new in re.findall(r"RewriteRule \^([a-z0-9/-]+)\(/\.\*\)\?\$ (/[a-z0-9/-]*/) \[R=301,L\]", ht):
            self.assertNotIn(old, pages, old)
            self.assertIn(new.strip("/"), pages, f"{old} -> {new}")

    def test_the_published_list_has_no_duplicates_and_includes_the_two_keywords_that_went_missing(self):
        # Not a check that every page of the build is in the list: a new keyword page must not stop a deploy.  build.py --record-tags adds them.
        words = redirects.published_tags()
        self.assertEqual(len(words), len(set(words)))
        self.assertIn("介護", words)
        self.assertIn("介護士", words)


if __name__ == "__main__":
    unittest.main()
