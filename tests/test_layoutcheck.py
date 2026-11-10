"""The phone-width measuring tool must see the defects it exists for: a page wider than the phone, vertical text, header links squeezed to one
character, and a table that scrolls inside its frame (which is fine).  Needs Chrome, so the measuring tests skip without it; in CI the deploy job
runs the tool itself on the real build (and fails when Chrome is missing)."""
import tempfile
import unittest
from pathlib import Path

from sokuhou import layoutcheck

BASE = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>t</title></head><body>{}</body></html>'

PAGES = {
    "good": '<header><nav><a href="/">トップ</a> <a href="/a/">ひとつめ</a></nav></header><h1>見出しの文章です</h1><p>これは、ふつうの段落の文章です。</p>',
    "wide": '<h1>幅の広いページ</h1><div style="width:520px;background:#ccc">この枠が画面より広い</div>',
    "vertical": '<header><nav style="display:flex"><a href="/" style="width:8px;display:block;overflow-wrap:anywhere">トップページ</a></nav></header><p>x</p>',
    "squeezed": '<div style="display:flex"><p style="width:12px;overflow-wrap:anywhere">縦に潰れた長い文章</p><div style="width:200px">横</div></div>',
    "brokenimg": '<h1>画像</h1><img src="/missing.png" width="40" height="40" alt="">',
    "externalimg": '<h1>外部の画像</h1><img src="https://tiles.example.org/1.png" width="40" height="40" alt="">',
    "framed": '<h1>表</h1><div style="overflow-x:auto"><table style="width:900px"><tr><td>広い表</td></tr></table></div>',
}


def make_site(tmp: Path, names) -> None:
    urls = []
    for n in names:
        d = tmp / n
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(BASE.format(PAGES[n]), encoding="utf-8")
        urls.append(f"<url><loc>https://x.test/{n}/</loc></url>")
    (tmp / "index.html").write_text(BASE.format("<h1>top</h1>"), encoding="utf-8")
    urls.append("<url><loc>https://x.test/</loc></url>")
    (tmp / "sitemap.xml").write_text("<urlset>" + "".join(urls) + "</urlset>", encoding="utf-8")


class PickPagesTest(unittest.TestCase):
    def test_every_kind_of_page_is_sampled_and_the_home_page_comes_first(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            locs = ["/"] + [f"/gift/p{i}/" for i in range(30)] + ["/month/3/", "/tool/quiz/"]
            for p in locs:
                (t / p.strip("/")).mkdir(parents=True, exist_ok=True)
                (t / p.strip("/") / "index.html").write_text("x", encoding="utf-8")
            (t / "sitemap.xml").write_text("<urlset>" + "".join(f"<url><loc>https://x.test{p}</loc></url>" for p in locs) + "</urlset>", encoding="utf-8")
            picked = layoutcheck.pick_pages(t)
            self.assertEqual(picked[0], "/")
            for must in ("/month/3/", "/tool/quiz/"):
                self.assertIn(must, picked)
            self.assertLessEqual(sum(p.startswith("/gift/") for p in picked), 3)


@unittest.skipUnless(layoutcheck.find_chrome(), "Chrome is not installed")
class MeasureTest(unittest.TestCase):
    def run_pages(self, names):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            make_site(t, names)
            pages = [f"/{n}/" for n in names]
            return layoutcheck.problems_of(layoutcheck.measure(t, pages, widths=(300, 375)))

    def test_a_good_page_and_a_table_inside_a_scroll_frame_pass(self):
        self.assertEqual(self.run_pages(["good", "framed"]), [])

    def test_a_page_wider_than_the_phone_is_reported_with_the_element_that_sticks_out(self):
        p = self.run_pages(["wide"])
        self.assertTrue(any(x.startswith("[overflow]") and "/wide/ @300px" in x and "div" in x for x in p), p)

    def test_vertical_header_links_and_squeezed_text_are_reported(self):
        p = self.run_pages(["vertical", "squeezed"])
        self.assertTrue(any(x.startswith("[nav]") and "/vertical/" in x for x in p), p)
        self.assertTrue(any(x.startswith("[squeezed]") and "/squeezed/" in x for x in p), p)

    def test_a_broken_picture_of_the_site_is_reported_but_a_blocked_third_party_picture_is_not(self):
        p = self.run_pages(["brokenimg"])
        self.assertTrue(any(x.startswith("[images]") and "/brokenimg/" in x for x in p), p)
        self.assertEqual(self.run_pages(["externalimg"]), [])


@unittest.skipUnless(layoutcheck.find_chrome(), "Chrome is not installed")
class InnerScrollTest(unittest.TestCase):
    """The 2026-11-10 defect: nowrap cells made a table scroll sideways inside its frame on a PC screen, the last column was cut off, and the
    page itself did not overflow, so no earlier check saw it."""

    def run_wide(self, cell_style):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            body = ('<h1>表</h1><div style="overflow-x:auto;max-width:960px;margin:0 auto"><table style="width:100%"><tr>'
                    f'<td style="{cell_style}">' + '楽天お買い物マラソン2026年11月のジャンル祭と同時に開催(2026年11月4日から11月11日まで)' * 2 + '</td><td>開催中</td></tr></table></div>')
            (t / "index.html").write_text(BASE.format(body), encoding="utf-8")
            return layoutcheck.problems_of(layoutcheck.measure(t, ["/"], widths=layoutcheck.WIDE_WIDTHS))

    def test_a_table_that_scrolls_inside_its_frame_on_a_pc_screen_is_reported(self):
        p = self.run_wide("white-space:nowrap")
        self.assertTrue(any(x.startswith("[innerscroll]") and "@1280px" in x for x in p), p)
        self.assertTrue(any(x.startswith("[innerscroll]") and "@1919px" in x for x in p), p)

    def test_a_table_that_fits_passes(self):
        self.assertEqual(self.run_wide(""), [])

    def test_only_a_site_that_asks_gets_the_pc_width_measurement(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "index.html").write_text(BASE.format("<h1>x</h1>"), encoding="utf-8")
            self.assertFalse(layoutcheck.wants_wide(t))
            (t / "index.html").write_text(BASE.format('<meta name="layoutcheck" content="tables-fit"><h1>x</h1>'), encoding="utf-8")
            self.assertTrue(layoutcheck.wants_wide(t))


class MissingChromeTest(unittest.TestCase):
    def test_without_chrome_the_check_fails_instead_of_passing(self):
        real = layoutcheck.find_chrome
        layoutcheck.find_chrome = lambda: None
        try:
            with tempfile.TemporaryDirectory() as t:
                with self.assertRaises(RuntimeError):
                    layoutcheck.measure(Path(t), ["/"])
        finally:
            layoutcheck.find_chrome = real


if __name__ == "__main__":
    unittest.main()
