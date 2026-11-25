"""The help articles (sites/minna/content/guides.json): shape, and every reference they make exists."""
import json
import re
import unittest
from pathlib import Path

from sites.minna import build, factory

HERE = Path(build.__file__).resolve().parent


class GuidesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guides = json.loads((HERE / "content" / "guides.json").read_text(encoding="utf-8"))["guides"]
        cls.specs = {s["slug"] for s in factory.load_specs()}

    def test_every_article_is_complete(self):
        slugs = [g["slug"] for g in self.guides]
        self.assertEqual(len(slugs), len(set(slugs)))
        for g in self.guides:
            self.assertRegex(g["slug"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
            self.assertTrue(20 <= len(g["description"]) <= 160, g["slug"])
            self.assertGreaterEqual(len(g["sections"]), 5, g["slug"])
            body = "".join(p for s in g["sections"] for p in s.get("paras", []) + s.get("list", []) + [c for r in s.get("table", {}).get("rows", []) for c in r])
            self.assertGreater(len(body), 900, g["slug"])
            for s in g["sections"]:
                self.assertTrue(s["h2"].strip())
                if s.get("table"):
                    n = len(s["table"]["head"])
                    self.assertTrue(all(len(r) == n for r in s["table"]["rows"]), g["slug"])
            for q, a in g.get("faq", []):
                self.assertTrue(q and a)
            text = json.dumps(g, ensure_ascii=False)
            for bad in ("None", "TODO", "undefined", "{{"):
                self.assertNotIn(bad, text, g["slug"])

    def test_related_series_and_site_wide_links_exist(self):
        for g in self.guides:
            for slug in g.get("related_series", []):
                self.assertIn(slug, self.specs, f"{g['slug']} points to the unknown series {slug}")
        known = {g["slug"] for g in self.guides}
        for slugs in build.GUIDE_BY_GENRE.values():
            for slug in slugs:
                self.assertIn(slug, known)
        for slug in build.GUIDE_DEFAULT:
            self.assertIn(slug, known)

    def test_sources_are_real_urls(self):
        for g in self.guides:
            for s in g.get("sources", []):
                self.assertRegex(s["url"], r"^https://")
                self.assertTrue(s["title"].strip())

    def test_a_guide_without_a_required_field_stops_the_build(self):
        import tempfile
        old = build.HERE
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "content").mkdir()
            (Path(t) / "content" / "guides.json").write_text(json.dumps({"guides": [{"slug": "x", "title": "t"}]}), encoding="utf-8")
            build.HERE = Path(t)
            try:
                with self.assertRaises(build.BuildError):
                    build.load_guides()
            finally:
                build.HERE = old

    def test_the_top_page_picks_up_the_newest_guides(self):
        newest = sorted(self.guides, key=lambda g: (g.get("date", ""), g["slug"]), reverse=True)
        box = build.new_guides_box(self.guides)
        self.assertEqual(re.findall(r'href="/guide/([a-z0-9-]+)/"', box), [g["slug"] for g in newest[:4]])
        self.assertNotIn(f'/guide/{newest[4]["slug"]}/', box)

    def test_a_newer_guide_replaces_the_oldest_one_on_the_top_page(self):
        """Negative case: a hand-kept list would not change when an article is added."""
        before = build.new_guides_box(self.guides)
        added = {"slug": "zz-brand-new", "title": "新しい記事", "description": "説明", "date": "2999-01-01"}
        after = build.new_guides_box(self.guides + [added])
        self.assertNotIn("/guide/zz-brand-new/", before)
        self.assertIn("/guide/zz-brand-new/", after)
        slugs = re.findall(r'href="/guide/([a-z0-9-]+)/"', before)
        self.assertNotIn(f"/guide/{slugs[-1]}/", after)
        self.assertEqual(build.new_guides_box([]), "")


if __name__ == "__main__":
    unittest.main()
