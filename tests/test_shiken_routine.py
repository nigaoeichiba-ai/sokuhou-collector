"""shiken-nittei.com の定期更新ルーティン: 朝チェックの公式ページの一覧が、サイトのデータから機械的に作られること。"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "sites" / "shiken" / "tools" / "morning_list.py"


class MorningListTest(unittest.TestCase):
    def test_every_source_of_every_event_has_an_official_page(self):
        from sites.shiken.gen import model
        from sites.shiken.gen.sources import OFFICIAL_PAGES
        used = {e["source"] for e in model.EVENT_LIST}
        for sid in used:
            self.assertIn(sid, OFFICIAL_PAGES, sid)
            self.assertTrue(OFFICIAL_PAGES[sid]["url"].startswith("https://"), sid)

    def test_the_list_follows_the_data_and_the_window(self):
        sys.path.insert(0, str(ROOT))
        spec_tool = __import__("importlib.util").util.spec_from_file_location("morning_list", TOOL)
        mod = __import__("importlib.util").util.module_from_spec(spec_tool)
        spec_tool.loader.exec_module(mod)
        from sites.shiken.gen import common, model
        before = common.TODAY
        try:
            data = mod.build(30, "2026-11-08", 7)
            ids = [e for g in data["sources"] for e in g["events"]]
            self.assertTrue(ids)
            self.assertTrue(all(-7 <= e["left"] <= 30 for e in ids))
            # every event of the data inside the window is in the list: nobody keeps a list by hand
            want = [e for e in model.EVENT_LIST if -7 <= common.left(e["iso"]) <= 30]
            self.assertEqual(len(ids), len(want))
            self.assertTrue(all(g["url"] and g["org"] for g in data["sources"]))
            # a day with other events gives another list
            other = mod.build(30, "2027-01-05", 7)
            self.assertNotEqual({g["source"] for g in data["sources"]}, {g["source"] for g in other["sources"]})
        finally:
            common.set_today(before.isoformat())

    def test_the_command_prints_the_markdown_list(self):
        import os
        r = subprocess.run([sys.executable, str(TOOL), "--today", "2026-11-08"], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("公式URL: https://", r.stdout)

    def test_the_routine_doc_is_in_the_repository_and_claude_md_points_to_it(self):
        doc = (ROOT / "sites" / "shiken" / "docs" / "daily-routine.md").read_text(encoding="utf-8")
        for needle in ("06:30", "07:00", "morning_list.py", "日次報告_YYYY-MM-DD.md", "確定稿なし", "公開を止めて"):
            self.assertIn(needle, doc, needle)
        self.assertIn("docs/daily-routine.md", (ROOT / "sites" / "shiken" / "CLAUDE.md").read_text(encoding="utf-8"))


class ConfirmedArticleTest(unittest.TestCase):
    """The desk's confirmed article is poured in as it is: every sentence of the file is on the page, the pictures and the two links back are there."""

    @classmethod
    def setUpClass(cls):
        import re
        from sokuhou import newsite
        from sites.shiken import gen
        gen.write()
        cls.pages, _ = newsite.build_pages(ROOT / "sites" / "shiken", release=True, strict_seo=True)
        cls.html = cls.pages["takken-junbi/index.html"]
        cls.md = (ROOT / "sites" / "shiken" / "articles" / "takken-junbi.md").read_text(encoding="utf-8")
        cls.re = re

    def test_every_sentence_of_the_confirmed_text_is_on_the_page_unchanged(self):
        import html as _html
        re = self.re
        md = re.sub(r"\A\s*<!--.*?-->\s*", "", self.md, flags=re.S)
        t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", md)
        t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
        t = re.sub(r"^(#{1,3} |- )", "", t, flags=re.M)
        t = re.sub(r"^\|[-| ]+\|$", "", t, flags=re.M).replace("|", " ").replace("---", "")
        main = self.html[self.html.index("<main"):self.html.index("</main>")]
        main = re.sub(r"<script.*?</script>|<style.*?</style>|<img[^>]*>", "", main, flags=re.S)
        page_text = re.sub(r"\s+", "", _html.unescape(re.sub(r"<[^>]+>", " ", main)))
        sents = [s for s in re.split(r"(?<=[。！？])", re.sub(r"\s+", " ", t)) if len(re.sub(r"\s+", "", s)) > 6]
        self.assertGreater(len(sents), 50)
        missing = [s for s in sents if re.sub(r"\s+", "", s) not in page_text]
        self.assertEqual(missing, [])

    def test_the_two_pictures_the_alt_texts_and_the_two_links_back(self):
        re = self.re
        for alt in re.findall(r"!\[([^\]]*)\]", self.md):
            self.assertIn(f'alt="{alt}"', self.html)
        self.assertIn("/assets/articles/takken-junbi-trend.webp", self.html)
        self.assertIn("/assets/articles/takken-junbi-radar.webp", self.html)
        self.assertTrue((ROOT / "sites" / "shiken" / "assets" / "articles" / "takken-junbi-trend.webp").exists())
        for src in ("takken/index.html", "goukaku-ritsu/index.html"):
            self.assertIn('href="/takken-junbi/"', self.pages[src], src)          # the links to the article, from the detail page and from the feature
        self.assertIn('href="/takken-junbi/"', self.pages["yomimono/index.html"])
        self.assertIn("全部で11本", re.sub(r"<[^>]+>", "", self.pages["yomimono/index.html"]))
        self.assertNotIn("<!--", self.html[self.html.index("<main"):self.html.index("</main>")])    # the note for Claude Code is not on the page

    def test_no_link_to_a_course_or_an_outside_page_is_in_the_article(self):
        main = self.html[self.html.index("<main"):self.html.index("</main>")]
        self.assertNotRegex(main, r'href="https?://')


class ZenkiKokiDeskTextTest(unittest.TestCase):
    """/zenki-koki/ carries the desk's text (articles/zenki-koki.md) unchanged: every sentence and every table cell is on the page; the old sentences are gone."""

    @classmethod
    def setUpClass(cls):
        import re
        from sokuhou import newsite
        from sites.shiken import gen
        gen.write()
        cls.pages, _ = newsite.build_pages(ROOT / "sites" / "shiken", release=True, strict_seo=True)
        cls.html = cls.pages["zenki-koki/index.html"]
        cls.md = (ROOT / "sites" / "shiken" / "articles" / "zenki-koki.md").read_text(encoding="utf-8")
        cls.re = re

    def _page_text(self):
        import html as _html
        re = self.re
        main = self.html[self.html.index("<main"):self.html.index("</main>")]
        main = re.sub(r"<script.*?</script>|<style.*?</style>", "", main, flags=re.S)
        return re.sub(r"\s+", "", _html.unescape(re.sub(r"<[^>]+>", " ", main)))

    def test_every_sentence_and_cell_of_the_desk_text_is_on_the_page(self):
        re = self.re
        md = re.sub(r"\A\s*<!--.*?-->\s*", "", self.md, flags=re.S).replace("**", "")
        page_text = self._page_text()
        cells = [c.strip() for l in md.splitlines() if l.startswith("|") and not re.fullmatch(r"[|:\- ]+", l) for c in l.strip().strip("|").split("|")]
        self.assertGreater(len(cells), 10)
        sents = []
        for l in md.splitlines():
            if l.startswith("# ") or l.startswith("|") or l.strip() in ("", "---"):      # the h1 stays the site's own; the table is checked cell by cell
                continue
            l = re.sub(r"^(#{2,3} |- )", "", l).strip()
            sents += [x for x in re.split(r"(?<=[。！？])", l) if len(re.sub(r"\s+", "", x)) > 3]
        self.assertGreater(len(sents), 30)
        missing = [x for x in sents + cells if re.sub(r"\s+", "", x) not in page_text]
        self.assertEqual(missing, [])

    def test_the_old_text_is_gone_and_no_emphasis_marks_or_separator_remain(self):
        text = self._page_text()
        for old in ("第1段階選抜は、出願者が多いときに", "前期日程と後期日程を、どう使い分けるかは、それぞれ違います", "後期日程の日は大学ごとに違い、このページに出ているのは前期の日程です"):
            self.assertNotIn(old, text)
        self.assertNotIn("**", text)
        main = self.html[self.html.index("<main"):self.html.index("</main>")]
        self.assertNotIn("<!--", main)
        self.assertNotRegex(main, r'href="https?://')
        for path in ("/kokkoritsu/", "/kyotsu/", "/postmark/", "/nyushi/"):
            self.assertIn(f'href="{path}"', self.html)           # the related links stay
        self.assertIn('"BreadcrumbList"', self.html)

    def test_the_two_labelled_lists_are_lists(self):
        self.assertIn("<li>前期日程 試験：2月25日(木) ／ 合格発表：3月8日(月)</li>", self.html)
        self.assertIn("<li>後期日程 なし（※前期日程のみ実施）</li>", self.html)


if __name__ == "__main__":
    unittest.main()
