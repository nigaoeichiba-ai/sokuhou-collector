"""The scaffold of a new site (sokuhou/newsite.py) and the common SEO checks (sokuhou/seokit.py).

A dummy site is made with `init`, filled with full-size synthetic pages (so that the bars of the proposal's 5-0 (8) are really passed) and built like a release:
sitecheck and, where Chrome exists, layoutcheck pass.  Every check also has a negative test that makes the old failure on purpose.
Past failures reproduced: minna's lists that are only a grid of pictures (thin), saichin's one page repeated with another prefecture's name (same text), kuma's small
municipality pages (few numbers), a deep page nobody links to.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import zlib
import unittest
from pathlib import Path

from sokuhou import layoutcheck, newsite, prefectures, seokit, sitecheck, sitekit
from sokuhou.layoutcheck import find_chrome

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://dummy.example"

PHRASES = [
    "{n}は、この十年のうちに{a}から{b}へ動いています。",
    "いちばん大きく動いたのは{y}年で、前の年より{d}ふえました。",
    "全国の平均と比べると、{n}の数字は{c}という位置にあります。",
    "{n}では、{y}年を境に、増え方が{e}になりました。",
    "{n}だけを見ても、{y}年から三年のあいだに{d}の差が出ています。",
    "隣の県と並べたとき、{n}の{a}という数字は、{c}にあたります。",
]


KANJI = "".join(chr(c) for c in range(0x4E00, 0x4E00 + 400))      # synthetic text: every page gets its own run of characters, so only the template repeats


def own_text(seed: int, sentences: int = 5) -> list[str]:
    import random
    r = random.Random(seed)
    return ["".join(r.choice(KANJI) for _ in range(22)) + "です。" for _ in range(sentences)]


def item_page(i: int, short: str, slug: str) -> dict:
    a, b = 1000 + i * 37, 1900 + i * 53
    paras = [PHRASES[(i + k) % len(PHRASES)].format(n=short, a=a, b=b, y=2016 + (i + k) % 9, d=40 + i * 3 + k, c=f"{10 + i + k}番目", e=f"毎年{3 + i}%ずつ") for k in range(2)]
    paras += own_text(100 + i, 16)
    return {"path": f"/pref/{slug}/", "kind": "item", "parent": "/list/", "title": f"{short}の人口あたりの数字(推移)", "h1": f"{short}の人口あたりの数字",
            "primary_kw": f"{short}の人口あたりの数字", "intent": 3, "updated": f"2026-10-{10 + i:02d}", "data_basis": "2026年4月1日現在", "sources": ["main"],
            "description": f"{short}の人口あたりの数字を、十二年分の表で示します。最新の数字は{b}で、四十七都道府県の中の順位と前の年との差も載せています。出典は総務省の公表表で、基準日と取得日も書いています。",
            "answer": f"{short}の最新の数字は{b}で、前の年より{40 + i}ふえました。四十七都道府県の中の順位は{10 + i}番目です。",
            "sections": [{"h2": "推移の表", "paras": paras[:2], "table": {"caption": f"{short}の十二年の推移", "cols": ["年", "数字", "前の年との差", "全国順位"], "num_cols": [0, 1, 2, 3],
                          "rows": [[str(2014 + k), str(a + k * (7 + i)), str(7 + i + k), str(10 + (i + k) % 30)] for k in range(12)]}},
                         {"h2": "読み方", "paras": paras[2:]}],
            "related": [{"path": "/list/", "text": "都道府県別の数字の一覧"}]}


LONG = ("この表は、出典が公表した数字を並べ替えたものです。並べ替えるときに数字そのものは変えていません。{k}という見方をすると、{x}から{y}までの幅に収まります。"
        "年によって調査の範囲が変わるため、{z}より前の数字とそのまま比べるときは注意が要ります。")


def rich_site(root: Path) -> Path:
    d = newsite.init_site("dummysite", "dummy.example", "ダミー統計", "ダ", root, "2026-11-03")
    for f in (d / "content").glob("*.json"):
        f.unlink()
    spec = json.loads((d / "site.json").read_text(encoding="utf-8"))
    spec["sources"] = {"main": {"org": "総務省", "table": "ダミーの調査表", "credit": "総務省『ダミーの調査表』を加工して作成", "url": "https://www.soumu.go.jp/", "basis": "2026年4月1日", "fetched": "2026-11-03"}}
    spec["footer_html"] = "出典: 総務省の公表表。各ページの末尾に基準日と取得日を書いています。"
    spec["purpose"] = "公的な統計を、ページごとに一つの問いへ答える形に整えて載せること。"
    spec["update_text"] = "出典の表が更新されたら、数字を入れ替えて、各ページの最終更新日を書き換えます。"
    spec["disclaimer"] = ["数字は出典の公表時点のものです。手続きの前に、出典の公開ページで最新の内容を確かめてください。"]
    spec["method"] = ["出典の表から数字を読み取り、順位と増減だけを当サイトで計算しています。"]
    (d / "site.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    rows = newsite._example_rows()
    ranked = sorted(rows, key=lambda r: -r[2])
    items = [item_page(i, short, slug) for i, (short, slug, _) in enumerate(ranked[:6])]
    paras = lambda tag, n: ["".join(own_text(zlib.crc32(tag.encode()) % 99999 + n * 100 + j, 8)) for j in range(1, 6)]   # noqa: E731
    pages = {
        "home": {"path": "/", "kind": "hub", "title": "人口あたりの数字とは", "h1": "人口あたりの数字の最新と推移", "primary_kw": "人口あたりの数字", "intent": 1,
                 "updated": "2026-11-03", "sources": ["main"], "description": "人口あたりの数字の最新値と、四十七都道府県の順位、十二年の推移をまとめています。数字は総務省の公表表から読み取り、更新日を各ページに書いています。出典のページも載せました。",
                 "answer": "人口あたりの数字は、いちばん高い県で5,000前後、低い県で1,000前後です。順位は一覧で確かめられます。",
                 "sections": [{"h2": "地図で見る", "paras": paras("全国", 1)[:3], "tilemap": {"title": "都道府県別の数字", "values": {s: v for _, s, v in rows}, "href_prefix": "/pref/"}},
                              {"h2": "上位の県", "paras": paras("上位", 2)[:2], "chart": {"kind": "bar", "title": "上位8県", "desc": "数字の高い順に8県を並べた棒グラフです。",
                                                                                  "labels": [r[0] for r in ranked[:8]], "values": [r[2] for r in ranked[:8]]}}],
                 "related": [{"path": "/guide/", "text": "人口あたりの数字の見方と計算のしかた"}]},
        "list": {"path": "/list/", "kind": "list", "parent": "/", "title": "人口あたりの数字 都道府県別の一覧", "h1": "人口あたりの数字 都道府県別の一覧", "primary_kw": "人口あたりの数字 都道府県別", "intent": 2,
                 "updated": "2026-11-03", "sources": ["main"], "description": "人口あたりの数字を、四十七都道府県で高い順に並べた表です。最新の値と順位を一覧にし、上位の県は個別のページで十二年の推移を見られます。表はCSVでも配っています。",
                 "answer": f"いちばん高いのは{ranked[0][0]}で{ranked[0][2]}です。四十七都道府県を高い順に並べた表と、地図を載せています。",
                 "dataset": {"csv": "data/list.csv", "table_section": 1, "license": "https://www.e-stat.go.jp/terms-of-use"},
                 "sections": [{"h2": "分かること", "paras": paras("一覧", 3)},
                              {"h2": "高い順の表", "table": {"caption": "都道府県別の数字(高い順)", "cols": ["順位", "都道府県", "数字"], "num_cols": [0, 2],
                                                            "rows": [[str(i + 1), {"text": s, "href": f"/pref/{sl}/"} if i < 6 else s, str(v)] for i, (s, sl, v) in enumerate(ranked)]}}]},
        "guide": {"path": "/guide/", "kind": "analysis", "parent": "/", "title": "人口あたりの数字の見方と計算", "h1": "人口あたりの数字の見方と計算のしかた", "primary_kw": "人口あたりの数字の見方", "intent": 4,
                  "updated": "2026-11-01", "sources": ["main"], "description": "人口あたりの数字が何を表すか、どう計算するか、年をまたいで比べるときに何に気をつけるかを、例の数字を使って説明します。数字は総務省の公表表から読み取った値です。",
                  "answer": "この数字は、総数を人口で割って一万人あたりにそろえたものです。県の大きさがちがっても比べられます。",
                  "sections": [{"h2": "計算のしかた", "paras": paras("計算", 4), "table": {"caption": "計算の例", "cols": ["総数", "人口", "一万人あたり"], "num_cols": [0, 1, 2], "rows": [["1200", "300000", "40"]]}},
                               {"h2": "比べるときの注意", "paras": paras("注意", 5)}],
                  "related": [{"path": "/list/", "text": "都道府県別の数字の一覧"}]},
    }
    for i, p in enumerate(items):
        pages[f"pref-{i}"] = p
    for k, p in pages.items():
        (d / "content" / f"{k}.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


class ScaffoldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.site = rich_site(cls.tmp / "sites")
        cls.pages, cls.report = newsite.build_pages(cls.site, release=True)
        cls.out = cls.tmp / "release"
        sitekit.write_pages(cls.pages, cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def edit(self, name: str, fn):
        """Build a copy of the dummy with one content file changed (fn gets the page dict)."""
        d = self.tmp / "copy" / name
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(self.site, d)
        return d

    def rebuild(self, d: Path, **kw):
        return newsite.build_pages(d, release=True, **kw)

    def page_file(self, d: Path, key: str) -> Path:
        return d / "content" / f"{key}.json"

    def mutate(self, d: Path, key: str, fn):
        f = self.page_file(d, key)
        p = json.loads(f.read_text(encoding="utf-8"))
        fn(p)
        f.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")

    # ---- the dummy passes ----
    def test_dummy_passes_every_gate(self):
        self.assertEqual(self.report["thin"], {}, self.report["thin"])
        self.assertEqual(sitecheck.check_dir(self.out, BASE), [])
        self.assertEqual(self.report["warnings"], [])

    def test_seo_parts_are_in_the_pages(self):
        home = self.pages["index.html"]
        self.assertIn('"@type": "WebSite"', home)
        guide = self.pages["guide/index.html"]
        self.assertIn('"@type": "BreadcrumbList"', guide)
        self.assertIn('"@type": "Article"', guide)
        self.assertNotIn("株式会社", guide.split("</head>")[0])
        lst = self.pages["list/index.html"]
        self.assertIn('"@type": "Dataset"', lst)
        self.assertIn("data/list.csv", lst)
        self.assertTrue(self.pages["data/list.csv"].startswith("﻿順位,都道府県,数字"))
        self.assertIn('<link rel="canonical" href="https://dummy.example/list/">', lst)

    def test_sitemap_lastmod_is_the_pages_own_update_day(self):
        sm = self.pages["sitemap.xml"]
        self.assertIn("<loc>https://dummy.example/guide/</loc><lastmod>2026-11-01</lastmod>", sm)
        self.assertIn(f"<loc>https://dummy.example/pref/{self._first_item_slug()}/</loc><lastmod>2026-10-10</lastmod>", sm)
        self.assertEqual(len(set(__import__("re").findall(r"<lastmod>([^<]+)", sm))) > 1, True)

    def _first_item_slug(self):
        return sorted(newsite._example_rows(), key=lambda r: -r[2])[0][1]

    def test_robots_lets_every_bot_in_and_names_no_one(self):
        """Owner decision pending on training bots: the default stays 'everyone allowed' (search and citation bots must never be blocked by the scaffold)."""
        robots = self.pages["robots.txt"]
        self.assertEqual(robots, "User-agent: *\nAllow: /\nSitemap: https://dummy.example/sitemap.xml\n")
        self.assertNotIn("Disallow", robots)
        d = newsite.init_site("presite", "p.example", "下見", "下", self.tmp / "pre", "2026-11-03")
        (d / "config.json").write_text((d / "config.json").read_text(encoding="utf-8").replace("株式会社MACS", ""), encoding="utf-8")
        pre, _ = newsite.build_pages(d)
        self.assertIn("Disallow: /", pre["robots.txt"])       # only a preview (operator not set) keeps everybody out

    def test_about_has_method_and_correction_policy(self):
        about = self.pages["about/index.html"]
        for needle in ("運営者情報", "数字の出し方", "誤りを見つけたら", "訂正の履歴"):
            self.assertIn(needle, about)

    @unittest.skipUnless(find_chrome(), "browser checks run locally")
    def test_layoutcheck_passes(self):
        self.assertEqual(layoutcheck.main([str(self.out), "--base", BASE]), 0)

    # ---- init and release guards ----
    def test_init_refuses_bad_names_and_never_overwrites(self):
        with self.assertRaises(sitekit.BuildError):
            newsite.init_site("Bad-Name", "x.example", "x", "x", self.tmp / "sites2", "2026-11-03")
        with self.assertRaises(sitekit.BuildError):
            newsite.init_site("dummysite", "x.example", "x", "x", self.tmp / "sites", "2026-11-03")

    def test_release_refuses_example_pages_and_unset_operator(self):
        d = newsite.init_site("exsite", "ex.example", "例サイト", "例", self.tmp / "s3", "2026-11-03")
        with self.assertRaises(sitekit.BuildError) as cm:
            newsite.build_pages(d, release=True)
        self.assertIn("example pages", str(cm.exception))
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        cfg["operator_name"] = ""
        (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(sitekit.BuildError):
            newsite.build_pages(d, release=True, allow_example=True)
        pages, _ = newsite.build_pages(d)                       # a preview build works and says "noindex" everywhere
        self.assertIn('content="noindex,nofollow"', pages["index.html"])

    def test_register_adds_a_valid_line_and_refuses_twice(self):
        from sokuhou import deployplan
        copy = self.tmp / "sites.json"
        shutil.copy(ROOT / "data" / "sites.json", copy)
        before = deployplan.load_registry(copy, env={})["sites"]
        newsite.register("dummysite", "dummy.example", "ダミー統計", copy, 10, keys_file=self.keys_copy("keys0"))
        after = deployplan.load_registry(copy, env={})["sites"]
        self.assertEqual(list(after)[-1], "dummysite")
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after["dummysite"]["min_pages"], 10)
        with self.assertRaises(sitekit.BuildError):
            newsite.register("dummysite", "dummy.example", "ダミー統計", copy, 10, keys_file=self.keys_copy("keys0b"))

    def test_register_command_reads_the_site_folder(self):
        from sokuhou import deployplan
        copy = self.tmp / "sites_cmd.json"
        shutil.copy(ROOT / "data" / "sites.json", copy)
        cfg = json.loads((self.site / "config.json").read_text(encoding="utf-8"))
        newsite.register(self.site.name, cfg["site_url"].split("//")[-1], cfg["site_name"], copy, 10, keys_file=self.keys_copy("keys0c"))
        entry = deployplan.load_registry(copy, env={})["sites"]["dummysite"]
        self.assertEqual(entry["domain"], "dummy.example")

    # ---- how the sources are shown (owner 2026-11-03: no addresses and no per-source dates on the site) ----
    def with_style(self, name: str, style: str | None, strip_credit: bool = False, site_credits=None):
        d = self.edit(name, None)
        spec = json.loads((d / "site.json").read_text(encoding="utf-8"))
        if style is None:
            spec.pop("sources_style", None)
        else:
            spec["sources_style"] = style
        if strip_credit:
            spec["sources"]["main"].pop("credit")
        if site_credits is not None:
            spec["credits"] = site_credits
        (d / "site.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        return d

    def test_credit_style_shows_one_line_and_the_update_day_only(self):
        page = self.pages["list/index.html"]
        self.assertIn('<p class="credit">出典: 総務省『ダミーの調査表』を加工して作成</p>', page)
        self.assertIn("最終更新日: 2026-11-03", page)
        main = page.split("<main", 1)[1].split("</main>")[0]
        for gone in ("soumu.go.jp", "取得日", "基準日", "出典と更新日", "出典の公開ページ"):
            self.assertNotIn(gone, main)

    def test_block_style_is_unchanged(self):
        """The sites that do not set sources_style keep the old block, byte for byte."""
        pages, _ = self.rebuild(self.with_style("blk", None))
        main = pages["list/index.html"].split("<main", 1)[1].split("</main>")[0]
        self.assertIn('<h2>出典と更新日</h2>\n<ul class="sources"><li>総務省「ダミーの調査表」(<a href="https://www.soumu.go.jp/" rel="noopener" target="_blank">出典の公開ページ</a>、基準日 2026年4月1日、取得日 2026-11-03)</li></ul>\n'
                      '<p class="stamp">最終更新日: 2026-11-03</p>', main)
        self.assertIn("出典の公開ページ", pages["about/index.html"])

    def test_none_style_shows_nothing_but_still_needs_a_declaration(self):
        pages, _ = self.rebuild(self.with_style("none", "none"))
        main = pages["list/index.html"].split("<main", 1)[1].split("</main>")[0]
        for gone in ("出典", "最終更新日", "class=\"credit\""):
            self.assertNotIn(gone, main)
        with self.assertRaises(sitekit.BuildError):
            self.rebuild(self.with_style("none2", "none", strip_credit=True))

    def test_numbers_without_any_declared_source_fail(self):
        """Negative: a table with no page credit, no source credit and no site credits is the failure the check is for."""
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(self.with_style("nocredit", "credit", strip_credit=True))
        self.assertIn("no source declared", str(cm.exception))

    def test_site_credits_or_a_page_credit_satisfy_the_check(self):
        pages, _ = self.rebuild(self.with_style("sitecred", "credit", strip_credit=True, site_credits=["総務省統計局『ダミー』を加工して作成"]))
        self.assertIn("出典: 総務省統計局『ダミー』を加工して作成", pages["list/index.html"])
        d = self.with_style("pagecred", "credit", strip_credit=True)
        self.mutate(d, "list", lambda p: p.update(credit="独自の一行"))
        for key in ("home", "guide", "pref-0", "pref-1", "pref-2", "pref-3", "pref-4", "pref-5"):
            self.mutate(d, key, lambda p: p.update(credit="別の一行"))
        pages, _ = self.rebuild(d)
        self.assertIn("出典: 独自の一行", pages["list/index.html"])

    def test_block_style_still_requires_sources_on_every_page(self):
        d = self.with_style("blk2", None)
        self.mutate(d, "guide", lambda p: p.update(sources=[]))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("no sources", str(cm.exception))

    def test_unknown_style_fails(self):
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(self.with_style("badstyle", "links"))
        self.assertIn("sources_style", str(cm.exception))

    def test_init_defaults_to_credit_style(self):
        d = newsite.init_site("cs", "cs.example", "表記", "表", self.tmp / "cs", "2026-11-03")
        spec = json.loads((d / "site.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["sources_style"], "credit")
        self.assertTrue(spec["sources"]["example"]["credit"])

    # ---- the first deploy: what the repository must hold (kurashi stopped on a missing IndexNow key, 2026-11-04) ----
    def keys_copy(self, name: str) -> Path:
        k = self.tmp / f"{name}.json"
        shutil.copy(ROOT / "data" / "indexnow_keys.json", k)
        return k

    def test_register_makes_the_indexnow_key_and_leaves_old_lines_alone(self):
        from sokuhou import indexnow
        keys, reg = self.keys_copy("keys1"), self.tmp / "reg1.json"
        shutil.copy(ROOT / "data" / "sites.json", reg)
        before = indexnow.load_keys(keys)
        newsite.register("dummysite", "dummy.example", "ダミー統計", reg, 10, site_dir=self.site, keys_file=keys)
        after = indexnow.load_keys(keys)
        self.assertEqual({h: k for h, k in after.items() if h in before}, before)
        self.assertRegex(after["dummy.example"], r"^[0-9a-f]{32}$")
        self.assertEqual(indexnow.prepare(self.tmp / "rel1", "https://dummy.example", after) if (self.tmp / "rel1").mkdir() is None else None, self.tmp / "rel1" / f"{after['dummy.example']}.txt")

    def test_register_refuses_when_the_repository_side_is_not_ready(self):
        keys, reg = self.keys_copy("keys2"), self.tmp / "reg2.json"
        shutil.copy(ROOT / "data" / "sites.json", reg)
        wrong = self.edit("wrongurl", None)
        cfg = json.loads((wrong / "config.json").read_text(encoding="utf-8"))
        cfg["site_url"] = "https://another.example"
        (wrong / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(sitekit.BuildError) as cm:
            newsite.register("dummysite", "dummy.example", "ダミー統計", reg, 10, site_dir=wrong, keys_file=keys)
        self.assertIn("site_url", str(cm.exception))
        self.assertNotIn("dummysite", reg.read_text(encoding="utf-8"))       # nothing was written
        nobuild = self.edit("nobuild", None)
        (nobuild / "build.py").unlink()
        with self.assertRaises(sitekit.BuildError) as cm:
            newsite.register("dummysite", "dummy.example", "ダミー統計", reg, 10, site_dir=nobuild, keys_file=keys)
        self.assertIn("build.py", str(cm.exception))

    def test_preflight_names_a_missing_key(self):
        problems = newsite.preflight(self.site, "no-key.example", self.keys_copy("keys3"))
        self.assertTrue(any("no IndexNow key for no-key.example" in p and "add-key" in p for p in problems), problems)

    def test_a_broken_key_register_is_said_plainly(self):
        bad = self.tmp / "badkeys.json"
        bad.write_text("{ not json", encoding="utf-8")
        self.assertTrue(any("cannot be read" in p for p in newsite.preflight(None, "x.example", bad)))
        with self.assertRaises(sitekit.BuildError):
            newsite.register("x", "x.example", "x", self.tmp / "none.json", 10, keys_file=bad)

    def test_every_registered_site_has_its_indexnow_key(self):
        """The failure of the first kurashi deploy: the register named a site whose host had no key.  atomou is the one site the deploy step leaves out."""
        from sokuhou import deployplan, indexnow
        keys = indexnow.load_keys()
        for name, site in deployplan.load_registry(env={})["sites"].items():
            if name != "atomou":
                self.assertIn(site["domain"], keys, f"{name}: no IndexNow key for {site['domain']}: python -m sokuhou.indexnow add-key {site['domain']}")

    # ---- negative tests: each check finds the failure it was made for ----
    def test_thin_page_becomes_noindex_and_leaves_the_sitemap(self):
        """minna 2026-10-20: a list that is only a grid of pictures is no page for a search to send anyone to."""
        d = self.edit("thin", None)
        self.mutate(d, "pref-0", lambda p: p.update(sections=[{"h2": "短い", "paras": ["数字だけの短いページです。"]}]))
        pages, report = self.rebuild(d)
        slug = sorted(newsite._example_rows(), key=lambda r: -r[2])[0][1]
        rel = f"pref/{slug}/index.html"
        self.assertIn(rel, report["thin"])
        self.assertIn('name="robots" content="noindex,follow"', pages[rel])
        self.assertNotIn(f"/pref/{slug}/</loc>", pages["sitemap.xml"])
        self.assertEqual(sitecheck.check_dir(self._write(pages), BASE), [])   # and the result is still a clean site (the page is linked, not in the sitemap)

    def _write(self, pages) -> Path:
        out = Path(tempfile.mkdtemp(dir=self.tmp))
        sitekit.write_pages(pages, out)
        return out

    def test_strict_seo_fails_on_a_thin_page(self):
        d = self.edit("strict", None)
        self.mutate(d, "pref-0", lambda p: p.update(sections=[{"h2": "短い", "paras": ["数字だけの短いページです。"]}]))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d, strict_seo=True)
        self.assertIn("thin", str(cm.exception))

    def test_item_page_with_few_numbers_is_thin(self):
        """kuma 2026-10-15: small municipality pages (few records) were 'crawled, not indexed'."""
        d = self.edit("few", None)
        self.mutate(d, "pref-1", lambda p: p["sections"][0]["table"].update(rows=p["sections"][0]["table"]["rows"][:2]))
        _, report = self.rebuild(d)
        why = [w for rel, ws in report["thin"].items() for w in ws if "numbers in tables" in w]
        self.assertTrue(why, report["thin"])

    def test_same_page_with_another_name_fails_the_build(self):
        """saichin 2026-10-19: one page repeated with another prefecture's name ('有用性の低いコンテンツ')."""
        d = self.edit("same", None)
        a = json.loads(self.page_file(d, "pref-0").read_text(encoding="utf-8"))
        b = json.loads(json.dumps(a).replace("pref-0", "x"))
        b["path"], b["primary_kw"], b["title"], b["h1"] = "/pref/copy/", "別の県の人口あたりの数字", "別の県の人口あたりの数字(推移)", "別の県の人口あたりの数字"
        (d / "content" / "pref-copy.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("overlaps by", str(cm.exception))

    def test_same_main_term_on_two_pages_fails(self):
        d = self.edit("kw", None)
        self.mutate(d, "pref-1", lambda p: p.update(primary_kw=json.loads(self.page_file(d, "pref-0").read_text(encoding="utf-8"))["primary_kw"]))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("already the main term", str(cm.exception))

    def test_term_missing_from_title_and_h1_fails(self):
        d = self.edit("kw2", None)
        self.mutate(d, "guide", lambda p: p.update(title="数字の説明", h1="数字の説明"))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        text = str(cm.exception)
        self.assertIn("title does not contain", text)
        self.assertIn("h1 does not contain", text)

    def test_page_without_main_term_or_with_wrong_intent_fails(self):
        d = self.edit("kw3", None)
        self.mutate(d, "guide", lambda p: p.update(primary_kw="", intent=9))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("no primary_kw", str(cm.exception))

    def test_a_page_four_clicks_deep_fails(self):
        d = self.edit("deep", None)
        self.mutate(d, "pref-0", lambda p: p.update(parent="/guide/"))
        for key, parent in (("deep1", "/pref/%s/" % self._first_item_slug()), ):
            c = json.loads(self.page_file(d, "pref-1").read_text(encoding="utf-8"))
            c.update(path="/deep/a/", parent=parent, primary_kw="深い一", title="深い一の数字", h1="深い一の数字")
            (d / "content" / "deep1.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        c2 = json.loads((d / "content" / "deep1.json").read_text(encoding="utf-8"))
        c2.update(path="/deep/b/", parent="/deep/a/", primary_kw="深い二", title="深い二の数字", h1="深い二の数字")
        c2["sections"][1]["paras"] = [p + "別の文です。" for p in c2["sections"][1]["paras"]]
        (d / "content" / "deep2.json").write_text(json.dumps(c2, ensure_ascii=False), encoding="utf-8")
        c3 = dict(c2, path="/deep/c/", parent="/deep/b/", primary_kw="深い三", title="深い三の数字", h1="深い三の数字")
        (d / "content" / "deep3.json").write_text(json.dumps(c3, ensure_ascii=False), encoding="utf-8")
        for k in ("deep1", "deep2", "deep3"):   # make them different enough not to trip the similarity check first
            self.mutate(d, k, lambda p, k=k: p["sections"][0]["table"].update(rows=[[str(2014 + j), str(zlib.crc32(f"{k}{j}".encode()) % 9000), str(j * 3 + len(k)), str(j + 20)] for j in range(12)]))
            self.mutate(d, k, lambda p, k=k: p["sections"][1].update(paras=[f"{k}だけの文章です。{'これは別の内容を書いた段落です。' * 3}{zlib.crc32(f"{k}{i}".encode()) % 777}を示します。" * 2 for i in range(4)]))
            self.mutate(d, k, lambda p, k=k: p["sections"][0].update(paras=[f"{k}の表の前の文です。数字は{zlib.crc32(f"{k}9".encode()) % 555}に始まります。" * 3]))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("clicks from the home page", str(cm.exception))

    def test_more_than_three_tables_fails(self):
        d = self.edit("tables", None)
        self.mutate(d, "guide", lambda p: p["sections"].extend([{"h2": f"表{i}", "table": {"cols": ["a"], "rows": [["1"]]}} for i in range(3)]))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("tables", str(cm.exception))

    def test_missing_sources_and_unknown_parent_fail(self):
        d = self.edit("spec", None)
        self.mutate(d, "guide", lambda p: p.update(sources=[], parent="/nowhere/"))
        with self.assertRaises(sitekit.BuildError) as cm:
            self.rebuild(d)
        self.assertIn("no source declared", str(cm.exception))
        self.assertIn("not a page", str(cm.exception))


class SeokitTest(unittest.TestCase):
    def test_orphan_is_found(self):
        pages = {"index.html": '<a href="/a/">a</a>', "a/index.html": "<p>x</p>", "b/index.html": "<p>nobody links here</p>"}
        out = seokit.link_problems(pages, {"index.html", "a/index.html", "b/index.html"}, "x.example")
        self.assertEqual(out, ["b/index.html: orphan page (no page links to it)"])

    def test_header_navigation_counts_as_a_link(self):
        pages = {"index.html": '<nav><a href="/a/">a</a></nav>', "a/index.html": '<a href="/">home</a>'}
        self.assertEqual(seokit.link_problems(pages, {"index.html", "a/index.html"}, "x.example"), [])

    def test_cycle_does_not_hide_an_unreachable_island(self):
        pages = {"index.html": "<p>none</p>", "a/index.html": '<a href="/b/">b</a>', "b/index.html": '<a href="/a/">a</a>'}
        out = seokit.link_problems(pages, {"index.html", "a/index.html", "b/index.html"}, "x.example")
        self.assertEqual(len(out), 0 if False else 2)       # each is linked by the other but neither can be reached from the home page
        self.assertTrue(all("cannot be reached" in o for o in out))

    def test_alt_problems(self):
        pages = {"p/index.html": '<img src="/a.png"><a href="/x"><img src="/b.png" alt=""></a><img src="/c.png" alt=""><a href="/y"><img src="/d.png" alt="ノートの表紙"></a>'}
        out = seokit.alt_problems(pages)
        self.assertEqual(len(out), 2)
        self.assertIn("without alt", out[0])
        self.assertIn("empty alt", out[1])

    def test_alt_problems_exempts_only_the_exact_valuecommerce_counter(self):
        vc = '<img src="//ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=1&amp;pid=2" height="1" width="1" border="0">'
        self.assertEqual(seokit.alt_problems({"p/index.html": vc}), [])
        self.assertEqual(seokit.alt_problems({"p/index.html": vc.replace('width="1"', 'width="0"')}), [])
        for bad in (vc.replace('height="1"', 'height="9"'), vc.replace("valuecommerce.com", "example.com"), vc.replace(' border="0">', ' border="0" class="x">')):
            self.assertEqual(len(seokit.alt_problems({"p/index.html": bad})), 1, bad)

    def test_visible_chars_ignores_breadcrumbs_scripts_and_tags(self):
        html = '<main><nav class="crumbs"><a href="/">トップ</a> &gt; <span>x</span></nav><h1>題</h1><script>var a=1;</script><p>あ い う</p></main>'
        self.assertEqual(seokit.visible_chars(html), 4)

    def test_thin_min_chars_lowers_only_the_named_page(self):
        body = "<main><h1>t</h1><p>" + "これは文章です。" * 90 + "</p><table><tr><td>1</td></tr></table></main>"    # about 720 characters
        pages = {"a/index.html": body, "b/index.html": body.replace("これは", "あれは")}
        kinds = {"a/index.html": "article", "b/index.html": "article"}
        base = seokit.thin_reasons(pages, kinds)
        self.assertTrue(any("readable characters" in w for w in base["a/index.html"]))
        self.assertTrue(any("readable characters" in w for w in base["b/index.html"]))
        low = seokit.thin_reasons(pages, kinds, {"a/index.html": 500})
        self.assertFalse(any("readable characters" in w for w in low.get("a/index.html", [])))     # the named page passes the lower bar
        self.assertTrue(any("needs 1200" in w for w in low["b/index.html"]))                        # every other page keeps the default
        self.assertEqual(seokit.thin_reasons(pages, kinds, None), base)                              # no setting: the same answer as before

    def test_thin_bars_by_kind(self):
        long_p = "<p>" + "これは長い文章です。" * 200 + "</p>"
        pages = {"a/index.html": f"<main><h1>t</h1>{long_p}</main>", "b/index.html": "<main><h1>t</h1><p>短い。</p><table><tr><td>1</td></tr></table></main>",
                 "c/index.html": "<main><h1>t</h1><p>短い。</p></main>"}
        kinds = {"a/index.html": "analysis", "b/index.html": "analysis", "c/index.html": "archive"}
        out = seokit.thin_reasons(pages, kinds)
        self.assertIn("a/index.html", out)             # long, but no table and no chart
        self.assertTrue(any("no table" in w for w in out["a/index.html"]))
        self.assertTrue(any("readable characters" in w for w in out["b/index.html"]))
        self.assertTrue(any("always noindex" in w for w in out["c/index.html"]))

    def test_similar_pairs_ignores_archive_and_finds_copies(self):
        text = "<main><p>" + "同じ文章を県の名前だけ変えて繰り返したページです。" * 30 + "</p></main>"
        pages = {"a/index.html": text, "b/index.html": text.replace("県", "市"), "c/index.html": "<main><p>" + "まったく別の内容で、数字も違う話をしています。" * 30 + "</p></main>"}
        kinds = {k: "item" for k in pages}
        pairs = seokit.similar_pairs(pages, kinds)
        self.assertEqual([(a, b) for a, b, _ in pairs], [("a/index.html", "b/index.html")])
        self.assertEqual(seokit.similar_pairs(pages, {**kinds, "b/index.html": "archive"}), [])


if __name__ == "__main__":
    unittest.main()
