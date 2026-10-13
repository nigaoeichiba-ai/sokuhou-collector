"""atomou: the archive (finished days stay as pages, found with "終わった日も含める", not in the lists, not indexed) and the result of a finished day (our own words and facts, checked on two
pages of two companies; a day with a result is a page worth finding)."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog, resultcheck, results_queue, skins  # noqa: E402
from tests.test_atomou_build import CFG  # noqa: E402

TODAY = date(2026, 10, 13)


def seed(title, day, **kw):
    it = {"title": title, "date": day, "kind": "開催", "category": "駅伝・マラソン", "group": "スポーツ", "subject": "出雲駅伝", "what": "大学三大駅伝の開幕戦", "place": "島根県出雲市",
          "source_url": "https://official.example/a", "source_quote": day, "checked_on": "2026-10-07", "verified": True, "precision": "day"}
    it.update(kw)
    return it


def result(title, day, **kw):
    r = {"title": title, "date": day, "text": "大学三大駅伝の開幕戦で、アンカーまで首位争いが続きました。優勝校は区間賞を3つ取り、中盤で先頭に立ちました。記録は昨年より約1分短くなりました。",
         "facts": [["優勝", "テスト大学"], ["記録", "2時間08分12秒"], ["区間数", "6区間"]], "written_on": "2026-10-13", "source_url": "https://official.example/r", "source_quote": "優勝 テスト大学",
         "source_url2": "https://news.example/r", "source_quote2": "テスト大学が優勝", "verified": True}
    r.update(kw)
    return r


def world(td: str, results=None):
    d = Path(td)
    (d / "seed_t_2026-10-07.json").write_text(json.dumps([
        seed("終わった大会(先月)", "2026-08-01"), seed("終わった大会(昨日)", "2026-10-12"), seed("先月の大きな行事", "2026-08-02", keep=True), seed("これからの大会", "2026-11-01"),
        seed("悲しみの日", "2026-10-10", sensitivity="grief")]), encoding="utf-8")
    (d / "blocklist.json").write_text('{"keywords": []}', encoding="utf-8")
    if results is not None:
        (d / "result_t_2026-10-13.json").write_text(json.dumps(results), encoding="utf-8")
    return catalog.build_catalog(TODAY, seed_dir=d)[0]


class Archive(unittest.TestCase):
    def test_a_day_that_ended_long_ago_is_kept_in_the_archive_not_dropped_and_not_in_the_lists(self):
        with tempfile.TemporaryDirectory() as td:
            entries = world(td)
        by = {e["title"]: e for e in entries}
        self.assertTrue(by["終わった大会(先月)"]["archived"])
        self.assertFalse(by["終わった大会(昨日)"]["archived"])        # inside the 30 days: still in the lists as もう○日
        self.assertFalse(by["先月の大きな行事"]["archived"])           # a kept day is never archived
        self.assertFalse(by["これからの大会"]["archived"])
        pub = {e["title"] for e in catalog.public_json(entries)}
        arc = {e["title"] for e in catalog.archive_json(entries)}
        self.assertEqual(arc, {"終わった大会(先月)"})
        self.assertNotIn("終わった大会(先月)", pub)
        self.assertIn("終わった大会(昨日)", pub)

    def test_the_build_has_the_archive_file_the_switch_and_holds_the_archived_pages_back_from_search_engines(self):
        pages = build.build_pages(CFG, release=False, today=TODAY)
        arc = json.loads(pages["assets/archive.json"])
        self.assertTrue(arc and all(e["status"] == "ended" for e in arc))
        self.assertIn('id="f-arch"', pages["search/index.html"])
        self.assertIn("終わった日も含める", pages["search/index.html"])
        one = arc[0]
        page = pages[f"e/{one['id']}/index.html"]
        self.assertIn("noindex", page)
        self.assertNotIn(f"/e/{one['id']}/", pages["sitemap.xml"])
        self.assertNotIn(one["id"], [e["id"] for e in json.loads(pages["assets/catalog.json"])])     # an archived day is not in the public list

    def test_the_search_page_script_reads_the_archive_only_when_asked(self):
        js = (ROOT / "sites/atomou/assets/app.js").read_text(encoding="utf-8")
        self.assertIn("/assets/archive.json", js)
        self.assertIn("if (c.status === 'ended' && !c.keep && !st.a) return false;", js)       # the finished days are left out unless the box is ticked


class Result(unittest.TestCase):
    def test_a_result_needs_text_facts_two_pages_of_two_companies_and_the_check(self):
        ok = result("t", "2026-10-12")
        self.assertTrue(catalog.result_ok(ok, TODAY))
        bad = {
            "not checked": {**ok, "verified": False},
            "text too short": {**ok, "text": "短い"},
            "two facts": {**ok, "facts": ok["facts"][:2]},
            "a fact with a long key": {**ok, "facts": ok["facts"][:2] + [["とても長い見出しの項目です", "x"]]},
            "one company twice": {**ok, "source_url2": "https://www.official.example/z"},
            "not https": {**ok, "source_url2": "http://news.example/r"},
            "no date": {**ok, "written_on": ""},
            "written in the future": {**ok, "written_on": "2026-12-01"},
            "no quote": {**ok, "source_quote2": ""},
        }
        for why, r in bad.items():
            self.assertFalse(catalog.result_ok(r, TODAY), why)

    def test_a_result_is_put_on_the_day_and_the_day_may_be_indexed(self):
        with tempfile.TemporaryDirectory() as td:
            entries = world(td, [result("終わった大会(昨日)", "2026-10-12"), result("終わった大会(先月)", "2026-08-01"), result("これからの大会", "2026-11-01"),
                                 result("終わった大会(昨日)", "2026-10-11")])
        by = {e["title"]: e for e in entries}
        self.assertEqual(by["終わった大会(昨日)"]["result"]["facts"][0], ["優勝", "テスト大学"])
        self.assertTrue(by["終わった大会(先月)"]["archived"] and by["終わった大会(先月)"]["result"])     # an archived day with a result
        self.assertIn("結果", by["終わった大会(昨日)"]["result"]["text"] + "結果")
        ids = catalog.indexable_ids(entries, TODAY, date(2026, 10, 8), 6)
        self.assertIn(by["終わった大会(先月)"]["id"], ids)       # the result makes it findable
        c = build.Ctx(CFG, True, TODAY, entries, skins.css())
        page = build.event_page(c, by["終わった大会(先月)"], True, entries)
        self.assertIn('<section class="result" id="result">', page)
        self.assertIn("<dt>優勝</dt><dd>テスト大学</dd>", page)
        self.assertIn("終わった大会(先月)の結果", page)
        plain = build.event_page(c, by["終わった大会(昨日)"], False, entries) if not by["終わった大会(昨日)"]["result"] else ""
        self.assertNotIn("id=\"result\"", build.event_page(c, by["これからの大会"], True, entries) if not by["これからの大会"].get("result") else "")
        self.assertEqual(plain, "")

    def test_a_card_without_a_result_shows_no_result_section(self):
        with tempfile.TemporaryDirectory() as td:
            entries = world(td)
        c = build.Ctx(CFG, True, TODAY, entries, skins.css())
        e = next(x for x in entries if x["title"] == "終わった大会(昨日)")
        self.assertNotIn('id="result"', build.event_page(c, e, False, entries))


class Checking(unittest.TestCase):
    def run_check(self, cands, pages):
        with tempfile.TemporaryDirectory() as td:
            entries = world(td)
        with mock.patch.object(resultcheck.catalog, "build_catalog", return_value=(entries, {})):
            return resultcheck.check(cands, TODAY, page_of=lambda u: pages[u])

    def cand(self, **kw):
        c = result("終わった大会(昨日)", "2026-10-12")
        c.pop("verified"), c.pop("written_on")
        c.update(kw)
        return c

    PAGES = {"https://official.example/r": "結果 優勝 テスト大学 記録 2時間08分12秒 6区間 の大会", "https://news.example/r": "テスト大学が優勝した。記録は2時間08分12秒"}

    def test_a_result_on_two_pages_passes(self):
        ok, bad = self.run_check([self.cand()], self.PAGES)
        self.assertEqual((len(ok), bad), (1, []))
        self.assertTrue(ok[0]["verified"] and ok[0]["written_on"] == "2026-10-13")

    def test_what_is_not_on_the_pages_or_not_ended_or_quiet_is_refused(self):
        for why, cand, pages in (
            ("no such card", self.cand(title="ない大会"), self.PAGES),
            ("the day has not ended yet", self.cand(title="これからの大会", date="2026-11-01"), self.PAGES),
            ("a quiet day gets no result page", self.cand(title="悲しみの日", date="2026-10-10"), self.PAGES),
            ("quote not on the page", self.cand(source_quote2="別の文"), self.PAGES),
            ("only 0 of 3 facts", self.cand(facts=[["優勝", "別の大学"], ["記録", "9時間"], ["区間数", "99区間"]]), self.PAGES),
        ):
            ok, bad = self.run_check([cand], pages)
            self.assertEqual(ok, [], why)
            self.assertTrue(bad and why in bad[0][1], (why, bad))


class Queue(unittest.TestCase):
    def test_the_days_waiting_for_a_result(self):
        with tempfile.TemporaryDirectory() as td:
            entries = world(td, [result("終わった大会(昨日)", "2026-10-12")])
            entries2 = world(td + "/x" if False else td, [])
        names = [r["title"] for r in results_queue.queue(entries, TODAY)]
        self.assertNotIn("終わった大会(昨日)", names)       # it has its result
        names2 = [r["title"] for r in results_queue.queue(entries2, TODAY)]
        self.assertIn("終わった大会(昨日)", names2)
        for gone in ("これからの大会", "悲しみの日", "終わった大会(先月)"):
            self.assertNotIn(gone, names2)                  # not ended; a quiet day; too long ago


if __name__ == "__main__":
    unittest.main()
