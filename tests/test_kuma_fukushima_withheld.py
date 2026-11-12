"""Fukushima prefecture's own bear data is not published (the prefecture refused its use on an ad-supported site, 2026-11-12).

What must hold: the collector no longer reads it, the data file is gone, the real source list has no Fukushima entry, the prefecture's page (built
from the Ministry of the Environment's figures) says plainly why no sighting counts are shown, /live/fukushima/ is not built and its old address redirects."""
import tempfile
import unittest
from pathlib import Path

from sites.kuma import build, retired
from sites.kuma import live as live_mod
from sokuhou import run
from tests.test_kuma_build import CFG, HAVE_PYPDF
from tests.test_kuma_cite import make_raw, text_of

ROOT = Path(__file__).resolve().parent.parent
TODAY = __import__("datetime").date(2026, 10, 7)


class FukushimaWithheldTest(unittest.TestCase):
    def test_the_collector_does_not_read_fukushima(self):
        names = [s.name for s in run.GROUPS["kuma"]]
        self.assertTrue(names, "the kuma source list was not found")
        self.assertNotIn("fukushima_kuma", names)
        self.assertFalse((ROOT / "data" / "fukushima_kuma.json").exists())
        self.assertFalse((ROOT / "sokuhou" / "sources" / "fukushima_kuma.py").exists())

    def test_the_site_has_no_fukushima_source_and_says_so(self):
        self.assertNotIn("fukushima", live_mod.LIVE_SOURCES)
        self.assertIn("福島", live_mod.WITHHELD)

    def test_the_old_count_page_redirects_to_the_prefecture_page(self):
        pages = {"fukushima/index.html": "x", "index.html": "y"}
        self.assertEqual(retired.redirects(pages)["/live/fukushima/"], "/fukushima/")

    @unittest.skipUnless(HAVE_PYPDF, "needs the PDF fixtures")
    def test_the_prefecture_page_explains_and_has_no_sighting_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            files = build.render_site(make_raw(), CFG, out, release=True, prefs={}, today=TODAY)
            self.assertNotIn("live/fukushima/index.html", files)
            html = (out / "fukushima" / "index.html").read_text(encoding="utf-8")
            # the other prefectures' pages do not carry the note
            others = [f for f in files if f.endswith("/index.html") and f.count("/") == 1 and not f.startswith(("fukushima/", "live/"))]
            self.assertGreater(len(others), 5)
            for f in others:
                self.assertNotIn("県の許可が得られていないため", (out / f).read_text(encoding="utf-8"), f)
        text = text_of(html)
        self.assertIn("福島県は、県の許可が得られていないため、県が公表しているクマの目撃情報(市町村別の件数など)を載せていません", text)
        self.assertNotIn("福島県が公表している件数", text)
        self.assertNotIn('href="/live/fukushima/"', html)


if __name__ == "__main__":
    unittest.main()
