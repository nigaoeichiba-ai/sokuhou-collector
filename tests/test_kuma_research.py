"""/research/ (sites/kuma/research.py): the notes are checked before they are published, and every published note is consistent with its own numbers."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, research
from sokuhou import sitecheck
from sokuhou.sitekit import BuildError
from sokuhou.sources import env_kuma
from tests.test_kuma_build import CFG, FIX, HAVE_PYPDF, raw_data

ROOT = Path(__file__).resolve().parents[1]
DOCS = research.load()


def sample():
    return {
        "slug": "sample-note", "date": "2026-10-15", "data_as_of": "2026-10-13", "title": "見本の研究ノート(件数を数えた)", "h1": "見本の研究ノート",
        "description": "見本の説明です。", "lead": "これは見本の研究ノートです。数えたのは見本の記録の件数で、四十字を超える長さにしてあります。",
        "findings": ["一つ目のわかったこと。", "二つ目のわかったこと。"],
        "sections": [{"h2": "一つ目", "paragraphs": ["本文です。[[ランキング|/ranking/sightings/]]を見てください。"], "chart": {"kind": "bars", "labels": ["a", "b"], "values": [1, 2], "title": "t", "desc": "d"}},
                     {"h2": "二つ目", "table": {"head": ["x", "y"], "rows": [["1", "2"]]}}],
        "method": ["数え方。"], "caveats": ["言えないこと。"], "credits": ["出典:見本のデータ(CC BY 4.0)を加工して作成"],
        "script": "sites/kuma/research/scripts/common.py",
    }


class ValidationTest(unittest.TestCase):
    def test_a_good_note_has_no_problems(self):
        self.assertEqual(research.problems(sample(), ROOT), [])

    def test_each_rule_is_caught(self):
        def bad(mutate):
            d = sample()
            mutate(d)
            return research.problems(d, ROOT)
        self.assertTrue(any("missing" in p for p in bad(lambda d: d.pop("method"))))
        self.assertTrue(any("claim not allowed" in p for p in bad(lambda d: d["findings"].__setitem__(0, "この県は安全です。"))))
        self.assertTrue(any("claim not allowed" in p for p in bad(lambda d: d["sections"][0]["paragraphs"].append("必ず出会います。"))))
        self.assertTrue(any("table rows" in p for p in bad(lambda d: d["sections"][1]["table"]["rows"].append(["1"]))))
        self.assertTrue(any("bar chart" in p for p in bad(lambda d: d["sections"][0]["chart"]["values"].append(3))))
        self.assertTrue(any("slug" in p for p in bad(lambda d: d.__setitem__("slug", "Bad Slug"))))
        self.assertTrue(any("ISO date" in p for p in bad(lambda d: d.__setitem__("date", "15 Oct"))))
        self.assertTrue(any("description" in p for p in bad(lambda d: d.__setitem__("description", "あ" * 161))))
        self.assertTrue(any("script not found" in p for p in bad(lambda d: d.__setitem__("script", "sites/kuma/research/scripts/nothing.py"))))
        self.assertTrue(any("internal link" in p for p in bad(lambda d: d["sections"][0]["paragraphs"].append("[[x|/live/akita]]"))))
        self.assertTrue(any("credits" in p for p in bad(lambda d: d.__setitem__("credits", ["どこかのデータ"]))))
        self.assertTrue(any("findings" in p for p in bad(lambda d: d.__setitem__("findings", ["一つだけ。"]))))

    def test_a_duplicate_slug_stops_the_build(self):
        with self.assertRaises(BuildError):
            research.check([sample(), sample()], ROOT)

    def test_text_is_escaped_and_only_site_links_are_made(self):
        html = research.inline("<b>x</b> [[秋田県|/live/akita/]] [[外|https://evil.example/]]")
        self.assertNotIn("<b>", html)
        self.assertIn('<a href="/live/akita/">秋田県</a>', html)
        self.assertNotIn('href="https://evil', html)


class PublishedNotesTest(unittest.TestCase):
    def test_there_is_at_least_one_note_and_every_one_passes(self):
        self.assertTrue(DOCS)
        research.check(DOCS, ROOT)
        self.assertEqual(len({d["slug"] for d in DOCS}), len(DOCS))

    def test_the_credits_are_the_ones_the_data_files_carry(self):
        credits = {json.loads(p.read_text(encoding="utf-8")).get("credit") for p in (ROOT / "data").glob("*_kuma.json")}
        for d in DOCS:
            for c in d["credits"]:
                self.assertIn(c, credits, f"{d['slug']}: credit differs from every data file: {c[:40]}")

    def test_hour_of_day_note_agrees_with_itself(self):
        d = next(x for x in DOCS if x["slug"] == "hour-of-day")
        hours, table = d["sections"][0]["chart"], d["sections"][1]["table"]
        self.assertEqual(len(hours["values"]), 24)
        self.assertAlmostEqual(sum(hours["values"]), 100, delta=1.2)                        # shares of one total (rounded to 0.1)
        total = sum(int(r[1].replace(",", "")) for r in table["rows"])
        self.assertIn(f"{total:,}件", d["lead"])                                              # the lead's total is the table's total
        for r in table["rows"]:
            self.assertAlmostEqual(sum(int(c.rstrip("%")) for c in r[2:]), 100, delta=2)      # four bands of one prefecture
        for r in d["sections"][3]["table"]["rows"]:
            wk, we, ratio = float(r[1]), float(r[2]), int(r[3].rstrip("%"))
            self.assertAlmostEqual(we / wk * 100, ratio, delta=4)                              # the ratio is of the shown (rounded) averages


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.docs = [sample(), {**copy.deepcopy(sample()), "slug": "second-note", "date": "2026-10-14", "h1": "二つ目の見本"}]
        raw = raw_data()
        raw["notices"] = env_kuma.parse_notices((FIX / "env_kuma_effort12.html").read_text(encoding="utf-8"))
        cls.files = build.render_site(raw, CFG, cls.out, release=True, research=cls.docs)
        cls.empty = build.render_site(raw, CFG, Path(cls.tmp.name) / "e", release=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_hub_and_each_note_are_pages_linked_from_the_home_page_and_the_checker_passes(self):
        for rel in ("research/index.html", "research/sample-note/index.html", "research/second-note/index.html"):
            self.assertIn(rel, self.files)
        home = self.read("index.html")
        self.assertIn('href="/research/sample-note/"', home)
        self.assertIn('href="/research/"', home)
        self.assertLess(home.index("sample-note"), home.index("second-note"))                  # newest first
        self.assertEqual(sitecheck.check_dir(self.out, CFG["site_url"]), [])

    def test_a_note_shows_what_was_found_how_it_was_counted_and_what_it_cannot_say(self):
        html = re.sub(r"<[^>]+>", " ", self.read("research/sample-note/index.html"))
        for part in ("わかったこと", "数え方", "この分析で言えないこと", "出典:見本のデータ", "sites/kuma/research/scripts/common.py", "2026年10月13日までのもの"):
            self.assertIn(part, html)

    def test_the_sitemap_date_of_a_note_is_the_day_it_was_written_and_the_hub_takes_the_newest(self):
        sm = dict(re.findall(r"<loc>https://kuma-sokuho.com([^<]*)</loc><lastmod>([^<]+)</lastmod>", self.read("sitemap.xml")))
        self.assertEqual(sm["/research/second-note/"], "2026-10-14")
        self.assertEqual(sm["/research/sample-note/"], "2026-10-15")
        self.assertEqual(sm["/research/"], "2026-10-15")

    def test_without_notes_there_is_no_page_and_no_link(self):
        self.assertNotIn("research/index.html", self.empty)
        self.assertNotIn('href="/research/"', (Path(self.tmp.name) / "e" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
