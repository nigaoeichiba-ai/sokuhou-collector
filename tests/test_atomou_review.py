"""atomou: the review build (sites/atomou/review.py): small, reachable by a review crawler, not findable by the public, and silent about what is coming."""
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import articles, catalog, review  # noqa: E402

TODAY = date(2026, 10, 8)
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
# phrases that would tell a reviewer (or anyone) about the application, the members or the plans; none may appear in the visible text of the content pages
# (a bare "会員" or "通知" is no use: an academy's members and a tax office's notice are ordinary content)
SPOILERS = ("モニター", "マイページ", "カレンダーに入れ", "カレンダーに残", "きせかえ", "予定に入れ", "ホーム画面に追加", "ログイン", "この端末の中", "localStorage", "あなたの日", "自分の日",
            "記録する", "通知をオン", "お知らせします", "先着300", "無料でご利用")


def visible(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


class ReviewBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = review.build_pages(CFG, TODAY)
        cls.html = {k: v for k, v in cls.pages.items() if k.endswith(".html") and isinstance(v, str) and not k.startswith("google")}   # (a Search Console ownership file is a one-line text, not a page)

    def test_only_the_content_and_the_legal_pages_exist(self):
        for k in self.pages:
            ok = (k in ("index.html", "404.html", "robots.txt", "sitemap.xml", ".htaccess", "ads.txt", "favicon.ico", "apple-touch-icon.png")
                  or re.match(r"^(c/[a-z]+|e/[0-9a-f]{10}|about|privacy|contact)/index\.html$", k) or k in ("contact/send.php", "contact/thanks.html")
                  or k in review.ALLOWED_ASSETS or k.startswith("google"))
            self.assertTrue(ok, k)
        for absent in ("sw.js", "manifest.webmanifest", "my/index.html", "add/index.html", "calendar/index.html", "plan/index.html", "skins/index.html", "manual/index.html",
                       "api/m.php", "api/push.php", "api/e.php", "assets/app.js", "assets/atomou.js", "assets/push.js", "assets/member.js", "assets/catalog.json", "terms/index.html", "thanks/index.html"):
            self.assertNotIn(absent, self.pages)

    def test_every_page_is_noindex_and_robots_lets_only_the_adsense_crawler_in(self):
        for k, h in self.html.items():
            self.assertIn('<meta name="robots" content="noindex,nofollow">', h, k)
        robots = self.pages["robots.txt"]
        self.assertIn("User-agent: Mediapartners-Google\nDisallow:\n", robots)
        self.assertIn("User-agent: *\nDisallow: /\n", robots)
        self.assertNotIn("Sitemap:", robots)                       # nothing points a crawler at the sitemap (it only serves the deploy checks)

    def test_no_password_and_no_demo_banner(self):
        self.assertNotIn("AuthType", self.pages[".htaccess"])
        for k, h in self.html.items():
            self.assertNotIn("プレビュー版", h, k)

    def test_links_stay_inside_the_review_set(self):
        for k, h in self.html.items():
            for m in re.findall(r'href="(/[^"#?]*)', h):
                self.assertRegex(m, r"^/(c/[a-z]+/|e/[0-9a-f]{10}/|about/|privacy/|contact/|assets/.*|favicon\.ico|apple-touch-icon\.png|)$", f"{k}: {m}")

    def test_the_only_scripts_recount_the_cards(self):
        for k, h in self.html.items():
            srcs = re.findall(r'<script[^>]*src="([^"]*)"', h)
            own = [s for s in srcs if not s.startswith("https://pagead2.googlesyndication.com/")]   # the AdSense code is the one outside script (its crawler needs it on the review copy)
            self.assertTrue(set(own) <= {"/assets/core.js", "/assets/review.js"}, f"{k}: {srcs}")
            if k.startswith("e/") and 'class="notice quiet"' in h:
                self.assertEqual(own, srcs, f"{k}: a quiet day carries no ad code")
            self.assertNotIn("data-act=", h, k)                    # no "add to my days" buttons
            self.assertNotIn("window.ATOMOU", h, k)

    def test_the_wording_says_nothing_about_what_is_coming(self):
        for k, h in self.html.items():
            if k in ("privacy/index.html", "contact/index.html", "contact/thanks.html", "404.html"):
                continue                                           # the legal boilerplate speaks of mail addresses and Cookies, not of the application
            text = visible(h)
            for w in SPOILERS:
                self.assertFalse(w in text, f"{k}: {w}")      # (assertNotIn would print the whole page)

    def test_every_event_has_an_explanation_and_the_pages_differ(self):
        guides = articles.load_guides()
        subjects = {e["subject"] for e in catalog.build_catalog(TODAY)[0]}
        self.assertEqual(sorted(subjects - set(guides)), [], "a subject without a guide gets no explanation")
        bodies = {}
        for k, h in self.html.items():
            if not k.startswith("e/"):
                continue
            self.assertIn('<section class="article"', h, k)
            text = visible(re.search(r'<section class="article".*?</section>', h, flags=re.S).group(0))
            self.assertGreater(len(re.sub(r"\s+", "", text)), 450, k)
            bodies[k] = re.sub(r"\s+", "", text)
        # the explanation of two events of one subject shares the guide's sentences, but never the whole text: facts of the event differ
        self.assertEqual(len(set(bodies.values())), len(bodies))

    def test_the_cards_carry_a_count_and_a_link(self):
        home = self.pages["index.html"]
        self.assertGreaterEqual(home.count('class="card'), 12)
        self.assertNotIn('<span class="num"></span>', home)
        self.assertIn('href="/e/', home)

    def test_the_deploy_ssh_setup_survives_a_dropped_key_scan(self):
        # runs 90, 91 and 97 lost the server for minutes (it drops simultaneous connections): each site starts at its own offset, the job waits for the server and records the host key itself
        wf = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        start = wf.index("      - name: SSH setup\n")
        run = wf[start: wf.index("\n      - name:", start + 10)]
        self.assertIn("ConnectionAttempts 2", run)
        self.assertIn("server not reachable (attempt", run)   # it waits for the server (run 97: one job could not connect for 5 minutes)
        self.assertIn('[ "$reached" = 1 ]', run)
        self.assertIn("StrictHostKeyChecking accept-new", run)
        self.assertNotIn("test -s ~/.ssh/known_hosts", run)   # an empty scan no longer fails the job

    def test_the_deploy_job_has_the_review_switch_and_hides_the_demo_behind_its_password(self):
        wf = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn("vars.ATOMOU_REVIEW == 'true' && '--review'", wf)
        self.assertIn('[ "$ATOMOU_PUBLIC" != "true" ] && { [ -z "$DEMO_USER" ] || [ -z "$DEMO_PASS" ]; }', wf)   # no password, no atomou deploy, review copy or not
        self.assertIn("vars.ATOMOU_PUBLIC != 'true' && (github.event_name != 'workflow_dispatch' || inputs.deploy)", wf)   # the password file is written in both modes
        self.assertIn("python sites/atomou/build.py --demo-sub --out demo_build", wf)
        self.assertIn('for d in demo demo.atomou.com; do mkdir -p "release/$d"; cp -a demo_build/. "release/$d/"; done', wf)   # either folder name can be the subdomain's document root
        self.assertIn('hidden=$(curl -s -o /dev/null -w \'%{http_code}\' "$URL$p")', wf)
        self.assertIn('[ "$hidden" = "401" ] || ok=0', wf)           # the live check: the hidden demo must refuse a visitor
        self.assertLess(wf.index("vars.ATOMOU_PUBLIC == 'true' && '--release'"), wf.index("vars.ATOMOU_REVIEW == 'true' && '--review'"))   # the real release wins over the review copy


class HiddenDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.atomou import build
        cls.pages = build.build_demo_sub(CFG, "https://demo.atomou.com", TODAY)

    def test_the_demo_names_its_own_host_and_stays_behind_a_password(self):
        self.assertIn("https://demo.atomou.com/", self.pages["index.html"])
        self.assertNotIn('rel="canonical" href="https://atomou.com', self.pages["index.html"])
        self.assertIn("AuthType Basic", self.pages[".htaccess"])
        self.assertIn("__HTPASSWD__", self.pages[".htaccess"])
        self.assertIn("noindex", self.pages["index.html"])

    def test_the_receivers_find_the_site_folder_one_level_further_up(self):
        # public_html/demo/api/m.php: dirname 3 is the site folder, outside every web folder; level 2 would be public_html itself
        php = {k: v for k, v in self.pages.items() if k.endswith(".php")}
        self.assertTrue({"api/m.php", "api/push.php", "api/e.php", "contact/send.php"} <= set(php), sorted(php))
        for k, v in php.items():
            self.assertIn("dirname(__DIR__, 3)", v, k)
            self.assertNotIn("dirname(__DIR__, 2)", v, k)
        self.assertIn("'https://demo.atomou.com'", self.pages["api/m.php"].replace('"', "'"))     # requests are accepted from the demo's own address


if __name__ == "__main__":
    unittest.main()
