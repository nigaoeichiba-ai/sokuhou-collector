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


AD_PREFIX = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788870&pid="


def external_links(folder: Path) -> list[str]:
    """Outside links that are not an approved advertisement of this site."""
    found = []
    for page in folder.rglob("*.html"):
        for href in re.findall(r'<a [^>]*href="(https?://[^"]+)"', page.read_text(encoding="utf-8")):
            if not href.startswith(BASE) and not href.startswith(AD_PREFIX):
                found.append(f"{page.name}: {href}")
    return found


def ad_links(folder: Path) -> list[str]:
    """Every advertisement anchor: [page: tag]."""
    found = []
    for page in folder.rglob("*.html"):
        for tag in re.findall(r'<a [^>]*href="' + re.escape(AD_PREFIX) + r'[^"]*"[^>]*>[^<]*</a>', page.read_text(encoding="utf-8")):
            found.append(f"{page.name}: {tag}")
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
            if re.fullmatch(r"google[0-9a-f]{16}\.html", page.name):
                continue
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

    def test_ownership_file_is_published_only_in_release_and_not_in_sitemap(self):
        proofs = [p for p in SITE.glob("google*.html")
                  if re.fullmatch(r"google[0-9a-f]{16}\.html", p.name)]
        self.assertTrue(proofs)
        sitemap = (self.rel / "sitemap.xml").read_text(encoding="utf-8")
        for proof in proofs:
            self.assertEqual((self.rel / proof.name).read_bytes(),
                             f"google-site-verification: {proof.name}\n".encode("utf-8"))
            self.assertFalse((self.rev / proof.name).exists())
            self.assertNotIn(proof.name, sitemap)

    def test_no_ad_link_and_no_outside_link_before_a_partnership_exists(self):
        self.assertEqual(external_links(self.rel), [])

    def test_the_only_advertisement_is_the_approved_one_with_pr_rel_target_and_a_word_as_text(self):
        ads = ad_links(self.rel)
        self.assertEqual(len(ads), 1, ads)
        page, tag = ads[0].split(": ", 1)
        self.assertEqual(page, "case-family-trip.html")
        self.assertIn('rel="nofollow sponsored noopener"', tag)
        self.assertIn('target="_blank"', tag)
        self.assertIn("pid=892753631", tag)
        text = re.sub(r"<[^>]+>", "", tag)
        self.assertNotIn("http", text)
        self.assertNotIn("JTB", text)                    # the advertiser's condition: no JTB wording of our own
        self.assertIn("PR（広告）", (self.rel / "case-family-trip.html").read_text(encoding="utf-8"))

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
        self.assertEqual(len(lines), (self.rel / "sitemap.xml").read_text(encoding="utf-8").count("<loc>"))   # one <loc> per line
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


FORBIDDEN = ("ファイナンシャルプランナー", "FP", "厚生労働省", "金利一覧", "試作", "サンプル", "〔アフィリ")   # 記事制作ルール 2026-11-20 and D26: no qualification, no source name, no production note
CONSULT_SLUGS = ("case-first-living", "case-childbirth-leave", "case-parent-care", "case-deposit-types")


def forbidden_in(text):
    return [w for w in FORBIDDEN if w in text]


def visible_text(html):
    html = re.sub(r"<(script|style).*?</>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


class ConsultArticlesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="moneyinfo_consult_"))
        cls.rb = load_release_build()
        cls.rb.build(cls.tmp / "release", None, review=False, own_contact=True)
        cls.rel = cls.tmp / "release"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, slug):
        return (self.rel / f"{slug}.html").read_text(encoding="utf-8")

    def test_the_four_articles_are_published_with_their_schedule_picture_and_lists(self):
        for slug in CONSULT_SLUGS:
            html = self.page(slug)
            self.assertIn("schedule-figure", html, slug)
            self.assertRegex(html, r'<img src="assets/timeline-[a-z-]+\.webp" alt="[^"]{10,}"', slug)   # the picture has a real alt text
            self.assertIn("<ul>", html, slug)
            self.assertIn("この記事の要点", html, slug)
            self.assertIn(f"{BASE}/{slug}.html", (self.rel / "sitemap.xml").read_text(encoding="utf-8"), slug)
            name = re.search(r'assets/(timeline-[a-z-]+\.webp)', html)
            self.assertTrue(name and (self.rel / "assets" / name[1]).exists(), slug)
            self.assertTrue((self.rel / "assets" / f"card-{slug[5:]}.webp").exists(), slug)      # the card and share picture

    def test_the_consultation_type_shows_a_budget_as_lists_not_as_a_run_of_numbers(self):
        for slug in ("case-first-living", "case-childbirth-leave", "case-parent-care"):
            html = self.page(slug)
            for heading in ("収入", "支出", "残りと資産"):
                self.assertRegex(html, rf"<h3>[^<]*{heading}[^<]*</h3>\s*<ul>", (slug, heading))

    def test_no_forbidden_word_no_source_name_no_decimal_yen_and_no_hidden_ad_marker(self):
        for slug in CONSULT_SLUGS:
            text = visible_text(self.page(slug))
            self.assertEqual(forbidden_in(text), [], slug)
            self.assertIsNone(re.search(r"\d+\.\d+円", text), slug)
            self.assertIn("2026年11月20日", text, slug)       # the date the amounts were checked
        self.assertNotIn("〔アフィリ", "".join(p.read_text(encoding="utf-8") for p in self.rel.rglob("*.html")))
        self.assertEqual(external_links(self.rel), [])      # no ad before the partnership of this site is approved

    def test_the_forbidden_word_check_finds_a_planted_word(self):
        self.assertEqual(forbidden_in("ファイナンシャルプランナーが提案します。厚生労働省の案内で確認"), ["ファイナンシャルプランナー", "厚生労働省"])
        self.assertEqual(forbidden_in("このご家庭の結論"), [])

    def test_the_home_the_list_and_the_planned_cases_know_the_new_articles(self):
        index, cases = self.page("index"), self.page("cases")
        for slug in CONSULT_SLUGS:
            self.assertIn(f'href="{slug}.html"', index, slug)
            self.assertIn(f'href="{slug}.html"', cases, slug)
        planned = cases.split("これから加えるモデルケース")[1]
        for published in ("初任給までの一人暮らしの準備", "育休から復職までの家計", "親と自分の家計を分けた準備"):
            self.assertNotIn(published, planned)       # a case that is published is not announced as "coming"

    def test_a_consult_card_shows_one_amount_and_one_condition_and_the_coming_cases_are_a_list(self):
        cases = self.page("cases")
        for slug in ("case-first-living", "case-childbirth-leave", "case-parent-care"):
            card = re.search(rf'<a class="case-index-card"[^>]*href="{slug}.html">(.*?)</a>', cases, re.S)[1]
            amount = re.search(r'case-card-amount">([^<]*)<', card)[1]
            self.assertEqual(len(re.findall(r"円", amount)), 1, amount)       # one amount, whole yen
            self.assertEqual(card.count("case-card-condition"), 1, slug)       # one condition line
        coming = cases.split("これから加えるモデルケース")[1]
        self.assertIn("進学（制作予定）", coming)
        self.assertIn("退職前後（制作予定）", coming)
        self.assertNotIn("planned-case\"", coming)                              # not cards any more

    def test_the_manuscript_check_never_leaves_a_planned_ad_place_on_the_screen(self):
        import consult_articles  # the module sits next to release_build.py (put on sys.path by load_release_build)
        slots = consult_articles.affiliate_slots()
        self.assertGreaterEqual(len(slots), 4)
        for _, text in slots:
            self.assertNotIn(text[:12], "".join(self.page(s) for s in CONSULT_SLUGS))


if __name__ == "__main__":
    unittest.main()
