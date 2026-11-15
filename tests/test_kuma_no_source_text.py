"""Owner 2026-11-15 (D26): no source names, source sections or outbound source links on screen.

What stays: the credit a licence asks for (class "credit", the footer's processing notice) and the pages that are the licence record itself
(/cite/ and /data/: they say which licence each row of the data has).  Everything else must have no source word and no outbound link
except an advertisement (rel sponsored), the site's own social accounts and the Google ad-settings links of the privacy page.
"""
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kuma import build
from sites.kuma import live as live_mod
from tests.test_kuma_build import AKITA, CFG, COUNTS_META, HAVE_PYPDF, MIYAGI, _counts_raw
from tests.test_kuma_cite import make_raw
from tests.test_kuma_official import LINKS

TODAY = date(2026, 10, 7)
SOURCE_WORDS = re.compile(r"出典|情報元|情報源|参考資料|参考文献|参照元")
ALLOWED_HOSTS = ("forms.example.com", "bsky.app", "x.com", "adssettings.google.com", "www.aboutads.info", "policies.google.com")
LICENCE_PAGES = ("cite/index.html", "data/index.html")        # the licence record: the words are the page's subject


def _strip_credit(html: str) -> str:
    """The page without the footer notice and without every paragraph marked as a licence credit."""
    html = re.sub(r'<p class="src">.*?</p>', "", html, flags=re.S)
    html = re.sub(r'<p class="[^"]*\bcredit\b[^"]*">.*?</p>', "", html, flags=re.S)
    return html


def visible_text(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", "", _strip_credit(html), flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def outbound_links(html: str) -> list[str]:
    """External <a> links that are not an advertisement and not on the allowed list."""
    out = []
    for m in re.finditer(r"<a\b[^>]*>", html):
        tag = m.group(0)
        href = re.search(r'href="(https?://[^"]+)"', tag)
        if not href or "sponsored" in tag:
            continue
        url = href.group(1)
        if "kuma-sokuho.com" in url or any(h in url for h in ALLOWED_HOSTS):
            continue
        out.append(url)
    return out


def problems(files: dict[str, str]) -> list[str]:
    bad = []
    for path, html in files.items():
        if not path.endswith(".html"):
            continue
        for u in outbound_links(html):
            bad.append(f"{path}: outbound link {u}")
        if path not in LICENCE_PAGES:
            m = SOURCE_WORDS.search(visible_text(html))
            if m:
                text = visible_text(html)
                bad.append(f"{path}: source word near {text[max(0, m.start() - 20):m.end() + 20]!r}")
    return bad


class DetectorTest(unittest.TestCase):
    """The check must catch what it is for (negative tests), and let the allowed things through."""

    def test_a_source_line_in_the_body_is_caught(self):
        self.assertTrue(problems({"a/index.html": "<main><p>出典: 環境省の資料</p></main>"}))

    def test_an_outbound_source_link_is_caught(self):
        self.assertTrue(problems({"a/index.html": '<main><a href="https://www.env.go.jp/x.html" rel="noopener" target="_blank">環境省</a></main>'}))

    def test_an_info_source_heading_is_caught(self):
        self.assertTrue(problems({"a/index.html": "<main><h2>情報源</h2></main>"}))

    def test_credits_advertisements_own_accounts_and_the_licence_pages_pass(self):
        ok = {
            "a/index.html": '<main><p class="notice credit">出典: 秋田県「クマダス」(CC BY 4.0)を加工して作成</p>'
                            '<a href="https://px.a8.net/x" rel="nofollow sponsored noopener">広告</a>'
                            '<a href="https://x.com/infosokuho">X</a></main><footer><p class="src">出典: 環境省を加工して作成。</p></footer>',
            "cite/index.html": "<main><p>出典の書き方</p></main>",
        }
        self.assertEqual(problems(ok), [])


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class BuiltSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        raw = make_raw()
        prefs = {"miyagi": MIYAGI, "akita": AKITA, "fukushima": _counts_raw()}
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            build.render_site(raw, CFG, cls.out, release=True, links=LINKS, prefs=prefs, today=TODAY)
        cls.files = {str(p.relative_to(cls.out)).replace("\\", "/"): p.read_text(encoding="utf-8") for p in cls.out.rglob("*.html")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_page_shows_a_source_word_or_an_outbound_source_link(self):
        self.assertEqual(problems(self.files), [])

    def test_the_footer_of_every_page_has_the_general_sentence_and_the_processing_notice(self):
        for path, html in self.files.items():
            if path == "404.html" or 'class="src"' not in html:
                continue
            foot = re.search(r'<p class="src">(.*?)</p>', html, re.S).group(1)
            self.assertIn("公式の発表をはじめとする複数の情報をもとにしています。", foot, path)
            self.assertIn("加工して作成。環境省が作成したものではありません。", foot, path)

    def test_the_licence_credits_stay_on_the_live_pages(self):
        live = self.files["live/akita/index.html"]
        self.assertIn("CC BY", live)
        self.assertIn("加工して作成", live)

    def test_the_confirmation_dates_stay(self):
        self.assertRegex(self.files["live/akita/index.html"], r"取得日: \d{4}年\d{1,2}月\d{1,2}日")
