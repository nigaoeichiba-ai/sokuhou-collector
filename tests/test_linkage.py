"""The linkage gate (sokuhou/linkage.py): a page that nothing links to, a category that lacks a page, a one-way related link, a top page that does not show the newest
articles, a link worded as a URL, an advertiser named without its affiliate link -- each is caught on a built folder, and each rule has a NEGATIVE test that reproduces the
real leak.  Plus complete(): tags and two-way related links come out of the content by themselves."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sokuhou import linkage

BASE = "https://example.test"


def ld_article(path, day):
    return {"@type": "Article", "headline": path, "datePublished": day, "dateModified": day, "mainEntityOfPage": BASE + path}


def ld_crumb(parent):
    items = [{"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}]
    if parent != "/":
        items.append({"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + parent})
    items.append({"@type": "ListItem", "position": len(items) + 1, "name": "x", "item": BASE + "/x/"})
    return {"@type": "BreadcrumbList", "itemListElement": items}


def write(root: Path, path: str, body: str, ld=(), noindex=False):
    rel = "index.html" if path == "/" else path.strip("/") + "/index.html"
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    scripts = "".join('<script type="application/ld+json">' + json.dumps(d) + "</script>" for d in ld)
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    f.write_text(f'<!doctype html><html><head><title>t</title>{robots}<link rel="canonical" href="{BASE}{path}">{scripts}</head><body><main>{body}</main></body></html>', encoding="utf-8")


def related(*paths):
    return '<h2>関連するページ</h2>\n<ul class="links">' + "".join(f'<li><a href="{p}">{p}</a></li>' for p in paths) + "</ul>"


def good_site(root: Path):
    """home -> category -> two articles, the home shows the newest, the articles list each other."""
    write(root, "/", '<a href="/cat/">cat</a><a href="/a/">A</a><a href="/b/">B</a>', [])
    write(root, "/cat/", '<a href="/a/">A</a><a href="/b/">B</a><a href="/">top</a>', [ld_crumb("/")])
    write(root, "/a/", "<p>text</p>" + related("/b/"), [ld_article("/a/", "2026-11-14"), {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + "/cat/"},
        {"@type": "ListItem", "position": 3, "name": "a", "item": BASE + "/a/"}]}])
    write(root, "/b/", "<p>text</p>" + related("/a/"), [ld_article("/b/", "2026-11-13"), {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + "/cat/"},
        {"@type": "ListItem", "position": 3, "name": "b", "item": BASE + "/b/"}]}])


def keys(root, site=None):
    return linkage.find(Path(root), BASE, site)


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        good_site(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def rules(self, site=None):
        return sorted({k.split("|")[0] for k in keys(self.root, site)})

    def test_good_site_is_clean(self):
        self.assertEqual(keys(self.root), [])

    def test_orphan_page_is_found(self):          # a new article that no page links to (the category and home were not updated)
        write(self.root, "/c/", "<p>new</p>", [ld_article("/c/", "2026-11-15")])
        self.assertIn("orphan", self.rules())

    def test_category_without_the_page_is_found(self):      # the page links to its category in the breadcrumb, the category does not list the page
        write(self.root, "/cat/", '<a href="/a/">A</a><a href="/">top</a>', [ld_crumb("/")])
        out = keys(self.root)
        self.assertTrue(any(k.startswith("parent-missing|/b/") for k in out), out)

    def test_one_way_related_link_is_found(self):
        write(self.root, "/b/", "<p>text</p>", [ld_article("/b/", "2026-11-13"), {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + "/cat/"},
            {"@type": "ListItem", "position": 3, "name": "b", "item": BASE + "/b/"}]}])
        out = keys(self.root)
        self.assertTrue(any(k.startswith("related-oneway|/a/") for k in out), out)

    def test_url_as_link_text_is_found(self):
        write(self.root, "/", '<a href="/cat/">cat</a><a href="/a/">A</a><a href="/b/">B</a><a href="https://www.example.com/x">https://www.example.com/x</a>', [])
        write(self.root, "/c/", '<a href="/a/">example.co.jp</a>', [ld_crumb("/")], noindex=True)
        out = keys(self.root)
        self.assertEqual(sum(1 for k in out if k.startswith("url-as-anchor")), 2, out)

    def test_worded_link_is_not_a_url(self):
        write(self.root, "/", '<a href="/cat/">cat</a><a href="/a/">A</a><a href="/b/">B</a><a href="https://www.example.com/x">公式サイトを見る</a>', [])
        self.assertNotIn("url-as-anchor", self.rules())

    def test_home_must_show_the_newest_articles(self):
        (self.root / "..").resolve()
        cfg = {"t": {"home_newest": 2}}
        orig = linkage.load_config
        linkage.load_config = lambda: cfg
        try:
            write(self.root, "/new/", "<p>n</p>", [ld_article("/new/", "2026-11-15"), {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + "/cat/"},
                {"@type": "ListItem", "position": 3, "name": "n", "item": BASE + "/new/"}]}])
            write(self.root, "/cat/", '<a href="/a/">A</a><a href="/b/">B</a><a href="/new/">N</a><a href="/">top</a>', [ld_crumb("/")])
            out = keys(self.root, "t")
            self.assertTrue(any(k.startswith("home-newest|/new/") for k in out), out)      # 11/15 is one of the 2 newest but the home does not link it
            write(self.root, "/", '<a href="/cat/">cat</a><a href="/a/">A</a><a href="/new/">N</a>', [])
            self.assertFalse(any(k.startswith("home-newest") for k in keys(self.root, "t")))
        finally:
            linkage.load_config = orig


class Affiliate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        good_site(self.root)
        self.orig = linkage.load_advertisers
        linkage.load_advertisers = lambda site: [{"id": "acme", "names": ["アクメ"], "sites": ["t"]}] if site == "t" else []

    def tearDown(self):
        linkage.load_advertisers = self.orig
        self.tmp.cleanup()

    def page(self, body):
        write(self.root, "/a/", "<p>text</p>" + body + related("/b/"), [ld_article("/a/", "2026-11-14"), {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "top", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": "cat", "item": BASE + "/cat/"},
            {"@type": "ListItem", "position": 3, "name": "a", "item": BASE + "/a/"}]}])

    def test_named_advertiser_without_link_is_found(self):      # the owner's rule: an affiliated advertiser that is written about carries its link
        self.page("<p>アクメのセールが始まりました。</p>")
        self.assertTrue(any(k.startswith("affiliate-missing|/a/") for k in keys(self.root, "t")))

    def test_advertiser_with_its_link_is_fine(self):
        self.page('<p>アクメのセール</p><p><a href="https://px.a8.net/svt/ejp?a8mat=X" rel="nofollow sponsored noopener" target="_blank">アクメの公式ショップを見る</a></p>')
        self.assertEqual([k for k in keys(self.root, "t") if k.startswith("affiliate")], [])

    def test_affiliate_link_without_sponsored_rel_is_found(self):
        self.page('<p>アクメ</p><p><a href="https://px.a8.net/svt/ejp?a8mat=X" target="_blank">アクメの公式ショップを見る</a></p>')
        self.assertTrue(any(k.startswith("affiliate-rel|/a/") for k in keys(self.root, "t")))

    def test_other_site_is_not_checked(self):
        self.page("<p>アクメのセールが始まりました。</p>")
        self.assertEqual([k for k in keys(self.root, "other") if k.startswith("affiliate")], [])


class Baseline(unittest.TestCase):
    def test_ratchet_only_new_findings_stop(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "r"
            good_site(root)
            write(root, "/c/", "<p>new</p>", [ld_article("/c/", "2026-11-15")])
            known = {k for k in keys(root)}
            orig = linkage.baseline
            linkage.baseline = lambda site: known
            try:
                self.assertEqual(linkage.main([str(root), "--base", BASE, "--site", "zz", "--mode", "ratchet"]), 0)       # what was there is allowed
                write(root, "/d/", "<p>newer</p>", [ld_article("/d/", "2026-11-16")])
                self.assertEqual(linkage.main([str(root), "--base", BASE, "--site", "zz", "--mode", "ratchet"]), 1)       # a new orphan stops
                self.assertEqual(linkage.main([str(root), "--base", BASE, "--site", "zz", "--mode", "shadow"]), 0)
            finally:
                linkage.baseline = orig


class Complete(unittest.TestCase):
    def pages(self):
        def p(path, tags, rel=None):
            return {"path": path, "kind": "article", "parent": "/cat/", "h1": "H " + path, "tags": tags, "related": rel or [], "published": "2026-11-1" + str(len(path) % 9)}
        return [p("/a/", ["rice", "price"]), p("/b/", ["rice"]), p("/c/", ["storm"]), p("/d/", ["price", "rice"])]

    def test_tags_make_related_links_both_ways(self):
        pages = linkage.complete(self.pages())
        by = {p["path"]: [r["path"] for r in p["related"]] for p in pages}
        self.assertIn("/b/", by["/a/"])
        self.assertIn("/a/", by["/b/"])
        self.assertEqual(by["/c/"], [])          # no shared tag, no link
        self.assertEqual(by["/a/"][0], "/d/")    # the closest (two shared tags) first

    def test_explicit_related_is_made_two_way(self):      # the one-way link of 2026-11-15 (bousai-light -> bousai-denchi-juden)
        pages = self.pages()
        for p in pages:
            p["tags"] = []
        pages[0]["related"] = [{"path": "/c/", "text": "C"}]
        out = linkage.complete(pages)
        self.assertEqual([r["path"] for r in out[2]["related"]], ["/a/"])

    def test_other_parent_is_not_reversed(self):      # a hub's list of children is not a related link
        pages = self.pages()
        pages[2]["parent"] = "/other/"
        pages[0]["tags"] = []
        pages[0]["related"] = [{"path": "/c/", "text": "C"}]
        out = linkage.complete(pages)
        self.assertEqual(out[2]["related"], [])

    def test_cap(self):
        pages = [{"path": f"/p{i}/", "kind": "article", "parent": "/c/", "h1": "h", "tags": ["x"], "related": []} for i in range(9)]
        out = linkage.complete(pages)
        self.assertTrue(all(len(p["related"]) >= 4 for p in out))
        self.assertTrue(all(len(set(r["path"] for r in p["related"])) == len(p["related"]) for p in out))


class SiteRules(unittest.TestCase):
    """trend's and kaidoki's own rules, each with the leak that really happened."""

    def load(self, folder: Path, site: str):
        import importlib.util
        spec = importlib.util.spec_from_file_location("lc_" + site, linkage.ROOT / "sites" / site / "linkcheck.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, linkage.load(folder, BASE)

    def test_trend_stale_home_date_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "/", '<p>最終更新：2026年11月11日</p><a class="article-card" href="/a/">A</a>', [])
            write(root, "/a/", "<p>x</p>", [ld_article("/a/", "2026-11-15")])
            mod, pages = self.load(root, "trend")
            self.assertTrue(any(k.startswith("home-date") for k in mod.check(root, BASE, pages)))
            write(root, "/", '<p>最終更新：2026年11月15日</p><a class="article-card" href="/a/">A</a>', [])
            mod, pages = self.load(root, "trend")
            self.assertEqual(mod.check(root, BASE, pages), [])

    def test_trend_missing_card_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "/", '<p>最終更新：2026年11月15日</p><a class="article-card" href="/old/">O</a>', [])
            write(root, "/old/", "<p>x</p>", [ld_article("/old/", "2026-11-07")])
            write(root, "/new/", "<p>x</p>", [ld_article("/new/", "2026-11-15")])
            mod, pages = self.load(root, "trend")
            self.assertTrue(any(k.startswith("home-cards|/new/") for k in mod.check(root, BASE, pages)))

    def kaidoki(self, home_rows, cal_rows):
        tbl = lambda rows: "<table><tr><th>モール</th><th>名前</th><th>期間</th></tr>" + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows) + "</table>"
        return '<h2>いま分かっている日程</h2>' + tbl(home_rows) + "<h2>次</h2>", tbl(cal_rows)

    def test_kaidoki_home_row_missing_on_calendar_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            h, c = self.kaidoki([("楽天", "楽天BF", "11月19日"), ("Yahoo", "YBF", "11月22日")], [("楽天", "楽天BF", "11月19日")])
            write(root, "/", h, [])
            write(root, "/calendar/", c, [])
            mod, pages = self.load(root, "kaidoki")
            out = mod.check(root, BASE, pages)
            self.assertEqual(len(out), 1, out)
            h, c = self.kaidoki([("楽天", "楽天BF", "11月19日")], [("楽天", "楽天BF", "11月19日")])
            write(root, "/", h, [])
            write(root, "/calendar/", c, [])
            mod, pages = self.load(root, "kaidoki")
            self.assertEqual(mod.check(root, BASE, pages), [])


class RealBuild(unittest.TestCase):
    """The real content of trend is clean against its baseline (nothing new has leaked)."""

    def build(self, site):
        from sokuhou import newsite
        files, _ = newsite.build_pages(linkage.ROOT / "sites" / site)
        d = tempfile.TemporaryDirectory()
        for rel, data in files.items():
            f = Path(d.name) / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return d

    def test_trend_has_nothing_new(self):
        d = self.build("trend")
        try:
            new = [k for k in linkage.find(Path(d.name), "https://trend-sokuho.com", "trend") if k not in linkage.baseline("trend")]
            self.assertEqual(new, [])
        finally:
            d.cleanup()

    # kaidoki is not built here: its content is written by sites/kaidoki/gen (for today's date) just before the build, and that writes into the repository; the deploy's own
    # Linkage gate runs on the real build of kaidoki against data/linkage/baseline_kaidoki.json


if __name__ == "__main__":
    unittest.main()
