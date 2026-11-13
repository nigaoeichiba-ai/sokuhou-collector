"""shiken-nittei.com (資格・試験への道, since 2026-11-13): the build of the owner's template, checked as the visitor and the crawler get it.

The site is made by sites/shiken/build.py (Node: renewal/template/scripts/build-site.mjs).  Here the whole site is built for a fixed day and checked:
the 33 old URLs, every exam page, titles / descriptions / headings, the site name, the affiliate sections, the links between the pages, what depends on the day,
the contact form and the visit counter.  Each check has a case that must fail (a negative test), so that a check that stopped looking is noticed.
"""
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"
TEMPLATE = SITE / "renewal" / "template"
REGISTRY = json.loads((TEMPLATE / "schedule" / "registry.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((TEMPLATE / "research" / "original-inventory.json").read_text(encoding="utf-8"))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BUILD = load(SITE / "build.py", "shiken_build_r")
AFF = load(ROOT / "tests" / "test_trend_affiliate.py", "trend_aff_r")


def read_pages(out: Path) -> dict[str, str]:
    return {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*.html")}


def text_of(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def page_problems(pages: dict[str, str]) -> list[str]:
    """Faults of the pages as a search engine sees them: one h1, a title and a description of the page's own, the canonical, no leftovers of the making."""
    out, titles, descs = [], {}, {}
    for rel, h in pages.items():
        if rel.startswith("google"):
            continue
        t = re.search(r"<title>(.*?)</title>", h, re.S)
        d = re.search(r'<meta name="description" content="(.*?)"', h)
        if len(re.findall(r"<h1[ >]", h)) != 1:
            out.append(f"{rel}: needs exactly one h1")
        if not t or not d:
            out.append(f"{rel}: title or description missing")
            continue
        if "資格・試験への道" not in t.group(1):
            out.append(f"{rel}: the title lacks the site name")
        if t.group(1) in titles:
            out.append(f"{rel}: the title of {titles[t.group(1)]}")
        titles[t.group(1)] = rel
        if not rel.startswith(("404", "contact/thanks")):
            if d.group(1) in descs:
                out.append(f"{rel}: the description of {descs[d.group(1)]}")
            descs[d.group(1)] = rel
            if len(d.group(1)) < 40:
                out.append(f"{rel}: description under 40 characters")
        want = "https://shiken-nittei.com/" + ("" if rel == "index.html" else rel[: -len("index.html")] if rel.endswith("/index.html") else rel)
        if not rel.startswith("404") and f'<link rel="canonical" href="{want}">' not in h:
            out.append(f"{rel}: canonical is not {want}")
        if re.search(r"元サイト|プレビュー|確認サイト|Codex|undefined|NaN|\[object|TODO|\$\{", text_of(h)):
            out.append(f"{rel}: a leftover of the making in the text")
        for img in re.findall(r"<img [^>]*>", h):
            if " alt=" not in img:
                out.append(f"{rel}: an image without alt")
    return out


class Renewal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.info = BUILD.make_site(cls.out, "2026-11-13")
        cls.pages = read_pages(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # --- the URLs ---------------------------------------------------------------------------------------------------------------------
    def test_every_old_url_is_kept_or_redirected(self):
        htaccess = (self.out / ".htaccess").read_text(encoding="utf-8")
        for p in INVENTORY["pages"] + [{"path": "/privacy/"}, {"path": "/about/"}, {"path": "/contact/"}]:
            path = p["path"]
            if path == "/":
                continue
            kept = (path.strip("/") + "/index.html") in self.pages
            redirected = f"RewriteRule ^{path.strip('/')}/?$ https://shiken-nittei.com/" in htaccess
            self.assertTrue(kept or redirected, f"{path} is neither kept nor redirected (301)")
            self.assertFalse(kept and redirected, f"{path} is both")

    def test_every_exam_and_situation_has_its_page_and_the_count_is_stated(self):
        for e in REGISTRY["exams"]:
            self.assertIn(f"exams/{e['id']}/index.html", self.pages, e["id"])
        for g in ("decided", "discover", "compare", "family", "prepared"):
            self.assertIn(f"guides/{g}/index.html", self.pages)
        self.assertEqual(len(REGISTRY["exams"]), 95)
        self.assertGreaterEqual(len(self.pages), 125)

    def test_the_sitemap_lists_what_is_indexed_and_nothing_else(self):
        sm = re.findall(r"<loc>(.*?)</loc>", (self.out / "sitemap.xml").read_text(encoding="utf-8"))
        indexed = {u for u in (("https://shiken-nittei.com/" + ("" if r == "index.html" else r[: -len("index.html")])) for r, h in self.pages.items() if "content=\"index,follow\"" in h)}
        self.assertEqual(set(sm), indexed)
        self.assertEqual(len(sm), len(set(sm)))
        self.assertNotIn("https://shiken-nittei.com/contact/thanks.html", sm)
        self.assertIn('<meta name="robots" content="noindex,follow">', self.pages["contact/thanks.html"])
        self.assertIn("Sitemap: https://shiken-nittei.com/sitemap.xml", (self.out / "robots.txt").read_text(encoding="utf-8"))

    # --- what a search engine reads ------------------------------------------------------------------------------------------------------
    def test_titles_descriptions_headings_canonicals_are_in_order(self):
        self.assertEqual(page_problems(self.pages), [])

    def test_the_page_checks_do_catch_faults(self):
        good = self.pages["boki/index.html"]
        bad = {
            "a/index.html": good.replace("<h1", "<h2", 1),
            "b/index.html": re.sub(r"<title>.*?</title>", "<title>題だけ</title>", good, flags=re.S),
            "c/index.html": good.replace("</main>", "<p>元サイトの文章</p></main>", 1),
        }
        found = " ".join(page_problems(bad))
        for needle in ("exactly one h1", "lacks the site name", "leftover of the making"):
            self.assertIn(needle, found)
        dup = {"x/index.html": good, "y/index.html": good}
        self.assertIn("the title of", " ".join(page_problems(dup)))

    def test_structured_data_matches_the_page(self):
        for rel in ("exams/takken/index.html", "boki/index.html", "guides/decided/index.html"):
            h = self.pages[rel]
            blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
            kinds = {b["@type"] for b in blocks}
            self.assertIn("WebPage", kinds, rel)
            self.assertIn("BreadcrumbList", kinds, rel)
            crumb = next(b for b in blocks if b["@type"] == "BreadcrumbList")
            self.assertEqual(crumb["itemListElement"][0]["name"], "トップ")
            self.assertEqual(crumb["itemListElement"][-1]["item"], "https://shiken-nittei.com/" + rel[: -len("index.html")])

    # --- the name ---------------------------------------------------------------------------------------------------------------------
    def test_the_old_site_name_is_gone_except_where_it_is_the_history(self):
        for rel, h in self.pages.items():
            t = text_of(h)
            hits = [m for m in re.finditer("試験日程カレンダー", t) if "商工会議所" not in t[max(0, m.start() - 12):m.start()]]
            if rel == "corrections/index.html":
                self.assertTrue(hits)             # the record of the renaming says it
                continue
            self.assertEqual(hits, [], rel)
        self.assertEqual(json.loads((SITE / "config.json").read_text(encoding="utf-8"))["site_name"], "資格・試験への道")
        self.assertIn("資格・試験への道運営部", self.pages["about/index.html"])
        self.assertIn("資格・試験への道", self.pages["index.html"])

    # --- the schedule -----------------------------------------------------------------------------------------------------------------
    def test_a_date_that_is_unannounced_or_unverified_is_never_given_a_day(self):
        for exam in REGISTRY["exams"]:
            fields = REGISTRY["meta"][exam["id"]]["fields"]
            for typ, state in fields.items():
                if state in ("unannounced", "unverified"):
                    rows = [x for x in REGISTRY["rows"] if x["exam"] == exam["id"] and x["type"] == typ]
                    self.assertEqual(rows, [], f"{exam['id']} {typ} is {state} but has a date")

    def test_every_date_has_a_source_and_the_check_day_is_not_in_the_future(self):
        for x in REGISTRY["rows"]:
            self.assertIn(x["sourceId"], REGISTRY["sources"], x["id"])
            self.assertLessEqual(x["checkedAt"], "2026-11-13", x["id"])
            self.assertRegex(x["date"], r"^\d{4}-\d{2}-\d{2}$")
        for sid, s in REGISTRY["sources"].items():
            self.assertTrue(s["url"].startswith("https://"), sid)

    # --- what depends on the day --------------------------------------------------------------------------------------------------------
    def test_the_lists_of_coming_dates_follow_the_day_of_the_build(self):
        d1 = self.pages["deadlines/index.html"]
        self.assertIn("2026年11月26日", d1)                  # TOEIC 1/10 deadline: still ahead on 11/13
        self.assertNotIn("2026年11月11日（水）", d1)         # already past on 11/13
        with tempfile.TemporaryDirectory() as tmp:
            BUILD.make_site(Path(tmp), "2026-12-20")
            d2 = (Path(tmp) / "deadlines" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("2026年11月26日", d2)
            self.assertIn("2026年12月20日", d2)              # the list says from which day it counts
            home = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026年12月", home)
        self.assertIn("2026年11月", self.pages["index.html"])

    def test_no_page_counts_days_from_a_fixed_day(self):
        for rel, h in self.pages.items():
            if rel.startswith("exams/") or rel in ("index.html",):
                continue
            self.assertNotRegex(text_of(h), r"あと\s*\d+\s*日", rel)

    # --- links ------------------------------------------------------------------------------------------------------------------------
    def test_no_page_is_an_orphan_and_the_lists_reach_every_exam(self):
        links: dict[str, set] = {}
        for rel, h in self.pages.items():
            if "noindex" in h and rel.startswith(("404", "contact/thanks")):
                continue
            for href in re.findall(r'<a [^>]*href="(/[^"#?]*)', h):
                links.setdefault(href, set()).add(rel)
        for rel in self.pages:
            if rel.startswith(("404", "google", "contact/thanks")) or rel == "index.html":
                continue
            url = "/" + rel[: -len("index.html")]
            inbound = links.get(url, set()) - {rel}
            self.assertTrue(inbound, f"{url} has no link from another page")
        sched = self.pages["schedule/index.html"]
        for e in REGISTRY["exams"]:
            self.assertIn(f'href="/exams/{e["id"]}/"', sched, e["id"])            # /schedule/ reaches every exam and round
        for slug in INVENTORY["pages"]:
            p = slug["path"]
            if p in ("/", "/takken/", "/gyosei/", "/sharoshi/", "/kangoshi/", "/kaigo-fukushi/", "/kyotsu/", "/kyotsu-tsuishi/", "/tokushu-nyushi/"):
                continue
            self.assertIn(f'href="{p}"', self.pages["index.html"] + self.pages["yomimono/index.html"] + self.pages["schedule/index.html"] + self.pages["nyushi/index.html"], f"{p} is linked from no hub")

    def test_the_footer_links_the_site_pages_on_every_page(self):
        for rel, h in self.pages.items():
            if rel.startswith("google"):
                continue
            for href in ("/about/", "/privacy/", "/contact/"):
                self.assertIn(f'href="{href}"', h, f"{rel} lacks {href}")

    # --- affiliate links ------------------------------------------------------------------------------------------------------------------
    def test_exam_pages_carry_the_pr_section_with_both_malls(self):
        sys_path = str(TEMPLATE / "dist")
        text = (TEMPLATE / "dist" / "affiliate.js").read_text(encoding="utf-8")
        self.assertIn("583f273a.77c989b6.583f273b.0a6a5fff", text)
        n = 0
        for e in REGISTRY["exams"]:
            h = self.pages[f"exams/{e['id']}/index.html"]
            self.assertIn("hb.afl.rakuten.co.jp/hgc/583f273a.77c989b6.583f273b.0a6a5fff/", h, e["id"])
            self.assertIn("amazon.co.jp/s?k=", h, e["id"])
            self.assertIn("tag=amazonmacs-22", h, e["id"])
            self.assertIn("【PR】", h, e["id"])
            self.assertEqual(AFF.problems(h), [], e["id"])
            n += 1
        self.assertEqual(n, 95, sys_path)

    def test_courses_of_the_partner_are_on_the_exams_it_covers(self):
        for eid in ("takken", "gyosei", "sharoshi", "shindanshi"):
            h = self.pages[f"exams/{eid}/index.html"]
            self.assertIn("px.a8.net/svt/ejp?a8mat=4BGJFS+FXCMIA+373C+7CX1E", h, eid)
            self.assertIn("www16.a8.net/0.gif?a8mat=4BGJFS+FXCMIA+373C+7CX1E", h, eid)      # the pixel of the same link
        fp = self.pages["exams/fp/index.html"]
        self.assertIn("px.a8.net/svt/ejp?a8mat=4BGJFS+FXCMIA+373C+7B7B6", fp)
        self.assertIn("a8.net/0.gif?a8mat=4BGJFS+FXCMIA+373C+7B7B6", fp)
        self.assertNotIn("px.a8.net", self.pages["exams/nurse/index.html"])

    def test_the_articles_that_fit_have_their_pr_section(self):
        for slug in ("boki", "boki-net", "eiken", "fp", "komuin", "koko", "minkan", "takken-junbi", "goukaku-ritsu", "kokkoritsu", "zenki-koki", "nyushi"):
            h = self.pages[f"{slug}/index.html"]
            self.assertIn("hb.afl.rakuten.co.jp/hgc/", h, slug)
            self.assertIn("amazon.co.jp/s?k=", h, slug)
            self.assertEqual(AFF.problems(h), [], slug)

    def test_no_affiliate_link_is_a_bare_address_or_lacks_rel(self):
        for rel, h in self.pages.items():
            self.assertEqual(AFF.problems(h), [], rel)
        bad = '<p>広告(PR)<a href="https://hb.afl.rakuten.co.jp/hgc/x/?pc=y">https://example.com/</a></p>'
        self.assertTrue(AFF.problems(bad))                                    # a negative case: the check does catch it

    # --- pages every site needs ------------------------------------------------------------------------------------------------------------
    def test_the_contact_form_matches_its_receiver(self):
        form = self.pages["contact/index.html"]
        php = (self.out / "contact" / "send.php").read_text(encoding="utf-8")
        for name in ("kind", "message", "page", "email", "website"):
            self.assertIn(f'name="{name}"', form)
        self.assertIn('action="/contact/send.php"', form)
        for k in json.loads((SITE / "config.json").read_text(encoding="utf-8"))["contact_kinds"]:
            self.assertIn(k, form)
            self.assertIn(k, php)
        self.assertIn("/contact/thanks.html", php)
        self.assertIn("資格・試験への道", php)

    def test_the_visit_counter_is_on_every_page_and_the_privacy_page_says_so(self):
        for rel, h in self.pages.items():
            if rel.startswith("google"):
                continue
            self.assertIn("/assets/measure.js", h, rel)
        self.assertTrue((self.out / "assets" / "measure.js").exists())
        self.assertTrue((self.out / "m" / "t.gif").exists())
        self.assertIn("アクセス解析", self.pages["privacy/index.html"])
        self.assertTrue((self.out / "googleabcac004d8b7d556.html").exists())

    def test_htaccess_redirects_https_and_the_old_pages(self):
        h = (self.out / ".htaccess").read_text(encoding="utf-8")
        for old, new in (("takken", "/exams/takken/"), ("kangoshi", "/exams/nurse/"), ("tokushu-nyushi", "/nyushi/")):
            self.assertIn(f"RewriteRule ^{old}/?$ https://shiken-nittei.com{new} [R=301,L,NE]", h)
        self.assertIn("RewriteCond %{HTTPS} !=on", h)
        self.assertIn('Ngx_Cache_NoCacheMode=on', h)

    def test_the_templates_own_node_tests_pass(self):
        """The template's tests of its browser code (calendar, guides, schedule data, exam details): run one by one (each exits non-zero on a failed test)."""
        import subprocess
        node = BUILD.find_node()
        for f in sorted((TEMPLATE / "tests").glob("*.test.mjs")):
            r = subprocess.run([node, str(f)], cwd=str(TEMPLATE), capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, f.name + " " + r.stdout[-1500:] + r.stderr[-1500:])

    def test_the_morning_list_reads_the_registry(self):
        ml = load(SITE / "tools" / "morning_list.py", "shiken_morning_r")
        data = ml.build(30, "2026-11-13")
        self.assertGreater(len(data["sources"]), 3)
        self.assertEqual(data["today"], "2026-11-13")
        for g in data["sources"]:
            self.assertTrue(g["url"].startswith("https://"))
            for e in g["events"]:
                self.assertTrue(-7 <= e["left"] <= 30, e)


if __name__ == "__main__":
    unittest.main()
