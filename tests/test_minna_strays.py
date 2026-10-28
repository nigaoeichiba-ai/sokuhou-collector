"""みんなのイラスト: no picture of the library or of the legacy sources has a stray piece at its edge (14 had one until 2026-10-28), and the check finds one when it is there."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from sites.minna import strays

HERE = Path(strays.__file__).resolve().parent


def make(draw_fn) -> Path:
    p = Path(tempfile.mkdtemp()) / "x.webp"
    im = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im))
    im.save(p, format="WEBP", lossless=True)
    return p


class Strays(unittest.TestCase):
    def test_a_piece_at_the_edge_is_found_and_one_inside_is_not(self):
        body = lambda d: d.ellipse((40, 20, 160, 140), fill=(255, 200, 60, 255))
        clean = make(body)
        self.assertEqual(strays.stray_pieces(clean), [])
        edge = make(lambda d: (body(d), d.rectangle((0, 70, 6, 90), fill=(255, 0, 0, 255))))
        self.assertEqual(len(strays.stray_pieces(edge)), 1)
        inside = make(lambda d: (body(d), d.rectangle((10, 70, 20, 90), fill=(255, 0, 0, 255))))     # a sparkle near the figure, away from the edge
        self.assertEqual(strays.stray_pieces(inside), [])

    def test_no_picture_of_the_site_has_one(self):
        bad = {}
        for f in sorted(list((HERE / "library").glob("*/*.webp")) + list((HERE / "src").glob("**/*.webp"))):
            s = strays.stray_pieces(f)
            if s:
                bad[f.relative_to(HERE).as_posix()] = s
        self.assertEqual(bad, {})


if __name__ == "__main__":
    unittest.main()
