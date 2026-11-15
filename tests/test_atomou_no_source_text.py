"""atomou (owner decision D26, 2026-11-15): no page shows a source (出典 / 情報元) or links to one.  Allowed external links: ads (rel sponsored) and the privacy page's
links to the ad providers' own settings pages.  Allowed word 出典: the sakura page, whose data (気象庁, processed) needs it."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_atomou_build import BuildOnce  # noqa: E402

LINK = re.compile(r'<a\s[^>]*href="(https?://[^"]+)"[^>]*>', re.I)
WORD = re.compile(r"出典|情報元|情報源|参考資料|参考文献|確認元|公式日程の案内")
ALLOWED_HOST = ("google.com", "aboutads.info")
ALLOWED_WORD_PAGES = ("kyou/sakura/index.html",)


def violations(path: str, h: str, own_host: str = "atomou.com") -> list[str]:
    h = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", h)
    out = []
    for m in LINK.finditer(h):
        tag, url = m.group(0), m.group(1)
        if "sponsored" in tag or own_host in url or any(x in url for x in ALLOWED_HOST):
            continue
        out.append(f"{path}: external link {url}")
    if path not in ALLOWED_WORD_PAGES:
        text = re.sub(r"<[^>]+>", " ", h)
        for m in WORD.finditer(text):
            out.append(f"{path}: {text[max(0, m.start() - 10):m.end() + 15]!r}")
    return out


class NoSourceText(BuildOnce):
    def test_no_page_shows_a_source_or_links_to_one(self):
        bad = []
        for k, v in self.rel.items():
            if k.endswith(".html") and isinstance(v, str):
                bad += violations(k, v)
        self.assertEqual(bad[:10], [], f"{len(bad)} violations")


class Footer(NoSourceText):
    def test_every_page_has_the_one_general_sentence_in_the_footer(self):   # full build and the review copy
        from sites.atomou import review
        S = "公式の発表をはじめとする複数の情報をもとにしています。"
        for k in ("index.html", "e/" + next(x for x in self.rel if x.startswith("e/")).split("/")[1] + "/index.html"):
            self.assertIn(S, self.rel[k], k)
        pages = review.build_pages(__import__("tests.test_atomou_build", fromlist=["CFG"]).CFG, __import__("tests.test_atomou_build", fromlist=["TODAY"]).TODAY)
        self.assertIn(S, pages["index.html"])


class Checker(unittest.TestCase):   # the check finds what it is for (negative cases)
    def test_it_finds_a_source_link_and_a_source_word(self):
        self.assertTrue(violations("e/x/index.html", '<p><a href="https://www.mhlw.go.jp/x" rel="noopener">公式ページ</a></p>'))
        self.assertTrue(violations("e/x/index.html", "<p>出典: 気象庁</p>"))
        self.assertTrue(violations("kyou/season/index.html", "<p>出典: 気象庁</p>"))

    def test_it_lets_ads_and_the_allowed_pages_through(self):
        self.assertEqual(violations("e/x/index.html", '<a href="https://px.a8.net/x" rel="nofollow sponsored noopener">PR</a>'), [])
        self.assertEqual(violations("kyou/sakura/index.html", "<p>出典: 気象庁</p>"), [])


if __name__ == "__main__":
    unittest.main()
