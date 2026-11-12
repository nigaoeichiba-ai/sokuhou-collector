"""trend-sokuho.com: every article whose topic has something to buy carries natural affiliate links (search pages only),
each with PR, rel and target, and no link shows a bare URL as its text (owner rule 2026-11-13)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1] / "sites" / "trend" / "content"
AFF = re.compile(r'https://(hb\.afl\.rakuten\.co\.jp/hgc/|www\.amazon\.co\.jp/s\?|px\.a8\.net/)')
ANCHOR = re.compile(r'<a\b([^>]*)>(.*?)</a>(.{0,12})', re.S)

# articles that must have a Rakuten and an Amazon search link (topic has a product to look for), and the reasons for the rest
MUST = ["bousai", "bousai-light", "bousai-denchi-juden", "bousai-keitai-toilet", "bousai-mizu-shokuryo", "trend-fire-alarm",
        "trend-fire-prevention-week", "trend-typhoon32", "trend-humidifier-care", "trend-rice-price", "trend-vegetable-price",
        "trend-engel-coefficient", "trend-crab-phone-call", "trend-blackfriday-price", "trend-nengajo-print"]


def problems(html: str) -> list[str]:
    out = []
    for attrs, text, after in ANCHOR.findall(html):
        href = re.search(r'href="([^"]*)"', attrs)
        href = href.group(1).replace("&amp;", "&") if href else ""
        visible = re.sub(r"<[^>]+>", "", text).strip()
        if re.match(r"^(https?://|www\.)", visible):
            out.append("url as link text: " + visible[:40])
        if AFF.match(href):
            if not all(w in attrs for w in ("nofollow", "sponsored", "noopener", 'target="_blank"')):
                out.append("affiliate link without rel/target: " + visible[:30])
            if "PR" not in after and "PR" not in html:
                out.append("affiliate link without PR: " + visible[:30])
    return out


def article_html(slug: str) -> str:
    d = json.loads((CONTENT / f"{slug}.json").read_text(encoding="utf-8"))
    return " ".join(s.get("html", "") for s in d["sections"])


class TrendAffiliate(unittest.TestCase):
    def test_topic_articles_have_both_malls(self):
        for slug in MUST:
            h = article_html(slug)
            self.assertIn("hb.afl.rakuten.co.jp/hgc/", h, slug)
            self.assertIn("amazon.co.jp/s?k=", h, slug)
            self.assertIn("amazonmacs-22", h, slug)

    def test_malls_are_on_separate_lists(self):
        for slug in MUST:
            for ul in re.findall(r"<ul>.*?</ul>", article_html(slug), re.S):
                self.assertFalse("rakuten" in ul and "amazon" in ul, slug)

    def test_every_article_is_clean(self):
        for f in sorted(CONTENT.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            html = " ".join(s.get("html", "") for s in d.get("sections", []))
            self.assertEqual(problems(html), [], f.name)

    def test_negative_cases_are_caught(self):
        self.assertTrue(problems('<a href="https://x.example/p">https://x.example/p</a>'))
        self.assertTrue(problems('<a href="https://hb.afl.rakuten.co.jp/hgc/ID/?pc=x" rel="nofollow">楽天で探す</a>（PR）'))
        self.assertTrue(problems('<a href="https://www.amazon.co.jp/s?k=a&amp;tag=t" rel="nofollow sponsored noopener" target="_blank">Amazonで探す</a>'))
        self.assertEqual(problems('<a href="https://www.amazon.co.jp/s?k=a&amp;tag=t" rel="nofollow sponsored noopener" target="_blank">Amazonで探す</a>（PR）'), [])


if __name__ == "__main__":
    unittest.main()
