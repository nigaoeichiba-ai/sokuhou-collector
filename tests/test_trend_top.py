"""trend-sokuho.com: the home page, the category pages, the cards and the head of every page (sites/trend/hooks.py).  The desk's fixed wording must be on the page word for word."""
from __future__ import annotations

import io
import json
import re
import unittest
from pathlib import Path

from PIL import Image

from sokuhou import newsite
from sokuhou.newsite import site_hooks

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
hooks = site_hooks(SITE)
BASE = "https://trend-sokuho.com"

TITLE = "今日の話題｜速報×深掘り"
H1 = "速報ニュースを、どこよりも深掘りする。"
LEAD = "「今日の話題」は、ニュースの見出しや表面的な情報だけで終わりません。速報性と深い洞察を1セットにし、出来事の背景と移り変わり、数字の裏にある意味、暮らしや実務への影響、そして「次に何をすればよいか」までを、一次情報の読み直しとともに1本にまとめてお届けします。"
DESC = LEAD      # the description follows the new lead (the desk, 2026-11-10)
HERO_SENTENCE = "見出しの先にある背景と数字を一次情報から読み解き、今日これから何をすればいいかまで示すサイトです。"      # Muse's final text 2026-11-11
FOOTER = "「今日の話題」は、気になる速報ニュースをどこよりも深く、多角的に読み解くメディアです。"
CAT_DESC = {"kakei": "コメや野菜の価格、給与、セールの動きなど、家計に関わる数字の記事です。省庁や公的機関の発表をもとに、店頭で使える比べ方まで紹介します。",
            "bousai": "台風や火災予防、防災グッズの備えなど、身を守るための記事です。気象庁や消防庁、防災庁の発表をもとに、家でやることまで紹介します。",
            "tenki": "インフルエンザや胃腸炎の流行、加湿器の手入れなど、季節と健康に関わる記事です。公的機関の報告の数字と、家庭での予防を紹介します。",
            "kurashi": "年賀はがきや電話勧誘への対応など、暮らしの手続きと困りごとの記事です。公的機関の案内をもとに、手順まで紹介します。"}
CAT_NAME = {"kakei": "家計・値上げ", "bousai": "防災・気象", "tenki": "天気・季節", "kurashi": "暮らし"}


def _prepared() -> list[dict]:
    cfg, spec, content = newsite.load_site(SITE)
    return hooks.prepare(cfg, spec, content, SITE)


def _lds(h: str) -> list[dict]:
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]


class TrendTop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages, cls.report = newsite.build_pages(SITE)
        cls.articles = [p for p in _prepared() if p.get("category")]

    def html(self, path: str) -> str:
        return self.pages["index.html" if path == "/" else path.strip("/") + "/index.html"]

    def test_the_home_page_has_the_desks_wording_word_for_word(self):
        h = self.html("/")
        self.assertIn(f"<title>{TITLE}</title>", h)
        self.assertIn(f"<h1>{H1}</h1>", h)
        self.assertIn(f'<p class="answer">{HERO_SENTENCE}</p>', h)       # the hero sentence replaced the old lead (Muse's final text 2026-11-11); the old lead stays as the meta description
        self.assertIn(f'<meta name="description" content="{DESC}">', h)
        self.assertIn(FOOTER, h[h.index("<footer"):])
        self.assertEqual(h.count("<h1"), 1)
        self.assertLess(h.index('class="hero"'), h.index("<h1>"))
        self.assertRegex(h, r'<img src="/assets/img/hero-kv\.webp" width="2384" height="1008" alt="黄色のサンバースト[^"]+" fetchpriority="high">')   # the LCP picture: size set, not lazy
        self.assertIn('<link rel="preload" as="image" href="/assets/img/hero-kv.webp"', h)
        self.assertIn("hero-kv.webp", " ".join(k for k in self.pages))

    def test_the_four_category_pages_have_the_desks_title_and_description(self):
        for slug, desc in CAT_DESC.items():
            h = self.html(f"/cat/{slug}/")
            self.assertIn(f"<title>{CAT_NAME[slug]}の記事一覧｜今日の話題</title>", h)
            self.assertIn(f'<meta name="description" content="{desc}">', h)
            self.assertIn(f'<link rel="canonical" href="{BASE}/cat/{slug}/">', h)

    def test_every_page_has_canonical_ogp_and_a_large_twitter_card(self):
        for rel, h in self.pages.items():
            if not (rel.endswith("index.html") and isinstance(h, str)):
                continue
            url = BASE + ("/" if rel == "index.html" else "/" + rel[: -len("index.html")])
            self.assertIn(f'<link rel="canonical" href="{url}">', h, rel)
            for tag in ('property="og:title"', 'property="og:description"', 'property="og:type"', f'property="og:url" content="{url}"', 'property="og:image"', 'name="twitter:image"'):
                self.assertIn(tag, h, f"{rel}: {tag}")
            self.assertIn('name="twitter:card" content="summary_large_image"', h, rel)

    def test_the_ogp_picture_is_the_articles_own_eyecatch_and_the_default_is_the_logo_on_white(self):
        for p in self.articles:
            h = self.html(p["path"])
            self.assertIn('property="og:type" content="article"', h)
            self.assertIn(f'property="og:image" content="{BASE}{p["_img"]}"', h, p["path"])
        for path in ("/", "/cat/bousai/"):
            self.assertIn(f'property="og:image" content="{BASE}/assets/og-default.png"', self.html(path))
        im = Image.open(io.BytesIO(self.pages["assets/og-default.png"]))
        self.assertEqual(im.size, (1200, 630))
        self.assertEqual(im.convert("RGB").getpixel((5, 5)), (255, 255, 255))

    def test_structured_data_matches_what_the_page_shows(self):
        home = {d["@type"]: d for d in _lds(self.html("/"))}
        self.assertEqual(set(home), {"WebSite", "Organization"})
        self.assertEqual(home["Organization"]["name"], "今日の話題")          # the site's name, as the Article's author: the company's name stays on /about/ only
        for p in self.articles:
            d = {x["@type"]: x for x in _lds(self.html(p["path"]))}
            art = d["Article"]
            self.assertEqual(art["headline"], p["h1"])
            self.assertEqual(art["datePublished"], p["published"])
            self.assertTrue(art["image"][0].startswith(BASE + "/assets/img/"))
            self.assertEqual(art["author"], art["publisher"])
            names = [i["name"] for i in d["BreadcrumbList"]["itemListElement"]]
            self.assertEqual(names[:2], ["トップ", p["category"]], p["path"])           # the category is the second step
        for slug in CAT_DESC:
            crumbs = [d for d in _lds(self.html(f"/cat/{slug}/")) if d["@type"] == "BreadcrumbList"][0]
            self.assertEqual([i["name"] for i in crumbs["itemListElement"]], ["トップ", CAT_NAME[slug]])

    def test_the_latest_articles_are_the_13_cards_in_the_desks_order_with_the_desks_leads(self):
        """2026-11-11 revision: the "最新の深掘り記事" list is the desk's fixed 13 (order and one-line leads in home.json "latest_leads"), not the newest-first rule of 11-10."""
        main = self.html("/")
        sec = main[main.index("最新の深掘り記事</h2>"):main.index("<h2>カテゴリ</h2>")]
        cards = re.findall(r'<article class="card">.*?</article>', sec, re.S)
        self.assertEqual(len(cards), 13)
        leads = json.loads((SITE / "content" / "home.json").read_text(encoding="utf-8"))["latest_leads"]
        by = {p["path"]: p for p in self.articles}
        for c, (path, lead) in zip(cards, leads.items()):
            self.assertIn(f'<h3><a href="{path}">{by[path]["h1"]}</a></h3>', c)
            self.assertIn(f'<p class="card-sum">{lead}</p>', c)
        self.assertEqual(len(leads), 13)
        titles = [by[p]["h1"] for p in leads]
        for new in ("給与は名目4.6％増、実質は2.2％増。数字の差が家計の実感です", "インフルエンザは定点10.26人", "加湿器は手入れのしやすい機種を選ぶ", "年賀はがきは1枚85円", "防災用ライトの選び方",
                    "たまねぎは平年の55％、レタスは122％。品目ごとに野菜の献立を組む週"):
            self.assertIn(new, titles)
            self.assertIn(f"<title>{new} | 今日の話題</title>", self.html(next(p for p in leads if by[p]["h1"] == new)))     # title tag, h1 and the card text agree

    def test_the_new_top_sections_are_in_the_desks_order_and_the_panel_has_8_items(self):
        h = self.html("/")
        heads = [x for x in re.findall(r"<h2>(.*?)</h2>", h)]
        want = ["いまの速報", "今日やること", "『今日の話題 速報×深掘り』3つの約束", "最新の深掘り記事", "カテゴリ", "防災特集／ご自宅の備蓄・備えを8項目でチェック", "取材・執筆基準"]
        self.assertEqual(heads, want)
        self.assertEqual(h.count('class="bt-btn"'), 8)
        self.assertIn('<b id="bt-n">5</b> / 8 項目', h)
        self.assertIn("最低限そろっている", h)
        for lab in ("しっかりそろっている", "あと少しで一通りそろう", "半分ほど。まず水と食料から", "まず水と食料から始めよう"):
            self.assertIn(lab, h)
        self.assertIn("台風32号（チャンパカ）／非常に強い・955hPa／危険度は5段階で表示（見本）｜11月10日16時現在", h)
        self.assertNotIn("株式会社MACS", h)

    def test_a_card_has_one_link_a_picture_with_size_and_the_title_as_alt(self):
        for path in ("/", "/cat/kakei/"):
            cards = re.findall(r'<article class="card[^"]*">.*?</article>', self.html(path), re.S)
            self.assertTrue(cards)
            for c in cards:
                self.assertEqual(len(re.findall(r'<a href="/(?:trend-|bousai)', c)), 1, "the title is the only link to the article")
                self.assertRegex(c, r'<img src="/assets/img/card/[^"]+\.webp" width="640" height="427" alt="[^"]{8,}"')
                self.assertRegex(c, r'<time datetime="\d{4}-\d{2}-\d{2}">\d+年\d+月\d+日</time>')
                self.assertRegex(c, r'class="card-cat" href="/cat/[a-z]+/"')
            if path != "/":
                self.assertNotIn('loading="lazy"', cards[0])
                self.assertTrue(all('loading="lazy"' in c for c in cards[1:]))
            else:
                self.assertTrue(all('loading="lazy"' in c for c in cards), "the home page's LCP picture is the hero, so every card below is lazy")
        for rel, body in self.pages.items():
            if rel.startswith("assets/img/card/"):
                self.assertGreater(len(body), 1000)

    def test_one_link_per_article_on_the_home_page_and_one_to_the_bousai_parent(self):
        h = self.html("/")
        main = h[h.index("<main"):h.index("</main>")]
        self.assertEqual(main.count('href="/bousai/"'), 4)      # the panel: three items without an own page (radio, rain gear, first aid) and the link under it
        for p in self.articles:
            if p["path"].startswith("/trend-"):
                self.assertLessEqual(main.count(f'href="{p["path"]}"'), 5, p["path"])         # the card, and the desk's flash / to-do / promise links (2026-11-11)
        self.assertNotIn("速報×深掘りの各ページ", main)

    def test_the_description_of_an_article_is_the_first_two_sentences_of_the_three_line_summary(self):
        for p in self.articles:
            sec = next((s for s in p["sections"] if s.get("h2") == "3行まとめ"), None)
            if sec is None:
                continue      # the desk's full-text rewrite (2026-11-10, the fire-alarm article) has no 3-line summary: its description is the first sentence of the body
            text = "".join(sec["paras"])
            two = "".join(re.findall(r"[^。]+。", text)[:2])
            self.assertIn(f'<meta name="description" content="{two}">', self.html(p["path"]), p["path"])
            self.assertIn(f'<meta property="og:description" content="{two}">', self.html(p["path"]), p["path"])

    def test_the_category_pages_open_with_the_desks_three_sentences(self):
        intro = json.loads((SITE / "site.json").read_text(encoding="utf-8"))["category_intro"]
        self.assertEqual(set(intro), set(CAT_DESC))
        for slug, sentences in intro.items():
            self.assertEqual(len(sentences), 4 if slug in ("kakei", "tenki", "kurashi") else 3)      # the desk's three sentences, and for the three short categories the extra paragraph (2026-11-09)
            body = self.html(f"/cat/{slug}/")
            for sent in sentences:
                self.assertIn(sent, body)
            self.assertLess(body.index(sentences[0]), body.index('class="cards"'))

    def test_an_article_shows_the_dates_near_the_title_and_keeps_the_last_updated_line(self):
        for p in self.articles:
            h = self.html(p["path"])
            self.assertRegex(h, r'<p class="dates">公開日 \d+年\d+月\d+日( / 更新日 \d+年\d+月\d+日)?</p>')
            self.assertIn("最終更新日:", h)
            self.assertLess(h.index('class="dates"'), h.index("<h2>"), p["path"])

    def test_the_breadcrumb_goes_through_the_category_page(self):
        for p in self.articles:
            crumbs = re.search(r'<nav class="crumbs".*?</nav>', self.html(p["path"]), re.S).group(0)
            self.assertIn('<a href="/cat/', crumbs, p["path"])

    def test_the_category_pages_are_in_the_navigation_and_the_footer_and_linked_from_the_home_page(self):
        h = self.html("/")
        for slug in CAT_DESC:
            self.assertGreaterEqual(h.count(f'href="/cat/{slug}/"'), 3, slug)       # header, the category list, the footer
        self.assertIn("カテゴリ</h2>", h)

    def test_a_category_page_without_enough_text_is_noindex_and_stays_out_of_the_sitemap(self):
        sm = self.pages["sitemap.xml"]
        for slug in CAT_DESC:
            noindex = bool(re.search(r'<meta name="robots" content="[^"]*noindex', self.html(f"/cat/{slug}/")))
            self.assertEqual(f"{BASE}/cat/{slug}/" in sm, not noindex, slug)

    def test_an_unknown_category_stops_the_build(self):
        cfg, spec, content = newsite.load_site(SITE)
        bad = json.loads(json.dumps(content))
        next(p for p in bad if p["path"] == "/trend-typhoon32/")["category"] = "でたらめ"
        with self.assertRaises(SystemExit):
            hooks.prepare(cfg, spec, bad, SITE)

    def test_depth_bar_a_new_thin_article_stops_the_build_a_bridge_page_and_an_old_one_do_not(self):
        """Desk's rule 2026-11-09: a NEW article needs 2,000 readable characters and its own table or chart.  A page declared a bridge (`noindex`) and the articles
        published before the bar (DEEP_GRANDFATHERED: no character count required of them) pass.  The failure it reproduces: a thin article going out as a normal one."""
        content = _prepared()                                                              # the pages as the build hands them to post(): category and dates set
        base = next(p for p in content if p["path"] == "/trend-typhoon32/")
        thin_html = "<main><h1>薄い</h1><p>" + "短い文です。" * 20 + "</p></main>"

        def new_page(**extra):
            p = json.loads(json.dumps(base))
            p.update({"path": "/trend-test-thin/", **extra})
            return p, {"trend-test-thin/index.html": thin_html}

        p, pages = new_page()
        problems = hooks.deep_problems(pages, [p])
        self.assertTrue(any("readable characters" in x for x in problems), problems)
        self.assertTrue(any("no table and no chart" in x for x in problems), problems)
        p, pages = new_page(noindex=True)
        self.assertEqual(hooks.deep_problems(pages, [p]), [])                              # declared as a bridge: allowed
        self.assertEqual(hooks.deep_problems({"trend-typhoon32/index.html": thin_html}, [base]), [])      # an old article: no character count required
        self.assertIn(base["path"], hooks.DEEP_GRANDFATHERED)
        self.assertEqual(hooks.DEEP_MIN_CHARS, 2000)
        # every article now on the site is either deep or on the list, so the build passes
        self.assertEqual(hooks.deep_problems(self.pages, [x for x in content if x["path"] not in hooks.DEEP_GRANDFATHERED]), [])

    def test_the_old_all_pages_list_and_the_stale_medical_line_are_gone(self):
        self.assertNotIn("医療の話題は扱いません", self.html("/"))
        self.assertNotIn("速報×深掘りの各ページ", self.html("/"))
        self.assertIn("健康・医療の話題は、具体的な薬名と効能の断定を書かず", self.pages["about/index.html"])


if __name__ == "__main__":
    unittest.main()
