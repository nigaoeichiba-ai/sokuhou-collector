"""sokuhou/postcheck.py: the live check after a deploy, on a fake site (no network).  Each failure that really happened is reproduced: the category lacks the page, a related
page does not link back, the page is not in the sitemap, an affiliate link without rel=sponsored, a link worded as a URL, an advertiser named without its link."""
from __future__ import annotations

import json
import unittest
from datetime import datetime

from sokuhou import linkage, postcheck

BASE = "https://example.test"


def crumb(parent, me):
    return {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "t", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "c", "item": BASE + parent},
                                                           {"@type": "ListItem", "position": 3, "name": "m", "item": BASE + me}]}


def html(body, ld=()):
    return "<html><head><title>t</title>" + "".join('<script type="application/ld+json">' + json.dumps(d) + "</script>" for d in ld) + f"</head><body><h1>h</h1>{body}</body></html>"


def rel(*p):
    return '<h2>関連するページ</h2><ul class="links">' + "".join(f'<li><a href="{x}">{x}</a></li>' for x in p) + "</ul>"


def site(**over):
    pages = {
        "/sitemap.xml": "<urlset><url><loc>%s/a/</loc></url><url><loc>%s/b/</loc></url></urlset>" % (BASE, BASE),
        "/": html('<a href="/cat/">c</a><a href="/a/">a</a>'),
        "/cat/": html('<a href="/a/">a</a><a href="/b/">b</a>'),
        "/a/": html('<p>PR</p><a href="https://px.a8.net/x" rel="nofollow sponsored noopener">公式を見る</a>' + rel("/b/"), [crumb("/cat/", "/a/"), {"@type": "Article", "datePublished": "2026-11-15"}]),
        "/b/": html(rel("/a/"), [crumb("/cat/", "/b/"), {"@type": "Article", "datePublished": "2026-11-14"}]),
    }
    pages.update(over)
    return lambda path: (200, pages[path]) if path in pages else (404, "")


class Post(unittest.TestCase):
    def setUp(self):
        self.cfg, self.ads = linkage.load_config, linkage.load_advertisers
        linkage.load_config = lambda: {"s": {"home_newest": 1}}
        linkage.load_advertisers = lambda site: [{"id": "acme", "names": ["アクメ"], "sites": ["s"]}]

    def tearDown(self):
        linkage.load_config, linkage.load_advertisers = self.cfg, self.ads

    def bad(self, fetch):
        return sorted({(r["page"], r["check"]) for r in postcheck.verify("s", BASE, ["/a/"], fetch) if r["ok"] is False})

    def test_good_site_passes(self):
        self.assertEqual(self.bad(site()), [])

    def test_category_lacking_the_page(self):
        self.assertIn(("/a/", "parent"), self.bad(site(**{"/cat/": html('<a href="/b/">b</a>')})))

    def test_related_does_not_link_back(self):
        self.assertIn(("/a/", "related"), self.bad(site(**{"/b/": html("<p>x</p>", [crumb("/cat/", "/b/")])})))

    def test_page_missing_from_sitemap(self):
        self.assertIn(("/a/", "sitemap"), self.bad(site(**{"/sitemap.xml": "<urlset><url><loc>%s/b/</loc></url></urlset>" % BASE})))

    def test_newest_article_missing_on_home(self):
        self.assertIn(("/a/", "home"), self.bad(site(**{"/": html('<a href="/cat/">c</a>')})))

    def test_affiliate_without_rel_and_url_text_and_missing_advertiser(self):
        a = html('<p>アクメのセール</p><a href="https://px.a8.net/x">https://www.acme.example/</a>' + rel("/b/"), [crumb("/cat/", "/a/"), {"@type": "Article", "datePublished": "2026-11-15"}])
        got = self.bad(site(**{"/a/": a}))
        self.assertIn(("/a/", "affiliate"), got)
        self.assertIn(("/a/", "link-text"), got)

    def test_advertiser_named_without_link(self):
        a = html("<p>アクメのセール</p>" + rel("/b/"), [crumb("/cat/", "/a/"), {"@type": "Article", "datePublished": "2026-11-15"}])
        self.assertIn(("/a/", "advertiser"), self.bad(site(**{"/a/": a})))

    def test_draft_says_fix_needed(self):
        rows = postcheck.verify("s", BASE, ["/a/"], site(**{"/cat/": html("<p>none</p>")}))
        text, ok = postcheck.render("s", BASE, rows, "t", "", "abc", datetime(2026, 11, 15, 12, 0))
        self.assertFalse(ok)
        self.assertIn("要修正", text)
        rows = postcheck.verify("s", BASE, ["/a/"], site())
        text, ok = postcheck.render("s", BASE, rows, "t", "", "abc", datetime(2026, 11, 15, 12, 0))
        self.assertTrue(ok)
        self.assertIn("自動確認: **OK**", text)


if __name__ == "__main__":
    unittest.main()
