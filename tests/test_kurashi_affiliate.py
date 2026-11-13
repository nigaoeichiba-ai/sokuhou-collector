"""kurashi-calendar.com: pages whose topic has something to buy carry Rakuten / Amazon search links with PR, rel and target; no URL as link text."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from sites.kurashi.gen.shop_links import SHOP_PAGES
from tests.test_trend_affiliate import problems

CONTENT = Path(__file__).resolve().parents[1] / "sites" / "kurashi" / "content"


def html_of(path: str) -> str:
    name = "home" if path == "/" else path.strip("/").replace("/", "-")
    d = json.loads((CONTENT / f"{name}.json").read_text(encoding="utf-8"))
    return " ".join(s.get("html", "") for s in d["sections"])


def a8_problems(html: str) -> list[str]:
    """The A8.net link must carry PR, rel (nofollow sponsored noopener), target=_blank, a word (not a URL) as its text, and its 1x1 pixel with the same a8mat."""
    import re
    out = []
    links = re.findall(r'<a ([^>]*href="https://px\.a8\.net/svt/ejp\?a8mat=([0-9A-Z+]+)"[^>]*)>(.*?)</a>', html, re.S)
    if not links:
        return ["no A8 link"]
    for attrs, mat, text in links:
        if not all(w in attrs for w in ("nofollow", "sponsored", "noopener", 'target="_blank"')):
            out.append("rel/target missing")
        if re.match(r"^\s*(https?://|www\.)", re.sub(r"<[^>]+>", "", text)):
            out.append("url as text")
        if f"https://" not in html or not re.search(r"<img [^>]*src=\"https://www\d+\.a8\.net/0\.gif\?a8mat=" + re.escape(mat) + '"', html):
            out.append("pixel missing")
    if "PR" not in html:
        out.append("PR missing")
    return out


class KurashiAffiliate(unittest.TestCase):
    def test_topic_pages_have_links(self):
        for path, (_h2, _intro, rk, am) in SHOP_PAGES.items():
            h = html_of(path)
            self.assertIn("hb.afl.rakuten.co.jp/hgc/", h, path)
            if am:
                self.assertIn("amazon.co.jp/s?k=", h, path)
            self.assertEqual(problems(h), [], path)

    def test_nengajo_has_the_a8_link_of_the_print_service(self):
        # A8.net 年賀状スクウェア (しまうまプリント): the text link of the SALEカレンダー media (007; kurashi has no media of its own yet), with its pixel, PR note, rel and target
        h = html_of("/nengajo/")
        self.assertEqual(a8_problems(h), [])
        self.assertIn("a8mat=4BGH3G+CRMUQI+33J0+", h)

    def test_a8_negative_cases_are_caught(self):
        good = ('<p class="pr-note"><strong>【PR】</strong>広告です。</p><p><a href="https://px.a8.net/svt/ejp?a8mat=A+B+C+D" rel="nofollow sponsored noopener" target="_blank">年賀状印刷</a>'
                '<img border="0" width="1" height="1" src="https://www11.a8.net/0.gif?a8mat=A+B+C+D" alt=""></p>')
        self.assertEqual(a8_problems(good), [])
        self.assertTrue(a8_problems(good.replace(">年賀状印刷<", ">https://px.a8.net/svt/ejp?a8mat=A+B+C+D<")))   # a URL as the visible text
        self.assertTrue(a8_problems(good.replace(' target="_blank"', "")))
        self.assertTrue(a8_problems(good.replace("sponsored ", "")))
        self.assertTrue(a8_problems(good.replace("【PR】", "")))
        self.assertTrue(a8_problems(good.replace('<img border="0" width="1" height="1" src="https://www11.a8.net/0.gif?a8mat=A+B+C+D" alt="">', "")))
        self.assertTrue(a8_problems("<p>なし</p>"))

    def test_missing_link_is_caught(self):
        self.assertNotIn("hb.afl.rakuten.co.jp/hgc/", "<p>年賀状</p>")
        self.assertTrue(problems('<a href="https://hb.afl.rakuten.co.jp/hgc/I/?pc=x">https://hb.afl.rakuten.co.jp/</a>（PR）'))


def stale_dates(site_updated: str, pages: dict) -> list[str]:
    """The update day on the top and in site.json must be the newest day of the pages (no typed-in value left behind)."""
    newest = max(v for k, v in pages.items() if k != "/")
    out = [f"site.json says {site_updated}, the newest page says {newest}"] if site_updated != newest else []
    if pages.get("/") != newest:
        out.append(f"the top page says {pages.get('/')}, the newest is {newest}")
    return out


class KurashiUpdateDay(unittest.TestCase):
    def test_site_and_top_show_the_newest_update_day(self):
        pages = {}
        for f in CONTENT.glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            pages[d["path"]] = d["updated"]
        site = json.loads((CONTENT.parent / "site.json").read_text(encoding="utf-8"))["updated"]
        self.assertEqual(stale_dates(site, pages), [])

    def test_a_stale_day_is_caught(self):
        self.assertTrue(stale_dates("2026-11-03", {"/": "2026-11-13", "/a/": "2026-11-13"}))
        self.assertTrue(stale_dates("2026-11-13", {"/": "2026-11-03", "/a/": "2026-11-13"}))
        self.assertEqual(stale_dates("2026-11-13", {"/": "2026-11-13", "/a/": "2026-11-13", "/b/": "2026-11-03"}), [])


if __name__ == "__main__":
    unittest.main()
