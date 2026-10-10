"""/cite/ of the bear site: where the numbers come from, how they are counted, the comparison with the ministry, how to quote.

Every figure is checked against numbers counted another way (from the fixtures) or copied from a hand count, and the page is checked with the
site checker.  The ministry comparison uses figures written into the test, so it does not depend on the PDF fixtures' real values.
"""
import copy
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from sites.kuma import build, cite
from sites.kuma import live as live_mod
from sokuhou import sitecheck
from sokuhou.sources import env_kuma, kumalib, otsu_kuma
from tests.test_kuma_build import AKITA, CFG, COUNTS_META, FIX, HAVE_PYPDF, MIYAGI, _counts_raw, _yamaguchi, raw_data

TODAY = date(2026, 10, 7)


def otsu_counts():
    """Otsu City's page (the fixture: dated headings only), read the way the collector reads it: counts only."""
    html = (Path(__file__).parent / "fixtures" / "otsu_kuma_page.html").read_text(encoding="utf-8")
    return otsu_kuma.parse(html, datetime(2026, 10, 7, 12, 0, tzinfo=kumalib.JST))


def text_of(html: str) -> str:
    body = html.split("<main", 1)[1].split("</main>", 1)[0]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def make_raw():
    """The ministry's figures for the compared months (April to the latest published month, July): Miyagi 5 (= ours), Akita 10 (ours: 8), Fukushima 723
    (ours: nothing in those months), Yamaguchi None (the prefecture is not in the ministry's table)."""
    raw = raw_data()
    raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
    rows = {p["name"]: p for p in raw["sightings"]["prefectures"]}
    for name in ("宮城", "秋田", "福島", "山口"):
        rows[name]["monthly"]["R08"] = [None] * 12
    rows["宮城"]["monthly"]["R08"][:4] = [0, 3, 0, 2]
    rows["秋田"]["monthly"]["R08"][:4] = [0, 0, 10, 0]
    rows["福島"]["monthly"]["R08"][:4] = [100, 200, 300, 123]
    return raw


def miyagi_rows():
    m = copy.deepcopy(MIYAGI)
    day = lambda mo, d: f"2026-{mo:02d}-{d:02d}T09:00:00+09:00"  # noqa: E731
    m["sightings"] = ([{"observed_at": day(5, d), "city": "大和町", "place": f"場所{d}", "count": 1, "kind": "目撃", "species": "クマ"} for d in (3, 9, 20)]
                      + [{"observed_at": day(7, d), "city": "富谷市", "place": f"場所{d}", "count": 1, "kind": "痕跡", "species": "クマ"} for d in (4, 18)]
                      + MIYAGI["sightings"][1:])
    m["as_of"] = "2026-10-05"
    return m


def akita_rows():
    a = copy.deepcopy(AKITA)
    a["sightings"] = [{"observed_at": f"2026-06-{d:02d}T09:00:00+09:00", "city": "鹿角市", "place": f"場所{d}", "count": 1, "kind": "目撃", "species": "クマ"}
                      for d in range(1, 9)] + AKITA["sightings"]
    return a


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class CitePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raw = make_raw()
        cls.prefs = {"miyagi": miyagi_rows(), "akita": akita_rows(), "yamaguchi": _yamaguchi(), "fukushima": _counts_raw(), "otsu": otsu_counts()}
        cls.out = Path(cls.tmp.name) / "site"
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            cls.files = build.render_site(cls.raw, CFG, cls.out, release=True, prefs=cls.prefs, today=TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_page_exists_and_the_site_checker_passes(self):
        self.assertIn("cite/index.html", self.files)
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])
        html = self.read("cite/index.html")
        self.assertIn("<title>データの出典・数え方・引用のしかた(クマ出没速報)", html)
        self.assertEqual(len(re.findall("<h1", html)), 1)

    def test_every_page_links_to_it_from_the_footer_and_the_hub_and_home_do_too(self):
        for rel in ("index.html", "live/index.html", "ranking/sightings/index.html", "about/index.html", "cite/index.html"):
            self.assertIn('href="/cite/"', self.read(rel), rel)
        self.assertEqual([r for r in self.files if r.endswith("index.html") and 'href="/cite/"' not in self.read(r)
                          and not r.startswith(("assets",))], [])

    def test_the_source_table_lists_every_source_with_its_own_count_licence_and_scope(self):
        text = text_of(self.read("cite/index.html"))
        self.assertIn("1. 取得元の一覧(5か所)", text)                  # Miyagi, Akita, Yamaguchi (records) + Fukushima, Otsu (counts only)
        compact = text.replace(" ", "")
        self.assertIn("再利用の許可が明示されている3か所は、詳しい記録(一覧・市町村ページ・地図・CSV)まで載せ、許可が明示されていない2か所は、市町村・月・件数・最新の日付だけを載せています", compact)
        self.assertIn("大津市のように、市のページが公開している情報でも、許可が明示されていなければ、件数だけです", compact)
        # counted from the fixtures by hand: Miyagi 3 (May) + 2 (July) + 2 (October; the Oct-29 row was dropped), Akita 8 (June) + 2 (August),
        # Fukushima 4 rows, Otsu 32 dated entries
        for name, count in (("宮城県", 7), ("秋田県", 10), ("滋賀県大津市", 32), ("福島県", 4)):
            self.assertRegex(text, name + r".{0,80}?" + str(count) + r" \d+月")
        self.assertRegex(text, r"滋賀県大津市 大津市のみ 件数のみ 32")
        self.assertIn("宮城県の規約(自由に二次利用可)", text)
        self.assertIn("CC BY 4.0", text)
        self.assertIn("再利用の許可が明示されていないため、件数と最新の日付だけを載せています", text)

    def test_the_counts_on_the_page_equal_the_counts_on_the_hub(self):
        hub = text_of(self.read("live/index.html"))
        cite_text = text_of(self.read("cite/index.html"))
        for name in ("宮城県", "秋田県", "山口県"):
            hub_n = re.search(re.escape(name) + r" ([\d,]+) \d+月\d+日の分まで", hub).group(1)
            self.assertRegex(cite_text, re.escape(name) + r".{0,60}?\b" + hub_n + r"\b")

    def test_the_ministry_comparison_uses_the_same_months_and_only_whole_prefectures_with_data(self):
        text = text_of(self.read("cite/index.html"))
        self.assertIn("同じ期間(令和8年度の4月〜7月)", text)
        self.assertIn("比べられる2都道府県のうち、1都道府県は、1件も違いません", text.replace(" ", ""))
        self.assertRegex(text, r"宮城県 記録 5 5 同じ")                   # the same figure on both sides
        self.assertRegex(text, r"秋田県 記録 10 8 80%")
        table = text.split("当サイト÷環境省", 1)[1].split("差が出る主な理由", 1)[0]
        self.assertNotIn("福島県", table)                                  # nothing held for April-July: not compared
        self.assertNotIn("山口県", table)                                  # not in the ministry's table (None): not compared
        self.assertNotIn("大津市", table)                                  # a part of a prefecture: not compared
        self.assertIn("9月9日公表", text)

    def test_ministry_rows_directly(self):
        with mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            d = build.prepare(self.raw)
            d["live_prefs"], d["live_counts"] = build.prepare_prefs(self.prefs), live_mod.prepare_counts(self.prefs)
            lv = live_mod.prepare_live(d, TODAY)
        _, items, months = cite.ministry_rows(d, cite.source_rows(d, lv))
        self.assertEqual(months, [4, 5, 6, 7])
        self.assertEqual([(x["pref"], x["env"], x["ours"]) for x in items], [("宮城", 5, 5), ("秋田", 10, 8)])

    def test_coverage_names_the_partial_sources_and_does_not_say_uncovered_means_safe(self):
        text = text_of(self.read("cite/index.html"))
        self.assertIn("取得元があるのは、5都道府県です(記録まで載せているのは3、件数だけは2)(滋賀県は大津市のみ)", text.replace(" ", ""))
        self.assertIn("載っていない地域(42都道府県)があります", text)
        self.assertIn("「載っていない」は、「出没がない」「安全」という意味ではありません", text)

    def test_how_to_quote_gives_dated_examples_with_the_real_numbers(self):
        text = text_of(self.read("cite/index.html"))
        self.assertIn("2026年10月7日閲覧", text)
        self.assertIn("秋田県の令和8年度の記録は10件(2026年8月31日の分まで)", text)    # the record source with the most rows and the whole prefecture
        self.assertIn("https://kuma-sokuho.com/live/akita/", text)
        self.assertIn("環境省・自治体が作成したものではありません", text)

    def test_the_stated_update_frequency_is_the_one_the_workflow_runs(self):
        wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "kuma-live.yml").read_text(encoding="utf-8")
        crons = re.findall(r'^\s*- cron: "([^"]+)"', wf, re.M)
        self.assertEqual(len(crons), 1)
        minute, hour, *rest = crons[0].split()
        self.assertTrue(minute.isdigit() and hour.isdigit() and rest == ["*", "*", "*"], crons)       # one fixed time a day
        text = text_of(self.read("cite/index.html"))
        self.assertIn("1日1回", text)
        self.assertNotIn("3時間ごと", text)
        self.assertIn("取得は、1日1回、自動で行っています", text_of(self.read("live/index.html")))

    def test_no_claim_of_what_the_site_does_not_do(self):
        text = text_of(self.read("cite/index.html"))
        for bad in ("日本一", "最多", "安全です", "確実", "全国のすべて"):
            self.assertNotIn(bad, text)
        self.assertIn("報道・SNS・住民の投稿・他のサイトが集めたデータは、使っていません", text)
        self.assertIn("重ねて数えています", text)                           # no deduplication is claimed
        self.assertIn("お問い合わせ", text)

    def test_the_csv_link_is_there_only_when_licensed_sources_exist(self):
        self.assertIn("データのダウンロード(CSV)のページ", self.read("cite/index.html"))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}):
            out = Path(tmp) / "c"
            build.render_site(self.raw, CFG, out, release=True, prefs={"fukushima": _counts_raw(), "otsu": otsu_counts()}, today=TODAY)
            html = (out / "cite/index.html").read_text(encoding="utf-8")
            self.assertNotIn('href="/data/"', html)
            text = text_of(html)
            self.assertIn("1. 取得元の一覧(2か所)", text)
            self.assertIn("再利用の許可が明示されている0か所は、詳しい記録", text.replace(" ", ""))


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class NoLiveDataTest(unittest.TestCase):
    def test_without_any_live_source_there_is_no_cite_page_and_no_footer_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "n"
            files = build.render_site(make_raw(), CFG, out, release=True, prefs=None, today=TODAY)
            self.assertNotIn("cite/index.html", files)
            self.assertNotIn('href="/cite/"', (out / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn('href="/live/"', (out / "index.html").read_text(encoding="utf-8"))       # no navigation link to pages that do not exist
            self.assertNotIn("live/index.html", files)
            self.assertNotIn("map/index.html", files)
            self.assertEqual(sitecheck.check_dir(out, CFG["site_url"]), [])


class HelpersTest(unittest.TestCase):
    def test_covered_prefs_order_and_the_rest(self):
        rows = [{"pref": "宮城", "mode": "records"}, {"pref": "福島", "mode": "counts"}, {"pref": "宮城", "mode": "counts"}]
        rec, cnt, none = cite.covered_prefs(rows)
        self.assertEqual((rec, cnt), (["宮城"], ["福島"]))              # a prefecture with records is not listed again as counts-only
        self.assertEqual(len(none), 45)
        self.assertNotIn("宮城", none)


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class StopListTest(unittest.TestCase):
    """A publisher's request to stop must work under both spellings (the collector's name 'fukushima_kuma' and the site's key 'fukushima') and hide the source everywhere."""

    def test_is_stopped_accepts_either_spelling(self):
        with mock.patch.object(kumalib, "STOPPED", {"fukushima_kuma"}):
            self.assertTrue(kumalib.is_stopped("fukushima"))
            self.assertTrue(kumalib.is_stopped("fukushima_kuma"))
            self.assertFalse(kumalib.is_stopped("fukui"))
            self.assertFalse(kumalib.is_stopped("miyagi_kuma"))
        with mock.patch.object(kumalib, "STOPPED", {"otsu"}):
            self.assertTrue(kumalib.is_stopped("otsu_kuma"))
        with mock.patch.object(kumalib, "STOPPED", set()):
            self.assertFalse(kumalib.is_stopped("fukushima"))

    def test_the_collector_skips_a_stopped_source_whichever_spelling_the_list_uses(self):
        from sokuhou import run
        called = []
        src = run.Source("fukushima_kuma", lambda: called.append(1) or {}, lambda o, n: None)
        for spelling in ("fukushima", "fukushima_kuma"):
            with mock.patch.object(kumalib, "STOPPED", {spelling}), tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(run.run_group([src], Path(tmp)), ([], {}))
        self.assertEqual(called, [])

    def test_a_stopped_record_source_and_a_stopped_counts_source_vanish_from_every_page(self):
        raw = make_raw()
        prefs = {"miyagi": miyagi_rows(), "yamaguchi": _yamaguchi(), "fukushima": _counts_raw()}
        for stopped, gone in (("miyagi_kuma", "宮城県"), ("fukushima", "福島県")):
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(live_mod.LIVE_SOURCES, {"fukushima": COUNTS_META}),                     mock.patch.object(kumalib, "STOPPED", {stopped}):
                out = Path(tmp) / "s"
                files = build.render_site(raw, CFG, out, release=True, prefs=prefs, today=TODAY)
                cite_text = text_of((out / "cite/index.html").read_text(encoding="utf-8"))
                self.assertNotRegex(cite_text, gone + r" (記録|件数のみ)")
                self.assertIn("1. 取得元の一覧(2か所)", cite_text)
                slug = "miyagi" if stopped == "miyagi_kuma" else "fukushima"
                self.assertNotIn(f"live/{slug}/index.html", files)
                self.assertNotIn(f"live/{slug}/feed.xml", files)
                self.assertEqual(sitecheck.check_dir(out, CFG["site_url"]), [])
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(kumalib, "STOPPED", {"otsu_kuma"}):
            out = Path(tmp) / "o"
            files = build.render_site(raw, CFG, out, release=True, prefs={"yamaguchi": _yamaguchi(), "otsu": otsu_counts()}, today=TODAY)
            self.assertNotIn("滋賀県大津市", text_of((out / "cite/index.html").read_text(encoding="utf-8")))
            self.assertFalse([f for f in files if f.startswith("live/shiga")])


if __name__ == "__main__":
    unittest.main()
