"""kuma: title・description・h1 に、情報元の名前(環境省・自治体の公式)を出さない。中身を表す言葉(年度・範囲・速報値)は残す。主題のページと本文のクレジットには触れない。"""
import re
import unittest

from sites.kuma import originnames as on


def page(title, h1="見出し", desc="説明", body="<p>出典: 環境省「クマに関する各種情報・取組」を加工して作成。</p>"):
    return (f'<head><title>{title}</title><meta name="description" content="{desc}"><meta property="og:title" content="{title}"></head>'
            f"<body><main><h1>{h1}</h1>{body}</main></body>")


class OriginNames(unittest.TestCase):
    def test_titles_h1_and_descriptions_lose_the_source_name(self):
        t = on.scrub("aichi/index.html", page("愛知県の熊(クマ)出没(令和7年度・環境省の速報値)", h1="愛知県のクマ出没(令和7年度・環境省の速報値)",
                                              desc="死亡事故は、環境省の一覧に1件載っています。環境省の速報値をもとにしています。"))
        self.assertIn("(令和7年度の速報値)", t)
        self.assertEqual(len(re.findall("環境省", re.sub(r"<p>.*?</p>", "", t))), 0)
        self.assertIn("公表された一覧に1件", t)

    def test_live_titles(self):
        t = on.scrub("live/akita/index.html", page("秋田県の熊(クマ)出没(令和8年度・秋田県の公式)", h1="最新のクマの目撃情報(自治体の公式)"))
        self.assertIn("(令和8年度)", t)
        self.assertNotIn("公式", re.sub(r"<p>.*?</p>", "", t))

    def test_the_credit_line_in_the_body_stays(self):
        self.assertIn("出典: 環境省「クマに関する各種情報・取組」を加工して作成。", on.scrub("deaths/index.html", page("死亡事故の一覧(環境省)")))

    def test_subject_pages_are_left_alone(self):
        p = page("環境省のクマに関するお知らせ(新着)")
        self.assertEqual(on.scrub("news/index.html", p), p)

    def test_negative_a_leftover_name_is_detected(self):
        leftover = re.compile(r"環境省|公式[)）に]")
        self.assertTrue(leftover.search("(令和7年度・環境省の速報値)"))              # the unscrubbed form is caught by the same scan
        self.assertFalse(leftover.search(re.sub(r"<p>.*?</p>", "", on.scrub("x/index.html", page("a(令和7年度・環境省の速報値)")))))


class RealBuild(unittest.TestCase):
    def test_no_page_but_the_subject_pages_names_the_ministry_in_title_or_h1(self):
        from tests.test_kuma_build import CFG, HAVE_PYPDF, LINKS, raw_data
        import tempfile
        from pathlib import Path
        from sites.kuma import build
        if not HAVE_PYPDF:
            self.skipTest("pypdf is not installed")
        with tempfile.TemporaryDirectory() as d:
            build.render_site(raw_data(), CFG, Path(d), release=True, links=LINKS)
            for f in Path(d).rglob("*.html"):
                rel = f.relative_to(d).as_posix()
                if rel in on.SUBJECT_PAGES:
                    continue
                t = f.read_text(encoding="utf-8")
                heads = re.findall(r"<title>(.*?)</title>|<h1[^>]*>(.*?)</h1>", t, re.S)
                self.assertFalse(any(re.search("環境省", x) for h in heads for x in h), rel)
