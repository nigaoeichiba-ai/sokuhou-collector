"""The site checker must catch the kinds of defect that reached the live sites, not only pass on clean pages.

Each negative test builds a tiny site that contains exactly one defect that really happened (or its mechanism) and asserts that the checker names it.
A checker that cannot fail is worthless: this is what the first version of the checks lacked.
"""
import tempfile
import unittest
from pathlib import Path

from sokuhou import sitecheck

BASE = "https://example.test"
HEAD = '<title>t</title><meta name="description" content="d"><link rel="canonical" href="https://example.test/{p}">'


def page(body, path="", head=None):
    return f"<!doctype html><html><head>{(head if head is not None else HEAD).format(p=path)}</head><body><main>{body}</main></body></html>"


def sitemap(*paths):
    return '<?xml version="1.0"?><urlset>' + "".join(f"<url><loc>{BASE}/{p}</loc></url>" for p in paths) + "</urlset>"


class Site:
    def __init__(self, files):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, text in files.items():
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")

    def check(self, **kw):
        return sitecheck.check_dir(self.root, BASE, **kw)


def good(extra_body="", **more):
    files = {"index.html": page('<h1>Top</h1><p>hello</p><a href="/month/">m</a>' + extra_body),
             "month/index.html": page('<h1>Months</h1><p>x</p><a href="/">top</a>', "month/"),
             "sitemap.xml": sitemap("", "month/")}
    files.update(more)
    return files


class CheckerTest(unittest.TestCase):
    def problems(self, files, **kw):
        s = Site(files)
        self.addCleanup(s.tmp.cleanup)
        return s.check(**kw)

    def test_a_clean_site_passes(self):
        self.assertEqual(self.problems(good()), [])

    def test_a_link_to_a_page_that_does_not_exist_is_reported_like_the_month_10_404(self):
        p = self.problems(good('<a href="/month/10/">October</a>'))
        self.assertTrue(any("[links]" in x and "/month/10/" in x for x in p), p)

    def test_a_missing_image_stylesheet_or_script_is_reported(self):
        p = self.problems(good('<img src="/img/a.webp" alt=""><script src="/a.js"></script>'))
        self.assertEqual(sum("[links]" in x for x in p), 2, p)

    def test_relative_links_and_fragments_resolve_against_the_page(self):
        files = good()
        files["month/index.html"] = page('<h1>M</h1><p>x</p><a href="../">up</a><a href="#top">frag</a><a href="/?q=1">q</a>', "month/")
        self.assertEqual(self.problems(files), [])

    def test_external_mailto_and_other_host_links_are_not_checked(self):
        self.assertEqual(self.problems(good('<a href="https://other.test/x">o</a><a href="mailto:a@b.c">m</a>')), [])

    def test_a_page_missing_from_the_sitemap_and_a_sitemap_url_without_a_page_are_reported(self):
        files = good()
        files["sitemap.xml"] = sitemap("", "gone/")
        p = self.problems(files)
        self.assertTrue(any("[sitemap]" in x and "gone/" in x for x in p), p)
        self.assertTrue(any("[sitemap]" in x and "month/index.html" in x and "missing" in x for x in p), p)

    def test_noindex_pages_and_the_404_page_do_not_need_the_sitemap_or_head_tags(self):
        files = good()
        files["contact/thanks.html"] = '<html><head><meta name="robots" content="noindex,nofollow"></head><body><p>ok</p></body></html>'
        files["404.html"] = "<html><body><h1>no</h1></body></html>"
        self.assertEqual(self.problems(files), [])

    def test_head_rules(self):
        files = good()
        files["month/index.html"] = "<html><head></head><body><h1>a</h1><h1>b</h1></body></html>"
        p = self.problems(files)
        for frag in ("no <title>", "no meta description", "2 <h1>", "no canonical"):
            self.assertTrue(any(frag in x for x in p), (frag, p))

    def test_a_canonical_on_another_host_is_reported(self):
        files = good()
        files["month/index.html"] = page("<h1>M</h1><p>x</p>", head='<title>t</title><meta name="description" content="d"><link rel="canonical" href="https://elsewhere.test/month/">')
        self.assertTrue(any("another host" in x for x in self.problems(files)))

    def test_leaked_python_and_template_values_are_reported_but_ordinary_words_are_not(self):
        p = self.problems(good("<p>価格 None 円</p><p>{{name}}</p><p>undefined</p>"))
        self.assertEqual(sum("[leaks]" in x for x in p), 3, p)
        self.assertEqual(self.problems(good("<p>Nonetheless, a nonempty answer</p>")), [])

    def test_a_table_outside_the_scroll_frame_is_reported_and_one_inside_is_not(self):
        t = "<table><tr><td>a</td></tr></table>"
        self.assertTrue(any("[tables]" in x for x in self.problems(good(t))))
        self.assertEqual(self.problems(good('<div class="tablewrap">' + t + "</div>")), [])

    def test_an_empty_section_an_empty_list_and_an_empty_href_are_reported(self):
        p = self.problems(good("<section><h2>Empty</h2></section><section><h2>Next</h2><p>text</p></section>"))
        self.assertTrue(any("[empty]" in x and "Empty" in x for x in p), p)
        self.assertTrue(any("empty list" in x for x in self.problems(good("<ul></ul>"))))
        self.assertTrue(any("empty href" in x for x in self.problems(good('<a href="">x</a>'))))

    def test_a_section_with_a_list_a_table_or_an_image_is_not_empty_and_a_script_filled_list_is_allowed(self):
        body = ('<h2>List</h2><ul><li>a</li></ul><h2>Table</h2><div class="tablewrap"><table><tr><td>1</td></tr></table></div>'
                '<h2>Image</h2><img src="/month/index.html" alt=""><h2>Live</h2><ul aria-live="polite"></ul><h3>Deeper</h3><p>x</p>')
        self.assertEqual(self.problems(good(body)), [])

    def test_an_image_without_alt_is_reported_but_a_hidden_script_filled_one_is_fine(self):
        self.assertTrue(any("[images]" in x for x in self.problems(good('<img src="/month/index.html">'))))
        self.assertEqual(self.problems(good('<img alt="x" hidden>')), [])

    def test_skipped_rules_are_left_out(self):
        self.assertEqual(self.problems(good("<ul></ul>"), skip=("lists",)), [])

    def test_a_folder_without_pages_fails(self):
        self.assertTrue(self.problems({"readme.txt": "x"}))


if __name__ == "__main__":
    unittest.main()
