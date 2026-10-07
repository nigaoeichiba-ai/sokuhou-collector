"""Permitted captures from the ministry's PDF.  The expected rows are read a second way (pypdf's plain text lines, in reading order) so the
positional parser is not checked against itself."""
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import pypdf
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False

from sokuhou import run
from sokuhou.sources import env_capture_kuma as cap

PDF = (Path(__file__).parent / "fixtures" / "env_kuma_capture.pdf").read_bytes()


def plain_row(name: str) -> list[int]:
    """The 57 numbers of a prefecture's line in the PDF's plain text (19 fiscal years x total / killed / not killed)."""
    text = pypdf.PdfReader(io.BytesIO(PDF)).pages[0].extract_text()
    line = next(x for x in text.splitlines() if x.startswith(name + " "))
    return [int(v.replace(",", "")) for v in line.split()[1:]]


@unittest.skipUnless(HAVE_PYPDF, "pypdf is not installed")
class CaptureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cap.parse_captures(PDF)
        cls.by = {p["name"]: p["by_year"] for p in cls.d["prefectures"]}

    def test_layout(self):
        self.assertEqual(self.d["updated"], "2026-09-09")
        self.assertEqual(self.d["as_of"], "R08年7月末")
        self.assertEqual(self.d["years"], ["H20", "H21", "H22", "H23", "H24", "H25", "H26", "H27", "H28", "H29", "H30", "R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"])
        self.assertEqual([p["name"] for p in self.d["prefectures"]], cap.LISTED)
        self.assertEqual(len(cap.LISTED), 36)  # Hokkaido to Tokushima; Kagawa to Okinawa have no captures and are not in the table

    def test_every_prefecture_row_equals_the_same_line_read_in_plain_text_order(self):
        for name in ("北海道", "秋田", "岩手", "福井", "徳島", "長野"):
            flat = [v for y in self.d["years"] for v in self.by[name][y]]
            self.assertEqual(flat, plain_row(name), name)

    def test_the_national_row_and_the_two_species_add_up(self):
        for y in self.d["years"]:
            for k in range(3):
                self.assertEqual(sum(p["by_year"][y][k] for p in self.d["prefectures"]), self.d["national"][y][k])
                self.assertEqual(sum(s[y][k] for s in self.d["species"].values()), self.d["national"][y][k])
        self.assertEqual(self.d["species"]["ヒグマ"]["R07"], self.by["北海道"]["R07"])  # all brown bears are in Hokkaido

    def test_the_provisional_year_is_flagged_by_its_month_and_total_equals_killed_plus_released(self):
        for tri in self.by["北海道"].values():
            self.assertEqual(tri[0], tri[1] + tri[2])
        self.assertLess(self.d["national"]["R08"][0], self.d["national"]["R07"][0])  # July-end figures of a year still running

    def test_a_changed_layout_is_refused_not_guessed(self):
        with self.assertRaises(cap.EnvCaptureError):
            tokens = cap.env._tokens(PDF, 0)
            with mock.patch.object(cap.env, "_tokens", lambda pdf, n: [t for t in tokens if not (t["text"] == "秋田")]):
                cap.parse_captures(PDF)
        with self.assertRaises(cap.EnvCaptureError):
            tokens = cap.env._tokens(PDF, 0)
            broken = [dict(t, text="9,999") if t["text"] == "2,691" else t for t in tokens]  # one cell changed: the sums no longer match
            with mock.patch.object(cap.env, "_tokens", lambda pdf, n: broken):
                cap.parse_captures(PDF)

    def test_collect_without_network_and_registration(self):
        with mock.patch.object(cap, "fetch", lambda url: SimpleNamespace(body=PDF)):
            out = cap.collect()
        self.assertEqual(out["source_pdf"], "https://www.env.go.jp/nature/choju/effort/effort12/capture-qe.pdf")
        self.assertIn("env_capture_kuma", {s.name for s in run.GROUPS["daily"]})


if __name__ == "__main__":
    unittest.main()
