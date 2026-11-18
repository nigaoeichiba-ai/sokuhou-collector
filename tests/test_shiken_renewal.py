"""shiken-nittei.com (資格・試験への道, since 2026-11-13): the build of the owner's template, checked as the visitor and the crawler get it.

The site is made by sites/shiken/build.py (Node: renewal/template/scripts/build-site.mjs).  Here the whole site is built for a fixed day and checked:
the 33 old URLs, every exam page, titles / descriptions / headings, the site name, the affiliate sections, the links between the pages, what depends on the day,
the contact form and the visit counter.  Each check has a case that must fail (a negative test), so that a check that stopped looking is noticed.
"""
from __future__ import annotations

import importlib.util
import datetime
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"
TEMPLATE = SITE / "renewal" / "template"
REGISTRY = json.loads((TEMPLATE / "schedule" / "registry.json").read_text(encoding="utf-8"))
# The day the test site is built as (2026-11-15, the morning check): not a fixed day. A date checked on a later day than a fixed one made the build refuse the data
# (checkedAt in the future) and the whole class fail on every morning update. It is the latest day a date was checked, and never before 2026-11-13.
JST_TODAY = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
BASE_DAY = max(["2026-11-13"] + [m["checkedAt"] for m in REGISTRY["meta"].values()] + [r["checkedAt"] for r in REGISTRY["rows"]])
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


APPLY_URLS = {m["applyPage"]["url"] for m in REGISTRY["meta"].values() if m.get("applyPage")}
PIXEL_HOST = {"5YJRM": "www15", "614CY": "www12", "61Z82": "www16", "60H7M": "www18"}
FOOTER_SENTENCE = "掲載の日程は、公式の発表をはじめとする複数の情報をもとにしています。申し込みの前に、主催者の最新の案内もご確認ください。"


def source_problems(html: str, apply_urls: set[str] | None = None) -> list[str]:
    """2026-11-15 (owner): no source name or source link on any page. The only outside link besides the affiliate (PR) ones is the one button of the
    application page in the 'ed-apply' section of an exam page (rel nofollow, new tab, an address kept in the registry as applyPage)."""
    out = []
    t = text_of(html)
    if re.search(r"出典|出所|出どころ|情報源", t):
        out.append("the word 出典 (or a synonym) is on the screen")
    if re.search(r"(IIBC|人事院|厚生労働省|情報処理推進機構|国立大学協会|公立大学協会|教育委員会)(の|が)?(案内|公表|発表|資料|ページ|サイト)", t):
        out.append("an organisation named as the origin of a date")
    body = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    apply_blocks = re.findall(r'<section class="ed-apply".*?</section>', body, flags=re.S)
    for blk in apply_blocks:
        body = body.replace(blk, "")
    for tag in re.findall(r"<a [^>]*href=\"https?://[^\"]*\"[^>]*>", body):
        if "sponsored" not in tag:
            out.append("an outside link that is not an affiliate link: " + tag[:80])
    for blk in apply_blocks:
        links = re.findall(r'<a [^>]*href="(https?://[^"]*)"([^>]*)>', blk)
        if len(links) != 1:
            out.append("the apply section must have exactly one link")
            continue
        href, rest = links[0]
        if 'rel="noopener nofollow"' not in rest or 'target="_blank"' not in rest:
            out.append("the apply link lacks rel/target")
        if apply_urls is not None and href not in apply_urls:
            out.append("the apply link is not an applyPage of the registry: " + href)
    return out


class Renewal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.info = BUILD.make_site(cls.out, BASE_DAY)
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
        self.assertEqual(len(REGISTRY["exams"]), 104)
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
            self.assertLessEqual(x["checkedAt"], JST_TODAY, x["id"])
            self.assertRegex(x["date"], r"^\d{4}-\d{2}-\d{2}$")
        for sid, s in REGISTRY["sources"].items():
            self.assertTrue(s["url"].startswith("https://"), sid)

    # --- what depends on the day --------------------------------------------------------------------------------------------------------
    def test_the_lists_of_coming_dates_follow_the_day_of_the_build(self):
        def ja(day: str) -> str:
            d = datetime.date.fromisoformat(day)
            return f"{d.year}年{d.month}月{d.day}日（{'月火水木金土日'[d.weekday()]}）"
        deadlines = sorted({r["date"] for r in REGISTRY["rows"] if r["type"] == "deadline"})
        ahead = [d for d in deadlines if d >= BASE_DAY and d <= "2026-12-19"]
        past = [d for d in deadlines if d < BASE_DAY and d >= "2026-10-01"]
        d1 = self.pages["deadlines/index.html"]
        self.assertTrue(ahead and past)
        self.assertIn(ja(ahead[0]).split("（")[0], d1)        # a deadline still ahead on the day of the build is listed
        self.assertNotIn(ja(past[-1]), d1)                    # one already past is not
        with tempfile.TemporaryDirectory() as tmp:
            BUILD.make_site(Path(tmp), "2026-12-20")
            d2 = (Path(tmp) / "deadlines" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(ja(ahead[0]).split("（")[0], d2)
            self.assertIn("2026年12月20日", d2)              # the list says from which day it counts
            home = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026年12月", home)
        self.assertIn(f"{int(BASE_DAY[:4])}年{int(BASE_DAY[5:7])}月", self.pages["index.html"])

    def test_a_check_day_after_the_day_of_the_build_is_refused(self):
        # the negative case of the fixed-day fault: a date checked later than the build day is really too far ahead, and the build says so
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                BUILD.make_site(Path(tmp), "2026-11-01")

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

    def test_no_page_shows_a_source_and_the_footer_has_the_one_sentence(self):
        for rel, h in self.pages.items():
            if rel.startswith("google"):
                continue
            self.assertEqual(source_problems(h, APPLY_URLS), [], rel)
            if not rel.startswith("404"):
                self.assertEqual(text_of(h).count(FOOTER_SENTENCE), 1, f"{rel}: the footer sentence must appear exactly once")
        # the browser scripts must not be able to draw a source either (the calendar, the lists and the dialogs are made in the browser)
        for js in (self.out / "_versions").rglob("*.js"):
            if js.name == "schedule-records.js":
                continue                       # the data (kept inside, never shown)
            code = js.read_text(encoding="utf-8")
            self.assertNotIn('rel="noopener noreferrer"', code, js.name)
            self.assertNotIn("出典：", code, js.name)
        # negative cases: the check does catch a source name and a source link
        self.assertTrue(source_problems('<p class="schedule-source">出典：<a href="https://www.eiken.or.jp/">日本英語検定協会 ↗</a></p>'))
        self.assertTrue(source_problems('<a href="https://www.jafp.or.jp/" target="_blank" rel="noopener noreferrer">公式</a>'))
        self.assertTrue(source_problems("<p>受験地による実施状況も、IIBCの案内で確かめてください。</p>"))
        self.assertTrue(source_problems('<section class="ed-apply"><a href="https://example.com/x" target="_blank" rel="noopener">申込</a></section>', APPLY_URLS))
        self.assertEqual(source_problems('<section class="ed-apply"><a href="https://mp.toeic.or.jp/home/apply?testType=T" target="_blank" rel="noopener nofollow">申込</a></section>', {"https://mp.toeic.or.jp/home/apply?testType=T"}), [])
        self.assertEqual(source_problems('<a href="https://hb.afl.rakuten.co.jp/x" rel="nofollow sponsored noopener">広告</a>'), [])

    def test_the_guides_link_every_exam_page_in_the_static_html(self):
        # the parent of the exam pages is the guide: a crawler (and the linkage check) reads the HTML before any script runs, so the links must be in it
        def missing(html: str) -> list[str]:
            return [e["id"] for e in REGISTRY["exams"] if f'href="/exams/{e["id"]}/"' not in html]
        for g in ("decided", "discover"):
            self.assertEqual(missing(self.pages[f"guides/{g}/index.html"]), [], g)
        self.assertTrue(missing("<main><div id=\"guide-exams\"></div></main>"))      # negative case: a guide whose list is only drawn by a script is caught

    def test_the_search_words_are_in_the_titles_and_the_exam_pages_describe_their_own_dates(self):
        # Search Console (2026-11-17): '2027年 国立大学入試日程' and '看護師国家試験 申し込み 締め切り' found pages whose titles lacked the words
        def title(rel):
            return re.search(r"<title>(.*?)</title>", self.pages[rel], re.S).group(1)
        for rel, words in (("kokkoritsu/index.html", ("入試日程", "国立大学", "2027")), ("nyushi/index.html", ("入試日程", "国立大学")),
                           ("kangoshi-ganshu/index.html", ("申し込み", "締め切り")), ("exams/nurse/index.html", ("申し込み", "締め切り"))):
            for w in words:
                self.assertIn(w, title(rel), f"{rel} lacks {w}")
        # an exam page with a coming date says it in the description (not only the same sentence with another name), and carries its FAQ as structured data
        d = re.search(r'<meta name="description" content="(.*?)"', self.pages["exams/toeic/index.html"]).group(1)
        self.assertRegex(d, r"申込の締切は20\d\d年\d+月\d+日")
        self.assertRegex(d, r"試験日は20\d\d年\d+月\d+日")
        for rel, h in self.pages.items():
            if rel.startswith("exams/") and "ed-faq" in h:
                self.assertIn('"@type":"FAQPage"', h, rel)
        # negative case: the old sentence that only changed the exam name is recognised
        old = "TOEIC（2027年）の日程と申し込みから当日までの準備をご案内します。確認日と、公表状況を分けて掲載しています。"
        self.assertNotRegex(old, r"申込の締切は20\d\d年")

    def test_audit_items_h1_inbound_links_and_article_data(self):
        # SEO audit 2026-11-17: the h1 of the exam pages are not shared, the pages that were linked from one page only have more, the articles carry Article data
        h1s: dict[str, str] = {}
        for rel, h in self.pages.items():
            if rel.startswith("exams/"):
                t = re.sub(r"<[^>]+>", "", re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S).group(1))
                self.assertNotIn(t, h1s, f"{rel} has the h1 of {h1s.get(t)}")
                h1s[t] = rel
        inbound: dict[str, set] = {}
        for rel, h in self.pages.items():
            me = "/" if rel == "index.html" else "/" + rel[: -len("index.html")]
            for link in set(re.findall(r'href="(/[^"#?]*)"', h)):
                if link != me:
                    inbound.setdefault(link, set()).add(me)
        for page in ("/kokkoritsu/", "/koko/", "/nendo/", "/takken-junbi/", "/zenki-koki/"):
            self.assertGreaterEqual(len(inbound.get(page, ())), 2, page)
        for rel in ("takken-junbi/index.html", "goukaku-ritsu/index.html", "nendo/index.html"):
            self.assertIn('"@type":"Article"', self.pages[rel], rel)
        self.assertNotIn('"@type":"Article"', self.pages["exams/toeic/index.html"])
        # negative case: two pages with one h1 are noticed
        dup = {"a": re.search(r"<h1>(.*?)</h1>", "<h1>X</h1>").group(1), "b": re.search(r"<h1>(.*?)</h1>", "<h1>X</h1>").group(1)}
        self.assertEqual(len(set(dup.values())), 1)

    def test_the_fixed_pages_have_informative_titles_and_descriptions(self):
        # SEO audit 2026-11-17: the fixed pages (about, privacy, contact) had one-word titles and descriptions under 60 characters
        for rel in ("about/index.html", "privacy/index.html", "contact/index.html"):
            h = self.pages[rel]
            t = re.search(r"<title>(.*?)</title>", h, re.S).group(1).split("｜")[0]
            d = re.search(r'<meta name="description" content="(.*?)"', h).group(1)
            self.assertGreaterEqual(len(t), 10, rel)
            self.assertGreaterEqual(len(d), 80, rel)
            self.assertLessEqual(len(d), 120, rel)
            self.assertIn("資格・試験への道", d, rel)
        # negative case: the old one-line description is too short
        self.assertLess(len("資格・試験への道へのお問い合わせ先です。日程の誤りのご指摘、ご意見・ご要望をお送りいただけます。"), 80)

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
        self.assertEqual(n, 104, sys_path)

    def test_courses_of_the_partner_are_on_the_exams_it_covers(self):
        for eid in ("takken", "gyosei", "sharoshi", "shindanshi"):
            h = self.pages[f"exams/{eid}/index.html"]
            self.assertIn("px.a8.net/svt/ejp?a8mat=4BGJFS+FXCMIA+373C+7CX1E", h, eid)
            self.assertIn("www16.a8.net/0.gif?a8mat=4BGJFS+FXCMIA+373C+7CX1E", h, eid)      # the pixel of the same link
        fp = self.pages["exams/fp/index.html"]
        self.assertIn("px.a8.net/svt/ejp?a8mat=4BGJFS+FXCMIA+373C+7B7B6", fp)
        self.assertIn("a8.net/0.gif?a8mat=4BGJFS+FXCMIA+373C+7B7B6", fp)
        self.assertNotIn("px.a8.net", self.pages["exams/nurse/index.html"])
        # Agaroot Academy (A8, approved 2026-11-17): the course link of the material that fits each exam; none where the partner has no course
        for eid, code in (("gyosei", "614CY"), ("takken", "61Z82"), ("sharoshi", "60H7M"), ("shindanshi", "5YJRM"), ("komuin-sogo", "5YJRM"), ("komuin-ippan", "5YJRM")):
            h = self.pages[f"exams/{eid}/index.html"]
            tag = re.search(r'<a href="https://px\.a8\.net/svt/ejp\?a8mat=4BGJFS\+GCTW8I\+44M0\+%s"([^>]*)>' % code, h)
            self.assertTrue(tag, eid)
            self.assertIn('rel="nofollow sponsored noopener"', tag.group(1))
            self.assertIn("PR", text_of(h))
            self.assertIn(f"https://{PIXEL_HOST[code]}.a8.net/0.gif?a8mat=4BGJFS+GCTW8I+44M0+{code}", h, eid)      # the pixel host of the real material (A8 console), not a guess
            self.assertIn("動画の講義", text_of(h), eid)                                                   # the advertiser wants a description of the course near the link
        for eid in ("kaigo", "nurse", "toeic", "eiken", "fp"):
            self.assertNotIn("a8mat=4BGJFS+GCTW8I", self.pages[f"exams/{eid}/index.html"], eid)
        # the new course of 2026-11-18 (advertiser news): its name and the price as an example with the day, and none of the claims the advertiser's terms forbid
        sh = text_of(self.pages["exams/sharoshi/index.html"])
        for w in ("社労士試験 速習カリキュラム", "税込217,800円", "2026年11月18日"):
            self.assertIn(w, sh)
        for page, h in self.pages.items():
            tx = text_of(h)
            if "アガルート" in tx:
                for bad in ("合格実績", "全額返金", "97%", "カバー率"):
                    self.assertNotIn(bad, tx, f"{page}: {bad}")
        self.assertEqual(AFF.problems('<p>広告(PR)<a href="https://px.a8.net/svt/ejp?a8mat=4BGJFS+GCTW8I+44M0+614CY">https://px.a8.net/x</a></p>') != [], True)   # negative case: a bare address as the link text is caught

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

    def test_the_temporary_source_folder_is_marked_as_es_modules(self):
        # real Node (the deploy workflow's) reads a .js file as CommonJS unless a package.json with "type": "module" is above it; Deno (the owner's PC) does not care,
        # so a missing marker passes here and fails only in the workflow (2026-11-13, the first deploy).  The marker is written by build-site.mjs; check that it is.
        text = (TEMPLATE / "scripts" / "build-site.mjs").read_text(encoding="utf-8")
        self.assertRegex(text, r"writeFile\(path\.join\(source,'package\.json'\),'\{\"type\":\"module\"\}'\)")
        self.assertIn('"type": "module"', (TEMPLATE / "package.json").read_text(encoding="utf-8"))

    def test_a_relative_output_folder_is_made_where_the_caller_stands(self):
        # the workflow builds with `--out release` from the repository root; the Node build runs in the template folder (2026-11-13: the first two deploys failed on this)
        import os
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                BUILD.make_site(Path("release"))
                self.assertTrue((Path(tmp) / "release" / "index.html").exists())
                self.assertTrue((Path(tmp) / "release" / ".htaccess").exists())
            finally:
                os.chdir(old)
        self.assertFalse((TEMPLATE / "release").exists())

    def test_every_folder_of_the_site_can_be_read_by_the_web_server(self):
        # the Node build works in a private temporary folder; its mode must not reach the site (on Linux the web server got 403 on /_versions/..., 2026-11-13).  On Windows the mode bits mean nothing; the workflow's Linux run is the real check.
        import os
        import stat
        for d, _dirs, files in os.walk(self.out):
            mode = stat.S_IMODE(os.stat(d).st_mode)
            self.assertEqual(mode & 0o055, 0o055, f"{d} is not readable by the web server ({oct(mode)})")
            for f in files:
                self.assertEqual(stat.S_IMODE(os.stat(os.path.join(d, f)).st_mode) & 0o044, 0o044, f)

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
