"""trend: the 「イメージです。」 label tool never stacks a second label (2026-11-16: two labels, a big one over a small one, were on the same picture)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from PIL import Image

SITE = Path(__file__).resolve().parents[1] / "sites" / "trend"
spec = importlib.util.spec_from_file_location("trend_image_label", SITE / "tools" / "image_label.py")
label = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label)


class ImageLabel(unittest.TestCase):
    def test_a_font_is_found(self):                # never skipped: a missing font must fail, not hide
        self.assertTrue(Path(label.FONT).exists(), label.FONT)

    def pic(self):
        return Image.new("RGB", (1280, 720), (200, 60, 60))

    def test_a_plain_picture_has_no_label_and_gets_one(self):
        im = self.pic()
        self.assertFalse(label.has_label(im))
        out = label.add_label(im)
        self.assertTrue(label.has_label(out))

    def test_a_second_label_is_never_stacked(self):
        once = label.add_label(self.pic())
        twice = label.add_label(once)
        self.assertEqual(list(once.getdata()), list(twice.getdata()))      # the picture is unchanged: no second label

    def test_the_left_label_is_found_too(self):
        out = label.add_label(self.pic(), side="left", x_left=0.008, bottom_frac=0.995)
        self.assertTrue(label.has_label(out))


if __name__ == "__main__":
    unittest.main()
