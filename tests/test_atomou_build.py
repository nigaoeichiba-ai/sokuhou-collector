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
CFG = {k: v for k, v in json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8")).items() if k != "google_client_id"}  # the Google hand-over is tested with and without an id below


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

    def test_card_titles_may_break_inside_long_english_names(self):
        # 2026-10-08: "SoftBank/Y!mobile/LINEMO" could not wrap and pushed a card 18px past a 300px screen (layoutcheck [overflow] on /c/sale/)
        css = self.rel["assets/style.css"]
        m = re.search(r"\.c-title[^{]*\{[^}]*overflow-wrap:anywhere", css)
        self.assertIsNotNone(m, "the card title needs overflow-wrap:anywhere")

    def test_every_button_and_chip_is_at_least_44px_tall(self):
        # 2026-10-08 Codex skin review: card buttons were 40px and chips 38-42px; 44px is the smallest comfortable touch target
        css = self.rel["assets/style.css"] + self.rel["assets/design.css"]
        short = [m.group(0) for m in re.finditer(r"[^{}]*\.(?:btn|chip|mini|sbtn)[^{}]*\{[^}]*min-height:(\d+)px", css) if int(m.group(1)) < 44]
        self.assertEqual(short, [])

    def test_breadcrumb_links_are_touch_targets(self):
        # 2026-10-09 device test (iPhone/Pixel emulation): the "トップ" link of every page was 30x19px
        css = self.rel["assets/style.css"]
        m = re.search(r"\.crumbs a\{[^}]*min-height:(\d+)px", css)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 44)

    def test_the_guide_sits_in_the_header_on_phones_and_floats_only_where_there_is_no_room(self):
        # 2026-10-09 device test: the floating button covered calendar days and card buttons on every phone
        css, js = self.rel["assets/style.css"], self.rel["assets/guide.js"] if "assets/guide.js" in self.rel else "".join(v for k, v in self.rel.items() if k.endswith(".js"))
        self.assertIn("guide-icon", js)
        self.assertIn(".hicons", js)
        self.assertRegex(css, r"@media \(max-width:699px\)\{[^@]*\.guide-btn\{display:none\}")
        self.assertRegex(css, r"@media \(max-width:359px\)\{\.guide-icon\{display:none\}\.guide-btn\{display:inline-block")   # 300px: no room for a 4th header icon (layoutcheck overflow)

    def test_every_page_has_a_share_picture_and_the_picture_exists(self):
        # 2026-10-09 review: the share card was the small "summary" one without a picture
        for path in ("index.html", "add/index.html", "use/index.html"):
            self.assertIn('og:image" content="https://atomou.com/assets/og.png"', self.rel[path])
            self.assertIn('twitter:card" content="summary_large_image"', self.rel[path])
        og = Path(build.HERE / "assets" / "og.png")
        self.assertTrue(og.exists())
        self.assertTrue(og.read_bytes().startswith(bytes([0x89]) + b"PNG"))

    def test_event_pages_lead_on_to_the_days_around_them(self):
        # 2026-10-09 review: a detail page was a dead end
        pages = [h for k, h in self.rel.items() if k.startswith("e/") and k.endswith("index.html")]
        with_near = [h for h in pages if "同じ頃の日" in h]
        self.assertGreater(len(with_near), len(pages) * 0.8)
        self.assertTrue(all("同じ頃の日" not in h or "この日の前後10日にある日です。" in h for h in pages))
        quiet = [h for h in pages if 'class="notice quiet"' in h]
        self.assertTrue(all("同じ頃の日" not in h for h in quiet))     # a quiet day leads nowhere else

    def test_sample_cards_in_a_narrow_box_are_single_column(self):
        # 2026-10-09 CI layoutcheck failure: at 720px+ the card grid has two columns, so a 360px box gave a 176px card and a 36px title column
        # (49px with the fonts of this machine, 36px with the fonts of CI). A box narrower than a card grid must not be a grid of two.
        manual = self.rel["manual/index.html"]
        boxes = re.findall(r'<div class="cards" style="([^"]*)">', manual)
        self.assertGreaterEqual(len(boxes), 2)
        for style in boxes:
            self.assertIn("grid-template-columns:1fr", style)

    def test_release_and_preview_differ_only_in_indexing(self):
        self.assertIn("Allow: /", self.rel["robots.txt"])
        self.assertIn("Disallow: /", self.prev["robots.txt"])
        self.assertNotIn("noindex", self.rel["index.html"])
        self.assertIn("noindex", self.prev["index.html"])

    def test_a_demo_build_asks_for_a_password_and_a_release_build_does_not(self):
        self.assertIn("AuthType Basic", self.prev[".htaccess"])
        self.assertIn("Require valid-user", self.prev[".htaccess"])
        self.assertIn(build.HTPASSWD_PLACEHOLDER, self.prev[".htaccess"])  # the deploy job fills in the path of the password file
        self.assertNotIn("AuthType", self.rel[".htaccess"])
        self.assertIn("Ngx_Cache_NoCacheMode=on", self.prev[".htaccess"])  # Xserver's server cache would answer without asking for the password
        self.assertNotIn("AllCacheMode", self.prev[".htaccess"])
        self.assertIn("AllCacheMode", self.rel[".htaccess"])  # the public site keeps the cache
        self.assertIn("RewriteRule", self.prev[".htaccess"])  # the https redirect stays in both

    def test_the_workflow_never_deploys_the_demo_unprotected(self):
        wf = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn('[ "$SITE" = "atomou" ] && [ "$ATOMOU_PUBLIC" != "true" ] && { [ -z "$DEMO_USER" ] || [ -z "$DEMO_PASS" ]; }', wf)   # also with the review copy: the demo that rides along in public_html/demo needs its password
        self.assertIn("grep -q \"AuthUserFile $home/$SITE_DIR/.htpasswd\" \"$f\"", wf)  # the build is checked to name the real password file before upload
        self.assertIn("[ \"$unauth\" = \"401\" ] || ok=0", wf)  # and the live demo must refuse a visitor without the password

    def test_calendar_and_plan_pages_and_the_guide_scripts(self):
        self.assertIn('data-page="calendar"', self.rel["calendar/index.html"])
        self.assertIn("/calendar/", self.rel["sitemap.xml"])
        self.assertIn("noindex", self.rel["plan/index.html"])
        self.assertNotIn("/plan/", self.rel["sitemap.xml"])
        for k in ("index.html", "calendar/index.html", "plan/index.html"):
            self.assertEqual(len(re.findall(r'<script src="/assets/[^"]+" defer>', self.rel[k])), 1, f"{k}: one script bundle")
            self.assertIn("/assets/atomou.js?v=", self.rel[k])
        bundle = self.rel["assets/atomou.js"]
        for marker in ("window.AtomouCore", "window.AtomouICS", "window.AtomouApp", "window.AtomouPlan", "window.AtomouQuick", "window.AtomouGuide"):
            self.assertIn(marker, bundle)
        self.assertNotIn("skins.css", self.rel["index.html"].split("window.ATOMOU=")[0])  # the other skins are fetched only when one is chosen

    def test_cards_are_short_no_source_line_and_two_buttons(self):
        e = next(x for x in self.entries if not x["quiet"])
        card = build.card_html(e)
        self.assertNotIn("出典", card)
        self.assertNotIn("確認日", card)
        self.assertIn("☆ 予定に入れる", card)
        self.assertIn(">詳細</a>", card)
        self.assertNotIn("カレンダーに入れる", card)
        page = self.rel[f"e/{e['id']}/index.html"]
        self.assertIn("出典", page)  # the source and the check date live on the detail page
        self.assertIn("確認日", page)
        self.assertIn("メモ・やることを追加", page)

    def test_home_has_the_todays_list_block_first(self):
        h = self.rel["index.html"]
        self.assertLess(h.index('id="todo"'), h.index('data-block="search"'))
        self.assertIn('id="grid" data-save-order="1"', h)

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
        allowed = {"id", "title", "date", "date_end", "precision", "weekday", "kind", "category", "group", "region", "tags", "quiet", "ad_ok", "son_toku", "source_url", "checked_on", "status", "subject", "what", "place"}
        for e in data:
            self.assertLessEqual(set(e), allowed)

    def test_skins_css_has_every_skin(self):
        css = self.rel["assets/skins.css"]
        for s in skins.SKINS:
            self.assertIn(f'[data-skin="{s["id"]}"]', css)
        self.assertNotIn("http", css)  # no external fonts or images

    def test_every_page_loads_only_its_own_scripts_and_the_ad_code_only_where_ads_may_be(self):
        by_id = {e["id"]: e for e in self.entries}
        pub = CFG["adsense_pub_id"].replace("ca-", "")
        self.assertIn(f"google.com, {pub}, DIRECT", self.rel["ads.txt"])
        seen = set()
        for k, v in self.rel.items():
            if k.endswith(".html") and isinstance(v, str):
                has = "adsbygoogle" in v
                kind = re.search(r'<body data-page="([^"]+)"', v)
                kind = kind.group(1) if kind else ""
                m = re.fullmatch(r"e/([^/]+)/index.html", k)
                if m:
                    e = by_id[m.group(1)]
                    self.assertEqual(has, not e["quiet"] and e.get("ad_ok", True), k)   # a quiet day or an item with ad_ok false never carries it
                elif kind:
                    self.assertEqual(has, kind in build.ADS_KINDS, k)     # the app's pages (record, calendar, my page, plan, search, skins) never do
                seen.add(has)
                for src in re.findall(r'<script[^>]+src="([^"]+)"', v):
                    self.assertTrue(src.startswith("/assets/") or src.startswith("https://pagead2.googlesyndication.com/"), f"{k}: {src}")
        self.assertEqual(seen, {True, False})
        self.assertNotIn("googletagmanager", self.rel["index.html"])  # no analytics (the privacy policy says so)

    def test_quiet_entries_never_get_related_items_or_ads(self):
        quiet = [e for e in self.entries if e["quiet"]]
        for e in quiet[:10]:
            page = self.rel[f"e/{e['id']}/index.html"]
            self.assertIn("この日は、静かにお知らせします", page)
            self.assertNotIn("同じジャンルの日", page)
            self.assertIn('class="card quiet', page)

    def test_a_first_visitor_gets_an_introduction_not_a_tour_over_the_page(self):
        home = self.rel["index.html"]
        self.assertIn('<section class="intro" id="intro"', home)
        self.assertIn(" hidden>", home.split('id="intro"', 1)[1].split(">", 1)[0] + " hidden>")   # shown by the script to a first-time visitor only
        for need in ("はじめての方へ", 'data-intro="start"', 'data-intro="close"', "いつでも見直せます"):
            self.assertIn(need, home)
        guide = (build.SITE["assets"] / "guide.js").read_text(encoding="utf-8")
        self.assertNotIn("setTimeout(start, 1200)", guide)       # the old behaviour: the spotlight tour started 1.2 s after the page opened
        self.assertIn("function offer()", guide)
        self.assertIn("/?guide=1", guide)                          # pages without a tour of their own send the "ガイドを見る" button to the home tour
        self.assertIn('id="guide"', self.rel["manual/index.html"])
        self.assertIn('href="/manual/#guide">使い方</a>', home)    # the footer link: where to look again
        my = self.rel["my/index.html"]
        self.assertIn('href="/?intro=1"', my)                      # the my page: the introduction and the guide again
        self.assertIn('data-guide="start"', my)

    def test_the_source_and_check_date_are_also_shown_right_under_the_card(self):
        e = self.entries[0]
        page = self.rel[f"e/{e['id']}/index.html"]
        line = re.search(r'<p class="small muted src-line">(.*?)</p>', page)
        self.assertIsNotNone(line)
        self.assertIn(e["checked_on"], line.group(1))
        self.assertIn('href="#src"', line.group(1))
        self.assertIn('<h2 id="src">', page)
        self.assertLess(page.index("src-line"), page.index("<h2 id=\"src\">"))     # the proof sits above the long text, not only below it

    def test_use_case_pages_do_not_say_notices_are_missing(self):
        for k, v in self.rel.items():
            if k.startswith("use/") and isinstance(v, str):
                self.assertNotIn("通知はまだありません", v, k)      # push and mail notices exist (optional)

    def test_a_set_of_days_can_be_saved_in_one_tap(self):
        pages = [v for kk, v in self.rel.items() if kk.startswith("e/") and isinstance(v, str) and "data-saveall" in v]
        self.assertTrue(pages)
        for v in pages:
            ids = re.search(r'data-saveall="([^"]+)"', v).group(1).split(",")
            self.assertTrue(all(re.fullmatch(r"[0-9a-f]{10}", i) for i in ids))
            self.assertIn(f"この日を含む{len(ids)}件をまとめて予定に入れる", v)
        quiet = [v for kk, v in self.rel.items() if kk.startswith("e/") and isinstance(v, str) and "この日は、静かにお知らせします" in v]
        self.assertTrue(all("data-saveall" not in v for v in quiet))     # a quiet day leads nowhere else

    def test_the_home_page_puts_the_visitors_own_days_before_the_search(self):
        home = self.rel["index.html"]
        self.assertLess(home.index('data-block="todo"'), home.index('data-block="mine"'))
        self.assertLess(home.index('data-block="mine"'), home.index('data-block="search"'))
        self.assertIn("<h2>よく使われる</h2>", self.rel["use/index.html"])

    def test_text_that_other_code_looks_for_still_matches(self):
        # a wording pass once changed strings that are search patterns: the privacy page's member sentence and the contact form's option (both live in shared parts)
        privacy = self.rel["privacy/index.html"]
        self.assertNotIn("会員登録などの機能を持ちません", privacy)         # the member site replaces it (the shared text says there is no sign-up)
        app = (build.SITE["assets"] / "app.js").read_text(encoding="utf-8")
        key = re.search(r"o\.value\.indexOf\('([^']+)'\) === 0", app).group(1)
        self.assertIn(f">{key}", self.rel["contact/index.html"])             # the "send it as a day I would like to see" option the search page links to

    def test_event_pages_have_share_and_google_calendar_links_and_quiet_ones_do_not(self):
        shared = 0
        for k, v in self.rel.items():
            if not (k.startswith("e/") and isinstance(v, str)):
                continue
            if 'class="share"' in v:
                shared += 1
                self.assertIn("line.me/R/msg/text/", v, k)
                self.assertIn("twitter.com/intent/tweet", v, k)
                self.assertNotIn("あなたの予定", v.split('class="share"')[1].split("</section>")[0].replace("あなたの予定は入りません", ""), k)
            if 'class="share"' in v:      # a day with a date can go to Google Calendar; "2027年1月ごろ" cannot
                self.assertEqual("calendar.google.com/calendar/render" in v, 'class="share" aria-label="人に送る" data-title' in v and 'data-p="day"' in v.split('class="share"')[1].split(">")[0], k)
        self.assertGreater(shared, 250)
        quiet = [e for e in self.entries if e["quiet"]]
        for e in quiet:
            self.assertNotIn('class="share"', self.rel[f"e/{e['id']}/index.html"])

    def test_calendar_feeds_hold_whole_public_days_only_and_are_well_formed(self):
        crlf = chr(13) + chr(10)
        feeds_ = {k: v for k, v in self.rel.items() if k.startswith("cal/") and k.endswith(".ics")}
        self.assertIn("cal/all.ics", feeds_)
        self.assertGreaterEqual(len(feeds_), 8)
        quiet_ids = {e["id"] for e in self.entries if e["quiet"]}
        month_ids = {e["id"] for e in self.entries if e["precision"] != "day"}
        for k, v in feeds_.items():
            self.assertTrue(v.startswith("BEGIN:VCALENDAR" + crlf) and v.endswith("END:VCALENDAR" + crlf), k)
            self.assertEqual(v.count("BEGIN:VEVENT"), v.count("END:VEVENT"), k)
            for line in v.split(crlf):
                self.assertLessEqual(len(line.encode("utf-8")), 75, f"{k}: {line[:30]}")
            for i in re.findall(r"UID:([0-9a-f]{10})@", v):
                self.assertNotIn(i, quiet_ids, k)
                self.assertNotIn(i, month_ids, k)
        self.assertIn("calendar.google.com/calendar/r?cid=webcal", self.rel["c/exams/index.html"])
        self.assertIn("DESCRIPTION:詳しい日付と出典: https://", feeds_["cal/all.ics"])

    def test_a_public_day_has_its_own_share_picture_and_a_quiet_one_does_not(self):
        from sites.atomou import ogimage
        if not ogimage.available():
            self.skipTest("no Pillow or Japanese font here (the pages then keep the common picture)")
        e = next(x for x in self.entries if not x["quiet"] and x["status"] != "ended")
        page = self.rel[f"e/{e['id']}/index.html"]
        self.assertIn(f"/og/{e['id']}.png", page)
        png = self.rel[f"og/{e['id']}.png"]
        self.assertTrue(png.startswith(bytes([137]) + b"PNG"))
        for q in (x for x in self.entries if x["quiet"]):
            self.assertNotIn(f"og/{q['id']}.png", self.rel)
            self.assertNotIn("/og/", self.rel[f"e/{q['id']}/index.html"])

    def test_interests_page_is_not_indexed_and_the_home_links_to_it(self):
        page = self.rel["interests/index.html"]
        self.assertIn("noindex", page)
        self.assertIn('href="/interests/"', self.rel["index.html"])
        self.assertNotIn("/interests/", self.rel["sitemap.xml"])
        import json as _j
        tax = _j.loads((build.ROOT / "data/atomou/interests.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(page.count("data-int-sec="), len(tax["sections"]))     # a section per group of the list of fields
        self.assertGreaterEqual(page.count('data-int="'), 200)                         # wide enough for niche tastes
        self.assertIn("準備中", page)                                                  # a field with no day yet can still be chosen
        ids = [i["id"] for s in tax["sections"] for i in s["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        names = [i["name"] for s in tax["sections"] for i in s["items"]]
        self.assertEqual(len(names), len(set(names)))

    def test_the_sentences_composed_for_every_day_read_as_japanese(self):
        # the lead and the questions are put together from the catalog entry; these are the slips a reader noticed (2026-10-09)
        bad = {"a range with 'までに'": r"まで(に)(開催|実施|始まり|行われ|終了)", "a clause as the subject": r"(る|れる|ます)は、20\d\d年", "a clause before の概要": r"(る|れる|ます)の概要",
               "決勝 for a horse race": r"決勝が行われ", "締切 twice": r"締切は、[^。]*が締切です", "改定 twice": r"改定は、[^。]*に改定されます", "場所 for an area": r"場所は(西日本|東日本|九州|東北)", "a month called a day": r"ごろは、「"}
        for k, v in self.rel.items():
            if k.startswith("e/") and isinstance(v, str):
                m = re.search(r'<section class="article".*?</section>', v, re.S)
                text = re.sub(r"<[^>]+>", "", m.group(0)) if m else ""
                for name, pat in bad.items():
                    self.assertIsNone(re.search(pat, text), f"{k}: {name}")

    def test_kind_words_fit_the_day_and_a_one_day_event_is_not_a_period(self):
        # a horse race is "held" (no "final"), an opposition is not a "peak"; the ids still come from the stored kind (2026-10-10)
        by_subject = {(e["subject"], e["kind"]) for e in self.entries}
        self.assertNotIn(("競馬", "決勝"), by_subject)
        self.assertIn(("競馬", "開催"), by_subject)
        self.assertTrue(any("衝" in e["title"] and e["kind"] == "衝" for e in self.entries))
        self.assertEqual(catalog.shown_kind({"kind": "決勝", "subject": "サッカー", "title": "天皇杯 決勝"}), "決勝")
        today = date(2026, 10, 10)
        one_day = {"title": "テスト", "date": "2026-10-10", "date_end": None, "precision": "day", "kind": "改定", "group": "締切・制度", "subject": "税", "place": "", "region": None}
        question, answer = build.articles.faq(one_day, build.fmt_date, today, None)[0]
        self.assertNotIn("期間中", answer)
        self.assertIn("今日", answer)

    def test_the_questions_of_a_subject_guide_do_not_name_one_member_of_the_subject(self):
        # the meteor-shower guide once asked "ふたご座流星群はどんな流星群ですか?" on the pages of other showers
        guides = json.loads((build.ROOT / "data/atomou/guides.json").read_text(encoding="utf-8"))
        for g in guides:
            if g["subject"] == "流星群":
                for q in g["faq"]:
                    self.assertNotRegex(q["q"], r"座流星群は")

    def test_words_the_use_cases_quote_from_the_screens_exist_on_the_screens(self):
        # a wording pass once renamed a heading and a button while the steps still named the old ones
        src = chr(10).join((build.HERE / f).read_text(encoding="utf-8") for f in ("build.py", "assets/app.js", "assets/plan.js", "assets/push.js", "assets/member.js", "assets/quick.js", "assets/guide.js", "skins.py", "articles.py"))
        examples = {"○○の納期", "うちの子の誕生日", "お酒をやめた日", "七五三のお参り", "健診の予約", "免許の期限", "冷蔵庫の保証が切れる日", "勉強をはじめた日", "夏休みのはじまり",
                    "年度末の締め切り", "最後の出勤日", "母の誕生日", "資格の更新", "駅伝・マラソン"}     # names a visitor types, and a catalog tag
        for u in usecases.USECASES:
            for text in [*u.get("steps", []), *u.get("tips", []), *u.get("cautions", []), u.get("situation", "")]:
                for tok in re.findall(r"『([^』]+)』", text):
                    core = tok.replace("☆ ", "").replace("★ ", "")
                    self.assertTrue(core in src or tok in examples, f"{u['slug']}: 『{tok}』 is not on any screen")

    def test_event_pages_state_source_and_check_date(self):
        e = self.entries[0]
        page = self.rel[f"e/{e['id']}/index.html"]
        self.assertIn(e["source_url"].replace("&", "&amp;"), page)
        self.assertIn(e["checked_on"], page)
        self.assertIn("公式ページで、最新の情報をご確認ください", page)

    def test_privacy_policy_says_where_personal_days_live(self):
        p = self.rel["privacy/index.html"]
        self.assertIn("localStorage", p)
        self.assertIn("サーバーには送りません", p)

    def test_manual_is_linked_from_every_page_and_has_the_questions(self):
        for k in ("index.html", "my/index.html", "e/" + self.entries[0]["id"] + "/index.html"):
            self.assertIn('href="/manual/"', self.rel[k], k)
        m = self.rel["manual/index.html"]
        for q in ("料金はかかりますか", "機種変更をしたら", "お知らせは来ますか", "「やること」とは何ですか"):
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
        self.assertGreaterEqual(dom.count('class="card'), 6)  # the first screen is six cards already in the page
        self.assertNotIn('<span class="num"></span>', dom)  # every card got its number
        text = re.sub(r"<[^>]+>", "", html.unescape(dom))
        self.assertIn("2026年10月8日(木)", text)      # today's line, filled by the script from the device's date
        self.assertIn("年末まであと84日", text)
        self.assertIn("年度末まであと174日", text)
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
        for want in ("今日で281日目", "年末まで、あと84日", "2027年まで、あと85日", "2026年度は、あと174日"):
            self.assertIn(want, dom)
        self.assertIn("date=2027-03-31", dom)   # 引っ越しの用意 -> the end of the fiscal year
        self.assertIn("date=2027-04-01", dom)   # 入学の用意 -> the start of the next one
        self.assertNotIn("alarm=", dom)  # the in-app calendar needs no alarm menu

    def test_interests_page_offers_every_subject_and_reads_a_friends_link(self):
        dom = html.unescape(self.dom("/interests/?pick=将棋,剣道"))
        self.assertGreaterEqual(dom.count('data-int="'), 60)
        self.assertRegex(dom, r'id="int-pick"(?![^>]*hidden)')
        self.assertIn("将棋・剣道", re.sub(r"<[^>]+>", "", dom))
        self.assertNotIn('data-int-drop="将棋"', dom)      # offered, never added without a tap

    def test_share_words_carry_todays_count_and_a_link_to_the_day(self):
        dom = html.unescape(self.dom("/e/f2bb25e347/"))
        m = re.search(r'data-share-to="line" href="([^"]+)"', dom)
        self.assertIsNotNone(m)
        from urllib.parse import unquote
        text = unquote(m.group(1))
        self.assertIn("まで、あと54日", text)             # counted from the device's date (2026-10-08), not from the build
        self.assertIn("/e/f2bb25e347/", text)

    def test_home_edit_mode_shows_a_bar_on_every_block(self):
        dom = self.dom("/?edit=1")
        self.assertEqual(dom.count('class="block-bar"'), 8)  # todo, search, cats, daily, mine, interests, soon, usecases
        self.assertNotIn('class="block-bar"', self.dom("/"))

    def test_no_uncaught_script_error_on_any_main_page(self):
        # 2026-10-08: /add/ threw "Cannot read properties of undefined (reading 'quiet')" before a kind was chosen; dump-dom cannot see the console,
        # so core.js writes every uncaught error on <html data-jserr> and this test reads it
        for path in ("/", "/add/", "/calendar/", "/my/", "/search/", "/skins/", "/today/", "/plan/", "/use/", "/add/?quick=1", "/?edit=1"):
            dom = self.dom(path)
            m = re.search(r'<html[^>]*data-jserr="([^"]*)"', dom)
            self.assertIsNone(m, f"{path}: {m.group(1) if m else ''}")

    def test_no_storage_errors_with_a_blank_profile(self):
        # a fresh profile has no atomou.v1: the pages must render (my page shows its empty state)
        dom = self.dom("/my/")
        self.assertRegex(dom, r'id="my-empty"(?![^>]*hidden)')


if __name__ == "__main__":
    unittest.main()
