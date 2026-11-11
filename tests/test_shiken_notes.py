"""shiken-nittei.com, the owner's order of 2026-11-09: the site-wide notes (where the dates come from, when the days were counted, "check the official page") are said once, in the footer."""
from __future__ import annotations

import re
import html as _html
import unittest
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"
FOOTER = "日程は、各試験団体・省庁・教育委員会の発表や、報道・関連サイトの情報をもとにしています。最終的な日程は、主催団体の公式発表でご確認ください。"
GONE = ("日付は公式で確かめたものだけです", "時点の計算です", "未発表の日程は含みません", "このページの日付は、公式ページで直接読めたものだけです", "公式ページで確かめた金額だけです")
CLOSING = ("最終的な日程は、主催団体の公式発表でご確認ください。日程は変更されることがあります。", "申し込む前に、必ず確かめてください。")


def text(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return _html.unescape(re.sub(r"<[^>]+>", "\n", html))


class NotesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.shiken import gen
        gen.write()
        cls.pages, _ = newsite.build_pages(SITE, release=True, strict_seo=True)
        cls.html = {k: v for k, v in cls.pages.items() if isinstance(v, str) and k.endswith(".html") and "<footer" in v}
        cls.keep = gen.KEEP_NOTES

    def path_of(self, rel: str) -> str:
        return "/" + rel[: -len("index.html")] if rel.endswith("index.html") else "/" + rel

    def test_the_footer_sentence_is_on_every_page_once(self):
        for rel, h in self.html.items():
            foot = h[h.index("<footer"):]
            self.assertEqual(text(foot).count(FOOTER), 1, rel)
            self.assertEqual(text(h).count(FOOTER), 1, rel)                     # and nowhere else on the page

    def test_the_general_notes_are_gone_from_every_page_outside_the_temporary_set(self):
        for rel, h in self.html.items():
            if self.path_of(rel) in self.keep or rel in ("404.html",) or rel.startswith(("about", "privacy", "contact", "method")):
                continue
            t = text(h)
            for s in GONE:
                self.assertNotIn(s, t, f"{rel}: {s}")
            for s in CLOSING:
                self.assertNotIn(s, t, rel)
            self.assertNotIn("出典: ", t, rel)

    def test_the_last_update_day_stays_on_every_content_page(self):
        for rel, h in self.html.items():
            if rel.endswith("index.html") and rel != "index.html" and not rel.startswith(("about", "contact", "privacy", "corrections")):
                self.assertIn("最終更新日: ", text(h), rel)

    def test_the_method_page_is_in_the_footer_and_not_in_the_header(self):
        for rel, h in self.html.items():
            head = h[h.index("<header"):h.index("</header>")]
            foot = h[h.index("<footer"):]
            self.assertNotIn('href="/method/"', head, rel)
            self.assertIn('<a href="/method/">方法と出典</a>', foot, rel)

    def test_the_pages_that_keep_the_old_notes_for_now_are_listed_and_few(self):
        # TEMPORARY: they leave this set when the desk's added sentences arrive (each page then passes the 1,200 characters without the notes)
        self.assertLessEqual(len(self.keep), 2)
        for path in self.keep:
            self.assertIn("最終的な日程は、主催団体の公式発表でご確認ください。日程は変更されることがあります。", text(self.html[path.strip("/") + "/index.html"]), path)

    def test_the_desks_added_sentences_are_on_the_pages_word_for_word_and_the_pages_stay_indexed(self):
        from sites.shiken import gen
        from sokuhou import seokit
        for slug in gen.ADD_AFTER:
            page = self.html[slug + "/index.html"]
            sentence = gen.added_sentence(slug)
            self.assertGreaterEqual(len(sentence), 100, slug)
            if slug in gen.HELD:
                self.assertNotIn(sentence, text(page), slug)          # waits for the desk
            else:
                self.assertIn("".join(sentence.split()), "".join(text(page).split()), slug)
                self.assertNotIn("最終的な日程は、主催団体の公式発表でご確認ください。日程は変更されることがあります。", text(page), slug)   # and the old notes are gone
            self.assertNotIn("noindex", page[:3000], slug)
            self.assertGreaterEqual(seokit.visible_chars(page), 1200, slug)

    def test_the_note_of_the_article_stays(self):
        self.assertIn("この記事について", text(self.html["takken-junbi/index.html"]))


if __name__ == "__main__":
    unittest.main()
