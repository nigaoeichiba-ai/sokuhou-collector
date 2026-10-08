"""atomou: the built site (pages, indexing rules, privacy-relevant properties) and the browser app in a real headless Chrome."""
import functools
import html
import http.server
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, skins, usecases  # noqa: E402
from sokuhou import sitecheck  # noqa: E402
from tests.test_atomou_core_js import find_chrome  # noqa: E402

TODAY = date(2026, 10, 8)
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))


class BuildOnce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rel = build.build_pages(CFG, release=True, today=TODAY)
        cls.prev = build.build_pages(CFG, release=False, today=TODAY)
        cls.entries, _ = catalog.build_catalog(TODAY)
        launch = date.fromisoformat(CFG["launch_date"])
        cls.index_ids = catalog.indexable_ids(cls.entries, TODAY, launch, CFG["index_per_week"])


class Pages(BuildOnce):
    def test_the_pages_exist(self):
        for p in ("index.html", "search/index.html", "my/index.html", "add/index.html", "skins/index.html", "manual/index.html", "today/index.html", "use/index.html",
                  "about/index.html", "privacy/index.html", "contact/index.html", "404.html", "sitemap.xml", "robots.txt", ".htaccess",
                  "assets/catalog.json", "assets/skins.css", "assets/app.js", "assets/core.js", "assets/ics.js", "assets/style.css", "favicon.ico"):
            self.assertIn(p, self.rel, p)
        self.assertEqual(sum(1 for k in self.rel if k.startswith("use/") and k.endswith("/index.html")), len(usecases.USECASES) + 1)
        self.assertEqual(sum(1 for k in self.rel if k.startswith("c/")), len(catalog.GROUPS))
        self.assertEqual(sum(1 for k in self.rel if k.startswith("e/")), len(self.entries))

    def test_release_and_preview_differ_only_in_indexing(self):
        self.assertIn("Allow: /", self.rel["robots.txt"])
        self.assertIn("Disallow: /", self.prev["robots.txt"])
        self.assertNotIn("noindex", self.rel["index.html"])
        self.assertIn("noindex", self.prev["index.html"])

    def test_release_is_refused_without_an_operator(self):
        with self.assertRaises(build.BuildError):
            build.build_pages({**CFG, "operator_name": ""}, release=True, today=TODAY)

    def test_my_page_and_held_back_events_are_noindex_and_not_in_the_sitemap(self):
        sm = self.rel["sitemap.xml"]
        self.assertIn("noindex", self.rel["my/index.html"])
        self.assertNotIn("/my/", sm)
        held = [e for e in self.entries if e["id"] not in self.index_ids]
        self.assertTrue(held and self.index_ids)
        for e in held[:20]:
            self.assertIn("noindex", self.rel[f"e/{e['id']}/index.html"])
            self.assertNotIn(f"/e/{e['id']}/", sm)
        for i in list(self.index_ids)[:20]:
            self.assertNotIn("noindex", self.rel[f"e/{i}/index.html"])
            self.assertIn(f"/e/{i}/", sm)

    def test_indexing_allowance_is_respected(self):
        self.assertLessEqual(len(self.index_ids), CFG["index_per_week"])  # launch week

    def test_sitecheck_passes_on_both_builds(self):
        for name, pages in (("release", self.rel), ("preview", self.prev)):
            with tempfile.TemporaryDirectory() as td:
                build.write_pages(pages, Path(td))
                self.assertEqual(sitecheck.check_dir(Path(td), CFG["site_url"]), [], name)

    def test_catalog_json_has_public_fields_only(self):
        data = json.loads(self.rel["assets/catalog.json"])
        self.assertEqual(len(data), len(self.entries))
        allowed = {"id", "title", "date", "date_end", "precision", "weekday", "kind", "category", "group", "region", "tags", "quiet", "ad_ok", "son_toku", "source_url", "checked_on", "status"}
        for e in data:
            self.assertLessEqual(set(e), allowed)

    def test_skins_css_has_every_skin(self):
        css = self.rel["assets/skins.css"]
        for s in skins.SKINS:
            self.assertIn(f'[data-skin="{s["id"]}"]', css)
        self.assertNotIn("http", css)  # no external fonts or images

    def test_every_page_loads_only_its_own_scripts_and_no_ads_yet(self):
        for k, v in self.rel.items():
            if k.endswith(".html") and isinstance(v, str):
                self.assertNotIn("adsbygoogle", v, k)  # no ad code until an AdSense id is set (and never on quiet pages)
                for src in re.findall(r'<script[^>]+src="([^"]+)"', v):
                    self.assertTrue(src.startswith("/assets/"), f"{k}: {src}")
        self.assertNotIn("googletagmanager", self.rel["index.html"])  # no analytics (the privacy policy says so)

    def test_quiet_entries_never_get_related_items_or_ads(self):
        quiet = [e for e in self.entries if e["quiet"]]
        for e in quiet[:10]:
            page = self.rel[f"e/{e['id']}/index.html"]
            self.assertIn("この日は、静かにお知らせします", page)
            self.assertNotIn("同じジャンルの日", page)
            self.assertIn('class="card quiet', page)

    def test_event_pages_state_source_and_check_date(self):
        e = self.entries[0]
        page = self.rel[f"e/{e['id']}/index.html"]
        self.assertIn(e["source_url"].replace("&", "&amp;"), page)
        self.assertIn(e["checked_on"], page)
        self.assertIn("公式ページでご確認ください", page)

    def test_privacy_policy_says_where_personal_days_live(self):
        p = self.rel["privacy/index.html"]
        self.assertIn("localStorage", p)
        self.assertIn("サーバーには送りません", p)

    def test_manual_is_linked_from_every_page_and_has_the_questions(self):
        for k in ("index.html", "my/index.html", "e/" + self.entries[0]["id"] + "/index.html"):
            self.assertIn('href="/manual/"', self.rel[k], k)
        m = self.rel["manual/index.html"]
        for q in ("料金はかかりますか", "機種変更をしたら", "お知らせが来ません"):
            self.assertIn(q, m)
        self.assertNotIn("必ず届き", m)  # nothing promises that a notice arrives


class StatsAndPrivacy(BuildOnce):
    def test_receiver_is_generated_with_the_same_key_pattern_as_the_app(self):
        php = self.rel["api/e.php"]
        self.assertIn("'/" + build.STAT_KEY_RE + "/'", php)
        js = (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("var STAT_RE = /" + build.STAT_KEY_RE + "/", js)
        for needle in ("php://input", "4096", "flock", "dirname(__DIR__, 2)", "http_response_code(405)"):
            self.assertIn(needle, php)
        self.assertEqual(php.count("REMOTE_ADDR"), 1)  # the address appears once, and only to be hashed
        self.assertIn("hash('sha256', $ip", php)
        self.assertNotIn("__RE__", php)

    def test_privacy_page_describes_the_statistics_and_not_the_old_no_analytics_text(self):
        p = self.rel["privacy/index.html"]
        self.assertIn('id="stats"', p)
        self.assertIn("検索した言葉は送りません", p)
        self.assertNotIn("アクセス解析ツールを使用していません", p)
        self.assertNotIn('id="google"', p)  # no Google hand-over without a client id

    def test_google_hand_over_appears_only_with_a_client_id(self):
        pages = build.build_pages({**CFG, "google_client_id": "123-abc.apps.googleusercontent.com"}, release=True, today=TODAY)
        self.assertIn('id="google"', pages["privacy/index.html"])
        self.assertIn('id="sync-now"', pages["my/index.html"])
        self.assertIn('"gclient":"123-abc.apps.googleusercontent.com"', pages["index.html"])
        self.assertNotIn("sync-now", self.rel["my/index.html"])
        self.assertNotIn("gclient", self.rel["index.html"])

    def test_my_page_has_the_statistics_switch(self):
        self.assertIn('id="p-stats"', self.rel["my/index.html"])


class CardMarkup(BuildOnce):
    """build.card_html and app.js cardHtml must produce the same structure: the static cards are replaced by the script's on first load."""

    @staticmethod
    def js_classes(js: str) -> set:
        chunk = js[js.index("function cardHtml"):js.index("function findEntry")]
        words = set(re.findall(r"class=\"([a-z][a-z0-9 -]*)", chunk))
        return ({c for w in words for c in w.split()} | {"mark"}) - {"m"}  # "mark m<g>" is written as two parts

    def py_classes(self) -> set:
        e = self.entries[0]
        out = set()
        for own in (False, True):
            out.update(c for chunk in re.findall(r'class="([^"]+)"', build.card_html(dict(e, quiet=True), own=own)) for c in chunk.split())
        return {c for c in out if c not in ("big", "quiet") and not re.fullmatch(r"m\d", c)}

    def test_class_lists_match(self):
        js = (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertEqual(self.py_classes(), self.js_classes(js) - {"quiet"}, "build.py card_html and app.js cardHtml drifted apart")

    def test_the_comparison_detects_drift(self):
        js = (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        drifted = js.replace('<p class="c-sub"></p>', "")
        self.assertNotEqual(self.py_classes(), self.js_classes(drifted) - {"quiet"})


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class AppInChrome(BuildOnce):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        build.write_pages(cls.rel, Path(cls.tmp.name))
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=cls.tmp.name))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def dom(self, path: str, extra: str = "") -> str:
        with tempfile.TemporaryDirectory() as prof:
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={prof}", "--virtual-time-budget=6000",
                                "--dump-dom", f"{self.base}{path}{'&' if '?' in path else '?'}today=2026-10-08{extra}"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")

    def test_home_counts_are_filled_and_nothing_is_empty(self):
        dom = self.dom("/")
        self.assertGreaterEqual(dom.count('class="card'), 12)
        self.assertNotIn('<span class="num"></span>', dom)  # every card got its number
        self.assertIn("今日は 2026年10月8日(木)", html.unescape(dom))
        self.assertIn("2026年は、もう281日め", html.unescape(dom))
        self.assertIn('data-dir="ato"', dom)

    def test_search_finds_by_word_and_by_synonym(self):
        for q, word in (("年賀", "年賀"), ("コミケ", "コミック"), ("時給", "最低賃金")):
            dom = html.unescape(self.dom(f"/search/?q={q}"))
            self.assertIn(word, dom, q)
            self.assertRegex(dom, r'<p class="small muted" id="found"[^>]*>\d+件', q)

    def test_search_with_no_match_offers_to_record_it(self):
        dom = self.dom("/search/?q=zzzqqqxxx")
        self.assertRegex(dom, r'id="none"(?![^>]*hidden)')

    def test_skin_override_applies_card_style(self):
        dom = self.dom("/", "&skin=pop")
        self.assertIn('data-skin="pop"', dom)
        self.assertIn('data-card="panel"', dom)
        dom = self.dom("/", "&skin=basic")
        self.assertNotIn("data-skin=", dom.split("<body")[0])

    def test_add_page_prefills_and_shows_the_live_count(self):
        dom = html.unescape(self.dom("/add/?kind=anniversary&title=付き合った日&date=2024-06-26"))
        self.assertIn("もう2年3か月12日", dom)
        self.assertIn("合計 834日", dom)

    def test_today_page_numbers_and_links(self):
        raw = html.unescape(self.dom("/today/"))
        dom = re.sub(r"<[^>]+>", "", raw) + raw
        for want in ("もう281日め", "年末まで、あと84日", "2027年まで、あと85日", "2026年度は、あと174日"):
            self.assertIn(want, dom)
        self.assertIn("date=2027-03-31", dom)   # 引っ越しの用意 -> the end of the fiscal year
        self.assertIn("date=2027-04-01", dom)   # 入学の用意 -> the start of the next one
        self.assertIn("alarm=week", dom)

    def test_home_edit_mode_shows_a_bar_on_every_block(self):
        dom = self.dom("/?edit=1")
        self.assertEqual(dom.count('class="block-bar"'), 7)
        self.assertNotIn('class="block-bar"', self.dom("/"))

    def test_no_storage_errors_with_a_blank_profile(self):
        # a fresh profile has no atomou.v1: the pages must render (my page shows its empty state)
        dom = self.dom("/my/")
        self.assertRegex(dom, r'id="my-empty"(?![^>]*hidden)')


if __name__ == "__main__":
    unittest.main()
