import tempfile
import unittest
from pathlib import Path

from sokuhou import contactform, sitekit

ROOT = Path(__file__).resolve().parents[1]

CFG = {"site_url": "https://example.test", "site_name": "テストサイト", "operator_name": "テスト運営", "contact_own": True,
       "contact_kinds": ["データの誤りのご指摘", "ご意見・ご要望", "その他"], "adsense_pub_id": None}
_ASSETS = tempfile.TemporaryDirectory()
(Path(_ASSETS.name) / "style.css").write_text("body{}", encoding="utf-8")
SITE = {"nav": [("トップ", "/", "/")], "glyph": "", "assets": Path(_ASSETS.name), "source_html": ""}


class FormTest(unittest.TestCase):
    def test_form_posts_to_the_receiver_and_has_a_hidden_honeypot(self):
        html = contactform.form_html(CFG)
        self.assertIn('action="/contact/send.php" method="post"', html)
        self.assertIn('name="website"', html)
        self.assertIn("cf-hp", html)
        self.assertEqual(html.count("<option"), 3)
        self.assertIn('minlength="5" maxlength="2000"', html)
        self.assertNotIn("docs.google.com", html)

    def test_default_kind_is_selected(self):
        html = contactform.form_html(CFG, default_kind="その他")
        self.assertRegex(html, r'<option value="その他" selected>')

    def test_php_receiver_has_the_safeguards(self):
        php = contactform.send_php(CFG)
        self.assertTrue(php.startswith("<?php"))
        for needle in ("REQUEST_METHOD", "website", "in_array($kind, $KINDS, true)", "FILTER_VALIDATE_EMAIL", "LOCK_EX", "rate-", "random_bytes",
                       "dirname(__DIR__, 2)", "/inbox", "303"):
            self.assertIn(needle, php)
        self.assertIn("データの誤りのご指摘", php)
        self.assertNotIn("__KINDS__", php)
        self.assertNotIn("__THANKS__", php)
        self.assertIn("/contact/thanks.html", php)
        self.assertNotIn("REMOTE_ADDR'] ?? ''), 'email", php)   # the address is only ever hashed
        self.assertNotRegex(php, r"'ip'\s*=>")

    def test_english_solicitation_spam_is_dropped_before_it_is_stored_or_mailed(self):
        import re
        php = contactform.send_php(CFG)
        self.assertLess(php.index("\\p{Hiragana}"), php.index("file_put_contents($inbox"))
        self.assertLess(php.index("\\p{Hiragana}"), php.index("@mail($to,"))
        words = re.search(r'preg_match\("/(search index[^"]*?)/i"', php).group(1)
        jp = re.compile(r"[぀-ヿ一-鿿]")
        spam = ["Hello\n\nInclude example.com in Google's Search Index to show up in online search results!",
                "Hi,\n\nDo you have any plans to revamp your website? Website Design & Development, SEO and more."]
        for s in spam:
            self.assertFalse(jp.search(s))                                                   # no Japanese: dropped by the first test
        self.assertTrue(re.search(words, "Include a site in Google's Search Index", re.I))   # a solicitation phrase is dropped even with a Japanese word beside it
        real = "最低賃金の表で、沖縄県の金額が古いようです。"
        self.assertTrue(jp.search(real))
        self.assertFalse(re.search(words, real, re.I))                                       # a real report passes both tests

    def test_a_kind_with_a_quote_cannot_break_the_php_string(self):
        php = contactform.send_php({**CFG, "contact_kinds": ["it's", "b"]})
        self.assertIn(r"it\'s", php)

    def test_the_message_is_mailed_to_info_at_the_sites_domain_built_at_run_time(self):
        php = contactform.send_php(CFG)
        self.assertIn("$to = 'info@' . $domain;", php)
        self.assertIn("$domain = basename($site);", php)
        self.assertIn("@mail($to,", php)
        self.assertLess(php.index("file_put_contents($inbox"), php.index("@mail($to,"))     # the saved line is the record; the mail comes after it
        self.assertLess(php.index("@mail($to,"), php.rindex("header('Location: /contact/thanks.html'"))
        self.assertLess(php.index("$_POST['website']"), php.index("@mail($to,"))              # a honeypot hit sends nothing
        self.assertIn("'-f' . $to", php)
        self.assertIn("Reply-To", php)
        self.assertIn("FILTER_VALIDATE_EMAIL", php)                                           # the only visitor text that reaches a header is validated
        self.assertNotIn("__SITE__", php)
        self.assertIn("[テストサイト] お問い合わせ", php)
        self.assertNotRegex(php, r"[\w.-]+@[\w-]+\.(com|jp|net)")                              # no literal address in the generated file

    def test_a_site_name_cannot_break_the_php_string(self):
        php = contactform.send_php({**CFG, "site_name": "a'b\"c$d{e}" + chr(92) + "f" + chr(10) + "g"})
        self.assertIn("[abcdefg] お問い合わせ", php)

    def test_no_file_of_the_repository_contains_a_real_info_address(self):
        import subprocess
        out = subprocess.run(["git", "grep", "-nI", "-E", r"info@(yorokobu-present|minna-no-illust|kuma-sokuho|saichin-sokuho)\.com"], cwd=ROOT,
                             capture_output=True).stdout.decode("utf-8", "replace")
        self.assertEqual([x for x in out.splitlines() if "test_contactform.py" not in x], [])


class PagesTest(unittest.TestCase):
    def build(self, **over):
        cfg = {**CFG, **over}
        return sitekit.legal_pages(SITE, cfg, False, purpose="目的", sources_html="出典", update_text="毎日", disclaimer_html="<p>免責</p>", contact_notice="注意")

    def test_contact_page_is_the_own_form_and_the_files_come_along(self):
        pages = self.build()
        self.assertIn('action="/contact/send.php"', pages["contact/index.html"])
        self.assertIn("contact/send.php", pages)
        self.assertIn("contact/thanks.html", pages)
        self.assertNotIn("docs.google.com", pages["contact/index.html"])
        self.assertIn('<meta name="robots" content="noindex,nofollow">', pages["contact/thanks.html"])

    def test_thanks_page_is_not_in_the_sitemap_and_the_receiver_is_not_a_page(self):
        pages = self.build()
        sm = sitekit.standard_files(pages, CFG, False, "2026-10-07")["sitemap.xml"]
        self.assertIn("/contact/", sm)
        self.assertNotIn("thanks", sm)
        self.assertNotIn("send.php", sm)

    def test_privacy_policy_explains_the_form_data(self):
        priv = self.build()["privacy/index.html"]
        self.assertIn("お問い合わせフォームで取得する情報", priv)
        self.assertIn("元のIPアドレスには戻せません", priv)

    def test_a_site_with_the_old_google_form_is_unchanged(self):
        pages = self.build(contact_own=False, contact_form_url="https://docs.google.com/forms/d/e/x/viewform")
        self.assertIn("docs.google.com", pages["contact/index.html"])
        self.assertNotIn("contact/send.php", pages)
        self.assertNotIn("お問い合わせフォームで取得する情報", pages["privacy/index.html"])

    def test_release_needs_some_way_to_be_contacted(self):
        self.assertEqual(sitekit.missing_config({"operator_name": "x", "contact_own": True}), [])
        self.assertTrue(sitekit.missing_config({"operator_name": "x"}))


if __name__ == "__main__":
    unittest.main()
