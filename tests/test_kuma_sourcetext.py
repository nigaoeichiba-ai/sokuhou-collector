"""kuma: 本文・表・見出しに『環境省の表』型の出どころを出さない(オーナー指示 2026-11-15/17、窓口 2026-11-23)。残すのは、ライセンスの必須表記と、免責の説明だけ。"""
import re
import tempfile
import unittest
from pathlib import Path

from sites.kuma import originnames, sourcetext as st

CREDIT = "出典: 環境省「クマに関する各種情報・取組」の公表資料(速報値)を加工して作成。環境省が作成したものではありません。"
DISCLAIMER = "このサイトは、環境省や自治体が公表している情報を加工して作成したもので、環境省・自治体が作成したものではありません。"


def left(t: str) -> int:
    """『環境省』が、保たれる表記の外に何か所あるか(題・説明・h1 の例外は呼び出し側で扱う)。"""
    return len(re.findall("環境省", st.CREDIT.sub("", t)))


class Phrases(unittest.TestCase):
    def test_the_usual_phrases_become_general_ones(self):
        t = st.scrub("a/index.html", "<p>環境省の表では、秋田県全体の最多は7月です。環境省は、件数を翌月末に載せます。環境省が都道府県から聞き取った<strong>速報値</strong>です。"
                                     "人身被害の統計(環境省・令和8年10月末まで)に、<a>秋田県の出没件数・人身被害(環境省)</a>。環境省「クマ類の生態と現状」。</p>")
        self.assertEqual(left(t), 0)
        for s in ("公的な表では", "国は、件数", "国が都道府県から", "人身被害の統計(令和8年10月末まで)", "人身被害(公的な統計)", "国の公表資料。"):
            self.assertIn(s, t)

    def test_the_credit_and_the_disclaimer_stay_word_for_word(self):
        t = st.scrub("a/index.html", f"<p>{CREDIT}</p><p>{DISCLAIMER}</p><p>環境省の表は速報値です。</p>")
        self.assertIn(CREDIT, t)
        self.assertIn(DISCLAIMER, t)
        self.assertIn("公的な表は速報値です", t)
        self.assertEqual(left(t), 0)

    def test_subject_pages_keep_their_title_and_h1_as_originnames_decided(self):
        p = '<head><title>環境省のクマに関するお知らせ(新着)</title><meta name="description" content="環境省の発表を一覧にします。"></head><body><h1>環境省のお知らせ</h1><p>環境省の表です。</p></body>'
        t = st.scrub("news/index.html", p)
        self.assertIn("<title>環境省のクマに関するお知らせ(新着)</title>", t)
        self.assertIn("<h1>環境省のお知らせ</h1>", t)
        self.assertIn("<p>公的な表です。</p>", t)

    def test_negative_an_unscrubbed_page_is_detected(self):
        raw = f"<p>{CREDIT}</p><p>環境省の表では、秋田県の最多は7月です。</p>"
        self.assertEqual(left(raw), 1)                  # the scan finds the leftover…
        self.assertEqual(left(st.scrub("a/index.html", raw)), 0)    # …and the scrub removes it

    def test_non_html_files_are_not_touched(self):
        self.assertEqual(st.scrub("data/x.csv", "環境省の表"), "環境省の表")


class RealBuild(unittest.TestCase):
    def test_no_page_of_the_built_site_names_the_ministry_outside_its_credit(self):
        from sites.kuma import build
        from tests.test_kuma_build import CFG, HAVE_PYPDF, LINKS, raw_data
        if not HAVE_PYPDF:
            self.skipTest("pypdf is not installed")
        with tempfile.TemporaryDirectory() as d:
            build.render_site(raw_data(), CFG, Path(d), release=True, links=LINKS)
            checked = 0
            for f in list(Path(d).rglob("*.html")) + list(Path(d).rglob("*.xml")):
                rel = f.relative_to(d).as_posix()
                t = f.read_text(encoding="utf-8")
                if rel in originnames.SUBJECT_PAGES:
                    for rx in (originnames._TITLE, originnames._META, originnames._H1):
                        t = rx.sub("", t)
                self.assertEqual(left(t), 0, rel)
                checked += 1
            self.assertGreater(checked, 20)


if __name__ == "__main__":
    unittest.main()
