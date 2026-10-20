"""The `seo` rule of sokuhou.sitecheck and its report.  Each negative test builds the defect that was really found on a live site (2026-10-20 audit) or its mechanism:
kuma's footer linked its source page as 'こちら' on 270 pages; no site had breadcrumb data; a noindex page in a sitemap and a canonical that points elsewhere are the
classic ways a page is told two things at once."""
import json
import unittest

from tests.test_sitecheck import BASE, Site, good, page
from sokuhou import sitecheck


def ld(obj):
    return '<script type="application/ld+json">' + (obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)) + "</script>"


def crumbs(*items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": n, **({"item": u} if u else {})} for i, (n, u) in enumerate(items, 1)]}


class SeoRuleTest(unittest.TestCase):
    def seo(self, files, **kw):
        s = Site(files)
        self.addCleanup(s.tmp.cleanup)
        return [p for p in s.check(**kw) if p.startswith("[seo]")]

    def test_a_clean_site_has_no_seo_problem(self):
        files = good(ld(crumbs(("Top", BASE + "/"), ("Months", None))))
        self.assertEqual(self.seo(files), [])

    def test_a_link_worded_kochira_is_reported_like_the_footer_of_kuma(self):
        p = self.seo(good('<p>出典は<a href="/month/">こちら</a>。</p>'))
        self.assertEqual(len(p), 1, p)
        self.assertIn("こちら", p[0])
        self.assertIn("index.html", p[0])

    def test_a_link_with_a_describing_text_or_an_external_kochira_is_not_reported(self):
        self.assertEqual(self.seo(good('<a href="/month/">月ごとの贈りどき</a>')), [])
        self.assertEqual(self.seo(good('<a href="https://other.example/x">こちら</a>')), [])      # an external link: not this site's page to name

    def test_a_noindex_page_in_the_sitemap_is_reported(self):
        files = good()
        files["month/index.html"] = page('<h1>Months</h1><p>x</p><a href="/">top</a>', "month/",
                                         head='<title>t</title><meta name="description" content="d"><meta name="robots" content="noindex,follow"><link rel="canonical" href="https://example.test/{p}">')
        p = self.seo(files)
        self.assertTrue(any("noindex page is in the sitemap" in x and "month/index.html" in x for x in p), p)

    def test_a_site_that_is_noindex_everywhere_on_purpose_is_not_reported_for_its_sitemap(self):
        noindex = '<title>t</title><meta name="description" content="d"><meta name="robots" content="noindex,nofollow"><link rel="canonical" href="https://example.test/{p}">'
        files = good()
        files["index.html"] = page('<h1>Top</h1><a href="/month/">m</a>', "", head=noindex)
        files["month/index.html"] = page('<h1>Months</h1><a href="/">top</a>', "month/", head=noindex)
        self.assertEqual(self.seo(files), [])

    def test_a_canonical_that_is_another_page_of_the_site_is_reported(self):
        files = good()
        files["month/index.html"] = page('<h1>Months</h1><p>x</p><a href="/">top</a>', "month/",
                                         head='<title>t</title><meta name="description" content="d"><link rel="canonical" href="https://example.test/">')
        p = self.seo(files)
        self.assertTrue(any("canonical is not the page's own address" in x for x in p), p)

    def test_broken_json_ld_is_reported(self):
        p = self.seo(good(ld('{"@type": "BreadcrumbList", "itemListElement": [')))
        self.assertTrue(any("not valid JSON" in x for x in p), p)

    def test_a_breadcrumb_item_on_another_host_or_to_a_missing_page_is_reported(self):
        other = self.seo(good(ld(crumbs(("Top", "https://other.example/"), ("Months", None)))))
        self.assertTrue(any("another host" in x for x in other), other)
        missing = self.seo(good(ld(crumbs(("Top", BASE + "/"), ("Gone", BASE + "/gone/"), ("Here", None)))))
        self.assertTrue(any("does not resolve" in x and "/gone/" in x for x in missing), missing)

    def test_a_breadcrumblist_with_one_item_or_wrong_positions_is_reported(self):
        one = self.seo(good(ld(crumbs(("Only", None)))))
        self.assertTrue(any("at least 2" in x for x in one), one)
        wrong = crumbs(("Top", BASE + "/"), ("Here", None))
        wrong["itemListElement"][1]["position"] = 5
        p = self.seo(good(ld(wrong)))
        self.assertTrue(any("wrong position" in x for x in p), p)

    def test_a_company_name_in_the_structured_data_is_reported(self):
        art = {"@context": "https://schema.org", "@type": "Article", "headline": "h", "publisher": {"@type": "Organization", "name": "株式会社テスト"}}
        p = self.seo(good(ld(art)))
        self.assertTrue(any("names a company" in x for x in p), p)
        ok = dict(art, publisher={"@type": "Organization", "name": "テスト速報"})
        self.assertEqual(self.seo(good(ld(ok))), [])

    def test_the_live_check_does_not_apply_the_seo_rule(self):
        files = good('<a href="/month/">こちら</a>')
        s = Site(files)
        self.addCleanup(s.tmp.cleanup)
        self.assertEqual([p for p in s.check(skip=("links", "sitemap", "seo")) if "[seo]" in p], [])

    def test_an_svg_title_does_not_become_the_page_title(self):
        files = good('<svg><title>Chart caption</title></svg>')
        site = Site(files)
        self.addCleanup(site.tmp.cleanup)
        self.assertEqual(sitecheck.parse(site.root / "index.html").title, "t")


class SeoReportTest(unittest.TestCase):
    def report(self, files):
        s = Site(files)
        self.addCleanup(s.tmp.cleanup)
        return sitecheck.seo_report(s.root, BASE)

    def test_duplicate_titles_descriptions_and_h1_are_listed(self):
        files = good()          # both pages: title 't', description 'd'
        files["month/index.html"] = page('<h1>Top</h1><p>x</p><a href="/">top</a>', "month/")
        r = self.report(files)
        self.assertTrue(any(x.startswith("[dup-title]") for x in r), r)
        self.assertTrue(any(x.startswith("[dup-desc]") for x in r), r)
        self.assertTrue(any(x.startswith("[dup-h1]") for x in r), r)

    def test_a_noindex_page_is_not_a_duplicate(self):
        files = good()
        files["month/index.html"] = page('<h1>Months</h1><p>x</p><a href="/">top</a>', "month/",
                                         head='<title>t</title><meta name="description" content="d"><meta name="robots" content="noindex"><link rel="canonical" href="https://example.test/{p}">')
        self.assertFalse([x for x in self.report(files) if x.startswith("[dup-")])

    def test_long_titles_short_descriptions_and_pages_few_links_point_to_are_listed(self):
        head = '<title>' + "あ" * 61 + '</title><meta name="description" content="短い"><link rel="canonical" href="https://example.test/{p}">'
        files = good()
        files["month/index.html"] = page('<h1>Months</h1><p>x</p><a href="/">top</a>', "month/", head=head)
        r = self.report(files)
        self.assertTrue(any(x.startswith("[title-long] month/index.html") for x in r), r)
        self.assertTrue(any(x.startswith("[desc-short] month/index.html") for x in r), r)
        self.assertTrue(any(x.startswith("[few-links-in] month/index.html") for x in r), r)       # only the home page links to it


if __name__ == "__main__":
    unittest.main()
