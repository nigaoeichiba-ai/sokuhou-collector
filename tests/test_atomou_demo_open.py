"""The open preview of demo.atomou.com (owner decision D24, 2026-11-14): only with --open; the default demo stays behind its password."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sites.atomou import build  # noqa: E402

CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))


class OpenPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closed = build.build_demo_sub(CFG, "https://demo.atomou.com")
        cls.open = build.build_demo_sub(CFG, "https://demo.atomou.com", open_=True)

    def test_default_demo_keeps_its_password(self):
        self.assertIn("AuthUserFile", self.closed[".htaccess"])
        self.assertIn("Require valid-user", self.closed[".htaccess"])
        self.assertTrue(any(k.startswith("api/") for k in self.closed))

    def test_open_has_no_password(self):
        self.assertNotIn("AuthUserFile", self.open[".htaccess"])
        self.assertNotIn("Require valid-user", self.open[".htaccess"])

    def test_open_is_never_indexed(self):
        ht = self.open[".htaccess"]
        self.assertIn('Header set X-Robots-Tag "noindex, nofollow"', ht)
        self.assertNotIn("sitemap.xml", self.open)
        for k, v in self.open.items():
            if k.endswith("index.html") and not k.startswith("e/"):
                self.assertIn('name="robots" content="noindex,nofollow"', v, k)

    def test_open_refuses_what_writes_on_the_server(self):
        self.assertFalse([k for k in self.open if k.startswith("api/") or k.endswith(".php")])
        self.assertIn("RewriteRule ^(api/|contact/send\\.php) - [F,L]", self.open[".htaccess"])
        # the rule really matches the receivers, and nothing else of the site
        pat = re.compile(r"^(api/|contact/send\.php)")
        for hit in ("api/m.php", "api/push.php", "api/w.php", "api/e.php", "api/s.php", "contact/send.php"):
            self.assertTrue(pat.match(hit), hit)
        for miss in ("index.html", "contact/index.html", "assets/app.js"):
            self.assertFalse(pat.match(miss), miss)

    def test_robots_lets_in_only_the_on_request_agents(self):
        r = self.open["robots.txt"]
        self.assertTrue(r.startswith("User-agent: *\nDisallow: /\n"))
        for agent in ("ChatGPT-User", "Claude-User", "Perplexity-User"):
            self.assertIn(f"User-agent: {agent}\nAllow: /", r)
        for agent in ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot"):
            self.assertNotIn(agent, r)

    def test_banner_says_it_is_a_sample(self):
        self.assertIn("登録・送信はできません", self.open["index.html"])
        self.assertNotIn("運営者情報などが未設定", self.open["index.html"])
        self.assertIn("運営者情報などが未設定", self.closed["index.html"])


if __name__ == "__main__":
    unittest.main()
