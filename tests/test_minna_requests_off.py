"""The illustration-request feature is switched off (owner order 2026-11-09; build.REQUESTS_ENABLED = False): no entrance, no link, a closed notice on /request/, a receiver that writes nothing,
and what was received is not touched.  Switching it on again is that one line (the tests of the feature itself run with it on: tests/test_minna_wishes.py)."""
import json
import re
import unittest
from unittest import mock

from sites.minna import build
from tests.test_minna_sitecache import shared_site

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "contact_own": True, "contact_kinds": ["イラストのリクエスト", "その他"]}


def read(rel: str) -> str:
    out, _ = shared_site()
    return (out / rel).read_text(encoding="utf-8")


class SwitchedOff(unittest.TestCase):
    def test_the_switch_is_one_constant_and_it_is_off(self):
        self.assertIs(build.REQUESTS_ENABLED, False)

    def test_no_page_links_to_the_request_page_or_offers_a_request(self):
        out, _ = shared_site()
        hits = {}
        for p in out.rglob("*.html"):
            t = p.read_text(encoding="utf-8")
            if re.search(r'href="/request/|data-miss|req-form|id="req-app"', t):
                hits[p.relative_to(out).as_posix()] = True
        self.assertEqual(hits, {})

    def test_the_menu_the_hubs_and_the_helper_have_no_request(self):
        top = read("index.html")
        self.assertNotIn("リクエスト", re.search(r'<nav aria-label="メイン">.*?</nav>', top, re.S).group(0))
        self.assertNotIn("イラストをリクエストする", read("tool/index.html"))
        assist = json.loads(read("data/assist.json"))
        self.assertNotIn("リクエストしたい", assist["chips"])
        self.assertNotIn("/request/", [p["u"] for p in assist["pages"]])

    def test_the_request_address_is_a_short_closed_notice_that_is_not_for_search(self):
        html = read("request/index.html")
        self.assertIn("受付は終了しました", html)
        self.assertIn('<meta name="robots" content="noindex,follow">', html)
        self.assertNotIn("<form", html.replace('<form class="hsearch"', ""))
        self.assertNotIn("<loc>https://minna-no-illust.com/request/</loc>", read("sitemap.xml"))
        self.assertNotIn("adsbygoogle", html)

    def test_the_receiver_answers_410_and_touches_nothing(self):
        php = read("api/q.php")
        self.assertIn("http_response_code(410)", php)
        for call in ("file_put_contents", "fopen", "unlink", "glob(", "mkdir", "rename", "fwrite", "file_get_contents", "mail("):
            self.assertNotIn(call, php, call)

    def test_the_scripts_get_enabled_false_and_show_no_button(self):
        self.assertEqual(json.loads(read("data/request-rules.json")), {"enabled": False})
        self.assertEqual(json.loads(read("data/request-board.json"))["rows"], [])
        for js in ("assets/app.js", "assets/assist.js"):
            self.assertIn("rules.enabled === false", read(js), js)

    def test_the_contact_form_has_no_request_kind_and_the_notices_match(self):
        contact = read("contact/index.html")
        self.assertNotIn("イラストのリクエスト", contact)
        self.assertNotIn("リクエストは、個別のお返事", contact)
        privacy = re.sub(r"<[^>]+>", "", read("privacy/index.html"))
        self.assertIn("リクエストの受付は終了しました", privacy)
        self.assertNotIn("「リクエスト」欄に書いて送った言葉(と、選んだ使い道・タッチ)は、イラストを企画するために", privacy)

    def test_what_was_received_is_not_in_the_build(self):
        out, _ = shared_site()
        self.assertFalse(any(p.name.startswith("req-") for p in out.rglob("*")))


class SwitchedBackOn(unittest.TestCase):
    """The one line brings it all back (the receiver, the page, the data files); the menu is built when the module loads, so the full site needs the constant true before the import."""
    def test_with_the_constant_true_the_page_the_receiver_and_the_data_come_back(self):
        with mock.patch.object(build, "REQUESTS_ENABLED", True):
            self.assertIn("req-form", build.request_page(CFG, True))
            php = build.request_php({"site_url": "https://minna-no-illust.com"})
            self.assertIn("file_put_contents", php)
            self.assertNotIn("http_response_code(410)", php)
            files = build.request_data_files()
            self.assertNotEqual(json.loads(files["data/request-rules.json"]), {"enabled": False})


if __name__ == "__main__":
    unittest.main()
