"""moneyinfo (kurashi-no-money.com, 暮らしのマネー情報): the release folder the deploy publishes, and the review folder that must stay out of search.

The site is a static output made by sites/moneyinfo/build.py (generate.py -> release_build.py).  These tests build it once and check what the
owner's rules and the deploy gates need: indexable only in a release, a sitemap/canonical/og/JSON-LD on every page, the site's own contact form
(the receiver is the shared sokuhou/contactform.py code), no ad link before a partnership exists, no heavy PNG, no source name shown on a page.
"""
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from sokuhou import contactform, sitecheck

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "moneyinfo"
BASE = "https://kurashi-no-money.com"


def load_release_build():
    spec = importlib.util.spec_from_file_location("moneyinfo_release_build", SITE / "release_build.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SITE))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(SITE))
    return mod


def external_links(folder: Path) -> list[str]:
    found = []
    for page in folder.rglob("*.html"):
        for href in re.findall(r'<a [^>]*href="(https?://[^"]+)"', page.read_text(encoding="utf-8")):
            if not href.startswith(BASE):
                found.append(f"{page.name}: {href}")
    return found


class MoneyinfoBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="moneyinfo_"))
        cls.rb = load_release_build()
        cls.rb.build(cls.tmp / "release", None, review=False, own_contact=True)
        cls.rb.build(cls.tmp / "review", None, review=True, own_contact=False)
        cls.rel, cls.rev = cls.tmp / "release", cls.tmp / "review"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_release_passes_the_site_check(self):
        self.assertEqual(sitecheck.check_dir(self.rel, BASE), [])

    def test_the_release_is_indexable_and_the_review_is_not(self):
        for page in self.rel.glob("*.html"):
            self.assertNotIn("noindex", page.read_text(encoding="utf-8"), page.name)
        for page in self.rev.glob("*.html"):
            self.assertIn("noindex,nofollow", page.read_text(encoding="utf-8"), page.name)
        self.assertIn("Disallow: /\n", (self.rev / "robots.txt").read_text(encoding="utf-8"))
        robots = (self.rel / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {BASE}/sitemap.xml", robots)

    def test_every_page_has_canonical_og_and_structured_data_and_is_in_the_sitemap(self):
        sitemap = (self.rel / "sitemap.xml").read_text(encoding="utf-8")
        for page in self.rel.glob("*.html"):
            html = page.read_text(encoding="utf-8")
            url = BASE + "/" if page.name == "index.html" else f"{BASE}/{page.name}"
            self.assertIn(f'<link rel="canonical" href="{url}">', html, page.name)
            self.assertIn('property="og:image"', html, page.name)
            self.assertIn("application/ld+json", html, page.name)
            self.assertIn(f"<loc>{url}</loc>", sitemap, page.name)
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
                json.loads(block)
        for jpg in re.findall(r'og:image" content="[^"]*/assets/shares/([^"]+)"', "".join(p.read_text(encoding="utf-8") for p in self.rel.glob("*.html"))):
            self.assertTrue((self.rel / "assets" / "shares" / jpg).exists(), jpg)

    def test_no_ad_link_and_no_outside_link_before_a_partnership_exists(self):
        self.assertEqual(external_links(self.rel), [])

    def test_the_outside_link_check_finds_a_planted_link(self):
        copy = self.tmp / "planted"
        shutil.copytree(self.rel, copy)
        page = copy / "index.html"
        page.write_text(page.read_text(encoding="utf-8").replace("</body>", '<a href="https://example.com/x">x</a></body>'), encoding="utf-8")
        self.assertEqual(external_links(copy), ["index.html: https://example.com/x"])

    def test_the_site_check_finds_a_broken_internal_link(self):
        copy = self.tmp / "broken"
        shutil.copytree(self.rel, copy)
        page = copy / "cases.html"
        page.write_text(page.read_text(encoding="utf-8").replace("</body>", '<a href="no-such-page.html">missing page</a></body>'), encoding="utf-8")
        self.assertTrue(any("no-such-page" in p for p in sitecheck.check_dir(copy, BASE)))

    def test_no_heavy_png_and_no_preview_wording_in_the_release(self):
        self.assertEqual([p.name for p in self.rel.rglob("*.png") if p.stat().st_size > 100_000], [])
        for page in self.rel.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("プレビュー", text, page.name)
            self.assertNotIn("確認画面", text, page.name)
        self.assertFalse((self.rel / "preview").exists())

    def test_the_contact_page_links_to_the_own_form_and_the_receiver_comes_along(self):
        contact = (self.rel / "contact.html").read_text(encoding="utf-8")
        self.assertIn(f'href="{BASE}/contact/"', contact)
        form = (self.rel / "contact" / "index.html").read_text(encoding="utf-8")
        self.assertIn('action="/contact/send.php"', form)
        self.assertIn('name="website"', form)     # the hidden honeypot
        self.assertIn("noindex", form)
        self.assertIn("Disallow: /contact/", (self.rel / "robots.txt").read_text(encoding="utf-8"))
        self.assertNotIn("/contact/", (self.rel / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((self.rel / "contact" / "thanks.html").exists())

    def test_the_receiver_is_the_shared_code_with_this_sites_choices(self):
        cfg = {"contact_kinds": self.rb.CONTACT_KINDS, "site_name": self.rb.SITE_NAME}
        self.assertEqual((self.rel / "contact" / "send.php").read_text(encoding="utf-8"), contactform.send_php(cfg))
        php = (self.rel / "contact" / "send.php").read_text(encoding="utf-8")
        for needle in ("website", "preg_match_all('~https?://~i'", "LOCK_EX", "info@"):
            self.assertIn(needle, php)
        for kind in self.rb.CONTACT_KINDS:
            self.assertEqual(kind, contactform._php_text(kind))   # nothing in a choice can end or alter the PHP string
        self.assertNotRegex(php, r"info@[a-z0-9-]+\.[a-z]")        # the address is built at run time, never printed

    def test_the_sitemap_has_one_loc_per_line_and_the_home_page_carries_the_marker(self):
        """deploy.yml's Verify step counts `grep -c '<loc>'` (lines, not tags) and greps the home page for the marker: a one-line sitemap counted 1 and rolled the first deploy back."""
        lines = [l for l in (self.rel / "sitemap.xml").read_text(encoding="utf-8").splitlines() if "<loc>" in l]
        entry = next(e for e in json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))["sites"] if e["name"] == "moneyinfo")
        self.assertEqual(len(lines), 20)
        self.assertGreaterEqual(len(lines), entry["min_pages"] - 5)
        self.assertIn(entry["marker"], (self.rel / "index.html").read_text(encoding="utf-8"))

    def test_the_release_has_what_the_deploy_step_demands(self):
        """deploy.yml's Build step fails without index.html and .htaccess, and with fewer pages than data/sites.json asks for (the first deploy failed on .htaccess)."""
        htaccess = (self.rel / ".htaccess").read_text(encoding="utf-8")
        self.assertIn("RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]", htaccess)
        reg = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
        entry = next(e for e in reg["sites"] if e["name"] == "moneyinfo")
        self.assertGreaterEqual(len(list(self.rel.rglob("*.html"))), entry["min_pages"])
        self.assertTrue((self.rel / "index.html").exists())

    def test_a_release_without_a_way_to_be_contacted_is_refused(self):
        with self.assertRaises(SystemExit):
            self.rb.build(self.tmp / "refused", None, review=False, own_contact=False)

    def test_the_build_does_not_overwrite_the_sources(self):
        with self.assertRaises(SystemExit):
            self.rb.build(SITE / "inside", None, review=True)


if __name__ == "__main__":
    unittest.main()
